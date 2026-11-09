#include "ParisDigitalTwin.h"
#include "ParisPedestrians.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/DirectionalLight.h"
#include "EngineUtils.h"
#include "Components/StaticMeshComponent.h"
#include "Components/LightComponent.h"
#include "Materials/Material.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FParisRealismWait,FAutomationTestBase*,Test);
bool FParisRealismWait::Update(){
    for(const auto& Context:GEngine->GetWorldContexts())if(auto World=Context.World())for(TActorIterator<AParisTwinScene> It(World);It;++It){
        auto Scene=*It;if(!Scene->bReady)continue;
        AStaticMeshActor* Sky=nullptr;int32 Count=0;
        for(TActorIterator<AStaticMeshActor> Actor(World);Actor;++Actor)if(Actor->ActorHasTag(TEXT("ParisPhotographicSky"))){Sky=*Actor;Count++;}
        Test->TestEqual(TEXT("Reuse a single photographic sky dome"),Count,1);if(!Sky)return true;
        const int32 Time=Scene->TimeOfDayPreset;const bool Rain=Scene->bRainyWeather;
        if(Rain)Scene->ToggleWeather();while(Scene->TimeOfDayPreset!=0)Scene->CycleTimeOfDay();
        Scene->CycleTimeOfDay();auto Mesh=Sky->GetStaticMeshComponent();
        Test->TestFalse(TEXT("Evening keeps cloud detail visible"),Sky->IsHidden());
        Test->TestEqual(TEXT("Evening uses its saved photographic material"),Mesh->GetMaterial(0)->GetMaterial()->GetName(),FString(TEXT("M_ParisEveningSky")));
        Test->TestEqual(TEXT("Sky never blocks walking or selection"),Mesh->GetCollisionEnabled(),ECollisionEnabled::NoCollision);
        for(TActorIterator<ADirectionalLight> Sun(World);Sun;++Sun)if(Sun->ActorHasTag(TEXT("ParisPhotoEnvironment"))){
            const auto Color=Sun->GetLightComponent()->GetLightColor();Test->TestTrue(TEXT("Evening avoids stacking saturated orange tint on temperature"),FMath::Abs(Color.R-Color.G)<.06f&&FMath::Abs(Color.R-Color.B)<.06f);
        }
        Scene->ToggleWeather();Test->TestFalse(TEXT("Rain cannot leave the sky hidden"),Sky->IsHidden());Scene->ToggleWeather();
        Test->TestEqual(TEXT("Leaving rain restores evening material"),Mesh->GetMaterial(0)->GetMaterial()->GetName(),FString(TEXT("M_ParisEveningSky")));
        Scene->CycleTimeOfDay();Test->TestEqual(TEXT("Night retains its own sky"),Mesh->GetMaterial(0)->GetMaterial()->GetName(),FString(TEXT("M_ParisNightSky")));
        Scene->CycleTimeOfDay();Test->TestEqual(TEXT("Day retains its original HDR panorama"),Mesh->GetMaterial(0)->GetMaterial()->GetName(),FString(TEXT("M_ParisPhotographicSky")));
        if(Scene->Crowd){
            auto Crowd=Scene->Crowd;const bool Enabled=Crowd->bEnabled;const int32 Quality=Scene->DetailQuality;
            Crowd->SetDisplay(true,1);Test->TestEqual(TEXT("Medium human range covers street-level views"),Crowd->HumanVisualRangeCm(),6000.);Test->TestEqual(TEXT("Medium skeletal budget stays bounded"),Crowd->HumanVisualBudget(),8);
            Crowd->SetDisplay(true,0);Test->TestEqual(TEXT("Low quality uses cheap crowd visuals"),Crowd->HumanVisualRangeCm(),0.);
            Crowd->SetDisplay(true,2);Test->TestEqual(TEXT("High human pool remains bounded"),Crowd->HumanVisualBudget(),16);Crowd->SetDisplay(Enabled,Quality);
        }
        while(Scene->TimeOfDayPreset!=Time)Scene->CycleTimeOfDay();if(Rain)Scene->ToggleWeather();return true;
    }return false;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisRealismTest,"ParisDigitalTwin.Live.StreetRealismRenderingPolicy",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisRealismTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FParisRealismWait(this));return true;}
#endif
