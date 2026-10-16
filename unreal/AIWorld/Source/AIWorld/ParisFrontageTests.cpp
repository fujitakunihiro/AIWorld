#include "ParisDigitalTwin.h"
#include "ParisPhotoFrontages.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "StaticMeshResources.h"
#include "Materials/Material.h"
#include "Engine/Engine.h"
#include "EngineUtils.h"
#include "WorldProtocol.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

#if WITH_DEV_AUTOMATION_TESTS
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FParisFrontageWait,FAutomationTestBase*,Test);
bool FParisFrontageWait::Update(){
    static double Started=0;if(!Started)Started=FPlatformTime::Seconds();
    for(const auto& Context:GEngine->GetWorldContexts())if(Context.World())for(TActorIterator<AParisTwinScene> SceneIt(Context.World());SceneIt;++SceneIt){
        auto Scene=*SceneIt;if(!Scene->bReady)continue;
        const bool Photo=FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal"))&&Scene->bCompactRuntime;
        auto Stats=MakeShared<FJsonObject>();AddParisFrontageStats(Scene,Stats);
        Test->TestEqual(TEXT("Frontage display is restricted to matching photoreal GIS data"),AIWorld::Number(Stats,TEXT("frontage_components")),Photo?4.:0.);
        if(Photo){
            TArray<UStaticMeshComponent*> NaniteParts;Scene->GetComponents(NaniteParts);
            for(auto NanitePart:NaniteParts)if(auto NaniteMesh=NanitePart->GetStaticMesh())if(NaniteMesh->HasValidNaniteData()){
                for(int32 Slot=0;Slot<NanitePart->GetNumMaterials();Slot++)if(auto Interface=NanitePart->GetMaterial(Slot))
                    Test->TestTrue(TEXT("Every actual Nanite material has a persisted usage permutation"),Interface->GetMaterial()->GetUsageByFlag(MATUSAGE_Nanite));
            }
            Test->TestTrue(TEXT("The source-derived window manifest was loaded"),AIWorld::Number(Stats,TEXT("frontage_windows"))>500);
            Test->TestEqual(TEXT("Source-derived entrance decorations were loaded"),AIWorld::Number(Stats,TEXT("frontage_entrances")),11.);
            Test->TestEqual(TEXT("Source-derived eave decorations were loaded"),AIWorld::Number(Stats,TEXT("frontage_cornices")),107.);
            TArray<UStaticMeshComponent*> Parts;Scene->GetComponents(Parts);TArray<UStaticMeshComponent*> Frontages;
            for(auto Part:Parts)if(Part->ComponentHasTag(TEXT("ParisPhotoFrontage"))){
                Frontages.Add(Part);Test->TestEqual(TEXT("Window display cannot change walking/picking collision"),Part->GetCollisionEnabled(),ECollisionEnabled::NoCollision);
                Test->TestFalse(TEXT("No overlap events from inferred decorations"),Part->GetGenerateOverlapEvents());
                Test->TestTrue(TEXT("No additional geographic transform"),Part->GetComponentTransform().Equals(FTransform::Identity,.001));
                Test->TestTrue(TEXT("Original profiles use real baked Nanite geometry"),Part->GetStaticMesh()->HasValidNaniteData());
                if(Part->ComponentHasTag(TEXT("ParisFrontage_glass"))){
                    const auto& Buffer=Part->GetStaticMesh()->GetRenderData()->LODResources[0].VertexBuffers.StaticMeshVertexBuffer;
                    bool HasZero=false,HasOne=false;
                    for(uint32 VertexIndex=0;VertexIndex<Buffer.GetNumVertices();VertexIndex++){
                        const auto UV=Buffer.GetVertexUV(VertexIndex,0);HasZero|=UV.Equals(FVector2f(0,0),.001f);HasOne|=UV.Equals(FVector2f(1,1),.001f);
                    }
                    Test->TestTrue(TEXT("Actual glazing render data has local UVs for parallax rooms"),HasZero&&HasOne);
                }
            }
            const int32 OldQuality=Scene->DetailQuality;const bool OldSurfaces=Scene->bDetailedSurfaces;
            Scene->DetailQuality=2;Scene->bDetailedSurfaces=true;Scene->ApplyDetailQuality();
            for(auto Part:Frontages)Test->TestTrue(TEXT("High displays stone and glazing together"),Part->IsVisible());
            Scene->ToggleLevels();for(auto Part:Frontages)Test->TestFalse(TEXT("Accuracy display hides inferred window art"),Part->IsVisible());Scene->ToggleLevels();
            Scene->ToggleIssues();for(auto Part:Frontages)Test->TestFalse(TEXT("Issue display hides inferred window art"),Part->IsVisible());Scene->ToggleIssues();
            Scene->ToggleFootprints();for(auto Part:Frontages)Test->TestFalse(TEXT("Footprints hide window art"),Part->IsVisible());Scene->ToggleFootprints();
            Scene->bDetailedSurfaces=false;Scene->ApplyDetailQuality();for(auto Part:Frontages)Test->TestFalse(TEXT("Flat mode restores original source window drawing"),Part->IsVisible());
            Scene->bDetailedSurfaces=true;Scene->DetailQuality=0;Scene->ApplyDetailQuality();for(auto Part:Frontages)Test->TestFalse(TEXT("Low mode omits added window geometry"),Part->IsVisible());
            Scene->DetailQuality=OldQuality;Scene->bDetailedSurfaces=OldSurfaces;Scene->ApplyDetailQuality();
            Test->TestEqual(TEXT("No GIS buildings are added or replaced"),Scene->BuildingCount,739);
        }
        // A stale source must fail closed rather than attaching duplicate art.
        auto Source=MakeShared<FJsonObject>();Source->SetStringField(TEXT("source_scene_sha256"),TEXT("stale"));
        CreateParisPhotoFrontages(Scene,Source);auto After=MakeShared<FJsonObject>();AddParisFrontageStats(Scene,After);
        Test->TestEqual(TEXT("Other GIS revisions cannot add inferred window geometry"),AIWorld::Number(After,TEXT("frontage_components")),AIWorld::Number(Stats,TEXT("frontage_components")));
        Started=0;return true;
    }
    if(FPlatformTime::Seconds()-Started>90){Test->AddError(TEXT("Frontage scene did not become ready"));Started=0;return true;}return false;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisFrontageTest,"ParisDigitalTwin.Live.FrontageGeometryAndFallback",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisFrontageTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FParisFrontageWait(this));return true;}
#endif
