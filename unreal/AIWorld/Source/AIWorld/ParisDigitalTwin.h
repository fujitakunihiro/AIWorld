#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/HUD.h"
#include "Dom/JsonObject.h"
#include "ParisGeoReference.h"
#include "ParisDigitalTwin.generated.h"

class UCameraComponent;
class UProceduralMeshComponent;
class UMaterialInterface;
class UPrimitiveComponent;
class UHierarchicalInstancedStaticMeshComponent;
class UStaticMesh;
class AParisWalker;
class AParisPedestrianCrowd;

UCLASS()
class AParisTwinCamera : public APawn {
    GENERATED_BODY()
public:
    AParisTwinCamera();
    virtual void Tick(float Delta) override;
    void Overview(double Extent,const FVector& Centre=FVector::ZeroVector);
    void Focus(const FVector& Location,double Distance);
    void Eye(const FVector& Location);
    void Zoom(double Factor);
    UPROPERTY() TObjectPtr<UCameraComponent> Camera;
    FVector Target=FVector::ZeroVector;
    double Radius=100000,Yaw=-135,Pitch=55;
    bool bEye=false;
};

UCLASS()
class AParisTwinController : public APlayerController {
    GENERATED_BODY()
public:
    virtual void BeginPlay() override;
    virtual void SetupInputComponent() override;
    void Pick();void ToggleLevels();void Overview();void Eye();void ZoomIn();void ZoomOut();void Capture();
    void BeginLook();void EndLook();
    FVector2D GetRawLookDelta() const;
    bool IsLooking() const { return bLooking; }
    void ToggleFootprints();void ToggleIssues();void ToggleHelp();
    void ToggleStreetDetails();void CycleDetailQuality();
    void LandmarkOne();void LandmarkTwo();void LandmarkThree();
    bool EnterWalk(bool ThirdPerson=false);void Walk();void ToggleWalkView();void TogglePeople();
    void ReturnToFree();
    UPROPERTY() TObjectPtr<AParisTwinCamera> FreeCamera;
    UPROPERTY() TObjectPtr<AParisWalker> Walker;
private:
    bool bLooking=false;
};

UCLASS()
class AParisTwinScene : public AActor {
    GENERATED_BODY()
public:
    AParisTwinScene();
    virtual void BeginPlay() override;
    virtual void Tick(float Delta) override;
    void Select(UPrimitiveComponent* Component);
    void SelectHit(const FHitResult& Hit);
    TSharedPtr<FJsonObject> SourceAt(const FVector& Point,const FString& Kind=TEXT(""),const TArray<TSharedPtr<FJsonValue>>& Allowed={}) const;
    void ToggleLevels();
    void ToggleFootprints();void ToggleIssues();void FocusLandmark(int32 Index);
    void Capture();
    void ToggleStreetDetails();void CycleDetailQuality();void ApplyDetailQuality();
    bool bReady=false,bLevels=false,bFootprints=false,bIssues=false;
    FString Status=TEXT("GISデータを読み込み中"),Selection;
    double Extent=800;
    FVector QualityCentre=FVector::ZeroVector;
    FVector SceneCentre=FVector::ZeroVector;
    FParisGeoReference GeoReference;
    FString IssueSummary;
    int32 BuildingCount=0,TriangleCount=0;
    int32 StreetCount=0,InstanceCount=0,InstanceTriangles=0,DetailQuality=1;
    bool bStreetDetails=true;
    TSharedPtr<FJsonObject> StreetInstanceSource(UPrimitiveComponent* Component,int32 Instance) const;
    bool FindWalkingSpawn(const FVector& Desired,FVector& Centre) const;
    void TogglePeople();
    bool bPeople=true;
    UPROPERTY() TObjectPtr<AParisPedestrianCrowd> Crowd;
private:
    UPROPERTY() TArray<TObjectPtr<UProceduralMeshComponent>> Meshes;
    UPROPERTY() TObjectPtr<UMaterialInterface> VertexMaterial;
    UPROPERTY() TObjectPtr<UMaterialInterface> StoneMaterial;
    UPROPERTY() TObjectPtr<UMaterialInterface> SlateMaterial;
    UPROPERTY() TObjectPtr<UMaterialInterface> WaterMaterial;
    UPROPERTY() TObjectPtr<UMaterialInterface> GlassMaterial;
    UPROPERTY() TObjectPtr<UMaterialInterface> ZincMaterial;
    UPROPERTY() TObjectPtr<UMaterialInterface> IronMaterial;
    UPROPERTY() TObjectPtr<UMaterialInterface> WoodMaterial;
    UPROPERTY() TArray<TObjectPtr<UStaticMesh>> StreetModels;
    UPROPERTY() TArray<TObjectPtr<UHierarchicalInstancedStaticMeshComponent>> StreetMeshes;
    TMap<UPrimitiveComponent*,TArray<FString>> StreetInstanceIDs;
    TMap<UPrimitiveComponent*,FString> StreetModelNames;
    TMap<UPrimitiveComponent*,TSharedPtr<FJsonObject>> Features;
    TArray<TSharedPtr<FJsonObject>> SourceFeatures,Landmarks,Issues;
    TSet<FString> OverlapIDs;
    UPROPERTY() TObjectPtr<UProceduralMeshComponent> FootprintMesh;
    void RefreshAppearance();
    double ReadyAt=0;
    bool bCaptured=false,bMeasured=false;
    bool bWalkLaunchPending=false;
    TArray<double> FrameTimes;
};

UCLASS()
class AParisTwinHUD : public AHUD {
    GENERATED_BODY()
public:
    virtual void DrawHUD() override;
    bool HandleClick(const FVector2D& Position);
    bool bHelp=false;
};
