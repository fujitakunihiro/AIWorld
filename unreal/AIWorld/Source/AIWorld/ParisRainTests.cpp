#include "ParisRainWeather.h"
#include "ParisDigitalTwin.h"
#include "Misc/AutomationTest.h"
#include "Engine/Engine.h"
#include "EngineUtils.h"
#include "Engine/World.h"
#include "Camera/CameraActor.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/BoxComponent.h"
#include "Components/AudioComponent.h"
#include "ProceduralMeshComponent.h"
#include "Sound/SoundWave.h"
#include "Materials/MaterialParameterCollection.h"
#include "Materials/MaterialParameterCollectionInstance.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"

#if WITH_DEV_AUTOMATION_TESTS
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FParisRainWait,FAutomationTestBase*,Test);
bool FParisRainWait::Update(){
    static double Started=0;if(!Started)Started=FPlatformTime::Seconds();
    for(const auto& Context:GEngine->GetWorldContexts())if(auto World=Context.World())for(TActorIterator<AParisTwinScene> It(World);It;++It){
        auto Scene=*It;if(!Scene->bReady)continue;
        auto Weather=Scene->RainWeather;auto PC=World->GetFirstPlayerController();auto OldView=PC->GetViewTarget();
        // A controlled fixture above the city avoids accidentally moving the
        // listener into an existing mapped building during the shelter test.
        auto View=World->SpawnActor<ACameraActor>();const FVector Eye=Scene->QualityCentre+FVector(0,0,20000);
        View->SetActorLocation(Eye);PC->SetViewTarget(View);PC->PlayerCameraManager->UpdateCamera(0.f);
        Weather->bMuted=false;
        for(int32 I=0;I<620;I++)Weather->Advance(.1f,true,0);
        Test->TestTrue(TEXT("Rain survives more than one minute and reaches full intensity"),Weather->Intensity>.99f&&Weather->VisibleDrops>0);
        Test->TestTrue(TEXT("Rain accumulates wetness"),Weather->Wetness>.99f);
        Test->TestTrue(TEXT("The test starts under an unobstructed sky"),Weather->Exposure>.95f);
        auto Collection=LoadObject<UMaterialParameterCollection>(nullptr,TEXT("/Game/Weather/MPC_ParisWeather"));
        Test->TestNotNull(TEXT("The shared wet-surface collection is a real asset"),Collection);
        if(Collection){float Value=0;World->GetParameterCollectionInstance(Collection)->GetScalarParameterValue(TEXT("Wetness"),Value);Test->TestTrue(TEXT("Actual materials receive wetness"),Value>.99f);}
        TArray<UProceduralMeshComponent*> Meshes;Scene->GetComponents(Meshes);int32 Vertices=0;
        for(auto M:Meshes)if(M->GetFName()==TEXT("ParisRainStreaks")){
            auto Section=M->GetProcMeshSection(0);Test->TestNotNull(TEXT("Actual rain geometry exists"),Section);
            if(Section){Vertices=Section->ProcVertexBuffer.Num();for(const auto& V:Section->ProcVertexBuffer){
                const FVector P=M->GetComponentTransform().TransformPosition(FVector(V.Position));
                if(!FMath::IsFinite(P.Z)||FMath::Abs(P.X-Eye.X)>3100||FMath::Abs(P.Y-Eye.Y)>3100||FMath::Abs(P.Z-Eye.Z)>2200){Test->AddError(TEXT("Rain escaped its world volume after long running"));break;}
            }}
            Test->TestEqual(TEXT("Cosmetic rain has no collision"),M->GetCollisionEnabled(),ECollisionEnabled::NoCollision);
        }
        Test->TestEqual(TEXT("Low rain uses the bounded mesh budget"),Vertices,650*4);
        TArray<UAudioComponent*> Sounds;Scene->GetComponents(Sounds);int32 Loops=0;
        for(auto C:Sounds)if(C->GetFName()==TEXT("ParisRainAudio")||C->GetFName()==TEXT("ParisRunoffAudio")){
            auto Wave=Cast<USoundWave>(C->Sound);Test->TestNotNull(TEXT("Real imported rain audio is bound"),Wave);
            if(Wave){Test->TestTrue(TEXT("Rain audio is stereo and loops"),Wave->bLooping&&Wave->NumChannels==2);Loops++;}
            Test->TestTrue(TEXT("The audio engine starts both nonzero rain layers"),C->IsPlaying()&&C->VolumeMultiplier>0);
        }
        Test->TestEqual(TEXT("Both rain bed and runoff layers are present"),Loops,2);
        auto Roof=World->SpawnActor<AActor>();auto Box=NewObject<UBoxComponent>(Roof);Roof->SetRootComponent(Box);Roof->AddInstanceComponent(Box);
        Box->SetBoxExtent(FVector(350,350,30));Box->SetCollisionEnabled(ECollisionEnabled::QueryOnly);Box->SetCollisionResponseToAllChannels(ECR_Ignore);Box->SetCollisionResponseToChannel(ECC_Visibility,ECR_Block);Box->RegisterComponent();Roof->SetActorLocation(Eye+FVector(0,0,350));
        for(int32 I=0;I<30;I++)Weather->Advance(.1f,true,0);
        const float Covered=Weather->Exposure;Test->TestTrue(TEXT("An actual overhead collider muffles rain"),Covered<.05f);
        Roof->Destroy();View->SetActorLocation(Eye+FVector(1200,0,0));PC->PlayerCameraManager->UpdateCamera(0.f);
        for(int32 I=0;I<30;I++)Weather->Advance(.1f,true,0);
        Test->TestTrue(TEXT("Leaving shelter restores outdoor rain sound"),Weather->Exposure>.95f);
        Weather->ToggleSound();Weather->Advance(.1f,true,1);
        for(auto C:Sounds)if(C->GetFName()==TEXT("ParisRainAudio")||C->GetFName()==TEXT("ParisRunoffAudio"))Test->TestTrue(TEXT("Mute silences both layers"),C->VolumeMultiplier==0);
        Weather->ToggleSound();Weather->Advance(.1f,true,1);
        for(int32 I=0;I<610;I++)Weather->Advance(.1f,false,0);
        Test->TestTrue(TEXT("Clear weather fades rain and dries surfaces"),Weather->Intensity<.001f&&Weather->Wetness==0);
        for(auto C:Sounds)if(C->GetFName()==TEXT("ParisRainAudio")||C->GetFName()==TEXT("ParisRunoffAudio"))Test->TestFalse(TEXT("Clear weather releases rain audio playback"),C->IsPlaying());
        auto Report=MakeShared<FJsonObject>();Report->SetNumberField(TEXT("simulated_rain_seconds"),68);Report->SetNumberField(TEXT("low_vertices"),Vertices);Report->SetNumberField(TEXT("looping_stereo_layers"),Loops);Report->SetNumberField(TEXT("sheltered_exposure"),Covered);Report->SetBoolField(TEXT("dry_cleanup"),Weather->Wetness==0);
        FString Text;FJsonSerializer::Serialize(Report,TJsonWriterFactory<>::Create(&Text));FFileHelper::SaveStringToFile(Text,*(FPaths::ProjectSavedDir()/TEXT("paris-rain-test.json")));
        PC->SetViewTarget(OldView);View->Destroy();Started=0;return true;
    }
    if(FPlatformTime::Seconds()-Started>120){Test->AddError(TEXT("Paris rain scene readiness timed out"));Started=0;return true;}return false;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisRainTest,"ParisDigitalTwin.Live.RainLifecycleAndShelter",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisRainTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FParisRainWait(this));return true;}
#endif
