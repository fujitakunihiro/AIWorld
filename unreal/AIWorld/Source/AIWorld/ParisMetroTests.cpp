#include "ParisMetro.h"
#include "ParisDigitalTwin.h"
#include "ParisWalker.h"
#include "Components/CapsuleComponent.h"
#include "Misc/AutomationTest.h"
#include "Engine/Engine.h"
#include "EngineUtils.h"
#if WITH_DEV_AUTOMATION_TESTS
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FParisMetroWait,FAutomationTestBase*,Test);
bool FParisMetroWait::Update(){
    static double Started=0;if(!Started)Started=FPlatformTime::Seconds();
    for(const auto& Context:GEngine->GetWorldContexts())if(auto World=Context.World())for(TActorIterator<AParisTwinScene> It(World);It;++It){auto Scene=*It;if(!Scene->bReady)continue;
        AParisMetro* Metro=nullptr;for(TActorIterator<AParisMetro> M(World);M;++M){Metro=*M;break;}auto PC=Cast<AParisTwinController>(World->GetFirstPlayerController());
        if(!Metro||!Metro->bReady||!PC){Test->AddError(TEXT("Metro or controller not ready"));Started=0;return true;}
        Test->TestTrue(TEXT("Station spacing is physically plausible"),Metro->Length>20000&&Metro->Length<60000);
        PC->Overview();Metro->EnterExit(PC);Test->TestTrue(TEXT("Can enter a walkable platform"),Metro->bInside&&PC->Walker&&PC->GetPawn()==PC->Walker);
        if(!Metro->bInside){Started=0;return true;}
        const int32 Initial=Metro->Station;FHitResult Floor;FCollisionQueryParams Params;Params.AddIgnoredActor(PC->Walker);
        Test->TestTrue(TEXT("Platform provides player collision"),World->LineTraceSingleByChannel(Floor,Metro->PlatformLocation(Initial),Metro->PlatformLocation(Initial)-FVector(0,0,400),ECC_Pawn,Params));
        Metro->BoardExit(PC);Test->TestTrue(TEXT("Boarding starts a ride and attaches the view"),Metro->bRiding&&Metro->bMoving&&PC->GetViewTarget()==Metro);
        const double Before=Metro->Distance;Metro->EnterExit(PC);Test->TestTrue(TEXT("Cannot exit while train moves"),Metro->bInside&&Metro->bRiding);
        for(int32 I=0;I<6000&&Metro->bMoving;I++){double Prev=Metro->Distance;Metro->SimulateStep(.05);if(!FMath::IsFinite(Metro->Distance)||Metro->Distance<0||Metro->Distance>Metro->Length||FMath::Abs(Metro->Distance-Prev)>60.01){Test->AddError(TEXT("Invalid or discontinuous train movement"));break;}}
        Test->TestTrue(TEXT("Train arrives at the other station"),!Metro->bMoving&&Metro->Station!=Initial&&FMath::Abs(Metro->Distance-Before)>10000);
        Metro->BoardExit(PC);Test->TestTrue(TEXT("Passenger can leave train onto platform"),!Metro->bRiding&&PC->GetViewTarget()==PC->Walker);
        Metro->EnterExit(PC);Test->TestFalse(TEXT("Passenger can return to street"),Metro->bInside);Test->TestTrue(TEXT("Exit restores world view"),PC->GetViewTarget()!=Metro);
        PC->Overview();Started=0;return true;
    }
    if(FPlatformTime::Seconds()-Started>40){Test->AddError(TEXT("Scene did not load"));Started=0;return true;}return false;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisMetroLiveTest,"ParisDigitalTwin.Live.MetroTravel",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisMetroLiveTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FParisMetroWait(this));return true;}
#endif
