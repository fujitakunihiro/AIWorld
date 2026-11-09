#include "ParisReference.h"
#include "ParisDigitalTwin.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Engine/StaticMesh.h"
#include "EngineUtils.h"
#include "Misc/AutomationTest.h"
#if WITH_DEV_AUTOMATION_TESTS
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FParisReferenceWait,FAutomationTestBase*,Test);
bool FParisReferenceWait::Update(){
    static double Started=0;if(!Started)Started=FPlatformTime::Seconds();
    for(const auto& Context:GEngine->GetWorldContexts())if(auto W=Context.World())for(TActorIterator<AParisTwinScene> It(W);It;++It){auto S=*It;if(!S->bReady)continue;
        Test->TestTrue(TEXT("Reference profile explicitly enabled"),IsParisReferenceLook());
        auto Stats=MakeShared<FJsonObject>();AddParisReferenceStats(S,Stats);Test->TestTrue(TEXT("Architectural attachments actually loaded"),Stats->GetNumberField(TEXT("reference_instances"))>10000);Test->TestTrue(TEXT("Tiled cornice and shared window meshes exist"),Stats->GetNumberField(TEXT("reference_models"))>=10);
        Test->TestNotNull(TEXT("Actual imported avenue tree asset"),LoadObject<UStaticMesh>(nullptr,TEXT("/Game/ParisPhotoreal/ReferenceNature/SM_ParisAvenueTree")));
        if(IsParisSeineDressed()){
            int32 Water=0;TArray<UPrimitiveComponent*> Visuals;S->GetComponents(Visuals);
            for(auto C:Visuals)if(C->GetMaterial(0)&&C->GetMaterial(0)->GetName()==TEXT("M_ParisSeineWater")){Water++;Test->TestTrue(TEXT("Calm water is bound to actual visible geometry"),C->IsVisible());}
            Test->TestEqual(TEXT("One Seine visual uses private calm water"),Water,1);
        }
        TArray<UStaticMeshComponent*> GroundParts;S->GetComponents(GroundParts);for(auto C:GroundParts)if(C->ComponentHasTag(TEXT("ParisGroundDisplay")))Test->TestEqual(TEXT("Physical ground continues outside the old cathedral photo zone"),C->GetMaterial(0)->GetName(),FString(TEXT("M_ParisRoadPaving")));
        const bool Old=S->bStreetDetails;if(!Old)S->ToggleStreetDetails();TArray<UHierarchicalInstancedStaticMeshComponent*> Parts;S->GetComponents(Parts);
        for(auto C:Parts)if(C->ComponentHasTag(TEXT("ParisReference"))){Test->TestTrue(TEXT("Source-aligned detail visible"),C->IsVisible());Test->TestNotNull(TEXT("Saved physical material exists"),C->GetMaterial(0));Test->TestEqual(TEXT("Display relief does not alter source collision"),C->GetCollisionEnabled(),ECollisionEnabled::NoCollision);}
        TArray<UBoxComponent*> Boxes;S->GetComponents(Boxes);for(auto C:Boxes)if(C->ComponentHasTag(TEXT("ParisStreetPropCollision")))Test->TestEqual(TEXT("Hidden festive props leave no invisible blocker"),C->GetCollisionEnabled(),ECollisionEnabled::NoCollision);
        TArray<UCapsuleComponent*> Capsules;S->GetComponents(Capsules);for(auto C:Capsules)if(C->ComponentHasTag(TEXT("ParisLuxuryUrn")))Test->TestEqual(TEXT("Hidden urn collision disabled"),C->GetCollisionEnabled(),ECollisionEnabled::NoCollision);
        S->ToggleStreetDetails();for(auto C:Parts)if(C->ComponentHasTag(TEXT("ParisReference")))Test->TestFalse(TEXT("F6 hides reference architecture"),C->IsVisible());S->ToggleStreetDetails();
        S->ToggleLevels();for(auto C:Parts)if(C->ComponentHasTag(TEXT("ParisReference")))Test->TestFalse(TEXT("Accuracy overlay remains readable"),C->IsVisible());S->ToggleLevels();
        const int32 OldTime=S->TimeOfDayPreset;const bool OldRain=S->bRainyWeather;
        for(int32 I=0;I<3;I++)S->CycleTimeOfDay();S->ToggleWeather();S->ToggleWeather();
        Test->TestEqual(TEXT("Day sunset night cycle returns to original time"),S->TimeOfDayPreset,OldTime);Test->TestEqual(TEXT("Rain cycle returns to original weather"),S->bRainyWeather,OldRain);
        for(auto C:Parts)if(C->ComponentHasTag(TEXT("ParisReference")))Test->TestTrue(TEXT("Appearance restores after time/weather/debug changes"),C->IsVisible());
        if(!Old)S->ToggleStreetDetails();Started=0;return true;
    }
    if(FPlatformTime::Seconds()-Started>180){Test->AddError(TEXT("Reference scene readiness timeout"));Started=0;return true;}return false;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisReferenceTest,"ParisDigitalTwin.Live.ReferenceArchitectureAndRestoration",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisReferenceTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FParisReferenceWait(this));return true;}
#endif
