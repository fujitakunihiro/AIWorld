#include "WorldProtocol.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/CommandLine.h"
#include "ParisDigitalTwin.h"
#include "Engine/Engine.h"
#include "EngineUtils.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
using namespace AIWorld;
#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisCoordinateTest,"ParisDigitalTwin.Live.CoordinateAgreement",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisCoordinateTest::RunTest(const FString&) {
    FString Text;if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("Data/paris-digital-twin.json"))))return false;auto J=Parse(Text);FParisGeoReference Geo;auto G=Object(J,TEXT("georeference"));if(!TestTrue(TEXT("Native Lambert-93 matches the exported origin"),Geo.Load(G)))return false;
    double Worst=0;for(const auto& V:Array(J,TEXT("coordinate_checks"))){auto Check=V->AsObject();const auto& LL=Array(Check,TEXT("wgs84"));const auto& XYZ=Array(Check,TEXT("ue_cm"));FVector Expected(XYZ[0]->AsNumber(),XYZ[1]->AsNumber(),XYZ[2]->AsNumber());const double Height=Number(Check,TEXT("height_ngf_m"));const auto Native=Geo.ToUE(FVector2D(LL[0]->AsNumber(),LL[1]->AsNumber()),Height);Worst=FMath::Max(Worst,(Native-Expected).Size()/100);const auto Back=Geo.WGS84FromUE(Expected);TestTrue(TEXT("Inverse recovers Python WGS84"),(Back-FVector2D(LL[0]->AsNumber(),LL[1]->AsNumber())).Size()<1e-8);TestTrue(TEXT("NGF height survives native centimetre round trip"),FMath::Abs(Geo.NGFFromUE(Expected)-Height)<1e-9);}
    TestTrue(TEXT("C++ / PROJ projected positions agree within 1mm"),Worst<.001);AddInfo(FString::Printf(TEXT("Native / Python projection maximum disagreement %.9fm"),Worst));G->SetStringField(TEXT("axes"),TEXT("wrong axes"));TestFalse(TEXT("Reject double/incorrect axis interpretation"),Geo.Load(G));return true;
}
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
        if(Kind==TEXT("building")){auto A=Object(M,TEXT("properties"));Buildings+=Array(A,TEXT("source_ids")).Num();TestTrue(TEXT("Original buildings retained through batching"),Array(M,TEXT("appearance_ranges")).Num()==Array(A,TEXT("source_ids")).Num());}
        Water|=Kind==TEXT("water");Road|=Kind==TEXT("road");
    }
    TestTrue(TEXT("Real district buildings loaded"),Buildings>20);TestTrue(TEXT("River and roads share this scene"),Water&&Road);return true;
}
#endif

#if WITH_DEV_AUTOMATION_TESTS
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FParisTwinSceneWait,FAutomationTestBase*,Test);
bool FParisTwinSceneWait::Update() {
    static double Started=0;static FVector Start,End;if(Started==0){Started=FPlatformTime::Seconds();FString Text;FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("Data/paris-digital-twin.json")));auto J=Parse(Text);for(const auto& V:Array(J,TEXT("objects"))){auto M=V->AsObject();if(String(M,TEXT("kind"))!=TEXT("roof"))continue;const auto& Points=Array(M,TEXT("positions_cm"));FVector Centre=FVector::ZeroVector;for(int32 I=Points.Num()-3;I<Points.Num();I++){const auto& P=Points[I]->AsArray();Centre+=FVector(P[0]->AsNumber(),P[1]->AsNumber(),P[2]->AsNumber())/3;}Start=Centre+FVector(0,0,200);End=Centre-FVector(0,0,10000);break;}}
    for(const auto& Context:GEngine->GetWorldContexts())if(Context.World())for(TActorIterator<AParisTwinScene> It(Context.World());It;++It){auto Scene=*It;if(!Scene->bReady)continue;FHitResult Hit;if(!Context.World()->LineTraceSingleByChannel(Hit,Start,End,ECC_Visibility)||Hit.GetActor()!=Scene)continue;Scene->SelectHit(Hit);
        Test->TestTrue(TEXT("Building selection keeps original OSM ID"),Scene->Selection.Contains(TEXT("osm/")));Test->TestTrue(TEXT("Building selection displays WGS84 and height evidence"),Scene->Selection.Contains(TEXT("WGS84 source anchor"))&&Scene->Selection.Contains(TEXT("height")));
        auto Mesh=Cast<UProceduralMeshComponent>(Hit.GetComponent());const FColor Before=Mesh->GetProcMeshSection(0)->ProcVertexBuffer[0].Color;
        Scene->ToggleLevels();Test->TestTrue(TEXT("L1 debug mode toggles on"),Scene->bLevels);Scene->ToggleLevels();Test->TestFalse(TEXT("Debug mode restores appearance"),Scene->bLevels);Test->TestTrue(TEXT("Debug mode preserves original vertex colour"),Mesh->GetProcMeshSection(0)->ProcVertexBuffer[0].Color==Before);
        Test->TestTrue(TEXT("Footprint picker resolves the real source polygon"),Scene->SourceAt(Hit.ImpactPoint,TEXT("building")).IsValid());
        if(auto Source=Scene->SourceAt(Hit.ImpactPoint,TEXT("building"))){const auto& Polygons=Array(Source,TEXT("polygons_cm"));if(!Polygons.IsEmpty()){const auto& Boundary=Polygons[0]->AsArray()[0]->AsArray()[0]->AsArray();const FVector Vertex(Boundary[0]->AsNumber(),Boundary[1]->AsNumber(),0);Test->TestTrue(TEXT("Batched wall boundary retains an individual source selection"),Scene->SourceAt(Vertex,TEXT("building")).IsValid());}}
        Scene->SelectHit(Hit);Test->TestTrue(TEXT("Actual hit geographic coordinates are separate from the source anchor"),Scene->Selection.Contains(TEXT("CLICK WGS84 lon"))&&Scene->Selection.Contains(TEXT("EPSG:2154")));
        Test->TestTrue(TEXT("Actual hit displays orthometric elevation"),Scene->Selection.Contains(TEXT("NGF-IGN69")));
        Scene->ToggleFootprints();Test->TestTrue(TEXT("Footprint mode hides volume meshes"),Scene->bFootprints&&!Mesh->IsVisible());Test->TestTrue(TEXT("Hidden roofs do not intercept map clicks"),Mesh->GetCollisionEnabled()==ECollisionEnabled::NoCollision);
        FHitResult FlatHit;Test->TestTrue(TEXT("Ground remains selectable in footprint mode"),Context.World()->LineTraceSingleByChannel(FlatHit,Start,End,ECC_Visibility));Scene->SelectHit(FlatHit);Test->TestTrue(TEXT("Flat map still identifies a building footprint"),Scene->Selection.Contains(TEXT("osm/"))&&Scene->Selection.Contains(TEXT("height")));
        Scene->ToggleFootprints();Test->TestTrue(TEXT("Volume mode restores roof collision"),Mesh->IsVisible()&&Mesh->GetCollisionEnabled()==ECollisionEnabled::QueryAndPhysics);
        Scene->ToggleIssues();Test->TestTrue(TEXT("Source review overlay enables"),Scene->bIssues);Scene->ToggleIssues();Test->TestTrue(TEXT("Source review restores original appearance"),!Scene->bIssues&&Mesh->GetProcMeshSection(0)->ProcVertexBuffer[0].Color==Before);
        Scene->FocusLandmark(0);auto Camera=Cast<AParisTwinCamera>(Context.World()->GetFirstPlayerController()->GetPawn());Test->TestTrue(TEXT("Landmark navigation focuses a real coordinate"),Camera&&!Camera->bEye&&(Camera->Target-Scene->SceneCentre).Size()>1000);if(Camera)Camera->Overview(Scene->Extent,Scene->SceneCentre);
        Started=0;return true;}
    if(FPlatformTime::Seconds()-Started>25){Test->AddError(TEXT("GIS scene collision/selection did not become ready"));Started=0;return true;}return false;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisTwinLiveTest,"ParisDigitalTwin.Live.SceneCollisionAndDebug",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisTwinLiveTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FParisTwinSceneWait(this));return true;}

DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FParisTwinStreetWait,FAutomationTestBase*,Test);
bool FParisTwinStreetWait::Update() {
    static double Started=0;if(Started==0)Started=FPlatformTime::Seconds();
    for(const auto& Context:GEngine->GetWorldContexts())if(Context.World())for(TActorIterator<AParisTwinScene> It(Context.World());It;++It){auto Scene=*It;if(!Scene->bReady)continue;
        TArray<UHierarchicalInstancedStaticMeshComponent*> Instances;Scene->GetComponents(Instances);
        Test->TestEqual(TEXT("Eleven shared street prototypes instead of thousands of components"),Instances.Num(),11);
        Test->TestTrue(TEXT("Real mapped furniture loaded"),Scene->StreetCount>1500&&Scene->InstanceCount>Scene->StreetCount);
        for(auto Mesh:Instances)if(Mesh->GetInstanceCount()>0){
            auto Source=Scene->StreetInstanceSource(Mesh,0);Test->TestTrue(TEXT("Instance index resolves an original mapped node"),Source.IsValid());if(!Source)continue;
            FTransform Transform;Mesh->GetInstanceTransform(0,Transform,true);FHitResult Pick;Pick.Component=Mesh;Pick.Item=0;Pick.ImpactPoint=Transform.GetLocation();Scene->SelectHit(Pick);
            Test->TestTrue(TEXT("Instance selection displays the correct original OSM node"),Scene->Selection.Contains(String(Source,TEXT("id")))&&Scene->Selection.Contains(TEXT("Mapped OSM position")));
            Test->TestTrue(TEXT("Instance selection distinguishes inferred appearance"),Scene->Selection.Contains(TEXT("unverified")));
            Test->TestFalse(TEXT("Out-of-range hit index cannot select an unrelated node"),Scene->StreetInstanceSource(Mesh,Mesh->GetInstanceCount()).IsValid());
        }
        const int32 Quality=Scene->DetailQuality,Count=Scene->InstanceCount;
        if(!Instances.IsEmpty()){
            FTransform Transform;Instances[0]->GetInstanceTransform(0,Transform,true);
            FHitResult Hit;FCollisionQueryParams Params;Params.bTraceComplex=true;
            const bool HitObject=Context.World()->LineTraceSingleByChannel(Hit,Transform.GetLocation()+FVector(0,0,6000),Transform.GetLocation()-FVector(0,0,100),ECC_Visibility,Params);
            auto Source=HitObject?Scene->StreetInstanceSource(Hit.GetComponent(),Hit.Item):nullptr;
            Test->TestTrue(TEXT("Actual complex cursor trace hits a mapped tree proxy"),Source.IsValid()&&String(Source,TEXT("kind"))==TEXT("street_tree"));
        }
        for(int32 I=0;I<3;I++)Scene->CycleDetailQuality();Test->TestEqual(TEXT("Quality cycling restores selected preset"),Scene->DetailQuality,Quality);Test->TestEqual(TEXT("Visual quality never deletes GIS instances"),Scene->InstanceCount,Count);
        Scene->ToggleStreetDetails();for(auto Mesh:Instances)Test->TestTrue(TEXT("Disabled props do not intercept picking"),!Mesh->IsVisible()&&Mesh->GetCollisionEnabled()==ECollisionEnabled::NoCollision);
        Scene->ToggleFootprints();Scene->ToggleFootprints();for(auto Mesh:Instances)Test->TestFalse(TEXT("Footprint mode preserves user-disabled street details"),Mesh->IsVisible());
        Scene->ToggleStreetDetails();for(auto Mesh:Instances)Test->TestTrue(TEXT("Street detail toggle restores rendering and queries"),Mesh->IsVisible()&&Mesh->GetCollisionEnabled()!=ECollisionEnabled::NoCollision);
        Started=0;return true;
    }
    if(FPlatformTime::Seconds()-Started>25){Test->AddError(TEXT("Street instance scene did not become ready"));Started=0;return true;}return false;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisTwinStreetTest,"ParisDigitalTwin.Live.StreetInstancesAndQuality",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisTwinStreetTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FParisTwinStreetWait(this));return true;}
#endif
