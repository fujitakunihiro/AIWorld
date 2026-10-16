#pragma once
#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
class AParisTwinScene;
void CreateParisGroundDisplay(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Source);
void SyncParisGroundDisplay(AParisTwinScene* Scene);
