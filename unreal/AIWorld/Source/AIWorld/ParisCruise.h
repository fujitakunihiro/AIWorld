#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ParisCruise.generated.h"
class FJsonObject;
class UStaticMeshComponent;
class UCameraComponent;
class UBoxComponent;
UCLASS()
class AParisCruise : public AActor {
    GENERATED_BODY()
public:
    AParisCruise();
    bool Initialize(const TSharedPtr<FJsonObject>& SceneData);
    virtual void Tick(float Delta) override;
    void SimulateStep(double Delta);
    void RefreshPose();
    void ActivateView(APlayerController* Controller);
    FString Describe() const;
    FVector Start=FVector::ZeroVector,End=FVector::ZeroVector;
    double Length=0,Distance=0,Speed=0,Travelled=0,WaterLevel=0,Yaw=0,Elapsed=0,TurnTime=-1,TurnStartYaw=0;
    int32 Direction=1,Turns=0;
    bool bReady=false;
private:
    UPROPERTY() TObjectPtr<UStaticMeshComponent> Body;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> Glass;
    UPROPERTY() TObjectPtr<UCameraComponent> Camera;
    UPROPERTY() TObjectPtr<UBoxComponent> PickBox;
};
