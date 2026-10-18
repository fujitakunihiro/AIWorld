#include "ParisScannedStatue.h"
#include "ParisDigitalTwin.h"
#include "WorldProtocol.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/Texture2D.h"
#include "Materials/MaterialInterface.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
using namespace AIWorld;

void CreateParisScannedStatue(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Architecture){
    if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoNCStatues")))return;
    FString Text;TSharedPtr<FJsonObject> Data;
    if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("Data/paris-notredame-statue.json")))||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Data)||!Data)return;
    // This optional asset is not covered by the project's code license or the
    // separate CC BY facade. Fail closed if identity, NC scope or frame differ.
    if(String(Data,TEXT("format"))!=TEXT("paris_noncommercial_scanned_statue_v1")||String(Data,TEXT("uid"))!=TEXT("b5bbdc379daa4ee19e3775bb179dbcc1")||String(Data,TEXT("license"))!=TEXT("CC-BY-NC-4.0")||String(Data,TEXT("use_scope"))!=TEXT("personal_noncommercial")||String(Data,TEXT("source_id"))!=TEXT("osm/way/201611261"))return;
    const auto Registration=Object(Data,TEXT("registration"));
    // +across is geographic north/viewer-left. Never accept the old mirrored
    // registration or place this saint on the southern/Sainte-Anne portal.
    const double Across=Number(Registration,TEXT("center_x_m"));
    if(Across<12||Across>16||FMath::Abs(Number(Registration,TEXT("handedness_determinant"))+1)>.0001)return;
    for(const FString Field:{TEXT("front_cm"),TEXT("across"),TEXT("depth")}){
        const auto& A=Array(Object(Architecture,TEXT("local_frame")),*Field);const auto& B=Array(Object(Data,TEXT("local_frame")),*Field);
        if(A.Num()!=3||B.Num()!=3)return;
        for(int32 I=0;I<3;I++)if(!FMath::IsFinite(B[I]->AsNumber())||FMath::Abs(A[I]->AsNumber()-B[I]->AsNumber())>.0001)return;
    }
    const FString Prefix=TEXT("/Game/ParisPhotoreal/NotreDameStatues/");
    const FString MeshPath=String(Data,TEXT("asset")),MaterialPath=String(Data,TEXT("surface_material")),TexturePath=String(Data,TEXT("texture_asset"));
    if(!MeshPath.StartsWith(Prefix)||!MaterialPath.StartsWith(Prefix)||!TexturePath.StartsWith(Prefix))return;
    auto Mesh=LoadObject<UStaticMesh>(nullptr,*MeshPath);auto Material=LoadObject<UMaterialInterface>(nullptr,*MaterialPath);
    auto Texture=LoadObject<UTexture2D>(nullptr,*TexturePath);
    if(!Mesh||!Material||!Texture){UE_LOG(LogTemp,Warning,TEXT("Optional NC sculpture unavailable; retaining authored fallback"));return;}
    auto Part=NewObject<UStaticMeshComponent>(Scene);Scene->AddInstanceComponent(Part);Part->SetupAttachment(Scene->GetRootComponent());
    Part->SetStaticMesh(Mesh);Part->SetMaterial(0,Material);
    // Vertices are already UE centimetres in the shared GIS frame.
    Part->ComponentTags.Add(TEXT("ParisScannedVirgin"));Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);Part->SetCanEverAffectNavigation(false);Part->SetCullDistance(45000);Part->RegisterComponent();
}

void SyncParisScannedStatue(AParisTwinScene* Scene,bool Detailed){
    TArray<UStaticMeshComponent*> Parts;Scene->GetComponents(Parts);bool Ready=false;
    for(auto Part:Parts)if(Part->ComponentHasTag(TEXT("ParisScannedVirgin")))Ready|=Part->GetStaticMesh()!=nullptr;
    const bool Visible=Detailed&&Scene->bDetailedSurfaces&&Ready;
    for(auto Part:Parts){
        if(Part->ComponentHasTag(TEXT("ParisScannedVirgin")))Part->SetVisibility(Visible);
        if(Part->ComponentHasTag(TEXT("ParisVirginFallback")))Part->SetVisibility(Detailed&&!Visible);
    }
}

void AddParisScannedStatueStats(const AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Report){
    TArray<UStaticMeshComponent*> Parts;Scene->GetComponents(Parts);int32 Count=0,Visible=0,Nanite=0,Fallback=0;int64 Triangles=0;
    for(auto Part:Parts){
        if(Part->ComponentHasTag(TEXT("ParisScannedVirgin"))&&Part->GetStaticMesh()){Count++;Visible+=Part->IsVisible();Nanite+=Part->GetStaticMesh()->HasValidNaniteData();Triangles+=Part->GetStaticMesh()->GetNumTriangles(0);}
        if(Part->ComponentHasTag(TEXT("ParisVirginFallback"))&&Part->IsVisible())Fallback++;
    }
    Report->SetNumberField(TEXT("scanned_virgin_components"),Count);Report->SetNumberField(TEXT("scanned_virgin_visible"),Visible);Report->SetNumberField(TEXT("scanned_virgin_nanite"),Nanite);Report->SetNumberField(TEXT("scanned_virgin_triangles"),Triangles);Report->SetNumberField(TEXT("scanned_virgin_fallback_visible"),Fallback);
    Report->SetStringField(TEXT("scanned_virgin_credit"),TEXT("Notre-Dame de Paris - Virgin Mary, Benoit Rogez (shadows44), CC BY-NC 4.0; cropped canopy, estimated scale/registration; personal noncommercial use"));
}
