#include "ParisSoundscape.h"
#include "ParisDigitalTwin.h"
#include "ParisCruise.h"
#include "ParisTraffic.h"
#include "ParisRainWeather.h"
#include "WorldProtocol.h"
#include "Components/AudioComponent.h"
#include "Sound/SoundWave.h"
#include "Sound/SoundAttenuation.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Serialization/JsonSerializer.h"
using namespace AIWorld;

namespace {
const TCHAR* Names[]={TEXT("Bell"),TEXT("Crowd"),TEXT("Seine"),TEXT("Ferry"),TEXT("Pigeon"),TEXT("Siren")};
const TCHAR* Labels[]={TEXT("Notre-Dame bells"),TEXT("Paris market crowd"),TEXT("Seine water"),TEXT("Ferry engine"),TEXT("Pigeon coo"),TEXT("French two-tone siren")};
const float Outer[]={60000,5500,7500,16000,4000,35000,5500};
bool VectorValue(const TSharedPtr<FJsonValue>& V,FVector& P){
    if(!V||V->Type!=EJson::Array||V->AsArray().Num()!=3)return false;const auto& A=V->AsArray();
    double X,Y,Z;if(!A[0]->TryGetNumber(X)||!A[1]->TryGetNumber(Y)||!A[2]->TryGetNumber(Z))return false;
    P=FVector(X,Y,Z);return !P.ContainsNaN();
}
}
AParisSoundscape::AParisSoundscape(){
    RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("SoundscapeRoot"));PrimaryActorTick.bCanEverTick=true;PrimaryActorTick.TickInterval=.2f;
    Tags.Add(TEXT("ParisSoundscape"));
}
UAudioComponent* AParisSoundscape::MakeChannel(const TCHAR* Name,USoundWave* Wave,float Inner,float Range,bool Spatial){
    auto C=NewObject<UAudioComponent>(this,Name);AddInstanceComponent(C);C->SetupAttachment(RootComponent);
    C->bAutoActivate=false;C->bAutoDestroy=false;C->bAllowSpatialization=Spatial;C->bIsUISound=!Spatial;
    C->SetVolumeMultiplier(0);C->RegisterComponent();C->SetSound(Wave);
    if(Spatial){
        FSoundAttenuationSettings Settings;Settings.bAttenuate=true;Settings.bSpatialize=true;
        Settings.DistanceAlgorithm=EAttenuationDistanceModel::NaturalSound;Settings.FalloffMode=ENaturalSoundFalloffMode::Silent;Settings.dBAttenuationAtMax=-42;
        Settings.AttenuationShape=EAttenuationShape::Sphere;Settings.AttenuationShapeExtents=FVector(Inner,0,0);Settings.FalloffDistance=Range-Inner;
        Settings.bEnableOcclusion=true;Settings.OcclusionTraceChannel=ECC_Visibility;Settings.OcclusionVolumeAttenuation=.42f;Settings.OcclusionLowPassFilterFrequency=1600;
        C->OcclusionCheckInterval=.5f;C->AdjustAttenuation(Settings);
    }
    return C;
}
bool AParisSoundscape::Initialize(AParisTwinScene* InScene,const TSharedPtr<FJsonObject>& Data){
    if(Scene.IsValid())return true;if(!InScene||!Data)return false;Scene=InScene;SetOwner(InScene);
    bMuted=FParse::Param(FCommandLine::Get(),TEXT("ParisTwinMuteSound"));
    for(const auto Name:Names){auto W=LoadObject<USoundWave>(nullptr,*(FString(TEXT("/Game/Soundscape/A_Paris"))+Name));if(!W||W->NumChannels!=1)return false;Waves.Add(W);}
    for(int32 I=0;I<7;I++)Channels.Add(MakeChannel(*FString::Printf(TEXT("ParisAmbient_%s%s"),Names[I==6?1:I],I==6?TEXT("_B"):TEXT("")),Waves[I==6?1:I],I==0?4000:I==5?1600:500,Outer[I]));
    Preview=MakeChannel(TEXT("ParisSoundPreview"),nullptr,0,1,false);
    for(TActorIterator<AParisCruise> It(GetWorld());It;++It)if(It->bReady){Ship=*It;break;}
    const float WaterZ=Ship.IsValid()?Ship->WaterLevel:-850;
    for(const auto& V:Array(Data,TEXT("pick_features"))){auto J=V->AsObject();const FString Kind=String(J,TEXT("kind")),ID=String(J,TEXT("id"));
        FVector P;
        if(Kind==TEXT("business")&&VectorValue(J->TryGetField(TEXT("point_cm")),P)){
            const FString Category=String(Object(J,TEXT("properties")),TEXT("category"));
            if(Category==TEXT("cafe")||Category==TEXT("restaurant")||Category==TEXT("bar")||Category==TEXT("supermarket")||Category==TEXT("convenience")||Category==TEXT("florist")||Category==TEXT("bakery")||Category==TEXT("deli"))Markets.Add({P+FVector(0,0,140),ID});
        }
        if((Kind==TEXT("street_bench")||Kind==TEXT("street_tree"))&&VectorValue(J->TryGetField(TEXT("point_cm")),P))BirdPlaces.Add({P+FVector(0,0,45),ID});
        if(Kind==TEXT("water"))for(const auto& Polygon:Array(J,TEXT("polygons_cm"))){
            if(Polygon->AsArray().IsEmpty())continue;const auto& Ring=Polygon->AsArray()[0]->AsArray();
            for(int32 I=1;I<Ring.Num();I++){FVector A,B;if(!VectorValue(Ring[I-1],A)||!VectorValue(Ring[I],B))continue;
                const double Bound=InScene->Extent*50.;
                if((FMath::Abs(A.X-B.X)<.01&&FMath::Abs(FMath::Abs(A.X)-Bound)<1)||(FMath::Abs(A.Y-B.Y)<.01&&FMath::Abs(FMath::Abs(A.Y)-Bound)<1))continue;
                A.Z=B.Z=WaterZ+30;WaterEdges.Add({A,B,ID});
            }
        }
    }
    Bell={InScene->QualityCentre+FVector(0,0,4300),TEXT("osm/way/201611261")};
    FString Text;TSharedPtr<FJsonObject> Architecture;
    if(FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("Data/paris-photo-architecture.json")))&&FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Architecture)){
        auto Frame=Object(Architecture,TEXT("local_frame"));FVector Front,Across,Depth;
        if(VectorValue(Frame->TryGetField(TEXT("front_cm")),Front)&&VectorValue(Frame->TryGetField(TEXT("across")),Across)&&VectorValue(Frame->TryGetField(TEXT("depth")),Depth))Bell.Position=Front+Across*1450+Depth*600+FVector(0,0,4300);
    }
    if(BirdPlaces.IsEmpty())BirdPlaces.Add({InScene->QualityCentre+FVector(500,0,45),TEXT("inferred:cathedral_plaza")});
    return true;
}
bool AParisSoundscape::NearestWater(const FVector& View,FParisSoundAnchor& Result) const {
    double Best=DBL_MAX;bool Found=false;
    for(const auto& E:WaterEdges){FVector D=E.B-E.A;const double T=FMath::Clamp(FVector::DotProduct(FVector(View.X,View.Y,E.A.Z)-E.A,D)/FMath::Max(D.SizeSquared(),1.),0.,1.);const FVector P=E.A+T*D;
        const double Distance=FVector::DistSquared2D(P,View);if(Distance<Best){Best=Distance;Result={P,E.SourceID};Found=true;}}
    return Found;
}
void AParisSoundscape::UpdateLoop(int32 Index,const FVector& P,float Gain,bool Enabled,float Start){
    auto C=Channels[Index];C->SetWorldLocation(P);C->SetVolumeMultiplier(bMuted||!Enabled?0:Gain);
    if(!bMuted&&Enabled&&Gain>.001f){if(!C->IsPlaying())C->Play(Start);}else if(C->IsPlaying())C->Stop();
}
void AParisSoundscape::SetMuted(bool Muted){
    bMuted=Muted;if(Muted){for(auto C:Channels){C->SetVolumeMultiplier(0);C->Stop();}Preview->SetVolumeMultiplier(0);Preview->Stop();PreviewRemaining=0;}
}
void AParisSoundscape::Audition(int32 Kind){
    if(bMuted){if(GEngine)GEngine->AddOnScreenDebugMessage(-1,3,FColor::Yellow,TEXT("Sound is muted [F11]"));return;}
    PreviewKind=Kind>=0?FMath::Clamp(Kind,0,5):(PreviewKind+1)%6;
    Preview->Stop();Preview->SetSound(Waves[PreviewKind]);Preview->SetVolumeMultiplier(.35f);Preview->Play();PreviewRemaining=FMath::Min(9.f,Waves[PreviewKind]->Duration);
    if(GEngine)GEngine->AddOnScreenDebugMessage(-1,4,FColor::Cyan,FString::Printf(TEXT("Listen: %s [F12: next]"),Labels[PreviewKind]));
}
void AParisSoundscape::Tick(float Delta){
    Super::Tick(Delta);auto S=Scene.Get();if(!S)return;Elapsed+=FMath::Clamp(Delta,0.f,1.f);
    if(PreviewRemaining>0){PreviewRemaining-=Delta;if(PreviewRemaining<=0)Preview->Stop();}
    auto PC=GetWorld()->GetFirstPlayerController();if(!PC)return;FVector View;FRotator Rotation;PC->GetPlayerViewPoint(View,Rotation);
    const bool Night=S->TimeOfDayPreset==2;
    const float CrowdGain=(Night?.065f:.30f)*(S->bRainyWeather?.72f:1.f);
    TArray<int32> Order;for(int32 I=0;I<Markets.Num();I++)Order.Add(I);Order.Sort([&](int32 A,int32 B){return FVector::DistSquared2D(View,Markets[A].Position)<FVector::DistSquared2D(View,Markets[B].Position);});
    int32 First=INDEX_NONE,Second=INDEX_NONE;
    if(!Order.IsEmpty()){First=Order[0];for(int32 I:Order)if(FVector::DistSquared2D(Markets[I].Position,Markets[First].Position)>FMath::Square(1600.)){Second=I;break;}}
    for(int32 I=0;I<2;I++){const int32 Anchor=I==0?First:Second;const FVector P=Markets.IsValidIndex(Anchor)?Markets[Anchor].Position:View;
        UpdateLoop(I==0?1:6,P,CrowdGain*(I==0?1.f:.55f),S->bPeople&&Markets.IsValidIndex(Anchor)&&FVector::Dist(View,P)<Outer[1],I==0?0:11.2f);}
    FParisSoundAnchor Water;const bool HasWater=NearestWater(View,Water);UpdateLoop(2,Water.Position,.44f,HasWater&&FVector::Dist(View,Water.Position)<Outer[2]);
    if(Ship.IsValid()&&Ship->bReady){const FVector P=Ship->GetActorLocation()+FVector(0,0,130);UpdateLoop(3,P,.38f,FVector::Dist(View,P)<Outer[3]);Channels[3]->SetPitchMultiplier(.84f+.16f*FMath::Clamp(float(Ship->Speed/200.),0.f,1.f));}
    else UpdateLoop(3,View,0,false);
    if(Elapsed>=NextBell){NextBell=Elapsed+Random.FRandRange(240,420);if(!bMuted&&FVector::Dist(View,Bell.Position)<Outer[0]){auto C=Channels[0];C->SetWorldLocation(Bell.Position);C->SetVolumeMultiplier(Night?.42f:.62f);C->Play();BellEvents++;}}
    if(Elapsed>=NextBird){NextBird=Elapsed+Random.FRandRange(Night?60:16,Night?120:38);const FParisSoundAnchor* Best=nullptr;double Distance=DBL_MAX;
        for(const auto& A:BirdPlaces){const double D=FVector::DistSquared2D(A.Position,View);if(D<Distance){Distance=D;Best=&A;}}
        if(Best&&!bMuted&&Distance<FMath::Square(double(Outer[4]))){auto C=Channels[4];C->SetWorldLocation(Best->Position);C->SetVolumeMultiplier((Night?.08f:.34f)*(S->bRainyWeather?.65f:1.f));C->Play();PigeonEvents++;}}
    if(Elapsed>=NextSiren){NextSiren=Elapsed+Random.FRandRange(125,245);
        if(!bMuted&&S->bTraffic&&S->Traffic){const auto& Cars=S->Traffic->Vehicles();double Best=DBL_MAX;int32 Candidate=INDEX_NONE;
            for(int32 I=0;I<Cars.Num();I++)if(Cars[I].bActive&&Cars[I].bMoving){const double D=FVector::DistSquared2D(View,Cars[I].Position);if(D>FMath::Square(4500.)&&D<FMath::Square(23000.)&&D<Best){Best=D;Candidate=I;}}
            if(Candidate!=INDEX_NONE){SirenVehicle=Candidate;SirenRemaining=Waves[5]->Duration;PreviousSirenPosition=Cars[Candidate].Position;Channels[5]->SetWorldLocation(PreviousSirenPosition+FVector(0,0,100));Channels[5]->SetVolumeMultiplier(.22f);Channels[5]->Play();SirenEvents++;}
        }
    }
    if(SirenRemaining>0){SirenRemaining-=Delta;const auto Traffic=S->Traffic.Get();
        if(!bMuted&&S->bTraffic&&Traffic&&Traffic->Vehicles().IsValidIndex(SirenVehicle)&&Traffic->Vehicles()[SirenVehicle].bActive){
            const FVector P=Traffic->Vehicles()[SirenVehicle].Position;const double Jump=FVector::Dist(P,PreviousSirenPosition);
            if(Jump>2500){Channels[5]->Stop();SirenRemaining=0;}
            else{const FVector Velocity=(P-PreviousSirenPosition)/FMath::Max(double(Delta),.01);const double Radial=FVector::DotProduct(Velocity,(P-View).GetSafeNormal());Channels[5]->SetWorldLocation(P+FVector(0,0,100));Channels[5]->SetPitchMultiplier(FMath::Clamp(34300./(34300.+Radial),.94,1.06));Channels[5]->SetVolumeMultiplier(.22f*FMath::Clamp(float(SirenRemaining/.8),0.f,1.f));}
            PreviousSirenPosition=P;
        }else{Channels[5]->Stop();SirenRemaining=0;}
    }
    ActiveVoices=Preview->IsPlaying()?1:0;for(auto C:Channels)ActiveVoices+=C->IsPlaying()?1:0;
}
void AParisSoundscape::AddStats(const TSharedPtr<FJsonObject>& Report) const {
    Report->SetNumberField(TEXT("soundscape_channels"),Channels.Num()+1);Report->SetNumberField(TEXT("soundscape_active_voices"),ActiveVoices);
    Report->SetNumberField(TEXT("soundscape_crowd_anchors"),Markets.Num());Report->SetNumberField(TEXT("soundscape_water_edges"),WaterEdges.Num());Report->SetNumberField(TEXT("soundscape_pigeon_anchors"),BirdPlaces.Num());
    Report->SetNumberField(TEXT("soundscape_bell_events"),BellEvents);Report->SetNumberField(TEXT("soundscape_pigeon_events"),PigeonEvents);Report->SetNumberField(TEXT("soundscape_siren_events"),SirenEvents);
    Report->SetBoolField(TEXT("soundscape_muted"),bMuted);Report->SetBoolField(TEXT("soundscape_ferry_attached"),Ship.IsValid());
    Report->SetStringField(TEXT("soundscape_bell_source_id"),Bell.SourceID);Report->SetStringField(TEXT("soundscape_provenance"),TEXT("Historic Emmanuel recording, Paris market/Seine recordings, recorded pigeon, authored French siren and original ferry synthesis; placements and event schedules inferred."));
}
void AParisSoundscape::EndPlay(const EEndPlayReason::Type Reason){for(auto C:Channels)if(C)C->Stop();if(Preview)Preview->Stop();Super::EndPlay(Reason);}
void CreateParisSoundscape(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Data){
    for(TActorIterator<AParisSoundscape> It(Scene->GetWorld());It;++It)if(It->GetOwner()==Scene)return;
    auto A=Scene->GetWorld()->SpawnActor<AParisSoundscape>();if(!A->Initialize(Scene,Data)){A->Destroy();UE_LOG(LogTemp,Error,TEXT("Paris sound assets missing; run Build-ParisSoundscape.ps1"));}
}
void SetParisSoundscapeMuted(UWorld* World,bool Muted){for(TActorIterator<AParisSoundscape> It(World);It;++It)It->SetMuted(Muted);}
void AuditionParisSoundscape(UWorld* World){for(TActorIterator<AParisSoundscape> It(World);It;++It){It->Audition();break;}}
void AddParisSoundscapeStats(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Report){for(TActorIterator<AParisSoundscape> It(Scene->GetWorld());It;++It)if(It->GetOwner()==Scene)It->AddStats(Report);}
