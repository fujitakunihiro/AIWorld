#include "ParisPedestrians.h"
#include "ParisDigitalTwin.h"
#include "WorldProtocol.h"
#include "Misc/AutomationTest.h"
#include "Engine/Engine.h"
#include "Engine/World.h"

#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisNavigationTest,"ParisDigitalTwin.Live.WalkingGraphRouting",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisNavigationTest::RunTest(const FString&){
    UWorld* World=nullptr;for(const auto& Context:GEngine->GetWorldContexts())if(Context.World()){World=Context.World();break;}if(!TestNotNull(TEXT("Routing world"),World))return false;
    const FString Fixture=TEXT(R"({"models":[],"routes":[{"id":"home","source_id":"osm/way/1","points_cm":[[0,0,0],[1000,0,0]]},{"id":"street","source_id":"osm/way/2","points_cm":[[1000,0,0],[1000,1000,0]]},{"id":"approach","source_id":"osm/way/2","points_cm":[[1000,1000,0],[1300,1000,0]]}],"agents":[{"id":"sim/person/0","route_id":"home","progress_m":2,"direction":1,"speed_mps":1.2}],"destinations":[{"id":"stop","business_id":"osm/node/1","name":"Other Street Cafe","route_id":"approach","parent_route_id":"street","parent_distance_cm":1000,"capacity":1,"dwell_seconds":2,"facing_yaw_degrees":180,"navigation_node_id":"s1"}],"navigation":{"nodes":[{"id":"h0","route_id":"home","distance_cm":0,"position_cm":[0,0,0]},{"id":"h1","route_id":"home","distance_cm":1000,"position_cm":[1000,0,0]},{"id":"s0","route_id":"street","distance_cm":0,"position_cm":[1000,0,0]},{"id":"s1","route_id":"street","distance_cm":1000,"position_cm":[1000,1000,0]}],"edges":[{"a":"h0","b":"h1","route_id":"home","start_cm":0,"end_cm":1000,"length_cm":1000},{"a":"h1","b":"s0","route_id":"","start_cm":0,"end_cm":0,"length_cm":0},{"a":"s0","b":"s1","route_id":"street","start_cm":0,"end_cm":1000,"length_cm":1000}]}})");
    auto Data=AIWorld::Parse(Fixture);auto Crowd=World->SpawnActor<AParisPedestrianCrowd>();Crowd->SetActorTickEnabled(false);if(!TestTrue(TEXT("Connected graph loads"),Crowd->Initialize(Data))){Crowd->Destroy();return false;}
    bool OtherStreet=false,Stopped=false;FVector Previous=Crowd->People()[0].Position;FString Before;
    Crowd->SimulateStep(.05);Before=Crowd->DescribePerson(TEXT("sim/person/0"));TestTrue(TEXT("Shortest round trip is computed from real graph lengths"),FMath::IsNearlyEqual(Crowd->People()[0].PlannedWalkingCm,4200.));Previous=Crowd->People()[0].Position;
    for(int32 I=0;I<1200;I++){Crowd->SimulateStep(.05);const auto& A=Crowd->People()[0];
        if(!TestTrue(TEXT("Continuous travel across graph junctions"),FVector::Dist(Previous,A.Position)<=6.01))break;Previous=A.Position;
        TestTrue(TEXT("Active route sample always equals position"),FVector::Dist(A.Position,Crowd->Network()[A.Route].Sample(A.Distance,A.Direction))<.001);
        OtherStreet|=A.Route==1;Stopped|=A.VisitStage==3;if(Crowd->CompletedVisits>0)break;
    }
    TestTrue(TEXT("Visits a different street and returns to its original point"),OtherStreet&&Stopped&&Crowd->NetworkVisitsCompleted==1&&Crowd->People()[0].Route==0&&FMath::IsNearlyEqual(Crowd->People()[0].Distance,200.));
    TestTrue(TEXT("Selected person inspection refreshes as journey state changes"),Before!=Crowd->DescribePerson(TEXT("sim/person/0"))&&Crowd->DescribePerson(TEXT("sim/person/0")).Contains(TEXT("sim/person/0")));Crowd->Destroy();
    Data=AIWorld::Parse(Fixture);auto Graph=AIWorld::Object(Data,TEXT("navigation"));auto Edges=Graph->GetArrayField(TEXT("edges"));Edges.RemoveAt(1);Graph->SetArrayField(TEXT("edges"),Edges);
    Crowd=World->SpawnActor<AParisPedestrianCrowd>();Crowd->SetActorTickEnabled(false);TestTrue(TEXT("Disconnected graph is valid data"),Crowd->Initialize(Data));
    for(int32 I=0;I<1000;I++)Crowd->SimulateStep(.05);
    TestTrue(TEXT("Unreachable target is never reserved or repeatedly replanned every step"),Crowd->Destinations()[0].Owner==-1&&Crowd->People()[0].Visit==-1&&Crowd->PlansRejected>0&&Crowd->PlansRejected<15);Crowd->Destroy();
    Data=AIWorld::Parse(Fixture);AIWorld::Object(Data,TEXT("navigation"))->GetArrayField(TEXT("edges"))[1]->AsObject()->SetNumberField(TEXT("length_cm"),-1);
    Crowd=World->SpawnActor<AParisPedestrianCrowd>();TestFalse(TEXT("Negative graph cost cannot load"),Crowd->Initialize(Data));Crowd->Destroy();return true;
}
#endif
