#include "ParisPhotoArchitecture.h"
#include "ParisPhotoFrontages.h"
#include "ParisScannedStatue.h"
#include "ParisRoadDetail.h"
#include "ParisDigitalTwin.h"
#include "WorldProtocol.h"
#include "Components/StaticMeshComponent.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "StaticMeshResources.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
using namespace AIWorld;

static TSharedPtr<FJsonObject> ScannedFacadeData(const TSharedPtr<FJsonObject>& Architecture){
    if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoScannedFacade")))return nullptr;
    FString Text;TSharedPtr<FJsonObject> Data;
    if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("Data/paris-notredame-scan.json")))||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Data)||!Data)return nullptr;
    if(String(Data,TEXT("format"))!=TEXT("paris_historic_scanned_facade_v1")||String(Data,TEXT("source_id"))!=TEXT("osm/way/201611261")||String(Object(Data,TEXT("source")),TEXT("license"))!=TEXT("CC-BY-4.0"))return nullptr;
    // The generated vertices already use this frame; never transform them twice.
    for(const FString Field:{TEXT("front_cm"),TEXT("across"),TEXT("depth")}){
        const auto& A=Array(Object(Architecture,TEXT("local_frame")),*Field);const auto& B=Array(Object(Data,TEXT("local_frame")),*Field);
        if(A.Num()!=3||B.Num()!=3)return nullptr;
        for(int32 I=0;I<3;I++)if(!FMath::IsFinite(B[I]->AsNumber())||FMath::Abs(A[I]->AsNumber()-B[I]->AsNumber())>.0001)return nullptr;
    }
    return Data;
}

TMap<FString,UStaticMesh*> LoadParisPhotoStreetMeshes(){
    TMap<FString,UStaticMesh*> Result;
    if(!FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal"))||FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoPhotoStreet")))return Result;
    FString Text;TSharedPtr<FJsonObject> Data;
    if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("Data/paris-photo-street.json")))||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Data)||!Data||String(Data,TEXT("format"))!=TEXT("paris_original_street_detail_v1"))return Result;
    for(const auto& Value:Array(Data,TEXT("objects"))){auto J=Value->AsObject();const FString ID=String(J,TEXT("id")),Path=String(J,TEXT("asset"));
        if((ID==TEXT("lamp_metal")||ID==TEXT("lamp_glass"))&&Path.StartsWith(TEXT("/Game/ParisPhotoreal/Street/SM_ParisLantern_")))
            if(auto Mesh=LoadObject<UStaticMesh>(nullptr,*Path))Result.Add(ID,Mesh);
    }
    // Never hide one half of a source fixture when the other asset is missing.
    if(Result.Num()!=2)Result.Empty();
    return Result;
}

void SyncParisPhotoStreetDetails(AParisTwinScene* Scene){
    const bool Detailed=Scene->DetailQuality>0&&!Scene->bFootprints&&!Scene->bLevels&&!Scene->bIssues;
    TArray<UInstancedStaticMeshComponent*> Parts;Scene->GetComponents(Parts);
    for(auto Part:Parts){
        if(Part->ComponentHasTag(TEXT("ParisPhotoStreetLamp"))){
            Part->SetVisibility(Detailed&&Scene->bStreetDetails);
            Part->SetCullDistances(Scene->DetailQuality==2?20000:14000,Scene->DetailQuality==2?25000:18000);
        }
        // Keep the original box collider / selection index alive. Debug and
        // Low restore that original rendering without duplicating either view.
        if(Part->ComponentHasTag(TEXT("ParisPhotoLampProxy"))){Part->SetRenderInMainPass(!Detailed);Part->SetRenderInDepthPass(!Detailed);}
    }
}

void CreateParisPhotoArchitecture(AParisTwinScene* Scene){
    if(!FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal"))||FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoArchitecture")))return;
    FString Text;TSharedPtr<FJsonObject> Data;
    if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("Data/paris-photo-architecture.json")))||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Data)||!Data)return;
    if(String(Data,TEXT("source_id"))!=TEXT("osm/way/201611261"))return;
    const auto& Origin=Array(Data,TEXT("origin_wgs84"));
    if(Origin.Num()!=2||FMath::Abs(Number(Data,TEXT("origin_elevation_ngf_m"))-Scene->GeoReference.OriginElevationNGF)>.001)return;
    // Verify the shared frame, never apply a second GIS/Cesium transform.
    if(Scene->GeoReference.ToUE(FVector2D(Origin[0]->AsNumber(),Origin[1]->AsNumber()),Scene->GeoReference.OriginElevationNGF).Size()>.1)return;
    auto Scan=ScannedFacadeData(Data);TMap<FString,UMaterialInterface*> Underlays;UStaticMesh* ScanMesh=nullptr;UMaterialInterface* ScanSurface=nullptr;
    if(Scan){
        const FString Prefix=TEXT("/Game/ParisPhotoreal/NotreDameScan/");const FString Path=String(Scan,TEXT("asset"));
        if(Path.StartsWith(Prefix))ScanMesh=LoadObject<UStaticMesh>(nullptr,*Path);
        const FString SurfacePath=String(Scan,TEXT("surface_material"));
        if(SurfacePath.StartsWith(Prefix))ScanSurface=LoadObject<UMaterialInterface>(nullptr,*SurfacePath);
        for(const FString ID:{TEXT("stone"),TEXT("wood"),TEXT("glass"),TEXT("iron"),TEXT("sculpture"),TEXT("stained"),TEXT("body")}){
            const FString MaterialPath=String(Object(Scan,TEXT("underlays")),*ID);
            if(MaterialPath.StartsWith(Prefix))if(auto Material=LoadObject<UMaterialInterface>(nullptr,*MaterialPath))Underlays.Add(ID,Material);
        }
        if(!ScanMesh||!ScanSurface||Underlays.Num()!=7){ScanMesh=nullptr;Underlays.Empty();UE_LOG(LogTemp,Warning,TEXT("Incomplete observed facade assets; keeping the complete authored fallback"));}
    }
    Scene->bPhotoScanReady=ScanMesh!=nullptr;
    if(ScanMesh)Scene->PhotoScanBodyMaterial=Underlays[TEXT("body")];
    for(const auto& Value:Array(Data,TEXT("objects"))){auto J=Value->AsObject();const FString Path=String(J,TEXT("asset"));if(!Path.StartsWith(TEXT("/Game/ParisPhotoreal/Architecture/SM_NotreDameWest_")))continue;
        auto Mesh=LoadObject<UStaticMesh>(nullptr,*Path);if(!Mesh){UE_LOG(LogTemp,Warning,TEXT("Missing authored facade asset %s"),*Path);continue;}
        auto Part=NewObject<UStaticMeshComponent>(Scene);Scene->AddInstanceComponent(Part);Part->SetupAttachment(Scene->GetRootComponent());Part->SetStaticMesh(Mesh);
        if(auto Material=Underlays.Find(String(J,TEXT("id"))))Part->SetMaterial(0,UMaterialInstanceDynamic::Create(*Material,Part));
        if(String(J,TEXT("id"))==TEXT("virgin_fallback"))Part->ComponentTags.Add(TEXT("ParisVirginFallback"));
        Part->ComponentTags.Add(TEXT("ParisPhotoArchitecture"));Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);Part->SetCanEverAffectNavigation(false);Part->SetCullDistance(45000);Part->RegisterComponent();
    }
    if(ScanMesh){
        auto Part=NewObject<UStaticMeshComponent>(Scene);Scene->AddInstanceComponent(Part);Part->SetupAttachment(Scene->GetRootComponent());Part->SetStaticMesh(ScanMesh);
        Part->SetMaterial(0,ScanSurface);
        // Coverage masks remain on the source body at distance. Keep the one
        // observed patch available there too; Nanite supplies its distant LOD.
        Part->ComponentTags.Add(TEXT("ParisScannedFacade"));Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);Part->SetCanEverAffectNavigation(false);Part->SetCullDistance(0);Part->RegisterComponent();
    }
    CreateParisScannedStatue(Scene,Data);
    Scene->ApplyDetailQuality();
}

void SyncParisPhotoArchitecture(AParisTwinScene* Scene){
    TArray<UStaticMeshComponent*> Parts;Scene->GetComponents(Parts);
    const bool Detailed=Scene->DetailQuality>0&&!Scene->bFootprints&&!Scene->bLevels&&!Scene->bIssues;
    const bool ScanVisible=Detailed&&Scene->bDetailedSurfaces&&Scene->bPhotoScanReady;
    for(auto Part:Parts){
        if(Part->ComponentHasTag(TEXT("ParisPhotoArchitecture"))){
            Part->SetVisibility(Detailed);
            if(auto Material=Cast<UMaterialInstanceDynamic>(Part->GetMaterial(0)))Material->SetScalarParameterValue(TEXT("NDScanActive"),ScanVisible?1.f:0.f);
        }
        if(Part->ComponentHasTag(TEXT("ParisScannedFacade")))Part->SetVisibility(ScanVisible);
    }
    SyncParisScannedStatue(Scene,Detailed);
}

void AddParisPhotoDetailStats(const AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Report){
    AddParisRoadDetailStats(Scene,Report);
    AddParisFrontageStats(Scene,Report);
    AddParisScannedStatueStats(Scene,Report);
    int32 Architecture=0,Trees=0,TreeCandidates=0,VisibleArchitecture=0,NaniteTrees=0,Lamps=0,LampParts=0,VisibleLamps=0,Ground=0,GroundVisible=0,GroundTriangles=0;int64 Triangles=0,TreeFallbackTriangles=0,LampTriangles=0;
    TArray<UStaticMeshComponent*> Parts;Scene->GetComponents(Parts);
    int32 ScanCount=0,ScanVisible=0,ScanNanite=0,ScanTriangles=0;
    for(auto Part:Parts){
        auto Mesh=Part->GetStaticMesh();if(!Mesh)continue;
        if(Part->ComponentHasTag(TEXT("ParisScannedFacade"))){ScanCount++;ScanVisible+=Part->IsVisible()?1:0;ScanNanite+=Mesh->HasValidNaniteData()?1:0;ScanTriangles+=Mesh->GetNumTriangles(0);}
        if(Part->ComponentHasTag(TEXT("ParisPhotoArchitecture"))){Architecture++;VisibleArchitecture+=Part->IsVisible()?1:0;Triangles+=Mesh->GetNumTriangles(0);}
        if(Part->ComponentHasTag(TEXT("ParisPhotoTree")))if(auto HISM=Cast<UHierarchicalInstancedStaticMeshComponent>(Part)){TreeCandidates+=HISM->GetInstanceCount();if(Mesh->GetName()==TEXT("SM_ParisBroadleaf")){Trees+=HISM->GetInstanceCount();TreeFallbackTriangles+=int64(HISM->GetInstanceCount())*Mesh->GetNumTriangles(0);if(Mesh->HasValidNaniteData())NaniteTrees+=HISM->GetInstanceCount();}}
        if(Part->ComponentHasTag(TEXT("ParisPhotoStreetLamp")))if(auto ISM=Cast<UInstancedStaticMeshComponent>(Part)){LampParts++;LampTriangles+=int64(ISM->GetInstanceCount())*Mesh->GetNumTriangles(0);if(Part->ComponentHasTag(TEXT("ParisPhotoLampMetal"))){Lamps+=ISM->GetInstanceCount();if(ISM->IsVisible())VisibleLamps+=ISM->GetInstanceCount();}}
        if(Part->ComponentHasTag(TEXT("ParisGroundDisplay"))){Ground++;GroundVisible+=Part->IsVisible()?1:0;GroundTriangles+=Mesh->GetNumTriangles(0);}
    }
    Report->SetNumberField(TEXT("authored_west_facade_components"),Architecture);Report->SetNumberField(TEXT("authored_west_facade_visible"),VisibleArchitecture);Report->SetNumberField(TEXT("authored_west_facade_triangles"),Triangles);
    Report->SetNumberField(TEXT("scanned_facade_components"),ScanCount);Report->SetNumberField(TEXT("scanned_facade_visible"),ScanVisible);Report->SetNumberField(TEXT("scanned_facade_nanite"),ScanNanite);Report->SetNumberField(TEXT("scanned_facade_triangles"),ScanTriangles);
    Report->SetStringField(TEXT("scanned_facade_provenance"),TEXT("Historic CC BY photo-derived surface; incomplete 2.5D reconstruction, provisional registration, estimated roughness, captured lighting remains"));
    Report->SetStringField(TEXT("authored_west_facade_provenance"),TEXT("Inferred original architectural study; not a surveyed full cathedral model"));
    Report->SetNumberField(TEXT("photo_tree_instances"),Trees);Report->SetNumberField(TEXT("photo_tree_nanite_instances"),NaniteTrees);Report->SetNumberField(TEXT("tree_fallback_triangles_before_culling"),double(TreeFallbackTriangles));
    Report->SetNumberField(TEXT("photo_tree_candidate_instances"),TreeCandidates);
    Report->SetNumberField(TEXT("photo_lantern_instances"),Lamps);Report->SetNumberField(TEXT("photo_lantern_visible"),VisibleLamps);Report->SetNumberField(TEXT("photo_lantern_batches"),LampParts);
    Report->SetNumberField(TEXT("photo_lantern_fallback_triangles_before_culling"),double(LampTriangles));
    Report->SetStringField(TEXT("photo_lantern_provenance"),TEXT("Original inferred Paris-style fixture; original mapped transform and collider retained; actual design unverified"));
    Report->SetNumberField(TEXT("ground_cutout_components"),Ground);Report->SetNumberField(TEXT("ground_cutout_visible"),GroundVisible);Report->SetNumberField(TEXT("ground_cutout_triangles"),GroundTriangles);
    Report->SetStringField(TEXT("instance_triangle_stat_basis"),TEXT("instance_triangles_before_culling retains the original prototype budget; photo tree fallback triangles are reported separately, not actual Nanite rasterized triangles"));
    Report->SetStringField(TEXT("tree_appearance_source"),TEXT("Poly Haven island_tree_01 CC0; appearance proxy at original mapped coordinates"));
}
