#include "ParisCruise.h"
#include "Components/StaticMeshComponent.h"
#include "Components/BoxComponent.h"
#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/PlayerController.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "WorldProtocol.h"
using namespace AIWorld;
AParisCruise::AParisCruise(){
    PrimaryActorTick.bCanEverTick=true;
    RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("CruiseRoot"));
    Body=CreateDefaultSubobject<UStaticMeshComponent>(TEXT("CruiseHull"));Body->SetupAttachment(RootComponent);Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);Body->SetMobility(EComponentMobility::Movable);
    Glass=CreateDefaultSubobject<UStaticMeshComponent>(TEXT("CruiseWindows"));Glass->SetupAttachment(RootComponent);Glass->SetCollisionEnabled(ECollisionEnabled::NoCollision);Glass->SetCastShadow(false);Glass->SetMobility(EComponentMobility::Movable);
    PickBox=CreateDefaultSubobject<UBoxComponent>(TEXT("CruisePick"));PickBox->SetupAttachment(RootComponent);PickBox->SetBoxExtent(FVector(1255,380,410));PickBox->SetRelativeLocation(FVector(0,0,270));PickBox->SetCollisionEnabled(ECollisionEnabled::QueryOnly);PickBox->SetCollisionResponseToAllChannels(ECR_Ignore);PickBox->SetCollisionResponseToChannel(ECC_Visibility,ECR_Block);PickBox->SetCanEverAffectNavigation(false);
    Camera=CreateDefaultSubobject<UCameraComponent>(TEXT("CruiseCamera"));Camera->SetupAttachment(RootComponent);const FVector Offset(-2700,1800,1700);Camera->SetRelativeLocation(Offset);Camera->SetRelativeRotation((FVector(0,0,230)-Offset).Rotation());Camera->FieldOfView=66;
}
bool AParisCruise::Initialize(const TSharedPtr<FJsonObject>& SceneData){
    FString Text;if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("Data/paris-cruise.json"))))return false;
    TSharedPtr<FJsonObject> J;auto Reader=TJsonReaderFactory<>::Create(Text);if(!FJsonSerializer::Deserialize(Reader,J)||!J.IsValid()||String(J,TEXT("recipe"))!=TEXT("paris_seine_cruise_v1"))return false;
    if(String(J,TEXT("source_scene_sha256"))!=String(SceneData,TEXT("source_scene_sha256")))return false;
    auto R=Object(J,TEXT("route"));const auto& A=Array(R,TEXT("start_cm"));const auto& B=Array(R,TEXT("end_cm"));if(A.Num()!=2||B.Num()!=2)return false;
    Start=FVector(A[0]->AsNumber(),A[1]->AsNumber(),0);End=FVector(B[0]->AsNumber(),B[1]->AsNumber(),0);WaterLevel=Number(J,TEXT("water_level_cm"));Length=FVector::Dist2D(Start,End);
    if(!FMath::IsFinite(Length)||Length<8000||!FMath::IsFinite(WaterLevel)||String(R,TEXT("water_source_id"))!=TEXT("osm/relation/2191006"))return false;
    for(const auto& V:Array(J,TEXT("parts"))){auto P=V->AsObject();const FString Asset=String(P,TEXT("asset"));if(!Asset.StartsWith(TEXT("/Game/ParisPhotoreal/Cruise/")))return false;auto Mesh=LoadObject<UStaticMesh>(nullptr,*Asset);if(!Mesh)return false;if(String(P,TEXT("id"))==TEXT("body"))Body->SetStaticMesh(Mesh);else if(String(P,TEXT("id"))==TEXT("glass"))Glass->SetStaticMesh(Mesh);}
    if(!Body->GetStaticMesh()||!Glass->GetStaticMesh())return false;
    Yaw=(End-Start).Rotation().Yaw;Distance=Length*.5;bReady=true;RefreshPose();return true;
}
void AParisCruise::Tick(float Delta){Super::Tick(Delta);if(!bReady)return;SimulateStep(FMath::Clamp(double(Delta),0.,.1));RefreshPose();}
void AParisCruise::SimulateStep(double Dt){
    if(!bReady||Dt<=0)return;Elapsed+=Dt;
    if(TurnTime>=0){TurnTime+=Dt;const double T=FMath::Clamp(TurnTime/10.,0.,1.);Yaw=TurnStartYaw+180.*T*T*(3.-2.*T);if(T>=1){Direction=-Direction;TurnTime=-1;Yaw=(End-Start).Rotation().Yaw+(Direction<0?180.:0.);}return;}
    const double Remaining=Direction>0?Length-Distance:Distance;
    const double Target=FMath::Min(200.,FMath::Max(20.,FMath::Sqrt(FMath::Max(0.,160.*Remaining))));
    Speed=FMath::FInterpConstantTo(Speed,Target,Dt,70.);const double Step=FMath::Min(Remaining,Speed*Dt);Distance=FMath::Clamp(Distance+Direction*Step,0.,Length);Travelled+=Step;
    if(Remaining-Step<.01){Speed=0;TurnTime=0;TurnStartYaw=Yaw;Turns++;}
}
void AParisCruise::RefreshPose(){const FVector P=FMath::Lerp(Start,End,Distance/Length);SetActorLocationAndRotation(FVector(P.X,P.Y,WaterLevel+2.5*FMath::Sin(Elapsed*.8)),FRotator(.15*FMath::Sin(Elapsed*.65),Yaw,.25*FMath::Sin(Elapsed*.9)));}
void AParisCruise::ActivateView(APlayerController* PC){if(PC){PC->SetViewTarget(this);if(PC->PlayerCameraManager)PC->PlayerCameraManager->SetGameCameraCutThisFrame();}}
FString AParisCruise::Describe() const{return TEXT("SIMULATED Seine sightseeing ferry | 25m CC0 passenger ferry, Innerscene\nInferred route on osm/relation/2191006; turns before bridges\nhttps://www.innerscene.com/tools/library/3d-parts/small-passenger-ferry-25-m-bb6ba356");}
