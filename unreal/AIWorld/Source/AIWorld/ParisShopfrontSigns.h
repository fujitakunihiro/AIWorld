#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Dom/JsonObject.h"
#include "ParisShopfrontSigns.generated.h"

class AParisTwinScene;
class UHierarchicalInstancedStaticMeshComponent;
class UTextRenderComponent;

// A bounded pool of labels on inferred shopfronts. OSM names are archival,
// while the signs themselves are an authored visual approximation.
UCLASS()
class AParisShopfrontSigns : public AActor {
    GENERATED_BODY()
public:
    AParisShopfrontSigns();
    bool Initialize(AParisTwinScene* InScene,const TSharedPtr<FJsonObject>& Data);
    virtual void Tick(float DeltaSeconds) override;
    void UpdateSigns();
    int32 ShopCount() const { return Shops.Num(); }
    UPROPERTY() TObjectPtr<UHierarchicalInstancedStaticMeshComponent> Panels;
    UPROPERTY() TObjectPtr<UHierarchicalInstancedStaticMeshComponent> MenuBoards;
    UPROPERTY() TObjectPtr<UHierarchicalInstancedStaticMeshComponent> ProduceCrates;
    UPROPERTY() TObjectPtr<UHierarchicalInstancedStaticMeshComponent> Produce;
    UPROPERTY() TArray<TObjectPtr<UTextRenderComponent>> Names;
    UPROPERTY() TArray<TObjectPtr<UTextRenderComponent>> Categories;
    UPROPERTY() TArray<TObjectPtr<UTextRenderComponent>> Menus;
private:
    struct FShop { FVector Position; double Yaw; FString Name; FString Category; bool Restaurant; bool Grocery; };
    TArray<FShop> Shops;
    UPROPERTY() TObjectPtr<AParisTwinScene> Scene;
    double Remaining=0;
};
