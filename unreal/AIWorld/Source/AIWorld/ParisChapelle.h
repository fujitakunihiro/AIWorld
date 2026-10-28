#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ParisChapelle.generated.h"
class AParisTwinScene;
class APlayerController;
class UCameraComponent;
class UProceduralMeshComponent;
UCLASS()
class AParisChapelleDetail : public AActor {
    GENERATED_BODY()
public:
    AParisChapelleDetail();
    bool Initialize(AParisTwinScene* InScene);
    void Sync();
    void ActivateView(APlayerController* PC);
    bool bReady=false;
    int32 WindowCount=0,ButtressCount=0;
    double SpireHeightCm=0;
private:
    UPROPERTY() TObjectPtr<AParisTwinScene> Scene;
    UPROPERTY() TObjectPtr<UProceduralMeshComponent> Stone;
    UPROPERTY() TObjectPtr<UProceduralMeshComponent> Glass;
    UPROPERTY() TObjectPtr<UProceduralMeshComponent> Roof;
    UPROPERTY() TObjectPtr<UCameraComponent> Camera;
};
