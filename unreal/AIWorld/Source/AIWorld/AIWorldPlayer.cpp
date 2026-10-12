#include "AIWorldPlayer.h"
#include "AIWorldScene.h"
#include "AIWorldResident.h"
#include "SAIWorldHUD.h"
#include "WorldProtocol.h"
#include "Camera/CameraComponent.h"
#include "Components/InputComponent.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "EngineUtils.h"
#include "DrawDebugHelpers.h"
using namespace AIWorld;

AAIWorldGameMode::AAIWorldGameMode(){PlayerControllerClass=AAIWorldPlayer::StaticClass();DefaultPawnClass=AAIWorldCamera::StaticClass();}
void AAIWorldGameMode::BeginPlay(){Super::BeginPlay();GetWorld()->SpawnActor<AAIWorldScene>();}
AAIWorldCamera::AAIWorldCamera(){PrimaryActorTick.bCanEverTick=true;RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("Root"));Camera=CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));Camera->SetupAttachment(RootComponent);Camera->FieldOfView=48;}
void AAIWorldCamera::Focus(const FVector& P,double R){Target=P;Radius=R;}
void AAIWorldCamera::Zoom(double F){Radius=FMath::Clamp(Radius*F,350.,65000.);}
void AAIWorldCamera::Tick(float Delta){
    Super::Tick(Delta);auto PC=Cast<AAIWorldPlayer>(GetController());
    if(PC && !PC->InputBlocked()) {
        float DX=0,DY=0;PC->GetInputMouseDelta(DX,DY);
        if(PC->IsInputKeyDown(EKeys::RightMouseButton)){Yaw+=DX*.28;Pitch=FMath::Clamp(Pitch+DY*.28,12.,80.);}
        const FVector Forward(FMath::Cos(FMath::DegreesToRadians(Yaw)),FMath::Sin(FMath::DegreesToRadians(Yaw)),0),Right(-Forward.Y,Forward.X,0);
        FVector Move=FVector::ZeroVector;
        if(PC->IsInputKeyDown(EKeys::W)||PC->IsInputKeyDown(EKeys::Up))Move-=Forward;
        if(PC->IsInputKeyDown(EKeys::S)||PC->IsInputKeyDown(EKeys::Down))Move+=Forward;
        if(PC->IsInputKeyDown(EKeys::A)||PC->IsInputKeyDown(EKeys::Left))Move-=Right;
        if(PC->IsInputKeyDown(EKeys::D)||PC->IsInputKeyDown(EKeys::Right))Move+=Right;
        if(PC->IsInputKeyDown(EKeys::MiddleMouseButton))Move=(-Right*DX+Forward*DY)*.04;
        if(!Move.IsNearlyZero()){Target+=Move*Radius*Delta*(PC->IsInputKeyDown(EKeys::LeftShift)?1.5:.45);PC->bFollow=false;}
    }
    const double A=FMath::DegreesToRadians(Yaw),B=FMath::DegreesToRadians(Pitch);
    const FVector Location=Target+FVector(FMath::Cos(A)*FMath::Cos(B),FMath::Sin(A)*FMath::Cos(B),FMath::Sin(B))*Radius;
    Camera->SetWorldLocation(Location);Camera->SetWorldRotation((Target-Location).Rotation());
}
void AAIWorldPlayer::BeginPlay(){Super::BeginPlay();bShowMouseCursor=true;FInputModeGameAndUI Mode;Mode.SetHideCursorDuringCapture(false);Mode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);SetInputMode(Mode);
    if(GEngine&&GEngine->GameViewport){SAssignNew(HUD,SAIWorldHUD).Owner(this);GEngine->GameViewport->AddViewportWidgetContent(HUD.ToSharedRef(),10);}
}
void AAIWorldPlayer::EndPlay(const EEndPlayReason::Type Reason){if(HUD&&GEngine&&GEngine->GameViewport)GEngine->GameViewport->RemoveViewportWidgetContent(HUD.ToSharedRef());HUD.Reset();Super::EndPlay(Reason);}
void AAIWorldPlayer::SetupInputComponent(){Super::SetupInputComponent();InputComponent->BindKey(EKeys::LeftMouseButton,IE_Pressed,this,&AAIWorldPlayer::Click);InputComponent->BindKey(EKeys::MouseScrollUp,IE_Pressed,this,&AAIWorldPlayer::ZoomIn);InputComponent->BindKey(EKeys::MouseScrollDown,IE_Pressed,this,&AAIWorldPlayer::ZoomOut);InputComponent->BindKey(EKeys::Home,IE_Pressed,this,&AAIWorldPlayer::FocusAll);InputComponent->BindKey(EKeys::V,IE_Pressed,this,&AAIWorldPlayer::FocusCamp);InputComponent->BindKey(EKeys::P,IE_Pressed,this,&AAIWorldPlayer::FocusParis);}
AAIWorldScene* AAIWorldPlayer::World() const {for(TActorIterator<AAIWorldScene> It(GetWorld());It;++It)return *It;return nullptr;}
AAIWorldCamera* AAIWorldPlayer::View() const{return Cast<AAIWorldCamera>(GetPawn());}
bool AAIWorldPlayer::InputBlocked() const{return HUD&&HUD->BlocksWorldInput();}
void AAIWorldPlayer::FocusCamp(){if(auto W=World())if(auto C=View()){C->Focus(Position(Object(W->Village,TEXT("camp"))),4500);bFollow=false;}}
void AAIWorldPlayer::FocusParis(){if(auto W=World())if(auto C=View()){C->Focus(FVector(W->Grid.Size*50,W->Grid.Size*50,1400),W->Grid.Size*127);C->Yaw=-135;bFollow=false;}}
void AAIWorldPlayer::FocusAll(){if(auto W=World())if(auto C=View()){C->Focus(FVector(W->Grid.Size*50,W->Grid.Size*50,800),W->Grid.Size*125);bFollow=false;}}
void AAIWorldPlayer::Select(const FString& ID,bool Follow){Selected=ID;bFollow=Follow;auto W=World();if(!W)return;for(const auto& P:W->People())P.Value->Select(P.Key==ID);if(Follow)if(auto R=W->Resident(ID))if(auto C=View())C->Focus(Position(Object(R,TEXT("position")))+FVector(0,0,65),850);W->RefreshPresentation();if(HUD)HUD->ShowResident();}
void AAIWorldPlayer::FocusItem(const TSharedPtr<FJsonObject>& Item){auto W=World();if(!W||!Item)return;const auto& IDs=Array(Item,TEXT("residentIds"));if(IDs.Num()){Select(IDs[0]->AsString());return;}const FString ID=String(Item,TEXT("buildingId"));for(const auto& V:Array(W->Village,TEXT("huts"))){auto H=V->AsObject();if(String(H,TEXT("id"))==ID){if(auto C=View())C->Focus(Position(H)+FVector(200,200,200),1600);bFollow=false;return;}}
    auto P=Object(Item,TEXT("position"));if(!P)P=Object(Item,TEXT("location"));if(P&&View()){View()->Focus(Position(P),1800);bFollow=false;}
}
void AAIWorldPlayer::SendText(const FString& Text,bool Conversation){auto W=World();if(!W)return;FString Clean=Text.TrimStartAndEnd();if(Clean.IsEmpty())return;if(Clean.Len()>(Conversation?300:500)){W->Reply=TEXT("文章が長すぎます。");return;}if(Conversation&&Selected.IsEmpty()){W->Reply=TEXT("話しかける住民を選んでください。");return;}W->Reply=TEXT("送信しています…");W->Send(TextCommand(Clean,Conversation?Selected:TEXT("")));}
void AAIWorldPlayer::SetEdit(int32 Mode,int32 Block){EditMode=Mode;Material=Block;bFollow=false;if(auto W=World())W->SetClassic(Mode!=0||(HUD&&HUD->ClassicPreferred()));}
void AAIWorldPlayer::ZoomIn(){if(!InputBlocked()&&View())View()->Zoom(.88);}
void AAIWorldPlayer::ZoomOut(){if(!InputBlocked()&&View())View()->Zoom(1.14);}
bool AAIWorldPlayer::TraceVoxel(FIntVector& Hit,FIntVector& Prev) const {
    auto W=World();if(!W||!W->bReady)return false;FVector Origin,Direction;if(!DeprojectMousePositionToWorld(Origin,Direction))return false;
    // Exact voxel DDA, independent of rendering and collision meshes.
    const FVector O(Origin.X/Unit,Origin.Z/Unit,Origin.Y/Unit),D(Direction.X,Direction.Z,Direction.Y);
    double Entry=0,Exit=1000;const double Bounds[]={double(W->Grid.Size),double(W->Grid.Height),double(W->Grid.Size)};
    for(int32 I=0;I<3;I++){if(FMath::Abs(D[I])<1.e-8){if(O[I]<0||O[I]>=Bounds[I])return false;continue;}double A=(0-O[I])/D[I],B=(Bounds[I]-O[I])/D[I];if(A>B)Swap(A,B);Entry=FMath::Max(Entry,A);Exit=FMath::Min(Exit,B);if(Entry>Exit)return false;}
    FVector At=O+D*(Entry+1.e-5);FIntVector Cell(FMath::FloorToInt(At.X),FMath::FloorToInt(At.Y),FMath::FloorToInt(At.Z));FIntVector Step;FVector TMax,TDelta;
    for(int32 I=0;I<3;I++){Step[I]=D[I]>=0?1:-1;TDelta[I]=FMath::Abs(D[I])<1.e-8?1.e30:FMath::Abs(1./D[I]);TMax[I]=FMath::Abs(D[I])<1.e-8?1.e30:Entry+((Cell[I]+(Step[I]>0?1:0)-At[I])/D[I]);}
    Prev=Cell;for(int32 N=0;N<2048&&W->Grid.Inside(Cell.X,Cell.Y,Cell.Z);N++){const uint8 B=W->Grid.Get(Cell.X,Cell.Y,Cell.Z);if(B&&B!=7){Hit=Cell;return true;}int32 Axis=TMax.X<TMax.Y?(TMax.X<TMax.Z?0:2):(TMax.Y<TMax.Z?1:2);if(TMax[Axis]>Exit)break;Prev=Cell;Cell[Axis]+=Step[Axis];TMax[Axis]+=TDelta[Axis];}return false;
}
void AAIWorldPlayer::Click(){if(InputBlocked())return;auto W=World();if(!W||!W->bConnected)return;
    if(EditMode==0){float MX,MY;GetMousePosition(MX,MY);double Best=24;FString ID;
        for(const auto& P:W->People()){FVector2D Screen;if(ProjectWorldLocationToScreen(P.Value->GetActorLocation()+FVector(0,0,90),Screen)){const double Distance=(Screen-FVector2D(MX,MY)).Size();if(Distance<Best){Best=Distance;ID=P.Key;}}}if(!ID.IsEmpty())Select(ID);return;}
    if(Pending){W->Reply=TEXT("前の編集の保存を待っています。");return;}FIntVector Hit,Prev;if(!TraceVoxel(Hit,Prev))return;const auto P=EditMode<0?Hit:Prev;if(!W->Grid.Inside(P.X,P.Y,P.Z))return;
    PendingOld=W->Grid.Get(P.X,P.Y,P.Z);const uint8 B=EditMode<0?0:Material;const FString Request=EditCommand(P.X,P.Y,P.Z,B,PendingOld);Pending=Parse(Request);bUndoing=false;W->Send(Request);
}
void AAIWorldPlayer::EditAccepted(const TSharedPtr<FJsonObject>& E){if(!Pending)return;for(const auto& K:{TEXT("x"),TEXT("y"),TEXT("z"),TEXT("block")})if(Number(E,K)!=Number(Pending,K))return;if(bUndoing)LastEdit.Reset();else{LastEdit=E;LastOld=PendingOld;}Pending.Reset();bUndoing=false;}
void AAIWorldPlayer::EditRejected(){Pending.Reset();bUndoing=false;}
void AAIWorldPlayer::Undo(){auto W=World();if(!W||!W->bConnected||!LastEdit||Pending)return;const int32 X=Number(LastEdit,TEXT("x")),Y=Number(LastEdit,TEXT("y")),Z=Number(LastEdit,TEXT("z"));const FString Command=EditCommand(X,Y,Z,LastOld,Number(LastEdit,TEXT("block")));Pending=Parse(Command);bUndoing=true;W->Send(Command);}
void AAIWorldPlayer::Tick(float Delta){Super::Tick(Delta);auto W=World();if(!W)return;if(bFollow)if(auto R=W->Resident(Selected))if(View())View()->Target=FMath::VInterpTo(View()->Target,Position(Object(R,TEXT("position")))+FVector(0,0,65),Delta,8);
    if(EditMode!=0&&!InputBlocked()){FIntVector Hit,Prev;if(TraceVoxel(Hit,Prev)){const auto P=EditMode<0?Hit:Prev;DrawDebugBox(GetWorld(),FVector(P.X+.5,P.Z+.5,P.Y+.5)*Unit,FVector(50),EditMode<0?FColor::Red:FColor::Yellow,false,-1,0,2);}}
}
FString AAIWorldPlayer::Summary() const {auto W=World();if(!W)return TEXT("AI WORLD · Unreal Engine");auto R=Object(W->Village,TEXT("resources"));const int32 Minute=FMath::FloorToInt(W->Time);return FString::Printf(TEXT("AI WORLD   |   %d日 %02d:%02d   |   %d人   食料 %.0f   木材 %.0f   石材 %.0f   |   %d×"),Minute/1440+1,Minute/60%24,Minute%60,Array(W->Village,TEXT("residents")).Num(),Number(R,TEXT("food")),Number(R,TEXT("wood")),Number(R,TEXT("stone")),W->Speed);}
FString AAIWorldPlayer::Detail() const {auto W=World();auto R=W?W->Resident(Selected):nullptr;if(!R)return TEXT("住民をクリックすると、目標・判断理由・記憶を確認できます。");
    FString T=String(R,TEXT("name"))+TEXT("  ·  ")+String(R,TEXT("job"))+TEXT("\n")+String(R,TEXT("personality"));
    T+=FString::Printf(TEXT("\n体力 %.0f  元気 %.0f  空腹 %.0f\n\n目標: %s\n行動: %s\n理由: %s\n"),Number(R,TEXT("health")),Number(R,TEXT("energy")),Number(R,TEXT("hunger")),*String(R,TEXT("goal")),*String(R,TEXT("action")),*String(R,TEXT("reason")));
    const auto Inv=Object(R,TEXT("inventory"));T+=FString::Printf(TEXT("運搬中: 食料 %.0f / 木材 %.0f / 石材 %.0f\n"),Number(Inv,TEXT("food")),Number(Inv,TEXT("wood")),Number(Inv,TEXT("stone")));
    auto AI=Object(R,TEXT("ai"));for(const auto& V:Array(W->Village,TEXT("tasks"))){auto Task=V->AsObject();if(String(Task,TEXT("id"))==String(AI,TEXT("taskId")))T+=FString::Printf(TEXT("現在の仕事: %s · %s\n進捗: %.0f / %.0f\n"),*String(Task,TEXT("title")),*String(Task,TEXT("status")),Number(Task,TEXT("progress")),Number(Task,TEXT("total")));}
    T+=TEXT("\n候補の実際の評価\n");for(const auto& V:Array(AI,TEXT("scores"))){auto S=V->AsObject();T+=FString::Printf(TEXT("%s: %.1f  %s\n"),*String(S,TEXT("action")),Number(S,TEXT("score")),*String(S,TEXT("reason")));}
    T+=TEXT("\n最近の行動\n");for(const auto& V:Array(AI,TEXT("history")))T+=String(V->AsObject(),TEXT("text"))+TEXT("\n");
    T+=TEXT("\n記憶\n")+String(R,TEXT("memorySummary"))+TEXT("\n");for(const auto& V:Array(R,TEXT("memories")))T+=V->AsString()+TEXT("\n");
    for(const auto& V:Array(R,TEXT("conversations"))){auto C=V->AsObject();T+=TEXT("\nあなた: ")+String(C,TEXT("question"))+TEXT("\n")+String(R,TEXT("name"))+TEXT(": ")+String(C,TEXT("answer"))+TEXT("\n");}return T;
}
