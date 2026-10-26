#include "ParisPhotoEnvironment.h"
#include "ParisDigitalTwin.h"
#include "ParisRuntimeMesh.h"
#include "WorldProtocol.h"
#include "EngineUtils.h"
#include "Engine/DirectionalLight.h"
#include "Engine/SkyLight.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/PostProcessVolume.h"
#include "Engine/TextureCube.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/StaticMesh.h"
#include "Components/StaticMeshComponent.h"
#include "Materials/MaterialInterface.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/SkyAtmosphereComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "DynamicRHI.h"
#include "HAL/IConsoleManager.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
using namespace AIWorld;

template<class T> static T* ReuseOrSpawn(UWorld* World){
    for(TActorIterator<T> It(World);It;++It)return *It;
    return World->SpawnActor<T>();
}
static int32 CVar(const TCHAR* Name){auto V=IConsoleManager::Get().FindConsoleVariable(Name);return V?V->GetInt():-1;}

void ConfigureParisPhotoEnvironment(UWorld* World,double OriginNGF){
    const bool Legacy=FParse::Param(FCommandLine::Get(),TEXT("ParisTwinLegacyLighting"));
    auto Sun=ReuseOrSpawn<ADirectionalLight>(World);Sun->Tags.AddUnique(TEXT("ParisPhotoEnvironment"));
    auto Light=CastChecked<UDirectionalLightComponent>(Sun->GetLightComponent());
    Light->SetMobility(EComponentMobility::Movable);Sun->SetActorRotation(FRotator(-43,-35,0));
    Light->SetAtmosphereSunLight(true);Light->SetUseTemperature(true);Light->SetTemperature(5600);
    Light->SetIntensity(Legacy?10.3f:50000.f);Light->SetLightSourceAngle(.8f);
    Light->DynamicShadowDistanceMovableLight=50000;Light->DynamicShadowCascades=4;
    auto Atmosphere=ReuseOrSpawn<ASkyAtmosphere>(World);Atmosphere->Tags.AddUnique(TEXT("ParisPhotoEnvironment"));
    Atmosphere->GetComponent()->TransformMode=ESkyAtmosphereTransformMode::PlanetTopAtComponentTransform;
    Atmosphere->SetActorLocation(FVector(0,0,-OriginNGF*100));Atmosphere->GetComponent()->MarkRenderStateDirty();
    // A cloud panorama is a visual/lighting layer. Reuse our own tagged actor;
    // it has no collision and never intercepts geographic selection or walking.
    if(!Legacy&&FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal"))){
        auto Material=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisPhotographicSky"));
        auto Sphere=LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Sphere.Sphere"));
        if(Material&&Sphere){
            AStaticMeshActor* Dome=nullptr;
            for(TActorIterator<AStaticMeshActor> It(World);It;++It)if(It->ActorHasTag(TEXT("ParisPhotographicSky"))){Dome=*It;break;}
            if(!Dome)Dome=World->SpawnActor<AStaticMeshActor>();
            Dome->Tags.AddUnique(TEXT("ParisPhotographicSky"));
            auto C=Dome->GetStaticMeshComponent();C->SetMobility(EComponentMobility::Movable);
            // AStaticMeshActor inherits bUseDefaultCollision=true. Disabling
            // only BodyInstance collision can be undone when the engine sphere
            // finishes loading and restores its external BlockAll profile.
            C->SetCollisionProfileName(TEXT("NoCollision"));C->SetCollisionResponseToAllChannels(ECR_Ignore);C->SetGenerateOverlapEvents(false);
            Dome->SetActorEnableCollision(false);C->SetStaticMesh(Sphere);C->SetMaterial(0,Material);Dome->SetActorScale3D(FVector(20000));
            C->SetCollisionEnabled(ECollisionEnabled::NoCollision);C->SetCanEverAffectNavigation(false);C->SetCastShadow(false);C->bAffectDistanceFieldLighting=false;
        }
    }
    auto Sky=ReuseOrSpawn<ASkyLight>(World);Sky->Tags.AddUnique(TEXT("ParisPhotoEnvironment"));
    auto SkyComponent=Sky->GetLightComponent();SkyComponent->SetMobility(EComponentMobility::Movable);
    auto Cube=(Legacy||FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal")))?LoadObject<UTextureCube>(nullptr,TEXT("/Game/Textures/T_ParisDayEnvironment")):nullptr;
    if(Cube){
        SkyComponent->SourceType=SLS_SpecifiedCubemap;SkyComponent->SetCubemap(Cube);
        // The source HDR is an appearance environment, not a calibrated Paris
        // illuminance measurement. Sun/camera use explicit photographic units.
        // Match the sky dome's 6000 radiance scale and the previous 2x fill.
        // A specified panorama avoids a one-off scene capture from inside
        // nearby city geometry, which otherwise produces black shaded walls.
        SkyComponent->SetIntensity(Legacy?.55f:12000.f);SkyComponent->SetRealTimeCaptureEnabled(false);
    }else{SkyComponent->SourceType=SLS_CapturedScene;SkyComponent->SetIntensity(2.f);SkyComponent->SetRealTimeCaptureEnabled(true);SkyComponent->RecaptureSky();}
    SkyComponent->SetLowerHemisphereColor(FLinearColor(.07f,.065f,.055f));SkyComponent->MarkRenderStateDirty();
    auto Fog=ReuseOrSpawn<AExponentialHeightFog>(World);Fog->Tags.AddUnique(TEXT("ParisPhotoEnvironment"));
    auto F=Fog->GetComponent();F->SetFogDensity(.0007f);F->SetFogHeightFalloff(.2f);
    F->SetFogMaxOpacity(.14f);F->SetStartDistance(3000);F->SetFogInscatteringColor(FLinearColor(.50f,.62f,.74f));
    F->SetVolumetricFog(false);
    auto Post=ReuseOrSpawn<APostProcessVolume>(World);Post->Tags.AddUnique(TEXT("ParisPhotoEnvironment"));Post->bUnbound=true;
    auto& P=Post->Settings;P.bOverride_AutoExposureMethod=true;P.AutoExposureMethod=EAutoExposureMethod::AEM_Manual;
    P.bOverride_AutoExposureBias=true;P.AutoExposureBias=Legacy?9.6f:.5f;
    P.bOverride_AutoExposureApplyPhysicalCameraExposure=true;P.AutoExposureApplyPhysicalCameraExposure=!Legacy;
    P.bOverride_CameraISO=true;P.CameraISO=100;P.bOverride_CameraShutterSpeed=true;P.CameraShutterSpeed=125;
    P.bOverride_DepthOfFieldFstop=true;P.DepthOfFieldFstop=8;
    P.bOverride_AmbientOcclusionIntensity=true;P.AmbientOcclusionIntensity=.45f;
    P.bOverride_AmbientOcclusionRadius=true;P.AmbientOcclusionRadius=70;
    // Force a defined default for comparison; Unlit remains an explicit debug
    // command. Its missing atmospheric sky must never be mistaken for Lit.
    if(auto PC=World->GetFirstPlayerController())PC->ConsoleCommand(TEXT("viewmode lit"),false);
}

void AddParisPhotoEnvironmentStats(UWorld* World,const TSharedPtr<FJsonObject>& Report){
    Report->SetStringField(TEXT("rhi"),GDynamicRHI?GDynamicRHI->GetName():TEXT("NullRHI"));
    Report->SetStringField(TEXT("shader_feature_level"),GMaxRHIFeatureLevel==ERHIFeatureLevel::SM6?TEXT("SM6"):TEXT("SM5"));
    for(const auto& Item:TMap<FString,FString>{{TEXT("gi_method"),TEXT("r.DynamicGlobalIlluminationMethod")},{TEXT("reflection_method"),TEXT("r.ReflectionMethod")},{TEXT("virtual_shadow_maps"),TEXT("r.Shadow.Virtual.Enable")},{TEXT("mesh_distance_fields"),TEXT("r.GenerateMeshDistanceFields")}})Report->SetNumberField(Item.Key,CVar(*Item.Value));
    int32 Sun=0,Sky=0,Atmosphere=0,Fog=0,Post=0,Cameras=0,Panoramas=0;
    for(TActorIterator<AStaticMeshActor> It(World);It;++It)if(It->ActorHasTag(TEXT("ParisPhotographicSky")))Panoramas++;
    for(TActorIterator<ADirectionalLight> It(World);It;++It){Sun++;Report->SetNumberField(TEXT("sun_intensity"),It->GetLightComponent()->Intensity);}
    for(TActorIterator<ASkyLight> It(World);It;++It)Sky++;
    for(TActorIterator<ASkyAtmosphere> It(World);It;++It)Atmosphere++;
    for(TActorIterator<AExponentialHeightFog> It(World);It;++It)Fog++;
    for(TActorIterator<APostProcessVolume> It(World);It;++It){Post++;Report->SetNumberField(TEXT("exposure_compensation"),It->Settings.AutoExposureBias);Report->SetBoolField(TEXT("physical_camera_exposure"),It->Settings.AutoExposureApplyPhysicalCameraExposure);}
    for(TActorIterator<ACameraActor> It(World);It;++It)if(It->ActorHasTag(TEXT("ParisFixedPhotoCamera")))Cameras++;
    Report->SetNumberField(TEXT("directional_lights"),Sun);Report->SetNumberField(TEXT("sky_lights"),Sky);
    Report->SetNumberField(TEXT("sky_atmospheres"),Atmosphere);Report->SetNumberField(TEXT("height_fogs"),Fog);
    Report->SetNumberField(TEXT("post_process_volumes"),Post);Report->SetNumberField(TEXT("photo_cameras"),Cameras);
    Report->SetNumberField(TEXT("photographic_sky_domes"),Panoramas);
    bool DoorDetail=false;for(TActorIterator<ACameraActor> It(World);It;++It)DoorDetail|=It->ActorHasTag(TEXT("ParisCathedralDoorCamera"));
    Report->SetBoolField(TEXT("door_detail_view"),DoorDetail);
    bool VirginDetail=false;for(TActorIterator<ACameraActor> It(World);It;++It)VirginDetail|=It->ActorHasTag(TEXT("ParisCathedralVirginCamera"));
    Report->SetBoolField(TEXT("virgin_detail_view"),VirginDetail);
    if(auto PC=World->GetFirstPlayerController())Report->SetStringField(TEXT("active_photo_camera"),PC->GetViewTarget()?PC->GetViewTarget()->GetName():TEXT(""));
}

bool ParisBridgeDeckHeight(const FParisMeshArrays& Mesh,const FVector2D& XY,double& Height){
    bool Found=false;Height=-DBL_MAX;
    for(int32 I=0;I+2<Mesh.Indices.Num();I+=3){
        const int32 IA=Mesh.Indices[I],IB=Mesh.Indices[I+1],IC=Mesh.Indices[I+2];
        if(!Mesh.Positions.IsValidIndex(IA)||!Mesh.Positions.IsValidIndex(IB)||!Mesh.Positions.IsValidIndex(IC)||!Mesh.Normals.IsValidIndex(IC))continue;
        if((Mesh.Normals[IA].Z+Mesh.Normals[IB].Z+Mesh.Normals[IC].Z)/3.<.4)continue;
        const FVector A=Mesh.Positions[IA],B=Mesh.Positions[IB],C=Mesh.Positions[IC];
        const double X=B.X-A.X,Y=B.Y-A.Y,U=C.X-A.X,V=C.Y-A.Y,Den=X*V-Y*U;
        if(FMath::Abs(Den)<1.e-6)continue;
        const double PX=XY.X-A.X,PY=XY.Y-A.Y,S=(PX*V-PY*U)/Den,T=(X*PY-Y*PX)/Den;
        if(S<-.00001||T<-.00001||S+T>1.00001)continue;
        Height=FMath::Max(Height,A.Z+S*(B.Z-A.Z)+T*(C.Z-A.Z));Found=true;
    }return Found;
}

void CreateParisPhotoCameras(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Data,const TArray<uint8>& GeometryBlob){
    for(const auto& V:Array(Data,TEXT("photo_cameras"))){auto J=V->AsObject();const auto& P=Array(J,TEXT("position_cm"));const auto& Target=Array(J,TEXT("target_cm"));if(P.Num()!=3||Target.Num()!=3)continue;
        const FName Name(*String(J,TEXT("name")));ACameraActor* Camera=nullptr;
        for(TActorIterator<ACameraActor> It(Scene->GetWorld());It;++It)if(It->GetFName()==Name){Camera=*It;break;}
        if(!Camera){FActorSpawnParameters Params;Params.Name=Name;Camera=Scene->GetWorld()->SpawnActor<ACameraActor>(ACameraActor::StaticClass(),FTransform::Identity,Params);}
        Camera->Tags.AddUnique(TEXT("ParisFixedPhotoCamera"));
#if WITH_EDITOR
        Camera->SetActorLabel(Name.ToString());
#endif
        FVector Position(P[0]->AsNumber(),P[1]->AsNumber(),P[2]->AsNumber());FVector Aim(Target[0]->AsNumber(),Target[1]->AsNumber(),Target[2]->AsNumber());
        double RoadLens=0;
        if(Name==TEXT("Camera_Paris_Street")&&FParse::Param(FCommandLine::Get(),TEXT("ParisTwinRoadView"))){
            FString RoadText;TSharedPtr<FJsonObject> Road;
            if(FFileHelper::LoadFileToString(RoadText,*(FPaths::ProjectContentDir()/TEXT("Data/paris-road-detail.json")))&&FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(RoadText),Road)&&Road.IsValid()&&String(Road,TEXT("source_scene_sha256"))==String(Data,TEXT("source_scene_sha256"))){
                auto Preview=Object(Road,TEXT("preview_camera"));const auto& RP=Array(Preview,TEXT("position_cm"));const auto& RT=Array(Preview,TEXT("target_cm"));
                if(RP.Num()==3&&RT.Num()==3){Position=FVector(RP[0]->AsNumber(),RP[1]->AsNumber(),RP[2]->AsNumber());Aim=FVector(RT[0]->AsNumber(),RT[1]->AsNumber(),RT[2]->AsNumber());RoadLens=Number(Preview,TEXT("focal_length_mm"),30);Camera->Tags.AddUnique(TEXT("ParisRoadCamera"));}
            }
        }
        bool RiverPreview=false;
        if(Name==TEXT("Camera_NotreDame_Riverside")&&FParse::Param(FCommandLine::Get(),TEXT("ParisTwinRiverView"))){
            FString RiverText;TSharedPtr<FJsonObject> River;
            if(FFileHelper::LoadFileToString(RiverText,*(FPaths::ProjectContentDir()/TEXT("Data/paris-water.json")))&&FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(RiverText),River)&&River.IsValid()&&String(River,TEXT("source_scene_sha256"))==String(Data,TEXT("source_scene_sha256"))){
                auto Preview=Object(River,TEXT("preview_camera"));const auto& RP=Array(Preview,TEXT("position_cm"));const auto& RT=Array(Preview,TEXT("target_cm"));
                if(RP.Num()==3&&RT.Num()==3){Position=FVector(RP[0]->AsNumber(),RP[1]->AsNumber(),RP[2]->AsNumber());Aim=FVector(RT[0]->AsNumber(),RT[1]->AsNumber(),RT[2]->AsNumber());RiverPreview=true;}
            }
        }
        double DetailLens=RoadLens;
        const bool DoorDetail=FParse::Param(FCommandLine::Get(),TEXT("ParisTwinDoorDetail"));
        const bool VirginDetail=FParse::Param(FCommandLine::Get(),TEXT("ParisTwinVirginDetail"));
        if(Name==TEXT("Camera_NotreDame_Front")&&(VirginDetail||DoorDetail||FParse::Param(FCommandLine::Get(),TEXT("ParisTwinPortalDetail")))){
            FString Text;TSharedPtr<FJsonObject> Architecture;
            if(FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("Data/paris-photo-architecture.json")))&&FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Architecture)&&Architecture&&String(Architecture,TEXT("source_id"))==TEXT("osm/way/201611261")){
                const auto Detail=Object(Architecture,VirginDetail?TEXT("virgin_camera"):(DoorDetail?TEXT("door_camera"):TEXT("detail_camera")));const auto& DP=Array(Detail,TEXT("position_cm"));const auto& DT=Array(Detail,TEXT("target_cm"));
                if(DP.Num()==3&&DT.Num()==3){
                    const FVector Location(DP[0]->AsNumber(),DP[1]->AsNumber(),DP[2]->AsNumber()),TargetPoint(DT[0]->AsNumber(),DT[1]->AsNumber(),DT[2]->AsNumber());
                    if(!Location.ContainsNaN()&&!TargetPoint.ContainsNaN()&&(TargetPoint-Location).Size()>100){Position=Location;Aim=TargetPoint;DetailLens=Number(Detail,TEXT("focal_length_mm"),35);Camera->Tags.AddUnique(VirginDetail?TEXT("ParisCathedralVirginCamera"):(DoorDetail?TEXT("ParisCathedralDoorCamera"):TEXT("ParisCathedralPortalCamera")));}
                }
            }
        }
        // Road decks / triangulated terrain can differ from the DEM sample
        // at an embankment. Stand 170cm above the actual walkable surface,
        // retaining the geographic XY anchor and all original source data.
        bool OnBridge=false;const FString BridgeID=String(J,TEXT("position_source_id"));
        if(!BridgeID.IsEmpty())for(const auto& Value:Array(Data,TEXT("objects"))){auto ObjectData=Value->AsObject();if(String(ObjectData,TEXT("kind"))!=TEXT("bridge"))continue;
            bool Matches=false;for(const auto& ID:Array(Object(ObjectData,TEXT("properties")),TEXT("source_ids")))Matches|=ID->AsString()==BridgeID;if(!Matches)continue;
            FParisMeshArrays Mesh;FString Error;double Z;
            if(ReadParisMeshArrays(ObjectData,GeometryBlob,Mesh,Error)&&ParisBridgeDeckHeight(Mesh,FVector2D(Position.X,Position.Y),Z)){
                Position.Z=Z+170;OnBridge=true;Camera->Tags.AddUnique(TEXT("ParisPhotoBridgeDeck"));break;
            }
        }
        FHitResult Ground;FCollisionQueryParams Query;Query.bTraceComplex=true;
        if(!RiverPreview&&!OnBridge&&Scene->GetWorld()->LineTraceSingleByChannel(Ground,Position+FVector(0,0,20000),Position-FVector(0,0,20000),ECC_Pawn,Query)&&Ground.ImpactNormal.Z>.4)
            Position.Z=Ground.ImpactPoint.Z+170;
        Camera->SetActorLocationAndRotation(Position,(Aim-Position).Rotation());auto C=Camera->GetCameraComponent();
        const double Lens=FMath::Clamp(DetailLens>0?DetailLens:Number(J,TEXT("focal_length_mm"),35),24.,85.);
        C->SetFieldOfView(FMath::RadiansToDegrees(2.*FMath::Atan(36./(2.*Lens))));C->PostProcessBlendWeight=1;
        C->PostProcessSettings.bOverride_DepthOfFieldFstop=true;C->PostProcessSettings.DepthOfFieldFstop=8;
        C->PostProcessSettings.bOverride_DepthOfFieldFocalDistance=true;C->PostProcessSettings.DepthOfFieldFocalDistance=(Aim-Position).Size();
    }
}

bool ActivateParisPhotoCamera(AParisTwinScene* Scene,FName Name){
    if(!Scene)return false;auto PC=Cast<AParisTwinController>(Scene->GetWorld()->GetFirstPlayerController());if(!PC)return false;
    for(TActorIterator<ACameraActor> It(Scene->GetWorld());It;++It)if(It->GetFName()==Name&&It->ActorHasTag(TEXT("ParisFixedPhotoCamera"))){
        PC->ReturnToFree();auto Free=Cast<AParisTwinCamera>(PC->GetPawn());if(!Free)return false;
        Free->Eye(It->GetActorLocation()-FVector(0,0,170));Free->Yaw=It->GetActorRotation().Yaw;Free->Pitch=It->GetActorRotation().Pitch;
        Free->Camera->SetFieldOfView(It->GetCameraComponent()->FieldOfView);Free->Camera->PostProcessSettings=It->GetCameraComponent()->PostProcessSettings;
        Free->Camera->PostProcessBlendWeight=1;PC->SetViewTarget(*It);PC->ConsoleCommand(TEXT("viewmode lit"),false);Scene->ClearInspection();return true;
    }return false;
}
