#pragma once
#include "CoreMinimal.h"

class UProceduralMeshComponent;
class UStaticMeshComponent;
class UStaticMesh;
class AActor;
class FJsonObject;

// Immutable visual copy only. The original GIS component owns collision,
// source selection and editable accuracy colours throughout its lifetime.
UStaticMeshComponent* BuildParisRenderCache(UProceduralMeshComponent* Source,UStaticMesh* Prebuilt=nullptr);
void SyncParisRenderCache(UProceduralMeshComponent* Source,bool DebugAppearance);
UStaticMeshComponent* FindParisRenderCache(const UProceduralMeshComponent* Source);
void AddParisRenderCacheStats(const AActor* Scene,const TSharedPtr<FJsonObject>& Report);
