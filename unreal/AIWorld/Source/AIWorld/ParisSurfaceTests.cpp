#include "ParisDigitalTwin.h"
#include "Misc/AutomationTest.h"
#include "Engine/Engine.h"
#include "Engine/Texture2D.h"
#include "Engine/TextureCube.h"
#include "EngineUtils.h"
#include "ProceduralMeshComponent.h"
#include "Materials/MaterialInterface.h"
#include "Materials/Material.h"

#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisPhotoTest,"ParisDigitalTwin.Live.PhotographicSurfaceBindings",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisPhotoTest::RunTest(const FString&){
    for(const FString Key:{TEXT("Stone"),TEXT("Paving"),TEXT("Grass"),TEXT("Asphalt"),TEXT("Wood")}){
        const FString MatName=Key==TEXT("Stone")?TEXT("Limestone"):Key==TEXT("Grass")?TEXT("GrassPhotographic"):Key==TEXT("Asphalt")?TEXT("AsphaltPhotographic"):Key==TEXT("Wood")?TEXT("Wood"):TEXT("Paving");
        auto Mat=LoadObject<UMaterial>(nullptr,*(TEXT("/Game/Materials/M_Paris")+MatName));
        if(!TestNotNull(TEXT("Actual photo material loads"),Mat))continue;
        TestFalse(TEXT("Normal graph is in world space"),Mat->bTangentSpaceNormal);
        for(const FString Role:{TEXT("Albedo"),TEXT("Normal"),TEXT("Orm")}){
            auto Texture=LoadObject<UTexture2D>(nullptr,*(TEXT("/Game/Textures/T_ParisPhoto")+Key+Role));
            if(!TestNotNull(TEXT("Bundled photographic texture loads"),Texture))continue;
#if WITH_EDITOR
            // NullRHI has no compiled shader resources for GetUsedTextures.
            // Follow the serialized output chain instead of testing an empty
            // GPU resource list, including external inputs to function calls.
            TArray<UMaterialExpression*> Chain;
            Mat->GetExpressionsInPropertyChain(Role==TEXT("Albedo")?MP_BaseColor:Role==TEXT("Normal")?MP_Normal:MP_Roughness,Chain,nullptr);
            TestTrue(TEXT("Texture is wired into the material output"),Chain.ContainsByPredicate([&](auto Expression){return Expression&&Expression->GetReferencedTexture()==Texture;}));
#endif
            TestEqual(TEXT("Correct colour space per role"),bool(Texture->SRGB),Role==TEXT("Albedo"));
            if(Role==TEXT("Normal")){
                TestEqual(TEXT("Normal compression"),Texture->CompressionSettings,TC_Normalmap);
#if WITH_EDITORONLY_DATA
                TestFalse(TEXT("DirectX normals are not inverted twice"),bool(Texture->bFlipGreenChannel));
#endif
            }
            if(Role==TEXT("Orm"))TestEqual(TEXT("ORM retains independent linear channels"),Texture->CompressionSettings,TC_Masks);
#if WITH_EDITORONLY_DATA
            TestEqual(TEXT("Actual 2K source width"),Texture->Source.GetSizeX(),int64(2048));
            TestEqual(TEXT("Actual 2K source height"),Texture->Source.GetSizeY(),int64(2048));
#endif
        }
        if(Key==TEXT("Stone")||Key==TEXT("Paving"))TestNotNull(TEXT("Original procedural fallback remains loadable"),LoadObject<UMaterial>(nullptr,*(TEXT("/Game/Materials/M_Paris")+MatName+TEXT("Procedural"))));
    }
    TestNotNull(TEXT("Actual HDR environment imports as a cubemap"),LoadObject<UTextureCube>(nullptr,TEXT("/Game/Textures/T_ParisDayEnvironment")));
    auto Cathedral=LoadObject<UMaterial>(nullptr,TEXT("/Game/Materials/M_ParisCathedralStone"));
    if(TestNotNull(TEXT("Belfry source display material exists"),Cathedral)){
        TestEqual(TEXT("Only the visual openings are masked"),Cathedral->GetBlendMode(),BLEND_Masked);
#if WITH_EDITOR
        TArray<UMaterialExpression*> MaskChain;Cathedral->GetExpressionsInPropertyChain(MP_OpacityMask,MaskChain,nullptr);
        TestTrue(TEXT("The opening mask has a serialized position-dependent graph"),MaskChain.Num()>=2);
#endif
    }
    auto Sky=LoadObject<UMaterial>(nullptr,TEXT("/Game/Materials/M_ParisPhotographicSky"));
    if(TestNotNull(TEXT("Visible photographic sky exists"),Sky))TestTrue(TEXT("Panorama is a sky surface"),Sky->bIsSky);
    return true;
}
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FParisSurfaceWait,FAutomationTestBase*,Test);
bool FParisSurfaceWait::Update() {
    static double Started=0;if(Started==0)Started=FPlatformTime::Seconds();
    for(const auto& Context:GEngine->GetWorldContexts())if(Context.World())for(TActorIterator<AParisTwinScene> It(Context.World());It;++It){
        auto Scene=*It;if(!Scene->bReady)continue;
        for(const FString Name:{TEXT("Limestone"),TEXT("Slate"),TEXT("Zinc"),TEXT("Paving"),TEXT("Asphalt")}){
            auto Base=LoadObject<UTexture2D>(nullptr,*(TEXT("/Game/Textures/T_Paris")+Name+TEXT("Basecolor")));
            auto Packed=LoadObject<UTexture2D>(nullptr,*(TEXT("/Game/Textures/T_Paris")+Name+TEXT("Surface")));
            if(Test->TestNotNull(TEXT("Authored albedo imported"),Base)){
                Test->TestTrue(TEXT("Base colour uses sRGB"),Base->SRGB);
#if WITH_EDITORONLY_DATA
                // NullRHI deliberately has no GPU platform mip data (GetSizeX
                // returns zero); inspect the actual imported source instead.
                Test->TestEqual(TEXT("Imported source width"),Base->Source.GetSizeX(),int64(512));
                Test->TestEqual(TEXT("Imported source height"),Base->Source.GetSizeY(),int64(512));
#endif
            }
            if(Test->TestNotNull(TEXT("Packed PBR imported"),Packed))Test->TestTrue(TEXT("PBR channels stay linear with wrapping"),!Packed->SRGB&&Packed->AddressX==TA_Wrap&&Packed->AddressY==TA_Wrap);
        }
        const int32 Quality=Scene->DetailQuality;const bool Surfaces=Scene->bDetailedSurfaces;
        Scene->DetailQuality=1;if(!Scene->bDetailedSurfaces)Scene->ToggleSurfaces();Scene->ApplyDetailQuality();
        TArray<UProceduralMeshComponent*> Meshes;Scene->GetComponents(Meshes);
        UProceduralMeshComponent* Wall=nullptr;TArray<UProceduralMeshComponent*> Details;int32 Paving=0;
        for(auto Mesh:Meshes)if(auto Material=Mesh->GetMaterial(0)){
            if(Material->GetMaterial()->GetName()==TEXT("M_ParisLimestone"))Wall=Mesh;
            if(Material->GetMaterial()->GetName()==TEXT("M_ParisPaving"))Paving++;
            if(Mesh->GetCollisionEnabled()==ECollisionEnabled::QueryOnly&&Mesh->GetCollisionResponseToChannel(ECC_Pawn)==ECR_Ignore&&Material->GetMaterial()->GetName()!=TEXT("M_Water")&&!Material->GetMaterial()->GetShadingModels().HasShadingModel(MSM_SingleLayerWater))Details.Add(Mesh);
        }
        Test->TestTrue(TEXT("Paving and walls use authored surfaces"),Wall&&Paving>0);
        Test->TestTrue(TEXT("Quality-zone window reliefs loaded"),Details.Num()>0);
        if(Wall){
            const int32 Vertices=Wall->GetProcMeshSection(0)->ProcVertexBuffer.Num();
            Scene->ToggleSurfaces();Test->TestEqual(TEXT("M toggles to the actual flat material"),Wall->GetMaterial(0)->GetName(),FString(TEXT("M_Vertex")));
            Scene->ToggleLevels();Scene->ToggleLevels();Test->TestEqual(TEXT("Accuracy overlay preserves flat preference"),Wall->GetMaterial(0)->GetName(),FString(TEXT("M_Vertex")));
            Scene->ToggleSurfaces();Test->TestEqual(TEXT("PBR restores without regenerating the city"),Wall->GetProcMeshSection(0)->ProcVertexBuffer.Num(),Vertices);
            Scene->DetailQuality=0;Scene->ApplyDetailQuality();Test->TestEqual(TEXT("Low quality avoids detailed surface shaders"),Wall->GetMaterial(0)->GetName(),FString(TEXT("M_Vertex")));
            for(auto Detail:Details)Test->TestTrue(TEXT("Low quality hides cosmetic geometry and picking"),!Detail->IsVisible()&&Detail->GetCollisionEnabled()==ECollisionEnabled::NoCollision);
            Scene->DetailQuality=1;Scene->ApplyDetailQuality();Scene->ToggleFootprints();Scene->ToggleFootprints();
            for(auto Detail:Details)Test->TestTrue(TEXT("Restored reliefs remain cosmetic and selectable"),Detail->IsVisible()&&Detail->GetCollisionEnabled()==ECollisionEnabled::QueryOnly&&Detail->GetCollisionResponseToChannel(ECC_Pawn)==ECR_Ignore);
        }
        Scene->DetailQuality=Quality;if(Scene->bDetailedSurfaces!=Surfaces)Scene->ToggleSurfaces();Scene->ApplyDetailQuality();
        Started=0;return true;
    }
    if(FPlatformTime::Seconds()-Started>25){Test->AddError(TEXT("Surface verification scene did not become ready"));Started=0;return true;}return false;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisSurfaceTest,"ParisDigitalTwin.Live.SurfaceMaterialsAndDetails",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisSurfaceTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FParisSurfaceWait(this));return true;}
#endif
