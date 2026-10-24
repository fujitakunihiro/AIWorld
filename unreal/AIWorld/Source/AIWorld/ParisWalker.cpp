#include "ParisWalker.h"
#include "ParisDigitalTwin.h"
#include "ParisPedestrians.h"
#include "ParisHumanAnimation.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Animation/AnimSequence.h"
#include "Materials/Material.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

AParisWalker::AParisWalker(){
    PrimaryActorTick.bCanEverTick=true;bUseControllerRotationYaw=true;
    GetCapsuleComponent()->InitCapsuleSize(34,88);GetCapsuleComponent()->SetCollisionProfileName(TEXT("Pawn"));
    auto Move=GetCharacterMovement();Move->MaxWalkSpeed=WalkSpeedCm;Move->MaxStepHeight=35;Move->SetWalkableFloorAngle(44);Move->GravityScale=1;Move->bOrientRotationToMovement=false;Move->RotationRate=FRotator(0,540,0);Move->MaxAcceleration=1000;Move->BrakingDecelerationWalking=1200;
    FirstCamera=CreateDefaultSubobject<UCameraComponent>(TEXT("FirstPerson"));FirstCamera->SetupAttachment(GetCapsuleComponent());FirstCamera->SetRelativeLocation(FVector(0,0,82));FirstCamera->bUsePawnControlRotation=true;FirstCamera->FieldOfView=70;
    CameraArm=CreateDefaultSubobject<USpringArmComponent>(TEXT("ThirdPersonArm"));CameraArm->SetupAttachment(GetCapsuleComponent());CameraArm->SetRelativeLocation(FVector(0,0,10));CameraArm->TargetArmLength=340;CameraArm->SocketOffset=FVector(0,35,20);CameraArm->bUsePawnControlRotation=true;CameraArm->bDoCollisionTest=true;CameraArm->ProbeSize=15;CameraArm->ProbeChannel=ECC_Camera;
    ThirdCamera=CreateDefaultSubobject<UCameraComponent>(TEXT("ThirdPerson"));ThirdCamera->SetupAttachment(CameraArm,USpringArmComponent::SocketName);ThirdCamera->FieldOfView=70;ThirdCamera->SetActive(false);
    GetMesh()->SetCollisionEnabled(ECollisionEnabled::NoCollision);GetMesh()->SetCanEverAffectNavigation(false);
}
bool AParisWalker::HasHumanAppearance() const { return GetMesh()->GetSkeletalMeshAsset()!=nullptr; }
bool AParisWalker::LoadHumanAppearance(){
    if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinSimplePeople")))return false;
    FString Text;TSharedPtr<FJsonObject> Data;const TArray<TSharedPtr<FJsonValue>>* Avatars=nullptr;
    if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("Data/paris-people.json")))||
       !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Data)||!Data.IsValid()||
       !Data->TryGetArrayField(TEXT("avatars"),Avatars)||Avatars->IsEmpty())return false;
    auto Avatar=(*Avatars)[0]->AsObject();const TSharedPtr<FJsonObject>* Clips=nullptr;
    if(!Avatar.IsValid()||!Avatar->TryGetObjectField(TEXT("animations"),Clips))return false;
    auto Path=[](const TSharedPtr<FJsonObject>& J,const TCHAR* Key){FString Value;J->TryGetStringField(Key,Value);return Value;};
    auto HumanMesh=LoadObject<USkeletalMesh>(nullptr,*Path(Avatar,TEXT("mesh")));
    auto Idle=LoadObject<UAnimSequence>(nullptr,*Path(*Clips,TEXT("idle")));
    auto Walk=LoadObject<UAnimSequence>(nullptr,*Path(*Clips,TEXT("walk")));
    auto Run=LoadObject<UAnimSequence>(nullptr,*Path(*Clips,TEXT("run")));
    if(!HumanMesh||!Idle||!Walk||!Run||Idle->GetSkeleton()!=HumanMesh->GetSkeleton()||Walk->GetSkeleton()!=HumanMesh->GetSkeleton()||Run->GetSkeleton()!=HumanMesh->GetSkeleton())return false;
    for(const auto& Slot:HumanMesh->GetMaterials())if(!Slot.MaterialInterface||!Slot.MaterialInterface->GetMaterial()->GetUsageByFlag(MATUSAGE_SkeletalMesh))return false;
    double Yaw=0;Avatar->TryGetNumberField(TEXT("yaw_offset_degrees"),Yaw);
    auto Body=GetMesh();Body->SetSkeletalMeshAsset(HumanMesh);Body->SetRelativeLocationAndRotation(FVector(0,0,-88),FRotator(0,Yaw,0));
    Body->VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::OnlyTickPoseWhenRendered;
    Body->SetCastShadow(!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoShadows")));
    Body->AddTickPrerequisiteActor(this);Body->SetAnimInstanceClass(UParisHumanAnimation::StaticClass());
    auto Anim=CastChecked<UParisHumanAnimation>(Body->GetAnimInstance());Anim->Idle=Idle;Anim->Walk=Walk;Anim->Run=Run;Anim->Sit=Idle;Anim->PersonIndex=0;
    auto ClipSpeed=[](UAnimSequence* Clip,float Fallback){const float Length=Clip->GetPlayLength();const float Speed=Length>.1f?Clip->ExtractRootMotionFromRange(0,Length,FAnimExtractContext(0,true)).GetTranslation().Size2D()/Length:0;return Speed>40&&Speed<900?Speed:Fallback;};
    Anim->NominalSpeedCm=ClipSpeed(Walk,120);Anim->NominalRunSpeedCm=ClipSpeed(Run,400);
    UE_LOG(LogTemp,Display,TEXT("PARIS_PLAYER_READY walk=%.0fcm/s run=%.0fcm/s rig=%s"),Anim->NominalSpeedCm,Anim->NominalRunSpeedCm,*HumanMesh->GetName());
    return true;
}
void AParisWalker::InitializeAppearance(AParisPedestrianCrowd* Crowd){
    if(HasHumanAppearance()||!Appearance.IsEmpty())return;
    if(LoadHumanAppearance()){UpdateAppearanceVisibility();return;}
    UE_LOG(LogTemp,Warning,TEXT("PARIS_PLAYER_FALLBACK: complete human walk/run assets unavailable; using the articulated character"));
    if(!Crowd)return;
    for(int32 I=0;I<6;I++){auto Part=NewObject<UStaticMeshComponent>(this);AddInstanceComponent(Part);Part->SetupAttachment(GetCapsuleComponent());Part->SetStaticMesh(Crowd->Model(ParisPersonPartModel(I,0)));Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);Part->SetCanEverAffectNavigation(false);Part->RegisterComponent();Appearance.Add(Part);}
    UpdateAppearanceVisibility();
}
void AParisWalker::ActivateAt(const FVector& Centre,const FRotator& Look,bool ThirdPerson){
    SetActorLocation(Centre,false,nullptr,ETeleportType::TeleportPhysics);LastSafe=PreviousLocation=Centre;DistanceTravelledCm=0;SetActorHiddenInGame(false);GetCapsuleComponent()->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);GetCharacterMovement()->StopMovementImmediately();GetCharacterMovement()->SetMovementMode(MOVE_Walking);
    FRotator View=Look;if(ThirdPerson&&FMath::Abs(View.Pitch)<1)View.Pitch=-12;
    if(Controller)Controller->SetControlRotation(View);SetActorRotation(FRotator(0,Look.Yaw,0));bThirdPerson=!ThirdPerson;ToggleView();
}
void AParisWalker::Suspend(){GetCharacterMovement()->StopMovementImmediately();GetCharacterMovement()->DisableMovement();GetCapsuleComponent()->SetCollisionEnabled(ECollisionEnabled::NoCollision);SetActorHiddenInGame(true);GetMesh()->SetComponentTickEnabled(false);}
void AParisWalker::UpdateAppearanceVisibility(){GetMesh()->SetVisibility(bThirdPerson);GetMesh()->SetComponentTickEnabled(bThirdPerson&&HasHumanAppearance());for(auto Part:Appearance)Part->SetVisibility(bThirdPerson);}
void AParisWalker::ToggleView(){bThirdPerson=!bThirdPerson;FirstCamera->SetActive(!bThirdPerson);ThirdCamera->SetActive(bThirdPerson);bUseControllerRotationYaw=!bThirdPerson;GetCharacterMovement()->bOrientRotationToMovement=bThirdPerson;UpdateAppearanceVisibility();}
void AParisWalker::Zoom(double Factor){if(bThirdPerson)CameraArm->TargetArmLength=FMath::Clamp(CameraArm->TargetArmLength*Factor,180.,600.);}
void AParisWalker::RecoverToSafe(){SetActorLocation(LastSafe,false,nullptr,ETeleportType::TeleportPhysics);PreviousLocation=LastSafe;GetCharacterMovement()->StopMovementImmediately();GetCharacterMovement()->SetMovementMode(MOVE_Walking);Recoveries++;}
void AParisWalker::Tick(float Delta){
    Super::Tick(Delta);auto PC=Cast<AParisTwinController>(Controller);if(!PC)return;
    auto Look=PC->GetControlRotation();const FVector2D Mouse=PC->IsLooking()?PC->GetRawLookDelta():FVector2D::ZeroVector;
    Look.Yaw+=Mouse.X*.22+((PC->IsInputKeyDown(EKeys::Right)?1:0)-(PC->IsInputKeyDown(EKeys::Left)?1:0))*60*Delta;
    Look.Pitch=FMath::Clamp(FRotator::NormalizeAxis(Look.Pitch)-Mouse.Y*.22+((PC->IsInputKeyDown(EKeys::Up)?1:0)-(PC->IsInputKeyDown(EKeys::Down)?1:0))*40*Delta,-75.,75.);Look.Roll=0;
    PC->SetControlRotation(Look);if(!bThirdPerson)SetActorRotation(FRotator(0,Look.Yaw,0));
    const FVector Forward=FRotator(0,Look.Yaw,0).Vector(),Right=FRotationMatrix(FRotator(0,Look.Yaw,0)).GetUnitAxis(EAxis::Y);
    FVector Input=Forward*((PC->IsInputKeyDown(EKeys::W)?1:0)-(PC->IsInputKeyDown(EKeys::S)?1:0))+Right*((PC->IsInputKeyDown(EKeys::D)?1:0)-(PC->IsInputKeyDown(EKeys::A)?1:0));
    GetCharacterMovement()->MaxWalkSpeed=(PC->IsInputKeyDown(EKeys::LeftShift)||PC->IsInputKeyDown(EKeys::RightShift))?RunSpeedCm:WalkSpeedCm;if(!Input.IsNearlyZero())AddMovementInput(Input.GetSafeNormal());
    const bool Inside=!Scene||(FMath::Abs(GetActorLocation().X-Scene->SceneCentre.X)<Scene->Extent*50-75&&FMath::Abs(GetActorLocation().Y-Scene->SceneCentre.Y)<Scene->Extent*50-75);
    if(GetCharacterMovement()->IsMovingOnGround()&&Inside)LastSafe=GetActorLocation();
    if(!Inside||GetActorLocation().Z<LastSafe.Z-350)RecoverToSafe();
    DistanceTravelledCm+=FVector::Dist2D(PreviousLocation,GetActorLocation());PreviousLocation=GetActorLocation();
    if(auto Anim=Cast<UParisHumanAnimation>(GetMesh()->GetAnimInstance()))Anim->SpeedCm=GetVelocity().Size2D();
    const bool Moving=GetVelocity().Size2D()>10;Phase+=GetVelocity().Size2D()*Delta*.035;
    const auto Pose=ParisPersonPose(FVector(0,0,-88),0,Phase,Moving);for(int32 I=0;I<Appearance.Num();I++)Appearance[I]->SetRelativeTransform(Pose[I]);
}
