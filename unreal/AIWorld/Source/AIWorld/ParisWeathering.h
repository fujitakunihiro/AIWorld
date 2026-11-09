#pragma once
#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
class AParisTwinScene;
void CreateParisWeathering(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Source);
void SyncParisWeathering(AParisTwinScene* Scene);
void AddParisWeatheringStats(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Report);
