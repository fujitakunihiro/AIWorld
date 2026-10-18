#include "ParisPhotoEnvironment.h"
#include "ParisDigitalTwin.h"
#include "ParisRuntimeMesh.h"
#include "WorldProtocol.h"
#include "Misc/AutomationTest.h"
#include "Engine/Engine.h"
#include "EngineUtils.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Engine/StaticMeshActor.h"
#include "ProceduralMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/SkyLight.h"
#include "Components/SkyLightComponent.h"

#if WITH_DEV_AUTOMATION_TESTS
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FParisPhotoWait,FAutomationTestBase*,Test);
bool FParisPhotoWait::Update(){
    static double Started=0;if(!Started)Started=FPlatformTime::Seconds();
    for(const auto& Context:GEngine->GetWorldContexts())if(Context.World())for(TActorIterator<AParisTwinScene> It(Context.World());It;++It){
        auto Scene=*It;if(!Scene->bReady)continue;auto World=Context.World();
        ConfigureParisPhotoEnvironment(World,Scene->GeoReference.OriginElevationNGF);
        ConfigureParisPhotoEnvironment(World,Scene->GeoReference.OriginElevationNGF);
        auto Stats=MakeShared<FJsonObject>();AddParisPhotoEnvironmentStats(World,Stats);
        for(auto Key:{TEXT("directional_lights"),TEXT("sky_lights"),TEXT("sky_atmospheres"),TEXT("height_fogs"),TEXT("post_process_volumes")})
            Test->TestEqual(TEXT("Reconfiguration never creates duplicate environment actors"),AIWorld::Number(Stats,Key),1.);
        Test->TestEqual(TEXT("Three photographic comparisons are available"),AIWorld::Number(Stats,TEXT("photo_cameras")),3.);
        Test->TestEqual(TEXT("Repeated configuration reuses the photographic sky"),AIWorld::Number(Stats,TEXT("photographic_sky_domes")),FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal"))?1.:0.);
        for(TActorIterator<AStaticMeshActor> SkyActor(World);SkyActor;++SkyActor)if(SkyActor->ActorHasTag(TEXT("ParisPhotographicSky"))){
            auto C=SkyActor->GetStaticMeshComponent();
            Test->TestFalse(TEXT("Async sky mesh load cannot restore the engine sphere's BlockAll collision"),C->bUseDefaultCollision);
            Test->TestFalse(TEXT("Sky actor cannot obstruct cafe, social or walking traces"),SkyActor->GetActorEnableCollision());
            Test->TestEqual(TEXT("Sky ignores geographic visibility queries"),C->GetCollisionResponseToChannel(ECC_Visibility),ECR_Ignore);
        }
        if(FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal")))for(TActorIterator<ASkyLight> Fill(World);Fill;++Fill){
            Test->TestEqual(TEXT("Panorama lighting cannot capture an occluding city wall at the origin"),Fill->GetLightComponent()->SourceType,SLS_SpecifiedCubemap);
            Test->TestNotNull(TEXT("The fill has an actual loaded HDR cubemap"),Fill->GetLightComponent()->Cubemap.Get());
        }
        Test->TestTrue(TEXT("Daylight uses explicit physical camera exposure"),Stats->GetBoolField(TEXT("physical_camera_exposure")));
        Test->TestEqual(TEXT("Environment starts at clear daytime"),Scene->EnvironmentLabel(),FString(TEXT("Day | Clear")));
        Scene->CycleTimeOfDay();Test->TestEqual(TEXT("Time control selects sunset"),Scene->EnvironmentLabel(),FString(TEXT("Sunset | Clear")));
        Scene->CycleTimeOfDay();Test->TestEqual(TEXT("Time control selects night"),Scene->EnvironmentLabel(),FString(TEXT("Night | Clear")));
        Scene->ToggleWeather();Scene->Tick(.09f);Test->TestEqual(TEXT("Rain can overlay the current time preset"),Scene->EnvironmentLabel(),FString(TEXT("Night | Rain")));
        bool RainGeometry=false;TArray<UProceduralMeshComponent*> MeshComponents;Scene->GetComponents<UProceduralMeshComponent>(MeshComponents);
        for(auto Mesh:MeshComponents)if(Mesh->GetFName()==FName(TEXT("ParisRainStreaks")))RainGeometry=Mesh->GetProcMeshSection(0)!=nullptr&&Mesh->GetProcMeshSection(0)->ProcIndexBuffer.Num()>0;
        Test->TestTrue(TEXT("Rain creates a lightweight visible streak mesh"),RainGeometry);
        Scene->ToggleWeather();Test->TestEqual(TEXT("Weather toggle restores clear conditions"),Scene->EnvironmentLabel(),FString(TEXT("Night | Clear")));
        Scene->CycleTimeOfDay();Test->TestEqual(TEXT("Time presets cycle back to daytime"),Scene->EnvironmentLabel(),FString(TEXT("Day | Clear")));
        auto PC=Cast<AParisTwinController>(World->GetFirstPlayerController());if(!Test->TestNotNull(TEXT("Photo camera controller"),PC)){Started=0;return true;}
        for(auto Name:{TEXT("Camera_NotreDame_Front"),TEXT("Camera_NotreDame_Riverside"),TEXT("Camera_Paris_Street")}){
            Test->TestTrue(TEXT("Named GIS-anchored camera activates"),ActivateParisPhotoCamera(Scene,FName(Name)));
            Test->TestEqual(TEXT("View target is the named photographic camera"),PC->GetViewTarget()->GetFName(),FName(Name));
            if(auto Camera=Cast<ACameraActor>(PC->GetViewTarget())){
                const bool Door=FString(Name)==TEXT("Camera_NotreDame_Front")&&FParse::Param(FCommandLine::Get(),TEXT("ParisTwinDoorDetail"));
                const bool StatueOrPortal=FString(Name)==TEXT("Camera_NotreDame_Front")&&(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinVirginDetail"))||FParse::Param(FCommandLine::Get(),TEXT("ParisTwinPortalDetail")));
                const double Lens=StatueOrPortal?50.:Door?42.:FString(Name)==TEXT("Camera_Paris_Street")?35.:28.;
                Test->TestTrue(TEXT("Natural photographic angle from lens metadata"),FMath::IsNearlyEqual(double(Camera->GetCameraComponent()->FieldOfView),FMath::RadiansToDegrees(2.*FMath::Atan(36./(2.*Lens))),.01));
                if(Door)Test->TestTrue(TEXT("Door inspection uses the geographic door camera"),Camera->ActorHasTag(TEXT("ParisCathedralDoorCamera")));
            }
            PC->ReturnToFree();Test->TestEqual(TEXT("Free navigation restores the possessed camera"),PC->GetViewTarget(),static_cast<AActor*>(PC->GetPawn()));
        }
        Test->TestFalse(TEXT("Unknown camera is rejected"),ActivateParisPhotoCamera(Scene,TEXT("MissingCamera")));
        for(TActorIterator<ACameraActor> Camera(World);Camera;++Camera)if(Camera->GetFName()==FName(TEXT("Camera_NotreDame_Riverside")))Test->TestTrue(TEXT("River camera uses the actual bridge deck, not the river DEM"),Camera->ActorHasTag(TEXT("ParisPhotoBridgeDeck")));
        Started=0;return true;
    }
    if(FPlatformTime::Seconds()-Started>45){Test->AddError(TEXT("Photo scene did not become ready"));Started=0;return true;}return false;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisPhotoEnvironmentTest,"ParisDigitalTwin.Live.PhotoEnvironmentAndCameraSwitching",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisPhotoEnvironmentTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FParisPhotoWait(this));return true;}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisBridgeCameraHeightTest,"ParisDigitalTwin.Live.PhotoBridgeDeckHeight",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisBridgeCameraHeightTest::RunTest(const FString&){
    FParisMeshArrays Mesh;Mesh.Positions={FVector(0,0,500),FVector(1000,0,600),FVector(0,1000,500),FVector(0,0,300),FVector(1000,0,400),FVector(0,1000,300)};Mesh.Indices={0,1,2,3,4,5};Mesh.Normals={FVector::UpVector,FVector::UpVector,FVector::UpVector,-FVector::UpVector,-FVector::UpVector,-FVector::UpVector};
    double Z=0;TestTrue(TEXT("Find a point on the sloped rendered bridge"),ParisBridgeDeckHeight(Mesh,FVector2D(250,250),Z));TestEqual(TEXT("Interpolate the upper road deck, excluding its underside"),Z,525.);TestFalse(TEXT("Reject a position outside the bridge"),ParisBridgeDeckHeight(Mesh,FVector2D(1200,1200),Z));return true;
}
#endif
