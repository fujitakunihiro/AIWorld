#include "ParisReference.h"
#include "ParisDigitalTwin.h"
#include "Components/BoxComponent.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Materials/MaterialInterface.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Misc/AutomationTest.h"
#if WITH_DEV_AUTOMATION_TESTS
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FParisLaneWait,FAutomationTestBase*,Test);
bool FParisLaneWait::Update(){
    static double Started=0;if(!Started)Started=FPlatformTime::Seconds();
    for(const auto& Context:GEngine->GetWorldContexts())if(auto W=Context.World())for(TActorIterator<AParisTwinScene> It(W);It;++It){auto S=*It;if(!S->bReady)continue;
        Test->TestTrue(TEXT("Everyday lane mode active"),IsParisLaneDressed());auto Report=MakeShared<FJsonObject>();AddParisReferenceStats(S,Report);auto Lane=Report->GetObjectField(TEXT("lane"));Test->TestTrue(TEXT("Parked bicycles actually instantiated"),Lane->GetNumberField(TEXT("bicycles"))>=10);
        TArray<UBoxComponent*> All,Boxes;S->GetComponents(All);for(auto C:All)if(C->ComponentHasTag(TEXT("ParisLaneCollision")))Boxes.Add(C);Test->TestTrue(TEXT("Street furniture has bounded physical collision"),Boxes.Num()>=15);
        for(auto C:Boxes){Test->TestEqual(TEXT("Bikes and planters block the walker"),C->GetCollisionEnabled(),ECollisionEnabled::QueryAndPhysics);Test->TestTrue(TEXT("Physical proxy retains source geographic ID"),C->ComponentTags.ContainsByPredicate([](FName N){return N.ToString().StartsWith(TEXT("osm/"));}));}
        if(Boxes.Num()){FHitResult Hit;Hit.Component=Boxes[0];Test->TestTrue(TEXT("Street prop can be inspected"),SelectParisLaneHit(S,Hit));Test->TestTrue(TEXT("Source coordinates shown"),S->SelectionCoordinates.Contains(TEXT("WGS84")));S->ClearInspection();}
        TArray<UStaticMeshComponent*> Ground;S->GetComponents(Ground);bool Bound=false;for(auto C:Ground)if(C->ComponentHasTag(TEXT("ParisGroundDisplay")))Bound=C->GetMaterial(0)&&C->GetMaterial(0)->GetName()==TEXT("M_ParisLanePaving");Test->TestTrue(TEXT("Fan paving is bound to visible ground, not hidden below it"),Bound);
        TArray<UHierarchicalInstancedStaticMeshComponent*> Parts;S->GetComponents(Parts);int32 Rendered=0;for(auto C:Parts)if(C->ComponentHasTag(TEXT("ParisLane"))&&C->GetInstanceCount()>0){Rendered++;Test->TestTrue(TEXT("Lane detail visible"),C->IsVisible());}
        Test->TestTrue(TEXT("Installed shop/bicycle/plant material groups"),Rendered>=10);
        S->ToggleStreetDetails();for(auto C:Boxes)Test->TestEqual(TEXT("F6 removes invisible street blockers"),C->GetCollisionEnabled(),ECollisionEnabled::NoCollision);S->ToggleStreetDetails();
        S->ToggleLevels();for(auto C:Boxes)Test->TestEqual(TEXT("Accuracy overlay removes prop blockers"),C->GetCollisionEnabled(),ECollisionEnabled::NoCollision);S->ToggleLevels();
        for(int32 I=0;I<3;I++)S->CycleTimeOfDay();S->ToggleWeather();S->ToggleWeather();for(auto C:Boxes)Test->TestEqual(TEXT("Time and weather restore prop collision"),C->GetCollisionEnabled(),ECollisionEnabled::QueryAndPhysics);Started=0;return true;
    }
    if(FPlatformTime::Seconds()-Started>180){Test->AddError(TEXT("Lane scene readiness timeout"));Started=0;return true;}return false;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisLaneTest,"ParisDigitalTwin.Live.LaneSurfacePropsAndRestoration",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisLaneTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FParisLaneWait(this));return true;}
#endif
