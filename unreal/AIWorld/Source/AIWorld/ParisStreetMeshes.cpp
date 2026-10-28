#include "ParisStreetMeshes.h"
#include "WorldProtocol.h"
#include "Engine/StaticMesh.h"
#include "MeshDescription.h"
#include "StaticMeshAttributes.h"
#include "PhysicsEngine/BodySetup.h"
using namespace AIWorld;

UStaticMesh* BuildParisStreetMesh(UObject* Outer,const TSharedPtr<FJsonObject>& Model,UMaterialInterface* Material) {
    const auto& Points=Array(Model,TEXT("positions_cm"));
    const auto& Normals=Array(Model,TEXT("normals"));
    const auto& Indices=Array(Model,TEXT("indices"));
    const auto& Palette=Array(Model,TEXT("vertex_colors"));
    const auto& SourceUV=Array(Model,TEXT("uv0"));
    if(Points.IsEmpty()||Points.Num()>100000||Normals.Num()!=Points.Num()||Indices.IsEmpty()||Indices.Num()%3)return nullptr;
    if(!Palette.IsEmpty()&&Palette.Num()!=Points.Num())return nullptr;
    if(!SourceUV.IsEmpty()&&SourceUV.Num()!=Points.Num())return nullptr;
    TArray<FVector2f> InputUV;InputUV.Reserve(SourceUV.Num());
    for(const auto& Value:SourceUV){if(!Value.IsValid()||Value->Type!=EJson::Array)return nullptr;const auto& U=Value->AsArray();double X,Y;if(U.Num()!=2||!U[0]->TryGetNumber(X)||!U[1]->TryGetNumber(Y)||!FMath::IsFinite(X)||!FMath::IsFinite(Y))return nullptr;InputUV.Emplace(float(X),float(Y));}
    FMeshDescription Description;FStaticMeshAttributes Attributes(Description);Attributes.Register();
    auto Positions=Attributes.GetVertexPositions();auto VertexNormals=Attributes.GetVertexInstanceNormals();
    auto Colors=Attributes.GetVertexInstanceColors();auto UVs=Attributes.GetVertexInstanceUVs();UVs.SetNumChannels(1);
    const FLinearColor Color(FColor::FromHex(String(Model,TEXT("color"))));
    TArray<FVertexID> Vertices;
    for(const auto& V:Points){const auto& P=V->AsArray();if(P.Num()!=3)return nullptr;FVector3f Position(P[0]->AsNumber(),P[1]->AsNumber(),P[2]->AsNumber());if(Position.ContainsNaN())return nullptr;auto ID=Description.CreateVertex();Positions[ID]=Position;Vertices.Add(ID);}
    const auto Group=Description.CreatePolygonGroup();
    for(int32 I=0;I<Indices.Num();I+=3){TArray<FVertexInstanceID> Triangle;
        for(int32 K=0;K<3;K++){const double Value=Indices[I+K]->AsNumber();if(Value<0||Value>=Vertices.Num()||FMath::FloorToDouble(Value)!=Value)return nullptr;const int32 Index=Value;const auto& N=Normals[Index]->AsArray();if(N.Num()!=3)return nullptr;const auto ID=Description.CreateVertexInstance(Vertices[Index]);Triangle.Add(ID);VertexNormals[ID]=FVector3f(N[0]->AsNumber(),N[1]->AsNumber(),N[2]->AsNumber());const FLinearColor Tint=Palette.IsEmpty()?Color:FLinearColor(FColor::FromHex(Palette[Index]->AsString()));Colors[ID]=FVector4f(Tint.R,Tint.G,Tint.B,Tint.A);UVs.Set(ID,0,InputUV.IsEmpty()?FVector2f::ZeroVector:InputUV[Index]);}
        Description.CreatePolygon(Group,Triangle);
    }
    auto Mesh=NewObject<UStaticMesh>(Outer);Mesh->GetStaticMaterials().Add(FStaticMaterial(Material));
    Mesh->CreateBodySetup();Mesh->GetBodySetup()->CollisionTraceFlag=CTF_UseSimpleAsComplex;
    UStaticMesh::FBuildMeshDescriptionsParams Params;Params.bFastBuild=true;Params.bBuildSimpleCollision=true;Params.bAllowCpuAccess=true;
    const TArray<const FMeshDescription*> Descriptions{&Description};if(!Mesh->BuildFromMeshDescriptions(Descriptions,Params))return nullptr;
    // These explicitly labelled proxy objects use cheap box picking/obstacles;
    // complex cursor traces must use the same proxy instead of missing them.
    Mesh->GetBodySetup()->CollisionTraceFlag=CTF_UseSimpleAsComplex;
    return Mesh;
}
