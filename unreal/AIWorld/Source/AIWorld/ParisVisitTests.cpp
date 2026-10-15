#include "ParisPedestrians.h"
#include "WorldProtocol.h"
#include "Misc/AutomationTest.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "ParisDigitalTwin.h"

#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisVisitTest,"ParisDigitalTwin.Live.CafeVisitLifecycle",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisVisitTest::RunTest(const FString&){
    UWorld* World=nullptr;for(const auto& Context:GEngine->GetWorldContexts())if(Context.World()){World=Context.World();break;}if(!TestNotNull(TEXT("Test world"),World))return false;
    const FString Fixture=TEXT(R"({"models":[],"routes":[{"id":"patrol","source_id":"osm/way/1","points_cm":[[0,0,0],[2000,0,0]]},{"id":"approach","source_id":"osm/way/1","points_cm":[[500,0,0],[500,300,0]]}],"agents":[{"id":"sim/person/0","route_id":"patrol","progress_m":2,"direction":1,"speed_mps":1.2}],"destinations":[{"id":"stop","business_id":"osm/node/1","name":"Fixture Cafe","route_id":"approach","parent_route_id":"patrol","parent_distance_cm":500,"capacity":1,"dwell_seconds":2,"facing_yaw_degrees":180}]})");
    auto Data=AIWorld::Parse(Fixture);auto Crowd=World->SpawnActor<AParisPedestrianCrowd>();Crowd->SetActorTickEnabled(false);
    if(!TestTrue(TEXT("Connected visit fixture initializes"),Crowd->Initialize(Data))){Crowd->Destroy();return false;}
    bool Stopped=false,Returned=false;FVector Previous=Crowd->People()[0].Position;
    for(int32 I=0;I<1000;I++){
        Crowd->SimulateStep(.05);const auto& A=Crowd->People()[0];
        if(!TestTrue(TEXT("No teleport at entry or return"),FVector::Dist(Previous,A.Position)<=6.01))break;Previous=A.Position;
        TestTrue(TEXT("Always on its current validated path"),FVector::Dist(A.Position,Crowd->Network()[A.Route].Sample(A.Distance,A.Direction))<.001);
        if(A.VisitStage==3){Stopped=true;TestTrue(TEXT("Stop holds one reservation and faces cafe"),Crowd->Destinations()[0].Owner==0&&!A.Moving&&FMath::IsNearlyEqual(A.Yaw,180.));}
        if(Crowd->CompletedVisits>0){Returned=true;TestTrue(TEXT("Completion releases reservation and restores source route"),A.Route==0&&A.VisitStage==0&&A.VisitCooldown>0&&Crowd->Destinations()[0].Owner==-1);break;}
    }
    TestTrue(TEXT("Visit reaches cafe and completes its return"),Stopped&&Returned);TestTrue(TEXT("Inspection distinguishes simulated occupancy"),Crowd->DescribeBusiness(TEXT("osm/node/1")).Contains(TEXT("not real occupancy")));Crowd->Destroy();
    // A permanently occupied return path must expire the reservation without
    // teleporting through the blocker. Clearing the blocker then allows exit.
    Crowd=World->SpawnActor<AParisPedestrianCrowd>();Crowd->SetActorTickEnabled(false);TestTrue(TEXT("Return-timeout fixture initializes"),Crowd->Initialize(AIWorld::Parse(Fixture)));
    for(int32 I=0;I<300&&Crowd->People()[0].VisitStage!=3;I++)Crowd->SimulateStep(.05);
    TestEqual(TEXT("Visitor first reaches its stop"),Crowd->People()[0].VisitStage,3);
    const FVector ReturnBlocker(500,150,0);for(int32 I=0;I<2400;I++)Crowd->SimulateStep(.05,&ReturnBlocker);
    TestTrue(TEXT("Expired return releases stop while staying on the safe side of blocker"),Crowd->Destinations()[0].Owner==-1&&Crowd->People()[0].bVisitAborted&&Crowd->People()[0].VisitStage==4&&Crowd->People()[0].Position.Y>150);
    for(int32 I=0;I<100;I++)Crowd->SimulateStep(.05);
    TestTrue(TEXT("Removing blocker permits a safe cancelled return and cooldown"),Crowd->AbortedVisits==1&&Crowd->People()[0].Route==0&&Crowd->People()[0].VisitStage==0&&Crowd->People()[0].VisitCooldown>0);Crowd->Destroy();
    // Two simultaneous candidates compete for exactly one slot. The rejected
    // visitor continues patrolling; it is never a second owner.
    Data=AIWorld::Parse(Fixture);auto Second=MakeShared<FJsonObject>();Second->SetStringField(TEXT("id"),TEXT("sim/person/1"));Second->SetStringField(TEXT("route_id"),TEXT("patrol"));Second->SetNumberField(TEXT("progress_m"),15);Second->SetNumberField(TEXT("speed_mps"),1.1);Second->SetNumberField(TEXT("direction"),-1);
    auto Agents=Data->GetArrayField(TEXT("agents"));Agents.Add(MakeShared<FJsonValueObject>(Second));Data->SetArrayField(TEXT("agents"),Agents);
    Crowd=World->SpawnActor<AParisPedestrianCrowd>();Crowd->SetActorTickEnabled(false);TestTrue(TEXT("Competing agents initialize"),Crowd->Initialize(Data));
    Crowd->SimulateStep(.05);int32 Reserved=0;for(const auto& A:Crowd->People())Reserved+=A.Visit>=0?1:0;TestEqual(TEXT("Atomic one-slot reservation"),Reserved,1);
    // A stationary player blocks the main approach. The visitor cancels and
    // releases the reservation, and a cooldown prevents immediate reselection.
    const FVector Blocker(300,0,0);for(int32 I=0;I<80;I++)Crowd->SimulateStep(.05,&Blocker);
    TestTrue(TEXT("Blocked approach records a failure and releases first owner"),Crowd->AbortedVisits>0&&Crowd->People()[0].Visit==-1&&Crowd->People()[0].VisitCooldown>0);
    for(int32 I=0;I<1000;I++)Crowd->SimulateStep(.05);
    for(const auto& A:Crowd->People())TestTrue(TEXT("Competition remains finite for 1000 further steps"),!A.Position.ContainsNaN()&&A.RecentActions.Num()<=4);
    Crowd->Destroy();
    Data=AIWorld::Parse(Fixture);Data->GetArrayField(TEXT("destinations"))[0]->AsObject()->SetNumberField(TEXT("parent_distance_cm"),700);
    Crowd=World->SpawnActor<AParisPedestrianCrowd>();TestFalse(TEXT("Disconnected visit cannot load"),Crowd->Initialize(Data));Crowd->Destroy();return true;
}
#endif
