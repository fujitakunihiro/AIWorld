#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ParisRainWeather.generated.h"

class UProceduralMeshComponent;
class UAudioComponent;
class UMaterialParameterCollection;

struct FParisRainSurface {
    FVector Point=FVector::ZeroVector,Normal=FVector::UpVector;
    bool Valid=false;
};

// Cosmetic weather only. The archived GIS and all source collision stay intact.
UCLASS()
class UParisRainWeather : public UActorComponent {
    GENERATED_BODY()
public:
    void Advance(float Delta,bool Raining,int32 Quality);
    void ToggleSound();
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    float Intensity=0,Wetness=0,Exposure=1;
    bool bMuted=false;
    int32 VisibleDrops=0,VisibleSplashes=0;
private:
    void Initialize();
    void SampleSurfaces(const FVector& View);
    void UpdateGeometry(const FVector& View,int32 Quality);
    UPROPERTY() TObjectPtr<UProceduralMeshComponent> Streaks;
    UPROPERTY() TObjectPtr<UProceduralMeshComponent> Splashes;
    UPROPERTY() TObjectPtr<UAudioComponent> RainAudio;
    UPROPERTY() TObjectPtr<UAudioComponent> DripAudio;
    UPROPERTY() TObjectPtr<UMaterialParameterCollection> Collection;
    TMap<FIntPoint,FParisRainSurface> Surfaces;
    TArray<FParisRainSurface> ImpactSurfaces;
    TArray<int32> ImpactCycles;
    TArray<FVector> DropVertices,SplashVertices,DropNormals,SplashNormals;
    TArray<FVector2D> DropUV,SplashUV;
    TArray<FLinearColor> DropColors,SplashColors;
    double Elapsed=0,SampleElapsed=1;
    float TargetExposure=1;
    bool bInitialized=false;
    int32 LastQuality=-1;
};
