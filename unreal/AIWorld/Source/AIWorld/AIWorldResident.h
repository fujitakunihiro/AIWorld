#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Dom/JsonObject.h"
#include "WorldProtocol.h"
#include "AIWorldResident.generated.h"
class AAIWorldScene;
class UProceduralMeshComponent;
class UStaticMeshComponent;
UCLASS()
class AIWORLD_API AAIWorldResident : public AActor {
    GENERATED_BODY()
public:
    AAIWorldResident();
    void Sync(AAIWorldScene* World,const TSharedPtr<FJsonObject>& Json);
    virtual void Tick(float Delta) override;
    void Select(bool Selected);
    FString ID;
private:
    UPROPERTY() TObjectPtr<AAIWorldScene> Scene;
    UPROPERTY() TObjectPtr<USceneComponent> Upper;
    UPROPERTY() TObjectPtr<USceneComponent> HeadPivot;
    UPROPERTY() TArray<TObjectPtr<USceneComponent>> ArmPivots;
    UPROPERTY() TArray<TObjectPtr<USceneComponent>> LegPivots;
    UPROPERTY() TArray<TObjectPtr<UProceduralMeshComponent>> Parts;
    UPROPERTY() TObjectPtr<UProceduralMeshComponent> Tool;
    UPROPERTY() TObjectPtr<UProceduralMeshComponent> Cargo;
    UPROPERTY() TObjectPtr<UProceduralMeshComponent> Face;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> Ring;
    FVector Destination=FVector::ZeroVector;
    FString Job, Action, ToolName, CargoName, Clothing;
    TSharedPtr<FJsonObject> RenderModel;
    AIWorld::FMesh BaseFace;
    TArray<FVector4> FaceMorphs;
    FLinearColor ShirtFrom, ShirtTo;
    double NextFace=0;
    bool bTired=false,bHappy=false,bWorried=false;
    double Phase=0, Anim=0;
    bool bInitialized=false;
    void Rebuild();
    UProceduralMeshComponent* Part(const TSharedPtr<FJsonObject>& Json,USceneComponent* Parent);
};
