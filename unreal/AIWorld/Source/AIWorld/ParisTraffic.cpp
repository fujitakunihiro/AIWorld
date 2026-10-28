#include "ParisTraffic.h"
#include "ParisBridgeDetail.h"
#include "ParisStreetMeshes.h"
#include "ParisWalker.h"
#include "Camera/PlayerCameraManager.h"
#include "WorldProtocol.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Materials/MaterialInterface.h"
#include "PhysicsEngine/BodySetup.h"
#include "GameFramework/PlayerController.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
using namespace AIWorld;

static bool TrafficVector(const TSharedPtr<FJsonValue>& V,FVector& P){
    if(!V.IsValid()||V->Type!=EJson::Array||V->AsArray().Num()!=3)return false;
    const auto& A=V->AsArray();P=FVector(A[0]->AsNumber(),A[1]->AsNumber(),A[2]->AsNumber());return !P.ContainsNaN();
}
AParisTraffic::AParisTraffic(){PrimaryActorTick.bCanEverTick=true;RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("TrafficRoot"));}
void AParisTraffic::LoadDetailedVisuals(){
    if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinSimpleCars")))return;
    FString Text;TSharedPtr<FJsonObject> Data;
    if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("Data/paris-vehicles.json")))||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Data)||!Data)return;
    if(String(Data,TEXT("recipe"))!=TEXT("paris_sedan_pbr_v1")||String(Data,TEXT("license"))!=TEXT("CC0-1.0")||Number(Data,TEXT("swept_radius_cm"))>240)return;
    const double Radius=Number(Data,TEXT("wheel_radius_cm")),Base=Number(Data,TEXT("wheelbase_cm"));
    if(Radius<25||Radius>40||Base<220||Base>290||Array(Data,TEXT("parts")).Num()!=6)return;
    TMap<FString,UStaticMesh*> Validated;TMap<FString,FVector> Pivots;
    const TSet<FString> Allowed{TEXT("body"),TEXT("windows"),TEXT("wheel_front_left"),TEXT("wheel_front_right"),TEXT("wheel_rear_left"),TEXT("wheel_rear_right")};
    for(const auto& V:Array(Data,TEXT("parts"))){
        auto J=V->AsObject();const FString ID=String(J,TEXT("id")),Path=String(J,TEXT("asset"));FVector Pivot;
        if(!Allowed.Contains(ID)||Validated.Contains(ID)||!Path.StartsWith(TEXT("/Game/ParisPhotoreal/Vehicles/SM_ParisSedan_"))||!TrafficVector(J->TryGetField(TEXT("pivot_cm")),Pivot)||Pivot.ContainsNaN()||Pivot.Size()>250)return;
        auto Mesh=LoadObject<UStaticMesh>(nullptr,*Path);if(!Mesh)return;
        if(ID==TEXT("body")){auto Setup=Mesh->GetBodySetup();if(!Setup||Setup->AggGeom.GetElementCount()<1)return;Setup->CollisionTraceFlag=CTF_UseSimpleAsComplex;}
        Validated.Add(ID,Mesh);if(ID.StartsWith(TEXT("wheel_")))Pivots.Add(TEXT("detail_")+ID,Pivot);
    }
    for(const auto& Pair:Validated){
        Models.Add(Pair.Value);auto ISM=NewObject<UInstancedStaticMeshComponent>(this);AddInstanceComponent(ISM);ISM->SetupAttachment(RootComponent);ISM->SetStaticMesh(Pair.Value);ISM->SetMobility(EComponentMobility::Movable);ISM->SetNumCustomDataFloats(2);ISM->SetHasPerInstancePrevTransforms(true);ISM->SetCanEverAffectNavigation(false);ISM->SetCollisionResponseToAllChannels(ECR_Ignore);ISM->SetCollisionResponseToChannel(ECC_Visibility,Pair.Key==TEXT("body")?ECR_Block:ECR_Ignore);ISM->SetCollisionEnabled(ECollisionEnabled::NoCollision);ISM->ComponentTags.Add(TEXT("ParisDetailedCar"));
        if(Pair.Key==TEXT("body"))ISM->ComponentTags.Add(TEXT("ParisCarBody"));
        if(Pair.Key==TEXT("windows"))ISM->ComponentTags.Add(TEXT("ParisCarGlass"));
        ISM->SetCastShadow(Pair.Key!=TEXT("windows")&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoShadows")));ISM->RegisterComponent();Meshes.Add(ISM);MeshByName.Add(TEXT("detail_")+Pair.Key,ISM);
    }
    WheelPivots=MoveTemp(Pivots);WheelRadius=Radius;WheelBase=Base;bDetailedReady=true;
}
bool AParisTraffic::Initialize(const TSharedPtr<FJsonObject>& Data){
    if(!Data.IsValid())return false;
    auto Paint=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisVehicle.M_ParisVehicle"));
    auto Glass=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisGlass.M_ParisGlass"));
    auto Rubber=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisCloth.M_ParisCloth"));
    auto Metal=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisIron.M_ParisIron"));
    if(!Paint||!Glass||!Rubber||!Metal)return false;
    for(const auto& V:Array(Data,TEXT("models"))){auto J=V->AsObject();const FString Name=String(J,TEXT("id"));auto Model=BuildParisStreetMesh(this,J,Name==TEXT("car_glass")?Glass:Name==TEXT("car_metal")?Metal:Name==TEXT("car_rubber")?Rubber:Paint);if(!Model)return false;Models.Add(Model);
        auto ISM=NewObject<UInstancedStaticMeshComponent>(this);AddInstanceComponent(ISM);ISM->SetupAttachment(RootComponent);ISM->SetStaticMesh(Model);ISM->SetMobility(EComponentMobility::Movable);ISM->SetCanEverAffectNavigation(false);ISM->SetCollisionEnabled(ECollisionEnabled::QueryOnly);ISM->SetCollisionResponseToAllChannels(ECR_Ignore);ISM->SetCollisionResponseToChannel(ECC_Visibility,ECR_Block);ISM->SetCastShadow(!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoShadows")));ISM->RegisterComponent();Meshes.Add(ISM);MeshByName.Add(Name,ISM);
    }
    TMap<FString,int32> RouteByID;
    for(const auto& V:Array(Data,TEXT("routes"))){auto J=V->AsObject();FParisPedestrianRoute R;R.ID=String(J,TEXT("id"));R.SourceID=String(J,TEXT("source_id"));R.SourceURL=String(J,TEXT("source_url"));R.PlacementSource=String(J,TEXT("route_source"));
        for(const auto& P:Array(J,TEXT("points_cm"))){FVector Point;if(!TrafficVector(P,Point))return false;if(!R.Points.IsEmpty()){const double D=(Point-R.Points.Last()).Size2D();if(D<.001)continue;R.Length+=D;}R.Points.Add(Point);R.Distances.Add(R.Length);}
        if(R.Points.Num()<2||R.Length<100||RouteByID.Contains(R.ID))return false;RouteByID.Add(R.ID,Routes.Num());Routes.Add(R);
    }
    TSet<FString> IDs;
    for(const auto& V:Array(Data,TEXT("agents"))){auto J=V->AsObject();const auto R=RouteByID.Find(String(J,TEXT("route_id")));const FString ID=String(J,TEXT("id"));if(!R||Cars.Num()>=128||IDs.Contains(ID))return false;IDs.Add(ID);
        FParisVehicle A;A.ID=ID;A.Route=*R;A.Variant=FMath::Clamp(int32(Number(J,TEXT("variant"))),0,2);A.Speed=Number(J,TEXT("speed_mps"))*100;if(A.Speed<=0||A.Speed>501)return false;A.Distance=FMath::Clamp(Number(J,TEXT("progress_m"))*100,0.,Routes[*R].Length);A.Position=Routes[*R].Sample(A.Distance,1,&A.Yaw);Cars.Add(A);
    }
    LoadDetailedVisuals();bFrozen=FParse::Param(FCommandLine::Get(),TEXT("ParisTwinFreezeTraffic"));
    bReady=true;SetDisplay(true,1);return true;
}
void AParisTraffic::SimulateStep(double Delta,const FVector* Player,const TArray<FVector>& People){
    if(bFrozen)return;
    Delta=FMath::Clamp(Delta,0.,.1);
    for(int32 I=0;I<Cars.Num();I++){auto& A=Cars[I];const auto& R=Routes[A.Route];A.bMoving=false;
        if(A.Wait>0){A.Wait=FMath::Max(0.,A.Wait-Delta);continue;}
        const double Next=A.bActive?FMath::Min(R.Length,A.Distance+A.Speed*Delta):0.;const FVector Candidate=R.Sample(Next,1);bool Blocked=false;
        auto Near=[&](const FVector& P,double Radius,bool Approaching){return FMath::Abs(Candidate.Z-P.Z)<200&&FVector::DistSquared2D(Candidate,P)<Radius*Radius&&(!Approaching||FVector::DistSquared2D(Candidate,P)<FVector::DistSquared2D(A.Position,P));};
        for(int32 J=0;J<Cars.Num();J++)if(I!=J&&Cars[J].bActive&&Near(Cars[J].Position,550,A.bActive)){Blocked=true;break;}
        if(Player&&Near(*Player,360,false))Blocked=true;
        for(const auto& P:People)if(Near(P,340,false)){Blocked=true;break;}
        if(Blocked){YieldSteps++;continue;}
        if(!A.bActive){A.bActive=true;A.Distance=0;A.Position=Candidate;A.Yaw=(R.Points[1]-R.Points[0]).Rotation().Yaw;Recycles++;continue;}
        const double Moved=FVector::Dist2D(Candidate,A.Position);TravelledCm+=Moved;A.WheelPhase=FMath::Fmod(A.WheelPhase+Moved/WheelRadius,2.*PI);A.Distance=Next;A.Position=R.Sample(Next,1,&A.Yaw);A.bMoving=true;
        // Hide at the segment end; recycle only after a delay and an empty start.
        if(Next>=R.Length-.001){A.bActive=false;A.Wait=1.5+(I%3)*.5;}
    }
}
void AParisTraffic::UpdateInstances(){
    TMap<FString,TArray<FTransform>> Items;TMap<FString,TArray<int32>> Lookup;
    FCollisionQueryParams GroundQuery;GroundQuery.AddIgnoredActor(this);if(Crowd)GroundQuery.AddIgnoredActor(Crowd);
    if(auto PC=GetWorld()->GetFirstPlayerController())if(PC->GetPawn())GroundQuery.AddIgnoredActor(PC->GetPawn());
    auto RoadHeight=[&](FVector& Point){
        double Z=0;if(ParisBridgeVisualHeight(GetWorld(),Point,Z))Point.Z=Z;
        // The archived route samples a terrain model; a rendered road triangle
        // can interpolate a different height between samples. Snap only the
        // visual pose to the actual walkable road, never alter the GIS route.
        FHitResult Floor;
        if(GetWorld()->LineTraceSingleByChannel(Floor,Point+FVector(0,0,500),Point-FVector(0,0,1000),ECC_Pawn,GroundQuery)&&Floor.ImpactNormal.Z>.65)Point.Z=Floor.ImpactPoint.Z+1.5;
    };
    TArray<int32> Visible;FVector View=FVector::ZeroVector;
    if(auto PC=GetWorld()->GetFirstPlayerController())if(PC->PlayerCameraManager)View=PC->PlayerCameraManager->GetCameraLocation();
    const double Range=DetailQuality==0?12000:DetailQuality==1?25000:45000;
    for(int32 I=0;I<Cars.Num();I++)if(Cars[I].bActive&&FVector::DistSquared2D(Cars[I].Position,View)<=Range*Range)Visible.Add(I);
    Visible.Sort([&](int32 A,int32 B){const double DA=FVector::DistSquared2D(Cars[A].Position,View),DB=FVector::DistSquared2D(Cars[B].Position,View);return DA==DB?A<B:DA<DB;});
    if(Visible.Num()>VisibleBudget)Visible.SetNum(VisibleBudget);RenderedCount=Visible.Num();DetailedRenderedCount=bDetailedActive?RenderedCount:0;
    for(int32 I:Visible){const auto& A=Cars[I];const auto& R=Routes[A.Route];
        FVector Ground=A.Position,Before=R.Sample(A.Distance-WheelBase*.5,1),After=R.Sample(A.Distance+WheelBase*.5,1);
        RoadHeight(Ground);RoadHeight(Before);RoadHeight(After);
        const FVector Slope=After-Before;const FTransform T(FRotator(Slope.Rotation().Pitch,A.Yaw,0),Ground);
        if(bDetailedActive){
            for(const FString& Name:{FString(TEXT("detail_body")),FString(TEXT("detail_windows"))}){Items.FindOrAdd(Name).Add(T);Lookup.FindOrAdd(Name).Add(I);}
            // Roll by actual travelled distance, not elapsed time. Waiting cars
            // keep their wheel phase. Steering follows the original lane bend.
            double Yaw0=0,Yaw1=0;R.Sample(A.Distance-100,1,&Yaw0);R.Sample(A.Distance+100,1,&Yaw1);
            const double Steering=FMath::Clamp(FMath::Atan(WheelBase*FMath::FindDeltaAngleRadians(FMath::DegreesToRadians(Yaw0),FMath::DegreesToRadians(Yaw1))/200.),-.45,.45);
            for(const auto& Wheel:WheelPivots){const double Steer=Wheel.Key.Contains(TEXT("front"))?Steering:0.;const FQuat Spin(FVector::YAxisVector,A.WheelPhase),Turn(FVector::UpVector,Steer);const FTransform Local(Turn*Spin,Wheel.Value);Items.FindOrAdd(Wheel.Key).Add(Local*T);Lookup.FindOrAdd(Wheel.Key).Add(I);}
        }else for(const FString& Name:{FString::Printf(TEXT("car_body_%d"),A.Variant),FString(TEXT("car_glass")),FString(TEXT("car_rubber")),FString(TEXT("car_metal"))}){Items.FindOrAdd(Name).Add(T);Lookup.FindOrAdd(Name).Add(I);}
    }
    for(auto& Pair:MeshByName){
        auto ISM=Pair.Value;const auto& Transforms=Items.FindOrAdd(Pair.Key);const auto& IDs=Lookup.FindOrAdd(Pair.Key);TArray<FTransform> Previous;
        if(ISM->ComponentHasTag(TEXT("ParisDetailedCar"))){
            // Visibility sorting can move an agent to a different instance
            // slot. Motion history follows the vehicle ID, never that slot.
            TMap<int32,FTransform> OldPoses;
            if(const auto OldIDs=CarByInstance.Find(ISM))for(int32 J=0;J<OldIDs->Num()&&J<ISM->GetInstanceCount();J++){FTransform Old;ISM->GetInstanceTransform(J,Old,false);OldPoses.Add((*OldIDs)[J],Old);}
            for(int32 J=0;J<IDs.Num();J++){const auto Old=OldPoses.Find(IDs[J]);Previous.Add(Old&&FVector::DistSquared(Old->GetLocation(),Transforms[J].GetLocation())<150*150?*Old:Transforms[J]);}
        }
        if(ISM->GetInstanceCount()!=Transforms.Num()){ISM->ClearInstances();ISM->AddInstances(Transforms,false,false,false);}
        if(!Transforms.IsEmpty()){
            if(!Previous.IsEmpty())ISM->BatchUpdateInstancesTransforms(0,Transforms,Previous,false,false,false);
            else ISM->BatchUpdateInstancesTransforms(0,Transforms,false,false,false);
        }
        if(ISM->NumCustomDataFloats==2)for(int32 J=0;J<IDs.Num();J++){const int32 I=IDs[J];ISM->SetCustomDataValue(J,0,float((I*5+Cars[I].Variant)%6),false);ISM->SetCustomDataValue(J,1,Cars[I].bMoving?0.f:1.f,false);}ISM->MarkRenderStateDirty();CarByInstance.Add(ISM,IDs);
    }
}
void AParisTraffic::SetDisplay(bool Enabled,int32 Quality){
    bEnabled=Enabled;DetailQuality=FMath::Clamp(Quality,0,2);bDetailedActive=bDetailedReady&&DetailQuality>0;VisibleBudget=bEnabled?FMath::Min(Cars.Num(),DetailQuality==0?20:40):0;
    const int32 Distance=DetailQuality==0?12000:DetailQuality==1?25000:45000;
    for(auto ISM:Meshes){const bool Visible=bEnabled&&(ISM->ComponentHasTag(TEXT("ParisDetailedCar"))==bDetailedActive);ISM->SetVisibility(Visible);ISM->SetCollisionEnabled(Visible?ECollisionEnabled::QueryOnly:ECollisionEnabled::NoCollision);ISM->SetCullDistances(Distance*.8,Distance);}UpdateInstances();
}
void AParisTraffic::AddVisualStats(const TSharedPtr<FJsonObject>& Report) const {
    int32 Batches=0,Nanite=0;int64 FallbackTriangles=0;
    for(auto Mesh:Meshes)if(Mesh->ComponentHasTag(TEXT("ParisDetailedCar"))){Batches++;if(auto Model=Mesh->GetStaticMesh()){Nanite+=Model->HasValidNaniteData()?1:0;FallbackTriangles+=int64(Model->GetNumTriangles(0))*Mesh->GetInstanceCount();}}
    Report->SetBoolField(TEXT("detailed_vehicle_assets_ready"),bDetailedReady);Report->SetBoolField(TEXT("detailed_vehicle_mode"),bDetailedActive);Report->SetNumberField(TEXT("detailed_vehicles_rendered"),DetailedRenderedCount);Report->SetNumberField(TEXT("detailed_vehicle_batches"),Batches);Report->SetNumberField(TEXT("vehicle_nanite_batches"),Nanite);Report->SetNumberField(TEXT("vehicle_fallback_triangles_before_culling"),double(FallbackTriangles));Report->SetNumberField(TEXT("vehicle_tire_radius_cm"),WheelRadius);Report->SetBoolField(TEXT("traffic_frozen_for_inspection"),bFrozen);Report->SetStringField(TEXT("vehicle_appearance_source"),TEXT("Mike Pan and Morgan McGuire, CC0 archived sedan; authored PBR conversion; simulated traffic"));
}
FString AParisTraffic::DescribeHit(UPrimitiveComponent* Component,int32 Instance) const {
    const auto Found=CarByInstance.Find(Component);if(!Found||!Found->IsValidIndex(Instance)||!Cars.IsValidIndex((*Found)[Instance]))return TEXT("");const auto& A=Cars[(*Found)[Instance]];const auto& R=Routes[A.Route];
    return FString::Printf(TEXT("%s | SIMULATED car (not observed traffic)\nRoad: %s | directed lane; inferred width/vehicle\n%s | %.2fm/s preview | %s\n%s\nVisual: %s"),*A.ID,*R.SourceID,*R.ID,A.Speed/100,A.bMoving?TEXT("moving"):TEXT("yielding / waiting"),*R.SourceURL,bDetailedActive?TEXT("CC0 detailed sedan; authored paint / glass / lights; distance-driven wheels"):TEXT("original compact-car proxy"));
}
void AParisTraffic::Tick(float Delta){
    Super::Tick(Delta);if(!bReady)return;SimAccumulator+=FMath::Min(double(Delta),.4);FVector Player;const FVector* Avoid=nullptr;
    if(auto PC=GetWorld()->GetFirstPlayerController())if(Cast<AParisWalker>(PC->GetPawn())){Player=PC->GetPawn()->GetActorLocation();Avoid=&Player;}
    TArray<FVector> People;if(Crowd)for(const auto& A:Crowd->People())People.Add(A.Position);
    while(SimAccumulator>=.05){SimulateStep(.05,Avoid,People);SimAccumulator-=.05;}
    RenderAccumulator+=Delta;if(bEnabled&&RenderAccumulator>=1./(bDetailedActive?60:DetailQuality==0?15:30)){UpdateInstances();RenderAccumulator=0;}
}
