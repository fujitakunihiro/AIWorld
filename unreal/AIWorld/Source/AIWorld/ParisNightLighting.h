#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Dom/JsonObject.h"
#include "ParisNightLighting.generated.h"

class AParisTwinScene;
class USpotLightComponent;
class UMaterialParameterCollection;
class UMaterialInterface;
class UPrimitiveComponent;

struct FParisNightSource {
    FVector Position=FVector::ZeroVector;
    FRotator Rotation=FRotator(-90,0,0);
    FString SourceID;
    float Lumens=4500,Radius=1500,Temperature=2800,OuterAngle=74;
    int32 Kind=0; // 0 mapped street lamp, 1 inferred storefront, 2 landmark flood
};

UCLASS()
class AParisNightLighting : public AActor {
    GENERATED_BODY()
public:
    AParisNightLighting();
    bool Initialize(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Data);
    virtual void Tick(float Delta) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    void Synchronize(bool Immediate=false);
    void AddStats(const TSharedPtr<FJsonObject>& Report) const;
    const TArray<FParisNightSource>& GetSources() const { return Sources; }
    int32 ActiveLights=0,ShadowLights=0,StreetBudget=0,ShopBudget=0,FloodBudget=0;
    float NightAmount=0;
private:
    UPROPERTY() TArray<TObjectPtr<USpotLightComponent>> Lights;
    UPROPERTY() TObjectPtr<UMaterialParameterCollection> Collection;
    UPROPERTY() TObjectPtr<UMaterialInterface> LanternMaterial;
    TWeakObjectPtr<AParisTwinScene> Scene;
    TArray<FParisNightSource> Sources;
    TArray<int32> Selected;
    TMap<TWeakObjectPtr<UPrimitiveComponent>,TWeakObjectPtr<UMaterialInterface>> OriginalLampMaterials;
    double SelectionElapsed=1;
    int32 PreviousPreset=-1,PreviousQuality=-1;
    bool PreviousDebug=false;
    void SelectLights(const FVector& View);
};

void CreateParisNightLighting(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Data);
void SyncParisNightLighting(AParisTwinScene* Scene);
void AddParisNightLightingStats(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Report);
