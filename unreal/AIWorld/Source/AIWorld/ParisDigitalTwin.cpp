#include "ParisDigitalTwin.h"
#include "ParisStreetMeshes.h"
#include "ParisWalker.h"
#include "ParisPedestrians.h"
#include "Components/CapsuleComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "WorldProtocol.h"
#include "Camera/CameraComponent.h"
#include "Components/InputComponent.h"
#include "GameFramework/PlayerInput.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/DirectionalLight.h"
#include "Engine/SkyLight.h"
#include "Components/SkyAtmosphereComponent.h"
#include "Engine/PostProcessVolume.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "EngineUtils.h"
#include "UnrealClient.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Serialization/JsonSerializer.h"
#include "DrawDebugHelpers.h"
using namespace AIWorld;

static AParisTwinScene* Twin(UWorld* World) {
    for(TActorIterator<AParisTwinScene> It(World);It;++It)return *It;
    return nullptr;
}
static bool Vector(const TSharedPtr<FJsonValue>& Value,FVector& Out) {
    if(!Value.IsValid()||Value->Type!=EJson::Array)return false;
    const auto& A=Value->AsArray();if(A.Num()!=3)return false;
    double X,Y,Z;if(!A[0]->TryGetNumber(X)||!A[1]->TryGetNumber(Y)||!A[2]->TryGetNumber(Z))return false;
    if(!FMath::IsFinite(X)||!FMath::IsFinite(Y)||!FMath::IsFinite(Z))return false;
    Out=FVector(X,Y,Z);return true;
}

static bool InRing(const FVector& Point,const TArray<TSharedPtr<FJsonValue>>& Ring) {
    if(Ring.Num()<3)return false;bool Inside=false;
    for(int32 I=0,J=Ring.Num()-1;I<Ring.Num();J=I++){FVector A,B;if(!Vector(Ring[I],A)||!Vector(Ring[J],B))return false;
        if((A.Y>Point.Y)!=(B.Y>Point.Y)&&Point.X<(B.X-A.X)*(Point.Y-A.Y)/(B.Y-A.Y)+A.X)Inside=!Inside;}
    return Inside;
}
static bool OnRing(const FVector& Point,const TArray<TSharedPtr<FJsonValue>>& Ring) {
    for(int32 I=1;I<Ring.Num();I++){FVector A,B;if(!Vector(Ring[I-1],A)||!Vector(Ring[I],B))continue;A.Z=B.Z=0;const FVector P(Point.X,Point.Y,0),Edge=B-A;const double T=FMath::Clamp(FVector::DotProduct(P-A,Edge)/FMath::Max(Edge.SizeSquared(),1e-12),0.,1.);if((P-A-Edge*T).SizeSquared()<=1.)return true;}return false;
}
static bool InPolygons(const FVector& Point,const TSharedPtr<FJsonObject>& Feature) {
    for(const auto& P:Array(Feature,TEXT("polygons_cm"))){const auto& Rings=P->AsArray();if(Rings.IsEmpty()||(!InRing(Point,Rings[0]->AsArray())&&!OnRing(Point,Rings[0]->AsArray())))continue;bool Hole=false;for(int32 I=1;I<Rings.Num();I++)Hole|=InRing(Point,Rings[I]->AsArray())&&!OnRing(Point,Rings[I]->AsArray());if(!Hole)return true;}return false;
}
static double DistanceToLines(const FVector& Point,const TSharedPtr<FJsonObject>& Feature) {
    double Best=TNumericLimits<double>::Max();
    for(const auto& Line:Array(Feature,TEXT("polylines_cm"))){const auto& Points=Line->AsArray();for(int32 I=1;I<Points.Num();I++){FVector A,B;if(!Vector(Points[I-1],A)||!Vector(Points[I],B))continue;A.Z=B.Z=0;FVector P(Point.X,Point.Y,0),Edge=B-A;double T=FMath::Clamp(FVector::DotProduct(P-A,Edge)/FMath::Max(Edge.SizeSquared(),1e-10),0.,1.);Best=FMath::Min(Best,(P-(A+Edge*T)).Size());}}return Best;
}
static FString FeatureText(const TSharedPtr<FJsonObject>& J) {
    auto P=Object(J,TEXT("properties"));FString Text=String(P,TEXT("name"))+TEXT("  ")+String(J,TEXT("id"))+TEXT("  ")+String(P,TEXT("reproduction_level"));
    const auto& LL=Array(P,TEXT("wgs84_centre"));if(LL.Num()==2)Text+=FString::Printf(TEXT("\nWGS84 source anchor: %.7f, %.7f"),LL[0]->AsNumber(),LL[1]->AsNumber());
    if(String(J,TEXT("kind"))==TEXT("building")){
        Text+=FString::Printf(TEXT(" / height envelope %.2fm\nGutter %.1f - %.1fm | IGN coverage %.1f%% | Body %s / roof inferred"),Number(P,TEXT("height_m")),Number(P,TEXT("height_gutter_min_m")),Number(P,TEXT("height_gutter_max_m")),Number(P,TEXT("official_height_coverage"))*100,*String(P,TEXT("reproduction_level_body")));
        Text+=TEXT("\n")+String(P,TEXT("height_source"));const auto& Refs=Array(P,TEXT("height_reference_ids"));if(!Refs.IsEmpty())Text+=TEXT(" | ")+Refs[0]->AsString()+FString::Printf(TEXT(" (+%d more)"),Refs.Num()-1);
        if(!Refs.IsEmpty()){Text+=FString::Printf(TEXT(" | source precision %.1fm"),Number(P,TEXT("height_precision_max_m")));const auto& Dates=Array(P,TEXT("height_data_dates"));if(!Dates.IsEmpty())Text+=TEXT(" | updated ")+Dates.Last()->AsString().Left(10);}
        Text+=TEXT("\nAppearance: inferred doors, balconies, cornices, dormers and roof material; overall L1");
    }
    else if(String(J,TEXT("kind")).StartsWith(TEXT("street_"))){
        Text+=FString::Printf(TEXT("\nMapped OSM position | height %.2fm (%s)"),Number(P,TEXT("height_m")),*String(P,TEXT("height_source")));
        Text+=TEXT("\n")+String(P,TEXT("appearance_source"));
        Text+=TEXT("\nOrientation: ")+String(P,TEXT("direction_source"));
    }
    else if(P.IsValid()&&P->HasField(TEXT("width_m")))Text+=FString::Printf(TEXT(" / width %.2fm\n%s"),Number(P,TEXT("width_m")),*String(P,TEXT("width_source")));
    else if(P.IsValid()&&P->HasField(TEXT("water_level_ngf_m")))Text+=FString::Printf(TEXT("\nWater level estimate NGF %.2fm | %s"),Number(P,TEXT("water_level_ngf_m")),*String(P,TEXT("water_level_source")));
    Text+=TEXT("\n")+String(P,TEXT("source_url"));return Text;
}

AParisTwinCamera::AParisTwinCamera() {
    PrimaryActorTick.bCanEverTick=true;RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("GISCameraRoot"));
    Camera=CreateDefaultSubobject<UCameraComponent>(TEXT("GISCamera"));Camera->SetupAttachment(RootComponent);Camera->FieldOfView=60;
}
void AParisTwinCamera::Overview(double Size,const FVector& Centre){bEye=false;Target=Centre;Radius=Size*110;Yaw=-135;Pitch=55;}
void AParisTwinCamera::Focus(const FVector& Location,double Distance){bEye=false;Target=Location;Radius=Distance;Pitch=55;}
void AParisTwinCamera::Eye(const FVector& Location){bEye=true;Target=Location+FVector(0,0,170);Yaw=-35;Pitch=0;}
void AParisTwinCamera::Zoom(double Factor){if(!bEye)Radius=FMath::Clamp(Radius*Factor,1500.,250000.);}
void AParisTwinCamera::Tick(float Delta) {
    Super::Tick(Delta);auto PC=Cast<AParisTwinController>(GetController());if(!PC)return;
    const FVector2D LookDelta=PC->IsLooking()?PC->GetRawLookDelta():FVector2D::ZeroVector;
    if(!LookDelta.IsNearlyZero()){Yaw+=LookDelta.X*.22;Pitch=FMath::Clamp(Pitch-LookDelta.Y*.22,bEye?-80.:10.,80.);}
    Yaw+=(PC->IsInputKeyDown(EKeys::Right)?1.:0.)*60*Delta-(PC->IsInputKeyDown(EKeys::Left)?1.:0.)*60*Delta;
    Pitch=FMath::Clamp(Pitch+((PC->IsInputKeyDown(EKeys::Up)?1.:0.)-(PC->IsInputKeyDown(EKeys::Down)?1.:0.))*40*Delta,bEye?-80.:10.,80.);
    const FVector Forward(FMath::Cos(FMath::DegreesToRadians(Yaw)),FMath::Sin(FMath::DegreesToRadians(Yaw)),0),Right(-Forward.Y,Forward.X,0);
    FVector Move=FVector::ZeroVector;
    if(PC->IsInputKeyDown(EKeys::W))Move+=Forward;if(PC->IsInputKeyDown(EKeys::S))Move-=Forward;
    if(PC->IsInputKeyDown(EKeys::D))Move+=Right;if(PC->IsInputKeyDown(EKeys::A))Move-=Right;
    Target+=Move*(bEye?350.:Radius*.3)*Delta;
    if(bEye){Camera->SetWorldLocation(Target);Camera->SetWorldRotation(FRotator(Pitch,Yaw,0));}
    else {const double R=FMath::DegreesToRadians(Pitch);const FVector Offset(-Forward.X*Radius*FMath::Cos(R),-Forward.Y*Radius*FMath::Cos(R),Radius*FMath::Sin(R));Camera->SetWorldLocation(Target+Offset);Camera->SetWorldRotation((Target-Camera->GetComponentLocation()).Rotation());}
}
void AParisTwinController::BeginPlay(){Super::BeginPlay();FreeCamera=Cast<AParisTwinCamera>(GetPawn());bShowMouseCursor=true;SetInputMode(FInputModeGameOnly());}
void AParisTwinController::SetupInputComponent() {
    Super::SetupInputComponent();InputComponent->BindKey(EKeys::LeftMouseButton,IE_Pressed,this,&AParisTwinController::Pick);
    InputComponent->BindKey(EKeys::RightMouseButton,IE_Pressed,this,&AParisTwinController::BeginLook);
    InputComponent->BindKey(EKeys::RightMouseButton,IE_Released,this,&AParisTwinController::EndLook);
    InputComponent->BindKey(EKeys::F1,IE_Pressed,this,&AParisTwinController::ToggleLevels);
    InputComponent->BindKey(EKeys::F2,IE_Pressed,this,&AParisTwinController::Overview);
    InputComponent->BindKey(EKeys::F3,IE_Pressed,this,&AParisTwinController::Eye);
    InputComponent->BindKey(EKeys::F4,IE_Pressed,this,&AParisTwinController::ToggleIssues);
    InputComponent->BindKey(EKeys::F5,IE_Pressed,this,&AParisTwinController::ToggleFootprints);
    InputComponent->BindKey(EKeys::F6,IE_Pressed,this,&AParisTwinController::ToggleStreetDetails);
    InputComponent->BindKey(EKeys::F7,IE_Pressed,this,&AParisTwinController::CycleDetailQuality);
    InputComponent->BindKey(EKeys::F8,IE_Pressed,this,&AParisTwinController::Walk);
    InputComponent->BindKey(EKeys::V,IE_Pressed,this,&AParisTwinController::ToggleWalkView);
    InputComponent->BindKey(EKeys::P,IE_Pressed,this,&AParisTwinController::TogglePeople);
    InputComponent->BindKey(EKeys::H,IE_Pressed,this,&AParisTwinController::ToggleHelp);
    InputComponent->BindKey(EKeys::One,IE_Pressed,this,&AParisTwinController::LandmarkOne);
    InputComponent->BindKey(EKeys::Two,IE_Pressed,this,&AParisTwinController::LandmarkTwo);
    InputComponent->BindKey(EKeys::Three,IE_Pressed,this,&AParisTwinController::LandmarkThree);
    InputComponent->BindKey(EKeys::F9,IE_Pressed,this,&AParisTwinController::Capture);
    InputComponent->BindKey(EKeys::MouseScrollUp,IE_Pressed,this,&AParisTwinController::ZoomIn);
    InputComponent->BindKey(EKeys::MouseScrollDown,IE_Pressed,this,&AParisTwinController::ZoomOut);
}
void AParisTwinController::BeginLook(){bLooking=true;bShowMouseCursor=false;SetInputMode(FInputModeGameOnly());}
void AParisTwinController::EndLook(){bLooking=false;bShowMouseCursor=true;SetInputMode(FInputModeGameOnly());}
FVector2D AParisTwinController::GetRawLookDelta() const {
    return PlayerInput?FVector2D(PlayerInput->GetRawKeyValue(EKeys::MouseX),PlayerInput->GetRawKeyValue(EKeys::MouseY)):FVector2D::ZeroVector;
}
void AParisTwinController::Pick(){float X,Y;if(GetMousePosition(X,Y))if(auto HUD=Cast<AParisTwinHUD>(GetHUD()))if(HUD->HandleClick(FVector2D(X,Y)))return;FHitResult Hit;if(GetHitResultUnderCursor(ECC_Visibility,true,Hit))if(auto S=Twin(GetWorld()))S->SelectHit(Hit);}
void AParisTwinController::ToggleLevels(){if(auto S=Twin(GetWorld()))S->ToggleLevels();}
void AParisTwinController::Overview(){ReturnToFree();if(auto C=Cast<AParisTwinCamera>(GetPawn()))if(auto S=Twin(GetWorld()))C->Overview(S->Extent,S->SceneCentre);}
void AParisTwinController::Eye(){ReturnToFree();if(auto C=Cast<AParisTwinCamera>(GetPawn()))if(auto S=Twin(GetWorld()))C->Eye(S->QualityCentre);}
void AParisTwinController::ZoomIn(){if(auto C=Cast<AParisTwinCamera>(GetPawn()))C->Zoom(.85);}
void AParisTwinController::ZoomOut(){if(auto C=Cast<AParisTwinCamera>(GetPawn()))C->Zoom(1.15);}
void AParisTwinController::Capture(){if(auto S=Twin(GetWorld()))S->Capture();}
void AParisTwinController::ToggleFootprints(){if(auto S=Twin(GetWorld()))S->ToggleFootprints();}
void AParisTwinController::ToggleIssues(){if(auto S=Twin(GetWorld()))S->ToggleIssues();}
void AParisTwinController::ToggleStreetDetails(){if(auto S=Twin(GetWorld()))S->ToggleStreetDetails();}
void AParisTwinController::CycleDetailQuality(){if(auto S=Twin(GetWorld()))S->CycleDetailQuality();}
void AParisTwinController::ToggleHelp(){if(auto H=Cast<AParisTwinHUD>(GetHUD()))H->bHelp=!H->bHelp;}
void AParisTwinController::LandmarkOne(){ReturnToFree();if(auto S=Twin(GetWorld()))S->FocusLandmark(0);}
void AParisTwinController::LandmarkTwo(){ReturnToFree();if(auto S=Twin(GetWorld()))S->FocusLandmark(1);}
void AParisTwinController::LandmarkThree(){ReturnToFree();if(auto S=Twin(GetWorld()))S->FocusLandmark(2);}
void AParisTwinController::ReturnToFree(){if(Cast<AParisWalker>(GetPawn())){Walker->Suspend();if(FreeCamera)Possess(FreeCamera);}}
bool AParisTwinController::EnterWalk(bool ThirdPerson){
    auto S=Twin(GetWorld());if(!S||!S->bReady)return false;
    if(auto Current=Cast<AParisWalker>(GetPawn())){if(Current->bThirdPerson!=ThirdPerson)Current->ToggleView();return true;}
    auto C=Cast<AParisTwinCamera>(GetPawn());if(!C)return false;FreeCamera=C;
    const FVector Desired=C->bEye?C->Target-FVector(0,0,170):C->Target;FVector Centre;
    if(!S->FindWalkingSpawn(Desired,Centre)){S->Selection=TEXT("No clear walking surface here yet. Try Overview then Walk.");return false;}
    if(S->bFootprints)S->ToggleFootprints();
    if(!Walker){FActorSpawnParameters Params;Params.SpawnCollisionHandlingOverride=ESpawnActorCollisionHandlingMethod::AlwaysSpawn;Walker=GetWorld()->SpawnActor<AParisWalker>(Centre,FRotator(0,C->Yaw,0),Params);if(!Walker)return false;Walker->Scene=S;Walker->InitializeAppearance(S->Crowd);}
    Possess(Walker);Walker->ActivateAt(Centre,FRotator(0,C->Yaw,0),ThirdPerson);S->Selection.Empty();return true;
}
void AParisTwinController::Walk(){if(Cast<AParisWalker>(GetPawn()))Walker->ToggleView();else EnterWalk(false);}
void AParisTwinController::ToggleWalkView(){if(Cast<AParisWalker>(GetPawn()))Walker->ToggleView();else EnterWalk(true);}
void AParisTwinController::TogglePeople(){if(auto S=Twin(GetWorld()))S->TogglePeople();}

AParisTwinScene::AParisTwinScene(){PrimaryActorTick.bCanEverTick=true;RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("GISRoot"));}
void AParisTwinScene::BeginPlay() {
    Super::BeginPlay();FString Text;
    if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("Data/paris-digital-twin.json")))){Status=TEXT("GIS生成データがありません。Paris-DigitalTwin.cmdから起動してください。");return;}
    auto Data=Parse(Text);if(!Data||String(Data,TEXT("format"))!=TEXT("paris_twin_scene_v1")){Status=TEXT("GISデータの形式が不正です");return;}
    auto Reference=Object(Data,TEXT("georeference"));
    bool Cesium=false;if(!Reference.IsValid()||!Reference->TryGetBoolField(TEXT("cesium_transform_applied"),Cesium)||String(Reference,TEXT("units"))!=TEXT("cm")||Cesium){Status=TEXT("GIS単位・二重変換設定が不正です");return;}
    if(!GeoReference.Load(Reference)){Status=TEXT("Lambert-93の座標原点が一致しません");return;}
    VertexMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_Vertex.M_Vertex"));
    StoneMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_Stone.M_Stone"));
    SlateMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_Slate.M_Slate"));
    WaterMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_Water.M_Water"));
    if(auto ParisStone=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisLimestone.M_ParisLimestone")))StoneMaterial=ParisStone;
    if(auto ParisRoof=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisSlate.M_ParisSlate")))SlateMaterial=ParisRoof;
    GlassMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisGlass.M_ParisGlass"));
    ZincMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisZinc.M_ParisZinc"));
    IronMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisIron.M_ParisIron"));
    WoodMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisWood.M_ParisWood"));
    if(!VertexMaterial||!StoneMaterial||!WaterMaterial){Status=TEXT("既存マテリアルがありません。Build-AIWorldUE.ps1を実行してください。");return;}
    Extent=Number(Data,TEXT("extent_m"),800);const auto& Q=Array(Data,TEXT("quality_centre_ue_cm"));if(Q.Num()==3)QualityCentre=FVector(Q[0]->AsNumber(),Q[1]->AsNumber(),Q[2]->AsNumber());
    Vector(Data->TryGetField(TEXT("scene_centre_ue_cm")),SceneCentre);
    for(const auto& V:Array(Data,TEXT("pick_features")))if(V->Type==EJson::Object)SourceFeatures.Add(V->AsObject());
    for(const auto& F:SourceFeatures)if(String(F,TEXT("kind"))==TEXT("building"))BuildingCount++;
    for(const auto& V:Array(Data,TEXT("landmarks")))if(V->Type==EJson::Object)Landmarks.Add(V->AsObject());
    auto Diagnostics=Object(Data,TEXT("diagnostics"));int32 Overlaps=0,Disconnected=0;
    for(const auto& V:Array(Diagnostics,TEXT("issues")))if(V->Type==EJson::Object){auto Issue=V->AsObject();Issues.Add(Issue);if(String(Issue,TEXT("kind"))==TEXT("building_overlap")){Overlaps++;for(const auto& ID:Array(Issue,TEXT("source_ids")))OverlapIDs.Add(ID->AsString());}else Disconnected++;}
    IssueSummary=FString::Printf(TEXT("Source review: %d building overlaps / %d separate road components"),Overlaps,Disconnected);
    const auto& Objects=Array(Data,TEXT("objects"));if(Objects.Num()>5000){Status=TEXT("GIS地区のメッシュ数が上限を超えました");return;}
    for(const auto& Value:Objects) {
        auto J=Value->AsObject();const auto& Points=Array(J,TEXT("positions_cm"));const auto& NormalsJSON=Array(J,TEXT("normals"));const auto& IndexJSON=Array(J,TEXT("indices"));
        if(Points.Num()>1000000||Points.Num()!=NormalsJSON.Num()||IndexJSON.Num()%3){Status=TEXT("GISメッシュの配列が不正です");return;}
        TArray<FVector> Vertices,Normals;TArray<int32> Indices;TArray<FLinearColor> Colors;bool Valid=true;
        const FLinearColor Color(FColor::FromHex(String(J,TEXT("color"))));
        const auto& VertexColors=Array(J,TEXT("vertex_colors"));
        for(int32 I=0;I<Points.Num();I++){FVector P,N;if(!Vector(Points[I],P)||!Vector(NormalsJSON[I],N)){Valid=false;break;}Vertices.Add(P);Normals.Add(N);Colors.Add(VertexColors.IsValidIndex(I)?FLinearColor(FColor::FromHex(VertexColors[I]->AsString())):Color);}
        for(const auto& I:IndexJSON){double N;if(!I->TryGetNumber(N)||N<0||N>=Vertices.Num()||FMath::FloorToDouble(N)!=N){Valid=false;break;}Indices.Add(int32(N));}
        if(!Valid){Status=TEXT("GISメッシュの数値・インデックスが不正です");return;}
        const FString Kind=String(J,TEXT("kind"));auto Mesh=NewObject<UProceduralMeshComponent>(this);AddInstanceComponent(Mesh);Mesh->SetupAttachment(RootComponent);Mesh->bUseAsyncCooking=true;Mesh->bUseComplexAsSimpleCollision=true;Mesh->RegisterComponent();
        Mesh->CreateMeshSection_LinearColor(0,Vertices,Indices,Normals,{},Colors,{},true);
        Mesh->SetCollisionEnabled(Kind==TEXT("water")?ECollisionEnabled::QueryOnly:ECollisionEnabled::QueryAndPhysics);Mesh->SetCollisionResponseToAllChannels(Kind==TEXT("water")?ECR_Ignore:ECR_Block);Mesh->SetCollisionResponseToChannel(ECC_Visibility,ECR_Block);
        Mesh->SetCastShadow((Kind==TEXT("building")||Kind==TEXT("roof"))&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoShadows")));
        const bool Stone=Kind==TEXT("building")||Kind==TEXT("quay")||Kind==TEXT("facade_trim");
        UMaterialInterface* Mat=Stone?StoneMaterial.Get():VertexMaterial.Get();
        if(Kind==TEXT("water"))Mat=WaterMaterial;
        else if(Kind==TEXT("roof"))Mat=String(Object(J,TEXT("properties")),TEXT("roof_material"))==TEXT("zinc")&&ZincMaterial?ZincMaterial.Get():(SlateMaterial?SlateMaterial.Get():StoneMaterial.Get());
        else if(Kind==TEXT("facade_roof")&&ZincMaterial)Mat=ZincMaterial;
        else if(Kind==TEXT("facade_glass")&&GlassMaterial)Mat=GlassMaterial;
        else if(Kind==TEXT("facade_iron")&&IronMaterial)Mat=IronMaterial;
        else if(Kind==TEXT("facade_wood")&&WoodMaterial)Mat=WoodMaterial;
        Mesh->SetMaterial(0,Mat);
        const double Distance=Number(Object(J,TEXT("properties")),TEXT("render_distance_m"));if(Distance>0)Mesh->SetCullDistance(Distance*100);
        Meshes.Add(Mesh);Features.Add(Mesh,J);TriangleCount+=Indices.Num()/3;
    }
    TMap<FString,UStaticMesh*> Models;TMap<FString,int32> ModelTriangles;
    auto CrownMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisFoliage.M_ParisFoliage"));
    for(const auto& Value:Array(Data,TEXT("instance_models"))){auto Model=Value->AsObject();const FString Name=String(Model,TEXT("id"));
        UMaterialInterface* Mat=Name==TEXT("tree_crown")?CrownMaterial:Name.Contains(TEXT("metal"))?IronMaterial.Get():Name==TEXT("lamp_glass")?GlassMaterial.Get():WoodMaterial.Get();
        auto Mesh=BuildParisStreetMesh(this,Model,Mat?Mat:VertexMaterial.Get());if(!Mesh){Status=TEXT("街路設備モデルが不正です");return;}Models.Add(Name,Mesh);StreetModels.Add(Mesh);ModelTriangles.Add(Name,Array(Model,TEXT("indices")).Num()/3);
    }
    for(const auto& Value:Array(Data,TEXT("instance_batches"))){auto Batch=Value->AsObject();const FString Name=String(Batch,TEXT("model"));auto Model=Models.Find(Name);if(!Model){Status=TEXT("街路設備モデルがありません");return;}
        TArray<FTransform> Transforms;TArray<FString> IDs;
        for(const auto& Entry:Array(Batch,TEXT("instances"))){auto Item=Entry->AsObject();FVector Position,Scale;if(!Vector(Item->TryGetField(TEXT("position_cm")),Position)||!Vector(Item->TryGetField(TEXT("scale")),Scale)||Scale.GetMin()<=0){Status=TEXT("街路設備の座標が不正です");return;}Transforms.Add(FTransform(FRotator(0,Number(Item,TEXT("yaw_degrees")),0),Position,Scale));IDs.Add(String(Item,TEXT("source_id")));}
        auto HISM=NewObject<UHierarchicalInstancedStaticMeshComponent>(this);AddInstanceComponent(HISM);HISM->SetupAttachment(RootComponent);HISM->SetStaticMesh(*Model);HISM->SetCanEverAffectNavigation(false);HISM->RegisterComponent();HISM->AddInstances(Transforms,false,false,false);
        HISM->SetCollisionEnabled(Name==TEXT("tree_crown")?ECollisionEnabled::QueryOnly:ECollisionEnabled::QueryAndPhysics);HISM->SetCollisionResponseToAllChannels(Name==TEXT("tree_crown")?ECR_Ignore:ECR_Block);HISM->SetCollisionResponseToChannel(ECC_Visibility,ECR_Block);
        HISM->SetCastShadow(Name==TEXT("tree_crown")&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoShadows")));
        StreetMeshes.Add(HISM);StreetInstanceIDs.Add(HISM,IDs);StreetModelNames.Add(HISM,Name);InstanceCount+=Transforms.Num();InstanceTriangles+=Transforms.Num()*ModelTriangles[Name];
    }
    for(const auto& F:SourceFeatures)StreetCount+=String(F,TEXT("kind")).StartsWith(TEXT("street_"))?1:0;
    Crowd=GetWorld()->SpawnActor<AParisPedestrianCrowd>();if(!Crowd->Initialize(Object(Data,TEXT("pedestrians")))){Status=TEXT("歩行者データか材質が不正です。再生成とビルドを実行してください。");return;}
    bPeople=!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoPeople"));
    FParse::Value(FCommandLine::Get(),TEXT("ParisTwinQuality="),DetailQuality);DetailQuality=FMath::Clamp(DetailQuality,0,2);
    bStreetDetails=!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoStreetDetails"));ApplyDetailQuality();
    if(auto J=Object(Data,TEXT("footprint_mesh"))){TArray<FVector> V,N;TArray<int32> I;TArray<FLinearColor> C;bool Valid=true;const auto& VertexColors=Array(J,TEXT("vertex_colors"));for(const auto& P:Array(J,TEXT("positions_cm"))){FVector Point;if(!Vector(P,Point)){Valid=false;break;}V.Add(Point);N.Add(FVector::UpVector);if(VertexColors.Num()!=Array(J,TEXT("positions_cm")).Num()){Valid=false;break;}C.Add(FLinearColor(FColor::FromHex(VertexColors[V.Num()-1]->AsString())));}for(const auto& Index:Array(J,TEXT("indices"))){const double Value=Index->AsNumber();if(Value<0||Value>=V.Num()||FMath::FloorToDouble(Value)!=Value){Valid=false;break;}I.Add(int32(Value));}if(!Valid||I.Num()%3){Status=TEXT("輪郭メッシュが不正です");return;}FootprintMesh=NewObject<UProceduralMeshComponent>(this);AddInstanceComponent(FootprintMesh);FootprintMesh->SetupAttachment(RootComponent);FootprintMesh->RegisterComponent();FootprintMesh->CreateMeshSection_LinearColor(0,V,I,N,{},C,{},false);FootprintMesh->SetMaterial(0,VertexMaterial);FootprintMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);FootprintMesh->SetCastShadow(false);FootprintMesh->SetVisibility(false);}
    auto Sun=GetWorld()->SpawnActor<ADirectionalLight>();Sun->GetLightComponent()->SetMobility(EComponentMobility::Movable);Sun->SetActorRotation(FRotator(-48,-35,0));Sun->GetLightComponent()->SetIntensity(10.3f);
    auto Direction=CastChecked<UDirectionalLightComponent>(Sun->GetLightComponent());Direction->SetAtmosphereSunLight(true);Direction->SetLightSourceAngle(3);
    auto Atmosphere=GetWorld()->SpawnActor<ASkyAtmosphere>();Atmosphere->GetComponent()->TransformMode=ESkyAtmosphereTransformMode::PlanetTopAtComponentTransform;Atmosphere->SetActorLocation(FVector(0,0,-GeoReference.OriginElevationNGF*100));Atmosphere->GetComponent()->MarkRenderStateDirty();
    auto Sky=GetWorld()->SpawnActor<ASkyLight>();Sky->GetLightComponent()->SetMobility(EComponentMobility::Movable);Sky->GetLightComponent()->SetIntensity(2.15f);Sky->GetLightComponent()->RecaptureSky();
    auto Post=GetWorld()->SpawnActor<APostProcessVolume>();Post->bUnbound=true;auto& P=Post->Settings;
    P.bOverride_AutoExposureMethod=true;P.AutoExposureMethod=EAutoExposureMethod::AEM_Manual;P.bOverride_AutoExposureBias=true;P.AutoExposureBias=9.6f;
    P.bOverride_AmbientOcclusionIntensity=true;P.AmbientOcclusionIntensity=.6f;P.bOverride_AmbientOcclusionRadius=true;P.AmbientOcclusionRadius=100;
    if(auto C=Cast<AParisTwinCamera>(GetWorld()->GetFirstPlayerController()->GetPawn())){if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinEye"))||FParse::Param(FCommandLine::Get(),TEXT("ParisTwinWalk"))||FParse::Param(FCommandLine::Get(),TEXT("ParisTwinThirdPerson")))C->Eye(QualityCentre);else C->Overview(Extent,SceneCentre);}
    int32 Landmark=0;if(FParse::Value(FCommandLine::Get(),TEXT("ParisTwinLandmark="),Landmark)&&Landmark>=1&&Landmark<=3)FocusLandmark(Landmark-1);
    if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinFootprints")))ToggleFootprints();
    if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinIssues")))ToggleIssues();
    bReady=true;ReadyAt=FPlatformTime::Seconds();Status=FString::Printf(TEXT("実データ地区: %d棟 / %d triangles / EPSG:2154 / 1m=100cm"),BuildingCount,TriangleCount);
    bWalkLaunchPending=FParse::Param(FCommandLine::Get(),TEXT("ParisTwinWalk"))||FParse::Param(FCommandLine::Get(),TEXT("ParisTwinThirdPerson"));
    UE_LOG(LogTemp,Display,TEXT("PARIS_TWIN_READY buildings=%d triangles=%d extent=%.0fm world_partition=%d"),BuildingCount,TriangleCount,Extent,GetWorld()->GetWorldPartition()!=nullptr);
}
void AParisTwinScene::Select(UPrimitiveComponent* Component) {
    auto Found=Features.Find(Component);if(Found)Selection=FeatureText(*Found);
}
TSharedPtr<FJsonObject> AParisTwinScene::SourceAt(const FVector& Point,const FString& Kind,const TArray<TSharedPtr<FJsonValue>>& Allowed) const {
    TSet<FString> IDs;for(const auto& ID:Allowed)IDs.Add(ID->AsString());TSharedPtr<FJsonObject> Best;double BestScore=TNumericLimits<double>::Max();
    for(const auto& Feature:SourceFeatures){if(!IDs.IsEmpty()&&!IDs.Contains(String(Feature,TEXT("id"))))continue;const FString K=String(Feature,TEXT("kind"));if(!Kind.IsEmpty()&&Kind!=K&&!(Kind==TEXT("path")&&K==TEXT("road"))&&!(Kind==TEXT("sidewalk")&&K==TEXT("road")))continue;
        const bool Road=K==TEXT("road")||K==TEXT("bridge");double Score=Road?DistanceToLines(Point,Feature):0.;if(Road){const double Width=Number(Object(Feature,TEXT("properties")),TEXT("width_m"),2)*50+(Kind==TEXT("sidewalk")?150:1);if(Score>Width)continue;}else if(!InPolygons(Point,Feature))continue;
        Score+=K==TEXT("building")?0.:Road?100000.:200000.;if(Score<BestScore){BestScore=Score;Best=Feature;}}
    return Best;
}
void AParisTwinScene::SelectHit(const FHitResult& Hit) {
    auto Found=Features.Find(Hit.GetComponent());TSharedPtr<FJsonObject> Source;
    if(bFootprints)Source=SourceAt(Hit.ImpactPoint);
    else if(StreetInstanceIDs.Contains(Hit.GetComponent()))Source=StreetInstanceSource(Hit.GetComponent(),Hit.Item);
    else if(Found){const auto J=*Found;auto P=Object(J,TEXT("properties"));const FString Kind=String(J,TEXT("kind"));const FString SourceKind=Kind==TEXT("roof")||Kind.StartsWith(TEXT("facade_"))?TEXT("building"):Kind==TEXT("quay")?TEXT("water"):Kind;if(!String(P,TEXT("source_id")).IsEmpty())Source=J;else Source=SourceAt(Hit.ImpactPoint,SourceKind,Array(P,TEXT("source_ids")));if(!Source&&Kind.StartsWith(TEXT("facade_")))Source=SourceAt(Hit.ImpactPoint-Hit.ImpactNormal*15,TEXT("building"),Array(P,TEXT("source_ids")));}
    const FString Person=Crowd&&Hit.GetActor()==Crowd?Crowd->DescribeHit(Hit.GetComponent(),Hit.Item):TEXT("");
    Selection=!Person.IsEmpty()?Person:Source?FeatureText(Source):TEXT("Geographic inspection point");
    const auto LL=GeoReference.WGS84FromUE(Hit.ImpactPoint),EN=GeoReference.ProjectedFromUE(Hit.ImpactPoint);
    Selection+=FString::Printf(TEXT("\nCLICK WGS84 lon %.7f / lat %.7f | EPSG:2154 %.3f, %.3fm\nUE %.1f, %.1f, %.1fcm | NGF-IGN69 %.3fm (shared origin %.2fm)"),LL.X,LL.Y,EN.X,EN.Y,Hit.ImpactPoint.X,Hit.ImpactPoint.Y,Hit.ImpactPoint.Z,GeoReference.NGFFromUE(Hit.ImpactPoint),GeoReference.OriginElevationNGF);
}
TSharedPtr<FJsonObject> AParisTwinScene::StreetInstanceSource(UPrimitiveComponent* Component,int32 Instance) const {
    const auto IDs=StreetInstanceIDs.Find(Component);if(!IDs||!IDs->IsValidIndex(Instance))return nullptr;
    for(const auto& F:SourceFeatures)if(String(F,TEXT("id"))==(*IDs)[Instance])return F;return nullptr;
}
void AParisTwinScene::ToggleStreetDetails(){bStreetDetails=!bStreetDetails;ApplyDetailQuality();}
void AParisTwinScene::CycleDetailQuality(){DetailQuality=(DetailQuality+1)%3;ApplyDetailQuality();}
void AParisTwinScene::TogglePeople(){bPeople=!bPeople;ApplyDetailQuality();}
void AParisTwinScene::ApplyDetailQuality(){
    for(auto& Pair:Features){const FString Kind=String(Pair.Value,TEXT("kind"));if(Kind.StartsWith(TEXT("facade_"))){const double Base=Number(Object(Pair.Value,TEXT("properties")),TEXT("render_distance_m"),300);Pair.Key->SetCullDistance(Base*(DetailQuality==0?.5:DetailQuality==2?1.7:1.)*100);}}
    for(auto HISM:StreetMeshes){const bool Tree=StreetModelNames[HISM].StartsWith(TEXT("tree_"));const int32 Distance=Tree?(DetailQuality==0?90000:DetailQuality==1?120000:180000):(DetailQuality==0?12000:DetailQuality==1?25000:45000);HISM->SetCullDistances(Distance*.8,Distance);HISM->SetVisibility(bStreetDetails&&!bFootprints);HISM->SetCollisionEnabled(bStreetDetails&&!bFootprints?(StreetModelNames[HISM]==TEXT("tree_crown")?ECollisionEnabled::QueryOnly:ECollisionEnabled::QueryAndPhysics):ECollisionEnabled::NoCollision);}
    if(Crowd)Crowd->SetDisplay(bPeople&&!bFootprints,DetailQuality);
}
bool AParisTwinScene::FindWalkingSpawn(const FVector& Desired,FVector& Centre) const {
    FCollisionQueryParams Params;Params.AddIgnoredActor(GetWorld()->GetFirstPlayerController()->GetPawn());
    if(auto PC=Cast<AParisTwinController>(GetWorld()->GetFirstPlayerController()))if(PC->Walker)Params.AddIgnoredActor(PC->Walker);
    for(int32 Ring=0;Ring<=6;Ring++)for(int32 I=0;I<(Ring?12:1);I++){
        const double A=I*PI/6;const FVector Point=Desired+FVector(FMath::Cos(A)*Ring*800,FMath::Sin(A)*Ring*800,0);
        if(FMath::Abs(Point.X-SceneCentre.X)>Extent*50-100||FMath::Abs(Point.Y-SceneCentre.Y)>Extent*50-100||SourceAt(Point,TEXT("building")))continue;
        if(SourceAt(Point,TEXT("water"))&&!SourceAt(Point,TEXT("bridge")))continue;
        FHitResult Floor;if(!GetWorld()->LineTraceSingleByChannel(Floor,Point+FVector(0,0,1200),Point-FVector(0,0,5000),ECC_Pawn,Params)||Floor.ImpactNormal.Z<.72)continue;
        Centre=Floor.ImpactPoint+FVector(0,0,90.2);if(!GetWorld()->OverlapBlockingTestByChannel(Centre,FQuat::Identity,ECC_Pawn,FCollisionShape::MakeCapsule(34,88),Params))return true;
    }return false;
}
void AParisTwinScene::FocusLandmark(int32 Index) {
    if(!Landmarks.IsValidIndex(Index))return;auto L=Landmarks[Index];FVector Point;if(!Vector(L->TryGetField(TEXT("ue_cm")),Point))return;
    if(auto C=Cast<AParisTwinCamera>(GetWorld()->GetFirstPlayerController()->GetPawn()))C->Focus(Point,Number(L,TEXT("radius_cm"),10000));
    for(const auto& F:SourceFeatures)if(String(F,TEXT("id"))==String(L,TEXT("source_id"))){Selection=FeatureText(F);break;}
}
void AParisTwinScene::ToggleFootprints() {
    if(!bFootprints)if(auto PC=Cast<AParisTwinController>(GetWorld()->GetFirstPlayerController()))PC->ReturnToFree();
    bFootprints=!bFootprints;if(FootprintMesh)FootprintMesh->SetVisibility(bFootprints);
    for(auto& Pair:Features){const FString Kind=String(Pair.Value,TEXT("kind"));if(Kind==TEXT("building")||Kind==TEXT("roof")||Kind.StartsWith(TEXT("facade_"))){Pair.Key->SetVisibility(!bFootprints);Pair.Key->SetCollisionEnabled(bFootprints?ECollisionEnabled::NoCollision:ECollisionEnabled::QueryAndPhysics);}}
    ApplyDetailQuality();
}
void AParisTwinScene::ToggleIssues(){bIssues=!bIssues;RefreshAppearance();}
void AParisTwinScene::RefreshAppearance() {
    for(auto& Pair:Features)if(String(Pair.Value,TEXT("kind"))==TEXT("building")) {
        auto C=Cast<UProceduralMeshComponent>(Pair.Key);
        if(auto Section=C->GetProcMeshSection(0)){for(const auto& Value:Array(Pair.Value,TEXT("appearance_ranges"))){auto Range=Value->AsObject();const bool Overlap=bIssues&&OverlapIDs.Contains(String(Range,TEXT("source_id")));const FColor Color=Overlap?FColor(235,65,92):bLevels?(String(Range,TEXT("body_level"))==TEXT("L2")?FColor(78,174,148):FColor(239,156,66)):FLinearColor(FColor::FromHex(String(Range,TEXT("color")))).ToFColor(false);const int32 Start=Number(Range,TEXT("start")),End=Start+Number(Range,TEXT("count"));for(int32 I=Start;I<End&&Section->ProcVertexBuffer.IsValidIndex(I);I++)Section->ProcVertexBuffer[I].Color=Color;}C->MarkRenderStateDirty();}C->SetMaterial(0,bLevels||bIssues?VertexMaterial.Get():StoneMaterial.Get());
    }
    for(auto& Pair:Features)if(String(Pair.Value,TEXT("kind"))==TEXT("roof")){
        auto C=Cast<UProceduralMeshComponent>(Pair.Key);const auto& LevelColors=Array(Pair.Value,TEXT("level_colors"));if(auto Section=C->GetProcMeshSection(0)){for(int32 I=0;I<Section->ProcVertexBuffer.Num();I++)Section->ProcVertexBuffer[I].Color=FLinearColor(FColor::FromHex(bLevels&&LevelColors.IsValidIndex(I)?LevelColors[I]->AsString():String(Pair.Value,TEXT("color")))).ToFColor(false);C->MarkRenderStateDirty();}C->SetMaterial(0,bLevels?VertexMaterial.Get():String(Object(Pair.Value,TEXT("properties")),TEXT("roof_material"))==TEXT("zinc")&&ZincMaterial?ZincMaterial.Get():(SlateMaterial?SlateMaterial.Get():StoneMaterial.Get()));
    }
}
void AParisTwinScene::ToggleLevels() {
    bLevels=!bLevels;RefreshAppearance();
}
void AParisTwinScene::Capture(){FScreenshotRequest::RequestScreenshot(FPaths::ProjectSavedDir()/TEXT("Screenshots/paris-twin.png"),true,false);}
void AParisTwinScene::Tick(float Delta) {
    Super::Tick(Delta);if(!bReady)return;const double Age=FPlatformTime::Seconds()-ReadyAt;
    if(bWalkLaunchPending&&Age>.1){if(auto PC=Cast<AParisTwinController>(GetWorld()->GetFirstPlayerController()))if(PC->EnterWalk(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinThirdPerson"))))bWalkLaunchPending=false;if(Age>15)bWalkLaunchPending=false;}
    if(bIssues)for(const auto& Issue:Issues)for(const auto& Line:Array(Issue,TEXT("polylines_cm"))){const auto& Points=Line->AsArray();for(int32 I=1;I<Points.Num();I++){FVector A,B;if(Vector(Points[I-1],A)&&Vector(Points[I],B))DrawDebugLine(GetWorld(),A,B,String(Issue,TEXT("kind"))==TEXT("building_overlap")?FColor(235,65,92):FColor(245,161,46),false,-1,0,2);}}
    if(!bCaptured&&Age>8&&FParse::Param(FCommandLine::Get(),TEXT("ParisTwinCapture"))){bCaptured=true;Capture();}
    double Duration=0;FParse::Value(FCommandLine::Get(),TEXT("ParisTwinBenchmark="),Duration);
    if(Duration>0&&Age>5&&!bMeasured){FrameTimes.Add(Delta*1000.);if(Age>=5+Duration){bMeasured=true;double Sum=0;for(double T:FrameTimes)Sum+=T;FrameTimes.Sort();auto J=MakeShared<FJsonObject>();J->SetNumberField(TEXT("fps"),FrameTimes.Num()*1000/FMath::Max(Sum,1.));J->SetNumberField(TEXT("frame_p95_ms"),FrameTimes[FMath::Clamp(FMath::CeilToInt(FrameTimes.Num()*.95)-1,0,FrameTimes.Num()-1)]);J->SetNumberField(TEXT("frames"),FrameTimes.Num());J->SetNumberField(TEXT("buildings"),BuildingCount);J->SetNumberField(TEXT("triangles"),TriangleCount);J->SetNumberField(TEXT("mesh_components"),Meshes.Num());J->SetNumberField(TEXT("instance_components"),StreetMeshes.Num());J->SetNumberField(TEXT("street_objects"),StreetCount);J->SetNumberField(TEXT("instances"),InstanceCount);J->SetNumberField(TEXT("instance_triangles_before_culling"),InstanceTriangles);J->SetNumberField(TEXT("detail_quality"),DetailQuality);J->SetNumberField(TEXT("pedestrians_total"),Crowd?Crowd->People().Num():0);J->SetNumberField(TEXT("pedestrians_visible_budget"),Crowd?Crowd->VisibleCount:0);J->SetNumberField(TEXT("pedestrian_distance_travelled_m"),Crowd?Crowd->TravelledCm/100:0);J->SetBoolField(TEXT("people_enabled"),bPeople);auto Walker=Cast<AParisWalker>(GetWorld()->GetFirstPlayerController()->GetPawn());J->SetBoolField(TEXT("walking"),Walker!=nullptr);J->SetBoolField(TEXT("third_person"),Walker&&Walker->bThirdPerson);J->SetBoolField(TEXT("street_details"),bStreetDetails);J->SetBoolField(TEXT("shadows_disabled"),FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoShadows")));FVector2D Size;GEngine->GameViewport->GetViewportSize(Size);J->SetNumberField(TEXT("viewport_width"),Size.X);J->SetNumberField(TEXT("viewport_height"),Size.Y);J->SetStringField(TEXT("rhi"),TEXT("DX11 preview; no Nanite/Lumen claim"));int32 LandmarkIndex=0;FParse::Value(FCommandLine::Get(),TEXT("ParisTwinLandmark="),LandmarkIndex);J->SetNumberField(TEXT("landmark_index"),LandmarkIndex);J->SetBoolField(TEXT("footprints"),bFootprints);J->SetStringField(TEXT("view"),Walker?(Walker->bThirdPerson?TEXT("walk_third"):TEXT("walk_first")):LandmarkIndex>0?TEXT("landmark"):FParse::Param(FCommandLine::Get(),TEXT("ParisTwinEye"))?TEXT("eye_1.7m"):TEXT("overview"));FString Output;FJsonSerializer::Serialize(J,TJsonWriterFactory<>::Create(&Output));FFileHelper::SaveStringToFile(Output,*(FPaths::ProjectSavedDir()/TEXT("paris-twin-performance.json")));UE_LOG(LogTemp,Display,TEXT("PARIS_TWIN_BENCHMARK %s"),*Output);if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinExit")))FPlatformMisc::RequestExit(false);}}
}
struct FParisButton{int32 Action;FString Label;FVector2D Position,Size;};
static TArray<FParisButton> ParisButtons(float Width,bool Help=false) {
    const TArray<FString> Labels={TEXT("Overview [F2]"),TEXT("Fly [F3]"),TEXT("Footprints [F5]"),TEXT("Issues [F4]"),TEXT("Notre-Dame [1]"),TEXT("Chapelle [2]"),TEXT("St-Michel [3]"),TEXT("Help [H]"),TEXT("Props [F6]"),TEXT("Quality [F7]"),TEXT("Walk [F8]"),TEXT("View [V]"),TEXT("People [P]")};
    TArray<int32> Order={0,1,10,11,12,8,9,4,5,6,7};if(Help){Order.Add(2);Order.Add(3);}
    TArray<FParisButton> Result;float X=16,Y=36;
    for(int32 I:Order){const float W=Labels[I].Len()*7.f+18;if(X+W>Width-16&&X>16){X=16;Y+=34;}Result.Add({I,Labels[I],FVector2D(X,Y),FVector2D(W,28)});X+=W+5;}return Result;
}
bool AParisTwinHUD::HandleClick(const FVector2D& P) {
    if(!Canvas)return false;auto C=Cast<AParisTwinController>(PlayerOwner);if(!C)return false;
    for(const auto& B:ParisButtons(Canvas->SizeX,bHelp))if(P.X>=B.Position.X&&P.X<=B.Position.X+B.Size.X&&P.Y>=B.Position.Y&&P.Y<=B.Position.Y+B.Size.Y){switch(B.Action){case 0:C->Overview();break;case 1:C->Eye();break;case 2:C->ToggleFootprints();break;case 3:C->ToggleIssues();break;case 4:C->LandmarkOne();break;case 5:C->LandmarkTwo();break;case 6:C->LandmarkThree();break;case 7:C->ToggleHelp();break;case 8:C->ToggleStreetDetails();break;case 9:C->CycleDetailQuality();break;case 10:C->Walk();break;case 11:C->ToggleWalkView();break;default:C->TogglePeople();break;}return true;}
    return P.Y<ParisButtons(Canvas->SizeX,bHelp).Last().Position.Y+38;
}
void AParisTwinHUD::DrawHUD() {
    Super::DrawHUD();auto S=Twin(GetWorld());if(!S||!Canvas)return;
    auto Text=[this](const FString& Message,float X,float Y,float Scale=1.f){Canvas->SetDrawColor(FColor::White);Canvas->DrawText(GEngine->GetSmallFont(),Message,X,Y,Scale,Scale,FFontRenderInfo());};
    const auto Buttons=ParisButtons(Canvas->SizeX,bHelp);const float Bottom=Buttons.Last().Position.Y+38;
    DrawRect(FLinearColor(.015f,.02f,.03f,.88f),8,8,Canvas->SizeX-16,Bottom-8);
    Text(FString::Printf(TEXT("PARIS DIGITAL TWIN | %d buildings | %d mapped street objects | %d simulated people | Quality: %s"),S->BuildingCount,S->StreetCount,S->Crowd?S->Crowd->People().Num():0,S->DetailQuality==0?TEXT("LOW"):S->DetailQuality==1?TEXT("MEDIUM"):TEXT("HIGH")),16,15,1.05f);
    for(const auto& B:Buttons){const bool Active=(B.Action==2&&S->bFootprints)||(B.Action==3&&S->bIssues)||(B.Action==7&&bHelp)||(B.Action==8&&S->bStreetDetails)||(B.Action==10&&Cast<AParisWalker>(PlayerOwner->GetPawn()))||(B.Action==12&&S->bPeople);DrawRect(Active?FLinearColor(.04f,.35f,.4f,1):FLinearColor(.12f,.17f,.23f,1),B.Position.X,B.Position.Y,B.Size.X,B.Size.Y);Text(B.Label,B.Position.X+10,B.Position.Y+7);}
    if(bHelp){DrawRect(FLinearColor(.015f,.02f,.03f,.93f),8,Bottom+4,FMath::Min(720.f,float(Canvas->SizeX-16)),116);Text(TEXT("Hold RIGHT mouse button and move the mouse to rotate. Release to show cursor."),16,Bottom+12);Text(TEXT("WASD: move | F8: walk with gravity | V: first/third person | Shift: run | F2: overview"),16,Bottom+36);Text(TEXT("Click a building, road or river for its source ID and the actual clicked coordinates."),16,Bottom+60);Text(TEXT("F1: building accuracy | F4/F5: issues/footprints | F9: screenshot | P: simulated people"),16,Bottom+84);}
    if(S->bIssues){DrawRect(FLinearColor(.07f,.025f,.01f,.88f),8,Bottom+(bHelp?126:4),FMath::Min(720.f,float(Canvas->SizeX-16)),42);Text(S->IssueSummary,16,Bottom+(bHelp?134:12));Text(TEXT("Red: source overlap | Orange: separate road paths (review; not automatically errors)"),16,Bottom+(bHelp?152:30));}
    if(!S->Selection.IsEmpty()){TArray<FString> Lines;S->Selection.ParseIntoArrayLines(Lines);const float Height=Lines.Num()*19+16,Y=Canvas->SizeY-50-Height;DrawRect(FLinearColor(.015f,.02f,.03f,.9f),8,Y,Canvas->SizeX-16,Height);for(int32 I=0;I<Lines.Num();I++)Text(Lines[I],16,Y+8+I*19);}
    DrawRect(FLinearColor(.015f,.02f,.03f,.85f),8,Canvas->SizeY-48,Canvas->SizeX-16,44);
    const auto Walker=Cast<AParisWalker>(PlayerOwner->GetPawn());
    const FString Movement=Walker?(Walker->bThirdPerson?TEXT("THIRD PERSON | "):TEXT("FIRST PERSON 1.7m | "))+FString(TEXT("WASD walk | Shift run | Right-drag look | V view | F2 overview")):TEXT("Right-drag: look | WASD: fly | F8: walk with gravity | V: third person | P: simulated people");
    Text(Movement,16,Canvas->SizeY-42);
    Text(TEXT("OpenStreetMap contributors / Ville de Paris (ODbL) | IGN BD TOPO / RGE ALTI (Etalab 2.0)"),16,Canvas->SizeY-22,.85f);
}
