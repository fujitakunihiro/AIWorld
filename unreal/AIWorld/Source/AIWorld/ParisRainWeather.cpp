#include "ParisRainWeather.h"
#include "ParisDigitalTwin.h"
#include "ParisPedestrians.h"
#include "ParisTraffic.h"
#include "ProceduralMeshComponent.h"
#include "Components/AudioComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialParameterCollection.h"
#include "Materials/MaterialParameterCollectionInstance.h"
#include "Sound/SoundBase.h"
#include "Engine/World.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

namespace {
constexpr double Cell=600.,Radius=1800.,Height=2600.;
double Wrap(double Value,double Period){return Value-FMath::FloorToDouble(Value/Period)*Period;}
FIntPoint CellAt(const FVector& P){return FIntPoint(FMath::FloorToInt(P.X/Cell),FMath::FloorToInt(P.Y/Cell));}
void Topology(int32 Count,TArray<int32>& Indices,TArray<FVector2D>& UV){
    Indices.Reserve(Count*6);UV.Reserve(Count*4);
    for(int32 I=0;I<Count;I++){const int32 V=I*4;Indices.Append({V,V+1,V+2,V,V+2,V+3});UV.Append({{0,0},{0,1},{1,1},{1,0}});}
}
}

void UParisRainWeather::Initialize(){
    if(bInitialized)return;bInitialized=true;
    bMuted=FParse::Param(FCommandLine::Get(),TEXT("ParisTwinMuteSound"));
    auto Owner=GetOwner();
    auto Mesh=[&](const TCHAR* Name,const TCHAR* Path){
        auto C=NewObject<UProceduralMeshComponent>(Owner,Name);Owner->AddInstanceComponent(C);C->SetupAttachment(Owner->GetRootComponent());
        C->SetCollisionEnabled(ECollisionEnabled::NoCollision);C->SetCastShadow(false);C->SetCanEverAffectNavigation(false);C->bAffectDistanceFieldLighting=false;C->RegisterComponent();
        auto M=LoadObject<UMaterialInterface>(nullptr,Path);
        if(M)C->SetMaterial(0,M);else UE_LOG(LogTemp,Error,TEXT("Paris rain asset missing: %s. Run Build-ParisRain.ps1"),Path);
        return C;
    };
    Streaks=Mesh(TEXT("ParisRainStreaks"),TEXT("/Game/Weather/M_ParisRain"));
    Splashes=Mesh(TEXT("ParisRainSplashes"),TEXT("/Game/Weather/M_ParisRainSplash"));
    Collection=LoadObject<UMaterialParameterCollection>(nullptr,TEXT("/Game/Weather/MPC_ParisWeather"));
    auto Audio=[&](const TCHAR* Name,const TCHAR* Path){
        auto C=NewObject<UAudioComponent>(Owner,Name);Owner->AddInstanceComponent(C);C->SetupAttachment(Owner->GetRootComponent());
        C->bAutoActivate=false;C->bAutoDestroy=false;C->bAllowSpatialization=false;C->SetVolumeMultiplier(0);C->RegisterComponent();
        C->SetSound(LoadObject<USoundBase>(nullptr,Path));C->SetLowPassFilterEnabled(true);
        return C;
    };
    RainAudio=Audio(TEXT("ParisRainAudio"),TEXT("/Game/Weather/A_ParisRain"));
    DripAudio=Audio(TEXT("ParisRunoffAudio"),TEXT("/Game/Weather/A_ParisRunoff"));
}

void UParisRainWeather::ToggleSound(){if(!bInitialized)Initialize();bMuted=!bMuted;}

void UParisRainWeather::SampleSurfaces(const FVector& View){
    FCollisionQueryParams Query(SCENE_QUERY_STAT(ParisRainCover),false);
    if(auto PC=GetWorld()->GetFirstPlayerController())if(PC->GetPawn())Query.AddIgnoredActor(PC->GetPawn());
    if(auto Scene=Cast<AParisTwinScene>(GetOwner())){if(Scene->Crowd)Query.AddIgnoredActor(Scene->Crowd);if(Scene->Traffic)Query.AddIgnoredActor(Scene->Traffic);}
    const FIntPoint Centre=CellAt(View);TMap<FIntPoint,FParisRainSurface> Next;
    // Reuse world cells as the viewer moves; no rotation of the rain volume.
    for(int32 X=-5;X<=5;X++)for(int32 Y=-5;Y<=5;Y++){
        const FIntPoint Key=Centre+FIntPoint(X,Y);
        if(auto Found=Surfaces.Find(Key))if(Found->Valid&&int32(GetTypeHash(Key)&7)!=FMath::FloorToInt(Elapsed*3.)%8){Next.Add(Key,*Found);continue;}
        const FVector P((Key.X+.5)*Cell,(Key.Y+.5)*Cell,View.Z);
        FHitResult Hit;FParisRainSurface S;
        if(GetWorld()->LineTraceSingleByChannel(Hit,P+FVector(0,0,20000),P-FVector(0,0,60000),ECC_Visibility,Query)){
            S.Point=Hit.ImpactPoint;S.Normal=Hit.ImpactNormal;S.Valid=S.Normal.Z>.6;
        }
        Next.Add(Key,S);
    }
    Surfaces=MoveTemp(Next);
    // Listener probes are separate from the rain grid so shelter responds at doors.
    int32 Open=0;
    for(const FVector2D Offset:{FVector2D(0,0),FVector2D(65,0),FVector2D(-65,0),FVector2D(0,65),FVector2D(0,-65)}){
        const FVector A=View+FVector(Offset.X,Offset.Y,15);FHitResult Hit;
        if(!GetWorld()->LineTraceSingleByChannel(Hit,A,A+FVector(0,0,20000),ECC_Visibility,Query))Open++;
    }
    TargetExposure=Open/5.f;
}

void UParisRainWeather::UpdateGeometry(const FVector& View,int32 Quality){
    const int32 Count=Quality==0?650:Quality==1?2800:4400,SplashCount=Quality==0?48:Quality==1?100:160;
    const FVector Anchor(View.X,View.Y,0);Streaks->SetWorldLocation(Anchor);Splashes->SetWorldLocation(Anchor);
    const bool Rebuild=LastQuality!=Quality;LastQuality=Quality;
    DropVertices.SetNum(Count*4);DropNormals.SetNum(Count*4);DropColors.SetNum(Count*4);
    SplashVertices.SetNum(SplashCount*4);SplashNormals.SetNum(SplashCount*4);SplashColors.SetNum(SplashCount*4);
    if(ImpactCycles.Num()!=SplashCount){ImpactCycles.Init(-1,SplashCount);ImpactSurfaces.SetNum(SplashCount);}
    FCollisionQueryParams ImpactQuery(SCENE_QUERY_STAT(ParisRainImpact),false);
    if(auto PC=GetWorld()->GetFirstPlayerController())if(PC->GetPawn())ImpactQuery.AddIgnoredActor(PC->GetPawn());
    if(auto Scene=Cast<AParisTwinScene>(GetOwner())){if(Scene->Crowd)ImpactQuery.AddIgnoredActor(Scene->Crowd);if(Scene->Traffic)ImpactQuery.AddIgnoredActor(Scene->Traffic);}
    const auto Scene=Cast<AParisTwinScene>(GetOwner());const float Light=Scene&&Scene->TimeOfDayPreset==2?.16f:Scene&&Scene->TimeOfDayPreset==1?.65f:1.f;
    FRandomStream Random(61723);VisibleDrops=VisibleSplashes=0;
    for(int32 I=0;I<Count;I++){
        const float Speed=Random.FRandRange(720,1020),Width=Random.FRandRange(.38,.85),Length=Random.FRandRange(18,38);
        const FVector Seed(Random.FRandRange(-Radius,Radius),Random.FRandRange(-Radius,Radius),Random.FRandRange(0,Height));
        const FVector P(View.X+Wrap(Seed.X+Elapsed*110.-View.X+Radius,Radius*2)-Radius,
            View.Y+Wrap(Seed.Y+Elapsed*38.-View.Y+Radius,Radius*2)-Radius,
            View.Z+1600.-Wrap(Seed.Z+Elapsed*Speed+View.Z,Height));
        const auto S=Surfaces.Find(CellAt(P));
        const float Floor=S&&S->Valid?S->Point.Z:View.Z-2000;
        const float Distance=FVector::Dist(P,View);
        const float Fade=FMath::Clamp((Distance-80.f)/180.f,0.f,1.f)*FMath::Clamp((Radius-Distance)/600.f,0.f,1.f);
        const bool Visible=P.Z>Floor+Length&&Fade>0;
        if(Visible)VisibleDrops++;
        const FVector Direction=FVector(110.,38.,-Speed).GetSafeNormal();
        FVector Side=FVector::CrossProduct(Direction,(View-P).GetSafeNormal()).GetSafeNormal()*Width;
        const FVector A=P-Anchor,B=A+Direction*Length;
        DropVertices[I*4]=A-Side;DropVertices[I*4+1]=B-Side;DropVertices[I*4+2]=B+Side;DropVertices[I*4+3]=A+Side;
        for(int32 J=0;J<4;J++){DropNormals[I*4+J]=FVector::UpVector;DropColors[I*4+J]=FLinearColor(.70*Light,.77*Light,.82*Light,Visible?Fade*Intensity*.5f:0);}
    }
    // Independent short-lived impacts; every respawn chooses a new exposed cell.
    for(int32 I=0;I<SplashCount;I++){
        const double Clock=Elapsed*2.8+I*.61803398875;const int32 Cycle=FMath::FloorToInt(Clock);const float Age=Wrap(Clock,1.);
        auto& S=ImpactSurfaces[I];
        if(ImpactCycles[I]!=Cycle){
            ImpactCycles[I]=Cycle;FRandomStream R(I*1597+Cycle*7919);const FVector Aim=View+FVector(R.FRandRange(-1800,1800),R.FRandRange(-1800,1800),0);FHitResult Hit;
            S.Valid=GetWorld()->LineTraceSingleByChannel(Hit,Aim+FVector(0,0,20000),Aim-FVector(0,0,60000),ECC_Visibility,ImpactQuery)&&Hit.ImpactNormal.Z>.6;
            if(S.Valid){S.Point=Hit.ImpactPoint;S.Normal=Hit.ImpactNormal;}
        }
        const bool Visible=S.Valid&&S.Point.Z<View.Z+150&&FVector::Dist2D(S.Point,View)<1800;
        const FVector P=(Visible?S.Point:View)+S.Normal*.8;
        const FVector Normal=Visible?S.Normal:FVector::UpVector,Tangent=FVector::CrossProduct(FVector::RightVector,Normal).GetSafeNormal(),Bitangent=FVector::CrossProduct(Normal,Tangent);
        const float Size=5.f+Age*14.f;const FVector A=P-Anchor;
        SplashVertices[I*4]=A-Tangent*Size-Bitangent*Size;SplashVertices[I*4+1]=A-Tangent*Size+Bitangent*Size;
        SplashVertices[I*4+2]=A+Tangent*Size+Bitangent*Size;SplashVertices[I*4+3]=A+Tangent*Size-Bitangent*Size;
        for(int32 J=0;J<4;J++){SplashNormals[I*4+J]=Normal;SplashColors[I*4+J]=FLinearColor(.32*Light,.39*Light,.43*Light,Visible?Intensity*FMath::Square(1-Age)*.45f:0);}
        if(Visible)VisibleSplashes++;
    }
    if(Rebuild){
        TArray<int32> Indices;DropUV.Reset();Topology(Count,Indices,DropUV);
        Streaks->CreateMeshSection_LinearColor(0,DropVertices,Indices,DropNormals,DropUV,DropColors,{},false);
        Indices.Reset();SplashUV.Reset();Topology(SplashCount,Indices,SplashUV);
        Splashes->CreateMeshSection_LinearColor(0,SplashVertices,Indices,SplashNormals,SplashUV,SplashColors,{},false);
    }else{
        Streaks->UpdateMeshSection_LinearColor(0,DropVertices,DropNormals,DropUV,DropColors,{},false);
        Splashes->UpdateMeshSection_LinearColor(0,SplashVertices,SplashNormals,SplashUV,SplashColors,{},false);
    }
}

void UParisRainWeather::Advance(float Delta,bool Raining,int32 Quality){
    if(!bInitialized){if(!Raining)return;Initialize();}
    const float Dt=FMath::Clamp(Delta,0.f,.1f);Elapsed+=Dt;SampleElapsed+=Dt;
    Intensity=FMath::FInterpTo(Intensity,Raining?1.f:0.f,Dt,Raining?1.6f:2.5f);
    Wetness=FMath::Clamp(Wetness+(Raining?.11f:-.018f)*Dt,0.f,1.f);
    if(Collection)if(auto Instance=GetWorld()->GetParameterCollectionInstance(Collection)){
        Instance->SetScalarParameterValue(TEXT("RainIntensity"),Intensity);Instance->SetScalarParameterValue(TEXT("Wetness"),Wetness);
    }
    auto PC=GetWorld()->GetFirstPlayerController();if(!PC)return;
    FVector View;FRotator Rotation;PC->GetPlayerViewPoint(View,Rotation);
    if(Intensity>.005f){
        if(SampleElapsed>.3){SampleElapsed=0;SampleSurfaces(View);}
        UpdateGeometry(View,FMath::Clamp(Quality,0,2));
    }
    Streaks->SetVisibility(Intensity>.005f);Splashes->SetVisibility(Intensity>.005f);
    Exposure=FMath::FInterpTo(Exposure,TargetExposure,Dt,3.f);
    for(auto C:{RainAudio.Get(),DripAudio.Get()}){
        const float Volume=bMuted?0.f:Intensity*(C==RainAudio?FMath::Lerp(.14f,.65f,Exposure):FMath::Lerp(.32f,.16f,Exposure));
        C->SetVolumeMultiplier(Volume);C->SetLowPassFilterFrequency(C==RainAudio?FMath::Lerp(1400.f,18000.f,Exposure):9000.f);
        if(Volume>.001f&&!C->IsPlaying()&&C->Sound)C->Play();else if(Volume<=.001f&&C->IsPlaying())C->Stop();
    }
}

void UParisRainWeather::EndPlay(const EEndPlayReason::Type Reason){
    if(RainAudio)RainAudio->Stop();if(DripAudio)DripAudio->Stop();
    if(Collection)if(auto Instance=GetWorld()->GetParameterCollectionInstance(Collection)){
        Instance->SetScalarParameterValue(TEXT("RainIntensity"),0);Instance->SetScalarParameterValue(TEXT("Wetness"),0);
    }
    Super::EndPlay(Reason);
}
