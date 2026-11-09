#include "ParisLuxury.h"
#include "ParisDigitalTwin.h"
#include "Components/CapsuleComponent.h"
#include "Components/BoxComponent.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Camera/CameraActor.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Misc/AutomationTest.h"
#if WITH_DEV_AUTOMATION_TESTS
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FParisLuxuryWait,FAutomationTestBase*,Test);
bool FParisLuxuryWait::Update(){
    static double Started=0;if(!Started)Started=FPlatformTime::Seconds();
    for(const auto& Context:GEngine->GetWorldContexts())if(auto World=Context.World())for(TActorIterator<AParisTwinScene> It(World);It;++It){auto S=*It;if(!S->bReady)continue;
        auto Stats=MakeShared<FJsonObject>();AddParisLuxuryStats(S,Stats);
        Test->TestEqual(TEXT("Shared decoration mesh groups"),(int32)Stats->GetNumberField(TEXT("luxury_models")),89);
        Test->TestTrue(TEXT("Shop displays populate the district"),Stats->GetNumberField(TEXT("street_shop_displays"))>40);
        Test->TestTrue(TEXT("Additional street accents actually loaded"),Stats->GetNumberField(TEXT("street_extra_objects"))>100);
        Test->TestTrue(TEXT("Street windows reuse source-aligned relief prototypes"),Stats->GetNumberField(TEXT("luxury_relief_windows"))>10000);
        Test->TestTrue(TEXT("Only a subset of upper windows receives inferred warm light"),Stats->GetNumberField(TEXT("luxury_lit_windows"))>2000&&Stats->GetNumberField(TEXT("luxury_lit_windows"))<15000);
        Test->TestTrue(TEXT("Over two thousand source windows receive flowers"),Stats->GetNumberField(TEXT("luxury_upper_windows"))>=2200);
        Test->TestTrue(TEXT("Streets receive overhead pennants and lights"),Stats->GetNumberField(TEXT("luxury_street_garlands"))>=30);
        Test->TestTrue(TEXT("District lamps receive safe banners and flowers"),Stats->GetNumberField(TEXT("luxury_district_poles"))>=300);
        Test->TestTrue(TEXT("Blank facade gaps receive banners"),Stats->GetNumberField(TEXT("luxury_facade_banners"))>=10);
        Test->TestEqual(TEXT("Each banner has a saved lantern"),Stats->GetNumberField(TEXT("luxury_facade_banners")),Stats->GetNumberField(TEXT("luxury_facade_lanterns")));
        Test->TestTrue(TEXT("Over one hundred baskets use verified walking headroom"),Stats->GetNumberField(TEXT("luxury_hanging_baskets"))>=100);
        Test->TestEqual(TEXT("Twelve bulbs per storefront"),(int32)Stats->GetNumberField(TEXT("luxury_bulbs")),4740);
        Test->TestEqual(TEXT("Every mapped storefront canopy upgraded"),(int32)Stats->GetNumberField(TEXT("luxury_canopies")),395);
        Test->TestEqual(TEXT("Existing tagged terrace upgrades"),(int32)Stats->GetNumberField(TEXT("luxury_tables")),49);
        Test->TestTrue(TEXT("Safely placed inferred flower urns"),Stats->GetNumberField(TEXT("luxury_urns"))>=200);
        TArray<UCapsuleComponent*> All,Colliders;S->GetComponents(All);for(auto C:All)if(C->ComponentHasTag(TEXT("ParisLuxuryUrn")))Colliders.Add(C);
        Test->TestEqual(TEXT("Physical urn proxies"),Colliders.Num(),(int32)Stats->GetNumberField(TEXT("luxury_urns")));const bool Old=S->bStreetDetails;if(!Old)S->ToggleStreetDetails();
        for(auto C:Colliders){Test->TestEqual(TEXT("Visible urn blocks walker"),C->GetCollisionResponseToChannel(ECC_Pawn),ECR_Block);Test->TestEqual(TEXT("Visible urn collision enabled"),C->GetCollisionEnabled(),ECollisionEnabled::QueryAndPhysics);}
        if(Colliders.Num()){FHitResult Hit;Hit.Component=Colliders[0];Test->TestTrue(TEXT("Urn can be inspected"),SelectParisLuxuryHit(S,Hit));Test->TestTrue(TEXT("Urn retains parent geographic ID"),S->Selection.Contains(TEXT("osm/")));Test->TestTrue(TEXT("Urn shows placement coordinates"),S->SelectionCoordinates.Contains(TEXT("WGS84")));S->ClearInspection();}
        TArray<UBoxComponent*> Boxes;S->GetComponents(Boxes);int32 NewBoxes=0;for(auto C:Boxes)if(C->ComponentHasTag(TEXT("ParisStreetPropCollision"))){NewBoxes++;Test->TestEqual(TEXT("Visible shop props block the walker"),C->GetCollisionEnabled(),ECollisionEnabled::QueryAndPhysics);}Test->TestTrue(TEXT("New displays use bounded collision proxies"),NewBoxes>40);
        S->ToggleStreetDetails();for(auto C:Colliders)Test->TestEqual(TEXT("Hidden urn leaves no invisible collision"),C->GetCollisionEnabled(),ECollisionEnabled::NoCollision);
        for(auto C:Boxes)if(C->ComponentHasTag(TEXT("ParisStreetPropCollision")))Test->TestEqual(TEXT("F6 removes hidden shop prop collisions"),C->GetCollisionEnabled(),ECollisionEnabled::NoCollision);
        TArray<UHierarchicalInstancedStaticMeshComponent*> Parts;S->GetComponents(Parts);for(auto C:Parts)if(C->ComponentHasTag(TEXT("ParisLuxury")))Test->TestFalse(TEXT("F6 hides decoration"),C->IsVisible());
        for(auto C:Parts)if(C->ComponentHasTag(TEXT("festoon_bulbs"))){Test->TestTrue(TEXT("Saved warm bulb material loads"),C->GetMaterial(0)!=nullptr);Test->TestFalse(TEXT("Small bulbs cast no costly shadows"),C->CastShadow);Test->TestEqual(TEXT("Decorative lights do not block walking"),C->GetCollisionEnabled(),ECollisionEnabled::NoCollision);}
        for(auto C:Parts)if(C->ComponentHasTag(TEXT("street_festoon_wire"))){
            Test->TestEqual(TEXT("Overhead decorations add no invisible collision"),C->GetCollisionEnabled(),ECollisionEnabled::NoCollision);
            for(int32 I=0;I<C->GetInstanceCount();I++){FTransform Transform;C->GetInstanceTransform(I,Transform);Test->TestTrue(TEXT("Span follows measured wall separation"),Transform.GetScale3D().X>=.6&&Transform.GetScale3D().X<=1.5);Test->TestTrue(TEXT("Span preserves vertical real-world scale"),FMath::IsNearlyEqual(Transform.GetScale3D().Z,1.));}
        }
        for(auto C:Parts)if(C->ComponentTags.ContainsByPredicate([](const FName& T){return T.ToString().StartsWith(TEXT("night_window_"));})){
            Test->TestFalse(TEXT("Window overlays add no shadows"),C->CastShadow);Test->TestEqual(TEXT("Window overlays cannot block walking"),C->GetCollisionEnabled(),ECollisionEnabled::NoCollision);
            Test->TestEqual(TEXT("Shared night shader can remove daytime overlays"),C->GetMaterial(0)->GetBlendMode(),BLEND_Masked);
        }
        for(auto C:Parts)if(C->ComponentTags.ContainsByPredicate([](const FName& T){return T.ToString().StartsWith(TEXT("proxy_"));})){
            Test->TestNotNull(TEXT("Distant decoration has its own distance control"),Cast<UMaterialInstanceDynamic>(C->GetMaterial(0)));Test->TestFalse(TEXT("Distant substitutes do not cast shadows"),C->CastShadow);Test->TestEqual(TEXT("Distant substitutes cannot block walking"),C->GetCollisionEnabled(),ECollisionEnabled::NoCollision);
        }
        for(TActorIterator<ACameraActor> Camera(World);Camera;++Camera)if(Camera->GetFName()==FName(TEXT("Camera_Paris_Street"))){
            const auto Location=Camera->GetActorLocation();const auto Rotation=Camera->GetActorRotation();Test->TestTrue(TEXT("District tour activates a saved camera"),CycleParisDistrictView(S));Test->TestTrue(TEXT("District tour changes location"),!Camera->GetActorLocation().Equals(Location,1));Camera->SetActorLocationAndRotation(Location,Rotation);break;
        }
        S->ToggleStreetDetails();if(!Old)S->ToggleStreetDetails();Started=0;return true;
    }
    if(FPlatformTime::Seconds()-Started>120){Test->AddError(TEXT("Luxury scene readiness timeout"));Started=0;return true;}return false;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisLuxuryTest,"ParisDigitalTwin.Live.LuxuryStreetAndWalkingClearance",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisLuxuryTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FParisLuxuryWait(this));return true;}
#endif
