#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ParisMetro.generated.h"
class FJsonObject;
class AParisTwinScene;
class AParisTwinController;
class UProceduralMeshComponent;
class UCameraComponent;
UCLASS()
class AParisMetro : public AActor {
    GENERATED_BODY()
public:
    AParisMetro();
    bool Initialize(AParisTwinScene* InScene,const TSharedPtr<FJsonObject>& Data);
    virtual void Tick(float Delta) override;
    void EnterExit(AParisTwinController* PC);
    void BoardExit(AParisTwinController* PC);
    void SimulateStep(double Delta);
    FVector PlatformLocation(int32 Station) const;
    bool bReady=false,bInside=false,bRiding=false,bMoving=false;
    int32 Station=0,Destination=1;
    double Length=0,Distance=0,Speed=0,Travelled=0;
private:
    void UpdateTrain();
    UPROPERTY() TObjectPtr<AParisTwinScene> Scene;
    UPROPERTY() TObjectPtr<USceneComponent> TrainRoot;
    UPROPERTY() TObjectPtr<UCameraComponent> TrainCamera;
    UPROPERTY() TObjectPtr<UProceduralMeshComponent> StationMesh;
    UPROPERTY() TObjectPtr<UProceduralMeshComponent> TrainMesh;
    FVector Entrances[2];
};
