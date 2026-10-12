#include "WorldProtocol.h"
#include "Misc/AutomationTest.h"
#include "Misc/Base64.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "AIWorldScene.h"
#include "AIWorldResident.h"
#include "Engine/Engine.h"
#include "EngineUtils.h"
using namespace AIWorld;
#if WITH_DEV_AUTOMATION_TESTS
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FWorldConnectionWait, FAutomationTestBase*, Test);
bool FWorldConnectionWait::Update() {
    static double Started=0;if(Started==0)Started=FPlatformTime::Seconds();
    for(const auto& Context:GEngine->GetWorldContexts())if(Context.World())for(TActorIterator<AAIWorldScene> It(Context.World());It;++It) {
        auto W=*It;if(!W->bReady||!W->bConnected)continue;
        Test->TestEqual(TEXT("Original 384 x 384 world loaded"),W->Grid.Size,384);
        Test->TestTrue(TEXT("Saved village population loaded"),Array(W->Village,TEXT("residents")).Num()>=5);
        Test->TestEqual(TEXT("Native characters reflect every saved resident"),W->People().Num(),Array(W->Village,TEXT("residents")).Num());
        auto R=Array(W->Village,TEXT("residents"))[0]->AsObject();Test->TestTrue(TEXT("Actual AI reasons are available"),!String(R,TEXT("reason")).IsEmpty());
        Started=0;return true;
    }
    if(FPlatformTime::Seconds()-Started>45){Test->AddError(TEXT("Native scene/socket did not become ready within 45s"));Started=0;return true;}return false;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWorldLiveTest,"AIWorld.Live.SavedVillage",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FWorldLiveTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FWorldConnectionWait(this));return true;}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWorldGridTest,"AIWorld.Protocol.SaveAndTerrain",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FWorldGridTest::RunTest(const FString&) {
    TArray<uint8> Bytes;Bytes.SetNumZeroed(32*32*8);Bytes[1+32*(1+32)]=3;auto J=MakeShared<FJsonObject>();J->SetNumberField(TEXT("format"),1);J->SetNumberField(TEXT("size"),32);J->SetNumberField(TEXT("height"),8);J->SetNumberField(TEXT("chunk"),32);J->SetStringField(TEXT("base"),FBase64::Encode(Bytes));
    FGrid G;FString Error;TestTrue(TEXT("Valid original block payload"),G.Load(J,Error));TestEqual(TEXT("Coordinate order x + size*(z+size*y)"),G.Get(1,1,1),uint8(3));
    FMesh Solid,Water;MeshChunk(G,0,0,false,Solid,Water);TestEqual(TEXT("Isolated cube six faces"),Solid.Positions.Num(),24);TestEqual(TEXT("Twelve triangles"),Solid.Indices.Num(),36);
    auto E=Parse(EditCommand(1,1,1,0,3));TestTrue(TEXT("Apply edit"),G.Edit(E));TestEqual(TEXT("Removal"),G.Get(1,1,1),uint8(0));G.Restore({});TestEqual(TEXT("Reconnect restores base/removals"),G.Get(1,1,1),uint8(3));
    TestFalse(TEXT("Reject outside saved grid"),G.Edit(Parse(EditCommand(32,1,1,3,0))));J->SetNumberField(TEXT("size"),1025);TestFalse(TEXT("Reject oversized payload before allocation"),G.Load(J,Error));return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWorldCommandTest,"AIWorld.Protocol.NativeCommands",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FWorldCommandTest::RunTest(const FString&) {
    auto J=Parse(TextCommand(TEXT("ミオに木材を集めて")));TestEqual(TEXT("Japanese survives JSON"),String(J,TEXT("text")),FString(TEXT("ミオに木材を集めて")));TestEqual(TEXT("Instruction type"),String(J,TEXT("type")),FString(TEXT("instruction")));
    FGuid ID;TestTrue(TEXT("Server compatible UUID"),FGuid::Parse(String(J,TEXT("id")),ID));auto C=Parse(TextCommand(TEXT("何をしている？"),TEXT("haru")));TestEqual(TEXT("Conversation target"),String(C,TEXT("residentId")),FString(TEXT("haru")));
    TestTrue(TEXT("Reject unsupported speed"),SpeedCommand(99).IsEmpty());TestEqual(TEXT("Pause accepted"),Number(Parse(SpeedCommand(0)),TEXT("speed")),0.);return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWorldAssetTest,"AIWorld.Assets.AuthoredModels",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FWorldAssetTest::RunTest(const FString&) {
    FString Text;TestTrue(TEXT("Model export exists"),FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("Data/models.json"))));auto J=Parse(Text);TestTrue(TEXT("Paris and tower native mesh batches"),Array(J,TEXT("statics")).Num()>20);
    for(const auto& V:Array(J,TEXT("statics"))){FMesh M;TestTrue(TEXT("Float buffers decode and indices in range"),DecodeMesh(V->AsObject(),M));}
    for(const auto& Kind:{TEXT("hut"),TEXT("house"),TEXT("farm"),TEXT("warehouse")})TestTrue(TEXT("Native staged building recipe"),Array(Object(J,TEXT("buildings")),Kind).Num()>0);
    TestTrue(TEXT("Farmer resident outfit"),Object(Object(J,TEXT("residents")),TEXT("農家")).IsValid());return true;
}
#endif
