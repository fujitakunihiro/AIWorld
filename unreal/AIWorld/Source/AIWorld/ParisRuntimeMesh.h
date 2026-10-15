#pragma once
#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

struct FParisMeshArrays {
    TArray<FVector> Positions,Normals;
    TArray<FLinearColor> Colors;
    TArray<int32> Indices;
};

// The source JSON remains available for auditing/legacy comparison. Binary
// payloads are validated once and decoded directly into native mesh arrays.
bool ValidateParisMeshBlob(const TSharedPtr<FJsonObject>& Metadata,const TArray<uint8>& Blob,FString& Error);
bool ReadParisMeshArrays(const TSharedPtr<FJsonObject>& Object,const TArray<uint8>& Blob,FParisMeshArrays& Out,FString& Error);
