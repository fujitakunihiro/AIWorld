#include "ParisNightLighting.h"
#include "ParisDigitalTwin.h"
#include "ParisBridgeDetail.h"
#include "WorldProtocol.h"
#include "Components/SpotLightComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Engine/ExponentialHeightFog.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Materials/MaterialParameterCollection.h"
#include "Materials/MaterialParameterCollectionInstance.h"
#include "Materials/MaterialInterface.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Serialization/JsonSerializer.h"
using namespace AIWorld;

namespace {
bool ReadVector(const TSharedPtr<FJsonObject>& J,const TCHAR* Key,FVector& P){
    const auto& A=Array(J,Key);if(A.Num()!=3)return false;
    P=FVector(A[0]->AsNumber(),A[1]->AsNumber(),A[2]->AsNumber());return !P.ContainsNaN();
}
}
AParisNightLighting::AParisNightLighting(){
    RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("NightLightingRoot"));
    PrimaryActorTick.bCanEverTick=true;PrimaryActorTick.TickInterval=.1f;
    Tags.Add(TEXT("ParisNightLighting"));
}

bool AParisNightLighting::Initialize(AParisTwinScene* InScene,const TSharedPtr<FJsonObject>& Data){
    if(Scene.IsValid())return true;Scene=InScene;SetOwner(InScene);
    Collection=LoadObject<UMaterialParameterCollection>(nullptr,TEXT("/Game/Night/MPC_ParisNight"));
    LanternMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Night/M_ParisNightLantern"));
    if(!Collection||!LanternMaterial||!InScene||!Data)return false;
    // Use the exact archived fixture transform, including estimated height and
    // bridge display correction. No invented street-light positions.
    TSet<FString> Seen;
    for(const auto& V:Array(Data,TEXT("instance_batches"))){auto B=V->AsObject();if(String(B,TEXT("model"))!=TEXT("lamp_glass"))continue;
        for(const auto& I:Array(B,TEXT("instances"))){auto J=I->AsObject();FVector P,Scale;const FString ID=String(J,TEXT("source_id"));
            if(ID.IsEmpty()||Seen.Contains(ID)||!ReadVector(J,TEXT("position_cm"),P)||!ReadVector(J,TEXT("scale"),Scale)||Scale.GetMin()<=0)continue;
            Seen.Add(ID);double BridgeZ;if(ParisBridgeVisualHeight(GetWorld(),P,BridgeZ))P.Z=BridgeZ;
            FParisNightSource S;S.Position=P+FVector(0,0,368*Scale.Z);S.SourceID=ID;Sources.Add(S);
        }
    }
    for(const auto& V:Array(Data,TEXT("pick_features"))){auto J=V->AsObject();if(String(J,TEXT("kind"))!=TEXT("business"))continue;
        FVector P;if(!ReadVector(J,TEXT("point_cm"),P))continue;auto Props=Object(J,TEXT("properties"));
        const FRotator R(0,Number(Props,TEXT("facade_yaw_degrees")),0);const FVector Out=R.RotateVector(FVector(0,1,0));
        FParisNightSource S;S.Position=P+Out*65+FVector(0,0,280);S.Rotation=(Out*.45-FVector(0,0,1)).Rotation();
        S.SourceID=String(J,TEXT("id"));S.Kind=1;S.Lumens=1600;S.Radius=750;S.Temperature=3000;S.OuterAngle=65;Sources.Add(S);
    }
    FString Text;TSharedPtr<FJsonObject> Architecture;
    if(FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("Data/paris-photo-architecture.json")))&&FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Architecture)){
        auto Frame=Object(Architecture,TEXT("local_frame"));FVector Front,Across,Depth;
        if(ReadVector(Frame,TEXT("front_cm"),Front)&&ReadVector(Frame,TEXT("across"),Across)&&ReadVector(Frame,TEXT("depth"),Depth)){
            for(float X:{-1400.f,-450.f,450.f,1400.f}){
                FParisNightSource S;S.Position=Front+Across*X-Depth*1000+FVector(0,0,180);
                const FVector Aim=Front+Across*(X*1.1f)+FVector(0,0,2200);
                S.Rotation=(Aim-S.Position).Rotation();S.Kind=2;S.Lumens=26000;S.Radius=6500;S.Temperature=3200;S.OuterAngle=38;
                S.SourceID=FString::Printf(TEXT("inferred_flood:osm/way/201611261:%.0f"),X);Sources.Add(S);
            }
        }
    }
    TArray<UInstancedStaticMeshComponent*> Parts;InScene->GetComponents(Parts);
    for(auto C:Parts)if(C->ComponentHasTag(TEXT("ParisStreetLampGlass")))OriginalLampMaterials.Add(C,C->GetMaterial(0));
    // Fixed reusable pool; camera movement never allocates hundreds of lights.
    for(int32 I=0;I<34;I++){
        auto L=NewObject<USpotLightComponent>(this);AddInstanceComponent(L);L->SetupAttachment(RootComponent);
        L->SetMobility(EComponentMobility::Movable);L->SetIntensityUnits(ELightUnits::Lumens);L->bUseInverseSquaredFalloff=true;
        L->SetUseTemperature(true);L->SetIntensity(0);L->SetVisibility(false);L->SetCastShadows(false);
        L->SetSourceRadius(7);L->SetSoftSourceRadius(18);L->SetVolumetricScatteringIntensity(.35f);L->SetIndirectLightingIntensity(.6f);
        L->RegisterComponent();Lights.Add(L);
    }
    Synchronize(true);return true;
}

void AParisNightLighting::SelectLights(const FVector& View){
    Selected.Reset();auto S=Scene.Get();if(!S)return;
    for(int32 Kind=0;Kind<3;Kind++){
        TArray<int32> Order;
        for(int32 I=0;I<Sources.Num();I++)if(Sources[I].Kind==Kind&&FVector::DistSquared2D(Sources[I].Position,View)<FMath::Square(Kind==2?22000.:8000.))Order.Add(I);
        Order.Sort([&](int32 A,int32 B){return FVector::DistSquared2D(Sources[A].Position,View)<FVector::DistSquared2D(Sources[B].Position,View);});
        const int32 Budget=Kind==0?StreetBudget:Kind==1?ShopBudget:FloodBudget;
        for(int32 I=0;I<FMath::Min(Budget,Order.Num());I++)Selected.Add(Order[I]);
    }
}

void AParisNightLighting::Synchronize(bool Immediate){
    auto S=Scene.Get();if(!S)return;
    const bool Debug=S->bLevels||S->bIssues||S->bFootprints;
    StreetBudget=S->bStreetDetails?(S->DetailQuality==0?6:S->DetailQuality==1?12:24):0;
    ShopBudget=S->DetailQuality==0?1:S->DetailQuality==1?3:6;
    FloodBudget=S->DetailQuality==2?4:2;
    if(Immediate)NightAmount=Debug?0:S->TimeOfDayPreset==2?1.f:S->TimeOfDayPreset==1?.32f:0;
    PreviousPreset=S->TimeOfDayPreset;PreviousQuality=S->DetailQuality;PreviousDebug=Debug;SelectionElapsed=1;
    for(TActorIterator<AExponentialHeightFog> It(GetWorld());It;++It)if(It->ActorHasTag(TEXT("ParisPhotoEnvironment")))It->GetComponent()->SetVolumetricFog(S->TimeOfDayPreset==2&&S->DetailQuality==2&&!Debug);
    for(auto& Pair:OriginalLampMaterials)if(Pair.Key.IsValid())Pair.Key->SetMaterial(0,NightAmount>0?LanternMaterial.Get():Pair.Value.Get());
    Tick(0);
}

void AParisNightLighting::Tick(float Delta){
    Super::Tick(Delta);auto S=Scene.Get();if(!S)return;
    const bool Debug=S->bLevels||S->bIssues||S->bFootprints;
    const int32 WantedStreet=S->bStreetDetails?(S->DetailQuality==0?6:S->DetailQuality==1?12:24):0;
    if(PreviousPreset!=S->TimeOfDayPreset||PreviousQuality!=S->DetailQuality||PreviousDebug!=Debug||WantedStreet!=StreetBudget){Synchronize(true);return;}
    const float Target=Debug?0:S->TimeOfDayPreset==2?1.f:S->TimeOfDayPreset==1?.32f:0;
    NightAmount=FMath::FInterpTo(NightAmount,Target,Delta,2.5f);
    if(Collection)if(auto Instance=GetWorld()->GetParameterCollectionInstance(Collection))Instance->SetScalarParameterValue(TEXT("NightAmount"),NightAmount);
    FVector View=S->QualityCentre;FRotator Rotation;if(auto PC=GetWorld()->GetFirstPlayerController())PC->GetPlayerViewPoint(View,Rotation);
    SelectionElapsed+=Delta;if(SelectionElapsed>=.5){SelectionElapsed=0;SelectLights(View);}
    ActiveLights=ShadowLights=0;int32 StreetShadows=0,FloodShadows=0;
    const bool NoShadows=FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoShadows"));
    for(int32 I=0;I<Lights.Num();I++){
        auto L=Lights[I];if(I>=Selected.Num()||NightAmount<.001f||Debug){L->SetIntensity(0);L->SetVisibility(false);L->SetCastShadows(false);continue;}
        const auto& Source=Sources[Selected[I]];const int32 MaxStreetShadows=S->DetailQuality==2?4:S->DetailQuality==1?1:0,MaxFloodShadows=S->DetailQuality==2?2:S->DetailQuality==1?1:0;
        const bool Shadow=!NoShadows&&(Source.Kind==0?StreetShadows++<MaxStreetShadows:Source.Kind==2?FloodShadows++<MaxFloodShadows:false);
        L->SetWorldLocationAndRotation(Source.Position,Source.Rotation);L->SetAttenuationRadius(Source.Radius);L->SetTemperature(Source.Temperature);
        L->SetOuterConeAngle(Source.OuterAngle);L->SetInnerConeAngle(Source.OuterAngle*.68f);L->SetIntensity(Source.Lumens*NightAmount);
        L->SetCastShadows(Shadow);L->SetVisibility(true);L->ComponentTags.Reset();L->ComponentTags.Add(FName(*Source.SourceID));L->ComponentTags.Add(TEXT("ParisNightLight"));
        ActiveLights++;ShadowLights+=Shadow?1:0;
    }
}

void AParisNightLighting::AddStats(const TSharedPtr<FJsonObject>& Report) const {
    int32 Lamps=0,Shops=0,Floods=0;for(const auto& S:Sources){Lamps+=S.Kind==0;Shops+=S.Kind==1;Floods+=S.Kind==2;}
    Report->SetNumberField(TEXT("night_mapped_lamp_sources"),Lamps);Report->SetNumberField(TEXT("night_inferred_store_lights"),Shops);Report->SetNumberField(TEXT("night_inferred_floods"),Floods);
    Report->SetNumberField(TEXT("night_active_lights"),ActiveLights);Report->SetNumberField(TEXT("night_shadow_lights"),ShadowLights);Report->SetNumberField(TEXT("night_light_pool"),Lights.Num());
    Report->SetNumberField(TEXT("night_amount"),NightAmount);Report->SetNumberField(TEXT("night_street_budget"),StreetBudget);
    Report->SetStringField(TEXT("night_provenance"),TEXT("Archived OSM lamp positions; estimated fixture heights; inferred 2800K/4500lm illumination, store lighting and cathedral flood placement. Not measured current lighting."));
}

void AParisNightLighting::EndPlay(const EEndPlayReason::Type Reason){
    for(auto L:Lights)if(L){L->SetIntensity(0);L->SetVisibility(false);}
    for(auto& Pair:OriginalLampMaterials)if(Pair.Key.IsValid())Pair.Key->SetMaterial(0,Pair.Value.Get());
    if(Collection)if(auto Instance=GetWorld()->GetParameterCollectionInstance(Collection))Instance->SetScalarParameterValue(TEXT("NightAmount"),0);
    Super::EndPlay(Reason);
}
void CreateParisNightLighting(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Data){
    for(TActorIterator<AParisNightLighting> It(Scene->GetWorld());It;++It)if(It->GetOwner()==Scene)return;
    auto Lights=Scene->GetWorld()->SpawnActor<AParisNightLighting>();if(!Lights->Initialize(Scene,Data)){Lights->Destroy();UE_LOG(LogTemp,Error,TEXT("Paris night assets missing; run Build-ParisNight.ps1"));}
}
void SyncParisNightLighting(AParisTwinScene* Scene){for(TActorIterator<AParisNightLighting> It(Scene->GetWorld());It;++It)if(It->GetOwner()==Scene)It->Synchronize(true);}
void AddParisNightLightingStats(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Report){for(TActorIterator<AParisNightLighting> It(Scene->GetWorld());It;++It)if(It->GetOwner()==Scene)It->AddStats(Report);}
