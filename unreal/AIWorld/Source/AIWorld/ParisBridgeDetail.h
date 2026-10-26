#pragma once
#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
class AParisTwinScene;
class UPrimitiveComponent;
void CreateParisBridgeDetail(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Source);
void SyncParisBridgeDetail(AParisTwinScene* Scene);
void AddParisBridgeDetailStats(const AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Report);
bool ParisBridgeSurfaceHeight(const AParisTwinScene* Scene,const FVector& Position,double& Height);
bool ParisBridgeVisualHeight(UWorld* World,const FVector& Position,double& Height);
FString ParisBridgeHitSource(const UPrimitiveComponent* Component);
