#include "ParisBridgeDetail.h"
#include "ParisDigitalTwin.h"
#include "ParisRuntimeMesh.h"
#include "ParisCollisionMesh.h"
#include "WorldProtocol.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "EngineUtils.h"
#include "Materials/MaterialInterface.h"
#include "PhysicsEngine/BodySetup.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
using namespace AIWorld;

static bool BridgeEnabled(const AParisTwinScene* Scene){
    return Scene&&Scene->BridgeData.IsValid()&&FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal"))&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinLegacyBridges"))&&!Scene->bLevels&&!Scene->bIssues&&!Scene->bFootprints;
}

bool ParisBridgeSurfaceHeight(const AParisTwinScene* Scene,const FVector& P,double& Height){
    if(!BridgeEnabled(Scene))return false;
    for(const auto& Value:Array(Scene->BridgeData,TEXT("profiles"))){auto B=Value->AsObject();const auto& C=Array(B,TEXT("centre_cm"));const auto& D=Array(B,TEXT("direction"));const auto& Z=Array(B,TEXT("endpoint_z_cm"));
        if(C.Num()!=3||D.Num()!=2||Z.Num()!=2)continue;
        const FVector2D Offset(P.X-C[0]->AsNumber(),P.Y-C[1]->AsNumber()),Direction(D[0]->AsNumber(),D[1]->AsNumber());
        const double X=FVector2D::DotProduct(Offset,Direction),Y=Offset.X*-Direction.Y+Offset.Y*Direction.X,L=Number(B,TEXT("length_cm")),W=Number(B,TEXT("width_cm"));
        if(L<100||W<100||FMath::Abs(X)>L*.5||FMath::Abs(Y)>W*.5)continue;
        const double T=FMath::Clamp((X+L*.5)/L,0.,1.);Height=FMath::Lerp(Z[0]->AsNumber(),Z[1]->AsNumber(),T)+4*Number(B,TEXT("crown_cm"))*T*(1-T);
        const double Road=Number(B,TEXT("road_width_cm"));if(Road>0&&FMath::Abs(Y)>Road*.5)Height+=14;return true;
    }return false;
}

bool ParisBridgeVisualHeight(UWorld* World,const FVector& P,double& Height){
    // Only presentation heights change. Route coordinates, arc lengths and
    // navigation ownership retain their archived source values.
    static TWeakObjectPtr<AParisTwinScene> Cached;
    if(!Cached.IsValid()||Cached->GetWorld()!=World){Cached.Reset();for(TActorIterator<AParisTwinScene> It(World);It;++It){Cached=*It;break;}}
    return Cached.IsValid()&&ParisBridgeSurfaceHeight(Cached.Get(),P,Height)&&FMath::Abs(Height-P.Z)<240;
}

FString ParisBridgeHitSource(const UPrimitiveComponent* Part){
    if(Part&&Part->ComponentHasTag(TEXT("ParisBridgeCollider")))for(const FName Tag:Part->ComponentTags)if(Tag.ToString().StartsWith(TEXT("osm/way/")))return Tag.ToString();
    return TEXT("");
}

void CreateParisBridgeDetail(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Source){
    if(!FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal"))||FParse::Param(FCommandLine::Get(),TEXT("ParisTwinLegacyBridges")))return;
    FString Text;TSharedPtr<FJsonObject> Data;
    if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("Data/paris-bridges.json")))||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Data)||!Data)return;
    if(String(Data,TEXT("recipe"))!=TEXT("paris_bridge_structure_v1")||String(Data,TEXT("source_scene_sha256"))!=String(Source,TEXT("source_scene_sha256")))return;
    TMap<FString,TSharedPtr<FJsonObject>> Profiles;for(const auto& V:Array(Data,TEXT("profiles")))Profiles.Add(String(V->AsObject(),TEXT("id")),V->AsObject());
    TMap<FString,UStaticMesh*> Models;
    for(const auto& V:Array(Data,TEXT("objects"))){const FString Path=String(V->AsObject(),TEXT("asset"));if(!Path.StartsWith(TEXT("/Game/ParisPhotoreal/Bridges/SM_ParisBridge_")))return;auto Mesh=LoadObject<UStaticMesh>(nullptr,*Path);if(!Mesh){UE_LOG(LogTemp,Warning,TEXT("Bridge assets missing; keeping original bridge %s"),*Path);return;}Models.Add(Path,Mesh);}
    TArray<FParisMeshArrays> Collisions;TArray<uint8> Empty;FString Error;
    for(const auto& V:Array(Data,TEXT("collisions"))){FParisMeshArrays Mesh;if(!ReadParisMeshArrays(V->AsObject(),Empty,Mesh,Error))return;Collisions.Add(MoveTemp(Mesh));}
    if(Collisions.Num()!=Profiles.Num()||Models.IsEmpty())return;
    Scene->BridgeData=Data;
    for(const auto& V:Array(Data,TEXT("objects"))){auto Item=V->AsObject();auto Part=NewObject<UStaticMeshComponent>(Scene);Scene->AddInstanceComponent(Part);Part->SetupAttachment(Scene->GetRootComponent());Part->SetStaticMesh(Models[String(Item,TEXT("asset"))]);
        Part->ComponentTags.Append({TEXT("ParisBridgeVisual"),FName(*String(Item,TEXT("bridge_id")))});Part->SetCollisionProfileName(TEXT("NoCollision"));Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);Part->SetCanEverAffectNavigation(false);Part->SetGenerateOverlapEvents(false);
        Part->SetCastShadow(!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoShadows")));Part->RegisterComponent();
    }
    const auto& Input=Array(Data,TEXT("collisions"));
    for(int32 I=0;I<Input.Num();I++){auto Item=Input[I]->AsObject();auto Profile=Profiles.FindRef(String(Item,TEXT("bridge_id")));if(!Profile)continue;
        auto Part=NewObject<UParisCollisionMesh>(Scene);Scene->AddInstanceComponent(Part);Part->SetupAttachment(Scene->GetRootComponent());Part->ComponentTags.Append({TEXT("ParisBridgeCollider"),FName(*String(Profile,TEXT("primary_source_id"))),FName(*String(Profile,TEXT("id")))});
        Part->bUseComplexAsSimpleCollision=true;Part->bUseAsyncCooking=false;Part->SetUsesVisualCache(true);Part->SetCanEverAffectNavigation(false);Part->SetCollisionProfileName(TEXT("BlockAll"));Part->RegisterComponent();const auto& M=Collisions[I];
        Part->CreateMeshSection_LinearColor(0,M.Positions,M.Indices,M.Normals,{},M.Colors,{},true);if(auto Body=Part->GetBodySetup())Body->bDoubleSidedGeometry=true;
    }
    SyncParisBridgeDetail(Scene);UE_LOG(LogTemp,Display,TEXT("PARIS_BRIDGES_READY bridges=%d visual_batches=%d continuous_collision=%d"),Profiles.Num(),Models.Num(),Collisions.Num());
}

void SyncParisBridgeDetail(AParisTwinScene* Scene){
    if(!Scene->BridgeData)return;const bool Active=BridgeEnabled(Scene);TSet<FName> Replaced;
    for(const auto& V:Array(Scene->BridgeData,TEXT("profiles")))for(const auto& ID:Array(V->AsObject(),TEXT("source_mesh_ids")))Replaced.Add(FName(*ID->AsString()));
    TArray<UPrimitiveComponent*> Parts;Scene->GetComponents(Parts);
    for(auto Part:Parts){
        if(Part->ComponentHasTag(TEXT("ParisSourceBridge"))){bool Replace=false;for(const FName ID:Replaced)Replace|=Part->ComponentHasTag(ID);if(Replace){Part->SetRenderInMainPass(!Active);Part->SetRenderInDepthPass(!Active);Part->SetCollisionEnabled(Active?ECollisionEnabled::NoCollision:ECollisionEnabled::QueryAndPhysics);}}
        if(Part->ComponentHasTag(TEXT("ParisBridgeVisual"))){Part->SetVisibility(Active);Part->SetCullDistance(Scene->DetailQuality==2?100000:60000);}
        if(Part->ComponentHasTag(TEXT("ParisBridgeCollider")))Part->SetCollisionEnabled(Active?ECollisionEnabled::QueryAndPhysics:ECollisionEnabled::NoCollision);
    }
}

void AddParisBridgeDetailStats(const AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Report){
    int32 Parts=0,Visible=0,Colliders=0,Nanite=0;int64 Triangles=0;TArray<UStaticMeshComponent*> Visuals;Scene->GetComponents(Visuals);
    for(auto Part:Visuals)if(Part->ComponentHasTag(TEXT("ParisBridgeVisual"))){Parts++;Visible+=Part->IsVisible()?1:0;if(auto Mesh=Part->GetStaticMesh()){Triangles+=Mesh->GetNumTriangles(0);Nanite+=Mesh->HasValidNaniteData()?1:0;}}
    TArray<UPrimitiveComponent*> All;Scene->GetComponents(All);for(auto Part:All)if(Part->ComponentHasTag(TEXT("ParisBridgeCollider"))&&Part->GetCollisionEnabled()!=ECollisionEnabled::NoCollision)Colliders++;
    Report->SetNumberField(TEXT("bridge_visual_batches"),Parts);Report->SetNumberField(TEXT("bridge_visible_batches"),Visible);Report->SetNumberField(TEXT("bridge_nanite_batches"),Nanite);Report->SetNumberField(TEXT("bridge_fallback_triangles_before_culling"),double(Triangles));Report->SetNumberField(TEXT("bridge_continuous_colliders"),Colliders);
    Report->SetNumberField(TEXT("bridge_reconstructions"),Scene->BridgeData?Array(Scene->BridgeData,TEXT("profiles")).Num():0);Report->SetBoolField(TEXT("bridge_view"),FParse::Param(FCommandLine::Get(),TEXT("ParisTwinBridgeView")));
}
