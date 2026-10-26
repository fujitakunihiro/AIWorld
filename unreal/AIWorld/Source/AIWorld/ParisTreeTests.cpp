#include "ParisDigitalTwin.h"
#include "WorldProtocol.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/Engine.h"
#include "EngineUtils.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

#if WITH_DEV_AUTOMATION_TESTS
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FParisTreeWait,FAutomationTestBase*,Test);
bool FParisTreeWait::Update(){
    static double Started=0;if(!Started)Started=FPlatformTime::Seconds();
    for(const auto& Context:GEngine->GetWorldContexts())if(Context.World())for(TActorIterator<AParisTwinScene> It(Context.World());It;++It){
        auto Scene=*It;if(!Scene->bReady)continue;
        const bool Photo=FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal"))&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoPhotoNature"));
        const int32 Old=Scene->DetailQuality;Scene->DetailQuality=2;Scene->ApplyDetailQuality();
        TArray<UHierarchicalInstancedStaticMeshComponent*> Parts;Scene->GetComponents(Parts);
        TSet<FString> IDs;int32 Batches=0,FarTrees=0,Trunks=0;
        for(auto Part:Parts){
            if(Part->ComponentHasTag(TEXT("ParisPhotoTreeTrunkProxy"))){
                Trunks+=Part->GetInstanceCount();
                Test->TestEqual(TEXT("Hidden source trunks still block the player"),Part->GetCollisionEnabled(),ECollisionEnabled::QueryAndPhysics);
            }
            if(!Part->ComponentHasTag(TEXT("ParisPhotoTree")))continue;
            Batches++;
            if(Part->ComponentHasTag(TEXT("ParisPhotoTreeFar")))FarTrees+=Part->GetInstanceCount();
            Test->TestTrue(TEXT("High quality uses real Nanite foliage"),Part->GetStaticMesh()&&Part->GetStaticMesh()->HasValidNaniteData());
            Test->TestEqual(TEXT("Distant wind stops at 60m"),Part->GetWorldPositionOffsetDisableDistance(),6000);
            Test->TestTrue(TEXT("Tree colour random seed is deterministic"),Part->InstancingRandomSeed==17117||Part->InstancingRandomSeed==93199);
            for(int32 Index=0;Index<Part->GetInstanceCount();Index++){
                auto Source=Scene->StreetInstanceSource(Part,Index);
                if(!Test->TestTrue(TEXT("Every detailed tree retains its geographic source"),Source.IsValid()))continue;
                const auto Props=AIWorld::Object(Source,TEXT("properties"));
                const auto& P=AIWorld::Array(Source,TEXT("point_cm"));
                if(!Test->TestEqual(TEXT("Original tree anchor is three dimensional"),P.Num(),3))continue;
                FTransform Transform;Part->GetInstanceTransform(Index,Transform,true);
                Test->TestTrue(TEXT("Photoreal tree does not move its mapped anchor"),Transform.GetLocation().Equals(FVector(P[0]->AsNumber(),P[1]->AsNumber(),P[2]->AsNumber()),.01));
                const double Width=AIWorld::Number(Props,TEXT("crown_diameter_m"))/6.;
                Test->TestTrue(TEXT("Recorded crown and height retain their original scale"),Transform.GetScale3D().Equals(FVector(Width,Width,AIWorld::Number(Props,TEXT("height_m"))/10.),.0001));
                Test->TestTrue(TEXT("Tree orientation stays aligned to its source"),Transform.GetRotation().Equals(FRotator(0,AIWorld::Number(Props,TEXT("yaw_degrees")),0).Quaternion(),.0001));
                IDs.Add(AIWorld::String(Source,TEXT("id")));
            }
        }
        if(Photo){
            Test->TestEqual(TEXT("All mapped trees receive a detailed crown exactly once"),IDs.Num(),1108);
            Test->TestEqual(TEXT("Two shared tree batches avoid per-tree components"),Batches,2);
            Test->TestEqual(TEXT("Original trunk collision count is preserved"),Trunks,IDs.Num());
            Test->TestTrue(TEXT("Trees beyond the old 170m limit are detailed"),FarTrees>0);
            Scene->DetailQuality=0;Scene->ApplyDetailQuality();
            for(auto Part:Parts)if(Part->ComponentHasTag(TEXT("ParisPhotoTree")))Test->TestTrue(TEXT("Low quality restores a lightweight original crown"),Part->GetStaticMesh()->GetName()!=TEXT("SM_ParisBroadleaf"));
        }else Test->TestEqual(TEXT("Non-photoreal mode retains its original tree renderer"),Batches,0);
        Scene->DetailQuality=Old;Scene->ApplyDetailQuality();Started=0;return true;
    }
    if(FPlatformTime::Seconds()-Started>90){Test->AddError(TEXT("Tree verification scene did not become ready"));Started=0;return true;}return false;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisTreeTest,"ParisDigitalTwin.Live.RealisticTreesAndSourceTransforms",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisTreeTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FParisTreeWait(this));return true;}
#endif
