#include "ParisTraffic.h"
#include "ParisDigitalTwin.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/StaticMesh.h"
#include "EngineUtils.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

#if WITH_DEV_AUTOMATION_TESTS
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FParisVehicleVisualWait,FAutomationTestBase*,Test);
bool FParisVehicleVisualWait::Update(){
    static double Started=0;if(!Started)Started=FPlatformTime::Seconds();
    for(const auto& Context:GEngine->GetWorldContexts())if(Context.World())for(TActorIterator<AParisTwinScene> It(Context.World());It;++It){
        auto Scene=*It;auto Traffic=Scene->Traffic;if(!Scene->bReady||!Traffic||!Traffic->bReady)continue;
        if(FParse::Param(FCommandLine::Get(),TEXT("ParisTwinSimpleCars"))){Test->TestFalse(TEXT("Explicit original car fallback remains available"),Traffic->HasDetailedModels());Started=0;return true;}
        if(!Test->TestTrue(TEXT("Verified detailed car assets load"),Traffic->HasDetailedModels())){Started=0;return true;}
        const int32 OldQuality=Scene->DetailQuality;Traffic->SetDisplay(true,1);
        if(auto PC=Cast<AParisTwinController>(Context.World()->GetFirstPlayerController())){PC->InspectTraffic();if(PC->PlayerCameraManager)PC->PlayerCameraManager->UpdateCamera(0);}
        const auto Before=Traffic->Vehicles();Traffic->SimulateStep(.05);int32 Rolling=0;
        for(int32 I=0;I<Before.Num();I++){const auto& A=Before[I];const auto& B=Traffic->Vehicles()[I];
            if(A.bActive&&B.bActive&&B.Distance>A.Distance&&B.Distance-A.Distance<30){
                const double Expected=FVector::Dist2D(A.Position,B.Position)/Traffic->TireRadiusCm();
                Test->TestTrue(TEXT("Wheel rotation matches real route displacement"),FMath::Abs(FMath::FindDeltaAngleRadians(A.WheelPhase,B.WheelPhase)-Expected)<1.e-6);Rolling++;
            }
            if(A.Distance==B.Distance)Test->TestEqual(TEXT("Waiting wheels do not spin"),B.WheelPhase,A.WheelPhase);
        }
        Test->TestTrue(TEXT("At least one car rolls on its existing route"),Rolling>0);
        for(int32 I=0;I<Traffic->Vehicles().Num();I++){const auto A=Traffic->Vehicles()[I];if(!A.bActive||A.Wait>0)continue;
            const FVector Player=Traffic->Network()[A.Route].Sample(A.Distance+A.Speed*.05,1);Traffic->SimulateStep(.05,&Player);
            Test->TestEqual(TEXT("Detailed cars still yield to player"),Traffic->Vehicles()[I].Distance,A.Distance);Test->TestEqual(TEXT("Braking also stops wheel rotation"),Traffic->Vehicles()[I].WheelPhase,A.WheelPhase);break;
        }
        Traffic->UpdateInstances();TArray<UInstancedStaticMeshComponent*> Meshes;Traffic->GetComponents(Meshes);UInstancedStaticMeshComponent* Body=nullptr;int32 Detailed=0,WheelBatches=0;
        for(auto Mesh:Meshes)if(Mesh->ComponentHasTag(TEXT("ParisDetailedCar"))){Detailed++;Test->TestEqual(TEXT("Every detailed batch has one instance per displayed car"),Mesh->GetInstanceCount(),Traffic->RenderedCount);Test->TestEqual(TEXT("Paint and brake custom data exist"),Mesh->NumCustomDataFloats,2);if(Mesh->GetInstanceCount()>0){FTransform Previous;Test->TestTrue(TEXT("Moving parts expose finite previous poses for temporal rendering"),Mesh->GetInstancePrevTransform(0,Previous,true)&&!Previous.ContainsNaN());}if(Mesh->ComponentHasTag(TEXT("ParisCarBody")))Body=Mesh;else if(!Mesh->ComponentHasTag(TEXT("ParisCarGlass")))WheelBatches++;}
        Test->TestEqual(TEXT("Body, glazing and four wheel batches"),Detailed,6);Test->TestEqual(TEXT("All four wheels have independent pivots"),WheelBatches,4);
        if(Test->TestNotNull(TEXT("Detailed shell mesh exists"),Body)){
            Test->TestTrue(TEXT("Source car uses real curved geometry"),Body->GetStaticMesh()->GetNumTriangles(0)>10000);
            Test->TestTrue(TEXT("Car has separate physical surface materials"),Body->GetStaticMesh()->GetStaticMaterials().Num()>8);
            const FBox Bounds=Body->GetStaticMesh()->GetBoundingBox();
            // Nanite fallback simplification may expand its conservative bounds
            // by a few centimetres. The actual invariant is the route's 2.4m
            // swept clearance, including those fallback bounds.
            const double X=FMath::Max(FMath::Abs(Bounds.Min.X),FMath::Abs(Bounds.Max.X)),Y=FMath::Max(FMath::Abs(Bounds.Min.Y),FMath::Abs(Bounds.Max.Y));
            Test->TestTrue(TEXT("Detailed and fallback body bounds fit the original road swept clearance"),FMath::Sqrt(X*X+Y*Y)<240&&Bounds.Min.Z>=-1&&Bounds.Max.Z<180);
            if(Test->TestTrue(TEXT("A close car is rendered"),Body->GetInstanceCount()>0)){
                FTransform T;Body->GetInstanceTransform(0,T,true);FHitResult Hit(Traffic,Body,T.GetLocation(),FVector::UpVector);Hit.Item=0;Scene->SelectHit(Hit);Test->TestTrue(TEXT("Detailed vehicle selection still traces road ID and real clicked coordinates"),Scene->Selection.Contains(TEXT("SIMULATED car"))&&Scene->Selection.Contains(TEXT("osm/way/"))&&Scene->Selection.Contains(TEXT("CLICK WGS84")));
                FCollisionQueryParams Picking;Picking.bTraceComplex=true;if(Scene->Crowd)Picking.AddIgnoredActor(Scene->Crowd);Picking.AddIgnoredActor(Context.World()->GetFirstPlayerController()->GetPawn());const FVector Aim=T.TransformPosition(FVector(0,0,85));FHitResult ActualHit;
                Test->TestTrue(TEXT("An actual complex cursor trace can pick the detailed vehicle"),Context.World()->LineTraceSingleByChannel(ActualHit,Aim+FVector(0,0,300),Aim-FVector(0,0,50),ECC_Visibility,Picking)&&ActualHit.GetActor()==Traffic&&ActualHit.GetComponent()==Body);
                for(auto Mesh:Meshes)if(Mesh->ComponentHasTag(TEXT("ParisDetailedCar"))&&!Mesh->ComponentHasTag(TEXT("ParisCarBody"))&&!Mesh->ComponentHasTag(TEXT("ParisCarGlass"))){FTransform W;Mesh->GetInstanceTransform(0,W,true);Test->TestTrue(TEXT("Wheel centres remain attached to their own car"),FVector::Dist(T.GetLocation(),W.GetLocation())<190);}
            }
            int32 GroundSamples=0;
            FCollisionQueryParams RoadQuery;RoadQuery.AddIgnoredActor(Traffic);if(Scene->Crowd)RoadQuery.AddIgnoredActor(Scene->Crowd);RoadQuery.AddIgnoredActor(Context.World()->GetFirstPlayerController()->GetPawn());
            for(int32 Step=0;Step<20;Step++){
                for(int32 K=0;K<20;K++)Traffic->SimulateStep(.05);Traffic->UpdateInstances();
                for(int32 I=0;I<Body->GetInstanceCount();I++){
                    FTransform Pose;Body->GetInstanceTransform(I,Pose,true);const FVector Root=Pose.GetLocation();FHitResult Floor;
                    if(Context.World()->LineTraceSingleByChannel(Floor,Root+FVector(0,0,500),Root-FVector(0,0,2000),ECC_Pawn,RoadQuery)&&Floor.ImpactNormal.Z>.65){
                        Test->TestTrue(TEXT("Moving cars neither sink into nor float above actual road collision"),FMath::Abs(Root.Z-Floor.ImpactPoint.Z)<8.);GroundSamples++;
                    }
                }
            }
            Test->TestTrue(TEXT("Road grounding sampled while vehicles travel and recycle"),GroundSamples>20);
        }
        const int32 Population=Traffic->Vehicles().Num();Traffic->SetDisplay(true,0);Test->TestFalse(TEXT("Low quality restores original car appearance"),Traffic->UsesDetailedModels());
        for(auto Mesh:Meshes)if(Mesh->ComponentHasTag(TEXT("ParisDetailedCar")))Test->TestTrue(TEXT("Hidden detailed car neither draws nor intercepts selection"),!Mesh->IsVisible()&&Mesh->GetInstanceCount()==0&&Mesh->GetCollisionEnabled()==ECollisionEnabled::NoCollision);
        Traffic->SetDisplay(true,2);Test->TestTrue(TEXT("High quality restores the detailed car"),Traffic->UsesDetailedModels());Test->TestEqual(TEXT("Appearance changes preserve simulated vehicles"),Traffic->Vehicles().Num(),Population);
        Traffic->SetDisplay(false,2);for(auto Mesh:Meshes)Test->TestTrue(TEXT("Disabling traffic clears all visual and picking instances"),!Mesh->IsVisible()&&Mesh->GetInstanceCount()==0&&Mesh->GetCollisionEnabled()==ECollisionEnabled::NoCollision);
        Scene->DetailQuality=OldQuality;Scene->ApplyDetailQuality();Started=0;return true;
    }
    if(FPlatformTime::Seconds()-Started>100){Test->AddError(TEXT("Vehicle scene failed to load"));Started=0;return true;}return false;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisVehicleVisualTest,"ParisDigitalTwin.Live.RealisticVehicleVisuals",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisVehicleVisualTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FParisVehicleVisualWait(this));return true;}
#endif
