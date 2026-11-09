#include "ParisMorris.h"
#include "ParisDigitalTwin.h"
#include "Components/CapsuleComponent.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FParisMorrisWait,FAutomationTestBase*,Test);
bool FParisMorrisWait::Update(){
    static double Started=0;if(!Started)Started=FPlatformTime::Seconds();
    for(const auto& Context:GEngine->GetWorldContexts())if(auto World=Context.World())for(TActorIterator<AParisTwinScene> It(World);It;++It){
        auto S=*It;if(!S->bReady)continue;
        TArray<UHierarchicalInstancedStaticMeshComponent*> All,Parts;S->GetComponents(All);
        for(auto C:All)if(C->ComponentHasTag(TEXT("ParisMorris")))Parts.Add(C);
        TArray<UCapsuleComponent*> Capsules,Colliders;S->GetComponents(Capsules);
        for(auto C:Capsules)if(C->ComponentHasTag(TEXT("ParisMorrisCollider")))Colliders.Add(C);
        Test->TestEqual(TEXT("Four shared iron and poster meshes load"),Parts.Num(),4);
        Test->TestEqual(TEXT("Eight mapped objects retain a walking collision proxy"),Colliders.Num(),8);
        int32 Instances=0,Columns=0,Signs=0;
        for(auto C:Parts){Instances+=C->GetInstanceCount();Test->TestTrue(TEXT("Prop mesh exists"),C->GetStaticMesh()!=nullptr);Test->TestTrue(TEXT("Prop material exists"),C->GetMaterial(0)!=nullptr);}
        for(auto C:Colliders){Columns+=C->ComponentHasTag(TEXT("ParisMorrisColumn"))?1:0;Signs+=C->ComponentHasTag(TEXT("ParisMorrisSign"))?1:0;
            Test->TestEqual(TEXT("Visible street prop blocks walking"),C->GetCollisionResponseToChannel(ECC_Pawn),ECR_Block);}
        Test->TestEqual(TEXT("Each position has iron and posters"),Instances,16);Test->TestEqual(TEXT("Mapped columns"),Columns,7);Test->TestEqual(TEXT("Mapped public poster box"),Signs,1);
        if(Colliders.Num()){
            FHitResult Hit;Hit.Component=Colliders[0];Hit.ImpactPoint=Colliders[0]->GetComponentLocation();
            Test->TestTrue(TEXT("Prop inspection recognizes collider"),SelectParisMorrisHit(S,Hit));
            Test->TestTrue(TEXT("Inspection retains OSM identifier"),S->Selection.Contains(TEXT("osm/node/")));
            Test->TestTrue(TEXT("Inspection displays geographic coordinates"),S->SelectionCoordinates.Contains(TEXT("WGS84")));S->ClearInspection();
        }
        const bool Old=S->bStreetDetails;if(!Old)S->ToggleStreetDetails();
        for(auto C:Parts)Test->TestTrue(TEXT("Details enabled: visible"),C->IsVisible());
        S->ToggleStreetDetails();for(auto C:Parts)Test->TestFalse(TEXT("Details hidden: prop hidden"),C->IsVisible());
        for(auto C:Colliders)Test->TestEqual(TEXT("Hidden prop does not block walking"),C->GetCollisionEnabled(),ECollisionEnabled::NoCollision);
        S->ToggleStreetDetails();if(!Old)S->ToggleStreetDetails();Started=0;return true;
    }
    if(FPlatformTime::Seconds()-Started>120){Test->AddError(TEXT("Morris scene readiness timeout"));Started=0;return true;}return false;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisMorrisTest,"ParisDigitalTwin.Live.MappedMorrisAndStreetSigns",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisMorrisTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FParisMorrisWait(this));return true;}
#endif
