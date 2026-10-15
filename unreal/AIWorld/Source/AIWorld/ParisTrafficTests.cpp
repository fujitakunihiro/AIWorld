#include "ParisDigitalTwin.h"
#include "ParisTraffic.h"
#include "Camera/PlayerCameraManager.h"
#include "Misc/AutomationTest.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Components/InstancedStaticMeshComponent.h"

#if WITH_DEV_AUTOMATION_TESTS
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FParisTrafficWait,FAutomationTestBase*,Test);
bool FParisTrafficWait::Update(){
    static double Started=0;if(Started==0)Started=FPlatformTime::Seconds();
    for(const auto& Context:GEngine->GetWorldContexts())if(Context.World())for(TActorIterator<AParisTwinScene> It(Context.World());It;++It){auto Scene=*It;if(!Scene->bReady||!Scene->Traffic||!Scene->Traffic->bReady)continue;auto Traffic=Scene->Traffic;
        Test->TestTrue(TEXT("Actual GIS road segments generate preview cars"),Traffic->Vehicles().Num()>15&&Traffic->Network().Num()>10);
        const double Before=Traffic->TravelledCm;for(int32 I=0;I<1000;I++)Traffic->SimulateStep(.05);
        Test->TestTrue(TEXT("1000 fixed traffic steps continue to move"),Traffic->TravelledCm>Before+1000);
        Test->TestTrue(TEXT("Segment end recycling remains live"),Traffic->Recycles>0);
        const auto& Cars=Traffic->Vehicles();
        for(int32 I=0;I<Cars.Num();I++){const auto& A=Cars[I];const auto& R=Traffic->Network()[A.Route];Test->TestTrue(TEXT("Vehicle position finite and on its original directed GIS route"),!A.Position.ContainsNaN()&&A.Distance>=0&&A.Distance<=R.Length+.001&&FVector::Dist(A.Position,R.Sample(A.Distance,1))<.01);
            for(int32 J=I+1;J<Cars.Num();J++)if(A.bActive&&Cars[J].bActive&&FMath::Abs(A.Position.Z-Cars[J].Position.Z)<200)Test->TestTrue(TEXT("Cars do not consume overlapping swept clearances"),FVector::Dist2D(A.Position,Cars[J].Position)>480);
        }
        for(int32 I=0;I<Cars.Num();I++)if(Cars[I].bActive&&Cars[I].Wait<=0){const auto A=Cars[I];const FVector Player=Traffic->Network()[A.Route].Sample(A.Distance+A.Speed*.05,1);const int32 Yields=Traffic->YieldSteps;Traffic->SimulateStep(.05,&Player);Test->TestEqual(TEXT("Car stops before a nearby player"),Traffic->Vehicles()[I].Distance,A.Distance);Test->TestTrue(TEXT("Yield reason registered"),Traffic->YieldSteps>Yields);break;}
        if(auto PC=Cast<AParisTwinController>(Context.World()->GetFirstPlayerController())){PC->InspectTraffic();if(auto Camera=Cast<AParisTwinCamera>(PC->GetPawn()))Camera->Tick(0);if(PC->PlayerCameraManager)PC->PlayerCameraManager->UpdateCamera(0);}
        Traffic->SetDisplay(true,0);Test->TestTrue(TEXT("Near camera cars use the low distance budget"),Traffic->RenderedCount>0&&Traffic->RenderedCount<=20);Scene->ApplyDetailQuality();
        Traffic->UpdateInstances();TArray<UInstancedStaticMeshComponent*> Meshes;Traffic->GetComponents(Meshes);bool Picked=false;
        for(auto Mesh:Meshes)if(Mesh->GetInstanceCount()>0){FTransform T;Mesh->GetInstanceTransform(0,T,true);FHitResult Hit(Traffic,Mesh,T.GetLocation(),FVector::UpVector);Hit.Item=0;Scene->SelectHit(Hit);Test->TestTrue(TEXT("Vehicle selection traces original road and inferred status"),Scene->Selection.Contains(TEXT("SIMULATED car"))&&Scene->Selection.Contains(TEXT("osm/way/"))&&Scene->Selection.Contains(TEXT("CLICK WGS84")));Picked=true;break;}
        Test->TestTrue(TEXT("Shared vehicle instances selectable"),Picked);
        if(auto PC=Cast<AParisTwinController>(Context.World()->GetFirstPlayerController())){PC->InspectTraffic();auto Camera=Cast<AParisTwinCamera>(PC->GetPawn());Test->TestTrue(TEXT("Car inspection gives a usable close view"),Camera&&Camera->bEye&&!Scene->SourceAt(Camera->Target,TEXT("building")).IsValid());PC->Overview();}
        const int32 Budget=Traffic->VisibleBudget,Count=Cars.Num(),Quality=Scene->DetailQuality;
        Scene->CycleDetailQuality();Scene->CycleDetailQuality();Scene->CycleDetailQuality();Test->TestEqual(TEXT("Quality restores car budget"),Traffic->VisibleBudget,Budget);Test->TestEqual(TEXT("Quality restores preset"),Scene->DetailQuality,Quality);Test->TestEqual(TEXT("Quality never removes simulation cars"),Traffic->Vehicles().Num(),Count);
        Scene->ToggleTraffic();for(auto Mesh:Meshes)Test->TestTrue(TEXT("Disabled traffic neither draws nor intercepts selection"),!Mesh->IsVisible()&&Mesh->GetCollisionEnabled()==ECollisionEnabled::NoCollision);
        Scene->ToggleFootprints();Scene->ToggleFootprints();Test->TestFalse(TEXT("Footprint cycle retains user-disabled traffic"),Traffic->bEnabled);
        Scene->ToggleTraffic();Test->TestTrue(TEXT("Traffic restored"),Traffic->bEnabled);
        Started=0;return true;
    }
    if(FPlatformTime::Seconds()-Started>25){Test->AddError(TEXT("Traffic did not load with the GIS scene"));Started=0;return true;}return false;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisTrafficLiveTest,"ParisDigitalTwin.Live.TrafficAndMappedProps",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisTrafficLiveTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FParisTrafficWait(this));return true;}
#endif
