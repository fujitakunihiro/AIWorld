#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "ParisWalker.generated.h"
class UCameraComponent;
class USpringArmComponent;
class UStaticMeshComponent;
class AParisPedestrianCrowd;
class AParisTwinScene;

UCLASS()
class AParisWalker : public ACharacter {
    GENERATED_BODY()
public:
    AParisWalker();
    virtual void Tick(float Delta) override;
    void InitializeAppearance(AParisPedestrianCrowd* Crowd);
    void ActivateAt(const FVector& Centre,const FRotator& Look,bool ThirdPerson);
    void Suspend();
    void ToggleView();
    void RecoverToSafe();
    bool bThirdPerson=false;
    int32 Recoveries=0;
    FVector LastSafe=FVector::ZeroVector;
    UPROPERTY() TObjectPtr<AParisTwinScene> Scene;
    UPROPERTY() TObjectPtr<UCameraComponent> FirstCamera;
    UPROPERTY() TObjectPtr<UCameraComponent> ThirdCamera;
    UPROPERTY() TObjectPtr<USpringArmComponent> CameraArm;
private:
    UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> Appearance;
    double Phase=0;
};
