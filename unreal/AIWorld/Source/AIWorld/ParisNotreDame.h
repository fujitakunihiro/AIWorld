#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ParisNotreDame.generated.h"
class AParisTwinScene;
class AParisTwinController;
class APlayerController;
class UCameraComponent;
class UPointLightComponent;
class UProceduralMeshComponent;
// Inferred reconstruction of the Notre-Dame de Paris interior (nave with double aisles and side
// chapels, transept with rose windows, choir, apse and double ambulatory). Proportions follow the
// published dimensions; the GIS footprint/collision of osm/way/201611261 is retained untouched.
UCLASS()
class AParisNotreDameInterior : public AActor {
    GENERATED_BODY()
public:
    AParisNotreDameInterior();
    bool Initialize(AParisTwinScene* InScene);
    void ActivateView(APlayerController* PC,int32 Index);
    void ToggleInterior(AParisTwinController* PC);
    bool IsCameraInside(const FVector& WorldLocation) const;
    virtual void Tick(float DeltaSeconds) override;
    bool bInteriorBuilt=false;bool bWasInside=false;int32 ViewIndex=0;
    float InteriorISO=800,InteriorShutter=30;
    int32 WindowCount=0,PierCount=0,ChairCount=0;
private:
    UPROPERTY() TObjectPtr<AParisTwinScene> Scene;
    UPROPERTY() TObjectPtr<UProceduralMeshComponent> InnerSolid;
    UPROPERTY() TObjectPtr<UProceduralMeshComponent> InnerGlass;
    UPROPERTY() TObjectPtr<UProceduralMeshComponent> InnerBeams;
    UPROPERTY() TObjectPtr<UCameraComponent> WestCamera;
    UPROPERTY() TObjectPtr<UCameraComponent> CrossingCamera;
    UPROPERTY() TObjectPtr<UCameraComponent> ChoirCamera;
    UPROPERTY() TArray<TObjectPtr<UPointLightComponent>> InnerLights;
    TArray<TWeakObjectPtr<AActor>> HiddenWorld;
};
