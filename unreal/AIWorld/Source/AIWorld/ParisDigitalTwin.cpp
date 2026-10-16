#include "ParisDigitalTwin.h"
#include "ParisStreetMeshes.h"
#include "ParisWalker.h"
#include "ParisPedestrians.h"
#include "ParisTraffic.h"
#include "ParisRuntimeMesh.h"
#include "ParisRenderCache.h"
#include "ParisCollisionMesh.h"
#include "ParisPhotoEnvironment.h"
#include "ParisPhotoArchitecture.h"
#include "ParisGroundDisplay.h"
#include "ParisPhotoFrontages.h"
#if WITH_EDITOR
#include "AssetCompilingManager.h"
#endif
#include "HAL/PlatformMemory.h"
#include "HAL/FileManager.h"
#include "TimerManager.h"
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
#include "Engine/TextureCube.h"
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
        if(String(P,TEXT("source_id"))==TEXT("osm/way/201611261"))Text+=TEXT("\nPhoto facade: original inferred west-front study. Official overall dimensions; opening/sculpture details approximate. Not a surveyed full cathedral model.");
    }
    else if(String(J,TEXT("kind"))==TEXT("business")){
        Text+=TEXT("\nInferred storefront / awning (actual exterior unverified) | building ")+String(P,TEXT("building_source_id"));
        Text+=TEXT("\nOSM outdoor_seating tag: ")+String(P,TEXT("outdoor_seating_tag"))+TEXT(" | table/chair position and occupancy inferred");
        Text+=TEXT("\nMapped POI anchor retained; displayed facade is inferred, not a surveyed entrance");
    }
    else if(String(J,TEXT("kind")).StartsWith(TEXT("street_"))){
        Text+=FString::Printf(TEXT("\nMapped OSM position | height %.2fm (%s)"),Number(P,TEXT("height_m")),*String(P,TEXT("height_source")));
        Text+=TEXT("\n")+String(P,TEXT("appearance_source"));
        Text+=TEXT("\nOrientation: ")+String(P,TEXT("direction_source"));
    }
    else if(P.IsValid()&&P->HasField(TEXT("width_m")))Text+=FString::Printf(TEXT(" / width %.2fm\n%s"),Number(P,TEXT("width_m")),*String(P,TEXT("width_source")));
    else if(P.IsValid()&&P->HasField(TEXT("water_level_ngf_m")))Text+=FString::Printf(TEXT("\nWater level estimate NGF %.2fm | %s"),Number(P,TEXT("water_level_ngf_m")),*String(P,TEXT("water_level_source")));
    if(!String(P,TEXT("occupancy_source")).IsEmpty())Text+=TEXT("\n")+String(P,TEXT("occupancy_source"));
    if(!String(P,TEXT("signal_state_source")).IsEmpty())Text+=TEXT("\n")+String(P,TEXT("signal_state_source"));
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
    if((!Move.IsNearlyZero()||PC->IsLooking())&&PC->GetViewTarget()!=this)PC->SetViewTarget(this);
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
    InputComponent->BindKey(EKeys::T,IE_Pressed,this,&AParisTwinController::ToggleTraffic);
    InputComponent->BindKey(EKeys::C,IE_Pressed,this,&AParisTwinController::InspectTraffic);
    InputComponent->BindKey(EKeys::B,IE_Pressed,this,&AParisTwinController::InspectBusiness);
    InputComponent->BindKey(EKeys::H,IE_Pressed,this,&AParisTwinController::ToggleHelp);
    InputComponent->BindKey(EKeys::N,IE_Pressed,this,&AParisTwinController::ToggleNavigation);
    InputComponent->BindKey(EKeys::M,IE_Pressed,this,&AParisTwinController::ToggleSurfaces);
    InputComponent->BindKey(EKeys::One,IE_Pressed,this,&AParisTwinController::LandmarkOne);
    InputComponent->BindKey(EKeys::Two,IE_Pressed,this,&AParisTwinController::LandmarkTwo);
    InputComponent->BindKey(EKeys::Three,IE_Pressed,this,&AParisTwinController::LandmarkThree);
    InputComponent->BindKey(EKeys::F9,IE_Pressed,this,&AParisTwinController::Capture);
    const TArray<FName> Photos={TEXT("Camera_NotreDame_Front"),TEXT("Camera_NotreDame_Riverside"),TEXT("Camera_Paris_Street")};
    const TArray<FKey> PhotoKeys={EKeys::Four,EKeys::Five,EKeys::Six};
    for(int32 I=0;I<Photos.Num();I++){FInputKeyBinding Binding(FInputChord(PhotoKeys[I]),IE_Pressed);const FName Name=Photos[I];Binding.KeyDelegate.GetDelegateForManualSet().BindWeakLambda(this,[this,Name](){ActivateParisPhotoCamera(Twin(GetWorld()),Name);});InputComponent->KeyBindings.Add(Binding);}
    InputComponent->BindKey(EKeys::MouseScrollUp,IE_Pressed,this,&AParisTwinController::ZoomIn);
    InputComponent->BindKey(EKeys::MouseScrollDown,IE_Pressed,this,&AParisTwinController::ZoomOut);
}
void AParisTwinController::BeginLook(){bLooking=true;bShowMouseCursor=false;SetInputMode(FInputModeGameOnly());}
void AParisTwinController::EndLook(){bLooking=false;bShowMouseCursor=true;SetInputMode(FInputModeGameOnly());}
FVector2D AParisTwinController::GetRawLookDelta() const {
    return PlayerInput?FVector2D(PlayerInput->GetRawKeyValue(EKeys::MouseX),PlayerInput->GetRawKeyValue(EKeys::MouseY)):FVector2D::ZeroVector;
}
void AParisTwinController::Pick(){float X,Y;if(GetMousePosition(X,Y))if(auto HUD=Cast<AParisTwinHUD>(GetHUD()))if(HUD->HandleClick(FVector2D(X,Y)))return;FHitResult Hit;if(GetHitResultUnderCursor(ECC_Visibility,true,Hit))if(auto S=Twin(GetWorld()))S->SelectHit(Hit);}
void AParisTwinController::ToggleNavigation(){if(auto S=Twin(GetWorld()))if(S->Crowd)S->Crowd->bShowNavigation=!S->Crowd->bShowNavigation;}
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
void AParisTwinController::ReturnToFree(){if(Cast<AParisWalker>(GetPawn())){Walker->Suspend();if(FreeCamera)Possess(FreeCamera);}if(GetPawn())SetViewTarget(GetPawn());}
bool AParisTwinController::EnterWalk(bool ThirdPerson){
    auto S=Twin(GetWorld());if(!S||!S->bReady)return false;
    if(auto Current=Cast<AParisWalker>(GetPawn())){if(Current->bThirdPerson!=ThirdPerson)Current->ToggleView();return true;}
    auto C=Cast<AParisTwinCamera>(GetPawn());if(!C)return false;FreeCamera=C;
    const FVector Desired=C->bEye?C->Target-FVector(0,0,170):C->Target;FVector Centre;
    if(!S->FindWalkingSpawn(Desired,Centre)){S->ClearInspection();S->Selection=TEXT("No clear walking surface here yet. Try Overview then Walk.");return false;}
    if(S->bFootprints)S->ToggleFootprints();
    if(!Walker){FActorSpawnParameters Params;Params.SpawnCollisionHandlingOverride=ESpawnActorCollisionHandlingMethod::AlwaysSpawn;Walker=GetWorld()->SpawnActor<AParisWalker>(Centre,FRotator(0,C->Yaw,0),Params);if(!Walker)return false;Walker->Scene=S;Walker->InitializeAppearance(S->Crowd);}
    Possess(Walker);Walker->ActivateAt(Centre,FRotator(0,C->Yaw,0),ThirdPerson);S->ClearInspection();return true;
}
void AParisTwinController::Walk(){if(Cast<AParisWalker>(GetPawn()))Walker->ToggleView();else EnterWalk(false);}
void AParisTwinController::ToggleWalkView(){if(Cast<AParisWalker>(GetPawn()))Walker->ToggleView();else EnterWalk(true);}
void AParisTwinController::TogglePeople(){if(auto S=Twin(GetWorld()))S->TogglePeople();}
void AParisTwinController::ToggleTraffic(){if(auto S=Twin(GetWorld()))S->ToggleTraffic();}
void AParisTwinController::InspectBusiness(){if(auto S=Twin(GetWorld()))S->FocusBusiness();}
void AParisTwinController::InspectTraffic(){
    auto S=Twin(GetWorld());if(!S||!S->Traffic)return;ReturnToFree();auto C=Cast<AParisTwinCamera>(GetPawn());if(!C)return;
    const FParisVehicle* Best=nullptr;double Distance=TNumericLimits<double>::Max();
    for(const auto& A:S->Traffic->Vehicles())if(A.bActive){const double D=FVector::DistSquared2D(A.Position,S->QualityCentre);if(D<Distance){Distance=D;Best=&A;}}
    if(!Best)return;
    const FVector Forward=FRotator(0,Best->Yaw,0).Vector();
    FCollisionQueryParams Params;Params.AddIgnoredActor(S->Traffic);if(S->Crowd)Params.AddIgnoredActor(S->Crowd);if(Walker)Params.AddIgnoredActor(Walker);
    for(double CameraOffset:{800.,600.,1000.,500.,1200.,-700.}){
        FVector Centre;if(!S->FindWalkingSpawn(Best->Position-Forward*CameraOffset,Centre))continue;
        const FVector Eye=Centre+FVector(0,0,82),Target=Best->Position+FVector(0,0,90);bool Occupied=false;
        for(const auto& Other:S->Traffic->Vehicles())if(Other.bActive&&FVector::DistSquared2D(Eye,Other.Position)<400*400){Occupied=true;break;}
        if(Occupied)continue;FHitResult Blocker;if(GetWorld()->LineTraceSingleByChannel(Blocker,Eye,Target,ECC_Visibility,Params))continue;
        C->Eye(Centre-FVector(0,0,88));const FRotator Look=(Target-Eye).Rotation();C->Yaw=Look.Yaw;C->Pitch=Look.Pitch;return;
    }
    // Clear overhead fallback; never put an unchecked orbit inside a facade.
    C->Focus(Best->Position,10000);C->Yaw=Best->Yaw;C->Pitch=80;
}

// Collision cooks asynchronously. CLI inspection must wait for walkable
// geometry; the interactive C key already runs after the world is ready.
static void ParisInitialTrafficView(AParisTwinScene* Scene,int32 Attempts){
    if(!IsValid(Scene)||!Scene->GetWorld())return;
    auto PC=Cast<AParisTwinController>(Scene->GetWorld()->GetFirstPlayerController());
    if(PC){PC->InspectTraffic();if(auto Camera=Cast<AParisTwinCamera>(PC->GetPawn()))if(Camera->bEye)return;}
    if(Attempts<=1)return;FTimerHandle Retry;
    Scene->GetWorld()->GetTimerManager().SetTimer(Retry,FTimerDelegate::CreateWeakLambda(Scene,[Scene,Attempts](){ParisInitialTrafficView(Scene,Attempts-1);}),.5,false);
}

static void ParisInitialBusinessView(AParisTwinScene* Scene,int32 Attempts){
    if(!IsValid(Scene)||!Scene->GetWorld()||Scene->FocusBusiness())return;
    if(Attempts<=1)return;FTimerHandle Retry;Scene->GetWorld()->GetTimerManager().SetTimer(Retry,FTimerDelegate::CreateWeakLambda(Scene,[Scene,Attempts](){ParisInitialBusinessView(Scene,Attempts-1);}),.5,false);
}
bool AParisTwinScene::FocusBusiness(){
    if(!bReady)return false;auto PC=Cast<AParisTwinController>(GetWorld()->GetFirstPlayerController());if(!PC)return false;PC->ReturnToFree();auto C=Cast<AParisTwinCamera>(PC->GetPawn());if(!C)return false;
    const bool SurfaceView=FParse::Param(FCommandLine::Get(),TEXT("ParisTwinSurfaceView"));
    const bool StreetPhoto=FParse::Param(FCommandLine::Get(),TEXT("ParisTwinStreetPhoto"));
    FVector ToSun=FVector::ZeroVector;for(TActorIterator<ADirectionalLight> It(GetWorld());It;++It){ToSun=-It->GetActorForwardVector().GetSafeNormal2D();break;}
    TArray<TPair<double,TSharedPtr<FJsonObject>>> Candidates;
    for(const auto& F:SourceFeatures)if(String(F,TEXT("kind"))==TEXT("business")){
        if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinSeatingView"))&&(!Crowd||!Crowd->Destinations().ContainsByPredicate([&](const FParisVisitDestination& D){return D.BusinessID==String(F,TEXT("id"))&&Crowd->People().IsValidIndex(D.Owner)&&Crowd->People()[D.Owner].VisitStage==3&&Crowd->People()[D.Owner].SeatBlend>.999&&Crowd->People()[D.Owner].Wait>3;})))continue;
        FVector P;if(!Vector(F->TryGetField(TEXT("point_cm")),P))continue;const auto Props=Object(F,TEXT("properties"));
        if(SurfaceView&&(FMath::Abs(P.X-QualityCentre.X)>5000||FMath::Abs(P.Y-QualityCentre.Y)>5000))continue;
        double D=FVector::DistSquared2D(P,QualityCentre)+(SurfaceView||(Crowd&&Crowd->Destinations().ContainsByPredicate([&](const FParisVisitDestination& D){return D.BusinessID==String(F,TEXT("id"));}))?0:1e10)+(Props->GetBoolField(TEXT("terrace_placed"))?0:1e12);
        if(SurfaceView)D+=(1-FVector::DotProduct(FRotator(0,Number(Props,TEXT("facade_yaw_degrees"))+90,0).Vector(),ToSun))*1e8;
        Candidates.Emplace(D,F);
    }
    Candidates.Sort([](const auto& A,const auto& B){return A.Key<B.Key;});
    FCollisionQueryParams Params;if(Crowd)Params.AddIgnoredActor(Crowd);if(Traffic)Params.AddIgnoredActor(Traffic);if(PC->Walker)Params.AddIgnoredActor(PC->Walker);
    // Try a bounded set of sites and street widths; an obstructed nearest shop
    // must not prevent every later retry from finding an actual clear view.
    const TArray<double> Distances=SurfaceView?TArray<double>{900.,650.,1300.}:TArray<double>{650.};
    for(int32 Index=0;Index<FMath::Min(Candidates.Num(),StreetPhoto?16:8);Index++){
      const auto Best=Candidates[Index].Value;FVector P;Vector(Best->TryGetField(TEXT("point_cm")),P);const auto Props=Object(Best,TEXT("properties"));const double Yaw=Number(Props,TEXT("facade_yaw_degrees"));const FVector Out=FRotator(0,Yaw+90,0).Vector(),Along=FRotator(0,Yaw,0).Vector();
      for(double Distance:Distances)for(double Side:{0.,350.,-350.,600.,-600.}){
        FVector Centre;if(!FindWalkingSpawn(P+Out*Distance+Along*Side,Centre))continue;const FVector Eye=Centre+FVector(0,0,82);FVector Target=P+Out*70+FVector(0,0,SurfaceView?550:160);FHitResult Hit;
        if(StreetPhoto){
            auto Road=SourceAt(Centre,TEXT("sidewalk"));if(!Road||Number(Object(Road,TEXT("properties")),TEXT("width_m"))<6)continue;
            double Width=0;for(double Sign:{1.,-1.}){FHitResult Boundary;Width+=GetWorld()->LineTraceSingleByChannel(Boundary,Eye,Eye+Out*Sign*1600,ECC_Visibility,Params)?Boundary.Distance:1600;}
            if(Width<700)continue;
            // Keep the camera at pedestrian height and look along a real facade.
            // Select the longer clear corridor; never reposition GIS features.
            double BestDistance=0;FVector Direction=Along;
            for(double Sign:{1.,-1.}){const FVector D=(Along*Sign-Out*.12).GetSafeNormal();FHitResult Wall;
                const FVector End=Eye+D*1400;const double Clear=GetWorld()->LineTraceSingleByChannel(Wall,Eye,End,ECC_Visibility,Params)?Wall.Distance:1400;
                if(Clear>BestDistance){BestDistance=Clear;Direction=D;}}
            if(BestDistance<850)continue;Target=Eye+Direction*BestDistance+FVector(0,0,BestDistance*.04);
        }
        if(GetWorld()->LineTraceSingleByChannel(Hit,Eye,Target,ECC_Visibility,Params))continue;
        if(bFootprints)ToggleFootprints();if(!bStreetDetails)ToggleStreetDetails();
        C->Eye(Centre-FVector(0,0,88));const auto Look=(Target-Eye).Rotation();C->Yaw=Look.Yaw;C->Pitch=Look.Pitch;
        ClearInspection();if(!SurfaceView){SelectedBusinessID=String(Best,TEXT("id"));Selection=String(Props,TEXT("name"))+TEXT(" | ")+String(Best,TEXT("id"))+TEXT("\nInferred storefront / terrace; archived OSM business point, not a surveyed exterior");}return true;
      }
    }return false;
}

AParisTwinScene::AParisTwinScene(){PrimaryActorTick.bCanEverTick=true;RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("GISRoot"));}
void AParisTwinScene::BeginPlay() {
    Super::BeginPlay();const double LoadStarted=FPlatformTime::Seconds();FString Text;TArray<uint8> GeometryBlob;
    const FString DataDir=FPaths::ProjectContentDir()/TEXT("Data");
    bCompactRuntime=!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinLegacyJSON"))&&FPaths::FileExists(DataDir/TEXT("paris-digital-twin-runtime.json"));
    const FString Input=DataDir/(bCompactRuntime?TEXT("paris-digital-twin-runtime.json"):TEXT("paris-digital-twin.json"));
    SceneInputBytes=IFileManager::Get().FileSize(*Input);
    if(SceneInputBytes<1||SceneInputBytes>512LL*1024*1024||!FFileHelper::LoadFileToString(Text,*Input)){Status=TEXT("GIS生成データがありません。Paris-DigitalTwin.cmdから起動してください。");return;}
    auto Data=Parse(Text);if(!Data||String(Data,TEXT("format"))!=TEXT("paris_twin_scene_v1")){Status=TEXT("GISデータの形式が不正です");return;}
    if(bCompactRuntime){
        const FString BlobPath=DataDir/TEXT("paris-digital-twin-meshes.bin");const int64 Size=IFileManager::Get().FileSize(*BlobPath);FString Error;
        if(Size<16||Size>512LL*1024*1024||!FFileHelper::LoadFileToArray(GeometryBlob,*BlobPath)||!ValidateParisMeshBlob(Object(Data,TEXT("geometry_blob")),GeometryBlob,Error)){Status=TEXT("軽量地形データが不正です。offline prepareを実行してください。 ")+Error;return;}
        SceneInputBytes+=GeometryBlob.Num();
    }
    auto Reference=Object(Data,TEXT("georeference"));
    bool Cesium=false;if(!Reference.IsValid()||!Reference->TryGetBoolField(TEXT("cesium_transform_applied"),Cesium)||String(Reference,TEXT("units"))!=TEXT("cm")||Cesium){Status=TEXT("GIS単位・二重変換設定が不正です");return;}
    if(!GeoReference.Load(Reference)){Status=TEXT("Lambert-93の座標原点が一致しません");return;}
    VertexMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_Vertex.M_Vertex"));
    StoneMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_Stone.M_Stone"));
    SlateMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_Slate.M_Slate"));
    WaterMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_Seine_Water.M_Seine_Water"));
    if(auto ParisStone=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_Paris_Limestone.M_Paris_Limestone")))StoneMaterial=ParisStone;
    if(auto ParisRoof=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_Paris_Roof_Slate.M_Paris_Roof_Slate")))SlateMaterial=ParisRoof;
    GlassMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_Paris_Glass.M_Paris_Glass"));
    ZincMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_Paris_Roof_Zinc.M_Paris_Roof_Zinc"));
    IronMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_Paris_Iron.M_Paris_Iron"));
    WoodMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisWood.M_ParisWood"));
    PavingMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_Paris_Cobblestone.M_Paris_Cobblestone"));
    if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinProceduralSurfaces"))){
        StoneMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisLimestoneProcedural.M_ParisLimestoneProcedural"));
        PavingMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisPavingProcedural.M_ParisPavingProcedural"));
        SlateMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisSlate.M_ParisSlate"));
    }
    AsphaltMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_Paris_Asphalt.M_Paris_Asphalt"));
    bDetailedSurfaces=!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinFlatMaterials"));
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
        auto J=Value->AsObject();FParisMeshArrays Arrays;FString Error;
        if(!ReadParisMeshArrays(J,GeometryBlob,Arrays,Error)){Status=TEXT("GISメッシュが不正です: ")+Error;return;}
        auto& Vertices=Arrays.Positions;auto& Normals=Arrays.Normals;auto& Indices=Arrays.Indices;auto& Colors=Arrays.Colors;
        const FString Kind=String(J,TEXT("kind"));UProceduralMeshComponent* Mesh=(Kind==TEXT("building")||Kind==TEXT("roof"))?NewObject<UParisCollisionMesh>(this):NewObject<UProceduralMeshComponent>(this);AddInstanceComponent(Mesh);Mesh->SetupAttachment(RootComponent);Mesh->bUseAsyncCooking=true;Mesh->bUseComplexAsSimpleCollision=true;Mesh->RegisterComponent();
        Mesh->CreateMeshSection_LinearColor(0,Vertices,Indices,Normals,{},Colors,{},true);
        Mesh->SetCollisionEnabled(Kind==TEXT("water")?ECollisionEnabled::QueryOnly:ECollisionEnabled::QueryAndPhysics);Mesh->SetCollisionResponseToAllChannels(Kind==TEXT("water")?ECR_Ignore:ECR_Block);Mesh->SetCollisionResponseToChannel(ECC_Visibility,ECR_Block);
        Mesh->SetCastShadow((Kind==TEXT("building")||Kind==TEXT("roof")||Kind==TEXT("facade_relief")||Kind==TEXT("facade_planter")||Kind==TEXT("facade_railing"))&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoShadows")));
        Mesh->SetMaterial(0,SurfaceMaterialFor(J));
        if(Kind==TEXT("ground"))Mesh->ComponentTags.Add(TEXT("ParisSourceTerrain"));
        bool Cosmetic=false;Object(J,TEXT("properties"))->TryGetBoolField(TEXT("cosmetic_only"),Cosmetic);
        if(Cosmetic){Mesh->SetCollisionEnabled(ECollisionEnabled::QueryOnly);Mesh->SetCollisionResponseToChannel(ECC_Pawn,ECR_Ignore);}
        const double Distance=Number(Object(J,TEXT("properties")),TEXT("render_distance_m"));if(Distance>0)Mesh->SetCullDistance(Distance*100);
        Meshes.Add(Mesh);Features.Add(Mesh,J);TriangleCount+=Indices.Num()/3;
        if((Kind==TEXT("building")||Kind==TEXT("roof"))&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoRenderCache"))){
            UStaticMesh* Baked=nullptr;
            if(FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal"))){auto Spec=Object(Object(Data,TEXT("baked_visuals")),*String(J,TEXT("id")));const FString Package=String(Spec,TEXT("asset"));if(!Package.IsEmpty())Baked=LoadObject<UStaticMesh>(nullptr,*Package);}
            if(!BuildParisRenderCache(Mesh,Baked))UE_LOG(LogTemp,Warning,TEXT("Paris render cache failed for %s; keeping procedural drawing"),*String(J,TEXT("id")));
        }
    }
    TMap<FString,UStaticMesh*> Models;TMap<FString,int32> ModelTriangles;
    auto CrownMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisFoliage.M_ParisFoliage"));
    for(const auto& Value:Array(Data,TEXT("instance_models"))){auto Model=Value->AsObject();const FString Name=String(Model,TEXT("id"));
        UMaterialInterface* Mat=Name==TEXT("tree_crown")?CrownMaterial:Name.Contains(TEXT("metal"))?IronMaterial.Get():(Name.Contains(TEXT("glass"))||Name==TEXT("signal_lens"))?GlassMaterial.Get():Name==TEXT("bicycle_rubber")?LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisCloth.M_ParisCloth")):Name.StartsWith(TEXT("awning_"))?LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisCloth.M_ParisCloth")):WoodMaterial.Get();
        auto Mesh=BuildParisStreetMesh(this,Model,Mat?Mat:VertexMaterial.Get());if(!Mesh){Status=TEXT("街路設備モデルが不正です");return;}Models.Add(Name,Mesh);StreetModels.Add(Mesh);ModelTriangles.Add(Name,Array(Model,TEXT("indices")).Num()/3);
    }
    ProxyTreeCrownModel=Models.FindRef(TEXT("tree_crown"));
    const auto PhotoLamps=LoadParisPhotoStreetMeshes();
    if(FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal"))&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoPhotoNature")))PhotoTreeModel=LoadObject<UStaticMesh>(nullptr,TEXT("/Game/ParisPhotoreal/Nature/SM_ParisBroadleaf"));
    for(const auto& Value:Array(Data,TEXT("instance_batches"))){auto Batch=Value->AsObject();const FString Name=String(Batch,TEXT("model"));auto Model=Models.Find(Name);if(!Model){Status=TEXT("街路設備モデルがありません");return;}
        TArray<FTransform> Far,Near;TArray<FString> FarIDs,NearIDs;
        const bool Tree=PhotoTreeModel&&(Name==TEXT("tree_crown")||Name==TEXT("tree_trunk"));
        const bool Lamp=PhotoLamps.Contains(Name);
        for(const auto& Entry:Array(Batch,TEXT("instances"))){auto Item=Entry->AsObject();FVector Position,Scale;if(!Vector(Item->TryGetField(TEXT("position_cm")),Position)||!Vector(Item->TryGetField(TEXT("scale")),Scale)||Scale.GetMin()<=0){Status=TEXT("街路設備の座標が不正です");return;}
            const bool Detailed=(Tree||Lamp)&&FVector::DistSquared2D(Position,QualityCentre)<FMath::Square(17000.);
            (Detailed?Near:Far).Add(FTransform(FRotator(0,Number(Item,TEXT("yaw_degrees")),0),Position,Scale));(Detailed?NearIDs:FarIDs).Add(String(Item,TEXT("source_id")));
        }
        auto AddGroup=[&](const TArray<FTransform>& Transforms,const TArray<FString>& IDs,bool Detailed){
            if(Transforms.IsEmpty())return;
            auto HISM=NewObject<UHierarchicalInstancedStaticMeshComponent>(this);AddInstanceComponent(HISM);HISM->SetupAttachment(RootComponent);HISM->SetStaticMesh(Detailed&&Name==TEXT("tree_crown")?PhotoTreeModel.Get():*Model);HISM->SetCanEverAffectNavigation(false);HISM->RegisterComponent();HISM->AddInstances(Transforms,false,false,false);
            HISM->SetCollisionEnabled(Name==TEXT("tree_crown")?ECollisionEnabled::QueryOnly:ECollisionEnabled::QueryAndPhysics);HISM->SetCollisionResponseToAllChannels(Name==TEXT("tree_crown")?ECR_Ignore:ECR_Block);HISM->SetCollisionResponseToChannel(ECC_Visibility,ECR_Block);
            HISM->SetCastShadow((Name==TEXT("tree_crown")||Name.StartsWith(TEXT("awning_")))&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoShadows")));
            if(Detailed&&Tree)HISM->ComponentTags.Add(Name==TEXT("tree_crown")?TEXT("ParisPhotoTree"):TEXT("ParisPhotoTreeTrunkProxy"));
            if(Detailed&&Lamp){
                HISM->ComponentTags.Add(TEXT("ParisPhotoLampProxy"));
                HISM->ComponentTags.Add(Name==TEXT("lamp_metal")?TEXT("ParisPhotoLampMetalProxy"):TEXT("ParisPhotoLampGlassProxy"));
                auto Visual=NewObject<UInstancedStaticMeshComponent>(this);AddInstanceComponent(Visual);Visual->SetupAttachment(RootComponent);
                Visual->SetCollisionProfileName(TEXT("NoCollision"));Visual->SetCollisionEnabled(ECollisionEnabled::NoCollision);Visual->SetCanEverAffectNavigation(false);
                Visual->SetStaticMesh(PhotoLamps[Name]);Visual->ComponentTags.Add(TEXT("ParisPhotoStreetLamp"));if(Name==TEXT("lamp_metal"))Visual->ComponentTags.Add(TEXT("ParisPhotoLampMetal"));
                Visual->SetCastShadow(Name==TEXT("lamp_metal")&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoShadows")));
                Visual->RegisterComponent();Visual->AddInstances(Transforms,false,false,false);
            }
            StreetMeshes.Add(HISM);StreetInstanceIDs.Add(HISM,IDs);StreetModelNames.Add(HISM,Name);InstanceCount+=Transforms.Num();InstanceTriangles+=Transforms.Num()*ModelTriangles[Name];
        };
        AddGroup(Far,FarIDs,false);AddGroup(Near,NearIDs,true);
    }
    for(const auto& F:SourceFeatures){const FString Kind=String(F,TEXT("kind"));StreetCount+=Kind.StartsWith(TEXT("street_"))?1:0;if(Kind==TEXT("business")){BusinessCount++;if(Object(F,TEXT("properties"))->GetBoolField(TEXT("terrace_placed")))TerraceCount++;}}
    Crowd=GetWorld()->SpawnActor<AParisPedestrianCrowd>();if(!Crowd->Initialize(Object(Data,TEXT("pedestrians")))){Status=TEXT("歩行者データか材質が不正です。再生成とビルドを実行してください。");return;}
    Traffic=GetWorld()->SpawnActor<AParisTraffic>();if(!Traffic->Initialize(Object(Data,TEXT("traffic")))){Status=TEXT("車両データか材質が不正です。再生成とビルドを実行してください。");return;}Traffic->Crowd=Crowd;
    bTraffic=!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoTraffic"));
    bPeople=!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoPeople"));
    FParse::Value(FCommandLine::Get(),TEXT("ParisTwinQuality="),DetailQuality);DetailQuality=FMath::Clamp(DetailQuality,0,2);
    bStreetDetails=!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoStreetDetails"));ApplyDetailQuality();
    if(auto J=Object(Data,TEXT("footprint_mesh"))){FParisMeshArrays A;FString Error;if(!ReadParisMeshArrays(J,GeometryBlob,A,Error)){Status=TEXT("輪郭メッシュが不正です: ")+Error;return;}FootprintMesh=NewObject<UProceduralMeshComponent>(this);AddInstanceComponent(FootprintMesh);FootprintMesh->SetupAttachment(RootComponent);FootprintMesh->RegisterComponent();FootprintMesh->CreateMeshSection_LinearColor(0,A.Positions,A.Indices,A.Normals,{},A.Colors,{},false);FootprintMesh->SetMaterial(0,VertexMaterial);FootprintMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);FootprintMesh->SetCastShadow(false);FootprintMesh->SetVisibility(false);}
    ConfigureParisPhotoEnvironment(GetWorld(),GeoReference.OriginElevationNGF);
    CreateParisPhotoCameras(this,Data,GeometryBlob);
    CreateParisPhotoArchitecture(this);
    CreateParisPhotoFrontages(this,Data);
    CreateParisGroundDisplay(this,Data);
    if(auto C=Cast<AParisTwinCamera>(GetWorld()->GetFirstPlayerController()->GetPawn())){if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinEye"))||FParse::Param(FCommandLine::Get(),TEXT("ParisTwinWalk"))||FParse::Param(FCommandLine::Get(),TEXT("ParisTwinThirdPerson")))C->Eye(QualityCentre);else C->Overview(Extent,SceneCentre);}
    int32 Landmark=0;if(FParse::Value(FCommandLine::Get(),TEXT("ParisTwinLandmark="),Landmark)&&Landmark>=1&&Landmark<=3)FocusLandmark(Landmark-1);
    if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinFootprints")))ToggleFootprints();
    if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinIssues")))ToggleIssues();
    if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinTrafficView"))){FTimerHandle Launch;GetWorld()->GetTimerManager().SetTimer(Launch,FTimerDelegate::CreateWeakLambda(this,[this](){ParisInitialTrafficView(this,20);}),.5,false);}
    if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinCafeView"))){FTimerHandle Launch;GetWorld()->GetTimerManager().SetTimer(Launch,FTimerDelegate::CreateWeakLambda(this,[this](){ParisInitialBusinessView(this,20);}),.5,false);}
    SceneLoadMs=(FPlatformTime::Seconds()-LoadStarted)*1000;
    bReady=true;ReadyAt=FPlatformTime::Seconds();Status=FString::Printf(TEXT("実データ地区: %d棟 / %d triangles / EPSG:2154 / 1m=100cm"),BuildingCount,TriangleCount);
    bWalkLaunchPending=FParse::Param(FCommandLine::Get(),TEXT("ParisTwinWalk"))||FParse::Param(FCommandLine::Get(),TEXT("ParisTwinThirdPerson"));
    FString PhotoCamera;if(FParse::Value(FCommandLine::Get(),TEXT("ParisTwinPhotoCamera="),PhotoCamera))ActivateParisPhotoCamera(this,FName(*PhotoCamera));
    UE_LOG(LogTemp,Display,TEXT("PARIS_TWIN_LOAD mode=%s input_bytes=%lld ready_ms=%.3f"),bCompactRuntime?TEXT("compact"):TEXT("legacy_json"),SceneInputBytes,SceneLoadMs);
    UE_LOG(LogTemp,Display,TEXT("PARIS_TWIN_READY buildings=%d triangles=%d extent=%.0fm world_partition=%d"),BuildingCount,TriangleCount,Extent,GetWorld()->GetWorldPartition()!=nullptr);
}
void AParisTwinScene::ClearInspection(){Selection.Empty();SelectedPersonID.Empty();SelectedBusinessID.Empty();SelectionCoordinates.Empty();}
FString AParisTwinScene::InspectionText() const {
    if(!SelectedPersonID.IsEmpty()&&Crowd)return Crowd->DescribePerson(SelectedPersonID)+SelectionCoordinates;
    if(!SelectedBusinessID.IsEmpty()&&Crowd)return Selection+Crowd->DescribeBusiness(SelectedBusinessID);
    return Selection;
}
void AParisTwinScene::Select(UPrimitiveComponent* Component) {
    auto Found=Features.Find(Component);if(Found){ClearInspection();Selection=FeatureText(*Found);}
}
TSharedPtr<FJsonObject> AParisTwinScene::SourceAt(const FVector& Point,const FString& Kind,const TArray<TSharedPtr<FJsonValue>>& Allowed) const {
    TSet<FString> IDs;for(const auto& ID:Allowed)IDs.Add(ID->AsString());TSharedPtr<FJsonObject> Best;double BestScore=TNumericLimits<double>::Max();
    for(const auto& Feature:SourceFeatures){if(!IDs.IsEmpty()&&!IDs.Contains(String(Feature,TEXT("id"))))continue;const FString K=String(Feature,TEXT("kind"));if(!Kind.IsEmpty()&&Kind!=K&&!(Kind==TEXT("path")&&K==TEXT("road"))&&!(Kind==TEXT("sidewalk")&&K==TEXT("road")))continue;
        const bool Road=K==TEXT("road")||K==TEXT("bridge");double Score=Road?DistanceToLines(Point,Feature):0.;if(Road){const double Width=Number(Object(Feature,TEXT("properties")),TEXT("width_m"),2)*50+(Kind==TEXT("sidewalk")?150:1);if(Score>Width)continue;}else if(!InPolygons(Point,Feature))continue;
        Score+=K==TEXT("building")?0.:Road?100000.:200000.;if(Score<BestScore){BestScore=Score;Best=Feature;}}
    return Best;
}
void AParisTwinScene::SelectHit(const FHitResult& Hit) {
    ClearInspection();
    auto Found=Features.Find(Hit.GetComponent());TSharedPtr<FJsonObject> Source;
    if(bFootprints)Source=SourceAt(Hit.ImpactPoint);
    else if(StreetInstanceIDs.Contains(Hit.GetComponent()))Source=StreetInstanceSource(Hit.GetComponent(),Hit.Item);
    else if(Found){const auto J=*Found;auto P=Object(J,TEXT("properties"));const FString Kind=String(J,TEXT("kind"));const FString SourceKind=Kind==TEXT("roof")||Kind.StartsWith(TEXT("facade_"))?TEXT("building"):Kind==TEXT("quay")?TEXT("water"):Kind;if(!String(P,TEXT("source_id")).IsEmpty())Source=J;else Source=SourceAt(Hit.ImpactPoint,SourceKind,Array(P,TEXT("source_ids")));if(!Source&&Kind.StartsWith(TEXT("facade_")))Source=SourceAt(Hit.ImpactPoint-Hit.ImpactNormal*15,TEXT("building"),Array(P,TEXT("source_ids")));}
    const FString Person=Crowd&&Hit.GetActor()==Crowd?Crowd->DescribeHit(Hit.GetComponent(),Hit.Item):TEXT("");
    const FString Car=Traffic&&Hit.GetActor()==Traffic?Traffic->DescribeHit(Hit.GetComponent(),Hit.Item):TEXT("");
    Selection=!Car.IsEmpty()?Car:!Person.IsEmpty()?Person:Source?FeatureText(Source):TEXT("Geographic inspection point");
    if(!Person.IsEmpty())SelectedPersonID=Crowd->PersonID(Hit.GetComponent(),Hit.Item);
    else if(Source&&String(Source,TEXT("kind"))==TEXT("business"))SelectedBusinessID=String(Source,TEXT("id"));
    const auto LL=GeoReference.WGS84FromUE(Hit.ImpactPoint),EN=GeoReference.ProjectedFromUE(Hit.ImpactPoint);
    SelectionCoordinates=FString::Printf(TEXT("\nCLICK WGS84 lon %.7f / lat %.7f | EPSG:2154 %.3f, %.3fm\nUE %.1f, %.1f, %.1fcm | NGF-IGN69 %.3fm (shared origin %.2fm)"),LL.X,LL.Y,EN.X,EN.Y,Hit.ImpactPoint.X,Hit.ImpactPoint.Y,Hit.ImpactPoint.Z,GeoReference.NGFFromUE(Hit.ImpactPoint),GeoReference.OriginElevationNGF);Selection+=SelectionCoordinates;
}
TSharedPtr<FJsonObject> AParisTwinScene::StreetInstanceSource(UPrimitiveComponent* Component,int32 Instance) const {
    const auto IDs=StreetInstanceIDs.Find(Component);if(!IDs||!IDs->IsValidIndex(Instance))return nullptr;
    for(const auto& F:SourceFeatures)if(String(F,TEXT("id"))==(*IDs)[Instance])return F;return nullptr;
}
void AParisTwinScene::ToggleStreetDetails(){bStreetDetails=!bStreetDetails;ApplyDetailQuality();}
void AParisTwinScene::CycleDetailQuality(){DetailQuality=(DetailQuality+1)%3;ApplyDetailQuality();}
void AParisTwinScene::TogglePeople(){bPeople=!bPeople;ApplyDetailQuality();}
void AParisTwinScene::ToggleTraffic(){bTraffic=!bTraffic;ApplyDetailQuality();}
void AParisTwinScene::ApplyDetailQuality(){
    for(auto& Pair:Features){const FString Kind=String(Pair.Value,TEXT("kind"));if(Kind.StartsWith(TEXT("facade_"))){const auto Props=Object(Pair.Value,TEXT("properties"));const double Base=Number(Props,TEXT("render_distance_m"),300);Pair.Key->SetCullDistance(Base*(DetailQuality==0?.5:DetailQuality==2?1.7:1.)*100);bool QualityOnly=false;Props->TryGetBoolField(TEXT("quality_only"),QualityOnly);if(QualityOnly){const bool Visible=!bFootprints&&DetailQuality>0;Pair.Key->SetVisibility(Visible);Pair.Key->SetCollisionEnabled(Visible?ECollisionEnabled::QueryOnly:ECollisionEnabled::NoCollision);}}}
    for(auto HISM:StreetMeshes){const bool Tree=StreetModelNames[HISM].StartsWith(TEXT("tree_"));const int32 Distance=Tree?(DetailQuality==0?90000:DetailQuality==1?120000:180000):(DetailQuality==0?12000:DetailQuality==1?25000:45000);HISM->SetCullDistances(Distance*.8,Distance);HISM->SetVisibility(bStreetDetails&&!bFootprints);HISM->SetCollisionEnabled(bStreetDetails&&!bFootprints?(StreetModelNames[HISM]==TEXT("tree_crown")?ECollisionEnabled::QueryOnly:ECollisionEnabled::QueryAndPhysics):ECollisionEnabled::NoCollision);}
    for(auto HISM:StreetMeshes){
        if(HISM->ComponentHasTag(TEXT("ParisPhotoTree")))HISM->SetStaticMesh(DetailQuality>0?PhotoTreeModel.Get():ProxyTreeCrownModel.Get());
        if(HISM->ComponentHasTag(TEXT("ParisPhotoTreeTrunkProxy"))){HISM->SetRenderInMainPass(DetailQuality==0);HISM->SetRenderInDepthPass(DetailQuality==0);}
    }
    if(Crowd)Crowd->SetDisplay(bPeople&&!bFootprints,DetailQuality);
    if(Traffic)Traffic->SetDisplay(bTraffic&&!bFootprints,DetailQuality);
    RefreshAppearance();
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
    ClearInspection();for(const auto& F:SourceFeatures)if(String(F,TEXT("id"))==String(L,TEXT("source_id"))){Selection=FeatureText(F);break;}
}
void AParisTwinScene::ToggleFootprints() {
    if(!bFootprints)if(auto PC=Cast<AParisTwinController>(GetWorld()->GetFirstPlayerController()))PC->ReturnToFree();
    bFootprints=!bFootprints;if(FootprintMesh)FootprintMesh->SetVisibility(bFootprints);
    for(auto& Pair:Features){const FString Kind=String(Pair.Value,TEXT("kind"));if(Kind==TEXT("building")||Kind==TEXT("roof")||Kind.StartsWith(TEXT("facade_"))){Pair.Key->SetVisibility(!bFootprints);Pair.Key->SetCollisionEnabled(bFootprints?ECollisionEnabled::NoCollision:ECollisionEnabled::QueryAndPhysics);}}
    ApplyDetailQuality();
}
void AParisTwinScene::ToggleIssues(){bIssues=!bIssues;RefreshAppearance();}
void AParisTwinScene::RefreshAppearance() {
    SyncParisPhotoArchitecture(this);
    SyncParisPhotoStreetDetails(this);
    SyncParisPhotoFrontages(this);
    SyncParisGroundDisplay(this);
    for(auto& Pair:Features)if(String(Pair.Value,TEXT("kind"))==TEXT("building")) {
        auto C=Cast<UProceduralMeshComponent>(Pair.Key);
        if(auto Section=C->GetProcMeshSection(0)){for(const auto& Value:Array(Pair.Value,TEXT("appearance_ranges"))){auto Range=Value->AsObject();const bool Overlap=bIssues&&OverlapIDs.Contains(String(Range,TEXT("source_id")));const FColor Color=Overlap?FColor(235,65,92):bLevels?(String(Range,TEXT("body_level"))==TEXT("L2")?FColor(78,174,148):FColor(239,156,66)):FLinearColor(FColor::FromHex(String(Range,TEXT("color")))).ToFColor(false);const int32 Start=Number(Range,TEXT("start")),End=Start+Number(Range,TEXT("count"));for(int32 I=Start;I<End&&Section->ProcVertexBuffer.IsValidIndex(I);I++)Section->ProcVertexBuffer[I].Color=Color;}C->MarkRenderStateDirty();}C->SetMaterial(0,bLevels||bIssues?VertexMaterial.Get():StoneMaterial.Get());
    }
    for(auto& Pair:Features)if(String(Pair.Value,TEXT("kind"))==TEXT("roof")){
        auto C=Cast<UProceduralMeshComponent>(Pair.Key);const auto& LevelColors=Array(Pair.Value,TEXT("level_colors"));if(auto Section=C->GetProcMeshSection(0)){for(int32 I=0;I<Section->ProcVertexBuffer.Num();I++)Section->ProcVertexBuffer[I].Color=FLinearColor(FColor::FromHex(bLevels&&LevelColors.IsValidIndex(I)?LevelColors[I]->AsString():String(Pair.Value,TEXT("color")))).ToFColor(false);C->MarkRenderStateDirty();}C->SetMaterial(0,bLevels?VertexMaterial.Get():String(Object(Pair.Value,TEXT("properties")),TEXT("roof_material"))==TEXT("zinc")&&ZincMaterial?ZincMaterial.Get():(SlateMaterial?SlateMaterial.Get():StoneMaterial.Get()));
    }
    for(auto& Pair:Features)if(auto Mesh=Cast<UProceduralMeshComponent>(Pair.Key)){
        Mesh->SetMaterial(0,SurfaceMaterialFor(Pair.Value));
        SyncParisRenderCache(Mesh,bLevels||bIssues);
    }
}
void AParisTwinScene::ToggleLevels() {
    bLevels=!bLevels;RefreshAppearance();
}
void AParisTwinScene::Capture(){FScreenshotRequest::RequestScreenshot(FPaths::ProjectSavedDir()/TEXT("Screenshots/paris-twin.png"),true,false);}
void AParisTwinScene::Tick(float Delta) {
    Super::Tick(Delta);if(!bReady)return;
#if WITH_EDITOR
    // First-run Nanite, SDF, mesh-card, texture and shader preparation is not
    // steady rendering. Restart the CLI warmup until all registered queues
    // are empty; other actors and the editor continue to tick normally.
    if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinWaitForAssets"))&&FAssetCompilingManager::Get().GetNumRemainingAssets()>0){
        ReadyAt=FPlatformTime::Seconds();FrameTimes.Reset();bCaptured=false;bGPUProfiled=false;return;
    }
#endif
    const double Age=FPlatformTime::Seconds()-ReadyAt;
    if(!bGPUProfiled&&Age>3&&FParse::Param(FCommandLine::Get(),TEXT("ParisTwinProfileGPU"))){
        bGPUProfiled=true;
        if(auto PC=GetWorld()->GetFirstPlayerController()){
            PC->ConsoleCommand(TEXT("r.ProfileGPU.ShowUI 0"),false);
            PC->ConsoleCommand(TEXT("ProfileGPU"),false);
        }
    }
    if(bWalkLaunchPending&&Age>.1){if(auto PC=Cast<AParisTwinController>(GetWorld()->GetFirstPlayerController()))if(PC->EnterWalk(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinThirdPerson"))))bWalkLaunchPending=false;if(Age>15)bWalkLaunchPending=false;}
    if(bIssues)for(const auto& Issue:Issues)for(const auto& Line:Array(Issue,TEXT("polylines_cm"))){const auto& Points=Line->AsArray();for(int32 I=1;I<Points.Num();I++){FVector A,B;if(Vector(Points[I-1],A)&&Vector(Points[I],B))DrawDebugLine(GetWorld(),A,B,String(Issue,TEXT("kind"))==TEXT("building_overlap")?FColor(235,65,92):FColor(245,161,46),false,-1,0,2);}}
    double CaptureAfter=8;FParse::Value(FCommandLine::Get(),TEXT("ParisTwinCaptureAfter="),CaptureAfter);if(!FMath::IsFinite(CaptureAfter))CaptureAfter=8;
    if(!bCaptured&&Age>FMath::Clamp(CaptureAfter,1.,120.)&&FParse::Param(FCommandLine::Get(),TEXT("ParisTwinCapture"))){
        if(!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinSeatingView"))){bCaptured=true;Capture();}
        else if(FocusBusiness()){bCaptured=true;FTimerHandle CaptureTimer;GetWorld()->GetTimerManager().SetTimer(CaptureTimer,FTimerDelegate::CreateWeakLambda(this,[this](){Capture();}),.2f,false);}
    }
    double Duration=0;FParse::Value(FCommandLine::Get(),TEXT("ParisTwinBenchmark="),Duration);
    if(Duration>0&&Age>5&&!bMeasured){FrameTimes.Add(Delta*1000.);if(Age>=5+Duration){bMeasured=true;double Sum=0;for(double T:FrameTimes)Sum+=T;FrameTimes.Sort();auto J=MakeShared<FJsonObject>();J->SetNumberField(TEXT("fps"),FrameTimes.Num()*1000/FMath::Max(Sum,1.));J->SetNumberField(TEXT("frame_p95_ms"),FrameTimes[FMath::Clamp(FMath::CeilToInt(FrameTimes.Num()*.95)-1,0,FrameTimes.Num()-1)]);J->SetNumberField(TEXT("frames"),FrameTimes.Num());J->SetNumberField(TEXT("buildings"),BuildingCount);J->SetNumberField(TEXT("businesses"),BusinessCount);J->SetNumberField(TEXT("terraces"),TerraceCount);J->SetNumberField(TEXT("scene_load_ms"),SceneLoadMs);J->SetNumberField(TEXT("scene_input_bytes"),SceneInputBytes);J->SetBoolField(TEXT("compact_runtime"),bCompactRuntime);const auto Memory=FPlatformMemory::GetStats();J->SetNumberField(TEXT("process_physical_mb"),Memory.UsedPhysical/(1024.*1024));J->SetNumberField(TEXT("process_peak_physical_mb"),Memory.PeakUsedPhysical/(1024.*1024));J->SetNumberField(TEXT("triangles"),TriangleCount);J->SetNumberField(TEXT("mesh_components"),Meshes.Num());J->SetNumberField(TEXT("instance_components"),StreetMeshes.Num());J->SetNumberField(TEXT("street_objects"),StreetCount);J->SetNumberField(TEXT("instances"),InstanceCount);J->SetNumberField(TEXT("instance_triangles_before_culling"),InstanceTriangles);J->SetNumberField(TEXT("detail_quality"),DetailQuality);J->SetNumberField(TEXT("pedestrians_total"),Crowd?Crowd->People().Num():0);J->SetNumberField(TEXT("pedestrians_visible_budget"),Crowd?Crowd->VisibleCount:0);J->SetNumberField(TEXT("pedestrian_distance_travelled_m"),Crowd?Crowd->TravelledCm/100:0);J->SetBoolField(TEXT("people_enabled"),bPeople);J->SetNumberField(TEXT("pedestrians_instanced_now"),Crowd?Crowd->RenderedCount:0);J->SetNumberField(TEXT("pedestrians_near"),Crowd?Crowd->NearRenderedCount:0);J->SetNumberField(TEXT("pedestrians_far"),Crowd?Crowd->FarRenderedCount:0);J->SetNumberField(TEXT("pedestrian_parts"),Crowd?Crowd->RenderedParts:0);J->SetNumberField(TEXT("visit_destinations"),Crowd?Crowd->Destinations().Num():0);J->SetNumberField(TEXT("navigation_nodes"),Crowd?Crowd->NavigationNodes():0);J->SetNumberField(TEXT("navigation_edges"),Crowd?Crowd->NavigationEdges():0);J->SetNumberField(TEXT("network_visits"),Crowd?Crowd->NetworkVisits:0);J->SetNumberField(TEXT("network_visits_completed"),Crowd?Crowd->NetworkVisitsCompleted:0);J->SetNumberField(TEXT("plans_rejected"),Crowd?Crowd->PlansRejected:0);J->SetBoolField(TEXT("navigation_overlay"),Crowd&&Crowd->bShowNavigation);J->SetNumberField(TEXT("visits_dwelling_rendered"),Crowd?Crowd->StandingVisitorsRendered:0);J->SetNumberField(TEXT("seated_rendered"),Crowd?Crowd->SeatedRenderedCount:0);J->SetNumberField(TEXT("seated_arrivals"),Crowd?Crowd->SeatArrivals:0);J->SetNumberField(TEXT("greetings_started"),Crowd?Crowd->SocialStarted:0);J->SetNumberField(TEXT("greetings_completed"),Crowd?Crowd->SocialCompleted:0);J->SetNumberField(TEXT("visits_completed"),Crowd?Crowd->CompletedVisits:0);J->SetNumberField(TEXT("visits_aborted"),Crowd?Crowd->AbortedVisits:0);J->SetBoolField(TEXT("full_people"),FParse::Param(FCommandLine::Get(),TEXT("ParisTwinFullPeople")));J->SetNumberField(TEXT("vehicles_instanced_now"),Traffic?Traffic->RenderedCount:0);J->SetNumberField(TEXT("vehicles_total"),Traffic?Traffic->Vehicles().Num():0);J->SetNumberField(TEXT("vehicle_visible_budget"),Traffic?Traffic->VisibleBudget:0);J->SetNumberField(TEXT("vehicle_distance_travelled_m"),Traffic?Traffic->TravelledCm/100:0);J->SetNumberField(TEXT("vehicle_recycles"),Traffic?Traffic->Recycles:0);J->SetNumberField(TEXT("vehicle_yield_steps"),Traffic?Traffic->YieldSteps:0);J->SetBoolField(TEXT("traffic_enabled"),bTraffic);auto Walker=Cast<AParisWalker>(GetWorld()->GetFirstPlayerController()->GetPawn());J->SetBoolField(TEXT("walking"),Walker!=nullptr);auto Camera=Cast<AParisTwinCamera>(GetWorld()->GetFirstPlayerController()->GetPawn());J->SetBoolField(TEXT("camera_eye"),Camera&&Camera->bEye);J->SetNumberField(TEXT("camera_pitch_degrees"),Camera?Camera->Pitch:0);J->SetNumberField(TEXT("camera_elevation_ngf_m"),Camera?GeoReference.NGFFromUE(Camera->Target):0);J->SetBoolField(TEXT("third_person"),Walker&&Walker->bThirdPerson);J->SetBoolField(TEXT("street_details"),bStreetDetails);J->SetBoolField(TEXT("shadows_disabled"),FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoShadows")));FVector2D Size;GEngine->GameViewport->GetViewportSize(Size);J->SetNumberField(TEXT("viewport_width"),Size.X);J->SetNumberField(TEXT("viewport_height"),Size.Y);J->SetStringField(TEXT("rhi"),TEXT("DX11 preview; no Nanite/Lumen claim"));int32 LandmarkIndex=0;FParse::Value(FCommandLine::Get(),TEXT("ParisTwinLandmark="),LandmarkIndex);J->SetNumberField(TEXT("landmark_index"),LandmarkIndex);J->SetBoolField(TEXT("footprints"),bFootprints);J->SetStringField(TEXT("view"),Walker?(Walker->bThirdPerson?TEXT("walk_third"):TEXT("walk_first")):FParse::Param(FCommandLine::Get(),TEXT("ParisTwinSeatingView"))?TEXT("seated_cafe_inspection"):FParse::Param(FCommandLine::Get(),TEXT("ParisTwinCafeView"))?TEXT("cafe_inspection"):FParse::Param(FCommandLine::Get(),TEXT("ParisTwinTrafficView"))?TEXT("traffic_inspection"):LandmarkIndex>0?TEXT("landmark"):FParse::Param(FCommandLine::Get(),TEXT("ParisTwinEye"))?TEXT("eye_1.7m"):TEXT("overview"));J->SetBoolField(TEXT("detailed_surfaces"),bDetailedSurfaces&&DetailQuality>0);J->SetBoolField(TEXT("photographic_surfaces"),!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinProceduralSurfaces"))&&bDetailedSurfaces&&DetailQuality>0);J->SetStringField(TEXT("surface_recipe"),FParse::Param(FCommandLine::Get(),TEXT("ParisTwinProceduralSurfaces"))?TEXT("original_periodic_pbr_v1"):TEXT("cc0_photo_orm_dx_v1"));AddParisRenderCacheStats(this,J);AddParisPhotoEnvironmentStats(GetWorld(),J);AddParisPhotoDetailStats(this,J);FString Output;FJsonSerializer::Serialize(J,TJsonWriterFactory<>::Create(&Output));FFileHelper::SaveStringToFile(Output,*(FPaths::ProjectSavedDir()/TEXT("paris-twin-performance.json")));UE_LOG(LogTemp,Display,TEXT("PARIS_TWIN_BENCHMARK %s"),*Output);if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinExit")))FPlatformMisc::RequestExit(false);}}
}
struct FParisButton{int32 Action;FString Label;FVector2D Position,Size;};
static TArray<FParisButton> ParisButtons(float Width,bool Help=false) {
    const TArray<FString> Labels={TEXT("Overview [F2]"),TEXT("Fly [F3]"),TEXT("Footprints [F5]"),TEXT("Issues [F4]"),TEXT("Notre-Dame [1]"),TEXT("Chapelle [2]"),TEXT("St-Michel [3]"),TEXT("Help [H]"),TEXT("Props [F6]"),TEXT("Quality [F7]"),TEXT("Walk [F8]"),TEXT("View [V]"),TEXT("People [P]"),TEXT("Traffic [T]"),TEXT("Cafes [B]"),TEXT("Surfaces [M]")};
    TArray<int32> Order={0,1,10,11,12,8,9,4,5,6,7};if(Help){Order.Add(2);Order.Add(3);Order.Add(13);Order.Add(14);Order.Add(15);}
    TArray<FParisButton> Result;float X=16,Y=36;
    for(int32 I:Order){const float W=Labels[I].Len()*7.f+18;if(X+W>Width-16&&X>16){X=16;Y+=34;}Result.Add({I,Labels[I],FVector2D(X,Y),FVector2D(W,28)});X+=W+5;}return Result;
}
bool AParisTwinHUD::HandleClick(const FVector2D& P) {
    if(!Canvas)return false;auto C=Cast<AParisTwinController>(PlayerOwner);if(!C)return false;
    for(const auto& B:ParisButtons(Canvas->SizeX,bHelp))if(P.X>=B.Position.X&&P.X<=B.Position.X+B.Size.X&&P.Y>=B.Position.Y&&P.Y<=B.Position.Y+B.Size.Y){switch(B.Action){case 0:C->Overview();break;case 1:C->Eye();break;case 2:C->ToggleFootprints();break;case 3:C->ToggleIssues();break;case 4:C->LandmarkOne();break;case 5:C->LandmarkTwo();break;case 6:C->LandmarkThree();break;case 7:C->ToggleHelp();break;case 8:C->ToggleStreetDetails();break;case 9:C->CycleDetailQuality();break;case 10:C->Walk();break;case 11:C->ToggleWalkView();break;case 12:C->TogglePeople();break;case 13:C->ToggleTraffic();break;case 15:C->ToggleSurfaces();break;default:C->InspectBusiness();break;}return true;}
    return P.Y<ParisButtons(Canvas->SizeX,bHelp).Last().Position.Y+38;
}
void AParisTwinHUD::DrawHUD() {
    Super::DrawHUD();auto S=Twin(GetWorld());if(!S||!Canvas)return;
    auto Text=[this](const FString& Message,float X,float Y,float Scale=1.f){Canvas->SetDrawColor(FColor::White);Canvas->DrawText(GEngine->GetSmallFont(),Message,X,Y,Scale,Scale,FFontRenderInfo());};
    const auto Buttons=ParisButtons(Canvas->SizeX,bHelp);const float Bottom=Buttons.Last().Position.Y+38;
    DrawRect(FLinearColor(.015f,.02f,.03f,.88f),8,8,Canvas->SizeX-16,Bottom-8);
    Text(FString::Printf(TEXT("PARIS DIGITAL TWIN | %d buildings | %d storefronts + %d terraces | %d people + %d cars (simulated) | %s"),S->BuildingCount,S->BusinessCount,S->TerraceCount,S->Crowd?S->Crowd->People().Num():0,S->Traffic?S->Traffic->Vehicles().Num():0,S->DetailQuality==0?TEXT("LOW"):S->DetailQuality==1?TEXT("MEDIUM"):TEXT("HIGH")),16,15,1.05f);
    for(const auto& B:Buttons){const bool Active=(B.Action==2&&S->bFootprints)||(B.Action==3&&S->bIssues)||(B.Action==7&&bHelp)||(B.Action==8&&S->bStreetDetails)||(B.Action==10&&Cast<AParisWalker>(PlayerOwner->GetPawn()))||(B.Action==12&&S->bPeople)||(B.Action==13&&S->bTraffic)||(B.Action==15&&S->bDetailedSurfaces&&S->DetailQuality>0);DrawRect(Active?FLinearColor(.04f,.35f,.4f,1):FLinearColor(.12f,.17f,.23f,1),B.Position.X,B.Position.Y,B.Size.X,B.Size.Y);Text(B.Label,B.Position.X+10,B.Position.Y+7);}
    if(bHelp){DrawRect(FLinearColor(.015f,.02f,.03f,.93f),8,Bottom+4,FMath::Min(720.f,float(Canvas->SizeX-16)),116);Text(TEXT("Hold RIGHT mouse button and move the mouse to rotate. Release to show cursor."),16,Bottom+12);Text(TEXT("WASD: move | F8: walk with gravity | V: first/third person | Shift: run | F2: overview"),16,Bottom+36);Text(TEXT("Click a building, road or river for its source ID and the actual clicked coordinates."),16,Bottom+60);Text(TEXT("F1: building accuracy | F4/F5: issues/footprints | F9: shot | P/T: people/cars | C: car view | B: cafes | M: surfaces | N: paths | 4/5/6: photo cameras"),16,Bottom+84);}
    if(S->bIssues){DrawRect(FLinearColor(.07f,.025f,.01f,.88f),8,Bottom+(bHelp?126:4),FMath::Min(720.f,float(Canvas->SizeX-16)),42);Text(S->IssueSummary,16,Bottom+(bHelp?134:12));Text(TEXT("Red: source overlap | Orange: separate road paths (review; not automatically errors)"),16,Bottom+(bHelp?152:30));}
    const FString Inspector=S->InspectionText();if(!Inspector.IsEmpty()){TArray<FString> Lines;Inspector.ParseIntoArrayLines(Lines);const float Height=Lines.Num()*19+16,Y=Canvas->SizeY-50-Height;DrawRect(FLinearColor(.015f,.02f,.03f,.9f),8,Y,Canvas->SizeX-16,Height);for(int32 I=0;I<Lines.Num();I++)Text(Lines[I],16,Y+8+I*19);}
    DrawRect(FLinearColor(.015f,.02f,.03f,.85f),8,Canvas->SizeY-48,Canvas->SizeX-16,44);
    const auto Walker=Cast<AParisWalker>(PlayerOwner->GetPawn());
    const FString Movement=Walker?(Walker->bThirdPerson?TEXT("THIRD PERSON | "):TEXT("FIRST PERSON 1.7m | "))+FString(TEXT("WASD walk | Shift run | Right-drag look | V view | F2 overview")):TEXT("Right-drag: look | WASD: fly | F8: walk with gravity | V: third person | P/T: people/cars | C: car view | B: cafes");
    Text(Movement,16,Canvas->SizeY-42);
    Text(TEXT("OpenStreetMap contributors / Ville de Paris (ODbL) | IGN BD TOPO / RGE ALTI (Etalab 2.0)"),16,Canvas->SizeY-22,.85f);
}
