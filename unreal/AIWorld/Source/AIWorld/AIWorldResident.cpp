#include "AIWorldResident.h"
#include "AIWorldScene.h"
#include "WorldProtocol.h"
#include "Components/StaticMeshComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "AIWorldPlayer.h"
using namespace AIWorld;
AAIWorldResident::AAIWorldResident() {
    PrimaryActorTick.bCanEverTick=true;
    RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    Upper=CreateDefaultSubobject<USceneComponent>(TEXT("Upper"));Upper->SetupAttachment(RootComponent);
    HeadPivot=CreateDefaultSubobject<USceneComponent>(TEXT("Head"));HeadPivot->SetupAttachment(Upper);
    for(int32 I=0;I<2;I++) {
        auto Arm=CreateDefaultSubobject<USceneComponent>(*FString::Printf(TEXT("Arm%d"),I));Arm->SetupAttachment(Upper);ArmPivots.Add(Arm);
        auto Leg=CreateDefaultSubobject<USceneComponent>(*FString::Printf(TEXT("Leg%d"),I));Leg->SetupAttachment(RootComponent);LegPivots.Add(Leg);
    }
    Ring=CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Selection"));Ring->SetupAttachment(RootComponent);
    Ring->SetStaticMesh(ConstructorHelpers::FObjectFinder<UStaticMesh>(TEXT("/Engine/BasicShapes/Cylinder.Cylinder")).Object);
    Ring->SetRelativeScale3D(FVector(.85,.85,.025));Ring->SetRelativeLocation(FVector(0,0,3));Ring->SetCollisionEnabled(ECollisionEnabled::NoCollision);Ring->SetVisibility(false);Ring->SetCastShadow(false);
}
UProceduralMeshComponent* AAIWorldResident::Part(const TSharedPtr<FJsonObject>& J,USceneComponent* Parent) {
    FMesh M; if(!DecodeMesh(J,M))return nullptr;for(auto& Color:M.Colors)if(Color.Equals(ShirtFrom,.0001f))Color=ShirtTo;auto C=NewObject<UProceduralMeshComponent>(this);
    AddInstanceComponent(C);C->SetupAttachment(Parent);C->RegisterComponent();C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    C->CreateMeshSection_LinearColor(0,M.Positions,M.Indices,M.Normals,{},M.Colors,{},false);C->SetMaterial(0,Scene->VertexMaterial());Parts.Add(C);return C;
}
void AAIWorldResident::Rebuild() {
    for(auto C:Parts)if(C)C->DestroyComponent();Parts.Reset();Tool=nullptr;Cargo=nullptr;
    auto R=Object(Object(Scene->Models(),TEXT("residents")),ID+TEXT(":")+Job);if(!R)R=Object(Object(Scene->Models(),TEXT("residents")),Job);if(!R)R=Object(Object(Scene->Models(),TEXT("residents")),TEXT("採集家"));RenderModel=R;
    ShirtFrom=FLinearColor(FColor::FromHex(String(R,TEXT("shirt"))));ShirtTo=FLinearColor(FColor::FromHex(Clothing));
    Part(Object(R,TEXT("body")),Upper);Face=Part(Object(R,TEXT("head")),HeadPivot);BaseFace=FMesh();DecodeMesh(Object(R,TEXT("head")),BaseFace);FaceMorphs.Reset();for(const auto& V:Array(R,TEXT("morphs"))){const auto& Row=V->AsArray();if(Row.Num()==4)FaceMorphs.Add(FVector4(Row[0]->AsNumber(),Row[1]->AsNumber(),Row[2]->AsNumber(),Row[3]->AsNumber()));}
    HeadPivot->SetRelativeLocation(FVector(0,0,72));
    for(int32 I=0;I<2;I++) {
        ArmPivots[I]->SetRelativeLocation(FVector((I?1:-1)*32,0,46));LegPivots[I]->SetRelativeLocation(FVector((I?1:-1)*12.5,0,60));
        Part(Object(R,TEXT("arm")),ArmPivots[I]);Part(Object(R,TEXT("leg")),LegPivots[I]);
    }
    ToolName=Job==TEXT("建築家")?TEXT("hammer"):Job==TEXT("木こり")?TEXT("axe"):Job==TEXT("採掘師")?TEXT("pick"):Job==TEXT("農家")?TEXT("hoe"):TEXT("basket");
    Tool=Part(Object(Object(R,TEXT("tools")),ToolName),ArmPivots[1]);if(Tool)Tool->SetRelativeLocation(FVector(0,5,-44));
    CargoName=TEXT("food");Cargo=Part(Object(Object(R,TEXT("cargos")),CargoName),Upper);if(Cargo)Cargo->SetRelativeLocation(FVector(0,40,25));
    Ring->SetMaterial(0,Scene->ColorMaterial(TEXT("#e5b764")));
}
void AAIWorldResident::Sync(AAIWorldScene* World,const TSharedPtr<FJsonObject>& J) {
    Scene=World;ID=String(J,TEXT("id"));Action=String(J,TEXT("action"));Clothing=String(J,TEXT("color"));const FString NewJob=String(J,TEXT("job"));bTired=Action==TEXT("resting")||Number(J,TEXT("energy"))<25;bWorried=Number(J,TEXT("health"))<40||Number(J,TEXT("hunger"))>75;bHappy=Action==TEXT("socializing")||Object(J,TEXT("speech")).IsValid();
    Destination=Position(Object(J,TEXT("position")));
    if(!bInitialized){bInitialized=true;SetActorLocation(Destination);Phase=(GetTypeHash(ID)%628)/100.;}
    if(Job!=NewJob){Job=NewJob;Rebuild();}
    FString DesiredTool=Job==TEXT("建築家")?TEXT("hammer"):Job==TEXT("木こり")?TEXT("axe"):Job==TEXT("採掘師")?TEXT("pick"):Job==TEXT("農家")?TEXT("hoe"):TEXT("basket");
    if(Action==TEXT("building"))DesiredTool=TEXT("hammer");else if(Action==TEXT("farming"))DesiredTool=TEXT("hoe");else if(Action==TEXT("gathering")){const FString Target=String(Object(J,TEXT("task")),TEXT("targetId"));for(const auto& V:Array(Scene->Village,TEXT("nodes"))){auto N=V->AsObject();if(String(N,TEXT("id"))==Target){const FString Kind=String(N,TEXT("kind"));DesiredTool=Kind==TEXT("wood")?TEXT("axe"):Kind==TEXT("stone")?TEXT("pick"):TEXT("basket");break;}}}
    if(DesiredTool!=ToolName){if(Tool){Parts.Remove(Tool);Tool->DestroyComponent();}ToolName=DesiredTool;Tool=Part(Object(Object(RenderModel,TEXT("tools")),ToolName),ArmPivots[1]);if(Tool)Tool->SetRelativeLocation(FVector(0,5,-44));}
    auto Inv=Object(J,TEXT("inventory"));const FString CargoKind=Number(Inv,TEXT("food"))>0?TEXT("food"):Number(Inv,TEXT("stone"))>0?TEXT("stone"):TEXT("wood");
    if(CargoKind!=CargoName){if(Cargo){Parts.Remove(Cargo);Cargo->DestroyComponent();}CargoName=CargoKind;Cargo=Part(Object(Object(RenderModel,TEXT("cargos")),CargoName),Upper);if(Cargo)Cargo->SetRelativeLocation(FVector(0,40,25));}
    if(Cargo)Cargo->SetVisibility(Number(Inv,TEXT("food"))+Number(Inv,TEXT("wood"))+Number(Inv,TEXT("stone"))>0);
}
void AAIWorldResident::Select(bool Value){Ring->SetVisibility(Value);}
void AAIWorldResident::Tick(float Delta) {
    Super::Tick(Delta);if(!Scene)return;
    const FVector Old=GetActorLocation();SetActorLocation(FMath::VInterpTo(Old,Destination,Delta,10));
    const FVector Move=Destination-Old;if(Move.SizeSquared2D()>1)SetActorRotation(FRotator(0,FMath::RadiansToDegrees(FMath::Atan2(Move.Y,Move.X))-90,0));
    auto PC=Cast<AAIWorldPlayer>(GetWorld()->GetFirstPlayerController());auto Camera=PC?PC->View():nullptr;
    if(Camera && Camera->Radius>7000 && PC->Selected!=ID){if(Tool)Tool->SetVisibility(Action==TEXT("building")||Action==TEXT("gathering")||Action==TEXT("farming"));return;}
    if(Scene->Speed>0)Anim+=Delta;const double Swing=FMath::Sin(Anim*8+Phase),Stride=FMath::Sin(Anim*10+Phase);
    const bool Walk=Action==TEXT("moving"), Work=Action==TEXT("building")||Action==TEXT("gathering")||Action==TEXT("farming"),Rest=Action==TEXT("resting");
    Upper->SetRelativeLocation(FVector(0,0,Rest?48:64+(Walk?FMath::Abs(Stride)*1.8:FMath::Sin(Anim*2+Phase)*.9)));
    Upper->SetRelativeRotation(FQuat(FVector::ForwardVector,Rest?-.08:Work?-.12:0));
    HeadPivot->SetRelativeRotation(FQuat(FVector::UpVector,Action==TEXT("exploring")?FMath::Sin(Anim*.8)*.35:FMath::Sin(Anim*.65+Phase)*.07));
    for(int32 I=0;I<2;I++) {
        const double Sign=I?1:-1;
        LegPivots[I]->SetRelativeRotation(FQuat(FVector::ForwardVector,Walk?Sign*Stride*.52:Rest?.25:0));
        LegPivots[I]->SetRelativeLocation(FVector(Sign*12.5,0,Rest?45:60));
        LegPivots[I]->SetRelativeScale3D(FVector(1,1,Rest?.75:1));
        const double Arm=Walk?-Sign*Stride*.36:Work?(I?.95-Swing*.55:.4):Action==TEXT("eating")?1.5:Action==TEXT("socializing")&&I?.75-Swing*.15:Rest?.3:0;
        ArmPivots[I]->SetRelativeRotation(FQuat(FVector::ForwardVector,Arm));
    }
    if(Tool)Tool->SetVisibility(Work || Action==TEXT("idle") || Action==TEXT("exploring"));
    if(Face && Anim>=NextFace){NextFace=Anim+.12;const double Cycle=3.2+FMath::Fmod(Phase,2.3),T=FMath::Fmod(Anim+Phase,Cycle);double Blink=FMath::Max(0.,1-FMath::Abs(T-.12)/.12);if(bTired)Blink=FMath::Max(Blink,Rest?.85:.35);FMesh M=BaseFace;
        for(const auto& Row:FaceMorphs){const int32 I=Row.X;if(M.Positions.IsValidIndex(I))M.Positions[I].Z+=(Row.Y*Blink+Row.Z*(bHappy?1:0)+Row.W*(bWorried?1:0))*Unit;}
        Face->UpdateMeshSection_LinearColor(0,M.Positions,M.Normals,{},M.Colors,{});
    }
}
