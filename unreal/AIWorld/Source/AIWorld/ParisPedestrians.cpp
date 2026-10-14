#include "ParisPedestrians.h"
#include "ParisStreetMeshes.h"
#include "ParisWalker.h"
#include "WorldProtocol.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Materials/MaterialInterface.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "GameFramework/PlayerController.h"
using namespace AIWorld;

static bool CrowdVector(const TSharedPtr<FJsonValue>& V,FVector& P) {
    if(!V.IsValid()||V->Type!=EJson::Array||V->AsArray().Num()!=3)return false;
    const auto& A=V->AsArray();P=FVector(A[0]->AsNumber(),A[1]->AsNumber(),A[2]->AsNumber());return !P.ContainsNaN();
}
FString ParisPersonPartModel(int32 Part,int32 Variant){return Part==0?FString::Printf(TEXT("person_torso_%d"),Variant):Part==1?TEXT("person_head"):Part<4?FString::Printf(TEXT("person_arm_%d"),Variant):TEXT("person_leg");}
TArray<FTransform> ParisPersonPose(const FVector& Root,double Yaw,double Phase,bool Moving) {
    const double Swing=Moving?FMath::Sin(Phase)*18:0;
    const FTransform Base(FRotator(0,Yaw,0),Root+FVector(0,0,Moving?-4*FMath::Abs(FMath::Sin(Phase)):0));
    TArray<FTransform> Result;
    Result.Add(FTransform::Identity*Base);
    Result.Add(FTransform(FVector(0,0,146))*Base);
    Result.Add(FTransform(FRotator(-Swing*1.3,0,0),FVector(0,-23,139))*Base);
    Result.Add(FTransform(FRotator(Swing*1.3,0,0),FVector(0,23,139))*Base);
    Result.Add(FTransform(FRotator(Swing,0,0),FVector(0,-9,84))*Base);
    Result.Add(FTransform(FRotator(-Swing,0,0),FVector(0,9,84))*Base);
    return Result;
}
FVector FParisPedestrianRoute::Sample(double Distance,double Direction,double* Yaw) const {
    if(Points.Num()<2)return FVector::ZeroVector;
    Distance=FMath::Clamp(Distance,0.,Length);int32 Lo=1,Hi=Distances.Num()-1;
    while(Lo<Hi){const int32 Mid=(Lo+Hi)/2;if(Distances[Mid]<Distance)Lo=Mid+1;else Hi=Mid;}
    const double T=(Distance-Distances[Lo-1])/FMath::Max(.001,Distances[Lo]-Distances[Lo-1]);
    if(Yaw)*Yaw=((Points[Lo]-Points[Lo-1])*Direction).Rotation().Yaw;
    return FMath::Lerp(Points[Lo-1],Points[Lo],T);
}
AParisPedestrianCrowd::AParisPedestrianCrowd(){PrimaryActorTick.bCanEverTick=true;RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("CrowdRoot"));}
bool AParisPedestrianCrowd::Initialize(const TSharedPtr<FJsonObject>& Data){
    if(!Data.IsValid())return false;
    auto Cloth=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisCloth.M_ParisCloth"));
    auto Skin=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisSkin.M_ParisSkin"));
    if(!Cloth||!Skin)return false;
    for(const auto& V:Array(Data,TEXT("models"))){auto J=V->AsObject();const FString Name=String(J,TEXT("id"));auto Mesh=BuildParisStreetMesh(this,J,Name==TEXT("person_head")?Skin:Cloth);if(!Mesh)return false;Models.Add(Mesh);ModelByName.Add(Name,Mesh);}
    TMap<FString,int32> RouteByID;
    for(const auto& V:Array(Data,TEXT("routes"))){auto J=V->AsObject();FParisPedestrianRoute Route;Route.ID=String(J,TEXT("id"));Route.SourceID=String(J,TEXT("source_id"));Route.SourceURL=String(J,TEXT("source_url"));Route.PlacementSource=String(J,TEXT("route_source"));
        for(const auto& P:Array(J,TEXT("points_cm"))){FVector Point;if(!CrowdVector(P,Point))return false;if(!Route.Points.IsEmpty()){const double Distance=(Point-Route.Points.Last()).Size2D();if(Distance<.001)continue;Route.Length+=Distance;}Route.Points.Add(Point);Route.Distances.Add(Route.Length);}
        if(Route.Points.Num()<2||Route.Length<100||RouteByID.Contains(Route.ID))return false;RouteByID.Add(Route.ID,Routes.Num());Routes.Add(Route);
    }
    for(const auto& V:Array(Data,TEXT("agents"))){auto J=V->AsObject();const auto Route=RouteByID.Find(String(J,TEXT("route_id")));if(!Route||Agents.Num()>=512)return false;
        FParisPedestrian A;A.ID=String(J,TEXT("id"));A.Route=*Route;A.Variant=FMath::Clamp(int32(Number(J,TEXT("variant"))),0,2);A.Direction=Number(J,TEXT("direction"),1)>0?1:-1;A.Speed=Number(J,TEXT("speed_mps"),1.2)*100;A.Distance=FMath::Clamp(Number(J,TEXT("progress_m"))*100,0.,Routes[*Route].Length);A.Phase=Agents.Num()*.8;A.Position=Routes[*Route].Sample(A.Distance,A.Direction,&A.Yaw);Agents.Add(A);
    }
    for(auto& Pair:ModelByName){auto ISM=NewObject<UInstancedStaticMeshComponent>(this);AddInstanceComponent(ISM);ISM->SetupAttachment(RootComponent);ISM->SetStaticMesh(Pair.Value);ISM->SetMobility(EComponentMobility::Movable);ISM->SetCanEverAffectNavigation(false);ISM->SetCollisionEnabled(ECollisionEnabled::QueryOnly);ISM->SetCollisionResponseToAllChannels(ECR_Ignore);ISM->SetCollisionResponseToChannel(ECC_Visibility,ECR_Block);ISM->SetCastShadow(true);ISM->RegisterComponent();Instances.Add(ISM);InstanceByName.Add(Pair.Key,ISM);}
    bReady=true;SetDisplay(true,1);return true;
}
UStaticMesh* AParisPedestrianCrowd::Model(const FString& Name) const {auto Found=ModelByName.Find(Name);return Found?*Found:nullptr;}
void AParisPedestrianCrowd::SimulateStep(double Delta,const FVector* Player){
    Delta=FMath::Clamp(Delta,0.,.1);
    for(int32 I=0;I<Agents.Num();I++){auto& A=Agents[I];const auto& R=Routes[A.Route];A.Moving=false;
        if(A.Wait>0){A.Wait=FMath::Max(0.,A.Wait-Delta);continue;}
        const double Next=FMath::Clamp(A.Distance+A.Direction*A.Speed*Delta,0.,R.Length);const FVector Candidate=R.Sample(Next,A.Direction);bool Blocked=false;
        for(int32 J=0;J<Agents.Num();J++){if(I==J||FMath::Abs(Candidate.Z-Agents[J].Position.Z)>150)continue;const double New=FVector::DistSquared2D(Candidate,Agents[J].Position),Old=FVector::DistSquared2D(A.Position,Agents[J].Position);if(New<65*65&&New<Old){Blocked=true;break;}}
        if(Player&&FMath::Abs(Candidate.Z-Player->Z)<250&&FVector::DistSquared2D(Candidate,*Player)<80*80&&FVector::DistSquared2D(Candidate,*Player)<FVector::DistSquared2D(A.Position,*Player))Blocked=true;
        if(Blocked){A.BlockedAge+=Delta;if(A.BlockedAge>2.5){A.Direction*=-1;A.Wait=.4;A.BlockedAge=0;RecoveryTurns++;}continue;}
        A.BlockedAge=0;TravelledCm+=FVector::Dist2D(Candidate,A.Position);A.Distance=Next;A.Position=R.Sample(Next,A.Direction,&A.Yaw);A.Moving=true;A.Phase+=A.Speed*Delta*.035;
        if(Next<=.001||Next>=R.Length-.001){A.Direction*=-1;A.Wait=.8+(I%3)*.4;}
    }
}
void AParisPedestrianCrowd::UpdateInstances(bool TraceGround){
    TMap<FString,TArray<FTransform>> Transforms;TMap<FString,TArray<int32>> Lookup;
    for(int32 I=0;I<VisibleCount;I++){auto& A=Agents[I];
        if(TraceGround){FHitResult Hit;FCollisionQueryParams Params;Params.AddIgnoredActor(this);if(GetWorld()->LineTraceSingleByChannel(Hit,A.Position+FVector(0,0,80),A.Position-FVector(0,0,120),ECC_Pawn,Params)&&Hit.Normal.Z>.7)A.GroundOffset=Hit.ImpactPoint.Z-A.Position.Z;}
        const auto Pose=ParisPersonPose(A.Position+FVector(0,0,A.GroundOffset),A.Yaw,A.Phase,A.Moving);
        for(int32 P=0;P<6;P++){const FString Name=ParisPersonPartModel(P,A.Variant);Transforms.FindOrAdd(Name).Add(Pose[P]);Lookup.FindOrAdd(Name).Add(I);}
    }
    for(auto& Pair:InstanceByName){const auto Found=Transforms.Find(Pair.Key);auto ISM=Pair.Value;
        const TArray<FTransform> Empty;const auto& Items=Found?*Found:Empty;
        if(ISM->GetInstanceCount()!=Items.Num()){ISM->ClearInstances();ISM->AddInstances(Items,false,false,false);}else if(!Items.IsEmpty())ISM->BatchUpdateInstancesTransforms(0,Items,false,true,true);
        AgentByInstance.Add(ISM,Lookup.FindRef(Pair.Key));
    }
}
void AParisPedestrianCrowd::SetDisplay(bool Enabled,int32 Quality){
    bEnabled=Enabled;DetailQuality=FMath::Clamp(Quality,0,2);VisibleCount=bEnabled?FMath::Min(Agents.Num(),DetailQuality==0?80:160):0;
    for(auto ISM:Instances){ISM->SetVisibility(bEnabled);ISM->SetCollisionEnabled(bEnabled?ECollisionEnabled::QueryOnly:ECollisionEnabled::NoCollision);const int32 Distance=DetailQuality==0?10000:DetailQuality==1?20000:35000;ISM->SetCullDistances(Distance*.8,Distance);}
    UpdateInstances();
}
FString AParisPedestrianCrowd::DescribeHit(UPrimitiveComponent* Component,int32 Instance) const {
    const auto Lookup=AgentByInstance.Find(Component);if(!Lookup||!Lookup->IsValidIndex(Instance)||!Agents.IsValidIndex((*Lookup)[Instance]))return TEXT("");const auto& A=Agents[(*Lookup)[Instance]];const auto& R=Routes[A.Route];
    return FString::Printf(TEXT("%s | SIMULATED pedestrian (not observed population)\nRoad: %s | %s\n%s | speed %.2fm/s | %s\n%s"),*A.ID,*R.SourceID,*R.PlacementSource,*R.ID,A.Speed/100,A.Moving?TEXT("walking"):TEXT("waiting / yielding"),*R.SourceURL);
}
void AParisPedestrianCrowd::Tick(float Delta){
    Super::Tick(Delta);if(!bReady)return;SimAccumulator+=FMath::Min(double(Delta),.4);FVector Player;const FVector* Avoid=nullptr;if(auto PC=GetWorld()->GetFirstPlayerController())if(Cast<AParisWalker>(PC->GetPawn())){Player=PC->GetPawn()->GetActorLocation();Avoid=&Player;}
    while(SimAccumulator>=.05){SimulateStep(.05,Avoid);SimAccumulator-=.05;}
    RenderAccumulator+=Delta;GroundAccumulator+=Delta;if(bEnabled&&RenderAccumulator>=1./30){UpdateInstances(GroundAccumulator>.5);RenderAccumulator=0;if(GroundAccumulator>.5)GroundAccumulator=0;}
}
