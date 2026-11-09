#pragma once
#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
class AParisTwinScene;
bool IsParisReferenceLook();
bool IsParisSeineLook();
bool IsParisSeineDressed();
bool IsParisLaneLook();
bool IsParisLaneDressed();
bool ParisLaneReplacesShop(const FString& ID);
bool SelectParisLaneHit(AParisTwinScene* Scene,const struct FHitResult& Hit);
FVector ParisReferenceDetailCentre(const FVector& Fallback);
void CreateParisReference(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Source);
void SyncParisReference(AParisTwinScene* Scene);
void AddParisReferenceStats(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Report);
