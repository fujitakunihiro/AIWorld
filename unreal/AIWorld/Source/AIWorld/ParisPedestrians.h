#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Dom/JsonObject.h"
#include "ParisPedestrians.generated.h"
class UInstancedStaticMeshComponent;
class UStaticMesh;
class UMaterialInterface;
class UPrimitiveComponent;

// Six articulated parts. Units are centimetres; Root is the ground underfoot.
TArray<FTransform> ParisPersonPose(const FVector& Root,double Yaw,double Phase,bool Moving);
FString ParisPersonPartModel(int32 Part,int32 Variant);

struct FParisPedestrianRoute {
    FString ID,SourceID,SourceURL,PlacementSource;
    TArray<FVector> Points;
    TArray<double> Distances;
    double Length=0;
    FVector Sample(double Distance,double Direction,double* Yaw=nullptr) const;
};
struct FParisPedestrian {
    FString ID;
    int32 Route=0,Variant=0,Direction=1;
    double Distance=0,Speed=120,Wait=0,BlockedAge=0,Phase=0,GroundOffset=0;
    FVector Position=FVector::ZeroVector;
    double Yaw=0;
    bool Moving=false;
};

UCLASS()
class AParisPedestrianCrowd : public AActor {
    GENERATED_BODY()
public:
    AParisPedestrianCrowd();
    bool Initialize(const TSharedPtr<FJsonObject>& Data);
    virtual void Tick(float Delta) override;
    void SimulateStep(double Delta,const FVector* Player=nullptr);
    void UpdateInstances(bool TraceGround=false);
    void SetDisplay(bool Enabled,int32 Quality);
    FString DescribeHit(UPrimitiveComponent* Component,int32 Instance) const;
    UStaticMesh* Model(const FString& Name) const;
    const TArray<FParisPedestrian>& People() const { return Agents; }
    const TArray<FParisPedestrianRoute>& Network() const { return Routes; }
    int32 VisibleCount=0,RecoveryTurns=0;
    double TravelledCm=0;
    bool bEnabled=true,bReady=false;
private:
    TArray<FParisPedestrianRoute> Routes;
    TArray<FParisPedestrian> Agents;
    UPROPERTY() TArray<TObjectPtr<UStaticMesh>> Models;
    UPROPERTY() TArray<TObjectPtr<UInstancedStaticMeshComponent>> Instances;
    TMap<FString,UStaticMesh*> ModelByName;
    TMap<FString,UInstancedStaticMeshComponent*> InstanceByName;
    TMap<UPrimitiveComponent*,TArray<int32>> AgentByInstance;
    int32 DetailQuality=1;
    double SimAccumulator=0,RenderAccumulator=0,GroundAccumulator=0;
};
