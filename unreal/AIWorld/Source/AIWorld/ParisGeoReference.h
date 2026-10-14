#pragma once
#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

// Conventional EPSG:2154 / GRS80 Lambert-93. No vertical datum conversion.
// Must consume the same projected origin as the Python/PROJ exporter.
struct FParisGeoReference {
    FVector2D OriginProjected=FVector2D::ZeroVector;
    bool Load(const TSharedPtr<FJsonObject>& Metadata);
    FVector2D WGS84FromUE(const FVector& Point) const;
    FVector ToUE(const FVector2D& LongitudeLatitude) const;
    FVector2D ProjectedFromUE(const FVector& Point) const;
    static FVector2D Project(const FVector2D& LongitudeLatitude);
    static FVector2D Unproject(const FVector2D& EastNorth);
};
