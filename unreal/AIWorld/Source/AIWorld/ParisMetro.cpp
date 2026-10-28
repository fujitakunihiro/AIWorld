#include "ParisMetro.h"
#include "ParisDigitalTwin.h"
#include "ParisWalker.h"
#include "Engine/World.h"
#include "Materials/MaterialInterface.h"
#include "ProceduralMeshComponent.h"
#include "KismetProceduralMeshLibrary.h"
#include "Camera/CameraComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/TextRenderComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "WorldProtocol.h"
using namespace AIWorld;
namespace {
struct MeshBuffer {
    TArray<FVector> V,N;TArray<int32> I;TArray<FVector2D> UV;TArray<FProcMeshTangent> T;TArray<FLinearColor> C;
    void Box(FVector Center,FVector Extent,FLinearColor Color){
        TArray<FVector> V0,N0;TArray<int32> I0;TArray<FVector2D> U0;TArray<FProcMeshTangent> T0;
        UKismetProceduralMeshLibrary::GenerateBoxMesh(Extent,V0,I0,N0,U0,T0);const int32 Base=V.Num();
        for(const auto& P:V0)V.Add(P+Center);for(auto Index:I0)I.Add(Base+Index);N.Append(N0);UV.Append(U0);T.Append(T0);for(int32 J=0;J<V0.Num();J++)C.Add(Color);
    }
    void Apply(UProceduralMeshComponent* Mesh,UMaterialInterface* Mat,bool Collision){Mesh->bUseComplexAsSimpleCollision=true;Mesh->CreateMeshSection_LinearColor(0,V,I,N,UV,C,T,Collision);Mesh->SetMaterial(0,Mat);Mesh->SetCollisionEnabled(Collision?ECollisionEnabled::QueryAndPhysics:ECollisionEnabled::NoCollision);Mesh->SetCanEverAffectNavigation(false);}
};
}
AParisMetro::AParisMetro(){
    PrimaryActorTick.bCanEverTick=true;RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("MetroRoot"));
    StationMesh=CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("MetroStation"));StationMesh->SetupAttachment(RootComponent);
    TrainRoot=CreateDefaultSubobject<USceneComponent>(TEXT("MetroTrainRoot"));TrainRoot->SetupAttachment(RootComponent);TrainRoot->SetMobility(EComponentMobility::Movable);
    TrainMesh=CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("MetroTrain"));TrainMesh->SetupAttachment(TrainRoot);TrainMesh->SetMobility(EComponentMobility::Movable);
    TrainCamera=CreateDefaultSubobject<UCameraComponent>(TEXT("MetroPassengerCamera"));TrainCamera->SetupAttachment(TrainRoot);TrainCamera->SetRelativeLocation(FVector(0,0,235));TrainCamera->SetRelativeRotation(FRotator(0,90,0));TrainCamera->FieldOfView=72;
}
bool AParisMetro::Initialize(AParisTwinScene* InScene,const TSharedPtr<FJsonObject>& Data){
    Scene=InScene;auto VertexMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_Vertex.M_Vertex"));FString Text;TSharedPtr<FJsonObject> J;
    if(!Scene||!VertexMaterial||!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("Data/paris-metro.json")))||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),J)||!J.IsValid()||String(J,TEXT("format"))!=TEXT("paris_metro_prototype_v1")||String(J,TEXT("source_scene_sha256"))!=String(Data,TEXT("source_scene_sha256")))return false;
    const auto& Stations=Array(J,TEXT("stations"));if(Stations.Num()!=2)return false;FVector Points[2];
    for(int32 I=0;I<2;I++){auto S=Stations[I]->AsObject();const auto& P=Array(S,TEXT("wgs84"));const auto& E=Array(S,TEXT("entrance_wgs84"));if(P.Num()!=2||E.Num()!=2)return false;Points[I]=Scene->GeoReference.ToUE(FVector2D(P[0]->AsNumber(),P[1]->AsNumber()),Scene->GeoReference.OriginElevationNGF);Entrances[I]=Scene->GeoReference.ToUE(FVector2D(E[0]->AsNumber(),E[1]->AsNumber()),Scene->GeoReference.OriginElevationNGF);}
    Length=FVector::Dist2D(Points[0],Points[1]);if(!FMath::IsFinite(Length)||Length<10000||Length>60000)return false;
    Points[0].Z=-30000;SetActorLocationAndRotation(Points[0],(Points[1]-Points[0]).Rotation());SetActorRotation(FRotator(0,(Points[1]-Points[0]).Rotation().Yaw,0));
    const FLinearColor Tile(.70,.70,.66),Trim(.08,.20,.16),Floor(.22,.23,.22),Rail(.30,.31,.31),Yellow(.87,.60,.10),Dark(.045,.045,.052),Red(.42,.025,.028),Window(.055,.12,.14),White(.70,.71,.68);
    MeshBuffer B;
    // Entire connection and station interiors are a fictional, low-cost stage.
    const double TrackLength=Length+10000;
    B.Box(FVector(Length/2,0,-45),FVector(TrackLength/2,330,45),Dark);
    for(int32 Side:{-1,1})B.Box(FVector(Length/2,Side*72,8),FVector(TrackLength/2,7,8),Rail);
    for(double X=-4800;X<Length+4800;X+=180)B.Box(FVector(X,0,-5),FVector(14,145,8),Floor);
    B.Box(FVector(Length/2,-420,320),FVector(TrackLength/2,60,320),Tile);
    B.Box(FVector(Length/2,0,720),FVector(TrackLength/2,1100,35),Tile);
    for(int32 S=0;S<2;S++){
        const double X=S?Length:0;
        B.Box(FVector(X,660,-50),FVector(4200,440,50),Floor);
        B.Box(FVector(X,285,4),FVector(4200,12,4),Yellow);
        B.Box(FVector(X,1110,340),FVector(4200,50,340),Tile);
        B.Box(FVector(X,1053,220),FVector(4200,8,9),Trim);
        for(double D=-3800;D<=3800;D+=500){B.Box(FVector(X+D,1050,480),FVector(4,8,200),White);B.Box(FVector(X+D,1000,60),FVector(4,60,60),Trim);}
        for(double D=-2400;D<=2400;D+=1600){B.Box(FVector(X+D,850,52),FVector(135,35,6),Trim);B.Box(FVector(X+D-100,850,25),FVector(5,26,25),Dark);B.Box(FVector(X+D+100,850,25),FVector(5,26,25),Dark);}
        B.Box(FVector(X,1040,410),FVector(300,10,70),Trim);
    }
    B.Apply(StationMesh,VertexMaterial,true);
    MeshBuffer Train;
    Train.Box(FVector(0,0,75),FVector(1150,130,75),White);Train.Box(FVector(0,0,350),FVector(1150,130,28),White);
    for(int32 Side:{-1,1}){
        Train.Box(FVector(0,Side*128,180),FVector(1150,7,22),Red);
        Train.Box(FVector(0,Side*128,300),FVector(1150,7,16),White);
        for(double X=-1100;X<=1100;X+=275){Train.Box(FVector(X,Side*128,240),FVector(15,8,90),White);}
        // Open window apertures let the passenger see the station and tunnel.
    }
    Train.Box(FVector(-1150,0,240),FVector(8,130,110),White);Train.Box(FVector(1150,0,240),FVector(8,130,110),White);
    for(double X=-750;X<=750;X+=500){Train.Box(FVector(X,-82,185),FVector(175,28,12),Trim);Train.Box(FVector(X,-115,235),FVector(175,8,48),Trim);}
    Train.Apply(TrainMesh,VertexMaterial,false);
    for(double X=-3500;X<=Length+3500;X+=2000){auto Light=NewObject<UPointLightComponent>(this);AddInstanceComponent(Light);Light->SetupAttachment(RootComponent);Light->SetRelativeLocation(FVector(X,200,600));Light->SetIntensity(9500);Light->SetAttenuationRadius(2200);Light->SetLightColor(FLinearColor(1,.86,.68));Light->SetCastShadows(false);Light->RegisterComponent();}
    for(int32 I=0;I<2;I++){auto Label=NewObject<UTextRenderComponent>(this);AddInstanceComponent(Label);Label->SetupAttachment(RootComponent);Label->SetRelativeLocation(FVector(I?Length:0,1020,400));Label->SetRelativeRotation(FRotator(0,-90,0));Label->SetHorizontalAlignment(EHTA_Center);Label->SetWorldSize(65);Label->SetText(FText::FromString(I?TEXT("SAINT-MICHEL  |  4"):TEXT("CITE  |  4")));Label->SetTextRenderColor(FColor::White);Label->RegisterComponent();}
    // Surface markers use mapped entrance coordinates; their appearance is inferred.
    for(int32 I=0;I<2;I++){
        FHitResult Hit;FCollisionQueryParams Params;Params.AddIgnoredActor(this);
        if(!GetWorld()->LineTraceSingleByChannel(Hit,Entrances[I]+FVector(0,0,1500),Entrances[I]-FVector(0,0,4000),ECC_Pawn,Params))continue;
        auto Sign=NewObject<UProceduralMeshComponent>(this);AddInstanceComponent(Sign);Sign->SetupAttachment(RootComponent);Sign->RegisterComponent();Sign->SetWorldLocationAndRotation(Hit.ImpactPoint,FRotator::ZeroRotator);
        MeshBuffer Marker;Marker.Box(FVector(-110,0,120),FVector(8,8,120),Trim);Marker.Box(FVector(110,0,120),FVector(8,8,120),Trim);Marker.Box(FVector(0,0,230),FVector(120,10,38),Red);Marker.Apply(Sign,VertexMaterial,false);Sign->SetCastShadow(true);
        auto Label=NewObject<UTextRenderComponent>(this);AddInstanceComponent(Label);Label->SetupAttachment(Sign);Label->SetRelativeLocation(FVector(0,-14,206));Label->SetRelativeRotation(FRotator(0,-90,0));Label->SetHorizontalAlignment(EHTA_Center);Label->SetWorldSize(37);Label->SetText(FText::FromString(TEXT("METRO  4")));Label->SetTextRenderColor(FColor::White);Label->RegisterComponent();
    }
    Distance=0;Station=0;Destination=1;bReady=true;UpdateTrain();return true;
}
FVector AParisMetro::PlatformLocation(int32 S) const{return GetActorTransform().TransformPosition(FVector((S?Length:0)-1500,800,190));}
void AParisMetro::UpdateTrain(){TrainRoot->SetRelativeLocation(FVector(Distance,0,0));}
void AParisMetro::Tick(float Delta){Super::Tick(Delta);if(bReady){SimulateStep(FMath::Clamp(double(Delta),0.,.1));UpdateTrain();}}
void AParisMetro::SimulateStep(double Dt){
    if(!bMoving||Dt<=0)return;const double Goal=Destination?Length:0;const double Remaining=FMath::Abs(Goal-Distance);const double Target=FMath::Min(1200.,FMath::Max(25.,FMath::Sqrt(240.*Remaining)));Speed=FMath::FInterpConstantTo(Speed,Target,Dt,120.);const double Step=FMath::Min(Remaining,Speed*Dt);Distance+=(Destination?1:-1)*Step;Travelled+=Step;if(Remaining-Step<.01){Distance=Goal;Speed=0;Station=Destination;bMoving=false;if(Scene){Scene->ClearInspection();Scene->Selection=FString::Printf(TEXT("Arrived: %s | L: leave train | K: exit to street"),Station?TEXT("Saint-Michel"):TEXT("Cite"));}}}
void AParisMetro::EnterExit(AParisTwinController* PC){
    if(!bReady||!PC||!Scene)return;
    if(bInside){if(bMoving&&bRiding){Scene->Selection=TEXT("Train in motion. Wait for arrival before leaving.");return;}PC->ReturnToFree();FVector Safe;if(Scene->FindWalkingSpawn(Entrances[Station],Safe)&&PC->EnterWalk(false)&&PC->Walker){PC->Walker->ActivateAt(Safe,FRotator(0,GetActorRotation().Yaw,0),false);PC->SetViewTarget(PC->Walker);}else PC->Overview();bInside=bRiding=false;Scene->ClearInspection();Scene->Selection=TEXT("Metro exit | mapped OSM entrance; street placement may be adjusted for collision");return;}
    const FVector Current=PC->GetPawn()?PC->GetPawn()->GetActorLocation():Scene->QualityCentre;Station=FVector::Dist2D(Current,Entrances[0])<=FVector::Dist2D(Current,Entrances[1])?0:1;Destination=1-Station;Distance=Station?Length:0;Speed=0;bMoving=false;UpdateTrain();
    PC->ReturnToFree();if(!PC->EnterWalk(false)||!PC->Walker){Scene->Selection=TEXT("Cannot enter metro: no safe player spawn.");return;}
    PC->Walker->ActivateAt(PlatformLocation(Station),FRotator(0,GetActorRotation().Yaw-28,0),false);PC->SetViewTarget(PC->Walker);bInside=true;Scene->ClearInspection();Scene->Selection=FString::Printf(TEXT("Metro 4 - %s | L: board and travel | K: exit to street\nStation location: OSM; interior and line are inferred"),Station?TEXT("Saint-Michel"):TEXT("Cite"));
}
void AParisMetro::BoardExit(AParisTwinController* PC){
    if(!bReady||!PC||!Scene||!bInside)return;
    if(bRiding){if(bMoving){Scene->Selection=TEXT("Train in motion. Wait for arrival before leaving.");return;}if(PC->Walker){PC->Walker->ActivateAt(PlatformLocation(Station),FRotator(0,GetActorRotation().Yaw-28,0),false);PC->SetViewTarget(PC->Walker);}bRiding=false;Scene->ClearInspection();Scene->Selection=TEXT("L: board train | K: exit to street");return;}
    if(bMoving)return;if(PC->Walker)PC->Walker->Suspend();bRiding=true;Destination=1-Station;bMoving=true;PC->SetViewTarget(this);Scene->ClearInspection();Scene->Selection=FString::Printf(TEXT("Metro 4: travelling to %s | L to leave after arrival"),Destination?TEXT("Saint-Michel"):TEXT("Cite"));
}
