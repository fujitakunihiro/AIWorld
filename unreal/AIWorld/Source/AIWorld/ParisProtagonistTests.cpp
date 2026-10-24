#include "ParisDigitalTwin.h"
#include "ParisWalker.h"
#include "ParisHumanAnimation.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Components/BoxComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/CapsuleComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "Camera/CameraComponent.h"
#include "Animation/AnimSequence.h"
#include "InputKeyEventArgs.h"

#if WITH_DEV_AUTOMATION_TESTS
class FParisProtagonistCheck : public IAutomationLatentCommand {
    FAutomationTestBase* Test;
    TWeakObjectPtr<AParisTwinScene> Scene;
    TWeakObjectPtr<AParisTwinController> PC;
    TArray<TWeakObjectPtr<AActor>> Fixtures;
    FVector Origin=FVector(150000,8000,0),Before=FVector::ZeroVector;
    int32 Phase=0;
    double Started=FPlatformTime::Seconds(),At=0;
    FName Foot;
    FVector FootBefore=FVector::ZeroVector;
    void Key(FKey K,bool Down){if(PC.IsValid())PC->InputKey(FInputKeyEventArgs(nullptr,FInputDeviceId::CreateFromInternalId(0),K,Down?IE_Pressed:IE_Released,Down?1.f:0.f,false,FPlatformTime::Cycles64()));}
    void Box(const FVector& P,const FVector& Extent){auto Actor=Scene->GetWorld()->SpawnActor<AActor>();auto C=NewObject<UBoxComponent>(Actor);Actor->SetRootComponent(C);Actor->AddInstanceComponent(C);C->SetBoxExtent(Extent);C->SetCollisionProfileName(TEXT("BlockAll"));C->RegisterComponent();Actor->SetActorLocation(P);Fixtures.Add(Actor);}
    void Cleanup(){Key(EKeys::W,false);Key(EKeys::D,false);Key(EKeys::LeftShift,false);Key(EKeys::RightShift,false);if(PC.IsValid()){if(PC->Walker){PC->Walker->Scene=Scene.Get();PC->Walker->GetMesh()->VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::OnlyTickPoseWhenRendered;}PC->Overview();}for(auto Actor:Fixtures)if(Actor.IsValid())Actor->Destroy();}
public:
    explicit FParisProtagonistCheck(FAutomationTestBase* In):Test(In){}
    virtual bool Update() override {
        if(FPlatformTime::Seconds()-Started>35){Test->AddError(TEXT("Protagonist test timed out"));Cleanup();return true;}
        if(!Scene.IsValid())for(const auto& Context:GEngine->GetWorldContexts())if(Context.World())for(TActorIterator<AParisTwinScene> It(Context.World());It;++It)if(It->bReady){Scene=*It;PC=Cast<AParisTwinController>(Context.World()->GetFirstPlayerController());break;}
        if(!Scene.IsValid()||!PC.IsValid())return false;
        const double Now=Scene->GetWorld()->GetTimeSeconds();
        if(Phase==0){
            PC->Eye();PC->Walk();auto Hero=PC->Walker.Get();if(!Hero||PC->GetPawn()!=Hero)return false;
            Test->TestTrue(TEXT("F8 enters third-person protagonist mode"),Hero->bThirdPerson&&Hero->ThirdCamera->IsActive());
            const bool Human=!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinSimplePeople"));
            Test->TestEqual(TEXT("Protagonist uses the complete human rig or the requested cheap fallback"),Hero->HasHumanAppearance(),Human);
            if(Human){auto Anim=Cast<UParisHumanAnimation>(Hero->GetMesh()->GetAnimInstance());if(!Anim){Test->AddError(TEXT("Missing protagonist animation instance"));Cleanup();return true;}
                Test->TestTrue(TEXT("Idle, walking and running are separate saved source clips"),Anim->Idle&&Anim->Walk&&Anim->Run&&Anim->Walk!=Anim->Run&&Anim->Run->bForceRootLock&&!Anim->Run->bEnableRootMotion);
                Test->TestTrue(TEXT("Avatar uses cm scale without rescaling the geographic world"),Hero->GetMesh()->GetRelativeScale3D().Equals(FVector::OneVector)&&Hero->GetMesh()->GetRelativeLocation().Z==-88);
                Hero->GetMesh()->VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
                for(int32 B=0;B<Hero->GetMesh()->GetNumBones();B++)if(Hero->GetMesh()->GetBoneName(B).ToString().ToLower().Contains(TEXT("l-foot")))Foot=Hero->GetMesh()->GetBoneName(B);
            }
            At=Now;Phase=10;return false;
        }
        auto Hero=PC->Walker.Get();auto Move=Hero->GetCharacterMovement();auto Anim=Cast<UParisHumanAnimation>(Hero->GetMesh()->GetAnimInstance());
        if(Phase==10&&Now-At>.3){
            Test->TestTrue(TEXT("Real GIS spawn leaves camera space instead of compressing the boom into a facade"),FVector::Dist(Hero->ThirdCamera->GetComponentLocation(),Hero->GetActorLocation()+Hero->CameraArm->GetRelativeLocation())>250);
            Hero->Scene=nullptr;Box(Origin+FVector(0,0,-10),FVector(5000,5000,10));Hero->ActivateAt(Origin+FVector(0,0,90.2),FRotator::ZeroRotator,true);
            Before=Hero->GetActorLocation();Key(EKeys::W,true);At=Now;Phase=1;return false;
        }
        if(Phase==1&&Now-At>1){
            Test->TestTrue(TEXT("Actual W key walks at 1.7m/s on collision geometry"),Move->IsMovingOnGround()&&FMath::IsNearlyEqual(Hero->GetVelocity().Size2D(),170.,5.)&&FVector::Dist2D(Before,Hero->GetActorLocation())>90);
            Before=Hero->GetActorLocation();Key(EKeys::LeftShift,true);At=Now;Phase=2;return false;
        }
        if(Phase==2&&Now-At>1){
            Test->TestTrue(TEXT("Holding Shift changes actual travel speed to 4.2m/s"),Hero->IsRunning()&&FMath::IsNearlyEqual(Hero->GetVelocity().Size2D(),420.,5.)&&FVector::Dist2D(Before,Hero->GetActorLocation())>300);
            if(Anim){Test->TestTrue(TEXT("Animation follows measured velocity"),FMath::Abs(Anim->SpeedCm-420)<5);Test->TestFalse(TEXT("Imported run has a foot joint"),Foot.IsNone());FootBefore=Hero->GetMesh()->GetSocketTransform(Foot,RTS_Component).GetLocation();}
            Key(EKeys::D,true);At=Now;Phase=3;return false;
        }
        if(Phase==3&&Now-At>.7){
            Test->TestTrue(TEXT("Diagonal running is normalized and turns the body toward travel"),Hero->GetVelocity().X>250&&Hero->GetVelocity().Y>250&&Hero->GetVelocity().Size2D()<421&&FMath::Abs(FRotator::NormalizeAxis(Hero->GetActorRotation().Yaw)-45)<8);
            Test->TestTrue(TEXT("Third-person body turning leaves camera heading independent"),FMath::Abs(PC->GetControlRotation().Yaw)<1);
            if(Anim)Test->TestTrue(TEXT("Running evaluates a changing skinned foot pose"),FVector::Dist(FootBefore,Hero->GetMesh()->GetSocketTransform(Foot,RTS_Component).GetLocation())>2);
            Key(EKeys::W,false);Key(EKeys::D,false);Key(EKeys::LeftShift,false);At=Now;Phase=4;return false;
        }
        if(Phase==4&&Now-At>.7){
            Test->TestTrue(TEXT("Releasing the keys stops movement and returns to idle"),Hero->GetVelocity().Size2D()<1&&(!Anim||Anim->SpeedCm<1)&&!Hero->IsRunning());
            Before=Hero->GetActorLocation();Hero->ToggleView();Test->TestTrue(TEXT("First-person hides the avatar and uses the eye camera"),Hero->FirstCamera->IsActive()&&!Hero->GetMesh()->IsVisible());Hero->ToggleView();Test->TestTrue(TEXT("View switching restores the body without teleportation"),Hero->ThirdCamera->IsActive()&&Hero->GetMesh()->IsVisible()&&FVector::Dist(Before,Hero->GetActorLocation())<.01);
            Hero->Zoom(.01);Test->TestEqual(TEXT("Camera zoom keeps a safe minimum distance"),Hero->CameraArm->TargetArmLength,180.f);Hero->Zoom(100);Test->TestEqual(TEXT("Camera zoom is bounded"),Hero->CameraArm->TargetArmLength,600.f);
            Box(Origin+FVector(650,0,150),FVector(10,1000,150));Hero->ActivateAt(Origin+FVector(0,0,90.2),FRotator::ZeroRotator,true);Key(EKeys::W,true);Key(EKeys::RightShift,true);At=Now;Phase=5;return false;
        }
        if(Phase==5&&Now-At>2.2){
            const double X=Hero->GetActorLocation().X-Origin.X;
            Test->TestTrue(TEXT("Right Shift also runs and capsule collision stops sprinting at walls"),Move->MaxWalkSpeed==420&&X>590&&X<610&&Hero->GetVelocity().Size2D()<5);
            Test->TestTrue(TEXT("Blocked character stops running animation despite held input"),!Anim||Anim->SpeedCm<5);
            Test->TestTrue(TEXT("Travel distance records real motion"),Hero->DistanceTravelledCm>590);
            Cleanup();Test->TestTrue(TEXT("Leaving protagonist mode suspends the body and collision"),Hero->IsHidden()&&!Hero->GetMesh()->IsComponentTickEnabled()&&Hero->GetCapsuleComponent()->GetCollisionEnabled()==ECollisionEnabled::NoCollision&&PC->GetPawn()==PC->FreeCamera);
            return true;
        }
        return false;
    }
};
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisProtagonistTest,"ParisDigitalTwin.Live.ProtagonistWalkRun",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisProtagonistTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FParisProtagonistCheck(this));return true;}
#endif
