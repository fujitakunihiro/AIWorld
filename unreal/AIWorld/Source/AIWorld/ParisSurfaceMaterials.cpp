#include "ParisDigitalTwin.h"
#include "ParisReference.h"
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
    const bool RiverDetail=bDetailedSurfaces&&DetailQuality>0&&FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal"))&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinProceduralSurfaces"))&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinLegacyWater"));
    if(Kind==TEXT("water")){
        if(RiverDetail&&IsParisSeineDressed()&&String(Feature,TEXT("id"))==TEXT("seine"))if(auto M=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisSeineWater")))return M;
        if(RiverDetail&&String(Feature,TEXT("id"))==TEXT("seine"))
            if(auto River=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_SeineRiver")))return River;
        return WaterMaterial.Get();
    }
    if(!bDetailedSurfaces||DetailQuality==0)return VertexMaterial.Get();
    if(IsParisLaneDressed()&&Kind==TEXT("path"))if(auto M=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisLanePaving")))return M;
    if(Kind==TEXT("park")&&FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal"))&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinProceduralSurfaces")))
        if(auto Grass=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisGrassPhotographic")))return Grass;
    if(Kind==TEXT("building")&&(bLevels||bIssues))return VertexMaterial.Get();
    if(Kind==TEXT("roof")&&bLevels)return VertexMaterial.Get();
    if(IsParisReferenceLook()&&(Kind==TEXT("facade_trim")||Kind==TEXT("facade_relief")))if(auto M=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisReferenceStone")))return M;
    if(Kind==TEXT("facade_trim")||Kind==TEXT("facade_relief"))return LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisCutStone.M_ParisCutStone"));
    if(Kind==TEXT("building")&&FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal"))&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoArchitecture"))&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinProceduralSurfaces")))
        for(const auto& ID:Array(Object(Feature,TEXT("properties")),TEXT("source_ids")))if(ID->AsString()==TEXT("osm/way/201611261")){
            if(bPhotoScanReady&&PhotoScanBodyMaterial&&!bFootprints)return PhotoScanBodyMaterial;
            if(auto Cathedral=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisCathedralStone")))return Cathedral;
        }
    if(Kind==TEXT("quay")&&RiverDetail)
        if(auto Quay=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisQuayWet")))return Quay;
    if(IsParisSeineDressed()&&Kind==TEXT("building"))if(auto M=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisSeineStone")))return M;
    if(IsParisReferenceLook()&&Kind==TEXT("building"))if(auto M=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisReferenceStone")))return M;
    if(Kind==TEXT("building")||Kind==TEXT("quay"))return StoneMaterial.Get();
    if(IsParisSeineDressed()&&(Kind==TEXT("roof")||Kind==TEXT("facade_roof")))if(auto M=LoadObject<UMaterialInterface>(nullptr,(Kind==TEXT("facade_roof")||String(Object(Feature,TEXT("properties")),TEXT("roof_material"))==TEXT("zinc"))?TEXT("/Game/Materials/M_ParisSeineZinc"):TEXT("/Game/Materials/M_ParisSeineSlate")))return M;
    if(Kind==TEXT("roof"))return String(Object(Feature,TEXT("properties")),TEXT("roof_material"))==TEXT("zinc")&&ZincMaterial?ZincMaterial.Get():SlateMaterial.Get();
    if(Kind==TEXT("facade_roof"))return ZincMaterial?ZincMaterial.Get():SlateMaterial.Get();
    if(Kind==TEXT("facade_glass"))return GlassMaterial?GlassMaterial.Get():VertexMaterial.Get();
    if(Kind==TEXT("facade_iron")||Kind==TEXT("facade_railing")||Kind==TEXT("facade_planter"))return IronMaterial?IronMaterial.Get():VertexMaterial.Get();
    if(Kind==TEXT("facade_wood")||Kind==TEXT("facade_joinery"))return WoodMaterial?WoodMaterial.Get():VertexMaterial.Get();
    if(Kind==TEXT("bridge"))return StoneMaterial.Get();
    const bool RoadDetail=FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal"))&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinProceduralSurfaces"))&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinLegacyRoads"));
    if(RoadDetail&&(Kind==TEXT("road")||Kind==TEXT("sidewalk")||Kind==TEXT("path"))){
        if(IsParisReferenceLook()&&Kind==TEXT("sidewalk"))if(auto M=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisReferenceSidewalk")))return M;
        const TCHAR* Path=Kind==TEXT("road")?TEXT("/Game/Materials/M_ParisRoadAsphalt"):Kind==TEXT("sidewalk")?TEXT("/Game/Materials/M_ParisRoadSidewalk"):TEXT("/Game/Materials/M_ParisRoadPaving");
        if(auto Material=LoadObject<UMaterialInterface>(nullptr,Path))return Material;
    }
    if(Kind==TEXT("path")||Kind==TEXT("sidewalk"))return PavingMaterial?PavingMaterial.Get():VertexMaterial.Get();
    if(Kind==TEXT("road")){
        if(FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal"))&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinProceduralSurfaces")))
            if(auto Asphalt=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisAsphaltPhotographic")))return Asphalt;
        return AsphaltMaterial?AsphaltMaterial.Get():VertexMaterial.Get();
    }
    return VertexMaterial.Get();
}
