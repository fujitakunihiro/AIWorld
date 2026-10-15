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
FString ParisPersonPartModel(int32 Part,int32 Variant,bool Seated){return Part==0?FString::Printf(TEXT("person_torso_%d"),Variant):Part==1?TEXT("person_head"):Part<4?FString::Printf(TEXT("person_arm_%d"),Variant):Part<6?(Seated?TEXT("person_thigh"):TEXT("person_leg")):TEXT("person_shin");}
TArray<FTransform> ParisPersonPose(const FVector& Root,double Yaw,double Phase,bool Moving,double Sit,double SeatHeight,double Gesture) {
    Sit=FMath::Clamp(Sit,0.,1.);const bool Seated=Sit>.001;
    const double Swing=Moving&&!Seated?FMath::Sin(Phase)*18:0;
    const FTransform Base(FRotator(0,Yaw,0),Root+FVector(0,0,(SeatHeight-84)*Sit+(Moving&&!Seated?-4*FMath::Abs(FMath::Sin(Phase)):0)));
    TArray<FTransform> Result;
    Result.Add(FTransform::Identity*Base);
    Result.Add(FTransform(FVector(0,0,146))*Base);
    Result.Add(FTransform(FRotator(-Swing*1.3+30*Gesture,0,0),FVector(0,-23,139))*Base);
    Result.Add(FTransform(FRotator(Swing*1.3,0,0),FVector(0,23,139))*Base);
    if(!Seated){Result.Add(FTransform(FRotator(Swing,0,0),FVector(0,-9,84))*Base);Result.Add(FTransform(FRotator(-Swing,0,0),FVector(0,9,84))*Base);}
    else {
        for(double Side:{-9.,9.})Result.Add(FTransform(FRotator(90*Sit,0,0),FVector(0,Side,84))*Base);
        for(int32 I=4;I<6;I++){const FVector Knee=Result[I].TransformPosition(FVector(0,0,-40));Result.Add(FTransform(FRotator(0,Yaw,0),Knee));}
    }
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
        if(Route.Points.Num()<2||Route.Length<.001||RouteByID.Contains(Route.ID))return false;RouteByID.Add(Route.ID,Routes.Num());Routes.Add(Route);
    }
    for(const auto& V:Array(Data,TEXT("destinations"))){auto J=V->AsObject();FParisVisitDestination D;D.ID=String(J,TEXT("id"));D.BusinessID=String(J,TEXT("business_id"));D.Name=String(J,TEXT("name"));
        auto Parent=RouteByID.Find(String(J,TEXT("parent_route_id")));auto Link=RouteByID.Find(String(J,TEXT("route_id")));if(!Parent||!Link||*Parent==*Link||Number(J,TEXT("capacity"))!=1)return false;
        D.ParentRoute=*Parent;D.Route=*Link;D.Entry=Number(J,TEXT("parent_distance_cm"));D.Dwell=Number(J,TEXT("dwell_seconds"));D.FacingYaw=Number(J,TEXT("facing_yaw_degrees"));
        if(!FMath::IsFinite(D.Entry)||D.Entry<0||D.Entry>Routes[*Parent].Length+.05||!FMath::IsFinite(D.Dwell)||D.Dwell<1||D.Dwell>60||!FMath::IsFinite(D.FacingYaw)||FVector::Dist(Routes[*Parent].Sample(D.Entry,1),Routes[*Link].Points[0])>.1)return false;
        D.Entry=FMath::Clamp(D.Entry,0.,Routes[*Parent].Length);
        for(const auto& Existing:Visits)if(Existing.ID==D.ID||Existing.BusinessID==D.BusinessID)return false;
        const FString SeatID=String(J,TEXT("seat_route_id"));
        if(!SeatID.IsEmpty()){auto Seat=RouteByID.Find(SeatID);if(!Seat||*Seat==*Parent||*Seat==*Link)return false;
            D.SeatRoute=*Seat;D.SeatHeight=Number(J,TEXT("seat_height_cm"));D.SeatYaw=Number(J,TEXT("seat_facing_yaw_degrees"));
            if(!FMath::IsFinite(D.SeatHeight)||D.SeatHeight<40||D.SeatHeight>52||!FMath::IsFinite(D.SeatYaw)||Routes[*Seat].PlacementSource!=TEXT("inferred_reserved_seat_approach")||Routes[*Seat].Length>600.1||FVector::Dist(Routes[*Link].Points.Last(),Routes[*Seat].Points[0])>.1)return false;
        }
        Visits.Add(D);
    }
    if(!InitializeNavigation(Data,RouteByID))return false;
    auto Social=Object(Data,TEXT("social"));bSocial=Social.IsValid()&&Social->HasTypedField<EJson::Boolean>(TEXT("enabled"))&&Social->GetBoolField(TEXT("enabled"));
    if(bSocial){SocialRange=Number(Social,TEXT("range_cm"));SocialDuration=Number(Social,TEXT("duration_seconds"));SocialCooldown=Number(Social,TEXT("cooldown_seconds"));
        if(!FMath::IsFinite(SocialRange)||SocialRange<125||SocialRange>300||!FMath::IsFinite(SocialDuration)||SocialDuration<1||SocialDuration>4||!FMath::IsFinite(SocialCooldown)||SocialCooldown<15||SocialCooldown>60)return false;}
    bShowNavigation=FParse::Param(FCommandLine::Get(),TEXT("ParisTwinRoutes"));
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
    if(Completed&&Routes[D.ParentRoute].SourceID!=Routes[A.ResumeRoute].SourceID)NetworkVisitsCompleted++;
    A.Route=A.ResumeRoute;A.Distance=A.ResumeDistance;A.Direction=A.ResumeDirection;A.Position=Routes[A.Route].Sample(A.Distance,A.Direction,&A.Yaw);A.Journey.Empty();
    A.SeatBlend=0;EndSocial(Agent);A.LastVisit=D.BusinessID;A.Visit=-1;A.VisitStage=0;A.VisitCooldown=30+(Agent%17);A.VisitAge=0;A.Wait=.5;
    A.VisitReason=TEXT("Resuming the original route; cafe selection is cooling down.");
    VisitAction(A,(Completed?TEXT("Returned from "):TEXT("Cancelled visit to "))+D.Name);if(Completed)CompletedVisits++;else AbortedVisits++;
}
void AParisPedestrianCrowd::SimulateStep(double Delta,const FVector* Player){
    Delta=FMath::Clamp(Delta,0.,.1);if(Delta<=0)return;
    for(int32 I=0;I<Agents.Num();I++){auto& A=Agents[I];A.Moving=false;A.VisitCooldown=FMath::Max(0.,A.VisitCooldown-Delta);
        if(A.VisitStage==0&&A.VisitCooldown<=0){if(!PlanVisit(I))A.VisitCooldown=5+(I%5);}
        if(A.VisitStage>0){auto& D=Visits[A.Visit];A.VisitAge+=Delta;
            if(A.VisitAge>A.VisitDeadline&&!A.bVisitAborted){A.bVisitAborted=true;EndSocial(I);VisitAction(A,TEXT("Visit timeout: returning safely"));
                A.VisitStage=4;const auto& L=A.Journey[A.JourneyIndex];A.Direction=L.Start>=A.Distance?1:-1;A.Wait=0;
            }
            // A blocked return never teleports. Expire its reservation so the
            // simulation cannot keep a destination permanently locked.
            if(A.VisitAge>A.VisitDeadline+10&&D.Owner==I)D.Owner=-1;
        }
        const auto* Stop=Visits.IsValidIndex(A.Visit)?&Visits[A.Visit]:nullptr;
        double SitTarget=Stop&&Stop->SeatRoute>=0&&A.VisitStage==3?FMath::Min(1.,A.Wait):0;
        if(Stop&&A.VisitStage==2&&A.Route==Stop->SeatRoute)SitTarget=FMath::Clamp((A.Distance-(Routes[A.Route].Length-40))/40,0.,.7);
        A.SeatBlend=FMath::FInterpConstantTo(A.SeatBlend,SitTarget,Delta,1.);
        if(A.SocialPartner>=0)continue;
        if(A.VisitStage==4&&A.SeatBlend>.001)continue;
        if(A.Wait>0){A.Wait=FMath::Max(0.,A.Wait-Delta);if(A.VisitStage==3){A.Yaw=Visits[A.Visit].SeatRoute>=0?Visits[A.Visit].SeatYaw:Visits[A.Visit].FacingYaw;if(A.Wait<=0){A.VisitStage=4;const auto& L=A.Journey[A.JourneyIndex];A.Direction=L.Start>=A.Distance?1:-1;VisitAction(A,TEXT("Finished stop; retracing walking route"));}}continue;}
        const auto& R=Routes[A.Route];
        double Next=FMath::Clamp(A.Distance+A.Direction*A.Speed*Delta,0.,R.Length);
        if(A.VisitStage>0){const auto& L=A.Journey[A.JourneyIndex];const double Target=A.VisitStage==4?L.Start:L.End;Next=A.Direction>0?FMath::Min(Next,Target):FMath::Max(Next,Target);}
        const FVector Candidate=R.Sample(Next,A.Direction);bool Blocked=false;
        for(int32 J=0;J<Agents.Num();J++){if(I==J||FMath::Abs(Candidate.Z-Agents[J].Position.Z)>150)continue;const double New=FVector::DistSquared2D(Candidate,Agents[J].Position),Old=FVector::DistSquared2D(A.Position,Agents[J].Position);if(New<65*65&&New<Old){Blocked=true;break;}}
        if(Player&&FMath::Abs(Candidate.Z-Player->Z)<250&&FVector::DistSquared2D(Candidate,*Player)<80*80&&FVector::DistSquared2D(Candidate,*Player)<FVector::DistSquared2D(A.Position,*Player))Blocked=true;
        if(Blocked){A.BlockedAge+=Delta;if(A.BlockedAge>2.5){
                if(A.VisitStage==1||A.VisitStage==2){A.bVisitAborted=true;A.VisitStage=4;A.Direction=A.Journey[A.JourneyIndex].Start>=A.Distance?1:-1;VisitAction(A,TEXT("Walking route blocked; returning"));}
                else if(A.VisitStage==0)A.Direction*=-1;
                A.Wait=.4;A.BlockedAge=0;RecoveryTurns++;
            }continue;}
        A.BlockedAge=0;TravelledCm+=FVector::Dist2D(Candidate,A.Position);A.Moving=FMath::Abs(A.Distance-Next)>.001;A.Distance=Next;A.Position=R.Sample(Next,A.Direction,&A.Yaw);A.Phase+=A.Speed*Delta*.035;
        if(Stop&&A.Route==Stop->SeatRoute&&A.SeatBlend>.001)A.Yaw+=FMath::FindDeltaAngleDegrees(A.Yaw,Stop->SeatYaw)*A.SeatBlend;
        if(A.VisitStage>0){const auto& L=A.Journey[A.JourneyIndex];const double Target=A.VisitStage==4?L.Start:L.End;
            if(FMath::Abs(Next-Target)<.001){
                if(A.VisitStage==4){if(A.JourneyIndex==0)FinishVisit(I,!A.bVisitAborted);else {A.JourneyIndex--;StartLeg(A,true);}}
                else if(A.JourneyIndex==A.Journey.Num()-1){auto& D=Visits[A.Visit];A.VisitStage=3;A.Wait=D.Dwell;A.Yaw=D.SeatRoute>=0?D.SeatYaw:D.FacingYaw;A.Moving=false;if(D.SeatRoute>=0)SeatArrivals++;VisitAction(A,FString::Printf(TEXT("%s at %s for %.0fs (simulated)"),D.SeatRoute>=0?TEXT("Sitting"):TEXT("Standing"),*D.Name,D.Dwell));}
                else {A.JourneyIndex++;StartLeg(A,false);A.VisitStage=A.JourneyIndex==A.Journey.Num()-1?2:1;}
            }
        }else if(Next<=.001||Next>=R.Length-.001){A.Direction*=-1;A.Wait=.8+(I%3)*.4;}
    }
    UpdateSocial(Delta);
}
void AParisPedestrianCrowd::UpdateInstances(bool TraceGround){
    TMap<FString,TArray<FTransform>> Transforms;TMap<FString,TArray<int32>> Lookup;
    TArray<int32> Visible;FVector View=FVector::ZeroVector;
    if(auto PC=GetWorld()->GetFirstPlayerController())if(PC->PlayerCameraManager)View=PC->PlayerCameraManager->GetCameraLocation();
    const double Range=DetailQuality==0?10000:DetailQuality==1?20000:35000;
    for(int32 I=0;I<Agents.Num();I++)if(FVector::DistSquared2D(Agents[I].Position,View)<=Range*Range)Visible.Add(I);
    Visible.Sort([&](int32 A,int32 B){const double DA=FVector::DistSquared2D(Agents[A].Position,View),DB=FVector::DistSquared2D(Agents[B].Position,View);return DA==DB?A<B:DA<DB;});
    if(Visible.Num()>VisibleCount)Visible.SetNum(VisibleCount);RenderedCount=Visible.Num();
    NearRenderedCount=0;FarRenderedCount=0;RenderedParts=0;StandingVisitorsRendered=0;SeatedRenderedCount=0;SeatedNearRenderedCount=0;
    const double NearRange=DetailQuality==0?2500:DetailQuality==1?4000:6000;
    const bool FullPeople=FParse::Param(FCommandLine::Get(),TEXT("ParisTwinFullPeople"));
    for(int32 I:Visible){auto& A=Agents[I];if(A.VisitStage==3)StandingVisitorsRendered++;
        const bool Seated=A.SeatBlend>.001;const auto* Stop=Visits.IsValidIndex(A.Visit)?&Visits[A.Visit]:nullptr;
        const bool PrivateSeat=Stop&&A.Route==Stop->SeatRoute;
        if(PrivateSeat)A.GroundOffset=0;
        if(Seated)SeatedRenderedCount++;
        if(TraceGround&&!PrivateSeat){FHitResult Hit;FCollisionQueryParams Params;Params.AddIgnoredActor(this);if(GetWorld()->LineTraceSingleByChannel(Hit,A.Position+FVector(0,0,80),A.Position-FVector(0,0,120),ECC_Pawn,Params)&&Hit.Normal.Z>.7)A.GroundOffset=Hit.ImpactPoint.Z-A.Position.Z;}
        const double Distance=FVector::Dist2D(A.Position,View);
        A.bFarPose=!FullPeople&&ModelByName.Contains(TEXT("person_far_0"))&&Distance>NearRange+(A.bFarPose?-200:200);
        if(A.bFarPose&&(!Seated||A.SeatBlend>=.999)){const FString Name=(Seated?FString::Printf(TEXT("person_far_seated_%d"),A.Variant):FString::Printf(TEXT("person_far_%d"),A.Variant));Transforms.FindOrAdd(Name).Add(FTransform(FRotator(0,A.Yaw,0),A.Position+FVector(0,0,A.GroundOffset)));Lookup.FindOrAdd(Name).Add(I);FarRenderedCount++;RenderedParts++;continue;}
        NearRenderedCount++;if(Seated)SeatedNearRenderedCount++;RenderedParts+=Seated?8:6;
        const auto Pose=ParisPersonPose(A.Position+FVector(0,0,A.GroundOffset),A.Yaw,A.Phase,A.Moving,A.SeatBlend,Stop?Stop->SeatHeight:48,A.SocialPartner>=0?.5+.3*FMath::Sin(A.SocialRemaining*5):0);
        for(int32 P=0;P<Pose.Num();P++){const FString Name=ParisPersonPartModel(P,A.Variant,Seated);Transforms.FindOrAdd(Name).Add(Pose[P]);Lookup.FindOrAdd(Name).Add(I);}
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
    return DescribePerson(PersonID(Component,Instance));
}
FString AParisPedestrianCrowd::PersonID(UPrimitiveComponent* Component,int32 Instance) const {
    const auto Lookup=AgentByInstance.Find(Component);if(!Lookup||!Lookup->IsValidIndex(Instance)||!Agents.IsValidIndex((*Lookup)[Instance]))return TEXT("");return Agents[(*Lookup)[Instance]].ID;
}
FString AParisPedestrianCrowd::DescribePerson(const FString& ID) const {
    const auto Found=Agents.FindByPredicate([&](const FParisPedestrian& A){return A.ID==ID;});if(!Found)return TEXT("");const auto& A=*Found;const auto& R=Routes[A.Route];
    const FString Goal=Visits.IsValidIndex(A.Visit)?Visits[A.Visit].Name:TEXT("Patrol source route");
    const FString Stages[]={TEXT("walking route"),TEXT("following walking graph"),TEXT("approaching cafe"),TEXT("cafe visit"),TEXT("returning to original point")};
    return FString::Printf(TEXT("%s | SIMULATED pedestrian (not observed population)\nRoad: %s | %s\n%s | speed %.2fm/s | %s\nGoal: %s | %s | stop %.1fs | leg %d/%d | route %.1fm\n%s\nRecent: %s\nPrevious: %s\n%s\n%s"),*A.ID,*R.SourceID,*R.PlacementSource,*R.ID,A.Speed/100,A.Moving?TEXT("walking"):TEXT("waiting / yielding"),*Goal,*Stages[A.VisitStage],A.VisitStage==3?A.Wait:0.,A.VisitStage?A.JourneyIndex+1:0,A.Journey.Num(),A.Distance/100,*A.VisitReason,*(A.RecentActions.IsEmpty()?FString(TEXT("Patrolling")):A.RecentActions.Last()),*(A.RecentActions.Num()<2?FString(TEXT("-")):A.RecentActions[A.RecentActions.Num()-2]),*R.SourceURL,*FString::Printf(TEXT("%s | %s"),A.SeatBlend>.001?TEXT("Reserved chair / sitting"):TEXT("Standing / walking"),A.SocialPartner>=0?*FString::Printf(TEXT("Greeting %s: %s (%.1fs)"),*Agents[A.SocialPartner].ID,*A.SocialLine,A.SocialRemaining):TEXT("No active greeting")));
}
FString AParisPedestrianCrowd::DescribeBusiness(const FString& ID) const {
    for(const auto& D:Visits)if(D.BusinessID==ID){const bool Owned=Agents.IsValidIndex(D.Owner);const FString Occupant=Owned?Agents[D.Owner].ID:TEXT("available");
        const FString Activity=!Owned?TEXT("free"):Agents[D.Owner].VisitStage==3?(Agents[D.Owner].SeatBlend>.001?TEXT("sitting"):TEXT("standing stop")):Agents[D.Owner].VisitStage==4?TEXT("returning"):TEXT("walking to cafe");
        const double Remaining=Owned&&Agents[D.Owner].VisitStage==3?Agents[D.Owner].Wait:0;
        return FString::Printf(TEXT("\nSIMULATED visit: %s | %s | capacity 1 | stop %.1f / %.0fs\nClear approach: %s | %s | not real occupancy or surveyed entrance"),*Occupant,*Activity,Remaining,D.Dwell,*D.ID,D.SeatRoute>=0?TEXT("one reserved chair"):TEXT("standing fallback"));
    }
    return TEXT("\nNo verified clear local visit approach; no simulated stop generated");
}
void AParisPedestrianCrowd::Tick(float Delta){
    Super::Tick(Delta);if(!bReady)return;SimAccumulator+=FMath::Min(double(Delta),.4);FVector Player;const FVector* Avoid=nullptr;if(auto PC=GetWorld()->GetFirstPlayerController())if(Cast<AParisWalker>(PC->GetPawn())){Player=PC->GetPawn()->GetActorLocation();Avoid=&Player;}
    while(SimAccumulator>=.05){SimulateStep(.05,Avoid);SimAccumulator-=.05;}
    DrawNavigation();
    RenderAccumulator+=Delta;GroundAccumulator+=Delta;if(bEnabled&&RenderAccumulator>=1./30){UpdateInstances(GroundAccumulator>.5);RenderAccumulator=0;if(GroundAccumulator>.5)GroundAccumulator=0;}
}
