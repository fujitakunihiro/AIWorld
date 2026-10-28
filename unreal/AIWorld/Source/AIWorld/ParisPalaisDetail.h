#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ParisPalaisDetail.generated.h"
class AParisTwinScene;
class APlayerController;
class FJsonObject;
class UCameraComponent;
class UHierarchicalInstancedStaticMeshComponent;
UCLASS()
class AParisPalaisDetail : public AActor {
    GENERATED_BODY()
public:
    AParisPalaisDetail();
    bool Initialize(AParisTwinScene* InScene,const TSharedPtr<FJsonObject>& WorldData);
    void Sync();
    void ActivateView(APlayerController* PC);
    bool bReady=false,bEnabled=true,bPhotorealGlass=false;
    int32 WindowCount=0;
    UPROPERTY() TArray<TObjectPtr<UHierarchicalInstancedStaticMeshComponent>> Groups;
private:
    UPROPERTY() TObjectPtr<AParisTwinScene> Scene;
    UPROPERTY() TObjectPtr<UCameraComponent> Camera;
};
