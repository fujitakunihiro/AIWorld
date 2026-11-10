#include "ParisChapelle.h"
#include "ParisDigitalTwin.h"
#include "ProceduralMeshComponent.h"
#include "Camera/CameraComponent.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Engine/Engine.h"
#include "EngineUtils.h"
#if WITH_DEV_AUTOMATION_TESTS
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FParisChapelleWait,FAutomationTestBase*,Test);
bool FParisChapelleWait::Update(){
    static double Started=0;if(!Started)Started=FPlatformTime::Seconds();
    for(const auto& Context:GEngine->GetWorldContexts())if(auto World=Context.World())for(TActorIterator<AParisTwinScene> It(World);It;++It){auto Scene=*It;if(!Scene->bReady)continue;
        AParisChapelleDetail* Detail=nullptr;for(TActorIterator<AParisChapelleDetail> D(World);D;++D){Detail=*D;break;}
        if(!Detail||!Detail->bReady){Test->AddError(TEXT("Chapel detail or source material missing"));Started=0;return true;}
        Test->TestEqual(TEXT("Fifteen inferred nave and apse bays"),Detail->WindowCount,15);Test->TestEqual(TEXT("Eighteen exterior buttresses"),Detail->ButtressCount,18);Test->TestEqual(TEXT("Official spire height in centimeters"),Detail->SpireHeightCm,7500.);
        Test->TestTrue(TEXT("Source footprint retained"),Scene->SourceFeatureByID(TEXT("osm/relation/3344870")).IsValid());
        TArray<UProceduralMeshComponent*> Parts;Detail->GetComponents(Parts);Test->TestEqual(TEXT("Exterior and interior stone, glass, slate, vault and light-shaft parts present"),Parts.Num(),7);Test->TestTrue(TEXT("Upper-chapel interior was built from baked materials"),Detail->bInteriorBuilt);
        for(auto P:Parts){Test->TestTrue(TEXT("Detail does not replace GIS collision"),P->GetCollisionEnabled()==ECollisionEnabled::NoCollision);Test->TestNotNull(TEXT("Detail material exists"),P->GetMaterial(0));}
        const int32 Old=Scene->DetailQuality;Scene->DetailQuality=0;Detail->Sync();Test->TestTrue(TEXT("Low mode restores original geometry"),Detail->IsHidden());Scene->DetailQuality=Old;Detail->Sync();
        if(auto PC=Cast<AParisTwinController>(World->GetFirstPlayerController())){PC->Overview();Detail->ActivateView(PC);Test->TestTrue(TEXT("Chapel view activates"),PC->GetViewTarget()==Detail);Test->TestTrue(TEXT("Cycling reaches the interior"),Detail->CycleView(PC)&&Detail->ViewIndex==1);Detail->ActivateView(PC,3);Test->TestEqual(TEXT("Interior window view selected"),Detail->ViewIndex,3);Test->TestFalse(TEXT("Cycling ends at the last interior view"),Detail->CycleView(PC));PC->Overview();}
        Started=0;return true;
    }
    if(FPlatformTime::Seconds()-Started>40){Test->AddError(TEXT("Scene not ready"));Started=0;return true;}return false;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisChapelleLiveTest,"ParisDigitalTwin.Live.SainteChapelleDetail",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisChapelleLiveTest::RunTest(const FString&){if(!FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal")))return true;ADD_LATENT_AUTOMATION_COMMAND(FParisChapelleWait(this));return true;}
#endif
