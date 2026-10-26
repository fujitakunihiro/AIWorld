#pragma once
#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
class AParisTwinScene;
void CreateParisRoadDetail(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Source);
void SyncParisRoadDetail(AParisTwinScene* Scene);
void AddParisRoadDetailStats(const AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Report);
