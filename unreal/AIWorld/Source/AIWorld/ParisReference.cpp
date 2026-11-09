#include "ParisReference.h"
#include "ParisDigitalTwin.h"
#include "WorldProtocol.h"
#include "Camera/CameraActor.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMeshActor.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Camera/CameraComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/SkyLight.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/PostProcessVolume.h"
#include "Engine/StaticMesh.h"
#include "EngineUtils.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
using namespace AIWorld;

bool IsParisLaneLook(){return FParse::Param(FCommandLine::Get(),TEXT("ParisTwinLane"));}
static bool LaneBaseline(){return FParse::Param(FCommandLine::Get(),TEXT("ParisTwinLaneBaseline"));}
bool IsParisLaneDressed(){return IsParisLaneLook()&&!LaneBaseline();}
bool IsParisSeineLook(){return FParse::Param(FCommandLine::Get(),TEXT("ParisTwinSeine"));}
bool IsParisSeineDressed(){return IsParisSeineLook()&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinSeineBaseline"));}
bool IsParisReferenceLook(){return FParse::Param(FCommandLine::Get(),TEXT("ParisTwinReferenceLook"))||IsParisLaneLook()||IsParisSeineDressed();}
static TSharedPtr<FJsonObject> ReferenceData(){
    static TSharedPtr<FJsonObject> Data;if(!Data){FString Text;const TCHAR* Path=IsParisSeineLook()?TEXT("Data/paris-seine.json"):IsParisLaneLook()?TEXT("Data/paris-lane.json"):TEXT("Data/paris-reference.json");if(FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/Path)))FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Data);
        if(Data&&IsParisSeineLook()){FString View=TEXT("Cathedral");FParse::Value(FCommandLine::Get(),TEXT("ParisTwinSeineCamera="),View);auto Cameras=Object(Data,TEXT("cameras"));if(Cameras&&Cameras->HasTypedField<EJson::Object>(View))Data->SetObjectField(TEXT("camera"),Object(Cameras,*View));}}
    return Data;
}
bool ParisLaneReplacesShop(const FString& ID){
    if(!IsParisLaneDressed())return false;if(auto D=ReferenceData())for(const auto& V:Array(D,TEXT("records"))){auto J=V->AsObject();if(String(J,TEXT("kind"))==TEXT("lane_shop")&&String(J,TEXT("source_id"))==ID)return true;}return false;
}
bool SelectParisLaneHit(AParisTwinScene* Scene,const FHitResult& Hit){
    auto C=Hit.GetComponent();if(!Scene||!C||!C->ComponentHasTag(TEXT("ParisLaneCollision")))return false;
    FString ID;for(const auto& Tag:C->ComponentTags)if(Tag.ToString().StartsWith(TEXT("osm/")))ID=Tag.ToString();Scene->ClearInspection();Scene->Selection=TEXT("街路の小物（推定配置） | ")+ID+TEXT("\n駐輪台数・外観は推定 / 現地の占有状況は未観測");const auto LL=Scene->GeoReference.WGS84FromUE(C->GetComponentLocation());Scene->SelectionCoordinates=FString::Printf(TEXT("WGS84 %.7f, %.7f"),LL.Y,LL.X);return true;
}
static bool RefVector(const TSharedPtr<FJsonObject>& J,const TCHAR* Key,FVector& V){
    if(!J)return false;const auto& A=Array(J,Key);if(A.Num()!=3)return false;double X,Y,Z;
    if(!A[0]->TryGetNumber(X)||!A[1]->TryGetNumber(Y)||!A[2]->TryGetNumber(Z)||!FMath::IsFinite(X)||!FMath::IsFinite(Y)||!FMath::IsFinite(Z))return false;V=FVector(X,Y,Z);return true;
}
FVector ParisReferenceDetailCentre(const FVector& Fallback){
    if(IsParisReferenceLook()||IsParisSeineLook())if(auto D=ReferenceData()){FVector Eye;if(RefVector(Object(D,TEXT("camera")),TEXT("eye_cm"),Eye))return Eye;}return Fallback;
}
void CreateParisReference(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Source){
    if(!Scene||(!IsParisReferenceLook()&&!IsParisSeineLook()&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinReferenceBaseline"))))return;
    auto Data=ReferenceData();if(!Data||String(Data,TEXT("format"))!=TEXT("paris_reference_v1")||String(Data,TEXT("source_scene_sha256"))!=String(Source,TEXT("source_scene_sha256"))){UE_LOG(LogTemp,Error,TEXT("PARIS_REFERENCE_INVALID_SOURCE"));return;}
    FVector Eye,Target;auto Camera=Object(Data,TEXT("camera"));
    if(RefVector(Camera,TEXT("eye_cm"),Eye)&&RefVector(Camera,TEXT("target_cm"),Target))for(TActorIterator<ACameraActor> It(Scene->GetWorld());It;++It)if(It->GetFName()==FName(TEXT("Camera_Paris_Street"))){It->SetActorLocationAndRotation(Eye,(Target-Eye).Rotation());It->GetCameraComponent()->SetFieldOfView(FMath::RadiansToDegrees(2.f*FMath::Atan(36.f/(2.f*Number(Camera,TEXT("focal_length_mm"),35)))));}
    if(!IsParisReferenceLook())return;
    TMap<FString,UStaticMesh*> Meshes;
    for(const auto& V:Array(Data,TEXT("objects"))){auto J=V->AsObject();const FString Path=String(J,TEXT("asset")),ID=String(J,TEXT("id"));
        if(!Path.StartsWith(TEXT("/Game/ParisPhotoreal/Reference/SM_ParisReference_"))||ID.IsEmpty())return;
        auto Mesh=LoadObject<UStaticMesh>(nullptr,*Path);if(!Mesh){UE_LOG(LogTemp,Error,TEXT("PARIS_REFERENCE_MISSING %s"),*Path);return;}Meshes.Add(ID,Mesh);
    }
    for(const auto& V:Array(Data,TEXT("records"))){auto J=V->AsObject();FVector P,S;if(!RefVector(J,TEXT("anchor_cm"),P)||!RefVector(J,TEXT("scale_xyz"),S)||S.GetMin()<=0||S.GetMax()>4||!FMath::IsFinite(Number(J,TEXT("yaw_degrees"))))return;for(const auto& M:Array(J,TEXT("models")))if(!Meshes.Contains(M->AsString()))return;}
    for(const auto& Pair:Meshes){
        auto C=NewObject<UHierarchicalInstancedStaticMeshComponent>(Scene);Scene->AddInstanceComponent(C);C->SetupAttachment(Scene->GetRootComponent());C->SetStaticMesh(Pair.Value);if(Pair.Key==TEXT("seine_bank_closure"))if(auto Quay=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisSeineQuay")))C->SetMaterial(0,Quay);C->ComponentTags.Add(TEXT("ParisReference"));C->ComponentTags.Add(FName(*Pair.Key));
        if(Pair.Key.StartsWith(TEXT("lane_")))C->ComponentTags.Add(TEXT("ParisLane"));
        C->SetCollisionEnabled(ECollisionEnabled::NoCollision);C->SetGenerateOverlapEvents(false);C->SetCanEverAffectNavigation(false);C->SetCastShadow(Pair.Key!=TEXT("seine_bed")&&Pair.Key!=TEXT("lane_paving")&&!Pair.Key.Contains(TEXT("shrub"))&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoShadows")));C->RegisterComponent();TArray<FTransform> Transforms;
        for(const auto& V:Array(Data,TEXT("records"))){auto J=V->AsObject();if(LaneBaseline()&&String(J,TEXT("kind")).StartsWith(TEXT("lane_")))continue;bool Included=false;for(const auto& M:Array(J,TEXT("models")))Included|=M->AsString()==Pair.Key;if(!Included)continue;FVector P,S;RefVector(J,TEXT("anchor_cm"),P);RefVector(J,TEXT("scale_xyz"),S);Transforms.Add(FTransform(FRotator(0,Number(J,TEXT("yaw_degrees")),0),P,S));}C->AddInstances(Transforms,false,false,false);
    }
    if(IsParisSeineDressed())if(auto Tree=LoadObject<UStaticMesh>(nullptr,TEXT("/Game/ParisPhotoreal/ReferenceNature/SM_ParisAvenueTree"))){
        // Inferred plane trees along the lower quays, sharing the district's avenue tree asset.
        TArray<FTransform> Transforms;for(const auto& V:Array(Data,TEXT("quay_trees"))){auto J=V->AsObject();FVector P;const double S=Number(J,TEXT("scale"),1);if(!RefVector(J,TEXT("anchor_cm"),P)||S<=.3||S>2)continue;Transforms.Add(FTransform(FRotator(0,Number(J,TEXT("yaw_degrees")),0),P,FVector(S)));}
        if(Transforms.Num()){auto C=NewObject<UHierarchicalInstancedStaticMeshComponent>(Scene);Scene->AddInstanceComponent(C);C->SetupAttachment(Scene->GetRootComponent());C->SetStaticMesh(Tree);C->ComponentTags.Add(TEXT("ParisReference"));C->ComponentTags.Add(TEXT("seine_quay_trees"));
            C->InstancingRandomSeed=40417;C->SetWorldPositionOffsetDisableDistance(6000);C->SetCollisionEnabled(ECollisionEnabled::NoCollision);C->SetGenerateOverlapEvents(false);C->SetCanEverAffectNavigation(false);C->SetCastShadow(!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoShadows")));C->RegisterComponent();C->AddInstances(Transforms,false,false,false);}}
    if(IsParisLaneLook()&&!LaneBaseline())for(const auto& V:Array(Data,TEXT("records"))){auto J=V->AsObject();FVector P;if(!RefVector(J,TEXT("anchor_cm"),P))continue;const FRotator R(0,Number(J,TEXT("yaw_degrees")),0);
        for(const auto& B:Array(J,TEXT("collision_boxes"))){FVector Centre,Size;if(!RefVector(B->AsObject(),TEXT("centre_cm"),Centre)||!RefVector(B->AsObject(),TEXT("size_cm"),Size)||Size.GetMin()<=0||Size.GetMax()>500)continue;
            auto C=NewObject<UBoxComponent>(Scene);Scene->AddInstanceComponent(C);C->SetupAttachment(Scene->GetRootComponent());C->SetBoxExtent(Size*.5);C->SetRelativeLocationAndRotation(P+R.RotateVector(Centre),R);C->ComponentTags.Add(TEXT("ParisLaneCollision"));C->ComponentTags.Add(FName(*String(J,TEXT("source_id"))));C->SetCollisionObjectType(ECC_WorldStatic);C->SetCollisionResponseToAllChannels(ECR_Block);C->SetGenerateOverlapEvents(false);C->SetCanEverAffectNavigation(false);C->RegisterComponent();}}
    SyncParisReference(Scene);UE_LOG(LogTemp,Display,TEXT("PARIS_REFERENCE_READY models=%d"),Meshes.Num());
}
static void ApplySeineEnvironment(AParisTwinScene* Scene){
    if(!IsParisSeineDressed())return;
    const bool Night=Scene->TimeOfDayPreset==2,Evening=Scene->TimeOfDayPreset==1,Wet=Scene->bRainyWeather;
    for(TActorIterator<ADirectionalLight> It(Scene->GetWorld());It;++It)if(It->ActorHasTag(TEXT("ParisPhotoEnvironment"))){
        // Photographic Paris reference: low afternoon sun raking across limestone.
        It->SetActorRotation(Night?FRotator(-35,-65,0):FRotator(Evening?-14:-27,Evening?25:15,0));
        if(auto L=Cast<UDirectionalLightComponent>(It->GetLightComponent())){L->SetUseTemperature(true);L->SetTemperature(Night?8200:Wet?6500:Evening?4000:5200);L->SetLightColor(FLinearColor::White);L->SetIntensity(Night?.35f:Wet?9000:Evening?21000:44000);L->SetLightSourceAngle(Wet?5.f:Evening?1.1f:1.f);}}
    for(TActorIterator<ASkyLight> It(Scene->GetWorld());It;++It)if(It->ActorHasTag(TEXT("ParisPhotoEnvironment"))){auto L=It->GetLightComponent();L->SetIntensity(L->SourceType==SLS_SpecifiedCubemap?(Night?260:Wet?12000:Evening?7000:11000):(Night?.4f:1.7f));}
    for(TActorIterator<AExponentialHeightFog> It(Scene->GetWorld());It;++It)if(It->ActorHasTag(TEXT("ParisPhotoEnvironment"))){auto F=It->GetComponent();F->SetFogDensity(Wet?.0012f:Night?.00065f:.00055f);F->SetFogMaxOpacity(Wet?.20f:Night?.12f:.22f);F->SetStartDistance(Night||Wet?12000:6000);F->SetFogInscatteringColor(Night?FLinearColor(.07f,.10f,.18f):Evening?FLinearColor(.70f,.58f,.46f):FLinearColor(.66f,.66f,.66f));}
    for(TActorIterator<APostProcessVolume> It(Scene->GetWorld());It;++It)if(It->ActorHasTag(TEXT("ParisPhotoEnvironment"))){auto& P=It->Settings;P.bOverride_AutoExposureBias=true;P.AutoExposureBias=Night?1.25f:Evening?.65f:.55f;P.bOverride_BloomIntensity=true;P.BloomIntensity=Night?.22f:.16f;
        // Mild photographic grade: tamed HDR sky saturation, warm highlights, soft lens vignette.
        const bool Grade=!Night&&!Wet;P.bOverride_ColorSaturation=Grade;P.ColorSaturation=FVector4(.86,.86,.86,1);P.bOverride_ColorContrast=Grade;P.ColorContrast=FVector4(1.06,1.06,1.06,1);
        P.bOverride_ColorGainHighlights=Grade;P.ColorGainHighlights=Evening?FVector4(1.06,.99,.90,1):FVector4(1.04,1.,.93,1);P.bOverride_ColorGainShadows=Grade;P.ColorGainShadows=FVector4(.96,.99,1.03,1);
        P.bOverride_VignetteIntensity=true;P.VignetteIntensity=Grade?.38f:.2f;}
    if(Night&&!Wet)for(TActorIterator<AStaticMeshActor> It(Scene->GetWorld());It;++It)if(It->ActorHasTag(TEXT("ParisPhotographicSky")))if(auto M=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisSeineTwilight")))It->GetStaticMeshComponent()->SetMaterial(0,M);
}
void SyncParisReference(AParisTwinScene* Scene){
    if(!Scene||!IsParisReferenceLook())return;
    const bool Shown=Scene->bStreetDetails&&Scene->bDetailedSurfaces&&Scene->DetailQuality>0&&!Scene->bFootprints&&!Scene->bLevels&&!Scene->bIssues;
    TArray<UHierarchicalInstancedStaticMeshComponent*> Parts;Scene->GetComponents(Parts);
    for(auto C:Parts)if(C->ComponentHasTag(TEXT("ParisReference"))){C->SetVisibility(Shown);const bool Bank=C->ComponentHasTag(TEXT("seine_bed"))||C->ComponentHasTag(TEXT("seine_bank_closure"))||C->ComponentHasTag(TEXT("seine_bank_coping"))||C->ComponentHasTag(TEXT("seine_lower_quay"));C->SetCullDistances(0,Bank?120000:IsParisSeineDressed()?(Scene->DetailQuality==2?85000:60000):(Scene->DetailQuality==2?24000:18000));}
    TArray<UBoxComponent*> Boxes;Scene->GetComponents(Boxes);for(auto C:Boxes)if(C->ComponentHasTag(TEXT("ParisLaneCollision")))C->SetCollisionEnabled(Shown?ECollisionEnabled::QueryAndPhysics:ECollisionEnabled::NoCollision);
    for(TActorIterator<AExponentialHeightFog> It(Scene->GetWorld());It;++It)if(It->ActorHasTag(TEXT("ParisPhotoEnvironment")))It->GetComponent()->SetStartDistance(Scene->TimeOfDayPreset==0&&!Scene->bRainyWeather?8000:3000);
    if(Scene->TimeOfDayPreset==0&&!Scene->bRainyWeather){
        FVector Eye,Target;auto Data=ReferenceData();float Yaw=-35;
        if(Data&&RefVector(Object(Data,TEXT("camera")),TEXT("eye_cm"),Eye)&&RefVector(Object(Data,TEXT("camera")),TEXT("target_cm"),Target))Yaw=(Target-Eye).Rotation().Yaw+40;
        for(TActorIterator<ADirectionalLight> It(Scene->GetWorld());It;++It)if(It->ActorHasTag(TEXT("ParisPhotoEnvironment"))){It->SetActorRotation(FRotator(-34,Yaw,0));auto L=Cast<UDirectionalLightComponent>(It->GetLightComponent());if(L){L->SetTemperature(5900);L->SetLightColor(FLinearColor::White);L->SetLightSourceAngle(.65f);L->SetIntensity(50000);}}
        for(TActorIterator<ASkyLight> It(Scene->GetWorld());It;++It)if(It->ActorHasTag(TEXT("ParisPhotoEnvironment")))It->GetLightComponent()->SetIntensity(It->GetLightComponent()->SourceType==SLS_SpecifiedCubemap?10000.f:1.7f);
        for(TActorIterator<AExponentialHeightFog> It(Scene->GetWorld());It;++It)if(It->ActorHasTag(TEXT("ParisPhotoEnvironment"))){auto F=It->GetComponent();F->SetFogDensity(.00035f);F->SetFogMaxOpacity(.08f);F->SetStartDistance(8000);}
        for(TActorIterator<APostProcessVolume> It(Scene->GetWorld());It;++It)if(It->ActorHasTag(TEXT("ParisPhotoEnvironment"))){auto& P=It->Settings;P.AutoExposureBias=.65f;P.bOverride_BloomIntensity=true;P.BloomIntensity=.12f;}
        if(IsParisLaneLook()&&!LaneBaseline()){
            for(TActorIterator<ADirectionalLight> It(Scene->GetWorld());It;++It)if(It->ActorHasTag(TEXT("ParisPhotoEnvironment"))){It->SetActorRotation(FRotator(-58,Yaw+25,0));if(auto L=Cast<UDirectionalLightComponent>(It->GetLightComponent())){L->SetIntensity(14000);L->SetTemperature(6200);L->SetLightSourceAngle(5);}}
            for(TActorIterator<ASkyLight> It(Scene->GetWorld());It;++It)if(It->ActorHasTag(TEXT("ParisPhotoEnvironment")))It->GetLightComponent()->SetIntensity(It->GetLightComponent()->SourceType==SLS_SpecifiedCubemap?17000.f:2.4f);
            for(TActorIterator<APostProcessVolume> It(Scene->GetWorld());It;++It)if(It->ActorHasTag(TEXT("ParisPhotoEnvironment")))It->Settings.AutoExposureBias=.95f;
            for(TActorIterator<AStaticMeshActor> It(Scene->GetWorld());It;++It)if(It->ActorHasTag(TEXT("ParisPhotographicSky")))if(auto M=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Weather/M_ParisRainSky"))){auto MID=UMaterialInstanceDynamic::Create(M,It->GetStaticMeshComponent());MID->SetScalarParameterValue(TEXT("SkyRadiance"),6000);It->GetStaticMeshComponent()->SetMaterial(0,MID);}
        }
    }
    ApplySeineEnvironment(Scene);
}
void AddParisReferenceStats(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Report){
    Report->SetBoolField(TEXT("seine_look"),IsParisSeineDressed());if(IsParisSeineLook())if(auto D=ReferenceData()){Report->SetObjectField(TEXT("seine_camera"),Object(D,TEXT("camera")));Report->SetObjectField(TEXT("seine"),Object(D,TEXT("seine")));}
    Report->SetBoolField(TEXT("reference_look"),IsParisReferenceLook());if(!IsParisReferenceLook())return;
    int32 Models=0,Instances=0,Visible=0;TArray<UHierarchicalInstancedStaticMeshComponent*> Parts;Scene->GetComponents(Parts);
    for(auto C:Parts)if(C->ComponentHasTag(TEXT("ParisReference"))){Models++;Instances+=C->GetInstanceCount();if(C->IsVisible())Visible++;}
    Report->SetNumberField(TEXT("reference_models"),Models);Report->SetNumberField(TEXT("reference_instances"),Instances);Report->SetNumberField(TEXT("reference_visible_models"),Visible);
    if(auto D=ReferenceData()){Report->SetObjectField(TEXT("reference_counts"),Object(D,TEXT("counts")));Report->SetStringField(TEXT("reference_recipe"),String(D,TEXT("recipe")));}
    Report->SetBoolField(TEXT("lane_look"),IsParisLaneLook());Report->SetBoolField(TEXT("lane_baseline"),LaneBaseline());if(IsParisLaneLook())if(auto D=ReferenceData())Report->SetObjectField(TEXT("lane"),Object(D,TEXT("lane")));
}
