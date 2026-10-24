#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Dom/JsonObject.h"
#include "ParisPedestrians.generated.h"
class UInstancedStaticMeshComponent;
class UStaticMesh;
class UMaterialInterface;
class UPrimitiveComponent;
class USkeletalMesh;
class USkeletalMeshComponent;
class UCapsuleComponent;
class UAnimSequence;

USTRUCT()
struct FParisHumanVisual {
    GENERATED_BODY()
    UPROPERTY() TObjectPtr<USkeletalMesh> Mesh;
    UPROPERTY() TObjectPtr<UAnimSequence> Idle;
    UPROPERTY() TObjectPtr<UAnimSequence> Walk;
    UPROPERTY() TObjectPtr<UAnimSequence> Sit;
    float YawOffset=0,NominalSpeed=120;
};

// Six articulated parts. Units are centimetres; Root is the ground underfoot.
TArray<FTransform> ParisPersonPose(const FVector& Root,double Yaw,double Phase,bool Moving,double Sit=0,double SeatHeight=48,double Gesture=0);
FString ParisPersonPartModel(int32 Part,int32 Variant,bool Seated=false);

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
    double SeatBlend=0,SocialRemaining=0,SocialCooldown=0;
    int32 SocialPartner=-1;
    FString SocialLine;
};
struct FParisVisitDestination {
    FString ID,BusinessID,Name;
    int32 ParentRoute=-1,Route=-1,Owner=-1,Node=-1;
    double Entry=0,Dwell=12,FacingYaw=0,SeatHeight=48,SeatYaw=0;
    int32 SeatRoute=-1;
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
    int32 SeatedRenderedCount=0,SeatedNearRenderedCount=0,SeatArrivals=0,SocialStarted=0,SocialCompleted=0;
    bool bShowNavigation=false;
    bool bEnabled=true,bReady=false;
    int32 SkeletalRenderedCount=0;
    int32 HumanVisualVariants() const { return HumanVisuals.Num(); }
    int32 HumanVisualBudget() const { return DetailQuality==2?16:DetailQuality==1?8:0; }
private:
    void InitializeHumanVisuals();
    bool RenderHuman(int32 Agent,const TSet<int32>& Wanted,TSet<int32>& Used,double Delta);
    UPROPERTY() TArray<FParisHumanVisual> HumanVisuals;
    UPROPERTY() TArray<TObjectPtr<USkeletalMeshComponent>> HumanMeshes;
    UPROPERTY() TArray<TObjectPtr<UCapsuleComponent>> HumanPickers;
    TArray<int32> HumanAgents;
    TMap<UPrimitiveComponent*,int32> HumanAgentByComponent;
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
    void UpdateSocial(double Delta);
    void EndSocial(int32 Agent);
    bool SocialVisible(int32 A,int32 B) const;
    bool bSocial=false;
    double SocialRange=280,SocialDuration=2.5,SocialCooldown=25,SocialAccumulator=0;
    UPROPERTY() TArray<TObjectPtr<UStaticMesh>> Models;
    UPROPERTY() TArray<TObjectPtr<UInstancedStaticMeshComponent>> Instances;
    TMap<FString,UStaticMesh*> ModelByName;
    TMap<FString,UInstancedStaticMeshComponent*> InstanceByName;
    TMap<UPrimitiveComponent*,TArray<int32>> AgentByInstance;
    int32 DetailQuality=1;
    double SimAccumulator=0,RenderAccumulator=0,GroundAccumulator=0;
};
