#include "ParisNightLighting.h"
#include "ParisDigitalTwin.h"
#include "WorldProtocol.h"
#include "Misc/AutomationTest.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Components/SpotLightComponent.h"
#include "Materials/MaterialParameterCollection.h"
#include "Materials/MaterialParameterCollectionInstance.h"
#include "Camera/CameraActor.h"
#include "Camera/PlayerCameraManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"

#if WITH_DEV_AUTOMATION_TESTS
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FParisNightWait,FAutomationTestBase*,Test);
bool FParisNightWait::Update(){
    static double Started=0;if(!Started)Started=FPlatformTime::Seconds();
    for(const auto& Context:GEngine->GetWorldContexts())if(auto World=Context.World())for(TActorIterator<AParisTwinScene> It(World);It;++It){
        auto Scene=*It;if(!Scene->bReady)continue;AParisNightLighting* Night=nullptr;int32 Actors=0;
        for(TActorIterator<AParisNightLighting> N(World);N;++N){Night=*N;Actors++;}
        if(!Test->TestNotNull(TEXT("Night lighting exists with real assets"),Night)){Started=0;return true;}
        Test->TestEqual(TEXT("Exactly one night-light manager"),Actors,1);
        Test->TestEqual(TEXT("Day starts with no artificial illumination"),Night->ActiveLights,0);
        TSet<FString> IDs;int32 Lamps=0;
        for(const auto& Source:Night->GetSources())if(Source.Kind==0){
            Test->TestFalse(TEXT("Mapped fixtures are never duplicated"),IDs.Contains(Source.SourceID));IDs.Add(Source.SourceID);Lamps++;
            auto Feature=Scene->SourceFeatureByID(Source.SourceID);Test->TestTrue(TEXT("Every lamp remains traceable to a GIS source"),Feature.IsValid());
            if(Feature){const auto& P=AIWorld::Array(Feature,TEXT("point_cm"));if(P.Num()==3)Test->TestTrue(TEXT("Night lighting preserves exact mapped XY"),FVector::Dist2D(Source.Position,FVector(P[0]->AsNumber(),P[1]->AsNumber(),P[2]->AsNumber()))<.01);}
        }
        Test->TestTrue(TEXT("The archived district includes hundreds of mapped lamps"),Lamps>400);
        auto PC=World->GetFirstPlayerController();auto OldView=PC->GetViewTarget();auto View=World->SpawnActor<ACameraActor>();
        View->SetActorLocation(Scene->QualityCentre+FVector(0,0,2000));PC->SetViewTarget(View);PC->PlayerCameraManager->UpdateCamera(0);
        const int32 OldQuality=Scene->DetailQuality;Scene->DetailQuality=1;
        Scene->CycleTimeOfDay();Scene->CycleTimeOfDay();Night->Synchronize(true);
        Test->TestTrue(TEXT("Night actually illuminates nearby surfaces"),Night->ActiveLights>0&&Night->ActiveLights<=17);
        Test->TestTrue(TEXT("Medium limits costly shadow lights"),Night->ShadowLights<=2);
        TArray<USpotLightComponent*> Lights;Night->GetComponents(Lights);Test->TestEqual(TEXT("A fixed reusable light pool bounds allocation"),Lights.Num(),34);
        for(auto Light:Lights)if(Light->IsVisible()){
            Test->TestTrue(TEXT("Visible lights emit positive photometric flux"),Light->Intensity>0&&Light->IntensityUnits==ELightUnits::Lumens);
            Test->TestTrue(TEXT("Street lighting uses warm colour temperature"),Light->Temperature>=2700&&Light->Temperature<=3300);
        }
        auto Collection=LoadObject<UMaterialParameterCollection>(nullptr,TEXT("/Game/Night/MPC_ParisNight"));
        Test->TestNotNull(TEXT("Window and lantern emission use a saved collection"),Collection);
        if(Collection){float Value=0;World->GetParameterCollectionInstance(Collection)->GetScalarParameterValue(TEXT("NightAmount"),Value);Test->TestTrue(TEXT("Window shaders receive the night preset"),Value>.99f);}
        Scene->ToggleWeather();Night->Tick(.1f);Test->TestTrue(TEXT("Rain does not extinguish night lights"),Night->ActiveLights>0&&Scene->bRainyWeather);Scene->ToggleWeather();
        Scene->DetailQuality=0;Night->Synchronize(true);Test->TestTrue(TEXT("Low bounds illumination without dynamic shadows"),Night->ActiveLights<=9&&Night->ShadowLights==0);
        Scene->DetailQuality=2;Night->Synchronize(true);Test->TestTrue(TEXT("High still respects the fixed pool and shadow limit"),Night->ActiveLights<=34&&Night->ShadowLights<=6);
        Scene->DetailQuality=1;Night->Synchronize(true);auto Report=MakeShared<FJsonObject>();Night->AddStats(Report);
        Scene->CycleTimeOfDay();Night->Synchronize(true);Test->TestEqual(TEXT("Returning to day turns off every local light"),Night->ActiveLights,0);
        for(auto Light:Lights)Test->TestTrue(TEXT("Day cannot leave hidden shadow work or light intensity"),!Light->IsVisible()&&!Light->CastShadows&&Light->Intensity==0);
        if(Collection){float Value=1;World->GetParameterCollectionInstance(Collection)->GetScalarParameterValue(TEXT("NightAmount"),Value);Test->TestEqual(TEXT("Day restores dark windows and lanterns"),Value,0.f);}
        Scene->DetailQuality=OldQuality;Night->Synchronize(true);PC->SetViewTarget(OldView);View->Destroy();
        FString Text;FJsonSerializer::Serialize(Report,TJsonWriterFactory<>::Create(&Text));FFileHelper::SaveStringToFile(Text,*(FPaths::ProjectSavedDir()/TEXT("paris-night-test.json")));
        Started=0;return true;
    }
    if(FPlatformTime::Seconds()-Started>120){Test->AddError(TEXT("Night scene readiness timeout"));Started=0;return true;}return false;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisNightTest,"ParisDigitalTwin.Live.NightLightingAndDayRestoration",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisNightTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FParisNightWait(this));return true;}
#endif
