#include "ParisWeathering.h"
#include "ParisDigitalTwin.h"
#include "Components/StaticMeshComponent.h"
#include "Components/SkyLightComponent.h"
#include "Engine/SkyLight.h"
#include "Engine/StaticMesh.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FParisWeatheringWait,FAutomationTestBase*,Test);
bool FParisWeatheringWait::Update(){
    static double Started=0;if(!Started)Started=FPlatformTime::Seconds();
    for(const auto& Context:GEngine->GetWorldContexts())if(auto World=Context.World())for(TActorIterator<AParisTwinScene> It(World);It;++It){
        auto S=*It;if(!S->bReady)continue;
        TArray<UStaticMeshComponent*> All,Parts;S->GetComponents(All);for(auto C:All)if(C->ComponentHasTag(TEXT("ParisWeathering")))Parts.Add(C);
        Test->TestTrue(TEXT("Tiled walls and road grime load"),Parts.Num()>10&&Parts.Num()<=256);
        for(auto C:Parts){Test->TestTrue(TEXT("Weathering has a saved mesh"),C->GetStaticMesh()!=nullptr);Test->TestTrue(TEXT("Weathering has a saved material"),C->GetMaterial(0)!=nullptr);
            Test->TestEqual(TEXT("Cosmetic stains never block walking"),C->GetCollisionEnabled(),ECollisionEnabled::NoCollision);Test->TestFalse(TEXT("Cosmetic stains cast no dynamic shadows"),C->CastShadow);}
        const int32 Quality=S->DetailQuality;const bool Detailed=S->bDetailedSurfaces;S->DetailQuality=1;if(!S->bDetailedSurfaces)S->ToggleSurfaces();S->ApplyDetailQuality();
        for(auto C:Parts)Test->TestTrue(TEXT("Weathering appears in detailed view"),C->IsVisible());
        S->ToggleSurfaces();for(auto C:Parts)Test->TestFalse(TEXT("Flat material view hides weathering"),C->IsVisible());S->ToggleSurfaces();
        S->DetailQuality=0;S->ApplyDetailQuality();for(auto C:Parts)Test->TestFalse(TEXT("Low quality hides the cosmetic layer"),C->IsVisible());
        S->DetailQuality=Quality;if(S->bDetailedSurfaces!=Detailed)S->ToggleSurfaces();S->ApplyDetailQuality();
        const int32 OldTime=S->TimeOfDayPreset;float Intensities[3]={};
        while(S->TimeOfDayPreset!=0)S->CycleTimeOfDay();
        for(int32 T=0;T<3;T++){for(TActorIterator<ASkyLight> Sky(World);Sky;++Sky)if(Sky->ActorHasTag(TEXT("ParisPhotoEnvironment")))Intensities[T]=Sky->GetLightComponent()->Intensity;S->CycleTimeOfDay();}
        Test->TestTrue(TEXT("Day, sunset and night retain positive ordered sky fill"),Intensities[0]>Intensities[1]&&Intensities[1]>Intensities[2]&&Intensities[2]>0);
        while(S->TimeOfDayPreset!=OldTime)S->CycleTimeOfDay();Started=0;return true;
    }
    if(FPlatformTime::Seconds()-Started>120){Test->AddError(TEXT("Weathering scene readiness timeout"));Started=0;return true;}return false;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisWeatheringTest,"ParisDigitalTwin.Live.LocalWeatheringAndSkyPresets",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisWeatheringTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FParisWeatheringWait(this));return true;}
#endif
