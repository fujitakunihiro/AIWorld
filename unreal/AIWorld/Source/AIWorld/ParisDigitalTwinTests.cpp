#include "WorldProtocol.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/CommandLine.h"
#include "ParisDigitalTwin.h"
#include "Engine/Engine.h"
#include "EngineUtils.h"
using namespace AIWorld;
#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisTwinDataTest,"AIWorld.ParisTwin.ArchivedGISMesh",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisTwinDataTest::RunTest(const FString&) {
    FString Text;if(!TestTrue(TEXT("Offline GIS scene exists"),FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("Data/paris-digital-twin.json")))))return false;
    auto J=Parse(Text);if(!TestTrue(TEXT("Scene parses"),J.IsValid()))return false;
    TestEqual(TEXT("Separate GIS contract"),String(J,TEXT("format")),FString(TEXT("paris_twin_scene_v1")));
    auto G=Object(J,TEXT("georeference"));TestEqual(TEXT("Already exported in UE centimetres"),String(G,TEXT("units")),FString(TEXT("cm")));
    TestEqual(TEXT("Shared Lambert-93 origin"),String(G,TEXT("projected_crs")),FString(TEXT("EPSG:2154")));
    TestFalse(TEXT("No Cesium double transform"),G->GetBoolField(TEXT("cesium_transform_applied")));
    int32 Buildings=0;bool Water=false,Road=false;
    for(const auto& V:Array(J,TEXT("objects"))){auto M=V->AsObject();const FString Kind=String(M,TEXT("kind"));const auto& P=Array(M,TEXT("positions_cm"));const auto& I=Array(M,TEXT("indices"));
        TestTrue(TEXT("Triangles are nonempty"),P.Num()>0&&I.Num()>0&&I.Num()%3==0);TestEqual(TEXT("Normals cover all vertices"),Array(M,TEXT("normals")).Num(),P.Num());
        if(Kind==TEXT("building")){Buildings++;auto A=Object(M,TEXT("properties"));TestEqual(TEXT("No false measured L2 claim"),String(A,TEXT("reproduction_level")),FString(TEXT("L1")));TestTrue(TEXT("Source URL retained"),!String(A,TEXT("source_url")).IsEmpty());}
        Water|=Kind==TEXT("water");Road|=Kind==TEXT("road");
    }
    TestTrue(TEXT("Real district buildings loaded"),Buildings>20);TestTrue(TEXT("River and roads share this scene"),Water&&Road);return true;
}
#endif

#if WITH_DEV_AUTOMATION_TESTS
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FParisTwinSceneWait,FAutomationTestBase*,Test);
bool FParisTwinSceneWait::Update() {
    static double Started=0;static FVector Start,End;if(Started==0){Started=FPlatformTime::Seconds();FString Text;FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("Data/paris-digital-twin.json")));auto J=Parse(Text);for(const auto& V:Array(J,TEXT("objects"))){auto M=V->AsObject();if(String(M,TEXT("kind"))!=TEXT("building"))continue;const auto& Points=Array(M,TEXT("positions_cm"));FVector Centre=FVector::ZeroVector;for(int32 I=Points.Num()-3;I<Points.Num();I++){const auto& P=Points[I]->AsArray();Centre+=FVector(P[0]->AsNumber(),P[1]->AsNumber(),P[2]->AsNumber())/3;}Start=Centre+FVector(0,0,200);End=Centre-FVector(0,0,10000);break;}}
    for(const auto& Context:GEngine->GetWorldContexts())if(Context.World())for(TActorIterator<AParisTwinScene> It(Context.World());It;++It){auto Scene=*It;if(!Scene->bReady)continue;FHitResult Hit;if(!Context.World()->LineTraceSingleByChannel(Hit,Start,End,ECC_Visibility)||Hit.GetActor()!=Scene)continue;Scene->Select(Hit.GetComponent());
        Test->TestTrue(TEXT("Building selection keeps original OSM ID"),Scene->Selection.Contains(TEXT("osm/")));Test->TestTrue(TEXT("Building selection displays WGS84 and height evidence"),Scene->Selection.Contains(TEXT("WGS84 source anchor"))&&Scene->Selection.Contains(TEXT("height")));
        auto Mesh=Cast<UProceduralMeshComponent>(Hit.GetComponent());const FColor Before=Mesh->GetProcMeshSection(0)->ProcVertexBuffer[0].Color;Scene->ToggleLevels();Test->TestTrue(TEXT("L1 debug mode toggles on"),Scene->bLevels);Scene->ToggleLevels();Test->TestFalse(TEXT("Debug mode restores appearance"),Scene->bLevels);Test->TestTrue(TEXT("Debug mode preserves original vertex colour"),Mesh->GetProcMeshSection(0)->ProcVertexBuffer[0].Color==Before);Started=0;return true;}
    if(FPlatformTime::Seconds()-Started>25){Test->AddError(TEXT("GIS scene collision/selection did not become ready"));Started=0;return true;}return false;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisTwinLiveTest,"ParisDigitalTwin.Live.SceneCollisionAndDebug",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisTwinLiveTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FParisTwinSceneWait(this));return true;}
#endif
