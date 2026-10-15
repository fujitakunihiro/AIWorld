#include "ParisPedestrians.h"
#include "WorldProtocol.h"
#include "DrawDebugHelpers.h"
#include "Camera/PlayerCameraManager.h"
#include "GameFramework/PlayerController.h"
#include "Engine/World.h"
#include <queue>
using namespace AIWorld;

bool AParisPedestrianCrowd::InitializeNavigation(const TSharedPtr<FJsonObject>& Data,const TMap<FString,int32>& RouteByID){
    NodesByRoute.SetNum(Routes.Num());const auto Graph=Object(Data,TEXT("navigation"));const auto& InputNodes=Array(Graph,TEXT("nodes"));const auto& InputEdges=Array(Graph,TEXT("edges"));
    if(InputNodes.IsEmpty()&&InputEdges.IsEmpty())return true;
    if(InputNodes.Num()>20000||InputEdges.Num()>50000)return false;TMap<FString,int32> ByID;
    for(const auto& Value:InputNodes){auto J=Value->AsObject();auto R=RouteByID.Find(String(J,TEXT("route_id")));const FString ID=String(J,TEXT("id"));if(!R||ByID.Contains(ID))return false;
        FParisWalkingNode N;N.Route=*R;N.Distance=Number(J,TEXT("distance_cm"));const auto& P=Array(J,TEXT("position_cm"));if(P.Num()!=3||!FMath::IsFinite(N.Distance)||N.Distance<0||N.Distance>Routes[*R].Length+.05)return false;
        N.Position=FVector(P[0]->AsNumber(),P[1]->AsNumber(),P[2]->AsNumber());if(N.Position.ContainsNaN()||FVector::Dist(N.Position,Routes[*R].Sample(N.Distance,1))>.1)return false;
        N.Distance=FMath::Clamp(N.Distance,0.,Routes[*R].Length);ByID.Add(ID,Nodes.Num());NodesByRoute[*R].Add(Nodes.Num());Nodes.Add(N);
    }
    for(const auto& Value:InputEdges){auto J=Value->AsObject();auto A=ByID.Find(String(J,TEXT("a")));auto B=ByID.Find(String(J,TEXT("b")));if(!A||!B||*A==*B)return false;
        FParisWalkingEdge E;E.A=*A;E.B=*B;E.Start=Number(J,TEXT("start_cm"));E.End=Number(J,TEXT("end_cm"));E.Length=Number(J,TEXT("length_cm"));const FString RouteID=String(J,TEXT("route_id"));
        if(!FMath::IsFinite(E.Length)||E.Length<0||!FMath::IsFinite(E.Start)||!FMath::IsFinite(E.End))return false;
        if(!RouteID.IsEmpty()){auto R=RouteByID.Find(RouteID);if(!R)return false;E.Route=*R;const auto& Route=Routes[*R];
            if(E.Start<0||E.End<0||E.Start>Route.Length+.05||E.End>Route.Length+.05||FMath::Abs(FMath::Abs(E.End-E.Start)-E.Length)>.1||FVector::Dist(Route.Sample(E.Start,1),Nodes[*A].Position)>.1||FVector::Dist(Route.Sample(E.End,1),Nodes[*B].Position)>.1)return false;
        }else if(E.Length!=0||FVector::Dist(Nodes[*A].Position,Nodes[*B].Position)>.1)return false;
        if(E.Route>=0){E.Start=FMath::Clamp(E.Start,0.,Routes[E.Route].Length);E.End=FMath::Clamp(E.End,0.,Routes[E.Route].Length);E.Length=FMath::Abs(E.End-E.Start);}
        Nodes[*A].Edges.Add(Edges.Num());Nodes[*B].Edges.Add(Edges.Num());Edges.Add(E);
    }
    const auto& Destinations=Array(Data,TEXT("destinations"));for(int32 I=0;I<Visits.Num();I++){const auto J=Destinations[I]->AsObject();auto N=ByID.Find(String(J,TEXT("navigation_node_id")));if(!N)return false;
        auto& D=Visits[I];D.Node=*N;if(Nodes[*N].Route!=D.ParentRoute||FMath::Abs(Nodes[*N].Distance-D.Entry)>.1)return false;
    }return true;
}

void AParisPedestrianCrowd::StartLeg(FParisPedestrian& A,bool Returning){
    const auto& L=A.Journey[A.JourneyIndex];A.Route=L.Route;A.Distance=Returning?L.End:L.Start;A.Direction=(Returning?L.Start-L.End:L.End-L.Start)>=0?1:-1;
    A.Position=Routes[A.Route].Sample(A.Distance,A.Direction,&A.Yaw);
}

bool AParisPedestrianCrowd::PlanVisit(int32 Agent){
    auto& A=Agents[Agent];if(!Visits.ContainsByPredicate([](const FParisVisitDestination& D){return D.Owner<0;})){PlansRejected++;A.VisitReason=TEXT("All cafe stops are reserved; continue the original route.");return false;}constexpr double Limit=12000;TArray<double> Costs;TArray<int32> Previous,PreviousEdge;
    Costs.Init(TNumericLimits<double>::Max(),Nodes.Num());Previous.Init(-1,Nodes.Num());PreviousEdge.Init(-1,Nodes.Num());
    using Entry=std::pair<double,int32>;std::priority_queue<Entry,std::vector<Entry>,std::greater<Entry>> Queue;
    if(NodesByRoute.IsValidIndex(A.Route))for(int32 N:NodesByRoute[A.Route]){Costs[N]=FMath::Abs(A.Distance-Nodes[N].Distance);if(Costs[N]<=Limit)Queue.emplace(Costs[N],N);}
    while(!Queue.empty()){
        const auto [Cost,N]=Queue.top();Queue.pop();if(Cost!=Costs[N]||Cost>Limit)continue;
        for(int32 Index:Nodes[N].Edges){const auto& E=Edges[Index];const int32 Other=E.A==N?E.B:E.A;const double Candidate=Cost+E.Length;
            if(Candidate<Costs[Other]&&Candidate<=Limit){Costs[Other]=Candidate;Previous[Other]=N;PreviousEdge[Other]=Index;Queue.emplace(Candidate,Other);}
        }
    }
    int32 Best=-1;double Cost=TNumericLimits<double>::Max();
    for(int32 I=0;I<Visits.Num();I++){const auto& D=Visits[I];if(D.Owner>=0)continue;double Walk=TNumericLimits<double>::Max();
        if(Nodes.IsEmpty()){if(D.ParentRoute==A.Route)Walk=FMath::Abs(A.Distance-D.Entry);}else if(Costs.IsValidIndex(D.Node))Walk=Costs[D.Node];
        if(Walk>Limit)continue;const double Candidate=2*(Walk+Routes[D.Route].Length);
        if(Candidate<Cost){Cost=Candidate;Best=I;}
    }
    if(Best<0){PlansRejected++;A.VisitReason=TEXT("No unreserved reachable cafe within 120m on the verified walking graph.");return false;}
    auto& D=Visits[Best];TArray<FParisWalkingLeg> Legs;
    auto Append=[&](int32 Route,double Start,double End){if(FMath::Abs(End-Start)>.001)Legs.Add({Route,Start,End});};
    if(Nodes.IsEmpty())Append(A.Route,A.Distance,D.Entry);
    else {
        TArray<FParisWalkingLeg> Reverse;int32 N=D.Node,Steps=0;
        while(Previous[N]>=0){if(++Steps>256){PlansRejected++;A.VisitReason=TEXT("Walking plan exceeds the bounded leg budget.");return false;}const int32 P=Previous[N];const auto& E=Edges[PreviousEdge[N]];
            if(E.Route>=0)Reverse.Add({E.Route,E.A==P?E.Start:E.End,E.A==P?E.End:E.Start});N=P;
        }
        Append(A.Route,A.Distance,Nodes[N].Distance);
        for(int32 I=Reverse.Num()-1;I>=0;I--)Append(Reverse[I].Route,Reverse[I].Start,Reverse[I].End);
    }
    Append(D.Route,0,Routes[D.Route].Length);if(Legs.IsEmpty()||Legs.Num()>256){PlansRejected++;A.VisitReason=TEXT("Walking plan exceeds the bounded leg budget.");return false;}
    FVector Last=A.Position;for(const auto& L:Legs){if(FVector::Dist(Last,Routes[L.Route].Sample(L.Start,1))>.1){PlansRejected++;A.VisitReason=TEXT("Discontinuous walking plan rejected; staying on the original route.");return false;}Last=Routes[L.Route].Sample(L.End,1);}
    // Claim only after a complete, continuous round trip has been planned.
    D.Owner=Agent;A.Visit=Best;A.ResumeRoute=A.Route;A.ResumeDistance=A.Distance;A.ResumeDirection=A.Direction;A.Journey=MoveTemp(Legs);A.JourneyIndex=0;
    A.PlannedWalkingCm=Cost;A.VisitDeadline=FMath::Max(90.,Cost/FMath::Max(1.,A.Speed)+D.Dwell+30);A.VisitAge=0;A.Wait=0;A.bVisitAborted=false;
    A.VisitStage=A.Journey.Num()==1?2:1;StartLeg(A,false);if(Routes[D.ParentRoute].SourceID!=Routes[A.ResumeRoute].SourceID)NetworkVisits++;
    A.VisitReason=FString::Printf(TEXT("Shortest available round trip %.1fm on verified paths; %d legs; one reserved stop."),Cost/100,A.Journey.Num());
    A.RecentActions.Add(TEXT("Reserved ")+D.Name);if(A.RecentActions.Num()>4)A.RecentActions.RemoveAt(0);return true;
}

void AParisPedestrianCrowd::DrawNavigation(){
    if(!bShowNavigation||!bEnabled)return;FVector View=FVector::ZeroVector;if(auto PC=GetWorld()->GetFirstPlayerController())if(PC->PlayerCameraManager)View=PC->PlayerCameraManager->GetCameraLocation();
    int32 Drawn=0;for(const auto& E:Edges){if(++Drawn>6000)break;const FVector A=Nodes[E.A].Position,B=Nodes[E.B].Position;
        if(FVector::DistSquared2D((A+B)*.5,View)>15000.*15000||E.Route<0)continue;const auto& R=Routes[E.Route];
        const double Step=FMath::Max(100.,FMath::Abs(E.End-E.Start)/30);double D=E.Start;const double Sign=E.End>=D?1:-1;
        const FColor Color=R.PlacementSource==TEXT("inferred_walking_connector")?FColor::Orange:FColor::Cyan;
        while(FMath::Abs(D-E.End)>.001){const double Next=Sign>0?FMath::Min(E.End,D+Step):FMath::Max(E.End,D-Step);DrawDebugLine(GetWorld(),R.Sample(D,1)+FVector(0,0,25),R.Sample(Next,1)+FVector(0,0,25),Color,false,-1,0,3);D=Next;}
    }
}
