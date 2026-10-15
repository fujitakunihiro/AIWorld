#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ParisPedestrians.h"
#include "ParisTraffic.generated.h"

class UStaticMesh;
class UInstancedStaticMeshComponent;
class UPrimitiveComponent;

struct FParisVehicle {
    FString ID;
    int32 Route=0,Variant=0;
    double Distance=0,Speed=500,Wait=0;
    FVector Position=FVector::ZeroVector;
    double Yaw=0;
    bool bActive=true,bMoving=false;
};

// Preview traffic, explicitly inferred. Source routes are directed independent
// road segments; cars are hidden before recycling, never driven in reverse.
UCLASS()
class AParisTraffic : public AActor {
    GENERATED_BODY()
public:
    AParisTraffic();
    bool Initialize(const TSharedPtr<FJsonObject>& Data);
    virtual void Tick(float Delta) override;
    void SimulateStep(double Delta,const FVector* Player=nullptr,const TArray<FVector>& People={});
    void SetDisplay(bool Enabled,int32 Quality);
    void UpdateInstances();
    FString DescribeHit(UPrimitiveComponent* Component,int32 Instance) const;
    const TArray<FParisVehicle>& Vehicles() const {return Cars;}
    const TArray<FParisPedestrianRoute>& Network() const {return Routes;}
    UPROPERTY() TObjectPtr<AParisPedestrianCrowd> Crowd;
    bool bEnabled=true,bReady=false;
    int32 VisibleBudget=0,RenderedCount=0,Recycles=0,YieldSteps=0;
    double TravelledCm=0;
private:
    TArray<FParisVehicle> Cars;
    TArray<FParisPedestrianRoute> Routes;
    UPROPERTY() TArray<TObjectPtr<UStaticMesh>> Models;
    UPROPERTY() TArray<TObjectPtr<UInstancedStaticMeshComponent>> Meshes;
    TMap<FString,UInstancedStaticMeshComponent*> MeshByName;
    TMap<UPrimitiveComponent*,TArray<int32>> CarByInstance;
    double SimAccumulator=0,RenderAccumulator=0;
    int32 DetailQuality=1;
};
