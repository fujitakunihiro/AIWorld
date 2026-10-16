#include "ParisGroundDisplay.h"
#include "ParisDigitalTwin.h"
#include "WorldProtocol.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
using namespace AIWorld;

void CreateParisGroundDisplay(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Source){
    if(!FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal"))||FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoGroundCutout")))return;
    FString Text;TSharedPtr<FJsonObject> Data;
    if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("Data/paris-photo-ground.json")))||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Data)||!Data)return;
    const FString Path=String(Data,TEXT("asset"));
    if(String(Data,TEXT("format"))!=TEXT("paris_covered_terrain_display_v1")||String(Data,TEXT("source_scene_sha256"))!=String(Source,TEXT("source_scene_sha256"))||!Path.StartsWith(TEXT("/Game/ParisPhotoreal/Ground/SM_ParisTerrainCut_")))return;
    auto Mesh=LoadObject<UStaticMesh>(nullptr,*Path);if(!Mesh)return;
    auto Part=NewObject<UStaticMeshComponent>(Scene);Scene->AddInstanceComponent(Part);Part->SetupAttachment(Scene->GetRootComponent());Part->SetStaticMesh(Mesh);
    Part->ComponentTags.Add(TEXT("ParisGroundDisplay"));Part->SetCollisionProfileName(TEXT("NoCollision"));Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Part->SetGenerateOverlapEvents(false);Part->SetCanEverAffectNavigation(false);Part->SetCastShadow(false);Part->RegisterComponent();
    SyncParisGroundDisplay(Scene);
}

void SyncParisGroundDisplay(AParisTwinScene* Scene){
    TArray<UStaticMeshComponent*> Visuals;Scene->GetComponents(Visuals);
    bool Active=false;const bool Detailed=Scene->DetailQuality>0&&!Scene->bLevels&&!Scene->bIssues&&!Scene->bFootprints;
    for(auto Part:Visuals)if(Part->ComponentHasTag(TEXT("ParisGroundDisplay"))){Active=Detailed;Part->SetVisibility(Detailed);}
    TArray<UPrimitiveComponent*> Sources;Scene->GetComponents(Sources);
    for(auto Part:Sources)if(Part->ComponentHasTag(TEXT("ParisSourceTerrain"))){Part->SetRenderInMainPass(!Active);Part->SetRenderInDepthPass(!Active);}
}
