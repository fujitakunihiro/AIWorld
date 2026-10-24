#include "ParisDigitalTwin.h"
#include "ParisPedestrians.h"
#include "ParisHumanAnimation.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/CapsuleComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Animation/AnimSequence.h"
#include "Materials/Material.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialExpressionTextureSample.h"
#include "Camera/PlayerCameraManager.h"

#if WITH_DEV_AUTOMATION_TESTS
class FParisHumanCheck : public IAutomationLatentCommand {
    FAutomationTestBase* Test;
    double Started=FPlatformTime::Seconds(),At=0;
    int32 Phase=0,PreviousQuality=1;
    bool PreviousEnabled=true;
    TWeakObjectPtr<AParisPedestrianCrowd> Crowd;
    TWeakObjectPtr<AActor> Fixture;
    TWeakObjectPtr<USkeletalMeshComponent> Body;
    FVector FootBefore=FVector::ZeroVector;double HipBefore=0;
    FName FootBone,HipBone;
    void Cleanup(){if(Fixture.IsValid())Fixture->Destroy();if(Crowd.IsValid())Crowd->SetDisplay(PreviousEnabled,PreviousQuality);}
public:
    explicit FParisHumanCheck(FAutomationTestBase* InTest):Test(InTest){}
    virtual bool Update() override {
        if(FPlatformTime::Seconds()-Started>35){Test->AddError(TEXT("Human visual test timed out"));Cleanup();return true;}
        if(!Crowd.IsValid())for(const auto& Context:GEngine->GetWorldContexts())if(Context.World())for(TActorIterator<AParisTwinScene> It(Context.World());It;++It)if(It->bReady&&It->Crowd){Crowd=It->Crowd;PreviousQuality=It->DetailQuality;PreviousEnabled=Crowd->bEnabled;break;}
        if(!Crowd.IsValid())return false;
        if(Phase==0){
            const bool Expected=FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal"))&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinSimplePeople"));
            Test->TestEqual(TEXT("Optional MIT human assets load only in requested photoreal mode"),Crowd->HumanVisualVariants(),Expected?2:0);
            if(!Expected)return true;
            auto World=Crowd->GetWorld();auto PC=Cast<AParisTwinController>(World->GetFirstPlayerController());
            if(!PC||!PC->FreeCamera)return true;
            PC->ReturnToFree();PC->FreeCamera->Eye(Crowd->People()[0].Position);PC->FreeCamera->Tick(0);PC->PlayerCameraManager->UpdateCamera(0);
            Crowd->SetDisplay(true,2);Crowd->UpdateInstances(true);
            Test->TestTrue(TEXT("Near skeletal characters use the bounded pool"),Crowd->SkeletalRenderedCount>0&&Crowd->SkeletalRenderedCount<=16);
            Test->TestEqual(TEXT("Crowd counts account for both skeletal and instanced people"),Crowd->RenderedCount,Crowd->SkeletalRenderedCount+Crowd->NearRenderedCount+Crowd->FarRenderedCount);
            TArray<UCapsuleComponent*> Pickers;Crowd->GetComponents(Pickers);TSet<FString> IDs;
            for(auto Picker:Pickers)if(Picker->GetCollisionEnabled()!=ECollisionEnabled::NoCollision){auto ID=Crowd->PersonID(Picker,INDEX_NONE);Test->TestFalse(TEXT("Human capsule selects the actual live pedestrian"),ID.IsEmpty());IDs.Add(ID);}
            Test->TestEqual(TEXT("Picking capsules and skeletal people match"),IDs.Num(),Crowd->SkeletalRenderedCount);
            TArray<UInstancedStaticMeshComponent*> Instances;Crowd->GetComponents(Instances);
            for(auto ISM:Instances)for(int32 I=0;I<ISM->GetInstanceCount();I++)if(IDs.Contains(Crowd->PersonID(ISM,I)))Test->AddError(TEXT("A real human is also drawn as a proxy"));
            TArray<USkeletalMeshComponent*> Skins;Crowd->GetComponents(Skins);
            for(auto Skin:Skins)if(Skin->IsVisible()){
                auto Mesh=Skin->GetSkeletalMeshAsset();auto Anim=Cast<UParisHumanAnimation>(Skin->GetAnimInstance());if(!Mesh||!Anim)continue;
                Test->TestTrue(TEXT("Human reference height is real scale"),Mesh->GetBounds().BoxExtent.Z*2>150&&Mesh->GetBounds().BoxExtent.Z*2<200);
                Test->TestTrue(TEXT("Human has an articulated skeleton and three real clips"),Mesh->GetRefSkeleton().GetNum()>60&&Anim->Idle&&Anim->Walk&&Anim->Sit);
                Test->TestTrue(TEXT("Route-driven clips preserve the saved root lock"),Anim->Walk->bForceRootLock&&Anim->Idle->bForceRootLock&&Anim->Sit->bForceRootLock&&!Anim->Walk->bEnableRootMotion);
                Test->TestEqual(TEXT("Head, body and masked hair surfaces are present"),Mesh->GetMaterials().Num(),3);
                for(const auto& Slot:Mesh->GetMaterials()){
                    Test->TestNotNull(TEXT("Human material binding survives saving and LOD generation"),Slot.MaterialInterface.Get());
                    if(Slot.MaterialInterface){
                        Test->TestTrue(TEXT("Surface was compiled for skinning"),Slot.MaterialInterface->GetMaterial()->GetUsageByFlag(MATUSAGE_SkeletalMesh));
                        Test->TestTrue(TEXT("Verified human source surfaces are assigned"),Slot.MaterialInterface->GetPathName().StartsWith(TEXT("/Game/ParisPhotoreal/People/Materials/M_")));
#if WITH_EDITORONLY_DATA
                        // NullRHI has no GPU material resources. Inspect the
                        // saved expression references rather than a shader map.
                        int32 Samples=0;
                        for(auto Expression:Slot.MaterialInterface->GetMaterial()->GetExpressions())
                            if(auto Sample=Cast<UMaterialExpressionTextureSample>(Expression))if(Sample->Texture)Samples++;
                        Test->TestTrue(TEXT("Human surface contains saved texture inputs"),Samples>0);
#else
                        TArray<UTexture*> Textures;Slot.MaterialInterface->GetUsedTextures(Textures);
                        Test->TestTrue(TEXT("Human surface contains rendered texture inputs"),Textures.Num()>0);
#endif
                    }
                }
                Fixture=World->SpawnActor<AActor>();auto Part=NewObject<USkeletalMeshComponent>(Fixture.Get());Fixture->SetRootComponent(Part);Fixture->AddInstanceComponent(Part);
                Part->SetSkeletalMeshAsset(Mesh);Part->VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;Part->RegisterComponent();Part->SetAnimInstanceClass(UParisHumanAnimation::StaticClass());
                auto Driver=CastChecked<UParisHumanAnimation>(Part->GetAnimInstance());Driver->Idle=Anim->Idle;Driver->Walk=Anim->Walk;Driver->Sit=Anim->Sit;Driver->SpeedCm=120;Driver->PersonIndex=5;
                Body=Part;
                for(int32 B=0;B<Part->GetNumBones();B++){const auto Name=Part->GetBoneName(B);const auto Text=Name.ToString().ToLower();if(Text.Contains(TEXT("l-foot")))FootBone=Name;if(Text.Contains(TEXT("pelvis")))HipBone=Name;}
                break;
            }
            if(!Body.IsValid()||FootBone.IsNone()||HipBone.IsNone()){Test->AddError(TEXT("No complete imported human rig"));Cleanup();return true;}
            Crowd->SetDisplay(true,0);Test->TestEqual(TEXT("Low quality returns entirely to cheap instances"),Crowd->SkeletalRenderedCount,0);
            Crowd->SetDisplay(false,2);Test->TestEqual(TEXT("People toggle hides the skeletal pool"),Crowd->SkeletalRenderedCount,0);
            Crowd->SetDisplay(true,2);PC->Overview();At=FPlatformTime::Seconds();Phase=1;return false;
        }
        const double Now=FPlatformTime::Seconds();
        if(Phase==1&&Now-At>.2){FootBefore=Body->GetSocketTransform(FootBone,RTS_Component).GetLocation();HipBefore=Body->GetSocketTransform(HipBone,RTS_Component).GetLocation().Z;At=Now;Phase=2;return false;}
        if(Phase==2&&Now-At>.35){
            Test->TestTrue(TEXT("Skinning evaluates a changing foot pose rather than sliding a rigid body"),FVector::Dist(FootBefore,Body->GetSocketTransform(FootBone,RTS_Component).GetLocation())>2);
            auto Driver=CastChecked<UParisHumanAnimation>(Body->GetAnimInstance());Driver->SpeedCm=0;Driver->SeatAlpha=1;At=Now;Phase=3;return false;
        }
        if(Phase==3&&Now-At>.3){Test->TestTrue(TEXT("Seated clip lowers the hips to a chair pose"),Body->GetSocketTransform(HipBone,RTS_Component).GetLocation().Z<HipBefore-15);Cleanup();return true;}
        return false;
    }
};
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisHumanTest,"ParisDigitalTwin.Live.RealisticPedestrianVisuals",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisHumanTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FParisHumanCheck(this));return true;}
#endif
