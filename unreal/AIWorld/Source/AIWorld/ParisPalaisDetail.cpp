#include "ParisPalaisDetail.h"
#include "ParisDigitalTwin.h"
#include "ParisStreetMeshes.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/PlayerController.h"
#include "Materials/MaterialInterface.h"
#include "Materials/Material.h"
#include "Misc/Crc.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Serialization/JsonSerializer.h"
#include "WorldProtocol.h"
using namespace AIWorld;
namespace {
bool ReadVector(const TArray<TSharedPtr<FJsonValue>>& A,FVector& V){if(A.Num()!=3)return false;double X,Y,Z;if(!A[0]->TryGetNumber(X)||!A[1]->TryGetNumber(Y)||!A[2]->TryGetNumber(Z)||!FMath::IsFinite(X)||!FMath::IsFinite(Y)||!FMath::IsFinite(Z))return false;V=FVector(X,Y,Z);return true;}
}
AParisPalaisDetail::AParisPalaisDetail(){RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("PalaisDetailRoot"));Camera=CreateDefaultSubobject<UCameraComponent>(TEXT("PalaisCamera"));Camera->SetupAttachment(RootComponent);Camera->FieldOfView=64;Camera->PostProcessBlendWeight=1;Camera->PostProcessSettings.bOverride_AutoExposureBias=true;Camera->PostProcessSettings.AutoExposureBias=1.15f;}
bool AParisPalaisDetail::Initialize(AParisTwinScene* InScene,const TSharedPtr<FJsonObject>& WorldData){
    Scene=InScene;if(!Scene||!WorldData.IsValid()||!Scene->SourceFeatureByID(TEXT("osm/relation/536982")))return false;
    FString Text;TSharedPtr<FJsonObject> J;
    if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("Data/paris-palais-frontages.json")))||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),J)||!J.IsValid()||String(J,TEXT("format"))!=TEXT("paris_palais_frontage_instances_v1")||String(J,TEXT("source_scene_sha256"))!=String(WorldData,TEXT("source_scene_sha256"))||String(J,TEXT("source_id"))!=TEXT("osm/relation/536982"))return false;
    const auto& Models=Array(J,TEXT("models"));const auto& Windows=Array(J,TEXT("windows"));if(Models.Num()!=4||Windows.Num()<20||Windows.Num()>3000||int32(Number(J,TEXT("window_count")))!=Windows.Num())return false;
    FVector Eye,Target;if(!ReadVector(Array(J,TEXT("inspection_eye_cm")),Eye)||!ReadVector(Array(J,TEXT("inspection_target_cm")),Target))return false;
    TArray<FTransform> Transforms;TArray<float> Seeds;Transforms.Reserve(Windows.Num());Seeds.Reserve(Windows.Num());
    for(const auto& V:Windows){auto Item=V->AsObject();if(!Item.IsValid()||String(Item,TEXT("source_id"))!=TEXT("osm/relation/536982"))return false;
        FVector Centre;if(!ReadVector(Array(Item,TEXT("centre_cm")),Centre))return false;const auto& N=Array(Item,TEXT("normal"));if(N.Num()!=2)return false;
        double X,Y;if(!N[0]->TryGetNumber(X)||!N[1]->TryGetNumber(Y)||!FMath::IsFinite(X)||!FMath::IsFinite(Y)||FMath::Abs(X*X+Y*Y-1)>.01)return false;
        const double Radius=FVector2D::Distance(FVector2D(Centre.X,Centre.Y),FVector2D(-15173.6394325,-7772.3607886));if(Radius>5000.1||Number(Item,TEXT("boundary_error_cm"),100)>3.01)return false;
        const FVector Tangent(Y,-X,0);Transforms.Emplace(Tangent.Rotation(),Centre,FVector::OneVector);
        const FString SeedKey=String(Item,TEXT("source_mesh_id"))+TEXT("/")+FString::FromInt(int32(Number(Item,TEXT("source_quad_index"))));Seeds.Add(float(FCrc::StrCrc32(*SeedKey)&0xffff)/65535.f);
    }
    TArray<UStaticMesh*> Meshes;TArray<FString> MeshKinds;TSet<FString> Kinds;
    const TMap<FString,FString> Materials={{TEXT("stone"),TEXT("/Game/Materials/M_Paris_Limestone")},{TEXT("wood"),TEXT("/Game/Materials/M_ParisWood")},{TEXT("glass"),TEXT("/Game/Materials/M_ParisGlass")},{TEXT("iron"),TEXT("/Game/Materials/M_ParisCastIron")}};
    for(const auto& V:Models){auto Model=V->AsObject();const FString ID=String(Model,TEXT("id")),Path=String(Model,TEXT("material"));const FString* Expected=Materials.Find(ID);if(!Expected||Kinds.Contains(ID)||Path!=*Expected)return false;Kinds.Add(ID);
        auto Material=LoadObject<UMaterialInterface>(nullptr,*Path);if(!Material)return false;
        if(ID==TEXT("glass")&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoPalaisPhotoGlass"))){auto Photo=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/ParisPhotoreal/Palais/M_PalaisReflectiveGlass.M_PalaisReflectiveGlass"));if(Photo&&Photo->GetMaterial()&&Photo->GetMaterial()->GetUsageByFlag(MATUSAGE_InstancedStaticMeshes)){Material=Photo;bPhotorealGlass=true;}}
        auto Mesh=BuildParisStreetMesh(this,Model,Material);if(!Mesh)return false;Meshes.Add(Mesh);MeshKinds.Add(ID);
    }
    for(int32 I=0;I<Meshes.Num();I++){
        auto Group=NewObject<UHierarchicalInstancedStaticMeshComponent>(this);AddInstanceComponent(Group);Group->SetupAttachment(RootComponent);Group->SetStaticMesh(Meshes[I]);Group->SetCollisionEnabled(ECollisionEnabled::NoCollision);Group->SetCanEverAffectNavigation(false);
        const bool IsGlass=MeshKinds[I]==TEXT("glass");if(IsGlass&&bPhotorealGlass)Group->SetNumCustomDataFloats(1);
        Group->SetCastShadow(!IsGlass&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoShadows")));Group->SetCullDistances(15000,22000);Group->ComponentTags.Add(TEXT("ParisPalaisDetail"));Group->ComponentTags.Add(FName(*(TEXT("ParisPalais_")+MeshKinds[I])));Group->RegisterComponent();Group->AddInstances(Transforms,false,false,false);
        if(IsGlass&&bPhotorealGlass){for(int32 SeedIndex=0;SeedIndex<Seeds.Num();SeedIndex++)Group->SetCustomDataValue(SeedIndex,0,Seeds[SeedIndex],false);Group->MarkRenderStateDirty();}Groups.Add(Group);
    }
    Camera->SetRelativeLocation(Eye);Camera->SetRelativeRotation((Target-Eye).Rotation());WindowCount=Windows.Num();bEnabled=!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoPalaisDetail"));bReady=true;Sync();return true;
}
void AParisPalaisDetail::Sync(){if(!Scene)return;const bool Show=bReady&&bEnabled&&Scene->DetailQuality>0&&Scene->bDetailedSurfaces&&!Scene->bFootprints&&!Scene->bLevels&&!Scene->bIssues;for(auto Group:Groups)if(Group)Group->SetVisibility(Show);}
void AParisPalaisDetail::ActivateView(APlayerController* PC){if(PC){PC->SetViewTarget(this);if(PC->PlayerCameraManager)PC->PlayerCameraManager->SetGameCameraCutThisFrame();}}
