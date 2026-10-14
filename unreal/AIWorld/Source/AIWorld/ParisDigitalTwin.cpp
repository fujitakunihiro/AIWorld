#include "ParisDigitalTwin.h"
#include "WorldProtocol.h"
#include "Camera/CameraComponent.h"
#include "Components/InputComponent.h"
#include "GameFramework/PlayerInput.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/SkyLightComponent.h"
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
static bool InPolygons(const FVector& Point,const TSharedPtr<FJsonObject>& Feature) {
    for(const auto& P:Array(Feature,TEXT("polygons_cm"))){const auto& Rings=P->AsArray();if(Rings.IsEmpty()||!InRing(Point,Rings[0]->AsArray()))continue;bool Hole=false;for(int32 I=1;I<Rings.Num();I++)Hole|=InRing(Point,Rings[I]->AsArray());if(!Hole)return true;}return false;
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
    }
    else if(P.IsValid()&&P->HasField(TEXT("width_m")))Text+=FString::Printf(TEXT(" / width %.2fm\n%s"),Number(P,TEXT("width_m")),*String(P,TEXT("width_source")));
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
void AParisTwinController::BeginPlay(){Super::BeginPlay();bShowMouseCursor=true;SetInputMode(FInputModeGameOnly());}
void AParisTwinController::SetupInputComponent() {
    Super::SetupInputComponent();InputComponent->BindKey(EKeys::LeftMouseButton,IE_Pressed,this,&AParisTwinController::Pick);
    InputComponent->BindKey(EKeys::RightMouseButton,IE_Pressed,this,&AParisTwinController::BeginLook);
    InputComponent->BindKey(EKeys::RightMouseButton,IE_Released,this,&AParisTwinController::EndLook);
    InputComponent->BindKey(EKeys::F1,IE_Pressed,this,&AParisTwinController::ToggleLevels);
    InputComponent->BindKey(EKeys::F2,IE_Pressed,this,&AParisTwinController::Overview);
    InputComponent->BindKey(EKeys::F3,IE_Pressed,this,&AParisTwinController::Eye);
    InputComponent->BindKey(EKeys::F4,IE_Pressed,this,&AParisTwinController::ToggleIssues);
    InputComponent->BindKey(EKeys::F5,IE_Pressed,this,&AParisTwinController::ToggleFootprints);
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
void AParisTwinController::Overview(){if(auto C=Cast<AParisTwinCamera>(GetPawn()))if(auto S=Twin(GetWorld()))C->Overview(S->Extent,S->SceneCentre);}
void AParisTwinController::Eye(){if(auto C=Cast<AParisTwinCamera>(GetPawn()))if(auto S=Twin(GetWorld()))C->Eye(S->QualityCentre);}
void AParisTwinController::ZoomIn(){if(auto C=Cast<AParisTwinCamera>(GetPawn()))C->Zoom(.85);}
void AParisTwinController::ZoomOut(){if(auto C=Cast<AParisTwinCamera>(GetPawn()))C->Zoom(1.15);}
void AParisTwinController::Capture(){if(auto S=Twin(GetWorld()))S->Capture();}
void AParisTwinController::ToggleFootprints(){if(auto S=Twin(GetWorld()))S->ToggleFootprints();}
void AParisTwinController::ToggleIssues(){if(auto S=Twin(GetWorld()))S->ToggleIssues();}
void AParisTwinController::ToggleHelp(){if(auto H=Cast<AParisTwinHUD>(GetHUD()))H->bHelp=!H->bHelp;}
void AParisTwinController::LandmarkOne(){if(auto S=Twin(GetWorld()))S->FocusLandmark(0);}
void AParisTwinController::LandmarkTwo(){if(auto S=Twin(GetWorld()))S->FocusLandmark(1);}
void AParisTwinController::LandmarkThree(){if(auto S=Twin(GetWorld()))S->FocusLandmark(2);}

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
    if(!VertexMaterial||!StoneMaterial||!WaterMaterial){Status=TEXT("既存マテリアルがありません。Build-AIWorldUE.ps1を実行してください。");return;}
    Extent=Number(Data,TEXT("extent_m"),800);const auto& Q=Array(Data,TEXT("quality_centre_ue_cm"));if(Q.Num()==3)QualityCentre=FVector(Q[0]->AsNumber(),Q[1]->AsNumber(),Q[2]->AsNumber());
    Vector(Data->TryGetField(TEXT("scene_centre_ue_cm")),SceneCentre);
    for(const auto& V:Array(Data,TEXT("pick_features")))if(V->Type==EJson::Object)SourceFeatures.Add(V->AsObject());
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
        for(int32 I=0;I<Points.Num();I++){FVector P,N;if(!Vector(Points[I],P)||!Vector(NormalsJSON[I],N)){Valid=false;break;}Vertices.Add(P);Normals.Add(N);Colors.Add(Color);}
        for(const auto& I:IndexJSON){double N;if(!I->TryGetNumber(N)||N<0||N>=Vertices.Num()||FMath::FloorToDouble(N)!=N){Valid=false;break;}Indices.Add(int32(N));}
        if(!Valid){Status=TEXT("GISメッシュの数値・インデックスが不正です");return;}
        const FString Kind=String(J,TEXT("kind"));auto Mesh=NewObject<UProceduralMeshComponent>(this);AddInstanceComponent(Mesh);Mesh->SetupAttachment(RootComponent);Mesh->bUseAsyncCooking=true;Mesh->bUseComplexAsSimpleCollision=true;Mesh->RegisterComponent();
        Mesh->CreateMeshSection_LinearColor(0,Vertices,Indices,Normals,{},Colors,{},true);
        Mesh->SetCollisionEnabled(Kind==TEXT("water")?ECollisionEnabled::QueryOnly:ECollisionEnabled::QueryAndPhysics);Mesh->SetCollisionResponseToAllChannels(Kind==TEXT("water")?ECR_Ignore:ECR_Block);Mesh->SetCollisionResponseToChannel(ECC_Visibility,ECR_Block);
        Mesh->SetCastShadow((Kind==TEXT("building")||Kind==TEXT("roof"))&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoShadows")));Mesh->SetMaterial(0,Kind==TEXT("water")?WaterMaterial.Get():Kind==TEXT("roof")?(SlateMaterial?SlateMaterial.Get():StoneMaterial.Get()):Kind==TEXT("building")?StoneMaterial.Get():VertexMaterial.Get());
        Meshes.Add(Mesh);Features.Add(Mesh,J);TriangleCount+=Indices.Num()/3;if(Kind==TEXT("building"))BuildingCount++;
    }
    if(auto J=Object(Data,TEXT("footprint_mesh"))){TArray<FVector> V,N;TArray<int32> I;TArray<FLinearColor> C;bool Valid=true;const auto& VertexColors=Array(J,TEXT("vertex_colors"));for(const auto& P:Array(J,TEXT("positions_cm"))){FVector Point;if(!Vector(P,Point)){Valid=false;break;}V.Add(Point);N.Add(FVector::UpVector);if(VertexColors.Num()!=Array(J,TEXT("positions_cm")).Num()){Valid=false;break;}C.Add(FLinearColor(FColor::FromHex(VertexColors[V.Num()-1]->AsString())));}for(const auto& Index:Array(J,TEXT("indices"))){const double Value=Index->AsNumber();if(Value<0||Value>=V.Num()||FMath::FloorToDouble(Value)!=Value){Valid=false;break;}I.Add(int32(Value));}if(!Valid||I.Num()%3){Status=TEXT("輪郭メッシュが不正です");return;}FootprintMesh=NewObject<UProceduralMeshComponent>(this);AddInstanceComponent(FootprintMesh);FootprintMesh->SetupAttachment(RootComponent);FootprintMesh->RegisterComponent();FootprintMesh->CreateMeshSection_LinearColor(0,V,I,N,{},C,{},false);FootprintMesh->SetMaterial(0,VertexMaterial);FootprintMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);FootprintMesh->SetCastShadow(false);FootprintMesh->SetVisibility(false);}
    auto Sun=GetWorld()->SpawnActor<ADirectionalLight>();Sun->GetLightComponent()->SetMobility(EComponentMobility::Movable);Sun->SetActorRotation(FRotator(-48,-35,0));Sun->GetLightComponent()->SetIntensity(10.3f);
    auto Direction=CastChecked<UDirectionalLightComponent>(Sun->GetLightComponent());Direction->SetAtmosphereSunLight(true);Direction->SetLightSourceAngle(3);
    GetWorld()->SpawnActor<ASkyAtmosphere>();auto Sky=GetWorld()->SpawnActor<ASkyLight>();Sky->GetLightComponent()->SetMobility(EComponentMobility::Movable);Sky->GetLightComponent()->SetIntensity(2.15f);Sky->GetLightComponent()->RecaptureSky();
    auto Post=GetWorld()->SpawnActor<APostProcessVolume>();Post->bUnbound=true;auto& P=Post->Settings;
    P.bOverride_AutoExposureMethod=true;P.AutoExposureMethod=EAutoExposureMethod::AEM_Manual;P.bOverride_AutoExposureBias=true;P.AutoExposureBias=9.6f;
    P.bOverride_AmbientOcclusionIntensity=true;P.AmbientOcclusionIntensity=.6f;P.bOverride_AmbientOcclusionRadius=true;P.AmbientOcclusionRadius=100;
    if(auto C=Cast<AParisTwinCamera>(GetWorld()->GetFirstPlayerController()->GetPawn())){if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinEye")))C->Eye(QualityCentre);else C->Overview(Extent,SceneCentre);}
    int32 Landmark=0;if(FParse::Value(FCommandLine::Get(),TEXT("ParisTwinLandmark="),Landmark)&&Landmark>=1&&Landmark<=3)FocusLandmark(Landmark-1);
    if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinFootprints")))ToggleFootprints();
    if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinIssues")))ToggleIssues();
    bReady=true;ReadyAt=FPlatformTime::Seconds();Status=FString::Printf(TEXT("実データ地区: %d棟 / %d triangles / EPSG:2154 / 1m=100cm"),BuildingCount,TriangleCount);
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
    else if(Found){const auto J=*Found;auto P=Object(J,TEXT("properties"));if(!String(P,TEXT("source_id")).IsEmpty())Source=J;else Source=SourceAt(Hit.ImpactPoint,String(J,TEXT("kind"))==TEXT("roof")?TEXT("building"):String(J,TEXT("kind")),Array(P,TEXT("source_ids")));}
    Selection=Source?FeatureText(Source):TEXT("Geographic inspection point");
    const auto LL=GeoReference.WGS84FromUE(Hit.ImpactPoint),EN=GeoReference.ProjectedFromUE(Hit.ImpactPoint);
    Selection+=FString::Printf(TEXT("\nCLICK WGS84 lon %.7f / lat %.7f | EPSG:2154 %.3f, %.3fm\nUE %.1f, %.1f, %.1fcm (Z is relative preview height)"),LL.X,LL.Y,EN.X,EN.Y,Hit.ImpactPoint.X,Hit.ImpactPoint.Y,Hit.ImpactPoint.Z);
}
void AParisTwinScene::FocusLandmark(int32 Index) {
    if(!Landmarks.IsValidIndex(Index))return;auto L=Landmarks[Index];FVector Point;if(!Vector(L->TryGetField(TEXT("ue_cm")),Point))return;
    if(auto C=Cast<AParisTwinCamera>(GetWorld()->GetFirstPlayerController()->GetPawn()))C->Focus(Point,Number(L,TEXT("radius_cm"),10000));
    for(const auto& F:SourceFeatures)if(String(F,TEXT("id"))==String(L,TEXT("source_id"))){Selection=FeatureText(F);break;}
}
void AParisTwinScene::ToggleFootprints() {
    bFootprints=!bFootprints;if(FootprintMesh)FootprintMesh->SetVisibility(bFootprints);
    for(auto& Pair:Features)if(String(Pair.Value,TEXT("kind"))==TEXT("building")||String(Pair.Value,TEXT("kind"))==TEXT("roof")){Pair.Key->SetVisibility(!bFootprints);Pair.Key->SetCollisionEnabled(bFootprints?ECollisionEnabled::NoCollision:ECollisionEnabled::QueryAndPhysics);}
}
void AParisTwinScene::ToggleIssues(){bIssues=!bIssues;RefreshAppearance();}
void AParisTwinScene::RefreshAppearance() {
    for(auto& Pair:Features)if(String(Pair.Value,TEXT("kind"))==TEXT("building")) {
        auto C=Cast<UProceduralMeshComponent>(Pair.Key);const bool Overlap=bIssues&&OverlapIDs.Contains(String(Pair.Value,TEXT("id")));const bool BodyL2=String(Object(Pair.Value,TEXT("properties")),TEXT("reproduction_level_body"))==TEXT("L2");const FColor Color=Overlap?FColor(235,65,92):bLevels?(BodyL2?FColor(78,174,148):FColor(239,156,66)):FLinearColor(FColor::FromHex(String(Pair.Value,TEXT("color")))).ToFColor(false);
        if(auto Section=C->GetProcMeshSection(0)){for(auto& V:Section->ProcVertexBuffer)V.Color=Color;C->MarkRenderStateDirty();}C->SetMaterial(0,bLevels||Overlap?VertexMaterial.Get():StoneMaterial.Get());
    }
    for(auto& Pair:Features)if(String(Pair.Value,TEXT("kind"))==TEXT("roof")){
        auto C=Cast<UProceduralMeshComponent>(Pair.Key);const auto& LevelColors=Array(Pair.Value,TEXT("level_colors"));if(auto Section=C->GetProcMeshSection(0)){for(int32 I=0;I<Section->ProcVertexBuffer.Num();I++)Section->ProcVertexBuffer[I].Color=FLinearColor(FColor::FromHex(bLevels&&LevelColors.IsValidIndex(I)?LevelColors[I]->AsString():String(Pair.Value,TEXT("color")))).ToFColor(false);C->MarkRenderStateDirty();}C->SetMaterial(0,bLevels?VertexMaterial.Get():(SlateMaterial?SlateMaterial.Get():StoneMaterial.Get()));
    }
}
void AParisTwinScene::ToggleLevels() {
    bLevels=!bLevels;RefreshAppearance();
}
void AParisTwinScene::Capture(){FScreenshotRequest::RequestScreenshot(FPaths::ProjectSavedDir()/TEXT("Screenshots/paris-twin.png"),true,false);}
void AParisTwinScene::Tick(float Delta) {
    Super::Tick(Delta);if(!bReady)return;const double Age=FPlatformTime::Seconds()-ReadyAt;
    if(bIssues)for(const auto& Issue:Issues)for(const auto& Line:Array(Issue,TEXT("polylines_cm"))){const auto& Points=Line->AsArray();for(int32 I=1;I<Points.Num();I++){FVector A,B;if(Vector(Points[I-1],A)&&Vector(Points[I],B))DrawDebugLine(GetWorld(),A,B,String(Issue,TEXT("kind"))==TEXT("building_overlap")?FColor(235,65,92):FColor(245,161,46),false,-1,0,2);}}
    if(!bCaptured&&Age>8&&FParse::Param(FCommandLine::Get(),TEXT("ParisTwinCapture"))){bCaptured=true;Capture();}
    double Duration=0;FParse::Value(FCommandLine::Get(),TEXT("ParisTwinBenchmark="),Duration);
    if(Duration>0&&Age>5&&!bMeasured){FrameTimes.Add(Delta*1000.);if(Age>=5+Duration){bMeasured=true;double Sum=0;for(double T:FrameTimes)Sum+=T;FrameTimes.Sort();auto J=MakeShared<FJsonObject>();J->SetNumberField(TEXT("fps"),FrameTimes.Num()*1000/FMath::Max(Sum,1.));J->SetNumberField(TEXT("frame_p95_ms"),FrameTimes[FMath::Clamp(FMath::CeilToInt(FrameTimes.Num()*.95)-1,0,FrameTimes.Num()-1)]);J->SetNumberField(TEXT("frames"),FrameTimes.Num());J->SetNumberField(TEXT("buildings"),BuildingCount);J->SetNumberField(TEXT("triangles"),TriangleCount);J->SetNumberField(TEXT("mesh_components"),Meshes.Num());J->SetBoolField(TEXT("shadows_disabled"),FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoShadows")));FVector2D Size;GEngine->GameViewport->GetViewportSize(Size);J->SetNumberField(TEXT("viewport_width"),Size.X);J->SetNumberField(TEXT("viewport_height"),Size.Y);J->SetStringField(TEXT("rhi"),TEXT("DX11 preview; no Nanite/Lumen claim"));J->SetStringField(TEXT("view"),FParse::Param(FCommandLine::Get(),TEXT("ParisTwinEye"))?TEXT("eye_1.7m"):TEXT("overview"));FString Output;FJsonSerializer::Serialize(J,TJsonWriterFactory<>::Create(&Output));FFileHelper::SaveStringToFile(Output,*(FPaths::ProjectSavedDir()/TEXT("paris-twin-performance.json")));UE_LOG(LogTemp,Display,TEXT("PARIS_TWIN_BENCHMARK %s"),*Output);if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinExit")))FPlatformMisc::RequestExit(false);}}
}
struct FParisButton{int32 Action;FString Label;FVector2D Position,Size;};
static TArray<FParisButton> ParisButtons(float Width) {
    const TArray<FString> Labels={TEXT("Overview [F2]"),TEXT("Street [F3]"),TEXT("Footprints [F5]"),TEXT("Issues [F4]"),TEXT("Notre-Dame [1]"),TEXT("Sainte-Chapelle [2]"),TEXT("Saint-Michel [3]"),TEXT("Help [H]")};
    TArray<FParisButton> Result;float X=16,Y=36;
    for(int32 I=0;I<Labels.Num();I++){const float W=Labels[I].Len()*7.5f+20;if(X+W>Width-16&&X>16){X=16;Y+=34;}Result.Add({I,Labels[I],FVector2D(X,Y),FVector2D(W,28)});X+=W+6;}return Result;
}
bool AParisTwinHUD::HandleClick(const FVector2D& P) {
    if(!Canvas)return false;auto C=Cast<AParisTwinController>(PlayerOwner);if(!C)return false;
    for(const auto& B:ParisButtons(Canvas->SizeX))if(P.X>=B.Position.X&&P.X<=B.Position.X+B.Size.X&&P.Y>=B.Position.Y&&P.Y<=B.Position.Y+B.Size.Y){switch(B.Action){case 0:C->Overview();break;case 1:C->Eye();break;case 2:C->ToggleFootprints();break;case 3:C->ToggleIssues();break;case 4:C->LandmarkOne();break;case 5:C->LandmarkTwo();break;case 6:C->LandmarkThree();break;default:C->ToggleHelp();break;}return true;}
    return P.Y<ParisButtons(Canvas->SizeX).Last().Position.Y+38;
}
void AParisTwinHUD::DrawHUD() {
    Super::DrawHUD();auto S=Twin(GetWorld());if(!S||!Canvas)return;
    auto Text=[this](const FString& Message,float X,float Y,float Scale=1.f){Canvas->SetDrawColor(FColor::White);Canvas->DrawText(GEngine->GetSmallFont(),Message,X,Y,Scale,Scale,FFontRenderInfo());};
    const auto Buttons=ParisButtons(Canvas->SizeX);const float Bottom=Buttons.Last().Position.Y+38;
    DrawRect(FLinearColor(.015f,.02f,.03f,.88f),8,8,Canvas->SizeX-16,Bottom-8);
    Text(FString::Printf(TEXT("PARIS DIGITAL TWIN | Phase 3 | %d buildings | IGN gutter heights / inferred roofs | 1m = 100cm"),S->BuildingCount),16,15,1.05f);
    for(const auto& B:Buttons){const bool Active=(B.Action==2&&S->bFootprints)||(B.Action==3&&S->bIssues)||(B.Action==7&&bHelp);DrawRect(Active?FLinearColor(.04f,.35f,.4f,1):FLinearColor(.12f,.17f,.23f,1),B.Position.X,B.Position.Y,B.Size.X,B.Size.Y);Text(B.Label,B.Position.X+10,B.Position.Y+7);}
    if(bHelp){DrawRect(FLinearColor(.015f,.02f,.03f,.93f),8,Bottom+4,FMath::Min(720.f,float(Canvas->SizeX-16)),116);Text(TEXT("Hold RIGHT mouse button and move the mouse to rotate. Release to show cursor."),16,Bottom+12);Text(TEXT("W/A/S/D: move | Arrow keys: rotate | Mouse wheel: overview zoom"),16,Bottom+36);Text(TEXT("Click a building, road or river for its source ID and the actual clicked coordinates."),16,Bottom+60);Text(TEXT("F1: body L2 green / L1 amber | F9: screenshot | Roof profiles remain inferred."),16,Bottom+84);}
    if(S->bIssues){DrawRect(FLinearColor(.07f,.025f,.01f,.88f),8,Bottom+(bHelp?126:4),FMath::Min(720.f,float(Canvas->SizeX-16)),42);Text(S->IssueSummary,16,Bottom+(bHelp?134:12));Text(TEXT("Red: source overlap | Orange: separate road paths (review; not automatically errors)"),16,Bottom+(bHelp?152:30));}
    if(!S->Selection.IsEmpty()){TArray<FString> Lines;S->Selection.ParseIntoArrayLines(Lines);const float Height=Lines.Num()*19+16,Y=Canvas->SizeY-50-Height;DrawRect(FLinearColor(.015f,.02f,.03f,.9f),8,Y,Canvas->SizeX-16,Height);for(int32 I=0;I<Lines.Num();I++)Text(Lines[I],16,Y+8+I*19);}
    DrawRect(FLinearColor(.015f,.02f,.03f,.85f),8,Canvas->SizeY-48,Canvas->SizeX-16,44);
    Text(TEXT("Hold RIGHT mouse to rotate | WASD move | Arrows rotate | Click the buttons above for views"),16,Canvas->SizeY-42);
    Text(TEXT("OpenStreetMap contributors / Ville de Paris (ODbL) | IGN BD TOPO / RGE ALTI (Etalab 2.0)"),16,Canvas->SizeY-22,.85f);
}
