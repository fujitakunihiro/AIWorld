#include "ParisDigitalTwin.h"
#include "ParisLuxury.h"
#include "ParisNightLighting.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Engine/PostProcessVolume.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/SpotLightComponent.h"
#include "Materials/MaterialParameterCollection.h"
#include "Materials/MaterialParameterCollectionInstance.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FParisFestivalWait,FAutomationTestBase*,Test);
bool FParisFestivalWait::Update(){
    for(const auto& Context:GEngine->GetWorldContexts())if(auto World=Context.World())for(TActorIterator<AParisTwinScene> It(World);It;++It){
        auto S=*It;if(!S->bReady)continue;
        const bool OldMode=IsParisFestivalEnabled(S),OldDetails=S->bStreetDetails;const int32 OldTime=S->TimeOfDayPreset;
        if(!S->bStreetDetails)S->ToggleStreetDetails();while(S->TimeOfDayPreset!=2)S->CycleTimeOfDay();
        if(!IsParisFestivalEnabled(S))ToggleParisFestival(S);
        Test->TestTrue(TEXT("Party mode enables independently of GIS"),IsParisFestivalEnabled(S));
        TArray<UHierarchicalInstancedStaticMeshComponent*> Parts;S->GetComponents(Parts);int32 Groups=0;
        for(auto C:Parts)if(C->ComponentHasTag(TEXT("ParisFestival"))){Groups++;Test->TestTrue(TEXT("Festival meshes actually visible"),C->IsVisible());Test->TestFalse(TEXT("Decorative glow adds no shadow rendering"),C->CastShadow);Test->TestEqual(TEXT("Hanging decoration cannot block walking"),C->GetCollisionEnabled(),ECollisionEnabled::NoCollision);}
        Test->TestEqual(TEXT("Nine shared mesh groups cover the party layer"),Groups,9);
        auto Collection=LoadObject<UMaterialParameterCollection>(nullptr,TEXT("/Game/Night/MPC_ParisNight"));
        auto Instance=Collection?World->GetParameterCollectionInstance(Collection):nullptr;Test->TestNotNull(TEXT("Saved festival collection exists"),Instance);
        auto CheckAmount=[&](float Expected){float Value=-1;if(Instance)Test->TestTrue(TEXT("Festival scalar exists"),Instance->GetScalarParameterValue(TEXT("FestivalAmount"),Value));Test->TestEqual(TEXT("Window colours follow active visibility"),Value,Expected);};CheckAmount(1);
        S->ToggleStreetDetails();CheckAmount(0);for(auto C:Parts)if(C->ComponentHasTag(TEXT("ParisFestival")))Test->TestFalse(TEXT("F6 hides the complete party layer"),C->IsVisible());S->ToggleStreetDetails();CheckAmount(1);
        for(TActorIterator<AParisNightLighting> N(World);N;++N){auto Report=MakeShared<FJsonObject>();N->AddStats(Report);Test->TestEqual(TEXT("Party mode reuses the existing fixed light pool"),(int32)Report->GetNumberField(TEXT("night_light_pool")),34);}
        ToggleParisFestival(S);CheckAmount(0);for(auto C:Parts)if(C->ComponentHasTag(TEXT("ParisFestival")))Test->TestFalse(TEXT("Normal mode removes all party geometry"),C->IsVisible());
        for(TActorIterator<AParisNightLighting> N(World);N;++N){TArray<USpotLightComponent*> Lights;N->GetComponents(Lights);for(auto L:Lights)if(L->IsVisible()){Test->TestTrue(TEXT("Normal mode restores colour temperature"),L->bUseTemperature);const auto Color=L->GetLightColor();Test->TestTrue(TEXT("Normal mode restores white light tint"),Color.Equals(FLinearColor::White,.001f));}}
        for(TActorIterator<APostProcessVolume> V(World);V;++V)if(V->ActorHasTag(TEXT("ParisPhotoEnvironment")))Test->TestEqual(TEXT("Normal night restores the original bloom"),V->Settings.BloomIntensity,.35f);
        if(OldMode)ToggleParisFestival(S);while(S->TimeOfDayPreset!=OldTime)S->CycleTimeOfDay();if(!OldDetails)S->ToggleStreetDetails();return true;
    }return false;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisFestivalTest,"ParisDigitalTwin.Live.FestivalModeAndRestoration",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisFestivalTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FParisFestivalWait(this));return true;}
#endif
