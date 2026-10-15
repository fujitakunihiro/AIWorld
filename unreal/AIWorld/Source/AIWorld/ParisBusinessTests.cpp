#include "ParisDigitalTwin.h"
#include "ParisRuntimeMesh.h"
#include "WorldProtocol.h"
#include "Misc/AutomationTest.h"
#include "Misc/Crc.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Camera/PlayerCameraManager.h"
using namespace AIWorld;

#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisRuntimeTest,"ParisDigitalTwin.Live.RuntimePacketSafety",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisRuntimeTest::RunTest(const FString&){
    // Fixed little-endian fixture, separately compared with the legacy arrays.
    auto Source=AIWorld::Parse(TEXT("{\"color\":\"#112233\",\"positions_cm\":[[0,0,0],[100,0,0],[0,100,0]],\"normals\":[[0,0,1],[0,0,1],[0,0,1]],\"indices\":[0,1,2]}"));
    TArray<uint8> Blob={'P','A','R','I','S','M','0','1',1,0,0,0,1,0,0,0};
    auto U32=[&](uint32 V){for(int32 I=0;I<4;I++)Blob.Add(uint8((V>>(8*I))&255));};
    auto Float=[&](float V){uint32 Bits;FMemory::Memcpy(&Bits,&V,4);U32(Bits);};
    for(const FVector3f P:{FVector3f(0,0,0),FVector3f(100,0,0),FVector3f(0,100,0)}){Float(P.X);Float(P.Y);Float(P.Z);Float(0);Float(0);Float(1);Blob.Append({0x11,0x22,0x33,0xff});}
    U32(0);U32(1);U32(2);
    auto Descriptor=MakeShared<FJsonObject>();Descriptor->SetNumberField(TEXT("offset"),16);Descriptor->SetNumberField(TEXT("vertex_count"),3);Descriptor->SetNumberField(TEXT("index_count"),3);Descriptor->SetNumberField(TEXT("byte_length"),96);
    auto Compact=MakeShared<FJsonObject>();Compact->SetObjectField(TEXT("mesh_buffer"),Descriptor);
    auto Meta=MakeShared<FJsonObject>();Meta->SetStringField(TEXT("file"),TEXT("paris-digital-twin-meshes.bin"));Meta->SetStringField(TEXT("format"),TEXT("paris_mesh_le_v1"));Meta->SetNumberField(TEXT("bytes"),Blob.Num());Meta->SetNumberField(TEXT("mesh_count"),1);Meta->SetNumberField(TEXT("vertex_stride"),28);Meta->SetStringField(TEXT("crc32"),FString::Printf(TEXT("%08x"),FCrc::MemCrc32(Blob.GetData(),Blob.Num())));
    FString Error;FParisMeshArrays A,B;
    TestTrue(TEXT("Valid runtime header and CRC accepted"),ValidateParisMeshBlob(Meta,Blob,Error));TestTrue(TEXT("Compact fixture decodes"),ReadParisMeshArrays(Compact,Blob,A,Error));TestTrue(TEXT("Legacy fixture decodes"),ReadParisMeshArrays(Source,{},B,Error));
    TestTrue(TEXT("Both modes preserve positions, indices and sRGB colours"),A.Positions==B.Positions&&A.Indices==B.Indices&&A.Colors==B.Colors&&A.Normals==B.Normals);
    Blob.Last()^=1;TestFalse(TEXT("Corrupted payload rejected before use"),ValidateParisMeshBlob(Meta,Blob,Error));Blob.Last()^=1;
    Descriptor->SetNumberField(TEXT("offset"),Blob.Num()+1);TestFalse(TEXT("Out-of-bounds offset cannot read memory"),ReadParisMeshArrays(Compact,Blob,A,Error));Descriptor->SetNumberField(TEXT("offset"),16);
    Blob[100]=3;TestFalse(TEXT("Out-of-range triangle index rejected"),ReadParisMeshArrays(Compact,Blob,A,Error));Blob[100]=0;
    Blob[18]=0xc0;Blob[19]=0x7f;TestFalse(TEXT("Nonfinite float rejected"),ReadParisMeshArrays(Compact,Blob,A,Error));return true;
}

DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FParisBusinessWait,FAutomationTestBase*,Test);
bool FParisBusinessWait::Update(){
    static double Started=0;if(Started==0)Started=FPlatformTime::Seconds();
    for(const auto& Context:GEngine->GetWorldContexts())if(Context.World())for(TActorIterator<AParisTwinScene> It(Context.World());It;++It){auto Scene=*It;if(!Scene->bReady)continue;
        Test->TestTrue(TEXT("Mapped businesses and safe inferred terraces generated"),Scene->BusinessCount>20&&Scene->TerraceCount>0);
        Test->TestEqual(TEXT("Requested runtime mode actually used"),Scene->bCompactRuntime,!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinLegacyJSON")));
        Test->TestTrue(TEXT("Startup timing and input size recorded"),Scene->SceneLoadMs>0&&Scene->SceneInputBytes>100000);
        TArray<UHierarchicalInstancedStaticMeshComponent*> Meshes;Scene->GetComponents(Meshes);bool Selected=false;
        for(auto Mesh:Meshes)if(Mesh->GetInstanceCount()>0){auto Source=Scene->StreetInstanceSource(Mesh,0);if(!Source||String(Source,TEXT("kind"))!=TEXT("business"))continue;
            FTransform T;Mesh->GetInstanceTransform(0,T,true);FHitResult Hit(Scene,Mesh,T.GetLocation(),FVector::UpVector);Hit.Item=0;Scene->SelectHit(Hit);
            Test->TestTrue(TEXT("Business inspection retains POI and distinguishes inferred facade"),Scene->Selection.Contains(String(Source,TEXT("id")))&&Scene->Selection.Contains(TEXT("Inferred storefront"))&&Scene->Selection.Contains(TEXT("WGS84 source anchor")));Selected=true;break;
        }
        Test->TestTrue(TEXT("Business instances are individually traceable"),Selected);
        if(!Scene->FocusBusiness()){if(FPlatformTime::Seconds()-Started<25)return false;Test->AddError(TEXT("No clear cafe camera position"));}
        if(auto PC=Cast<AParisTwinController>(Context.World()->GetFirstPlayerController())){auto C=Cast<AParisTwinCamera>(PC->GetPawn());Test->TestTrue(TEXT("Cafe view is outside a building at eye level"),C&&C->bEye&&!Scene->SourceAt(C->Target,TEXT("building")).IsValid());PC->Overview();}
        Started=0;return true;
    }
    if(FPlatformTime::Seconds()-Started>25){Test->AddError(TEXT("Business scene did not load"));Started=0;return true;}return false;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisBusinessLiveTest,"ParisDigitalTwin.Live.BusinessesAndTerraces",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisBusinessLiveTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FParisBusinessWait(this));return true;}
#endif
