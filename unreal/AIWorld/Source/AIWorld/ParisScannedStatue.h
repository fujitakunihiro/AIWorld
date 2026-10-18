#pragma once
#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
class AParisTwinScene;
void CreateParisScannedStatue(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Architecture);
void SyncParisScannedStatue(AParisTwinScene* Scene,bool Detailed);
void AddParisScannedStatueStats(const AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Report);
