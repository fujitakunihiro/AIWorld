#pragma once
#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
#include "ProceduralMeshComponent.h"

namespace AIWorld {
constexpr double Unit = 100.;
struct FMesh {
    TArray<FVector> Positions, Normals;
    TArray<FLinearColor> Colors;
    TArray<int32> Indices;
    void Append(const FMesh& Other, const FVector& Offset = FVector::ZeroVector);
};
struct FGrid {
    int32 Size = 0, Height = 0, Chunk = 32;
    TArray<uint8> Base, Blocks;
    TSet<int32> StaticHidden, Hidden;
    bool Inside(int32 X, int32 Y, int32 Z) const;
    int32 Index(int32 X, int32 Y, int32 Z) const;
    uint8 Get(int32 X, int32 Y, int32 Z, bool Mask = false) const;
    bool Load(const TSharedPtr<FJsonObject>& Json, FString& Error);
    bool Edit(const TSharedPtr<FJsonObject>& Json);
    void Restore(const TArray<TSharedPtr<FJsonValue>>& Edits);
};
TSharedPtr<FJsonObject> Parse(const FString& Text);
FString String(const TSharedPtr<FJsonObject>& J, const FString& Key);
double Number(const TSharedPtr<FJsonObject>& J, const FString& Key, double Fallback = 0);
TSharedPtr<FJsonObject> Object(const TSharedPtr<FJsonObject>& J, const FString& Key);
const TArray<TSharedPtr<FJsonValue>>& Array(const TSharedPtr<FJsonObject>& J, const FString& Key);
FVector Position(const TSharedPtr<FJsonObject>& J);
FLinearColor BlockColor(uint8 Block);
bool DecodeMesh(const TSharedPtr<FJsonObject>& Json, FMesh& Out);
void MeshChunk(const FGrid& Grid, int32 CX, int32 CZ, bool Classic, FMesh& Solid, FMesh& Water);
FString SpeedCommand(int32 Speed);
FString TextCommand(const FString& Text, const FString& Resident = TEXT(""));
FString EditCommand(int32 X, int32 Y, int32 Z, uint8 Block, uint8 Expected);
}
