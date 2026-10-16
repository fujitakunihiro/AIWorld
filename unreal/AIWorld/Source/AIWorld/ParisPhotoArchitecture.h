#pragma once
#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
class AParisTwinScene;
class UStaticMesh;
TMap<FString,UStaticMesh*> LoadParisPhotoStreetMeshes();
void SyncParisPhotoStreetDetails(AParisTwinScene* Scene);
void CreateParisPhotoArchitecture(AParisTwinScene* Scene);
void SyncParisPhotoArchitecture(AParisTwinScene* Scene);
void AddParisPhotoDetailStats(const AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Report);
