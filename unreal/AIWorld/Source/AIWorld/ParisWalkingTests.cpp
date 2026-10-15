#include "ParisDigitalTwin.h"
#include "ParisWalker.h"
#include "ParisPedestrians.h"
#include "Misc/AutomationTest.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "GameFramework/SpringArmComponent.h"
#include "GameFramework/CharacterMovementComponent.h"

#if WITH_DEV_AUTOMATION_TESTS
class FParisWalkingCheck : public IAutomationLatentCommand {
    FAutomationTestBase* Test;
    int32 Phase=0,PreviousRecoveries=0;
    double Started=FPlatformTime::Seconds(),PhaseStarted=0;
    FVector Before=FVector::ZeroVector,Fixture=FVector(150000,0,0);
    TWeakObjectPtr<AParisTwinController> PC;
    TWeakObjectPtr<AParisTwinScene> Scene;
    TArray<TWeakObjectPtr<AActor>> Fixtures;
    void Cleanup(){if(PC.IsValid()){if(PC->Walker)PC->Walker->Scene=Scene.Get();PC->Overview();}for(auto Actor:Fixtures)if(Actor.IsValid())Actor->Destroy();}
    void Box(UWorld* World,const FVector& Position,const FVector& Extent){auto Actor=World->SpawnActor<AActor>();auto Component=NewObject<UBoxComponent>(Actor);Actor->SetRootComponent(Component);Actor->AddInstanceComponent(Component);Component->SetBoxExtent(Extent);Component->SetCollisionProfileName(TEXT("BlockAll"));Component->RegisterComponent();Actor->SetActorLocation(Position);Fixtures.Add(Actor);}
public:
    explicit FParisWalkingCheck(FAutomationTestBase* InTest):Test(InTest){}
    virtual bool Update() override {
        if(FPlatformTime::Seconds()-Started>45){Test->AddError(TEXT("Walking test timed out"));Cleanup();return true;}
        if(!Scene.IsValid())for(const auto& Context:GEngine->GetWorldContexts())if(Context.World())for(TActorIterator<AParisTwinScene> It(Context.World());It;++It)if(It->bReady){Scene=*It;PC=Cast<AParisTwinController>(Context.World()->GetFirstPlayerController());break;}
        if(!Scene.IsValid()||!PC.IsValid())return false;auto World=Scene->GetWorld();const double Now=World->GetTimeSeconds();
        if(Phase==0){
            PC->Eye();if(!PC->EnterWalk(false))return false;auto Walker=PC->Walker.Get();
            Test->TestTrue(TEXT("First person uses a possessed native Character"),PC->GetPawn()==Walker&&Walker->FirstCamera->IsActive());
            Test->TestEqual(TEXT("Human capsule diameter 68cm"),Walker->GetCapsuleComponent()->GetScaledCapsuleRadius(),34.f);
            Test->TestEqual(TEXT("Eye offset plus capsule half height is 1.70m"),Walker->FirstCamera->GetRelativeLocation().Z+Walker->GetCapsuleComponent()->GetScaledCapsuleHalfHeight(),170.);
            PhaseStarted=Now;Phase=1;return false;
        }
        auto Walker=PC->Walker.Get();if(!Walker){Test->AddError(TEXT("Walker disappeared"));Cleanup();return true;}
        if(Phase==1){if(Now-PhaseStarted<.7)return false;Test->TestTrue(TEXT("Real GIS street supports native walking gravity"),Walker->GetCharacterMovement()->IsMovingOnGround());Before=Walker->GetActorLocation();PC->ToggleWalkView();Test->TestTrue(TEXT("Third person has a collision-tested camera boom"),Walker->bThirdPerson&&Walker->ThirdCamera->IsActive()&&Walker->CameraArm->bDoCollisionTest);PC->ToggleWalkView();Test->TestTrue(TEXT("View switching does not teleport the walker"),FVector::Dist(Before,Walker->GetActorLocation())<.01);PhaseStarted=Now;Phase=2;}
        if(Phase==2){Walker->AddMovementInput(FRotator(0,PC->GetControlRotation().Yaw,0).Vector());if(Now-PhaseStarted<1)return false;Test->TestTrue(TEXT("WASD-equivalent input moves a grounded Character through the real district"),FVector::Dist2D(Before,Walker->GetActorLocation())>50);Walker->Scene=nullptr;
            Box(World,Fixture+FVector(0,0,-10),FVector(600,600,10));Box(World,Fixture+FVector(200,0,140),FVector(10,500,140));Box(World,Fixture+FVector(105,300,15),FVector(65,80,15));
            Walker->ActivateAt(Fixture+FVector(0,0,220),FRotator::ZeroRotator,false);Walker->GetCharacterMovement()->SetMovementMode(MOVE_Falling);PhaseStarted=Now;Phase=3;return false;}
        if(Phase==3){if(Now-PhaseStarted<.15)return false;Test->TestTrue(TEXT("Gravity creates a downward velocity"),Walker->GetCharacterMovement()->Velocity.Z<0);PhaseStarted=Now;Phase=4;return false;}
        if(Phase==4){if(Now-PhaseStarted<.8)return false;Test->TestTrue(TEXT("Falling Character lands on collision geometry"),Walker->GetCharacterMovement()->IsMovingOnGround()&&FMath::Abs(Walker->GetActorLocation().Z-90)<5);PhaseStarted=Now;Phase=5;}
        if(Phase==5){Walker->AddMovementInput(FVector::ForwardVector);if(Now-PhaseStarted<1.5)return false;const double X=Walker->GetActorLocation().X-Fixture.X;Test->TestTrue(TEXT("Capsule stops at a wall instead of passing through"),X>100&&X<160);Walker->ActivateAt(Fixture+FVector(0,300,90.2),FRotator::ZeroRotator,true);PhaseStarted=Now;Phase=6;return false;}
        if(Phase==6){Walker->AddMovementInput(FVector::ForwardVector);if(Now-PhaseStarted<1.5)return false;Test->TestTrue(TEXT("Native movement climbs a 30cm step"),Walker->GetActorLocation().Z>110&&Walker->GetCharacterMovement()->IsMovingOnGround());PreviousRecoveries=Walker->Recoveries;Walker->SetActorLocation(Walker->LastSafe-FVector(0,0,500),false,nullptr,ETeleportType::TeleportPhysics);Walker->GetCharacterMovement()->SetMovementMode(MOVE_Falling);PhaseStarted=Now;Phase=7;return false;}
        if(Phase==7){if(Now-PhaseStarted<.15)return false;Test->TestTrue(TEXT("A fall below the terrain recovers to the last safe position"),Walker->Recoveries>PreviousRecoveries&&FVector::Dist(Walker->LastSafe,Walker->GetActorLocation())<10);Cleanup();
            auto Crowd=Scene->Crowd.Get();if(!Test->TestNotNull(TEXT("GIS-derived pedestrian crowd exists"),Crowd))return true;
            Test->TestTrue(TEXT("A populated route network is loaded"),Crowd->People().Num()>50&&Crowd->Network().Num()>50);const double TravelBefore=Crowd->TravelledCm;
            for(int32 I=0;I<1000;I++)Crowd->SimulateStep(.05);
            Test->TestTrue(TEXT("Crowd advances through 1000 bounded simulation steps"),Crowd->TravelledCm>TravelBefore+10000);
            for(const auto& Agent:Crowd->People()){const auto& Route=Crowd->Network()[Agent.Route];Test->TestTrue(TEXT("Pedestrians remain finite and on their GIS-derived route"),!Agent.Position.ContainsNaN()&&Agent.Distance>=0&&Agent.Distance<=Route.Length&&FVector::Dist(Agent.Position,Route.Sample(Agent.Distance,Agent.Direction))<.001);}
            // Distance culling must hide a remote fixture view, then restore
            // picking when the actual camera returns to a person in the city.
            auto Camera=PC->FreeCamera.Get();Camera->Eye(Fixture);Camera->Tick(0);PC->PlayerCameraManager->UpdateCamera(0);Crowd->UpdateInstances();
            Test->TestEqual(TEXT("Remote camera omits all crowd instances without deleting agents"),Crowd->RenderedCount,0);
            Camera->Eye(Crowd->People()[0].Position);Camera->Tick(0);PC->PlayerCameraManager->UpdateCamera(0);
            Crowd->UpdateInstances(true);Test->TestTrue(TEXT("Near-camera people return within the visual budget"),Crowd->RenderedCount>0&&Crowd->RenderedCount<=Crowd->VisibleCount);TArray<UInstancedStaticMeshComponent*> Instances;Crowd->GetComponents(Instances);bool FoundPerson=false;
            for(auto Instance:Instances)if(Instance->GetInstanceCount()>0){const FString Description=Crowd->DescribeHit(Instance,0);FoundPerson|=Description.Contains(TEXT("SIMULATED pedestrian"))&&Description.Contains(TEXT("osm/way/"));}
            Test->TestTrue(TEXT("Crowd picking distinguishes simulated people and their source road"),FoundPerson);
            const int32 Count=Crowd->People().Num();Scene->TogglePeople();Test->TestEqual(TEXT("People can be hidden without deleting their data"),Crowd->VisibleCount,0);Scene->ToggleFootprints();Scene->ToggleFootprints();Test->TestFalse(TEXT("Footprints preserve disabled people"),Crowd->bEnabled);Scene->TogglePeople();Test->TestEqual(TEXT("People display toggle preserves agent state"),Crowd->People().Num(),Count);PC->Overview();return true;
        }
        return false;
    }
};
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisWalkingTest,"ParisDigitalTwin.Live.WalkingAndPedestrians",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisWalkingTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FParisWalkingCheck(this));return true;}
#endif
