#include "ParisRoadDetail.h"
#include "ParisDigitalTwin.h"
#include "WorldProtocol.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
using namespace AIWorld;

static bool RoadFinishEnabled(){
    return FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal"))&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinLegacyRoads"))&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinProceduralSurfaces"));
}

void CreateParisRoadDetail(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Source){
    if(!RoadFinishEnabled())return;
    FString Text;TSharedPtr<FJsonObject> Data;
    if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("Data/paris-road-detail.json")))||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Data)||!Data)return;
    if(String(Data,TEXT("recipe"))!=TEXT("paris_road_finish_v1")||String(Data,TEXT("source_scene_sha256"))!=String(Source,TEXT("source_scene_sha256")))return;
    for(const auto& Value:Array(Data,TEXT("objects"))){auto Item=Value->AsObject();const FString Path=String(Item,TEXT("asset"));
        if(!Path.StartsWith(TEXT("/Game/ParisPhotoreal/Roads/SM_ParisRoad_")))continue;
        auto Mesh=LoadObject<UStaticMesh>(nullptr,*Path);if(!Mesh){UE_LOG(LogTemp,Warning,TEXT("Missing road finish asset %s"),*Path);continue;}
        auto Part=NewObject<UStaticMeshComponent>(Scene);Scene->AddInstanceComponent(Part);Part->SetupAttachment(Scene->GetRootComponent());Part->SetStaticMesh(Mesh);
        // These visual details retain the source surface as the only collider
        // and selection target, including walking and crowd navigation.
        Part->ComponentTags.Add(TEXT("ParisRoadDetail"));Part->ComponentTags.Add(FName(*String(Item,TEXT("id"))));
        Part->SetCollisionProfileName(TEXT("NoCollision"));Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);Part->SetGenerateOverlapEvents(false);Part->SetCanEverAffectNavigation(false);
        Part->SetCastShadow(!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoShadows")));Part->RegisterComponent();
    }
    SyncParisRoadDetail(Scene);
}

void SyncParisRoadDetail(AParisTwinScene* Scene){
    const bool Visible=RoadFinishEnabled()&&Scene->bDetailedSurfaces&&Scene->DetailQuality>0&&Scene->bStreetDetails&&!Scene->bFootprints&&!Scene->bLevels&&!Scene->bIssues;
    TArray<UStaticMeshComponent*> Parts;Scene->GetComponents(Parts);
    for(auto Part:Parts)if(Part->ComponentHasTag(TEXT("ParisRoadDetail"))){Part->SetVisibility(Visible);Part->SetCullDistance(Scene->DetailQuality==2?22000:15000);}
}

void AddParisRoadDetailStats(const AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Report){
    int32 Count=0,Visible=0;int64 Triangles=0;
    TArray<UStaticMeshComponent*> Parts;Scene->GetComponents(Parts);
    for(auto Part:Parts)if(Part->ComponentHasTag(TEXT("ParisRoadDetail"))){Count++;Visible+=Part->IsVisible()?1:0;if(auto Mesh=Part->GetStaticMesh())Triangles+=Mesh->GetNumTriangles(0);}
    Report->SetNumberField(TEXT("road_detail_components"),Count);Report->SetNumberField(TEXT("road_detail_visible"),Visible);Report->SetNumberField(TEXT("road_detail_triangles_before_culling"),double(Triangles));
    Report->SetBoolField(TEXT("road_view"),FParse::Param(FCommandLine::Get(),TEXT("ParisTwinRoadView")));
    Report->SetStringField(TEXT("road_finish_recipe"),RoadFinishEnabled()&&Scene->bDetailedSurfaces&&Scene->DetailQuality>0?TEXT("paris_road_finish_v1"):TEXT("legacy"));
}
