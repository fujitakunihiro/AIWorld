#include "ParisRenderCache.h"
#include "ParisCollisionMesh.h"
#include "ParisDigitalTwin.h"
#include "WorldProtocol.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Engine/Engine.h"
#include "EngineUtils.h"
#include "ProceduralMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "StaticMeshResources.h"

#if WITH_DEV_AUTOMATION_TESTS
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FParisCacheWait,FAutomationTestBase*,Test);
bool FParisCacheWait::Update(){
    static double Started=0;if(Started==0)Started=FPlatformTime::Seconds();
    for(const auto& Context:GEngine->GetWorldContexts())if(Context.World())for(TActorIterator<AParisTwinScene> It(Context.World());It;++It){
        auto Scene=*It;if(!Scene->bReady)continue;
        auto Report=MakeShared<FJsonObject>();AddParisRenderCacheStats(Scene,Report);
        const bool Disabled=FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoRenderCache"));
        const int32 Count=AIWorld::Number(Report,TEXT("render_cache_components"));
        Test->TestTrue(TEXT("Explicit fallback keeps procedural rendering"),Disabled?Count==0:Count>0);
        TArray<UProceduralMeshComponent*> Sources;Scene->GetComponents(Sources);int32 Triangles=0;
        UProceduralMeshComponent* SelectedSource=nullptr;FVector TracePoint;
        for(auto Source:Sources)if(auto Cache=FindParisRenderCache(Source)){
            const auto Section=Source->GetProcMeshSection(0);const auto& LOD=Cache->GetStaticMesh()->GetRenderData()->LODResources[0];
            Test->TestEqual(TEXT("Cached triangles preserve GIS geometry"),int32(LOD.GetNumTriangles()),Section->ProcIndexBuffer.Num()/3);
            Test->TestTrue(TEXT("The procedural copy keeps visibility and collision without duplicate draws"),!Source->bRenderInMainPass&&!Source->bRenderInDepthPass&&!Source->CastShadow&&Source->IsVisible()&&Source->GetCollisionEnabled()==ECollisionEnabled::QueryAndPhysics);
            Test->TestTrue(TEXT("Render-only copy cannot create a second obstacle or intercept picking"),Cache->IsVisible()&&Cache->GetCollisionEnabled()==ECollisionEnabled::NoCollision&&!Cache->CanEverAffectNavigation());
            Test->TestEqual(TEXT("Cache uses the selected surface"),Cache->GetMaterial(0),Source->GetMaterial(0));
            Test->TestTrue(TEXT("Cached source allocates no duplicate procedural render proxy"),Cast<UParisCollisionMesh>(Source)&&Cast<UParisCollisionMesh>(Source)->UsesVisualCache());
            FBox Box(ForceInit);TSet<FColor> Palette;
            for(const auto& Vertex:Section->ProcVertexBuffer){Box+=Vertex.Position;Palette.Add(Vertex.Color);}
            const auto Bounds=Cache->GetStaticMesh()->GetBounds();
            Test->TestTrue(TEXT("Footprint and height bounds agree within 1mm"),(Box.GetCenter()-Bounds.Origin).GetAbsMax()<.1&&(Box.GetExtent()-Bounds.BoxExtent).GetAbsMax()<.1);
            const auto& Buffer=LOD.VertexBuffers.ColorVertexBuffer;
            for(uint32 V=0;V<Buffer.GetNumVertices();V+=FMath::Max(1u,Buffer.GetNumVertices()/12))Test->TestTrue(TEXT("Linear vertex colour survives the renderer change"),Palette.Contains(Buffer.VertexColor(V)));
            Triangles+=Section->ProcIndexBuffer.Num()/3;
            if(!SelectedSource)for(int32 I=0;I<Section->ProcIndexBuffer.Num();I+=3){
                const auto& A=Section->ProcVertexBuffer[Section->ProcIndexBuffer[I]];
                if(A.Normal.Z<.7)continue;
                TracePoint=(A.Position+Section->ProcVertexBuffer[Section->ProcIndexBuffer[I+1]].Position+Section->ProcVertexBuffer[Section->ProcIndexBuffer[I+2]].Position)/3;
                SelectedSource=Source;break;
            }
        }
        Test->TestEqual(TEXT("Benchmark reports actual cached triangles"),int32(AIWorld::Number(Report,TEXT("render_cache_triangles"))),Triangles);
        if(SelectedSource){
            FHitResult Hit;FCollisionQueryParams Params;Params.bTraceComplex=true;
            Test->TestTrue(TEXT("Visible cached city retains original GIS collision"),Context.World()->LineTraceSingleByChannel(Hit,TracePoint+FVector(0,0,1000),TracePoint-FVector(0,0,1000),ECC_Visibility,Params)&&Hit.GetActor()==Scene);
            Scene->SelectHit(Hit);Test->TestTrue(TEXT("Click still resolves a geographic source"),Scene->Selection.Contains(TEXT("osm/"))&&Scene->Selection.Contains(TEXT("CLICK WGS84")));
            Scene->ClearInspection();Scene->ToggleLevels();
            for(auto Source:Sources)if(auto Cache=FindParisRenderCache(Source))Test->TestTrue(TEXT("Accuracy colours use original dynamic vertices"),Source->bRenderInMainPass&&Source->bRenderInDepthPass&&!Cache->IsVisible());
            Scene->ToggleLevels();Scene->ToggleIssues();
            for(auto Source:Sources)if(auto Cache=FindParisRenderCache(Source))Test->TestTrue(TEXT("Issue colours bypass the immutable copy"),Source->bRenderInMainPass&&!Cache->IsVisible());
            Scene->ToggleIssues();Scene->ToggleFootprints();
            for(auto Source:Sources)if(auto Cache=FindParisRenderCache(Source))Test->TestTrue(TEXT("Footprint mode hides both visual paths and original collision"),!Cache->IsVisible()&&!Source->IsVisible()&&Source->GetCollisionEnabled()==ECollisionEnabled::NoCollision);
            Scene->ToggleFootprints();Scene->ToggleSurfaces();
            for(auto Source:Sources)if(auto Cache=FindParisRenderCache(Source))Test->TestTrue(TEXT("Surface toggle and volume restoration synchronize the cache"),!Source->bRenderInMainPass&&Source->IsVisible()&&Cache->IsVisible()&&Cache->GetMaterial(0)==Source->GetMaterial(0));
            Scene->ToggleSurfaces();
        }
        Started=0;return true;
    }
    if(FPlatformTime::Seconds()-Started>30){Test->AddError(TEXT("Render cache scene did not become ready"));Started=0;return true;}return false;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisCacheTest,"ParisDigitalTwin.Live.RenderCacheParityAndModes",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisCacheTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FParisCacheWait(this));return true;}
#endif
