#include "ParisPedestrians.h"
#include "ParisStreetMeshes.h"
#include "ParisWalker.h"
#include "Camera/PlayerCameraManager.h"
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
    for(const auto& V:Array(Data,TEXT("destinations"))){auto J=V->AsObject();FParisVisitDestination D;D.ID=String(J,TEXT("id"));D.BusinessID=String(J,TEXT("business_id"));D.Name=String(J,TEXT("name"));
        auto Parent=RouteByID.Find(String(J,TEXT("parent_route_id")));auto Link=RouteByID.Find(String(J,TEXT("route_id")));if(!Parent||!Link||*Parent==*Link||Number(J,TEXT("capacity"))!=1)return false;
        D.ParentRoute=*Parent;D.Route=*Link;D.Entry=Number(J,TEXT("parent_distance_cm"));D.Dwell=Number(J,TEXT("dwell_seconds"));D.FacingYaw=Number(J,TEXT("facing_yaw_degrees"));
        if(!FMath::IsFinite(D.Entry)||D.Entry<0||D.Entry>Routes[*Parent].Length+.05||!FMath::IsFinite(D.Dwell)||D.Dwell<1||D.Dwell>60||!FMath::IsFinite(D.FacingYaw)||FVector::Dist(Routes[*Parent].Sample(D.Entry,1),Routes[*Link].Points[0])>.1)return false;
        D.Entry=FMath::Clamp(D.Entry,0.,Routes[*Parent].Length);
        for(const auto& Existing:Visits)if(Existing.ID==D.ID||Existing.BusinessID==D.BusinessID)return false;
        Visits.Add(D);
    }
    for(const auto& V:Array(Data,TEXT("agents"))){auto J=V->AsObject();const auto Route=RouteByID.Find(String(J,TEXT("route_id")));if(!Route||Agents.Num()>=512)return false;
        FParisPedestrian A;A.ID=String(J,TEXT("id"));A.Route=*Route;A.Variant=FMath::Clamp(int32(Number(J,TEXT("variant"))),0,2);A.Direction=Number(J,TEXT("direction"),1)>0?1:-1;A.Speed=Number(J,TEXT("speed_mps"),1.2)*100;A.Distance=FMath::Clamp(Number(J,TEXT("progress_m"))*100,0.,Routes[*Route].Length);A.Phase=Agents.Num()*.8;A.Position=Routes[*Route].Sample(A.Distance,A.Direction,&A.Yaw);Agents.Add(A);
    }
    for(auto& Pair:ModelByName){auto ISM=NewObject<UInstancedStaticMeshComponent>(this);AddInstanceComponent(ISM);ISM->SetupAttachment(RootComponent);ISM->SetStaticMesh(Pair.Value);ISM->SetMobility(EComponentMobility::Movable);ISM->SetCanEverAffectNavigation(false);ISM->SetCollisionEnabled(ECollisionEnabled::QueryOnly);ISM->SetCollisionResponseToAllChannels(ECR_Ignore);ISM->SetCollisionResponseToChannel(ECC_Visibility,ECR_Block);ISM->SetCastShadow(!Pair.Key.StartsWith(TEXT("person_far_"))&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoShadows")));ISM->RegisterComponent();Instances.Add(ISM);InstanceByName.Add(Pair.Key,ISM);}
    bReady=true;SetDisplay(true,1);return true;
}
UStaticMesh* AParisPedestrianCrowd::Model(const FString& Name) const {auto Found=ModelByName.Find(Name);return Found?*Found:nullptr;}
static void VisitAction(FParisPedestrian& A,const FString& Text){A.RecentActions.Add(Text);if(A.RecentActions.Num()>4)A.RecentActions.RemoveAt(0);}
void AParisPedestrianCrowd::FinishVisit(int32 Agent,bool Completed){
    auto& A=Agents[Agent];if(!Visits.IsValidIndex(A.Visit))return;auto& D=Visits[A.Visit];if(D.Owner==Agent)D.Owner=-1;
    A.LastVisit=D.BusinessID;A.Visit=-1;A.VisitStage=0;A.VisitCooldown=30+(Agent%17);A.VisitAge=0;A.Wait=.5;
    VisitAction(A,(Completed?TEXT("Returned from "):TEXT("Cancelled visit to "))+D.Name);if(Completed)CompletedVisits++;else AbortedVisits++;
}
void AParisPedestrianCrowd::SimulateStep(double Delta,const FVector* Player){
    Delta=FMath::Clamp(Delta,0.,.1);if(Delta<=0)return;
    for(int32 I=0;I<Agents.Num();I++){auto& A=Agents[I];A.Moving=false;A.VisitCooldown=FMath::Max(0.,A.VisitCooldown-Delta);
        if(A.VisitStage==0&&A.VisitCooldown<=0){
            int32 Best=-1;double Cost=TNumericLimits<double>::Max();
            for(int32 J=0;J<Visits.Num();J++){const auto& D=Visits[J];if(D.Owner>=0||D.ParentRoute!=A.Route)continue;
                const double Candidate=FMath::Abs(A.Distance-D.Entry)+2*Routes[D.Route].Length;
                if(Candidate<Cost){Cost=Candidate;Best=J;}
            }
            if(Best>=0){auto& D=Visits[Best];D.Owner=I;A.Visit=Best;A.VisitStage=1;A.VisitAge=0;A.bVisitAborted=false;A.ResumeDirection=A.Direction;A.Direction=A.Distance<=D.Entry?1:-1;A.Wait=0;
                A.VisitReason=FString::Printf(TEXT("Closest unreserved stop on this route: %.1fm walking (approach + return). One visitor per stop."),Cost/100);
                VisitAction(A,TEXT("Reserved ")+D.Name);
            }else A.VisitCooldown=3+(I%3);
        }
        if(A.VisitStage>0){auto& D=Visits[A.Visit];A.VisitAge+=Delta;
            if(A.VisitAge>90&&!A.bVisitAborted){A.bVisitAborted=true;VisitAction(A,TEXT("Visit timeout: returning safely"));
                if(A.VisitStage==1){FinishVisit(I,false);continue;}A.VisitStage=4;A.Direction=-1;A.Wait=0;
            }
            // A blocked return never teleports. Expire its reservation so the
            // simulation cannot keep a destination permanently locked.
            if(A.VisitAge>100&&D.Owner==I)D.Owner=-1;
        }
        if(A.Wait>0){A.Wait=FMath::Max(0.,A.Wait-Delta);if(A.VisitStage==3){A.Yaw=Visits[A.Visit].FacingYaw;if(A.Wait<=0){A.VisitStage=4;A.Direction=-1;VisitAction(A,TEXT("Finished stop; retracing approach"));}}continue;}
        const auto& R=Routes[A.Route];
        double Next=FMath::Clamp(A.Distance+A.Direction*A.Speed*Delta,0.,R.Length);
        if(A.VisitStage==1){const double Entry=Visits[A.Visit].Entry;Next=A.Direction>0?FMath::Min(Next,Entry):FMath::Max(Next,Entry);}
        const FVector Candidate=R.Sample(Next,A.Direction);bool Blocked=false;
        for(int32 J=0;J<Agents.Num();J++){if(I==J||FMath::Abs(Candidate.Z-Agents[J].Position.Z)>150)continue;const double New=FVector::DistSquared2D(Candidate,Agents[J].Position),Old=FVector::DistSquared2D(A.Position,Agents[J].Position);if(New<65*65&&New<Old){Blocked=true;break;}}
        if(Player&&FMath::Abs(Candidate.Z-Player->Z)<250&&FVector::DistSquared2D(Candidate,*Player)<80*80&&FVector::DistSquared2D(Candidate,*Player)<FVector::DistSquared2D(A.Position,*Player))Blocked=true;
        if(Blocked){A.BlockedAge+=Delta;if(A.BlockedAge>2.5){
                if(A.VisitStage==1){FinishVisit(I,false);A.Direction*=-1;}
                else if(A.VisitStage==2){A.bVisitAborted=true;A.VisitStage=4;A.Direction=-1;VisitAction(A,TEXT("Approach blocked; returning"));}
                else if(A.VisitStage==0)A.Direction*=-1;
                A.Wait=.4;A.BlockedAge=0;RecoveryTurns++;
            }continue;}
        A.BlockedAge=0;TravelledCm+=FVector::Dist2D(Candidate,A.Position);A.Moving=FMath::Abs(A.Distance-Next)>.001;A.Distance=Next;A.Position=R.Sample(Next,A.Direction,&A.Yaw);A.Phase+=A.Speed*Delta*.035;
        if(A.VisitStage==1&&FMath::Abs(Next-Visits[A.Visit].Entry)<.001){auto& D=Visits[A.Visit];A.Route=D.Route;A.Distance=0;A.Direction=1;A.Position=Routes[A.Route].Sample(0,1,&A.Yaw);A.VisitStage=2;VisitAction(A,TEXT("Walking clear approach to ")+D.Name);}
        else if(A.VisitStage==2&&Next>=R.Length-.001){auto& D=Visits[A.Visit];A.VisitStage=3;A.Wait=D.Dwell;A.Yaw=D.FacingYaw;A.Moving=false;VisitAction(A,FString::Printf(TEXT("Standing at %s for %.0fs (simulated)"),*D.Name,D.Dwell));}
        else if(A.VisitStage==4&&Next<=.001){auto& D=Visits[A.Visit];A.Route=D.ParentRoute;A.Distance=D.Entry;A.Direction=A.ResumeDirection;A.Position=Routes[A.Route].Sample(A.Distance,A.Direction,&A.Yaw);FinishVisit(I,!A.bVisitAborted);}
        else if(A.VisitStage==0&&(Next<=.001||Next>=R.Length-.001)){A.Direction*=-1;A.Wait=.8+(I%3)*.4;}
    }
}
void AParisPedestrianCrowd::UpdateInstances(bool TraceGround){
    TMap<FString,TArray<FTransform>> Transforms;TMap<FString,TArray<int32>> Lookup;
    TArray<int32> Visible;FVector View=FVector::ZeroVector;
    if(auto PC=GetWorld()->GetFirstPlayerController())if(PC->PlayerCameraManager)View=PC->PlayerCameraManager->GetCameraLocation();
    const double Range=DetailQuality==0?10000:DetailQuality==1?20000:35000;
    for(int32 I=0;I<Agents.Num();I++)if(FVector::DistSquared2D(Agents[I].Position,View)<=Range*Range)Visible.Add(I);
    Visible.Sort([&](int32 A,int32 B){const double DA=FVector::DistSquared2D(Agents[A].Position,View),DB=FVector::DistSquared2D(Agents[B].Position,View);return DA==DB?A<B:DA<DB;});
    if(Visible.Num()>VisibleCount)Visible.SetNum(VisibleCount);RenderedCount=Visible.Num();
    NearRenderedCount=0;FarRenderedCount=0;RenderedParts=0;StandingVisitorsRendered=0;
    const double NearRange=DetailQuality==0?2500:DetailQuality==1?4000:6000;
    const bool FullPeople=FParse::Param(FCommandLine::Get(),TEXT("ParisTwinFullPeople"));
    for(int32 I:Visible){auto& A=Agents[I];if(A.VisitStage==3)StandingVisitorsRendered++;
        if(TraceGround){FHitResult Hit;FCollisionQueryParams Params;Params.AddIgnoredActor(this);if(GetWorld()->LineTraceSingleByChannel(Hit,A.Position+FVector(0,0,80),A.Position-FVector(0,0,120),ECC_Pawn,Params)&&Hit.Normal.Z>.7)A.GroundOffset=Hit.ImpactPoint.Z-A.Position.Z;}
        const double Distance=FVector::Dist2D(A.Position,View);
        A.bFarPose=!FullPeople&&ModelByName.Contains(TEXT("person_far_0"))&&Distance>NearRange+(A.bFarPose?-200:200);
        if(A.bFarPose){const FString Name=FString::Printf(TEXT("person_far_%d"),A.Variant);Transforms.FindOrAdd(Name).Add(FTransform(FRotator(0,A.Yaw,0),A.Position+FVector(0,0,A.GroundOffset)));Lookup.FindOrAdd(Name).Add(I);FarRenderedCount++;RenderedParts++;continue;}
        NearRenderedCount++;RenderedParts+=6;
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
    const FString Goal=Visits.IsValidIndex(A.Visit)?Visits[A.Visit].Name:TEXT("Patrol source route");
    const FString Stages[]={TEXT("walking route"),TEXT("to cafe entry"),TEXT("approaching cafe"),TEXT("standing cafe visit"),TEXT("returning to source route")};
    return FString::Printf(TEXT("%s | SIMULATED pedestrian (not observed population)\nRoad: %s | %s\n%s | speed %.2fm/s | %s\nGoal: %s | %s | remaining stop %.1fs\n%s\nRecent: %s\nPrevious: %s\n%s"),*A.ID,*R.SourceID,*R.PlacementSource,*R.ID,A.Speed/100,A.Moving?TEXT("walking"):TEXT("waiting / yielding"),*Goal,*Stages[A.VisitStage],A.VisitStage==3?A.Wait:0.,*A.VisitReason,*(A.RecentActions.IsEmpty()?FString(TEXT("Patrolling")):A.RecentActions.Last()),*(A.RecentActions.Num()<2?FString(TEXT("-")):A.RecentActions[A.RecentActions.Num()-2]),*R.SourceURL);
}
FString AParisPedestrianCrowd::DescribeBusiness(const FString& ID) const {
    for(const auto& D:Visits)if(D.BusinessID==ID){const FString Occupant=Agents.IsValidIndex(D.Owner)?Agents[D.Owner].ID:TEXT("available");return FString::Printf(TEXT("\nSIMULATED standing visit: %s | capacity 1 | dwell %.0fs\nClear approach: %s | not real occupancy or surveyed entrance"),*Occupant,D.Dwell,*D.ID);}
    return TEXT("\nNo verified clear local visit approach; no simulated stop generated");
}
void AParisPedestrianCrowd::Tick(float Delta){
    Super::Tick(Delta);if(!bReady)return;SimAccumulator+=FMath::Min(double(Delta),.4);FVector Player;const FVector* Avoid=nullptr;if(auto PC=GetWorld()->GetFirstPlayerController())if(Cast<AParisWalker>(PC->GetPawn())){Player=PC->GetPawn()->GetActorLocation();Avoid=&Player;}
    while(SimAccumulator>=.05){SimulateStep(.05,Avoid);SimAccumulator-=.05;}
    RenderAccumulator+=Delta;GroundAccumulator+=Delta;if(bEnabled&&RenderAccumulator>=1./30){UpdateInstances(GroundAccumulator>.5);RenderAccumulator=0;if(GroundAccumulator>.5)GroundAccumulator=0;}
}
