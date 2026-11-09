#include "ParisMinimap.h"
#include "ParisDigitalTwin.h"
#include "ParisWalker.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Misc/AutomationTest.h"
#include "Camera/PlayerCameraManager.h"

#if WITH_DEV_AUTOMATION_TESTS
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FParisMinimapWait,FAutomationTestBase*,Test);
bool FParisMinimapWait::Update(){
    for(const auto& Context:GEngine->GetWorldContexts())if(auto World=Context.World())for(TActorIterator<AParisTwinScene> It(World);It;++It){
        auto S=*It;if(!S->bReady)continue;auto Report=MakeShared<FJsonObject>();AddParisMinimapStats(S,Report);Test->TestTrue(TEXT("Offline map belongs to the loaded GIS scene"),Report->GetBoolField(TEXT("minimap_ready")));Test->TestTrue(TEXT("Real mapped polygons loaded"),Report->GetNumberField(TEXT("minimap_triangles"))>1000);
        const FVector4 B(-40000,-40000,40000,40000);Test->TestTrue(TEXT("Shared origin appears at the map centre"),ParisMapPoint(FVector::ZeroVector,B).Equals(FVector2D(.5,.5)));Test->TestTrue(TEXT("Lambert north is screen up"),ParisMapPoint(FVector(0,-40000,0),B).Equals(FVector2D(.5,0)));Test->TestTrue(TEXT("East stays on the right"),ParisMapPoint(FVector(40000,0,0),B).Equals(FVector2D(1,.5)));
        auto PC=Cast<AParisTwinController>(World->GetFirstPlayerController());if(!PC)return true;auto HUD=PC->GetHUD();
        for(const auto& Size:TArray<FVector2D>{{800,600},{1280,720},{1920,1080}}){auto R=ParisMinimapRect(HUD,Size.X,Size.Y);Test->TestTrue(TEXT("Map remains in the top right at different resolutions"),R.IsValid()&&R.X>Size.X*.6&&R.X+R.Size+20<Size.X&&R.Y+R.Size+65<Size.Y-48);Test->TestTrue(TEXT("Map consumes clicks inside its own panel"),R.Contains(FVector2D(R.X+10,R.Y+10)));}
        ToggleParisMinimap(HUD);Test->TestFalse(TEXT("8 hides only the map panel"),ParisMinimapRect(HUD,1280,720).IsValid());ToggleParisMinimap(HUD);Test->TestTrue(TEXT("8 restores the map"),ParisMinimapRect(HUD,1280,720).IsValid());
        auto OldView=PC->GetViewTarget();PC->Overview();auto Camera=Cast<AParisTwinCamera>(PC->GetPawn());const auto OldTarget=Camera?Camera->Target:FVector::ZeroVector;
        if(Camera){Camera->Target=FVector(1234,-4567,150);FRotator R;FString Label;Test->TestTrue(TEXT("Aerial map follows the point being viewed, not the distant camera"),ParisMapObserver(S,R,Label).Equals(Camera->Target,.01));Camera->Target=OldTarget;}
        if(PC->EnterWalk(true)){FRotator R;FString Label;Test->TestTrue(TEXT("Walking map tracks the player rather than the trailing camera"),ParisMapObserver(S,R,Label).Equals(PC->GetPawn()->GetActorLocation(),.01));Test->TestEqual(TEXT("Walking marker is labelled current position"),Label,FString(TEXT("現在地")));PC->ReturnToFree();}else Test->AddError(TEXT("Could not validate a walking map marker"));
        PC->SetViewTarget(OldView);return true;
    }return false;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisMinimapTest,"ParisDigitalTwin.Live.MinimapGeographyAndPlayerTracking",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisMinimapTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FParisMinimapWait(this));return true;}
#endif
