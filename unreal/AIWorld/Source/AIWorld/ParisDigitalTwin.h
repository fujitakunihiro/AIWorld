#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/HUD.h"
#include "Dom/JsonObject.h"
#include "ParisDigitalTwin.generated.h"

class UCameraComponent;
class UProceduralMeshComponent;
class UMaterialInterface;
class UPrimitiveComponent;

UCLASS()
class AParisTwinCamera : public APawn {
    GENERATED_BODY()
public:
    AParisTwinCamera();
    virtual void Tick(float Delta) override;
    void Overview(double Extent);
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
    void ToggleLevels();
    void Capture();
    bool bReady=false,bLevels=false;
    FString Status=TEXT("GISデータを読み込み中"),Selection;
    double Extent=800;
    FVector QualityCentre=FVector::ZeroVector;
    int32 BuildingCount=0,TriangleCount=0;
private:
    UPROPERTY() TArray<TObjectPtr<UProceduralMeshComponent>> Meshes;
    UPROPERTY() TObjectPtr<UMaterialInterface> VertexMaterial;
    UPROPERTY() TObjectPtr<UMaterialInterface> StoneMaterial;
    UPROPERTY() TObjectPtr<UMaterialInterface> WaterMaterial;
    TMap<UPrimitiveComponent*,TSharedPtr<FJsonObject>> Features;
    double ReadyAt=0;
    bool bCaptured=false,bMeasured=false;
    TArray<double> FrameTimes;
};

UCLASS()
class AParisTwinHUD : public AHUD {
    GENERATED_BODY()
public:
    virtual void DrawHUD() override;
};
