#include "ParisPhotoFrontages.h"
#include "ParisDigitalTwin.h"
#include "WorldProtocol.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Camera/CameraActor.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#if WITH_EDITOR
#include "AssetCompilingManager.h"
#endif
using namespace AIWorld;

static TSharedPtr<FJsonObject> ParisSupplement(const TCHAR* File,const TCHAR* Format,const TSharedPtr<FJsonObject>& Source){
    FString Text;TSharedPtr<FJsonObject> Data;
    if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("Data")/File))||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Data)||!Data)return nullptr;
    const FString Hash=String(Data,TEXT("source_scene_sha256"));
    if(String(Data,TEXT("format"))!=Format||Hash.Len()!=64||Hash!=String(Source,TEXT("source_scene_sha256")))return nullptr;
    return Data;
}

void CreateParisPhotoFrontages(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Source){
    if(!FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal")))return;
    const auto Data=ParisSupplement(TEXT("paris-photo-frontages.json"),TEXT("paris_inferred_frontages_v2"),Source);if(!Data)return;
    const auto& Origin=Array(Data,TEXT("origin_wgs84"));
    if(Origin.Num()!=2||FMath::Abs(Number(Data,TEXT("origin_elevation_ngf_m"))-Scene->GeoReference.OriginElevationNGF)>.001)return;
    if(Scene->GeoReference.ToUE(FVector2D(Origin[0]->AsNumber(),Origin[1]->AsNumber()),Scene->GeoReference.OriginElevationNGF).Size()>.1)return;
    // Inspect the same real camera position with or without the new display.
    if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinWindowDetail"))){
        const auto& Point=Array(Data,TEXT("inspection_target_cm"));if(Point.Num()==3){
            const FVector Target(Point[0]->AsNumber(),Point[1]->AsNumber(),Point[2]->AsNumber());
            for(TActorIterator<ACameraActor> CameraIt(Scene->GetWorld());CameraIt;++CameraIt)if(CameraIt->GetFName()==FName(TEXT("Camera_Paris_Street")))CameraIt->SetActorRotation((Target-CameraIt->GetActorLocation()).Rotation());
        }
    }
    if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinEntryDetail"))){
        const auto& Eye=Array(Data,TEXT("inspection_entry_camera_cm"));const auto& Aim=Array(Data,TEXT("inspection_entry_target_cm"));
        if(Eye.Num()==3&&Aim.Num()==3){
            FVector Position(Eye[0]->AsNumber(),Eye[1]->AsNumber(),Eye[2]->AsNumber());const FVector Target(Aim[0]->AsNumber(),Aim[1]->AsNumber(),Aim[2]->AsNumber());
            FHitResult Ground;FCollisionQueryParams Query;Query.bTraceComplex=true;
            if(Scene->GetWorld()->LineTraceSingleByChannel(Ground,Position+FVector(0,0,20000),Position-FVector(0,0,20000),ECC_Pawn,Query)&&Ground.ImpactNormal.Z>.4)Position.Z=Ground.ImpactPoint.Z+170;
            for(TActorIterator<ACameraActor> It(Scene->GetWorld());It;++It)if(It->GetFName()==FName(TEXT("Camera_Paris_Street")))It->SetActorLocationAndRotation(Position,(Target-Position).Rotation());
        }
    }
    if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoFrontages")))return;
    // Fail as a complete layer: missing joinery must not expose just floating
    // glazing. Do not invoke LoadObject on a missing or unrelated package.
    TArray<UStaticMesh*> Models;
    if(Array(Data,TEXT("objects")).Num()!=4)return;
    TSet<FString> Kinds;
    for(const auto& Value:Array(Data,TEXT("objects"))){
        const FString Kind=String(Value->AsObject(),TEXT("id"));
        if((Kind!=TEXT("stone")&&Kind!=TEXT("joinery")&&Kind!=TEXT("glass")&&Kind!=TEXT("iron"))||Kinds.Contains(Kind))return;Kinds.Add(Kind);
        const FString Path=String(Value->AsObject(),TEXT("asset"));
        if(!Path.StartsWith(TEXT("/Game/ParisPhotoreal/Frontages/SM_ParisFrontage_")))return;
        auto Mesh=LoadObject<UStaticMesh>(nullptr,*Path);if(!Mesh)return;Models.Add(Mesh);
    }
    for(int32 Index=0;Index<Models.Num();Index++){
        const FString Kind=String(Array(Data,TEXT("objects"))[Index]->AsObject(),TEXT("id"));
        auto Part=NewObject<UStaticMeshComponent>(Scene);Scene->AddInstanceComponent(Part);Part->SetupAttachment(Scene->GetRootComponent());
        Part->SetCollisionProfileName(TEXT("NoCollision"));Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);Part->SetGenerateOverlapEvents(false);Part->SetCanEverAffectNavigation(false);
        Part->SetStaticMesh(Models[Index]);Part->ComponentTags.Add(TEXT("ParisPhotoFrontage"));Part->ComponentTags.Add(FName(*(TEXT("ParisFrontage_")+Kind)));
        Part->ComponentTags.Add(FName(*FString::Printf(TEXT("ParisWindowCount_%d"),int32(Number(Data,TEXT("window_count"))))));
        Part->ComponentTags.Add(FName(*FString::Printf(TEXT("ParisEntranceCount_%d"),int32(Number(Data,TEXT("entrance_count"))))));
        Part->ComponentTags.Add(FName(*FString::Printf(TEXT("ParisCorniceCount_%d"),int32(Number(Data,TEXT("cornice_count"))))));
        Part->SetCastShadow(Kind!=TEXT("glass")&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoShadows")));Part->SetCullDistance(22000);Part->RegisterComponent();
    }
    SyncParisPhotoFrontages(Scene);
}

void SyncParisPhotoFrontages(AParisTwinScene* Scene){
    const bool Detailed=Scene->bDetailedSurfaces&&Scene->DetailQuality>0&&!Scene->bLevels&&!Scene->bIssues&&!Scene->bFootprints;
    TArray<UStaticMeshComponent*> Parts;Scene->GetComponents(Parts);
    for(auto Part:Parts)if(Part->ComponentHasTag(TEXT("ParisPhotoFrontage")))Part->SetVisibility(Detailed);
}

void AddParisFrontageStats(const AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Report){
#if WITH_EDITOR
    Report->SetNumberField(TEXT("benchmark_assets_pending"),FAssetCompilingManager::Get().GetNumRemainingAssets());
#endif
    Report->SetBoolField(TEXT("benchmark_wait_for_assets"),FParse::Param(FCommandLine::Get(),TEXT("ParisTwinWaitForAssets")));
    int32 Components=0,Visible=0,Triangles=0,Windows=0,Entrances=0,Cornices=0;TArray<UStaticMeshComponent*> Parts;Scene->GetComponents(Parts);
    for(auto Part:Parts)if(Part->ComponentHasTag(TEXT("ParisPhotoFrontage"))){
        Components++;Visible+=Part->IsVisible()?1:0;if(auto Mesh=Part->GetStaticMesh())Triangles+=Mesh->GetNumTriangles(0);
        for(const auto& Tag:Part->ComponentTags){
            const FString Name=Tag.ToString();
            for(const auto& Prefix:{FString(TEXT("ParisWindowCount_")),FString(TEXT("ParisEntranceCount_")),FString(TEXT("ParisCorniceCount_"))})if(Name.StartsWith(Prefix)){
                const int32 Count=FCString::Atoi(*Name.RightChop(Prefix.Len()));
                if(Prefix==TEXT("ParisWindowCount_"))Windows=Count;else if(Prefix==TEXT("ParisEntranceCount_"))Entrances=Count;else Cornices=Count;
            }
        }
    }
    Report->SetNumberField(TEXT("frontage_components"),Components);Report->SetNumberField(TEXT("frontage_visible"),Visible);Report->SetNumberField(TEXT("frontage_triangles"),Triangles);Report->SetNumberField(TEXT("frontage_windows"),Windows);
    Report->SetNumberField(TEXT("frontage_entrances"),Entrances);Report->SetNumberField(TEXT("frontage_cornices"),Cornices);
    Report->SetStringField(TEXT("frontage_provenance"),TEXT("Inferred window profiles, panelled doors, iron pulls and stepped cornices at source facade quads; not surveyed facades or real interiors"));
    Report->SetBoolField(TEXT("window_detail_view"),FParse::Param(FCommandLine::Get(),TEXT("ParisTwinWindowDetail")));
    Report->SetBoolField(TEXT("entry_detail_view"),FParse::Param(FCommandLine::Get(),TEXT("ParisTwinEntryDetail")));
}
