#pragma once
#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
class AParisTwinScene;
struct FHitResult;
void CreateParisLuxury(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Source);
void SyncParisLuxury(AParisTwinScene* Scene);
bool IsParisFestivalEnabled(AParisTwinScene* Scene);
void SyncParisFestivalAppearance(AParisTwinScene* Scene);
void ToggleParisFestival(AParisTwinScene* Scene);
bool CycleParisDistrictView(AParisTwinScene* Scene);
bool SelectParisLuxuryHit(AParisTwinScene* Scene,const FHitResult& Hit);
void AddParisLuxuryStats(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Report);
