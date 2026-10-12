#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "WorldProtocol.h"
#include "IWebSocket.h"
#include "AIWorldScene.generated.h"

class UHierarchicalInstancedStaticMeshComponent;
class UMaterialInstanceDynamic;
class AAIWorldResident;
class ADirectionalLight;
class ASkyLight;
class AExponentialHeightFog;
class UInstancedStaticMeshComponent;
struct FNativePart { AIWorld::FMesh Mesh; double Stage=0; };
struct FNativeParticle { FVector Position,Velocity; float Age=0; };

UCLASS()
class AIWORLD_API AAIWorldScene : public AActor {
    GENERATED_BODY()
public:
    AAIWorldScene();
    virtual void BeginPlay() override;
    virtual void Tick(float Delta) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    AIWorld::FGrid Grid;
    TSharedPtr<FJsonObject> Village;
    FString Status=TEXT("世界に接続しています…"), Reply;
    double Time=480,FPS=60; int32 Speed=1, Revision=-1, Quality=1,LightPreview=-1;
    bool bConnected=false, bReady=false, bClassic=false;
    bool bSound=true;
    void Send(const FString& Command);
    void SetClassic(bool Value);
    void SetQuality(int32 Value);
    TSharedPtr<FJsonObject> Resident(const FString& ID) const;
    const TMap<FString,TObjectPtr<AAIWorldResident>>& People() const {return Residents;}
    void Receive(const FString& Text);
    void RefreshPresentation(){SyncVillage();}
    UMaterialInterface* VertexMaterial() const {return Vertex;}
    const TSharedPtr<FJsonObject>& Models() const {return Assets;}
    UMaterialInstanceDynamic* ColorMaterial(const FString& Color);
    UProceduralMeshComponent* NewMesh(const AIWorld::FMesh& Mesh, UMaterialInterface* Material, bool Shadow=true);
private:
    TSharedPtr<IWebSocket> Socket;
    TSharedPtr<FJsonObject> Assets, SceneData;
    TMap<FString,TArray<FNativePart>> BuildingTemplates;
    TMap<FString,AIWorld::FMesh> Primitives;
    UPROPERTY() TArray<TObjectPtr<UProceduralMeshComponent>> Terrain;
    UPROPERTY() TArray<TObjectPtr<UProceduralMeshComponent>> StaticModels;
    UPROPERTY() TArray<TObjectPtr<UHierarchicalInstancedStaticMeshComponent>> Nature;
    UPROPERTY() TMap<FString,TObjectPtr<UProceduralMeshComponent>> Structures;
    UPROPERTY() TMap<FString,TObjectPtr<AAIWorldResident>> Residents;
    UPROPERTY() TMap<FString,TObjectPtr<UMaterialInstanceDynamic>> ColorMaterials;
    UPROPERTY() TObjectPtr<UMaterialInterface> Vertex;
    UPROPERTY() TObjectPtr<UMaterialInterface> Color;
    UPROPERTY() TObjectPtr<UMaterialInterface> Water;
    UPROPERTY() TObjectPtr<UMaterialInterface> Stone;
    UPROPERTY() TObjectPtr<UMaterialInterface> Slate;
    UPROPERTY() TObjectPtr<UMaterialInterface> TerrainMaterial;
    UPROPERTY() TObjectPtr<ADirectionalLight> Sun;
    UPROPERTY() TObjectPtr<ASkyLight> Sky;
    UPROPERTY() TObjectPtr<AExponentialHeightFog> Fog;
    UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> Effects;
    TSet<int32> Dirty;
    TMap<FString,FString> StructureKeys;
    FString MaskSignature;
    FString URL;
    double RetryAt=0, NextNature=0, NextLight=0;
    bool bLoading=false, bEnded=false;
    int32 Failures=0;
    double ReadyAt=0;
    bool bBenchmarkDone=false,bCaptured=false,bSkyRecaptured=false;
    TArray<double> FrameTimes;
    TArray<FNativeParticle> Particles;
    double NextParticles=0,NextSound=0;
    int32 LastEvent=-1;
    void PlayEvent(const FString& Kind);
    void FetchWorld();
    void Connect();
    void LoadAssets();
    void SyncVillage();
    void SyncMask();
    void RebuildNature();
    void DirtyEdit(const TSharedPtr<FJsonObject>& Edit);
    void AllDirty();
    void BuildChunk(int32 Key);
    void DrawStructure(const FString& ID, const FString& Key, const AIWorld::FMesh& Mesh, UMaterialInterface* Surface=nullptr);
    AIWorld::FMesh Primitive(const FString& Name,const FVector& P,const FVector& Scale,const FLinearColor& Color) const;
};
