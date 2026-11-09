#pragma once
#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
class AParisTwinScene;
struct FHitResult;

void CreateParisMorris(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Source);
void SyncParisMorris(AParisTwinScene* Scene);
bool SelectParisMorrisHit(AParisTwinScene* Scene,const FHitResult& Hit);
void AddParisMorrisStats(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Report);
