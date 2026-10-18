#include "ParisDigitalTwin.h"
#include "ParisScannedStatue.h"
#include "Engine/Engine.h"
#include "Engine/StaticMesh.h"
#include "EngineUtils.h"
#include "Components/StaticMeshComponent.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

#if WITH_DEV_AUTOMATION_TESTS
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FParisScannedStatueWait,FAutomationTestBase*,Test);
bool FParisScannedStatueWait::Update(){
    static double Started=0;if(!Started)Started=FPlatformTime::Seconds();
    for(const auto& Context:GEngine->GetWorldContexts())if(Context.World())for(TActorIterator<AParisTwinScene> It(Context.World());It;++It){
        auto Scene=*It;if(!Scene->bReady)continue;
        TArray<UStaticMeshComponent*> Parts;Scene->GetComponents(Parts);UStaticMeshComponent* Scan=nullptr;UStaticMeshComponent* Fallback=nullptr;
        for(auto Part:Parts){if(Part->ComponentHasTag(TEXT("ParisScannedVirgin")))Scan=Part;if(Part->ComponentHasTag(TEXT("ParisVirginFallback")))Fallback=Part;}
        if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoNCStatues")))Test->TestNull(TEXT("NC opt-out never loads the sculpture"),Scan);
        Test->TestEqual(TEXT("Scanned art retains all GIS buildings"),Scene->BuildingCount,739);
        const int32 OldQuality=Scene->DetailQuality;const bool OldSurfaces=Scene->bDetailedSurfaces;
        Scene->DetailQuality=2;if(!Scene->bDetailedSurfaces)Scene->ToggleSurfaces();Scene->ApplyDetailQuality();
        if(Scan&&Fallback){
            Test->TestTrue(TEXT("Actual sculpture has built Nanite data"),Scan->GetStaticMesh()->HasValidNaniteData());
            Test->TestTrue(TEXT("Actual sculpture is visible"),Scan->IsVisible());
            Test->TestFalse(TEXT("Only matching inferred Virgin anchor is replaced"),Fallback->IsVisible());
            Test->TestEqual(TEXT("Scan cannot change source collision"),Scan->GetCollisionEnabled(),ECollisionEnabled::NoCollision);
            Test->TestTrue(TEXT("Already transformed GIS vertices stay at identity"),Scan->GetComponentTransform().Equals(FTransform::Identity,.001));
            Scene->ToggleSurfaces();Test->TestFalse(TEXT("Comparison hides real sculpture"),Scan->IsVisible());Test->TestTrue(TEXT("Comparison restores inferred figure"),Fallback->IsVisible());Scene->ToggleSurfaces();
            Scene->ToggleLevels();Test->TestFalse(TEXT("Accuracy view hides provisional registration"),Scan->IsVisible());Scene->ToggleLevels();
            Scene->DetailQuality=0;Scene->ApplyDetailQuality();Test->TestFalse(TEXT("Low quality hides detailed scan"),Scan->IsVisible());Test->TestFalse(TEXT("Low quality also hides authored fallback"),Fallback->IsVisible());
            Scene->DetailQuality=2;Scene->ApplyDetailQuality();
            auto Original=Scan->GetStaticMesh();Scan->SetStaticMesh(nullptr);SyncParisScannedStatue(Scene,true);
            Test->TestTrue(TEXT("Unavailable scan restores the complete original figure"),Fallback->IsVisible());
            Scan->SetStaticMesh(Original);SyncParisScannedStatue(Scene,true);
            Test->TestTrue(TEXT("Recovered scan is visible"),Scan->IsVisible());Test->TestFalse(TEXT("Recovered scan removes duplicate figure"),Fallback->IsVisible());
        }else if(Fallback)Test->TestTrue(TEXT("Optional model absent keeps the original figure"),Fallback->IsVisible());
        Scene->DetailQuality=OldQuality;if(Scene->bDetailedSurfaces!=OldSurfaces)Scene->ToggleSurfaces();Scene->ApplyDetailQuality();
        Started=0;return true;
    }
    if(FPlatformTime::Seconds()-Started>90){Test->AddError(TEXT("Scanned sculpture scene did not become ready"));Started=0;return true;}return false;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisScannedStatueTest,"ParisDigitalTwin.Live.ScannedVirginAndFallback",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisScannedStatueTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FParisScannedStatueWait(this));return true;}
#endif
