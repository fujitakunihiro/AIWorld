#pragma once
#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
class UStaticMesh;
class UMaterialInterface;

// Builds an authored prototype once. All mapped copies share this mesh and
// material through HISM; no external model or editor placement is required.
UStaticMesh* BuildParisStreetMesh(UObject* Outer,const TSharedPtr<FJsonObject>& Model,UMaterialInterface* Material);
