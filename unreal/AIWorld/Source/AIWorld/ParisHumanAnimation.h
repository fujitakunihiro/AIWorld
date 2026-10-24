#pragma once
#include "CoreMinimal.h"
#include "Animation/AnimInstance.h"
#include "ParisHumanAnimation.generated.h"
class UAnimSequence;

// A native blend graph: idle <-> walk/run <-> seated idle. Run is optional
// so the crowd keeps its existing walking and cafe behavior.
// Inputs are copied to the proxy on the game thread; animation evaluation reads
// only the proxy, never the pedestrian simulation or its shared route data.
UCLASS(Transient)
class UParisHumanAnimation : public UAnimInstance {
    GENERATED_BODY()
public:
    UPROPERTY(Transient) TObjectPtr<UAnimSequence> Idle;
    UPROPERTY(Transient) TObjectPtr<UAnimSequence> Walk;
    UPROPERTY(Transient) TObjectPtr<UAnimSequence> Run;
    UPROPERTY(Transient) TObjectPtr<UAnimSequence> Sit;
    float SpeedCm=0,SeatAlpha=0,NominalSpeedCm=120,NominalRunSpeedCm=400;
    float RunStartSpeedCm=190,FullRunSpeedCm=300;
    int32 PersonIndex=INDEX_NONE;
protected:
    virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override;
    virtual void DestroyAnimInstanceProxy(FAnimInstanceProxy* Proxy) override;
};
