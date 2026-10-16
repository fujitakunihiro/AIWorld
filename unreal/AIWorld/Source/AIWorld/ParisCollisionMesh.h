#pragma once
#include "CoreMinimal.h"
#include "ProceduralMeshComponent.h"
#include "ParisCollisionMesh.generated.h"

// Keep GIS query/physics data alive while the immutable visual uses UE's
// static draw path. Returning no proxy avoids allocating duplicate GPU data.
UCLASS()
class UParisCollisionMesh : public UProceduralMeshComponent {
    GENERATED_BODY()
public:
    void SetUsesVisualCache(bool Enabled);
    bool UsesVisualCache() const { return bUsesVisualCache; }
    virtual FPrimitiveSceneProxy* CreateSceneProxy() override;
private:
    bool bUsesVisualCache=false;
};
