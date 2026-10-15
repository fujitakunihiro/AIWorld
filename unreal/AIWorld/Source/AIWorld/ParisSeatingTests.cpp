#include "ParisPedestrians.h"
#include "WorldProtocol.h"
#include "Misc/AutomationTest.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Components/BoxComponent.h"

#if WITH_DEV_AUTOMATION_TESTS
static UWorld* SeatingWorld(){for(const auto& C:GEngine->GetWorldContexts())if(C.World())return C.World();return nullptr;}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisSeatingTest,"ParisDigitalTwin.Live.CafeSeatingLifecycle",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisSeatingTest::RunTest(const FString&){
    auto World=SeatingWorld();if(!TestNotNull(TEXT("World"),World))return false;
    const FString Fixture=TEXT(R"({"models":[],"routes":[{"id":"patrol","source_id":"osm/way/1","points_cm":[[150000,0,0],[152000,0,0]]},{"id":"approach","source_id":"osm/way/1","points_cm":[[150500,0,0],[150500,300,0]]},{"id":"seat","source_id":"osm/way/1","route_source":"inferred_reserved_seat_approach","points_cm":[[150500,300,0],[150500,450,0]]}],"agents":[{"id":"sim/person/0","route_id":"patrol","progress_m":2,"direction":1,"speed_mps":1.2}],"destinations":[{"id":"stop","business_id":"osm/node/1","name":"Seat Cafe","route_id":"approach","seat_route_id":"seat","seat_height_cm":48,"seat_facing_yaw_degrees":90,"parent_route_id":"patrol","parent_distance_cm":500,"capacity":1,"dwell_seconds":4,"facing_yaw_degrees":180}]})");
    auto Crowd=World->SpawnActor<AParisPedestrianCrowd>();Crowd->SetActorTickEnabled(false);if(!TestTrue(TEXT("Reserved seat fixture loads"),Crowd->Initialize(AIWorld::Parse(Fixture)))){Crowd->Destroy();return false;}
    bool Sat=false,Rose=false;FVector Previous=Crowd->People()[0].Position;double PreviousBlend=0;
    for(int32 I=0;I<1200;I++){Crowd->SimulateStep(.05);const auto& A=Crowd->People()[0];
        TestTrue(TEXT("No teleport through private approach or return"),FVector::Dist(Previous,A.Position)<=6.01);Previous=A.Position;
        TestTrue(TEXT("Sit and stand blend is bounded by elapsed time"),FMath::Abs(A.SeatBlend-PreviousBlend)<=.05001);PreviousBlend=A.SeatBlend;
        TestTrue(TEXT("Body root remains on the selected reserved route"),FVector::Dist(A.Position,Crowd->Network()[A.Route].Sample(A.Distance,A.Direction))<.001);
        if(A.VisitStage==3&&A.SeatBlend>.999){Sat=true;TestTrue(TEXT("Seated visitor holds exclusive chair and correct facing"),Crowd->Destinations()[0].Owner==0&&A.Route==2&&!A.Moving&&FMath::IsNearlyEqual(A.Yaw,90.));
            TestTrue(TEXT("Inspector reports actual seated state"),Crowd->DescribePerson(A.ID).Contains(TEXT("Reserved chair / sitting")));}
        if(Sat&&A.VisitStage==4&&A.SeatBlend<.001)Rose=true;
        if(Crowd->CompletedVisits){TestTrue(TEXT("Stand before leaving and restore original route and reservation"),Rose&&A.Route==0&&A.VisitStage==0&&A.SeatBlend==0&&Crowd->Destinations()[0].Owner==-1&&A.VisitCooldown>0);break;}
    }
    TestTrue(TEXT("Visitor sits, stands and completes return"),Sat&&Rose&&Crowd->CompletedVisits==1);TestEqual(TEXT("One actual chair arrival recorded"),Crowd->SeatArrivals,1);Crowd->Destroy();
    const auto Pose=ParisPersonPose(FVector::ZeroVector,0,0,false,1,48);
    TestEqual(TEXT("Seated pose has separate knees"),Pose.Num(),8);
    TestTrue(TEXT("Pelvis on 48cm seat and knees in front"),FMath::IsNearlyEqual(Pose[0].GetLocation().Z+84,48.)&&FMath::IsNearlyEqual(Pose[6].GetLocation().X,40.)&&FMath::IsNearlyEqual(Pose[6].GetLocation().Z,48.));
    // Invalid private geometry cannot silently become a public approach.
    auto Data=AIWorld::Parse(Fixture);Data->GetArrayField(TEXT("destinations"))[0]->AsObject()->SetStringField(TEXT("seat_route_id"),TEXT("patrol"));
    Crowd=World->SpawnActor<AParisPedestrianCrowd>();TestFalse(TEXT("Wrong seat route rejected"),Crowd->Initialize(Data));Crowd->Destroy();
    Data=AIWorld::Parse(Fixture);auto Graph=AIWorld::Parse(TEXT(R"({"nodes":[{"id":"entry","route_id":"patrol","distance_cm":500,"position_cm":[150500,0,0]},{"id":"private","route_id":"seat","distance_cm":150,"position_cm":[150500,450,0]}],"edges":[]})"));
    Data->SetObjectField(TEXT("navigation"),Graph);Data->GetArrayField(TEXT("destinations"))[0]->AsObject()->SetStringField(TEXT("navigation_node_id"),TEXT("entry"));
    Crowd=World->SpawnActor<AParisPedestrianCrowd>();TestFalse(TEXT("Private chair cannot be exposed as a public graph node"),Crowd->Initialize(Data));Crowd->Destroy();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisSocialTest,"ParisDigitalTwin.Live.LocalSocialInteraction",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisSocialTest::RunTest(const FString&){
    auto World=SeatingWorld();if(!TestNotNull(TEXT("World"),World))return false;
    const FString Fixture=TEXT(R"({"models":[],"social":{"enabled":true,"range_cm":280,"duration_seconds":2.5,"cooldown_seconds":25},"routes":[{"id":"left","source_id":"osm/way/1","points_cm":[[150000,0,0],[150000,200,0]]},{"id":"right","source_id":"osm/way/1","points_cm":[[150180,0,0],[150180,200,0]]}],"agents":[{"id":"sim/person/0","route_id":"left","progress_m":1.9,"direction":1,"speed_mps":1},{"id":"sim/person/1","route_id":"right","progress_m":1.9,"direction":1,"speed_mps":1}]})");
    auto Crowd=World->SpawnActor<AParisPedestrianCrowd>();Crowd->SetActorTickEnabled(false);if(!TestTrue(TEXT("Social fixture loads"),Crowd->Initialize(AIWorld::Parse(Fixture)))){Crowd->Destroy();return false;}
    bool Paired=false,Finished=false;double TravelBefore=0;
    for(int32 I=0;I<400;I++){Crowd->SimulateStep(.05);const auto& A=Crowd->People()[0];const auto& B=Crowd->People()[1];
        TestTrue(TEXT("Pair always reciprocal"),(A.SocialPartner==1)==(B.SocialPartner==0));
        if(A.SocialPartner==1){Paired=true;TestTrue(TEXT("Brief greeting has a real partner and bounded duration"),A.SocialRemaining<=2.5&&B.SocialRemaining<=2.5&&!A.Moving&&!B.Moving);TestTrue(TEXT("Inspector uses active greeting state"),Crowd->DescribePerson(A.ID).Contains(TEXT("Bonjour")));TravelBefore=Crowd->TravelledCm;}
        if(Paired&&Crowd->SocialCompleted>0){Finished=true;TestTrue(TEXT("Greeting releases both people with cooldown"),A.SocialPartner==-1&&B.SocialPartner==-1&&A.SocialCooldown>0&&B.SocialCooldown>0);}
    }
    TestTrue(TEXT("One short conversation completes, then patrol resumes"),Paired&&Finished&&Crowd->SocialStarted==1&&Crowd->TravelledCm>TravelBefore+100);Crowd->Destroy();
    auto Wall=World->SpawnActor<AActor>();auto Box=NewObject<UBoxComponent>(Wall);Wall->SetRootComponent(Box);Wall->AddInstanceComponent(Box);Box->SetBoxExtent(FVector(10,500,200));Box->SetCollisionProfileName(TEXT("BlockAll"));Box->RegisterComponent();Wall->SetActorLocation(FVector(150090,100,150));
    Crowd=World->SpawnActor<AParisPedestrianCrowd>();Crowd->SetActorTickEnabled(false);TestTrue(TEXT("Occlusion fixture loads"),Crowd->Initialize(AIWorld::Parse(Fixture)));
    for(int32 I=0;I<1000;I++)Crowd->SimulateStep(.05);
    TestEqual(TEXT("No conversation through a wall over 1000 steps"),Crowd->SocialStarted,0);Crowd->Destroy();Wall->Destroy();
    return true;
}
#endif
