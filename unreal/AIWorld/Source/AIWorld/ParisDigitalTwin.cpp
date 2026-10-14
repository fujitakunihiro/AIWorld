#include "ParisDigitalTwin.h"
#include "WorldProtocol.h"
#include "Camera/CameraComponent.h"
#include "Components/InputComponent.h"
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

AParisTwinCamera::AParisTwinCamera() {
    PrimaryActorTick.bCanEverTick=true;RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("GISCameraRoot"));
    Camera=CreateDefaultSubobject<UCameraComponent>(TEXT("GISCamera"));Camera->SetupAttachment(RootComponent);Camera->FieldOfView=60;
}
void AParisTwinCamera::Overview(double Size){bEye=false;Target=FVector::ZeroVector;Radius=Size*110;Yaw=-135;Pitch=55;}
void AParisTwinCamera::Eye(const FVector& Location){bEye=true;Target=Location+FVector(0,0,170);Yaw=-35;Pitch=0;}
void AParisTwinCamera::Zoom(double Factor){if(!bEye)Radius=FMath::Clamp(Radius*Factor,1500.,250000.);}
void AParisTwinCamera::Tick(float Delta) {
    Super::Tick(Delta);auto PC=Cast<AParisTwinController>(GetController());if(!PC)return;
    float DX=0,DY=0;PC->GetInputMouseDelta(DX,DY);
    if(PC->IsInputKeyDown(EKeys::RightMouseButton)){Yaw+=DX*.22;Pitch=FMath::Clamp(Pitch-DY*.22,bEye?-80.:10.,80.);}
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
    InputComponent->BindKey(EKeys::F1,IE_Pressed,this,&AParisTwinController::ToggleLevels);
    InputComponent->BindKey(EKeys::F2,IE_Pressed,this,&AParisTwinController::Overview);
    InputComponent->BindKey(EKeys::F3,IE_Pressed,this,&AParisTwinController::Eye);
    InputComponent->BindKey(EKeys::F9,IE_Pressed,this,&AParisTwinController::Capture);
    InputComponent->BindKey(EKeys::MouseScrollUp,IE_Pressed,this,&AParisTwinController::ZoomIn);
    InputComponent->BindKey(EKeys::MouseScrollDown,IE_Pressed,this,&AParisTwinController::ZoomOut);
}
void AParisTwinController::Pick(){FHitResult Hit;if(GetHitResultUnderCursor(ECC_Visibility,true,Hit))if(auto S=Twin(GetWorld()))S->Select(Hit.GetComponent());}
void AParisTwinController::ToggleLevels(){if(auto S=Twin(GetWorld()))S->ToggleLevels();}
void AParisTwinController::Overview(){if(auto C=Cast<AParisTwinCamera>(GetPawn()))if(auto S=Twin(GetWorld()))C->Overview(S->Extent);}
void AParisTwinController::Eye(){if(auto C=Cast<AParisTwinCamera>(GetPawn()))if(auto S=Twin(GetWorld()))C->Eye(S->QualityCentre);}
void AParisTwinController::ZoomIn(){if(auto C=Cast<AParisTwinCamera>(GetPawn()))C->Zoom(.85);}
void AParisTwinController::ZoomOut(){if(auto C=Cast<AParisTwinCamera>(GetPawn()))C->Zoom(1.15);}
void AParisTwinController::Capture(){if(auto S=Twin(GetWorld()))S->Capture();}

AParisTwinScene::AParisTwinScene(){PrimaryActorTick.bCanEverTick=true;RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("GISRoot"));}
void AParisTwinScene::BeginPlay() {
    Super::BeginPlay();FString Text;
    if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("Data/paris-digital-twin.json")))){Status=TEXT("GIS生成データがありません。Paris-DigitalTwin.cmdから起動してください。");return;}
    auto Data=Parse(Text);if(!Data||String(Data,TEXT("format"))!=TEXT("paris_twin_scene_v1")){Status=TEXT("GISデータの形式が不正です");return;}
    auto Reference=Object(Data,TEXT("georeference"));
    bool Cesium=false;if(!Reference.IsValid()||!Reference->TryGetBoolField(TEXT("cesium_transform_applied"),Cesium)||String(Reference,TEXT("units"))!=TEXT("cm")||Cesium){Status=TEXT("GIS単位・二重変換設定が不正です");return;}
    VertexMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_Vertex.M_Vertex"));
    StoneMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_Stone.M_Stone"));
    WaterMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_Water.M_Water"));
    if(!VertexMaterial||!StoneMaterial||!WaterMaterial){Status=TEXT("既存マテリアルがありません。Build-AIWorldUE.ps1を実行してください。");return;}
    Extent=Number(Data,TEXT("extent_m"),800);const auto& Q=Array(Data,TEXT("quality_centre_ue_cm"));if(Q.Num()==3)QualityCentre=FVector(Q[0]->AsNumber(),Q[1]->AsNumber(),Q[2]->AsNumber());
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
        Mesh->CreateMeshSection_LinearColor(0,Vertices,Indices,Normals,{},Colors,{},Kind!=TEXT("water"));
        Mesh->SetCollisionEnabled(Kind==TEXT("water")?ECollisionEnabled::NoCollision:ECollisionEnabled::QueryAndPhysics);Mesh->SetCollisionResponseToAllChannels(ECR_Block);
        Mesh->SetCastShadow(Kind==TEXT("building")&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoShadows")));Mesh->SetMaterial(0,Kind==TEXT("water")?WaterMaterial.Get():Kind==TEXT("building")?StoneMaterial.Get():VertexMaterial.Get());
        Meshes.Add(Mesh);Features.Add(Mesh,J);TriangleCount+=Indices.Num()/3;if(Kind==TEXT("building"))BuildingCount++;
    }
    auto Sun=GetWorld()->SpawnActor<ADirectionalLight>();Sun->GetLightComponent()->SetMobility(EComponentMobility::Movable);Sun->SetActorRotation(FRotator(-48,-35,0));Sun->GetLightComponent()->SetIntensity(10.3f);
    auto Direction=CastChecked<UDirectionalLightComponent>(Sun->GetLightComponent());Direction->SetAtmosphereSunLight(true);Direction->SetLightSourceAngle(3);
    GetWorld()->SpawnActor<ASkyAtmosphere>();auto Sky=GetWorld()->SpawnActor<ASkyLight>();Sky->GetLightComponent()->SetMobility(EComponentMobility::Movable);Sky->GetLightComponent()->SetIntensity(2.15f);Sky->GetLightComponent()->RecaptureSky();
    auto Post=GetWorld()->SpawnActor<APostProcessVolume>();Post->bUnbound=true;auto& P=Post->Settings;
    P.bOverride_AutoExposureMethod=true;P.AutoExposureMethod=EAutoExposureMethod::AEM_Manual;P.bOverride_AutoExposureBias=true;P.AutoExposureBias=9.6f;
    P.bOverride_AmbientOcclusionIntensity=true;P.AmbientOcclusionIntensity=.6f;P.bOverride_AmbientOcclusionRadius=true;P.AmbientOcclusionRadius=100;
    if(auto C=Cast<AParisTwinCamera>(GetWorld()->GetFirstPlayerController()->GetPawn())){if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinEye")))C->Eye(QualityCentre);else C->Overview(Extent);}
    bReady=true;ReadyAt=FPlatformTime::Seconds();Status=FString::Printf(TEXT("実データ地区: %d棟 / %d triangles / EPSG:2154 / 1m=100cm"),BuildingCount,TriangleCount);
    UE_LOG(LogTemp,Display,TEXT("PARIS_TWIN_READY buildings=%d triangles=%d extent=%.0fm world_partition=%d"),BuildingCount,TriangleCount,Extent,GetWorld()->GetWorldPartition()!=nullptr);
}
void AParisTwinScene::Select(UPrimitiveComponent* Component) {
    auto Found=Features.Find(Component);if(!Found)return;auto J=*Found;auto P=Object(J,TEXT("properties"));
    Selection=String(P,TEXT("name"))+TEXT("  ")+String(J,TEXT("id"))+TEXT("  ")+String(P,TEXT("reproduction_level"));
    if(String(J,TEXT("kind"))==TEXT("building")) {
        const auto& LL=Array(P,TEXT("wgs84_centre"));
        if(LL.Num()==2)Selection+=FString::Printf(TEXT("\nWGS84 source anchor: %.7f, %.7f / height %.2fm"),LL[0]->AsNumber(),LL[1]->AsNumber(),Number(P,TEXT("height_m")));
        Selection+=TEXT("\n")+String(P,TEXT("height_source"))+TEXT(" / ")+String(P,TEXT("source_url"));
    }
}
void AParisTwinScene::ToggleLevels() {
    bLevels=!bLevels;
    for(auto& Pair:Features)if(String(Pair.Value,TEXT("kind"))==TEXT("building")) {
        auto C=Cast<UProceduralMeshComponent>(Pair.Key);if(bLevels){C->SetMaterial(0,VertexMaterial);auto Section=C->GetProcMeshSection(0);if(Section){for(auto& V:Section->ProcVertexBuffer)V.Color=FColor(239,156,66);C->MarkRenderStateDirty();}}
        else {auto Section=C->GetProcMeshSection(0);if(Section){const auto Color=FLinearColor(FColor::FromHex(String(Pair.Value,TEXT("color")))).ToFColor(false);for(auto& V:Section->ProcVertexBuffer)V.Color=Color;C->MarkRenderStateDirty();}C->SetMaterial(0,StoneMaterial);}
    }
}
void AParisTwinScene::Capture(){FScreenshotRequest::RequestScreenshot(FPaths::ProjectSavedDir()/TEXT("Screenshots/paris-twin.png"),true,false);}
void AParisTwinScene::Tick(float Delta) {
    Super::Tick(Delta);if(!bReady)return;const double Age=FPlatformTime::Seconds()-ReadyAt;
    if(!bCaptured&&Age>8&&FParse::Param(FCommandLine::Get(),TEXT("ParisTwinCapture"))){bCaptured=true;Capture();}
    double Duration=0;FParse::Value(FCommandLine::Get(),TEXT("ParisTwinBenchmark="),Duration);
    if(Duration>0&&Age>5&&!bMeasured){FrameTimes.Add(Delta*1000.);if(Age>=5+Duration){bMeasured=true;double Sum=0;for(double T:FrameTimes)Sum+=T;FrameTimes.Sort();auto J=MakeShared<FJsonObject>();J->SetNumberField(TEXT("fps"),FrameTimes.Num()*1000/FMath::Max(Sum,1.));J->SetNumberField(TEXT("frame_p95_ms"),FrameTimes[FMath::Clamp(FMath::CeilToInt(FrameTimes.Num()*.95)-1,0,FrameTimes.Num()-1)]);J->SetNumberField(TEXT("frames"),FrameTimes.Num());J->SetNumberField(TEXT("buildings"),BuildingCount);J->SetNumberField(TEXT("triangles"),TriangleCount);J->SetNumberField(TEXT("mesh_components"),Meshes.Num());J->SetBoolField(TEXT("shadows_disabled"),FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoShadows")));FVector2D Size;GEngine->GameViewport->GetViewportSize(Size);J->SetNumberField(TEXT("viewport_width"),Size.X);J->SetNumberField(TEXT("viewport_height"),Size.Y);J->SetStringField(TEXT("rhi"),TEXT("DX11 preview; no Nanite/Lumen claim"));J->SetStringField(TEXT("view"),FParse::Param(FCommandLine::Get(),TEXT("ParisTwinEye"))?TEXT("eye_1.7m"):TEXT("overview"));FString Output;FJsonSerializer::Serialize(J,TJsonWriterFactory<>::Create(&Output));FFileHelper::SaveStringToFile(Output,*(FPaths::ProjectSavedDir()/TEXT("paris-twin-performance.json")));UE_LOG(LogTemp,Display,TEXT("PARIS_TWIN_BENCHMARK %s"),*Output);if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinExit")))FPlatformMisc::RequestExit(false);}}
}
void AParisTwinHUD::DrawHUD() {
    Super::DrawHUD();auto S=Twin(GetWorld());if(!S||!Canvas)return;
    auto Text=[this](const FString& Message,float Y,FLinearColor Color){Canvas->DrawText(GEngine->GetSmallFont(),Message,20,Y,1,1,FFontRenderInfo());};
    DrawRect(FLinearColor(.015f,.02f,.03f,.9f),10,10,FMath::Min(1100.f,float(Canvas->SizeX-20)),154);
    Canvas->SetDrawColor(FColor::White);Text(TEXT("PARIS DIGITAL TWIN | Phase 1 / L1 geographic preview"),18,FLinearColor::White);Text(S->Status,38,FLinearColor::White);
    Text(TEXT("F1: L1 colour | F2: overview | F3: eye 1.7m | F9: screenshot | RMB rotate / WASD / wheel / click building"),58,FLinearColor::White);
    Text(TEXT("OpenStreetMap contributors + Ville de Paris (ODbL) | IGN RGE ALTI (Etalab 2.0)"),78,FLinearColor::White);
    Text(S->Selection.IsEmpty()?TEXT("Heights may be estimated. Flat terrain and bridge decks are preview approximations. No L3-L5 facade claim."):S->Selection,98,FLinearColor::White);
}
