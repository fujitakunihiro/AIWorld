#include "ParisDigitalTwin.h"
#include "ParisPhotoArchitecture.h"
#include "WorldProtocol.h"
#include "Engine/Engine.h"
#include "Engine/StaticMesh.h"
#include "EngineUtils.h"
#include "Components/StaticMeshComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"

#if WITH_DEV_AUTOMATION_TESTS
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FParisObservedFacadeWait,FAutomationTestBase*,Test);
bool FParisObservedFacadeWait::Update(){
    static double Started=0;if(!Started)Started=FPlatformTime::Seconds();
    for(const auto& Context:GEngine->GetWorldContexts())if(Context.World())for(TActorIterator<AParisTwinScene> It(Context.World());It;++It){
        auto Scene=*It;if(!Scene->bReady)continue;
        const bool Expected=FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal"))&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoScannedFacade"))&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoArchitecture"))&&FPaths::FileExists(FPaths::ProjectContentDir()/TEXT("Data/paris-notredame-scan.json"));
        auto Stats=MakeShared<FJsonObject>();AddParisPhotoDetailStats(Scene,Stats);
        Test->TestEqual(TEXT("Observed facade assets must be complete before replacing any original display"),AIWorld::Number(Stats,TEXT("scanned_facade_components")),Expected?1.:0.);
        Test->TestEqual(TEXT("Ready flag agrees with actual loaded geometry"),Scene->bPhotoScanReady,Expected);
        Test->TestEqual(TEXT("Original GIS buildings remain available"),Scene->BuildingCount,739);
        if(Expected){
            TArray<UStaticMeshComponent*> Parts;Scene->GetComponents(Parts);
            const int32 OldQuality=Scene->DetailQuality;const bool OldSurfaces=Scene->bDetailedSurfaces;
            Scene->DetailQuality=2;Scene->ApplyDetailQuality();
            for(auto Part:Parts)if(Part->ComponentHasTag(TEXT("ParisScannedFacade"))){
                Test->TestTrue(TEXT("Observed facade has real Nanite data"),Part->GetStaticMesh()->HasValidNaniteData());
                Test->TestTrue(TEXT("Observed facade is visible at high quality"),Part->IsVisible());
                Test->TestEqual(TEXT("Original walking and picking collision is retained"),Part->GetCollisionEnabled(),ECollisionEnabled::NoCollision);
            }
            Scene->ToggleSurfaces();
            for(auto Part:Parts){
                if(Part->ComponentHasTag(TEXT("ParisScannedFacade")))Test->TestFalse(TEXT("Flat comparison hides the scan"),Part->IsVisible());
                if(Part->ComponentHasTag(TEXT("ParisPhotoArchitecture")))if(auto Material=Cast<UMaterialInstanceDynamic>(Part->GetMaterial(0)))
                    Test->TestEqual(TEXT("Hiding the scan restores every underlying authored surface"),Material->K2_GetScalarParameterValue(TEXT("NDScanActive")),0.f);
            }
            Scene->ToggleSurfaces();Scene->ToggleLevels();
            for(auto Part:Parts)if(Part->ComponentHasTag(TEXT("ParisScannedFacade")))Test->TestFalse(TEXT("Geographic accuracy overlay hides provisional scan registration"),Part->IsVisible());
            Scene->ToggleLevels();Scene->DetailQuality=0;Scene->ApplyDetailQuality();
            for(auto Part:Parts)if(Part->ComponentHasTag(TEXT("ParisScannedFacade")))Test->TestFalse(TEXT("Low quality restores the original lightweight source"),Part->IsVisible());
            Scene->DetailQuality=OldQuality;Scene->ApplyDetailQuality();if(Scene->bDetailedSurfaces!=OldSurfaces)Scene->ToggleSurfaces();
        }
        Started=0;return true;
    }
    if(FPlatformTime::Seconds()-Started>90){Test->AddError(TEXT("Observed facade scene did not load"));Started=0;return true;}return false;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisObservedFacadeTest,"ParisDigitalTwin.Live.ObservedFacadeAndFallback",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisObservedFacadeTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FParisObservedFacadeWait(this));return true;}
#endif
