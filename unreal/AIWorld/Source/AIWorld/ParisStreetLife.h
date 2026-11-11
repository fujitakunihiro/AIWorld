#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Dom/JsonObject.h"
#include "ParisStreetLife.generated.h"
class AParisTwinScene;
class UHierarchicalInstancedStaticMeshComponent;
class USkeletalMeshComponent;
class UStaticMesh;
class UMaterialInterface;

// Street life at the mapped storefronts, modelled on Ile de la Cite reference photographs
// (references/ile-de-la-cite): long cafe awnings over rows of bistro tables and rattan chairs,
// souvenir postcard spinners, scarf racks and chalkboard menus, plus seated customers.
// Positions reuse the inferred storefront frames; real layouts and occupancy are unverified.
struct FParisTourist{FVector A,B;double Yaw=0,Speed=110,Phase=0;int32 Variant=0;bool Walk=false;};
UCLASS()
class AParisStreetLife : public AActor {
    GENERATED_BODY()
public:
    AParisStreetLife();
    bool Initialize(AParisTwinScene* InScene,const TSharedPtr<FJsonObject>& Data);
    virtual void Tick(float DeltaSeconds) override;
    int32 TerraceCount=0,TableCount=0,ChairCount=0,ShopDisplayCount=0,SeatedVisible=0,ParvisCount=0;
private:
    UHierarchicalInstancedStaticMeshComponent* AddPrototype(const FName& Key,UStaticMesh* Mesh,double CullCm);
    void UpdateSeated();
    void UpdateTourists(bool Reassign);
    void AddTourist(const FVector& A,const FVector& B,double Yaw,uint32 Seed,bool Walk);
    UPROPERTY() TObjectPtr<AParisTwinScene> Scene;
    UPROPERTY() TMap<FName,TObjectPtr<UHierarchicalInstancedStaticMeshComponent>> Parts;
    UPROPERTY() TArray<TObjectPtr<USkeletalMeshComponent>> Seated;
    TArray<FTransform> TerraceFronts,ShopFronts;
    TArray<FTransform> Seats;      // occupied chairs (world), facing the street
    TArray<int32> SeatVariant;     // avatar index per seat
    TArray<int32> SlotSeat;        // seat shown by each pooled mesh
    TArray<int32> SlotVariant;
    double Remaining=0,Clock=0;
    TArray<FParisTourist> Tourists;
    UPROPERTY() TArray<TObjectPtr<USkeletalMeshComponent>> Walkers;
    TArray<int32> WalkerTourist,WalkerVariant;
};
