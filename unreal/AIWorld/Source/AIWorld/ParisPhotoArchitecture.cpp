#include "ParisPhotoArchitecture.h"
#include "ParisPhotoFrontages.h"
#include "ParisDigitalTwin.h"
#include "WorldProtocol.h"
#include "Components/StaticMeshComponent.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "StaticMeshResources.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
using namespace AIWorld;

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
    for(const auto& Value:Array(Data,TEXT("objects"))){auto J=Value->AsObject();const FString Path=String(J,TEXT("asset"));if(!Path.StartsWith(TEXT("/Game/ParisPhotoreal/Architecture/SM_NotreDameWest_")))continue;
        auto Mesh=LoadObject<UStaticMesh>(nullptr,*Path);if(!Mesh){UE_LOG(LogTemp,Warning,TEXT("Missing authored facade asset %s"),*Path);continue;}
        auto Part=NewObject<UStaticMeshComponent>(Scene);Scene->AddInstanceComponent(Part);Part->SetupAttachment(Scene->GetRootComponent());Part->SetStaticMesh(Mesh);
        Part->ComponentTags.Add(TEXT("ParisPhotoArchitecture"));Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);Part->SetCanEverAffectNavigation(false);Part->SetCullDistance(45000);Part->RegisterComponent();
    }
    SyncParisPhotoArchitecture(Scene);
}

void SyncParisPhotoArchitecture(AParisTwinScene* Scene){
    TArray<UStaticMeshComponent*> Parts;Scene->GetComponents(Parts);
    for(auto Part:Parts)if(Part->ComponentHasTag(TEXT("ParisPhotoArchitecture")))Part->SetVisibility(Scene->DetailQuality>0&&!Scene->bFootprints&&!Scene->bLevels&&!Scene->bIssues);
}

void AddParisPhotoDetailStats(const AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Report){
    AddParisFrontageStats(Scene,Report);
    int32 Architecture=0,Trees=0,TreeCandidates=0,VisibleArchitecture=0,NaniteTrees=0,Lamps=0,LampParts=0,VisibleLamps=0,Ground=0,GroundVisible=0,GroundTriangles=0;int64 Triangles=0,TreeFallbackTriangles=0,LampTriangles=0;
    TArray<UStaticMeshComponent*> Parts;Scene->GetComponents(Parts);
    for(auto Part:Parts){
        auto Mesh=Part->GetStaticMesh();if(!Mesh)continue;
        if(Part->ComponentHasTag(TEXT("ParisPhotoArchitecture"))){Architecture++;VisibleArchitecture+=Part->IsVisible()?1:0;Triangles+=Mesh->GetNumTriangles(0);}
        if(Part->ComponentHasTag(TEXT("ParisPhotoTree")))if(auto HISM=Cast<UHierarchicalInstancedStaticMeshComponent>(Part)){TreeCandidates+=HISM->GetInstanceCount();if(Mesh->GetName()==TEXT("SM_ParisBroadleaf")){Trees+=HISM->GetInstanceCount();TreeFallbackTriangles+=int64(HISM->GetInstanceCount())*Mesh->GetNumTriangles(0);if(Mesh->HasValidNaniteData())NaniteTrees+=HISM->GetInstanceCount();}}
        if(Part->ComponentHasTag(TEXT("ParisPhotoStreetLamp")))if(auto ISM=Cast<UInstancedStaticMeshComponent>(Part)){LampParts++;LampTriangles+=int64(ISM->GetInstanceCount())*Mesh->GetNumTriangles(0);if(Part->ComponentHasTag(TEXT("ParisPhotoLampMetal"))){Lamps+=ISM->GetInstanceCount();if(ISM->IsVisible())VisibleLamps+=ISM->GetInstanceCount();}}
        if(Part->ComponentHasTag(TEXT("ParisGroundDisplay"))){Ground++;GroundVisible+=Part->IsVisible()?1:0;GroundTriangles+=Mesh->GetNumTriangles(0);}
    }
    Report->SetNumberField(TEXT("authored_west_facade_components"),Architecture);Report->SetNumberField(TEXT("authored_west_facade_visible"),VisibleArchitecture);Report->SetNumberField(TEXT("authored_west_facade_triangles"),Triangles);
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
