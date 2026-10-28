#include "ParisCruise.h"
#include "ParisDigitalTwin.h"
#include "Components/BoxComponent.h"
#include "Misc/AutomationTest.h"
#include "Engine/Engine.h"
#include "EngineUtils.h"
#if WITH_DEV_AUTOMATION_TESTS
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FParisCruiseWait,FAutomationTestBase*,Test);
bool FParisCruiseWait::Update(){
    static double Started=0;if(Started==0)Started=FPlatformTime::Seconds();
    for(const auto& Context:GEngine->GetWorldContexts())if(auto World=Context.World())for(TActorIterator<AParisTwinScene> SceneIt(World);SceneIt;++SceneIt){auto Scene=*SceneIt;if(!Scene->bReady)continue;
        AParisCruise* Boat=nullptr;for(TActorIterator<AParisCruise> It(World);It;++It){Boat=*It;break;}
        if(!Boat||!Boat->bReady){Test->AddError(TEXT("Cruise model or route failed to load"));Started=0;return true;}
        Test->TestTrue(TEXT("Cruise has a safe navigable reach"),Boat->Length>8000);
        const double Before=Boat->Travelled;const int32 Turns=Boat->Turns;
        for(int32 I=0;I<6000;I++){
            const double Prev=Boat->Distance;Boat->SimulateStep(.05);
            if(!FMath::IsFinite(Boat->Distance)||Boat->Distance<0||Boat->Distance>Boat->Length||FMath::Abs(Boat->Distance-Prev)>10.01){Test->AddError(TEXT("Cruise moved outside route or jumped"));break;}
        }
        Test->TestTrue(TEXT("Cruise advances and turns smoothly at endpoints"),Boat->Travelled>Before+30000&&Boat->Turns>Turns);
        Boat->RefreshPose();Test->TestTrue(TEXT("Boat remains at water height"),FMath::Abs(Boat->GetActorLocation().Z-Boat->WaterLevel)<3);
        auto Box=Boat->FindComponentByClass<UBoxComponent>();Test->TestNotNull(TEXT("Cruise is selectable"),Box);
        if(Box){FHitResult Hit(Boat,Box,Boat->GetActorLocation(),FVector::UpVector);Scene->SelectHit(Hit);Test->TestTrue(TEXT("Selection includes OSM river and real geographic coordinates"),Scene->Selection.Contains(TEXT("osm/relation/2191006"))&&Scene->Selection.Contains(TEXT("CLICK WGS84")));}
        if(auto PC=Cast<AParisTwinController>(World->GetFirstPlayerController())){Boat->ActivateView(PC);Test->TestTrue(TEXT("Cruise view follows vessel"),PC->GetViewTarget()==Boat);PC->Overview();Test->TestTrue(TEXT("Overview returns from cruise"),PC->GetViewTarget()!=Boat);}
        Started=0;return true;
    }
    if(FPlatformTime::Seconds()-Started>40){Test->AddError(TEXT("Paris scene did not load"));Started=0;return true;}return false;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisCruiseLiveTest,"ParisDigitalTwin.Live.CruiseOnSeine",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisCruiseLiveTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FParisCruiseWait(this));return true;}
#endif
