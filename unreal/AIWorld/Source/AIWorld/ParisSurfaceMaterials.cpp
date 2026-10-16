#include "ParisDigitalTwin.h"
#include "WorldProtocol.h"
#include "Materials/MaterialInterface.h"
#include "EngineUtils.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
using namespace AIWorld;

void AParisTwinController::ToggleSurfaces() {
    for(TActorIterator<AParisTwinScene> It(GetWorld());It;++It)It->ToggleSurfaces();
}

void AParisTwinScene::ToggleSurfaces() {
    bDetailedSurfaces=!bDetailedSurfaces;
    RefreshAppearance();
}

UMaterialInterface* AParisTwinScene::SurfaceMaterialFor(const TSharedPtr<FJsonObject>& Feature) const {
    const FString Kind=String(Feature,TEXT("kind"));
    if(Kind==TEXT("water"))return WaterMaterial.Get();
    if(!bDetailedSurfaces||DetailQuality==0)return VertexMaterial.Get();
    if(Kind==TEXT("park")&&FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal"))&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinProceduralSurfaces")))
        if(auto Grass=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisGrassPhotographic")))return Grass;
    if(Kind==TEXT("building")&&(bLevels||bIssues))return VertexMaterial.Get();
    if(Kind==TEXT("roof")&&bLevels)return VertexMaterial.Get();
    if(Kind==TEXT("facade_trim")||Kind==TEXT("facade_relief"))return LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisCutStone.M_ParisCutStone"));
    if(Kind==TEXT("building")&&FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal"))&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoArchitecture"))&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinProceduralSurfaces")))
        for(const auto& ID:Array(Object(Feature,TEXT("properties")),TEXT("source_ids")))if(ID->AsString()==TEXT("osm/way/201611261"))
            if(auto Cathedral=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisCathedralStone")))return Cathedral;
    if(Kind==TEXT("building")||Kind==TEXT("quay"))return StoneMaterial.Get();
    if(Kind==TEXT("roof"))return String(Object(Feature,TEXT("properties")),TEXT("roof_material"))==TEXT("zinc")&&ZincMaterial?ZincMaterial.Get():SlateMaterial.Get();
    if(Kind==TEXT("facade_roof"))return ZincMaterial?ZincMaterial.Get():SlateMaterial.Get();
    if(Kind==TEXT("facade_glass"))return GlassMaterial?GlassMaterial.Get():VertexMaterial.Get();
    if(Kind==TEXT("facade_iron")||Kind==TEXT("facade_railing")||Kind==TEXT("facade_planter"))return IronMaterial?IronMaterial.Get():VertexMaterial.Get();
    if(Kind==TEXT("facade_wood")||Kind==TEXT("facade_joinery"))return WoodMaterial?WoodMaterial.Get():VertexMaterial.Get();
    if(Kind==TEXT("bridge"))return StoneMaterial.Get();
    if(Kind==TEXT("path")||Kind==TEXT("sidewalk"))return PavingMaterial?PavingMaterial.Get():VertexMaterial.Get();
    if(Kind==TEXT("road")){
        if(FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal"))&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinProceduralSurfaces")))
            if(auto Asphalt=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisAsphaltPhotographic")))return Asphalt;
        return AsphaltMaterial?AsphaltMaterial.Get():VertexMaterial.Get();
    }
    return VertexMaterial.Get();
}
