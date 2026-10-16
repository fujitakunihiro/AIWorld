#include "ParisDigitalTwin.h"
#include "Components/StaticMeshComponent.h"
#include "ProceduralMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "StaticMeshResources.h"
#include "Engine/Engine.h"
#include "EngineUtils.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

#if WITH_DEV_AUTOMATION_TESTS
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FParisGroundWait,FAutomationTestBase*,Test);
bool FParisGroundWait::Update(){
    static double Started=0;if(!Started)Started=FPlatformTime::Seconds();
    for(const auto& Context:GEngine->GetWorldContexts())if(Context.World())for(TActorIterator<AParisTwinScene> It(Context.World());It;++It){
        auto Scene=*It;if(!Scene->bReady)continue;
        const bool Photo=FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal"));
        UProceduralMeshComponent* Source=nullptr;UStaticMeshComponent* Display=nullptr;
        TArray<UProceduralMeshComponent*> Originals;Scene->GetComponents(Originals);
        for(auto Part:Originals)if(Part->ComponentHasTag(TEXT("ParisSourceTerrain")))Source=Part;
        TArray<UStaticMeshComponent*> Visuals;Scene->GetComponents(Visuals);
        for(auto Part:Visuals)if(Part->ComponentHasTag(TEXT("ParisGroundDisplay")))Display=Part;
        if(!Test->TestNotNull(TEXT("Source terrain is always retained"),Source)){Started=0;return true;}
        Test->TestEqual(TEXT("Original terrain triangle topology is unchanged"),Source->GetProcMeshSection(0)->ProcIndexBuffer.Num()/3,2993);
        Test->TestEqual(TEXT("Original terrain collision is retained"),Source->GetCollisionEnabled(),ECollisionEnabled::QueryAndPhysics);
        Test->TestEqual(TEXT("Display only loads in photoreal compact scene"),Display!=nullptr,Photo&&Scene->bCompactRuntime);
        if(Display){
            Test->TestEqual(TEXT("Cutout never replaces terrain collision"),Display->GetCollisionEnabled(),ECollisionEnabled::NoCollision);
            Test->TestTrue(TEXT("Display is in the original world frame"),Display->GetComponentTransform().Equals(FTransform::Identity,.001));
            const int32 Old=Scene->DetailQuality;Scene->DetailQuality=2;Scene->ApplyDetailQuality();
            Test->TestTrue(TEXT("Covered terrain is not drawn twice"),Display->IsVisible()&&!Source->bRenderInMainPass&&!Source->bRenderInDepthPass&&Source->IsVisible());
            const auto& Colors=Display->GetStaticMesh()->GetRenderData()->LODResources[0].VertexBuffers.ColorVertexBuffer;
            Test->TestTrue(TEXT("Cutout retains the original terrain palette"),Colors.GetNumVertices()>0&&Colors.VertexColor(0)==Source->GetProcMeshSection(0)->ProcVertexBuffer[0].Color);
            Scene->ToggleLevels();Test->TestTrue(TEXT("Accuracy view restores source terrain"),!Display->IsVisible()&&Source->bRenderInMainPass);Scene->ToggleLevels();
            Scene->DetailQuality=0;Scene->ApplyDetailQuality();Test->TestTrue(TEXT("Low restores original terrain drawing"),!Display->IsVisible()&&Source->bRenderInMainPass);
            Scene->DetailQuality=Old;Scene->ApplyDetailQuality();
        }
        Started=0;return true;
    }
    if(FPlatformTime::Seconds()-Started>60){Test->AddError(TEXT("Ground display scene did not become ready"));Started=0;return true;}return false;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisGroundTest,"ParisDigitalTwin.Live.CoveredTerrainDisplayAndCollision",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisGroundTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FParisGroundWait(this));return true;}
#endif
