#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Dom/JsonObject.h"
#include "ParisSoundscape.generated.h"

class AParisTwinScene;
class AParisCruise;
class UAudioComponent;
class USoundWave;

struct FParisSoundAnchor { FVector Position=FVector::ZeroVector;FString SourceID; };
struct FParisWaterEdge { FVector A=FVector::ZeroVector,B=FVector::ZeroVector;FString SourceID; };

UCLASS()
class AParisSoundscape : public AActor {
    GENERATED_BODY()
public:
    AParisSoundscape();
    bool Initialize(AParisTwinScene* InScene,const TSharedPtr<FJsonObject>& Data);
    virtual void Tick(float Delta) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    void SetMuted(bool Muted);
    void Audition(int32 Kind=-1);
    bool NearestWater(const FVector& Listener,FParisSoundAnchor& Result) const;
    void AddStats(const TSharedPtr<FJsonObject>& Report) const;
    const TArray<FParisSoundAnchor>& CrowdAnchors() const {return Markets;}
    const TArray<FParisSoundAnchor>& PigeonAnchors() const {return BirdPlaces;}
    const FParisSoundAnchor& BellAnchor() const {return Bell;}
    bool bMuted=false;
    int32 ActiveVoices=0,BellEvents=0,PigeonEvents=0,SirenEvents=0,PreviewKind=-1;
private:
    UPROPERTY() TArray<TObjectPtr<USoundWave>> Waves;
    UPROPERTY() TArray<TObjectPtr<UAudioComponent>> Channels;
    UPROPERTY() TObjectPtr<UAudioComponent> Preview;
    TWeakObjectPtr<AParisTwinScene> Scene;
    TWeakObjectPtr<AParisCruise> Ship;
    TArray<FParisSoundAnchor> Markets,BirdPlaces;
    TArray<FParisWaterEdge> WaterEdges;
    FParisSoundAnchor Bell;
    FRandomStream Random{712901};
    double Elapsed=0,NextBell=10,NextBird=18,NextSiren=65,PreviewRemaining=0,SirenRemaining=0;
    int32 SirenVehicle=INDEX_NONE;
    FVector PreviousSirenPosition=FVector::ZeroVector;
    UAudioComponent* MakeChannel(const TCHAR* Name,USoundWave* Wave,float Inner,float Outer,bool Spatial=true);
    void UpdateLoop(int32 Channel,const FVector& Position,float Gain,bool Enabled,float Start=0);
};

void CreateParisSoundscape(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Data);
void SetParisSoundscapeMuted(UWorld* World,bool Muted);
void AuditionParisSoundscape(UWorld* World);
void AddParisSoundscapeStats(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Report);
