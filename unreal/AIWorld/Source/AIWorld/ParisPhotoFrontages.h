#pragma once
#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
class AParisTwinScene;
void CreateParisPhotoFrontages(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Source);
void SyncParisPhotoFrontages(AParisTwinScene* Scene);
void AddParisFrontageStats(const AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Report);
