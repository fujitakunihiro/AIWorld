#include "ParisLuxury.h"
#include "ParisReference.h"
#include "ParisDigitalTwin.h"
#include "WorldProtocol.h"
#include "ParisPhotoEnvironment.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialParameterCollection.h"
#include "Materials/MaterialParameterCollectionInstance.h"
#include "Engine/PostProcessVolume.h"
#include "ParisNightLighting.h"
#include "Components/CapsuleComponent.h"
#include "Components/BoxComponent.h"
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

static TMap<TWeakObjectPtr<AParisTwinScene>,int32> DistrictViewIndices;
static TMap<TWeakObjectPtr<AParisTwinScene>,bool> FestivalStates;
bool IsParisFestivalEnabled(AParisTwinScene* Scene){
    if(!Scene)return false;if(auto Enabled=FestivalStates.Find(Scene))return *Enabled;
    return FParse::Param(FCommandLine::Get(),TEXT("ParisTwinFestival"));
}
void SyncParisFestivalAppearance(AParisTwinScene* Scene){
    if(!Scene)return;const bool Shown=IsParisFestivalEnabled(Scene)&&Scene->bStreetDetails&&!Scene->bLevels&&!Scene->bIssues&&!Scene->bFootprints;
    if(auto Collection=LoadObject<UMaterialParameterCollection>(nullptr,TEXT("/Game/Night/MPC_ParisNight")))if(auto Instance=Scene->GetWorld()->GetParameterCollectionInstance(Collection))Instance->SetScalarParameterValue(TEXT("FestivalAmount"),Shown?1.f:0.f);
    for(TActorIterator<APostProcessVolume> It(Scene->GetWorld());It;++It)if(It->ActorHasTag(TEXT("ParisPhotoEnvironment"))){auto& P=It->Settings;P.bOverride_BloomIntensity=true;P.BloomIntensity=Shown?(Scene->TimeOfDayPreset==2?.9f:.35f):(Scene->TimeOfDayPreset==2?.35f:.2f);}
}
void ToggleParisFestival(AParisTwinScene* Scene){
    if(!Scene)return;for(auto It=FestivalStates.CreateIterator();It;++It)if(!It.Key().IsValid())It.RemoveCurrent();
    FestivalStates.Add(Scene,!IsParisFestivalEnabled(Scene));SyncParisLuxury(Scene);SyncParisNightLighting(Scene);
}
static bool LuxuryVector(const TSharedPtr<FJsonObject>& J,const TCHAR* Key,FVector& Out);
static bool LoadLuxuryData(TSharedPtr<FJsonObject>& Data){
    FString Text;return FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("Data/paris-luxury.json")))&&FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Data)&&Data.IsValid();
}
static bool SetDistrictCamera(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Camera){
    if(!Scene)return false;FVector Eye,Target;if(!LuxuryVector(Camera,TEXT("eye_cm"),Eye)||!LuxuryVector(Camera,TEXT("target_cm"),Target))return false;
    for(TActorIterator<ACameraActor> It(Scene->GetWorld());It;++It)if(It->GetFName()==FName(TEXT("Camera_Paris_Street"))){It->SetActorLocationAndRotation(Eye,(Target-Eye).Rotation());return true;}return false;
}

static bool LuxuryVector(const TSharedPtr<FJsonObject>& J,const TCHAR* Key,FVector& Out){
    if(!J)return false;const auto& A=Array(J,Key);if(A.Num()!=3)return false;
    double X,Y,Z;if(!A[0]->TryGetNumber(X)||!A[1]->TryGetNumber(Y)||!A[2]->TryGetNumber(Z)||!FMath::IsFinite(X)||!FMath::IsFinite(Y)||!FMath::IsFinite(Z))return false;
    Out=FVector(X,Y,Z);return true;
}

void CreateParisLuxury(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Source){
    if(!Scene||!Source||!FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal")))return;
    TArray<UHierarchicalInstancedStaticMeshComponent*> Existing;Scene->GetComponents(Existing);for(auto C:Existing)if(C->ComponentHasTag(TEXT("ParisLuxury")))return;
    TSharedPtr<FJsonObject> Data;if(!LoadLuxuryData(Data))return;
    if(String(Data,TEXT("format"))!=TEXT("paris_luxury_street_v1")||String(Data,TEXT("source_scene_sha256"))!=String(Source,TEXT("source_scene_sha256")))return;
    if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinLuxuryView")))SetDistrictCamera(Scene,Object(Data,FParse::Param(FCommandLine::Get(),TEXT("ParisTwinLuxuryClose"))?TEXT("inspection_close_camera"):TEXT("inspection_camera")));
    if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinDistrictView"))){
        const auto& Views=Array(Data,TEXT("district_views"));int32 Index=0;FParse::Value(FCommandLine::Get(),TEXT("ParisTwinDistrictSpot="),Index);
        if(Views.IsValidIndex(Index)&&SetDistrictCamera(Scene,Views[Index]->AsObject()))DistrictViewIndices.Add(Scene,Index);
    }
    if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoLuxury")))return;
    if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinExtraObjectsView")))SetDistrictCamera(Scene,Object(Data,TEXT("extra_objects_camera")));
    TMap<FString,UStaticMesh*> Meshes;
    for(const auto& V:Array(Data,TEXT("objects"))){auto J=V->AsObject();const FString ID=String(J,TEXT("id")),Path=String(J,TEXT("asset"));
        if(!Path.StartsWith(TEXT("/Game/ParisPhotoreal/Luxury/SM_ParisLuxury_"))||ID.IsEmpty())return;
        auto Mesh=LoadObject<UStaticMesh>(nullptr,*Path);if(!Mesh){UE_LOG(LogTemp,Warning,TEXT("Missing luxury asset %s"),*Path);return;}Meshes.Add(ID,Mesh);
    }
    // Validate the entire manifest before adding any partial decoration.
    for(const auto& V:Array(Data,TEXT("records"))){auto J=V->AsObject();FVector P;
        if(!LuxuryVector(J,TEXT("anchor_cm"),P)||!FMath::IsFinite(Number(J,TEXT("yaw_degrees"))))return;
        if(J->HasField(TEXT("scale_xyz"))){FVector Scale;if(!LuxuryVector(J,TEXT("scale_xyz"),Scale)||Scale.GetMin()<=0||Scale.GetMax()>4)return;}
        for(const auto& ID:Array(J,TEXT("models")))if(!Meshes.Contains(ID->AsString()))return;
    }
    for(const auto& Pair:Meshes){
        auto C=NewObject<UHierarchicalInstancedStaticMeshComponent>(Scene);Scene->AddInstanceComponent(C);C->SetupAttachment(Scene->GetRootComponent());C->SetStaticMesh(Pair.Value);
        if(IsParisSeineDressed()&&Pair.Key==TEXT("relief_glass")){
            if(auto Glass=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisSeineWindow")))C->SetMaterial(0,Glass);
            C->InstancingRandomSeed=73129;
        }
        C->ComponentTags.Add(TEXT("ParisLuxury"));C->ComponentTags.Add(FName(*Pair.Key));C->SetCollisionEnabled(ECollisionEnabled::NoCollision);C->SetGenerateOverlapEvents(false);C->SetCanEverAffectNavigation(false);
        C->SetCastShadow(!Pair.Key.Contains(TEXT("nature"))&&!Pair.Key.Contains(TEXT("flowers"))&&!Pair.Key.StartsWith(TEXT("festoon_"))&&!Pair.Key.StartsWith(TEXT("window_"))&&!Pair.Key.StartsWith(TEXT("night_window_"))&&!Pair.Key.StartsWith(TEXT("proxy_"))&&!Pair.Key.EndsWith(TEXT("bulbs"))&&Pair.Key!=TEXT("relief_glass")&&Pair.Key!=TEXT("street_festoon_wire")&&Pair.Key!=TEXT("facade_lantern")&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoShadows")));C->RegisterComponent();
        if(Pair.Key.StartsWith(TEXT("proxy_")))C->CreateDynamicMaterialInstance(0);
        if(Pair.Key.StartsWith(TEXT("festival_"))){C->ComponentTags.Add(TEXT("ParisFestival"));C->SetCastShadow(false);}
        if(Pair.Key.StartsWith(TEXT("market_"))){C->ComponentTags.Add(TEXT("ParisStreetDisplay"));C->SetCastShadow(!Pair.Key.Contains(TEXT("blooms"))&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoShadows")));}
        if(Pair.Key.StartsWith(TEXT("market_extra_"))){C->ComponentTags.Add(TEXT("ParisExtraObject"));if(Pair.Key.Contains(TEXT("leaves"))||Pair.Key.Contains(TEXT("hanging")))C->SetCastShadow(false);}
        TArray<FTransform> Transforms;
        for(const auto& V:Array(Data,TEXT("records"))){auto J=V->AsObject();bool Includes=false;for(const auto& ID:Array(J,TEXT("models")))Includes|=ID->AsString()==Pair.Key;if(!Includes)continue;
            FVector P,Scale(1);LuxuryVector(J,TEXT("anchor_cm"),P);if(J->HasField(TEXT("scale_xyz")))LuxuryVector(J,TEXT("scale_xyz"),Scale);Transforms.Add(FTransform(FRotator(0,Number(J,TEXT("yaw_degrees")),0),P,Scale));
        }
        C->AddInstances(Transforms,false,false,false);
    }
    for(const auto& V:Array(Data,TEXT("records"))){auto J=V->AsObject();if(String(J,TEXT("kind"))!=TEXT("urn"))continue;FVector P;LuxuryVector(J,TEXT("anchor_cm"),P);
        auto C=NewObject<UCapsuleComponent>(Scene);Scene->AddInstanceComponent(C);C->SetupAttachment(Scene->GetRootComponent());C->InitCapsuleSize(43,53);C->SetRelativeLocation(P+FVector(0,0,53));
        C->ComponentTags.Add(TEXT("ParisLuxuryUrn"));C->ComponentTags.Add(FName(*String(J,TEXT("source_id"))));if(String(J,TEXT("anchor_source_kind"))==TEXT("street_bench"))C->ComponentTags.Add(TEXT("ParisPublicUrn"));C->SetCollisionObjectType(ECC_WorldStatic);C->SetCollisionResponseToAllChannels(ECR_Block);C->SetGenerateOverlapEvents(false);C->SetCanEverAffectNavigation(false);C->RegisterComponent();
    }
    for(const auto& V:Array(Data,TEXT("records"))){auto J=V->AsObject();for(const auto& B:Array(J,TEXT("collision_boxes"))){FVector P,Centre,Size;if(!LuxuryVector(J,TEXT("anchor_cm"),P)||!LuxuryVector(B->AsObject(),TEXT("centre_cm"),Centre)||!LuxuryVector(B->AsObject(),TEXT("size_cm"),Size)||Size.GetMin()<=0)continue;
        const FRotator Rotation(0,Number(J,TEXT("yaw_degrees")),0);auto C=NewObject<UBoxComponent>(Scene);Scene->AddInstanceComponent(C);C->SetupAttachment(Scene->GetRootComponent());C->SetBoxExtent(Size*.5);C->SetRelativeLocationAndRotation(P+Rotation.RotateVector(Centre),Rotation);C->ComponentTags.Add(TEXT("ParisStreetPropCollision"));C->ComponentTags.Add(FName(*String(J,TEXT("source_id"))));C->ComponentTags.Add(FName(*String(J,TEXT("kind"))));C->SetCollisionObjectType(ECC_WorldStatic);C->SetCollisionResponseToAllChannels(ECR_Block);C->SetGenerateOverlapEvents(false);C->SetCanEverAffectNavigation(false);C->RegisterComponent();}}
    SyncParisLuxury(Scene);
}

void SyncParisLuxury(AParisTwinScene* Scene){
    if(!Scene)return;const bool Visible=Scene->bStreetDetails&&!Scene->bLevels&&!Scene->bIssues&&!Scene->bFootprints;
    TArray<UHierarchicalInstancedStaticMeshComponent*> Parts;Scene->GetComponents(Parts);
    for(auto C:Parts)if(C->ComponentHasTag(TEXT("ParisLuxury"))){
        bool Relief=false;for(const auto& Tag:C->ComponentTags)Relief|=Tag.ToString().StartsWith(TEXT("relief_"));
        const bool Festival=C->ComponentHasTag(TEXT("ParisFestival"));
        bool Architectural=Relief;for(const auto& Tag:C->ComponentTags)Architectural|=Tag.ToString().StartsWith(TEXT("night_window_"));
        C->SetVisibility(Visible&&(!IsParisReferenceLook()||Architectural)&&(!C->ComponentHasTag(TEXT("ParisStreetDisplay"))||!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoStreetProps")))&&(!C->ComponentHasTag(TEXT("ParisExtraObject"))||!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoExtraObjects")))&&(!Festival||IsParisFestivalEnabled(Scene))&&(!Relief||(Scene->DetailQuality>0&&Scene->bDetailedSurfaces)));bool Canopy=false,Window=false,Proxy=false,NightWindow=false;
        for(const auto& Tag:C->ComponentTags){const FString ID=Tag.ToString();Canopy|=ID.StartsWith(TEXT("canopy_"))||ID.StartsWith(TEXT("proxy_shop_"))||ID.StartsWith(TEXT("street_festoon_"))||ID.StartsWith(TEXT("proxy_street_"));Window|=ID.StartsWith(TEXT("window_"))||ID.StartsWith(TEXT("proxy_window_"));Proxy|=ID.StartsWith(TEXT("proxy_"));}
        for(const auto& Tag:C->ComponentTags)NightWindow|=Tag.ToString().StartsWith(TEXT("night_window_"));
        const int32 End=Canopy?(Scene->DetailQuality==0?10000:Scene->DetailQuality==1?18000:25000):Window?(Scene->DetailQuality==0?3500:Scene->DetailQuality==1?7000:11000):(Scene->DetailQuality==0?5000:Scene->DetailQuality==1?9000:15000);
        C->SetCullDistances(0,Festival?(Scene->DetailQuality==0?10000:Scene->DetailQuality==1?25000:35000):(Proxy||NightWindow)?150000:Relief?(Scene->DetailQuality==2?16000:11000):End);if(Proxy)if(auto M=Cast<UMaterialInstanceDynamic>(C->GetMaterial(0)))M->SetScalarParameterValue(TEXT("NearCutCm"),End);
    }
    TArray<UCapsuleComponent*> Colliders;Scene->GetComponents(Colliders);for(auto C:Colliders)if(C->ComponentHasTag(TEXT("ParisLuxuryUrn")))C->SetCollisionEnabled(Visible&&!IsParisReferenceLook()?ECollisionEnabled::QueryAndPhysics:ECollisionEnabled::NoCollision);
    TArray<UBoxComponent*> Boxes;Scene->GetComponents(Boxes);for(auto C:Boxes)if(C->ComponentHasTag(TEXT("ParisStreetPropCollision")))C->SetCollisionEnabled(Visible&&!IsParisReferenceLook()&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoStreetProps"))&&(!C->ComponentHasTag(TEXT("street_accent"))||!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoExtraObjects")))?ECollisionEnabled::QueryAndPhysics:ECollisionEnabled::NoCollision);
    SyncParisFestivalAppearance(Scene);
}

bool SelectParisLuxuryHit(AParisTwinScene* Scene,const FHitResult& Hit){
    auto C=Hit.GetComponent();if(!Scene||!C||(!C->ComponentHasTag(TEXT("ParisLuxuryUrn"))&&!C->ComponentHasTag(TEXT("ParisStreetPropCollision"))))return false;
    FString ID;for(const auto& Tag:C->ComponentTags)if(Tag.ToString().StartsWith(TEXT("osm/")))ID=Tag.ToString();
    Scene->ClearInspection();const auto LL=Scene->GeoReference.WGS84FromUE(C->GetComponentLocation());
    if(C->ComponentHasTag(TEXT("street_accent"))){Scene->Selection=TEXT("街角のオブジェ | ")+ID+TEXT("\n店舗・街路設備を基準とした推定配置 / 現地の実物は未確認");Scene->SelectionCoordinates=FString::Printf(TEXT("WGS84 %.7f, %.7f"),LL.Y,LL.X);return true;}
    Scene->Selection=(C->ComponentHasTag(TEXT("ParisStreetPropCollision"))?C->ComponentHasTag(TEXT("terrace_parasol"))?TEXT("カフェのパラソル | "):TEXT("店先のディスプレイ | "):TEXT("花の飾り鉢 | "))+ID+(C->ComponentHasTag(TEXT("ParisPublicUrn"))?TEXT("\n街路設備位置を基準とした推定装飾 / 現地の実物は未確認"):TEXT("\n店舗位置を基準とした推定装飾 / 現地の実物は未確認"));Scene->SelectionCoordinates=FString::Printf(TEXT("WGS84 %.7f, %.7f"),LL.Y,LL.X);return true;
}

bool CycleParisDistrictView(AParisTwinScene* Scene){
    if(!Scene)return false;TSharedPtr<FJsonObject> Data;if(!LoadLuxuryData(Data))return false;
    const auto& Views=Array(Data,TEXT("district_views"));if(Views.IsEmpty())return false;
    for(auto It=DistrictViewIndices.CreateIterator();It;++It)if(!It.Key().IsValid())It.RemoveCurrent();
    const int32 Previous=DistrictViewIndices.Contains(Scene)?DistrictViewIndices[Scene]:0;const int32 Index=(Previous+1)%Views.Num();
    if(!SetDistrictCamera(Scene,Views[Index]->AsObject())||!ActivateParisPhotoCamera(Scene,TEXT("Camera_Paris_Street")))return false;
    DistrictViewIndices.Add(Scene,Index);return true;
}

void AddParisLuxuryStats(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Report){
    int32 Models=0,Instances=0,Urns=0,Tables=0,Canopies=0,Baskets=0,Strings=0,Windows=0,Banners=0,Lanterns=0,Poles=0;TArray<UHierarchicalInstancedStaticMeshComponent*> Parts;Scene->GetComponents(Parts);
    for(auto C:Parts)if(C->ComponentHasTag(TEXT("ParisLuxury"))){Models++;Instances+=C->GetInstanceCount();if(C->ComponentHasTag(TEXT("urn_stone")))Urns=C->GetInstanceCount();if(C->ComponentHasTag(TEXT("table_stone")))Tables=C->GetInstanceCount();if(C->ComponentHasTag(TEXT("canopy_metal")))Canopies=C->GetInstanceCount();if(C->ComponentHasTag(TEXT("floral_basket")))Baskets=C->GetInstanceCount()*2;if(C->ComponentHasTag(TEXT("festoon_bulbs")))Strings=C->GetInstanceCount();if(C->ComponentHasTag(TEXT("facade_lantern")))Lanterns=C->GetInstanceCount();for(const auto& Tag:C->ComponentTags){if(Tag.ToString().StartsWith(TEXT("window_flowers_")))Windows+=C->GetInstanceCount();if(Tag.ToString().StartsWith(TEXT("banner_")))Banners+=C->GetInstanceCount();}}
    for(auto C:Parts)if(C->ComponentHasTag(TEXT("pole_metal")))Poles=C->GetInstanceCount();
    int32 Garlands=0;for(auto C:Parts)if(C->ComponentHasTag(TEXT("street_festoon_wire")))Garlands=C->GetInstanceCount();
    int32 Accents=0,AccentParts=0;for(auto C:Parts)if(C->ComponentHasTag(TEXT("ParisExtraObject"))){AccentParts+=C->IsVisible();for(const auto& Tag:C->ComponentTags){const FString Name=Tag.ToString();if(Name==TEXT("market_extra_hanging_gold")||Name==TEXT("market_extra_bread")||Name==TEXT("market_extra_wine")||Name==TEXT("market_extra_cart")||Name==TEXT("market_extra_bicycle")||Name==TEXT("market_extra_orrery_base")||Name==TEXT("market_extra_topiary_pot"))Accents+=C->GetInstanceCount();}}Report->SetNumberField(TEXT("street_extra_objects"),Accents);Report->SetNumberField(TEXT("street_extra_visible_parts"),AccentParts);
    int32 VisibleDisplays=0;for(auto C:Parts)if(C->ComponentHasTag(TEXT("ParisStreetDisplay"))&&C->IsVisible())VisibleDisplays++;Report->SetNumberField(TEXT("street_prop_visible_parts"),VisibleDisplays);
    int32 Displays=0,Parasols=0;for(auto C:Parts){if(C->ComponentHasTag(TEXT("market_parasol_metal")))Parasols=C->GetInstanceCount();for(const auto& Tag:C->ComponentTags)if(Tag==TEXT("market_menu")||Tag==TEXT("market_books")||Tag==TEXT("market_produce")||Tag==TEXT("market_flowers_frame"))Displays+=C->GetInstanceCount();}Report->SetNumberField(TEXT("street_shop_displays"),Displays);Report->SetNumberField(TEXT("street_terrace_parasols"),Parasols);
    int32 Fans=0,Badges=0,ShopTrims=0,ActiveParts=0;
    for(auto C:Parts){if(C->ComponentHasTag(TEXT("festival_canopy_metal")))Fans=C->GetInstanceCount();if(C->ComponentHasTag(TEXT("festival_banner_gold")))Badges=C->GetInstanceCount();for(const auto& T:C->ComponentTags)if(T.ToString().StartsWith(TEXT("festival_shop_glow_")))ShopTrims+=C->GetInstanceCount();if(C->ComponentHasTag(TEXT("ParisFestival"))&&C->IsVisible())ActiveParts++;}
    Report->SetBoolField(TEXT("festival_enabled"),IsParisFestivalEnabled(Scene));Report->SetNumberField(TEXT("festival_visible_parts"),ActiveParts);Report->SetNumberField(TEXT("festival_canopies"),Fans);Report->SetNumberField(TEXT("festival_lanterns"),Fans*9);Report->SetNumberField(TEXT("festival_fairy_lights"),Fans*75);Report->SetNumberField(TEXT("festival_wall_stars"),Badges);Report->SetNumberField(TEXT("festival_shop_trims"),ShopTrims);
    Report->SetNumberField(TEXT("luxury_street_garlands"),Garlands);Report->SetNumberField(TEXT("luxury_street_flags"),Garlands*14);Report->SetNumberField(TEXT("luxury_street_bulbs"),Garlands*17);
    int32 LitWindows=0;for(auto C:Parts)if(C->ComponentTags.ContainsByPredicate([](const FName& T){return T.ToString().StartsWith(TEXT("night_window_"));}))LitWindows+=C->GetInstanceCount();Report->SetNumberField(TEXT("luxury_lit_windows"),LitWindows);
    int32 Relief=0;for(auto C:Parts)if(C->ComponentHasTag(TEXT("relief_stone")))Relief=C->GetInstanceCount();Report->SetNumberField(TEXT("luxury_relief_windows"),Relief);
    Report->SetNumberField(TEXT("luxury_district_poles"),Poles);Report->SetNumberField(TEXT("luxury_pole_bulbs"),Poles*3);
    Report->SetNumberField(TEXT("luxury_models"),Models);Report->SetNumberField(TEXT("luxury_instances"),Instances);Report->SetNumberField(TEXT("luxury_urns"),Urns);Report->SetNumberField(TEXT("luxury_tables"),Tables);Report->SetNumberField(TEXT("luxury_canopies"),Canopies);
    Report->SetNumberField(TEXT("luxury_hanging_baskets"),Baskets);Report->SetNumberField(TEXT("luxury_light_strings"),Strings);Report->SetNumberField(TEXT("luxury_bulbs"),Strings*12);
    Report->SetNumberField(TEXT("luxury_upper_windows"),Windows);Report->SetNumberField(TEXT("luxury_facade_banners"),Banners);Report->SetNumberField(TEXT("luxury_facade_lanterns"),Lanterns);
}
