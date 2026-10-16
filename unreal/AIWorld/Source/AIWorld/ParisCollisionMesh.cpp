#include "ParisCollisionMesh.h"

void UParisCollisionMesh::SetUsesVisualCache(bool Enabled){
    if(bUsesVisualCache!=Enabled){bUsesVisualCache=Enabled;MarkRenderStateDirty();}
}
FPrimitiveSceneProxy* UParisCollisionMesh::CreateSceneProxy(){
    return bUsesVisualCache?nullptr:Super::CreateSceneProxy();
}
