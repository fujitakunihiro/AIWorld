#include "ParisPalaisDetail.h"
#include "ParisDigitalTwin.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Engine/Engine.h"
#include "Engine/StaticMesh.h"
#include "StaticMeshResources.h"
#include "EngineUtils.h"
#if WITH_DEV_AUTOMATION_TESTS
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FParisPalaisWait,FAutomationTestBase*,Test);
bool FParisPalaisWait::Update(){
    static double Started=0;if(!Started)Started=FPlatformTime::Seconds();
    for(const auto& Context:GEngine->GetWorldContexts())if(auto World=Context.World())for(TActorIterator<AParisTwinScene> It(World);It;++It){auto Scene=*It;if(!Scene->bReady)continue;
        AParisPalaisDetail* Detail=nullptr;for(TActorIterator<AParisPalaisDetail> D(World);D;++D){Detail=*D;break;}
        if(!Detail||!Detail->bReady){Test->AddError(TEXT("Palais geometry did not load or GIS source changed"));Started=0;return true;}
        Test->TestTrue(TEXT("Mapped palace source is retained"),Scene->SourceFeatureByID(TEXT("osm/relation/536982")).IsValid());Test->TestEqual(TEXT("Four instanced material groups"),Detail->Groups.Num(),4);Test->TestTrue(TEXT("Bounded mapped window count"),Detail->WindowCount>100&&Detail->WindowCount<3000);
        for(auto Group:Detail->Groups){Test->TestTrue(TEXT("Shared facade model exists"),Group->GetStaticMesh()!=nullptr);Test->TestEqual(TEXT("A copy for each traced source window"),Group->GetInstanceCount(),Detail->WindowCount);Test->TestTrue(TEXT("Visual relief preserves source collision"),Group->GetCollisionEnabled()==ECollisionEnabled::NoCollision);}
        if(!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoPalaisPhotoGlass"))){
            Test->TestTrue(TEXT("Reflective window material is active"),Detail->bPhotorealGlass);
            if(Detail->Groups.Num()==4){auto Glass=Detail->Groups[2];Test->TestEqual(TEXT("Per-window seed channel present"),Glass->NumCustomDataFloats,1);Test->TestEqual(TEXT("Each window has a deterministic seed"),Glass->PerInstanceSMCustomData.Num(),Detail->WindowCount);
                if(Glass->PerInstanceSMCustomData.Num()>2){float Min=1,Max=0;for(float Seed:Glass->PerInstanceSMCustomData){Min=FMath::Min(Min,Seed);Max=FMath::Max(Max,Seed);}Test->TestTrue(TEXT("Window appearance varies"),Max-Min>.5f);}
                if(auto Mesh=Glass->GetStaticMesh()){auto Data=Mesh->GetRenderData();if(Data&&Data->LODResources.Num()){const auto& Buffer=Data->LODResources[0].VertexBuffers.StaticMeshVertexBuffer;FVector2f Min(2,2),Max(-1,-1);for(uint32 I=0;I<Buffer.GetNumVertices();I++){auto UV=Buffer.GetVertexUV(I,0);Min.X=FMath::Min(Min.X,UV.X);Min.Y=FMath::Min(Min.Y,UV.Y);Max.X=FMath::Max(Max.X,UV.X);Max.Y=FMath::Max(Max.Y,UV.Y);}Test->TestTrue(TEXT("Window UVs retain their source corners"),Min.X<.01&&Min.Y<.01&&Max.X>.99&&Max.Y>.99);}else Test->AddError(TEXT("Glass render data missing"));}
            }
        }
        const int32 Q=Scene->DetailQuality;Scene->DetailQuality=0;Detail->Sync();for(auto Group:Detail->Groups)Test->TestFalse(TEXT("Low quality shows original GIS"),Group->IsVisible());Scene->DetailQuality=Q;Detail->Sync();
        if(auto PC=Cast<AParisTwinController>(World->GetFirstPlayerController())){PC->Overview();Detail->ActivateView(PC);Test->TestTrue(TEXT("Palais view activates"),PC->GetViewTarget()==Detail);PC->Overview();}
        Started=0;return true;
    }
    if(FPlatformTime::Seconds()-Started>60){Test->AddError(TEXT("Palais scene not ready"));Started=0;return true;}return false;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisPalaisLiveTest,"ParisDigitalTwin.Live.PalaisFrontages",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisPalaisLiveTest::RunTest(const FString&){if(!FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal")))return true;ADD_LATENT_AUTOMATION_COMMAND(FParisPalaisWait(this));return true;}
#endif
