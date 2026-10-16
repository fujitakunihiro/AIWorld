#include "ParisRenderCache.h"
#include "ParisCollisionMesh.h"
#include "ProceduralMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/Actor.h"
#include "MeshDescription.h"
#include "StaticMeshAttributes.h"
#include "StaticMeshResources.h"
#include "Dom/JsonObject.h"

static const FName CacheTag(TEXT("ParisImmutableVisual"));

UStaticMeshComponent* FindParisRenderCache(const UProceduralMeshComponent* Source){
    if(Source)for(auto Child:Source->GetAttachChildren())
        if(Child->ComponentHasTag(CacheTag))return Cast<UStaticMeshComponent>(Child);
    return nullptr;
}

UStaticMeshComponent* BuildParisRenderCache(UProceduralMeshComponent* Source,UStaticMesh* Prebuilt){
    if(!Source||!Source->GetOwner())return nullptr;
    if(auto Existing=FindParisRenderCache(Source))return Existing;
    const auto Section=Source->GetProcMeshSection(0);
    if(!Section||Section->ProcVertexBuffer.IsEmpty()||Section->ProcIndexBuffer.IsEmpty())return nullptr;
    // GeometryScript / Nanite can remove tiny or degenerate roof triangles.
    // Keep the strict original-geometry contract: use the exact fast builder
    // whenever an offline asset's fallback topology differs from its GIS source.
    if(Prebuilt&&Prebuilt->GetNumTriangles(0)!=Section->ProcIndexBuffer.Num()/3){
        UE_LOG(LogTemp,Display,TEXT("PARIS_BAKE_EXACT_FALLBACK %s baked=%d source=%d"),*Prebuilt->GetName(),Prebuilt->GetNumTriangles(0),Section->ProcIndexBuffer.Num()/3);
        Prebuilt=nullptr;
    }
    UStaticMesh* Mesh=Prebuilt;
    if(!Mesh){
    FMeshDescription Description;FStaticMeshAttributes Attributes(Description);Attributes.Register();
    auto Positions=Attributes.GetVertexPositions();auto Normals=Attributes.GetVertexInstanceNormals();
    auto Tangents=Attributes.GetVertexInstanceTangents();auto Signs=Attributes.GetVertexInstanceBinormalSigns();
    auto Colors=Attributes.GetVertexInstanceColors();auto UVs=Attributes.GetVertexInstanceUVs();UVs.SetNumChannels(1);
    TArray<FVertexID> Vertices;Vertices.Reserve(Section->ProcVertexBuffer.Num());
    for(const auto& Vertex:Section->ProcVertexBuffer){auto ID=Description.CreateVertex();Positions[ID]=FVector3f(Vertex.Position);Vertices.Add(ID);}
    const auto Group=Description.CreatePolygonGroup();
    for(int32 I=0;I<Section->ProcIndexBuffer.Num();I+=3){
        TArray<FVertexInstanceID> Triangle;Triangle.Reserve(3);
        for(int32 K=0;K<3;K++){
            const int32 Index=Section->ProcIndexBuffer[I+K];if(!Vertices.IsValidIndex(Index))return nullptr;
            const auto& Vertex=Section->ProcVertexBuffer[Index];const auto ID=Description.CreateVertexInstance(Vertices[Index]);Triangle.Add(ID);
            Normals[ID]=FVector3f(Vertex.Normal);Tangents[ID]=FVector3f(Vertex.Tangent.TangentX);
            Signs[ID]=Vertex.Tangent.bFlipTangentY?-1.f:1.f;
            // UE's fast static-mesh builder writes ToFColorSRGB(), whereas
            // PMC stores its final colour bytes directly. Undo that encoding
            // here so the resulting GPU bytes exactly match the original.
            const FLinearColor Tint(Vertex.Color);Colors[ID]=FVector4f(Tint.R,Tint.G,Tint.B,Tint.A);
            UVs.Set(ID,0,FVector2f(Vertex.UV0));
        }
        Description.CreatePolygon(Group,Triangle);
    }
    Mesh=NewObject<UStaticMesh>(Source);Mesh->GetStaticMaterials().Add(FStaticMaterial(Source->GetMaterial(0)));
    UStaticMesh::FBuildMeshDescriptionsParams Params;Params.bFastBuild=true;Params.bBuildSimpleCollision=false;Params.bAllowCpuAccess=true;Params.bCommitMeshDescription=false;
    if(!Mesh->BuildFromMeshDescriptions({&Description},Params))return nullptr;
    }
    auto Cache=NewObject<UStaticMeshComponent>(Source->GetOwner());Source->GetOwner()->AddInstanceComponent(Cache);
    Cache->ComponentTags.Add(CacheTag);Cache->SetupAttachment(Source);Cache->SetMobility(Source->Mobility);Cache->SetStaticMesh(Mesh);
    if(Prebuilt)Cache->ComponentTags.Add(TEXT("ParisBakedVisual"));
    Cache->SetCollisionEnabled(ECollisionEnabled::NoCollision);Cache->SetCollisionResponseToAllChannels(ECR_Ignore);
    Cache->SetGenerateOverlapEvents(false);Cache->SetCanEverAffectNavigation(false);Cache->SetCastShadow(Source->CastShadow);
    Cache->SetCullDistance(Source->LDMaxDrawDistance);Cache->RegisterComponent();
    SyncParisRenderCache(Source,false);return Cache;
}

void SyncParisRenderCache(UProceduralMeshComponent* Source,bool DebugAppearance){
    if(auto Cache=FindParisRenderCache(Source)){
        // Preserve IsVisible() and all collision/selection semantics. In 5.8
        // HiddenInGame also makes IsVisible() false, so exclude the original
        // from render passes instead of changing its hidden state.
        Source->SetRenderInMainPass(DebugAppearance);Source->SetRenderInDepthPass(DebugAppearance);
        Source->SetCastShadow(DebugAppearance&&Cache->CastShadow);
        if(auto Collision=Cast<UParisCollisionMesh>(Source))Collision->SetUsesVisualCache(!DebugAppearance);
        Cache->SetVisibility(Source->IsVisible()&&!DebugAppearance);
        Cache->SetMaterial(0,Source->GetMaterial(0));
    }
}

void AddParisRenderCacheStats(const AActor* Scene,const TSharedPtr<FJsonObject>& Report){
    int32 Count=0,Triangles=0,Baked=0,DistanceFields=0,Cards=0,Nanite=0,PaletteErrors=0;double BoundsError=0;TArray<UProceduralMeshComponent*> Sources;Scene->GetComponents(Sources);
    for(auto Source:Sources)if(auto Cache=FindParisRenderCache(Source)){
        Count++;if(Cache->ComponentHasTag(TEXT("ParisBakedVisual")))Baked++;if(auto Data=Cache->GetStaticMesh()->GetRenderData())if(!Data->LODResources.IsEmpty()){
            const auto& LOD=Data->LODResources[0];Triangles+=LOD.GetNumTriangles();
            if(LOD.DistanceFieldData)DistanceFields++;if(LOD.CardRepresentationData)Cards++;
            if(Cache->GetStaticMesh()->HasValidNaniteData())Nanite++;
            if(Cache->ComponentHasTag(TEXT("ParisBakedVisual")))if(auto Section=Source->GetProcMeshSection(0)){
                FBox Box(ForceInit);TSet<FColor> Palette;for(const auto& V:Section->ProcVertexBuffer){Box+=V.Position;Palette.Add(V.Color);}
                const auto Bounds=Cache->GetStaticMesh()->GetBounds();BoundsError=FMath::Max(BoundsError,FMath::Max((Box.GetCenter()-Bounds.Origin).GetAbsMax(),(Box.GetExtent()-Bounds.BoxExtent).GetAbsMax()));
                const auto& Colors=LOD.VertexBuffers.ColorVertexBuffer;
                for(uint32 I=0;I<Colors.GetNumVertices();I+=FMath::Max(1u,Colors.GetNumVertices()/24))if(!Palette.Contains(Colors.VertexColor(I)))PaletteErrors++;
            }
        }
    }
    Report->SetNumberField(TEXT("render_cache_components"),Count);
    Report->SetNumberField(TEXT("render_cache_triangles"),Triangles);
    Report->SetNumberField(TEXT("baked_visual_components"),Baked);
    Report->SetNumberField(TEXT("distance_field_visual_components"),DistanceFields);
    Report->SetNumberField(TEXT("lumen_card_visual_components"),Cards);
    Report->SetNumberField(TEXT("nanite_visual_components"),Nanite);
    Report->SetNumberField(TEXT("baked_bounds_max_error_cm"),BoundsError);
    Report->SetNumberField(TEXT("baked_palette_mismatch_samples"),PaletteErrors);
    Report->SetStringField(TEXT("render_cache_recipe"),Baked?TEXT("static_gis_sdf_nanite_v3"):TEXT("exact_geometry_static_mesh_v1"));
}
