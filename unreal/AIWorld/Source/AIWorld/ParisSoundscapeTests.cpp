#include "ParisSoundscape.h"
#include "ParisDigitalTwin.h"
#include "ParisRainWeather.h"
#include "ParisCruise.h"
#include "Misc/AutomationTest.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Components/AudioComponent.h"
#include "Sound/SoundWave.h"
#include "Camera/CameraActor.h"
#include "Camera/PlayerCameraManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"

#if WITH_DEV_AUTOMATION_TESTS
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FParisSoundscapeWait,FAutomationTestBase*,Test);
bool FParisSoundscapeWait::Update(){
    static double Started=0;if(!Started)Started=FPlatformTime::Seconds();
    for(const auto& Context:GEngine->GetWorldContexts())if(auto World=Context.World())for(TActorIterator<AParisTwinScene> It(World);It;++It){
        auto Scene=*It;if(!Scene->bReady)continue;AParisSoundscape* Sound=nullptr;int32 Count=0;
        for(TActorIterator<AParisSoundscape> A(World);A;++A){Sound=*A;Count++;}
        if(!Test->TestNotNull(TEXT("Soundscape is present with real assets"),Sound)){Started=0;return true;}
        Test->TestEqual(TEXT("Exactly one soundscape actor"),Count,1);CreateParisSoundscape(Scene,nullptr);
        Count=0;for(TActorIterator<AParisSoundscape> A(World);A;++A)Count++;Test->TestEqual(TEXT("Repeated creation does not duplicate voices"),Count,1);
        Test->TestTrue(TEXT("Bell remains linked to the actual cathedral source ID"),Scene->SourceFeatureByID(Sound->BellAnchor().SourceID).IsValid());
        Test->TestTrue(TEXT("Bell is placed at the tower rather than at the listener"),Sound->BellAnchor().Position.Z>Scene->QualityCentre.Z+2500);
        Test->TestTrue(TEXT("Crowd anchors follow mapped businesses"),Sound->CrowdAnchors().Num()>20);
        if(!Sound->CrowdAnchors().IsEmpty())Test->TestTrue(TEXT("Crowd position has a traceable source"),Scene->SourceFeatureByID(Sound->CrowdAnchors()[0].SourceID).IsValid());
        Test->TestTrue(TEXT("Bird placement has scene anchors"),!Sound->PigeonAnchors().IsEmpty());
        FParisSoundAnchor A,B;Test->TestTrue(TEXT("Water follows actual river polygon edges"),Sound->NearestWater(Scene->QualityCentre,A));
        Test->TestTrue(TEXT("Water audio retains its OSM source"),Scene->SourceFeatureByID(A.SourceID).IsValid());
        Sound->NearestWater(Scene->QualityCentre+FVector(-16000,-16000,0),B);Test->TestTrue(TEXT("Water emitter moves along the bank as the listener moves"),FVector::Dist2D(A.Position,B.Position)>1000);
        TArray<UAudioComponent*> Components;Sound->GetComponents(Components);Test->TestEqual(TEXT("Voice allocation is bounded including preview"),Components.Num(),8);
        auto PC=Cast<AParisTwinController>(World->GetFirstPlayerController());auto OldView=PC->GetViewTarget();auto View=World->SpawnActor<ACameraActor>();
        Sound->SetMuted(false);Scene->RainWeather->bMuted=false;
        View->SetActorLocation(Sound->CrowdAnchors()[0].Position+FVector(0,0,150));PC->SetViewTarget(View);PC->PlayerCameraManager->UpdateCamera(0);
        const int32 Time=Scene->TimeOfDayPreset;Scene->TimeOfDayPreset=0;Sound->Tick(.2f);float DayGain=0,NightGain=0;
        for(auto C:Components)if(C->GetFName()==TEXT("ParisAmbient_Crowd"))DayGain=C->VolumeMultiplier;
        Scene->TimeOfDayPreset=2;Sound->Tick(.2f);for(auto C:Components)if(C->GetFName()==TEXT("ParisAmbient_Crowd"))NightGain=C->VolumeMultiplier;
        Test->TestTrue(TEXT("Night reduces crowd activity"),DayGain>NightGain&&NightGain>0);Scene->TimeOfDayPreset=Time;
        for(TActorIterator<AParisCruise> Ship(World);Ship;++Ship)if(Ship->bReady){
            const FVector Old=Ship->GetActorLocation();Ship->SetActorLocation(Old+FVector(600,350,0));Sound->Tick(.2f);
            for(auto C:Components)if(C->GetFName()==TEXT("ParisAmbient_Ferry"))Test->TestTrue(TEXT("Engine sound tracks the moving ferry"),FVector::Dist(C->GetComponentLocation(),Ship->GetActorLocation()+FVector(0,0,130))<.1);
            Ship->RefreshPose();break;
        }
        for(auto C:Components)if(C->GetFName()!=TEXT("ParisSoundPreview")){
            auto W=Cast<USoundWave>(C->Sound);Test->TestTrue(TEXT("Spatial sources use actual nonempty mono SoundWaves"),W&&W->NumChannels==1&&W->Duration>1);
            Test->TestTrue(TEXT("Spatial sources have attenuation and occlusion enabled"),C->bAllowSpatialization&&C->bOverrideAttenuation&&C->AttenuationOverrides.bEnableOcclusion);
        }
        for(int32 Kind=0;Kind<6;Kind++){
            Sound->Audition(Kind);bool Playing=false;for(auto C:Components)if(C->GetFName()==TEXT("ParisSoundPreview"))Playing=C->IsPlaying()&&C->Sound&&C->VolumeMultiplier>0;
            Test->TestTrue(TEXT("Each of the six sound previews reaches audio playback"),Playing&&Sound->PreviewKind==Kind);
        }
        PC->ToggleSound();Test->TestTrue(TEXT("F11 mutes rain and city sounds together"),Sound->bMuted&&Scene->RainWeather->bMuted);
        for(auto C:Components)Test->TestTrue(TEXT("Mute stops all ambient and preview voices"),!C->IsPlaying()&&C->VolumeMultiplier==0);
        Sound->Audition(0);for(auto C:Components)if(C->GetFName()==TEXT("ParisSoundPreview"))Test->TestFalse(TEXT("Preview respects mute"),C->IsPlaying());
        PC->ToggleSound();Test->TestFalse(TEXT("F11 restores the shared sound preference"),Sound->bMuted||Scene->RainWeather->bMuted);
        auto Report=MakeShared<FJsonObject>();Sound->Tick(.2f);Sound->AddStats(Report);Report->SetNumberField(TEXT("preview_categories_verified"),6);Report->SetNumberField(TEXT("day_crowd_gain"),DayGain);Report->SetNumberField(TEXT("night_crowd_gain"),NightGain);
        FString Text;FJsonSerializer::Serialize(Report,TJsonWriterFactory<>::Create(&Text));FFileHelper::SaveStringToFile(Text,*(FPaths::ProjectSavedDir()/TEXT("paris-soundscape-test.json")));
        PC->SetViewTarget(OldView);View->Destroy();Started=0;return true;
    }
    if(FPlatformTime::Seconds()-Started>120){Test->AddError(TEXT("Soundscape scene readiness timeout"));Started=0;return true;}return false;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisSoundscapeTest,"ParisDigitalTwin.Live.SpatialSoundscapeAndSharedMute",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisSoundscapeTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FParisSoundscapeWait(this));return true;}
#endif
