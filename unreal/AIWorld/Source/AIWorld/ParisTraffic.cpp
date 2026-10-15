#include "ParisTraffic.h"
#include "ParisStreetMeshes.h"
#include "ParisWalker.h"
#include "Camera/PlayerCameraManager.h"
#include "WorldProtocol.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Materials/MaterialInterface.h"
#include "GameFramework/PlayerController.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
using namespace AIWorld;

static bool TrafficVector(const TSharedPtr<FJsonValue>& V,FVector& P){
    if(!V.IsValid()||V->Type!=EJson::Array||V->AsArray().Num()!=3)return false;
    const auto& A=V->AsArray();P=FVector(A[0]->AsNumber(),A[1]->AsNumber(),A[2]->AsNumber());return !P.ContainsNaN();
}
AParisTraffic::AParisTraffic(){PrimaryActorTick.bCanEverTick=true;RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("TrafficRoot"));}
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
    bReady=true;SetDisplay(true,1);return true;
}
void AParisTraffic::SimulateStep(double Delta,const FVector* Player,const TArray<FVector>& People){
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
        TravelledCm+=FVector::Dist2D(Candidate,A.Position);A.Distance=Next;A.Position=R.Sample(Next,1,&A.Yaw);A.bMoving=true;
        // Hide at the segment end; recycle only after a delay and an empty start.
        if(Next>=R.Length-.001){A.bActive=false;A.Wait=1.5+(I%3)*.5;}
    }
}
void AParisTraffic::UpdateInstances(){
    TMap<FString,TArray<FTransform>> Items;TMap<FString,TArray<int32>> Lookup;
    TArray<int32> Visible;FVector View=FVector::ZeroVector;
    if(auto PC=GetWorld()->GetFirstPlayerController())if(PC->PlayerCameraManager)View=PC->PlayerCameraManager->GetCameraLocation();
    const double Range=DetailQuality==0?12000:DetailQuality==1?25000:45000;
    for(int32 I=0;I<Cars.Num();I++)if(Cars[I].bActive&&FVector::DistSquared2D(Cars[I].Position,View)<=Range*Range)Visible.Add(I);
    Visible.Sort([&](int32 A,int32 B){const double DA=FVector::DistSquared2D(Cars[A].Position,View),DB=FVector::DistSquared2D(Cars[B].Position,View);return DA==DB?A<B:DA<DB;});
    if(Visible.Num()>VisibleBudget)Visible.SetNum(VisibleBudget);RenderedCount=Visible.Num();
    for(int32 I:Visible){const auto& A=Cars[I];const auto& R=Routes[A.Route];
        const FVector Slope=R.Sample(A.Distance+50,1)-R.Sample(A.Distance-50,1);const FTransform T(FRotator(Slope.Rotation().Pitch,A.Yaw,0),A.Position);
        for(const FString& Name:{FString::Printf(TEXT("car_body_%d"),A.Variant),FString(TEXT("car_glass")),FString(TEXT("car_rubber")),FString(TEXT("car_metal"))}){Items.FindOrAdd(Name).Add(T);Lookup.FindOrAdd(Name).Add(I);}
    }
    for(auto& Pair:MeshByName){auto ISM=Pair.Value;const auto& Transforms=Items.FindOrAdd(Pair.Key);if(ISM->GetInstanceCount()!=Transforms.Num()){ISM->ClearInstances();ISM->AddInstances(Transforms,false,false,false);}else if(!Transforms.IsEmpty())ISM->BatchUpdateInstancesTransforms(0,Transforms,false,true,true);CarByInstance.Add(ISM,Lookup.FindRef(Pair.Key));}
}
void AParisTraffic::SetDisplay(bool Enabled,int32 Quality){
    bEnabled=Enabled;DetailQuality=FMath::Clamp(Quality,0,2);VisibleBudget=bEnabled?FMath::Min(Cars.Num(),DetailQuality==0?20:40):0;
    const int32 Distance=DetailQuality==0?12000:DetailQuality==1?25000:45000;
    for(auto ISM:Meshes){ISM->SetVisibility(bEnabled);ISM->SetCollisionEnabled(bEnabled?ECollisionEnabled::QueryOnly:ECollisionEnabled::NoCollision);ISM->SetCullDistances(Distance*.8,Distance);}UpdateInstances();
}
FString AParisTraffic::DescribeHit(UPrimitiveComponent* Component,int32 Instance) const {
    const auto Found=CarByInstance.Find(Component);if(!Found||!Found->IsValidIndex(Instance)||!Cars.IsValidIndex((*Found)[Instance]))return TEXT("");const auto& A=Cars[(*Found)[Instance]];const auto& R=Routes[A.Route];
    return FString::Printf(TEXT("%s | SIMULATED car (not observed traffic)\nRoad: %s | directed lane; inferred width/vehicle\n%s | %.2fm/s preview | %s\n%s"),*A.ID,*R.SourceID,*R.ID,A.Speed/100,A.bMoving?TEXT("moving"):TEXT("yielding / waiting"),*R.SourceURL);
}
void AParisTraffic::Tick(float Delta){
    Super::Tick(Delta);if(!bReady)return;SimAccumulator+=FMath::Min(double(Delta),.4);FVector Player;const FVector* Avoid=nullptr;
    if(auto PC=GetWorld()->GetFirstPlayerController())if(Cast<AParisWalker>(PC->GetPawn())){Player=PC->GetPawn()->GetActorLocation();Avoid=&Player;}
    TArray<FVector> People;if(Crowd)for(const auto& A:Crowd->People())People.Add(A.Position);
    while(SimAccumulator>=.05){SimulateStep(.05,Avoid,People);SimAccumulator-=.05;}
    RenderAccumulator+=Delta;if(bEnabled&&RenderAccumulator>=1./(DetailQuality==0?15:30)){UpdateInstances();RenderAccumulator=0;}
}
