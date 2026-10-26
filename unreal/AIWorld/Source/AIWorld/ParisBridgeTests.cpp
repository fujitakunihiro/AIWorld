#include "ParisBridgeDetail.h"
#include "ParisDigitalTwin.h"
#include "WorldProtocol.h"
#include "Engine/Engine.h"
#include "EngineUtils.h"
#include "Components/StaticMeshComponent.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
using namespace AIWorld;

#if WITH_DEV_AUTOMATION_TESTS
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FParisBridgeWalkWait,FAutomationTestBase*,Test);
bool FParisBridgeWalkWait::Update(){
    static double Started=0;if(!Started)Started=FPlatformTime::Seconds();
    for(const auto& Context:GEngine->GetWorldContexts())if(Context.World())for(TActorIterator<AParisTwinScene> It(Context.World());It;++It){auto Scene=*It;if(!Scene->bReady)continue;
        const bool Enabled=FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal"))&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinLegacyBridges"))&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinLegacyJSON"));
        if(!Enabled){Test->TestFalse(TEXT("Legacy renderer keeps its original bridge surfaces"),Scene->BridgeData.IsValid());Started=0;return true;}
        if(!Test->TestTrue(TEXT("Detailed bridge manifest is loaded"),Scene->BridgeData.IsValid())){Started=0;return true;}
        const auto& Profiles=Array(Scene->BridgeData,TEXT("profiles"));Test->TestEqual(TEXT("Seven complete bridges reconstructed"),Profiles.Num(),7);
        const int32 OldQuality=Scene->DetailQuality;Scene->DetailQuality=1;Scene->ApplyDetailQuality();
        FCollisionQueryParams Query;Query.AddIgnoredActor(Context.World()->GetFirstPlayerController()->GetPawn());
        TArray<UHierarchicalInstancedStaticMeshComponent*> Fixtures;Scene->GetComponents(Fixtures);for(auto Fixture:Fixtures)Query.AddIgnoredComponent(Fixture);
        int32 Samples=0;
        for(const auto& V:Profiles){auto B=V->AsObject();const auto& C=Array(B,TEXT("centre_cm"));const auto& D=Array(B,TEXT("direction"));const FVector Centre(C[0]->AsNumber(),C[1]->AsNumber(),0),Direction(D[0]->AsNumber(),D[1]->AsNumber(),0),Side(-Direction.Y,Direction.X,0);const double L=Number(B,TEXT("length_cm")),W=Number(B,TEXT("width_cm"));
            for(double X:{-.38,-.20,0.,.20,.38})for(double Y:{-.40,-.20,0.,.20,.40}){
                FVector P=Centre+Direction*(X*L)+Side*(Y*W);double Z=0;
                if(!Test->TestTrue(TEXT("Bridge height covers former gaps between lanes"),ParisBridgeSurfaceHeight(Scene,P,Z)))continue;
                FHitResult Hit;const bool Found=Context.World()->LineTraceSingleByChannel(Hit,FVector(P.X,P.Y,Z+80),FVector(P.X,P.Y,Z-80),ECC_Pawn,Query);
                Test->TestTrue(*FString::Printf(TEXT("%s continuous walking collider at x=%.2f y=%.2f"),*String(B,TEXT("id")),X,Y),Found&&Hit.GetComponent()&&Hit.GetComponent()->ComponentHasTag(TEXT("ParisBridgeCollider")));
                if(Found){Test->TestTrue(TEXT("Rendered deck height and collision agree"),FMath::Abs(Hit.ImpactPoint.Z-Z)<1.);
                    Scene->SelectHit(Hit);Test->TestTrue(TEXT("Bridge clicks retain an original OSM source and actual coordinates"),Scene->Selection.Contains(String(B,TEXT("primary_source_id")))&&Scene->Selection.Contains(TEXT("CLICK WGS84")));}
                Samples++;
            }
            FVector P=Centre+Side*(W*.5-160);double Z=0;if(ParisBridgeSurfaceHeight(Scene,P,Z)){
                FHitResult Hit;const FVector Start(P.X,P.Y,Z+88),End=Start+Side*230;
                Test->TestTrue(TEXT("A capsule cannot walk through the bridge parapet"),Context.World()->SweepSingleByChannel(Hit,Start,End,FQuat::Identity,ECC_Pawn,FCollisionShape::MakeCapsule(34,86),Query)&&Hit.GetComponent()&&Hit.GetComponent()->ComponentHasTag(TEXT("ParisBridgeCollider")));
            }
        }
        Test->TestEqual(TEXT("All bridges sampled across carriageway and both pavements"),Samples,175);
        Scene->DetailQuality=0;Scene->ApplyDetailQuality();double LowZ;const auto B=Profiles[0]->AsObject();const auto& C=Array(B,TEXT("centre_cm"));Test->TestTrue(TEXT("Low quality retains a complete walkable bridge"),ParisBridgeSurfaceHeight(Scene,FVector(C[0]->AsNumber(),C[1]->AsNumber(),0),LowZ));
        Scene->ToggleLevels();Test->TestFalse(TEXT("Accuracy overlay restores archived bridge geometry"),ParisBridgeSurfaceHeight(Scene,FVector(C[0]->AsNumber(),C[1]->AsNumber(),0),LowZ));Scene->ToggleLevels();
        Scene->DetailQuality=OldQuality;Scene->ApplyDetailQuality();Started=0;return true;
    }
    if(FPlatformTime::Seconds()-Started>100){Test->AddError(TEXT("Bridge walking scene did not become ready"));Started=0;return true;}return false;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisBridgeWalkTest,"ParisDigitalTwin.Live.RealisticBridgesAndContinuousWalking",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisBridgeWalkTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FParisBridgeWalkWait(this));return true;}
#endif
