#include "ParisDigitalTwin.h"
#include "ParisPhotoArchitecture.h"
#include "WorldProtocol.h"
#include "Components/StaticMeshComponent.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/Engine.h"
#include "EngineUtils.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

#if WITH_DEV_AUTOMATION_TESTS
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FParisPhotoDetailWait,FAutomationTestBase*,Test);
bool FParisPhotoDetailWait::Update(){
    static double Started=0;if(!Started)Started=FPlatformTime::Seconds();
    for(const auto& Context:GEngine->GetWorldContexts())if(Context.World())for(TActorIterator<AParisTwinScene> It(Context.World());It;++It){auto Scene=*It;if(!Scene->bReady)continue;
        const bool Photo=FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal"));
        auto Stats=MakeShared<FJsonObject>();AddParisPhotoDetailStats(Scene,Stats);
        Test->TestEqual(TEXT("GIS source building count is preserved"),Scene->BuildingCount,739);
        Test->TestEqual(TEXT("All five authored facade materials load only in photoreal mode"),AIWorld::Number(Stats,TEXT("authored_west_facade_components")),Photo?5.:0.);
        if(Photo){
            Test->TestTrue(TEXT("Real tree instances are available"),AIWorld::Number(Stats,TEXT("photo_tree_instances"))>0);
            const auto Old=Scene->DetailQuality;Scene->DetailQuality=2;Scene->ApplyDetailQuality();
            TArray<UStaticMeshComponent*> Parts;Scene->GetComponents(Parts);
            TMap<UStaticMeshComponent*,UStaticMesh*> HighTrees;
            for(auto Part:Parts){
                if(Part->ComponentHasTag(TEXT("ParisPhotoArchitecture"))){Test->TestTrue(TEXT("Authored facade visible at high quality"),Part->IsVisible());Test->TestEqual(TEXT("Art cannot replace source collision"),Part->GetCollisionEnabled(),ECollisionEnabled::NoCollision);}
                if(Part->ComponentHasTag(TEXT("ParisPhotoTree"))){HighTrees.Add(Part,Part->GetStaticMesh());auto HISM=CastChecked<UHierarchicalInstancedStaticMeshComponent>(Part);Test->TestNotNull(TEXT("Original mapped tree ID survives partitioning"),Scene->StreetInstanceSource(HISM,0).Get());}
            }
            Scene->ToggleLevels();for(auto Part:Parts)if(Part->ComponentHasTag(TEXT("ParisPhotoArchitecture")))Test->TestFalse(TEXT("Source accuracy debug hides inferred art"),Part->IsVisible());Scene->ToggleLevels();
            Scene->DetailQuality=0;Scene->ApplyDetailQuality();
            for(auto Part:Parts)if(Part->ComponentHasTag(TEXT("ParisPhotoArchitecture")))Test->TestFalse(TEXT("Low quality hides decorative facade"),Part->IsVisible());
            for(const auto& Pair:HighTrees)Test->TestTrue(TEXT("Low quality restores the lightweight tree proxy"),Pair.Key->GetStaticMesh()!=Pair.Value);
            Scene->DetailQuality=2;Scene->ApplyDetailQuality();for(const auto& Pair:HighTrees)Test->TestTrue(TEXT("High quality restores original real tree mesh"),Pair.Key->GetStaticMesh()==Pair.Value);
            Scene->DetailQuality=Old;Scene->ApplyDetailQuality();

            TArray<UInstancedStaticMeshComponent*> Fixtures;Scene->GetComponents(Fixtures);
            int32 VisualCount=0;
            for(auto Visual:Fixtures)if(Visual->ComponentHasTag(TEXT("ParisPhotoStreetLamp"))){
                VisualCount++;
                Test->TestEqual(TEXT("Lantern art has no collision; original picking proxy is retained"),Visual->GetCollisionEnabled(),ECollisionEnabled::NoCollision);
                Test->TestTrue(TEXT("Lantern visual is a real Nanite mesh"),Visual->GetStaticMesh()&&Visual->GetStaticMesh()->HasValidNaniteData());
                const FName ProxyTag=Visual->ComponentHasTag(TEXT("ParisPhotoLampMetal"))?TEXT("ParisPhotoLampMetalProxy"):TEXT("ParisPhotoLampGlassProxy");
                auto Proxy=Fixtures.FindByPredicate([&](auto Part){return Part->ComponentHasTag(ProxyTag);});
                if(Test->TestTrue(TEXT("Each detailed lamp has its original source proxy"),Proxy!=nullptr)){
                    Test->TestEqual(TEXT("No new geographic lamp positions"),Visual->GetInstanceCount(),(*Proxy)->GetInstanceCount());
                    for(int32 I=0;I<Visual->GetInstanceCount();I++){
                        FTransform A,B;Visual->GetInstanceTransform(I,A,true);(*Proxy)->GetInstanceTransform(I,B,true);
                        Test->TestTrue(TEXT("Detailed lamp preserves source position, rotation and scale"),A.Equals(B,.001));
                        Test->TestNotNull(TEXT("Original lamp ID remains inspectable"),Scene->StreetInstanceSource(*Proxy,I).Get());
                    }
                }
            }
            Test->TestEqual(TEXT("Two shared lamp rendering batches"),VisualCount,2);
            Scene->DetailQuality=0;Scene->ApplyDetailQuality();
            for(auto Visual:Fixtures)if(Visual->ComponentHasTag(TEXT("ParisPhotoStreetLamp")))Test->TestFalse(TEXT("Low hides detailed lanterns"),Visual->IsVisible());
            Scene->DetailQuality=2;Scene->ApplyDetailQuality();
            Scene->ToggleStreetDetails();for(auto Visual:Fixtures)if(Visual->ComponentHasTag(TEXT("ParisPhotoStreetLamp")))Test->TestFalse(TEXT("Props toggle also hides lantern art"),Visual->IsVisible());Scene->ToggleStreetDetails();
            Scene->ToggleLevels();for(auto Visual:Fixtures)if(Visual->ComponentHasTag(TEXT("ParisPhotoStreetLamp")))Test->TestFalse(TEXT("Accuracy overlay hides inferred lantern art"),Visual->IsVisible());Scene->ToggleLevels();
            for(auto Visual:Fixtures)if(Visual->ComponentHasTag(TEXT("ParisPhotoStreetLamp")))Test->TestTrue(TEXT("Detailed view restores lantern art"),Visual->IsVisible());
            Scene->DetailQuality=Old;Scene->ApplyDetailQuality();
        }
        Started=0;return true;
    }
    if(FPlatformTime::Seconds()-Started>90){Test->AddError(TEXT("Photo detail scene did not become ready"));Started=0;return true;}return false;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisPhotoDetailTest,"ParisDigitalTwin.Live.PhotoDetailAssetsAndFallback",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisPhotoDetailTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FParisPhotoDetailWait(this));return true;}
#endif
