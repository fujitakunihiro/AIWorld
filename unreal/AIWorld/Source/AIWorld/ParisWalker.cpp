#include "ParisWalker.h"
#include "ParisDigitalTwin.h"
#include "ParisPedestrians.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"

AParisWalker::AParisWalker(){
    PrimaryActorTick.bCanEverTick=true;bUseControllerRotationYaw=true;
    GetCapsuleComponent()->InitCapsuleSize(34,88);GetCapsuleComponent()->SetCollisionProfileName(TEXT("Pawn"));
    auto Move=GetCharacterMovement();Move->MaxWalkSpeed=170;Move->MaxStepHeight=35;Move->SetWalkableFloorAngle(44);Move->GravityScale=1;Move->bOrientRotationToMovement=false;Move->BrakingDecelerationWalking=1200;
    FirstCamera=CreateDefaultSubobject<UCameraComponent>(TEXT("FirstPerson"));FirstCamera->SetupAttachment(GetCapsuleComponent());FirstCamera->SetRelativeLocation(FVector(0,0,82));FirstCamera->bUsePawnControlRotation=true;FirstCamera->FieldOfView=70;
    CameraArm=CreateDefaultSubobject<USpringArmComponent>(TEXT("ThirdPersonArm"));CameraArm->SetupAttachment(GetCapsuleComponent());CameraArm->SetRelativeLocation(FVector(0,0,15));CameraArm->TargetArmLength=400;CameraArm->SocketOffset=FVector(0,45,0);CameraArm->bUsePawnControlRotation=true;CameraArm->bDoCollisionTest=true;CameraArm->ProbeSize=15;CameraArm->ProbeChannel=ECC_Camera;
    ThirdCamera=CreateDefaultSubobject<UCameraComponent>(TEXT("ThirdPerson"));ThirdCamera->SetupAttachment(CameraArm,USpringArmComponent::SocketName);ThirdCamera->FieldOfView=65;ThirdCamera->SetActive(false);
}
void AParisWalker::InitializeAppearance(AParisPedestrianCrowd* Crowd){
    if(!Crowd||!Appearance.IsEmpty())return;
    for(int32 I=0;I<6;I++){auto Part=NewObject<UStaticMeshComponent>(this);AddInstanceComponent(Part);Part->SetupAttachment(GetCapsuleComponent());Part->SetStaticMesh(Crowd->Model(ParisPersonPartModel(I,0)));Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);Part->SetCanEverAffectNavigation(false);Part->RegisterComponent();Appearance.Add(Part);}
}
void AParisWalker::ActivateAt(const FVector& Centre,const FRotator& Look,bool ThirdPerson){
    SetActorLocation(Centre,false,nullptr,ETeleportType::TeleportPhysics);LastSafe=Centre;SetActorHiddenInGame(false);GetCapsuleComponent()->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);GetCharacterMovement()->StopMovementImmediately();GetCharacterMovement()->SetMovementMode(MOVE_Walking);
    if(Controller)Controller->SetControlRotation(Look);SetActorRotation(FRotator(0,Look.Yaw,0));bThirdPerson=!ThirdPerson;ToggleView();
}
void AParisWalker::Suspend(){GetCharacterMovement()->StopMovementImmediately();GetCharacterMovement()->DisableMovement();GetCapsuleComponent()->SetCollisionEnabled(ECollisionEnabled::NoCollision);SetActorHiddenInGame(true);}
void AParisWalker::ToggleView(){bThirdPerson=!bThirdPerson;FirstCamera->SetActive(!bThirdPerson);ThirdCamera->SetActive(bThirdPerson);for(auto Part:Appearance)Part->SetVisibility(bThirdPerson);}
void AParisWalker::RecoverToSafe(){SetActorLocation(LastSafe,false,nullptr,ETeleportType::TeleportPhysics);GetCharacterMovement()->StopMovementImmediately();GetCharacterMovement()->SetMovementMode(MOVE_Walking);Recoveries++;}
void AParisWalker::Tick(float Delta){
    Super::Tick(Delta);auto PC=Cast<AParisTwinController>(Controller);if(!PC)return;
    auto Look=PC->GetControlRotation();const FVector2D Mouse=PC->IsLooking()?PC->GetRawLookDelta():FVector2D::ZeroVector;
    Look.Yaw+=Mouse.X*.22+((PC->IsInputKeyDown(EKeys::Right)?1:0)-(PC->IsInputKeyDown(EKeys::Left)?1:0))*60*Delta;
    Look.Pitch=FMath::Clamp(FRotator::NormalizeAxis(Look.Pitch)-Mouse.Y*.22+((PC->IsInputKeyDown(EKeys::Up)?1:0)-(PC->IsInputKeyDown(EKeys::Down)?1:0))*40*Delta,-75.,75.);Look.Roll=0;
    PC->SetControlRotation(Look);SetActorRotation(FRotator(0,Look.Yaw,0));
    const FVector Forward=FRotator(0,Look.Yaw,0).Vector(),Right=FRotationMatrix(FRotator(0,Look.Yaw,0)).GetUnitAxis(EAxis::Y);
    FVector Input=Forward*((PC->IsInputKeyDown(EKeys::W)?1:0)-(PC->IsInputKeyDown(EKeys::S)?1:0))+Right*((PC->IsInputKeyDown(EKeys::D)?1:0)-(PC->IsInputKeyDown(EKeys::A)?1:0));
    GetCharacterMovement()->MaxWalkSpeed=PC->IsInputKeyDown(EKeys::LeftShift)?340:170;if(!Input.IsNearlyZero())AddMovementInput(Input.GetSafeNormal());
    const bool Inside=!Scene||(FMath::Abs(GetActorLocation().X-Scene->SceneCentre.X)<Scene->Extent*50-75&&FMath::Abs(GetActorLocation().Y-Scene->SceneCentre.Y)<Scene->Extent*50-75);
    if(GetCharacterMovement()->IsMovingOnGround()&&Inside)LastSafe=GetActorLocation();
    if(!Inside||GetActorLocation().Z<LastSafe.Z-350)RecoverToSafe();
    const bool Moving=GetVelocity().Size2D()>10;Phase+=GetVelocity().Size2D()*Delta*.035;
    const auto Pose=ParisPersonPose(FVector(0,0,-88),0,Phase,Moving);for(int32 I=0;I<Appearance.Num();I++)Appearance[I]->SetRelativeTransform(Pose[I]);
}
