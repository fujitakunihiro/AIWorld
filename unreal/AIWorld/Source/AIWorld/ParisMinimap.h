#pragma once
#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
class AParisTwinScene;
class AHUD;
class UCanvas;
struct FParisMapRect {float X=0,Y=0,Size=0;bool IsValid()const{return Size>0;}bool Contains(const FVector2D& P)const{return IsValid()&&P.X>=X&&P.X<=X+Size+20&&P.Y>=Y&&P.Y<=Y+Size+65;}};
FParisMapRect ParisMinimapRect(AHUD* HUD,float Width,float Height);
FVector2D ParisMapPoint(const FVector& World,const FVector4& Bounds);
FVector ParisMapObserver(AParisTwinScene* Scene,FRotator& Direction,FString& Label);
void InitializeParisMinimap(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Source);
void DrawParisMinimap(AHUD* HUD,UCanvas* Canvas,AParisTwinScene* Scene);
void ToggleParisMinimap(AHUD* HUD);
void AddParisMinimapStats(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Report);
