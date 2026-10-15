#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Dom/JsonObject.h"
#include "ParisPedestrians.generated.h"
class UInstancedStaticMeshComponent;
class UStaticMesh;
class UMaterialInterface;
class UPrimitiveComponent;

// Six articulated parts. Units are centimetres; Root is the ground underfoot.
TArray<FTransform> ParisPersonPose(const FVector& Root,double Yaw,double Phase,bool Moving);
FString ParisPersonPartModel(int32 Part,int32 Variant);

struct FParisPedestrianRoute {
    FString ID,SourceID,SourceURL,PlacementSource;
    TArray<FVector> Points;
    TArray<double> Distances;
    double Length=0;
    FVector Sample(double Distance,double Direction,double* Yaw=nullptr) const;
};
struct FParisWalkingLeg { int32 Route=-1;double Start=0,End=0; };
struct FParisWalkingNode { int32 Route=-1;double Distance=0;FVector Position=FVector::ZeroVector;TArray<int32> Edges; };
struct FParisWalkingEdge { int32 A=-1,B=-1,Route=-1;double Start=0,End=0,Length=0; };
struct FParisPedestrian {
    FString ID;
    int32 Route=0,Variant=0,Direction=1;
    double Distance=0,Speed=120,Wait=0,BlockedAge=0,Phase=0,GroundOffset=0;
    FVector Position=FVector::ZeroVector;
    double Yaw=0;
    bool Moving=false;
    // 0 patrol, 1 walk to entry, 2 approach, 3 dwell, 4 retrace approach.
    int32 Visit=-1,VisitStage=0,ResumeDirection=1;
    double VisitCooldown=0,VisitAge=0;
    FString LastVisit,VisitReason;
    TArray<FString> RecentActions;
    bool bVisitAborted=false,bFarPose=false;
    int32 ResumeRoute=-1,JourneyIndex=0;
    double ResumeDistance=0,VisitDeadline=90,PlannedWalkingCm=0;
    TArray<FParisWalkingLeg> Journey;
};
struct FParisVisitDestination {
    FString ID,BusinessID,Name;
    int32 ParentRoute=-1,Route=-1,Owner=-1,Node=-1;
    double Entry=0,Dwell=12,FacingYaw=0;
};

UCLASS()
class AParisPedestrianCrowd : public AActor {
    GENERATED_BODY()
public:
    AParisPedestrianCrowd();
    bool Initialize(const TSharedPtr<FJsonObject>& Data);
    virtual void Tick(float Delta) override;
    void SimulateStep(double Delta,const FVector* Player=nullptr);
    void UpdateInstances(bool TraceGround=false);
    void SetDisplay(bool Enabled,int32 Quality);
    FString DescribeHit(UPrimitiveComponent* Component,int32 Instance) const;
    FString DescribeBusiness(const FString& ID) const;
    FString PersonID(UPrimitiveComponent* Component,int32 Instance) const;
    FString DescribePerson(const FString& ID) const;
    int32 NavigationNodes() const { return Nodes.Num(); }
    int32 NavigationEdges() const { return Edges.Num(); }
    UStaticMesh* Model(const FString& Name) const;
    const TArray<FParisPedestrian>& People() const { return Agents; }
    const TArray<FParisPedestrianRoute>& Network() const { return Routes; }
    const TArray<FParisVisitDestination>& Destinations() const { return Visits; }
    int32 VisibleCount=0,RenderedCount=0,RecoveryTurns=0;
    int32 NearRenderedCount=0,FarRenderedCount=0,RenderedParts=0,StandingVisitorsRendered=0,CompletedVisits=0,AbortedVisits=0;
    double TravelledCm=0;
    int32 NetworkVisits=0,NetworkVisitsCompleted=0,PlansRejected=0;
    bool bShowNavigation=false;
    bool bEnabled=true,bReady=false;
private:
    TArray<FParisPedestrianRoute> Routes;
    TArray<FParisPedestrian> Agents;
    TArray<FParisVisitDestination> Visits;
    TArray<FParisWalkingNode> Nodes;
    TArray<FParisWalkingEdge> Edges;
    TArray<TArray<int32>> NodesByRoute;
    bool PlanVisit(int32 Agent);
    bool InitializeNavigation(const TSharedPtr<FJsonObject>& Data,const TMap<FString,int32>& RouteByID);
    void StartLeg(FParisPedestrian& Agent,bool Returning);
    void DrawNavigation();
    void FinishVisit(int32 Agent,bool Completed);
    UPROPERTY() TArray<TObjectPtr<UStaticMesh>> Models;
    UPROPERTY() TArray<TObjectPtr<UInstancedStaticMeshComponent>> Instances;
    TMap<FString,UStaticMesh*> ModelByName;
    TMap<FString,UInstancedStaticMeshComponent*> InstanceByName;
    TMap<UPrimitiveComponent*,TArray<int32>> AgentByInstance;
    int32 DetailQuality=1;
    double SimAccumulator=0,RenderAccumulator=0,GroundAccumulator=0;
};
