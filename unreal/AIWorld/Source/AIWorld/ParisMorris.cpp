#include "ParisMorris.h"
#include "ParisDigitalTwin.h"
#include "WorldProtocol.h"
#include "Components/CapsuleComponent.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Camera/CameraActor.h"
#include "EngineUtils.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
using namespace AIWorld;

static bool MorrisVector(const TSharedPtr<FJsonObject>& J,const TCHAR* Key,FVector& Out){
    if(!J)return false;const auto& A=Array(J,Key);if(A.Num()!=3)return false;
    double X,Y,Z;if(!A[0]->TryGetNumber(X)||!A[1]->TryGetNumber(Y)||!A[2]->TryGetNumber(Z)||!FMath::IsFinite(X)||!FMath::IsFinite(Y)||!FMath::IsFinite(Z))return false;
    Out=FVector(X,Y,Z);return true;
}

void CreateParisMorris(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Source){
    if(!Scene||!Source||!FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal"))||FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoPhotoStreet"))||FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoMorris")))return;
    TArray<UHierarchicalInstancedStaticMeshComponent*> Existing;Scene->GetComponents(Existing);
    for(auto C:Existing)if(C->ComponentHasTag(TEXT("ParisMorris")))return;
    FString Text;TSharedPtr<FJsonObject> Data;
    if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("Data/paris-morris.json")))||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Data)||!Data)return;
    if(String(Data,TEXT("format"))!=TEXT("paris_morris_props_v1")||String(Data,TEXT("source_scene_sha256"))!=String(Source,TEXT("source_scene_sha256")))return;
    TMap<FString,UStaticMesh*> Assets;
    for(const auto& V:Array(Data,TEXT("objects"))){auto J=V->AsObject();const FString ID=String(J,TEXT("id")),Path=String(J,TEXT("asset"));
        if(!Path.StartsWith(TEXT("/Game/ParisPhotoreal/Morris/SM_ParisMorris_")))return;
        auto Mesh=LoadObject<UStaticMesh>(nullptr,*Path);if(!Mesh){UE_LOG(LogTemp,Warning,TEXT("Missing Morris asset %s"),*Path);return;}Assets.Add(ID,Mesh);
    }
    for(const FString ID:{TEXT("column_iron"),TEXT("column_paper"),TEXT("sign_iron"),TEXT("sign_paper")})if(!Assets.Contains(ID))return;
    TMap<FString,UHierarchicalInstancedStaticMeshComponent*> Groups;
    for(const auto& Pair:Assets){
        auto Part=NewObject<UHierarchicalInstancedStaticMeshComponent>(Scene);Scene->AddInstanceComponent(Part);Part->SetupAttachment(Scene->GetRootComponent());
        Part->SetStaticMesh(Pair.Value);Part->ComponentTags.Add(TEXT("ParisMorris"));Part->ComponentTags.Add(FName(*Pair.Key));
        Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);Part->SetCanEverAffectNavigation(false);Part->SetCullDistance(35000);Part->RegisterComponent();Groups.Add(Pair.Key,Part);
    }
    for(const auto& V:Array(Data,TEXT("records"))){auto J=V->AsObject();const FString Kind=String(J,TEXT("kind")),ID=String(J,TEXT("source_id"));FVector Anchor;
        if((Kind!=TEXT("column")&&Kind!=TEXT("sign"))||!ID.StartsWith(TEXT("osm/node/"))||!MorrisVector(J,TEXT("anchor_cm"),Anchor))continue;
        const double Radius=Number(J,TEXT("footprint_radius_cm")),Yaw=Number(J,TEXT("yaw_degrees"));
        if(!FMath::IsFinite(Radius)||!FMath::IsFinite(Yaw)||Radius<20||Radius>120)continue;
        const FTransform Transform(FRotator(0,Yaw,0),Anchor);
        Groups[Kind+TEXT("_iron")]->AddInstance(Transform);Groups[Kind+TEXT("_paper")]->AddInstance(Transform);
        auto Collider=NewObject<UCapsuleComponent>(Scene);Scene->AddInstanceComponent(Collider);Collider->SetupAttachment(Scene->GetRootComponent());
        Collider->ComponentTags.Add(TEXT("ParisMorrisCollider"));Collider->ComponentTags.Add(FName(*ID));Collider->ComponentTags.Add(Kind==TEXT("column")?TEXT("ParisMorrisColumn"):TEXT("ParisMorrisSign"));
        const float HalfHeight=Kind==TEXT("column")?226.f:137.f;Collider->InitCapsuleSize((float)Radius,HalfHeight);Collider->SetRelativeLocation(Anchor+FVector(0,0,HalfHeight));
        Collider->SetCollisionObjectType(ECC_WorldStatic);Collider->SetCollisionResponseToAllChannels(ECR_Block);Collider->SetGenerateOverlapEvents(false);Collider->SetCanEverAffectNavigation(false);Collider->RegisterComponent();
    }
    if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinMorrisView"))){
        const auto Camera=Object(Data,TEXT("inspection_camera"));FVector Eye,Target;
        if(MorrisVector(Camera,TEXT("eye_cm"),Eye)&&MorrisVector(Camera,TEXT("target_cm"),Target))
            for(TActorIterator<ACameraActor> It(Scene->GetWorld());It;++It)if(It->GetFName()==FName(TEXT("Camera_Paris_Street")))It->SetActorLocationAndRotation(Eye,(Target-Eye).Rotation());
    }
    SyncParisMorris(Scene);
}

void SyncParisMorris(AParisTwinScene* Scene){
    if(!Scene)return;
    const bool Visible=Scene->bStreetDetails&&!Scene->bLevels&&!Scene->bIssues&&!Scene->bFootprints;
    TArray<UHierarchicalInstancedStaticMeshComponent*> Parts;Scene->GetComponents(Parts);
    for(auto C:Parts)if(C->ComponentHasTag(TEXT("ParisMorris")))C->SetVisibility(Visible);
    TArray<UCapsuleComponent*> Colliders;Scene->GetComponents(Colliders);
    for(auto C:Colliders)if(C->ComponentHasTag(TEXT("ParisMorrisCollider")))C->SetCollisionEnabled(Visible?ECollisionEnabled::QueryAndPhysics:ECollisionEnabled::NoCollision);
}

bool SelectParisMorrisHit(AParisTwinScene* Scene,const FHitResult& Hit){
    auto C=Hit.GetComponent();if(!Scene||!C||!C->ComponentHasTag(TEXT("ParisMorrisCollider")))return false;
    FString ID;for(const FName& Tag:C->ComponentTags)if(Tag.ToString().StartsWith(TEXT("osm/node/")))ID=Tag.ToString();
    const FVector2D LL=Scene->GeoReference.WGS84FromUE(C->GetComponentLocation());Scene->ClearInspection();
    Scene->Selection=(C->ComponentHasTag(TEXT("ParisMorrisColumn"))?TEXT("モリス広告塔 | "):TEXT("街頭掲示板 | "))+ID+TEXT("\n位置: OpenStreetMap / 外観・ポスター: 推定");
    Scene->SelectionCoordinates=FString::Printf(TEXT("WGS84 %.7f, %.7f"),LL.Y,LL.X);return true;
}

void AddParisMorrisStats(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Report){
    int32 Columns=0,Signs=0,Visible=0;TArray<UCapsuleComponent*> Colliders;Scene->GetComponents(Colliders);
    for(auto C:Colliders)if(C->ComponentHasTag(TEXT("ParisMorrisCollider"))){Columns+=C->ComponentHasTag(TEXT("ParisMorrisColumn"))?1:0;Signs+=C->ComponentHasTag(TEXT("ParisMorrisSign"))?1:0;Visible+=C->GetCollisionEnabled()!=ECollisionEnabled::NoCollision?1:0;}
    Report->SetNumberField(TEXT("morris_mapped_columns"),Columns);Report->SetNumberField(TEXT("morris_mapped_signs"),Signs);Report->SetNumberField(TEXT("morris_active_collision_proxies"),Visible);
    Report->SetStringField(TEXT("morris_appearance_provenance"),TEXT("Inferred original geometry and fictional posters; mapped OSM positions."));
}
