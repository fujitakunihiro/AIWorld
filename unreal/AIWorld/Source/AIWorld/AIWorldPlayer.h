#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/Pawn.h"
#include "Dom/JsonObject.h"
#include "AIWorldPlayer.generated.h"
class AAIWorldScene;
class UCameraComponent;
class SAIWorldHUD;

UCLASS()
class AIWORLD_API AAIWorldCamera : public APawn {
    GENERATED_BODY()
public:
    AAIWorldCamera();
    virtual void Tick(float Delta) override;
    void Focus(const FVector& Position,double NewRadius);
    void Zoom(double Factor);
    FVector Target=FVector(4000,4000,900);
    double Radius=5200,Yaw=-135,Pitch=48;
private:
    UPROPERTY() TObjectPtr<UCameraComponent> Camera;
};
UCLASS()
class AIWORLD_API AAIWorldPlayer : public APlayerController {
    GENERATED_BODY()
public:
    virtual void BeginPlay() override;
    virtual void SetupInputComponent() override;
    virtual void Tick(float Delta) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    AAIWorldScene* World() const;
    AAIWorldCamera* View() const;
    void FocusCamp();void FocusParis();void FocusAll();
    void Select(const FString& ID,bool Follow=true);
    void FocusItem(const TSharedPtr<FJsonObject>& Item);
    void SendText(const FString& Text,bool Conversation);
    void SetEdit(int32 Mode,int32 Material=1);
    void Undo();
    void EditAccepted(const TSharedPtr<FJsonObject>& E);void EditRejected();
    bool InputBlocked() const;
    FString Detail() const;FString Summary() const;
    FString Selected;
    int32 EditMode=0,Material=1;
    bool bFollow=false;
private:
    TSharedPtr<SAIWorldHUD> HUD;
    TSharedPtr<FJsonObject> Pending,LastEdit;
    uint8 PendingOld=0,LastOld=0;bool bUndoing=false;
    void Click();void ZoomIn();void ZoomOut();
    bool TraceVoxel(FIntVector& Hit,FIntVector& Previous) const;
};
UCLASS()
class AIWORLD_API AAIWorldGameMode : public AGameModeBase {
    GENERATED_BODY()
public:
    AAIWorldGameMode();
    virtual void BeginPlay() override;
};
