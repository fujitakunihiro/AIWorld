#include "ParisDigitalTwin.h"
#include "ParisRoadDetail.h"
#include "WorldProtocol.h"
#include "Engine/Engine.h"
#include "Engine/Texture2D.h"
#include "EngineUtils.h"
#include "Components/StaticMeshComponent.h"
#include "ProceduralMeshComponent.h"
#include "Materials/MaterialInterface.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

#if WITH_DEV_AUTOMATION_TESTS
DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(FParisRoadWait,FAutomationTestBase*,Test);
bool FParisRoadWait::Update(){
    static double Started=0;if(!Started)Started=FPlatformTime::Seconds();
    for(const auto& Context:GEngine->GetWorldContexts())if(Context.World())for(TActorIterator<AParisTwinScene> It(Context.World());It;++It){
        auto Scene=*It;if(!Scene->bReady)continue;
        const bool Photo=FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal"))&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinLegacyRoads"))&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinProceduralSurfaces"));
        const int32 OldQuality=Scene->DetailQuality;const bool OldSurfaces=Scene->bDetailedSurfaces,OldProps=Scene->bStreetDetails;
        Scene->DetailQuality=2;Scene->bDetailedSurfaces=true;Scene->bStreetDetails=true;Scene->ApplyDetailQuality();
        TArray<UStaticMeshComponent*> Components;Scene->GetComponents(Components);TArray<UStaticMeshComponent*> Details;
        for(auto Part:Components)if(Part->ComponentHasTag(TEXT("ParisRoadDetail"))){
            Details.Add(Part);Test->TestTrue(TEXT("Detailed street edges are visible"),Part->IsVisible());
            Test->TestEqual(TEXT("Inferred road art cannot change source collision"),Part->GetCollisionEnabled(),ECollisionEnabled::NoCollision);
            Test->TestFalse(TEXT("Road art cannot intercept geographic clicks"),Part->GetCollisionResponseToChannel(ECC_Visibility)==ECR_Block);
        }
        Test->TestTrue(TEXT("Road details are restricted to photographic mode"),Photo?Details.Num()>0:Details.IsEmpty());
        if(Photo){
            auto Atlas=LoadObject<UTexture2D>(nullptr,TEXT("/Game/Textures/T_ParisRoadEdge"));
            if(Test->TestNotNull(TEXT("GIS-aligned street distance atlas exists"),Atlas)){
                Test->TestFalse(TEXT("Packed centimetre distances remain linear"),bool(Atlas->SRGB));
                Test->TestEqual(TEXT("Packed distance precision is not block compressed"),Atlas->CompressionSettings,TC_VectorDisplacementmap);
                Test->TestEqual(TEXT("Atlas must not wrap to another street"),Atlas->AddressX,TA_Clamp);
            }
            TArray<UProceduralMeshComponent*> Sources;Scene->GetComponents(Sources);UProceduralMeshComponent* Road=nullptr;
            for(auto Mesh:Sources)if(auto Material=Mesh->GetMaterial(0))if(Material->GetName()==TEXT("M_ParisRoadAsphalt"))Road=Mesh;
            if(Test->TestNotNull(TEXT("The real source roadway receives the new asphalt"),Road)){
                const int32 Vertices=Road->GetProcMeshSection(0)->ProcVertexBuffer.Num();
                Scene->bDetailedSurfaces=false;Scene->ApplyDetailQuality();
                Test->TestEqual(TEXT("Flat mode uses the original source surface"),Road->GetMaterial(0)->GetName(),FString(TEXT("M_Vertex")));
                for(auto Part:Details)Test->TestFalse(TEXT("Flat mode removes road decorations"),Part->IsVisible());
                Scene->bDetailedSurfaces=true;Scene->DetailQuality=0;Scene->ApplyDetailQuality();
                for(auto Part:Details)Test->TestFalse(TEXT("Low quality omits kerbs and grates"),Part->IsVisible());
                Scene->DetailQuality=2;Scene->ApplyDetailQuality();
                Test->TestEqual(TEXT("Visual switching retains every original road vertex"),Road->GetProcMeshSection(0)->ProcVertexBuffer.Num(),Vertices);
                Test->TestEqual(TEXT("Detailed road material restores"),Road->GetMaterial(0)->GetName(),FString(TEXT("M_ParisRoadAsphalt")));
                Scene->bStreetDetails=false;Scene->ApplyDetailQuality();for(auto Part:Details)Test->TestFalse(TEXT("Props toggle includes cosmetic street edges"),Part->IsVisible());
                Scene->bStreetDetails=true;Scene->ToggleLevels();for(auto Part:Details)Test->TestFalse(TEXT("Accuracy overlay hides inferred street fixtures"),Part->IsVisible());Scene->ToggleLevels();
            }
        }
        Scene->DetailQuality=OldQuality;Scene->bDetailedSurfaces=OldSurfaces;Scene->bStreetDetails=OldProps;Scene->ApplyDetailQuality();
        Started=0;return true;
    }
    if(FPlatformTime::Seconds()-Started>90){Test->AddError(TEXT("Road verification scene did not become ready"));Started=0;return true;}return false;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FParisRoadTest,"ParisDigitalTwin.Live.RoadFinishAndCollision",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ClientContext|EAutomationTestFlags::EngineFilter)
bool FParisRoadTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FParisRoadWait(this));return true;}
#endif
