#include "ParisWeathering.h"
#include "ParisDigitalTwin.h"
#include "WorldProtocol.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Camera/CameraActor.h"
#include "EngineUtils.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
using namespace AIWorld;

void CreateParisWeathering(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Source){
    if(!Scene||!Source||!FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal"))||FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoFrontages")))return;
    TArray<UStaticMeshComponent*> Existing;Scene->GetComponents(Existing);
    for(auto C:Existing)if(C->ComponentHasTag(TEXT("ParisWeathering")))return;
    FString Text;TSharedPtr<FJsonObject> Data;
    if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("Data/paris-weathering.json")))||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Data)||!Data)return;
    if(String(Data,TEXT("format"))!=TEXT("paris_local_weathering_v2")||String(Data,TEXT("source_scene_sha256"))!=String(Source,TEXT("source_scene_sha256")))return;
    if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinWeatheringView"))){
        const auto Camera=Object(Data,TEXT("inspection_camera"));const auto& Eye=Array(Camera,TEXT("eye_cm"));const auto& Target=Array(Camera,TEXT("target_cm"));
        if(Eye.Num()==3&&Target.Num()==3){
            const FVector Position(Eye[0]->AsNumber(),Eye[1]->AsNumber(),Eye[2]->AsNumber()),Aim(Target[0]->AsNumber(),Target[1]->AsNumber(),Target[2]->AsNumber());
            if(!Position.ContainsNaN()&&!Aim.ContainsNaN())for(TActorIterator<ACameraActor> It(Scene->GetWorld());It;++It)if(It->GetFName()==FName(TEXT("Camera_Paris_Street")))It->SetActorLocationAndRotation(Position,(Aim-Position).Rotation());
        }
    }
    if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoWeathering")))return;
    const auto& Objects=Array(Data,TEXT("objects"));if(Objects.Num()<3||Objects.Num()>256)return;
    TArray<UStaticMesh*> Meshes;
    for(const auto& V:Objects){const FString Path=String(V->AsObject(),TEXT("asset"));
        if(!Path.StartsWith(TEXT("/Game/ParisPhotoreal/Weathering/SM_ParisWeathering_")))return;
        auto Mesh=LoadObject<UStaticMesh>(nullptr,*Path);if(!Mesh){UE_LOG(LogTemp,Warning,TEXT("Missing weathering asset %s"),*Path);return;}Meshes.Add(Mesh);
    }
    for(int32 I=0;I<Meshes.Num();I++){
        auto Part=NewObject<UStaticMeshComponent>(Scene);Scene->AddInstanceComponent(Part);Part->SetupAttachment(Scene->GetRootComponent());
        Part->SetStaticMesh(Meshes[I]);Part->ComponentTags.Add(TEXT("ParisWeathering"));Part->ComponentTags.Add(FName(*String(Objects[I]->AsObject(),TEXT("id"))));
        Part->SetCollisionProfileName(TEXT("NoCollision"));Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);Part->SetGenerateOverlapEvents(false);Part->SetCanEverAffectNavigation(false);Part->SetCastShadow(false);Part->bAffectDistanceFieldLighting=false;Part->SetCullDistance(30000);Part->RegisterComponent();
    }
    SyncParisWeathering(Scene);
}
void SyncParisWeathering(AParisTwinScene* Scene){
    const bool Visible=Scene->bDetailedSurfaces&&Scene->DetailQuality>0&&!Scene->bLevels&&!Scene->bIssues&&!Scene->bFootprints;
    TArray<UStaticMeshComponent*> Parts;Scene->GetComponents(Parts);for(auto C:Parts)if(C->ComponentHasTag(TEXT("ParisWeathering")))C->SetVisibility(Visible);
}
void AddParisWeatheringStats(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Report){
    int32 Count=0,Visible=0;TArray<UStaticMeshComponent*> Parts;Scene->GetComponents(Parts);
    for(auto C:Parts)if(C->ComponentHasTag(TEXT("ParisWeathering"))){Count++;Visible+=C->IsVisible()?1:0;}
    Report->SetNumberField(TEXT("weathering_components"),Count);Report->SetNumberField(TEXT("weathering_visible"),Visible);
    Report->SetStringField(TEXT("weathering_provenance"),TEXT("Inferred localized staining below source-aligned facade windows, near wall bases and along mapped road edges; not surveyed grime."));
}
