#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ParisChapelle.generated.h"
class AParisTwinScene;
class APlayerController;
class AParisTwinController;
class UCameraComponent;
class UPointLightComponent;
class UProceduralMeshComponent;
UCLASS()
class AParisChapelleDetail : public AActor {
    GENERATED_BODY()
public:
    AParisChapelleDetail();
    bool Initialize(AParisTwinScene* InScene);
    void Sync();
    void ActivateView(APlayerController* PC,int32 Index=0);
    bool CycleView(APlayerController* PC);
    void ToggleInterior(AParisTwinController* PC);
    virtual void Tick(float DeltaSeconds) override;
    int32 ViewIndex=0;bool bInteriorBuilt=false;bool bWasInside=false;bool bSavedExposure=false;float SavedISO=100,SavedShutter=125;float InteriorISO=400,InteriorShutter=30;
    bool bReady=false;
    int32 WindowCount=0,ButtressCount=0;
    double SpireHeightCm=0;
private:
    UPROPERTY() TObjectPtr<AParisTwinScene> Scene;
    UPROPERTY() TObjectPtr<UProceduralMeshComponent> Stone;
    UPROPERTY() TObjectPtr<UProceduralMeshComponent> Glass;
    UPROPERTY() TObjectPtr<UProceduralMeshComponent> Roof;
    UPROPERTY() TObjectPtr<UCameraComponent> Camera;
    UPROPERTY() TObjectPtr<UCameraComponent> WestCamera;
    UPROPERTY() TObjectPtr<UCameraComponent> ApseCamera;
    UPROPERTY() TObjectPtr<UCameraComponent> WindowCamera;
    UPROPERTY() TObjectPtr<UProceduralMeshComponent> InnerSolid;
    UPROPERTY() TObjectPtr<UProceduralMeshComponent> InnerGlass;
    UPROPERTY() TObjectPtr<UProceduralMeshComponent> InnerVault;
    UPROPERTY() TObjectPtr<UProceduralMeshComponent> InnerBeams;
    UPROPERTY() TArray<TObjectPtr<UPointLightComponent>> InnerLights;
};
