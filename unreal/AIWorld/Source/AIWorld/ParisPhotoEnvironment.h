#pragma once
#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
class UWorld;
class AParisTwinScene;
struct FParisMeshArrays;
void ConfigureParisPhotoEnvironment(UWorld* World,double OriginNGF);
void AddParisPhotoEnvironmentStats(UWorld* World,const TSharedPtr<FJsonObject>& Report);
bool ParisBridgeDeckHeight(const FParisMeshArrays& Mesh,const FVector2D& XY,double& Height);
void CreateParisPhotoCameras(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Data,const TArray<uint8>& GeometryBlob);
bool ActivateParisPhotoCamera(AParisTwinScene* Scene,FName Name);
