#include "ParisStreetLife.h"
#include "ParisDigitalTwin.h"
#include "ParisProcMesh.h"
#include "ParisHumanAnimation.h"
#include "WorldProtocol.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/CapsuleComponent.h"
#include "Animation/AnimSequence.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Camera/PlayerCameraManager.h"
#include "Camera/CameraActor.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "Materials/MaterialInterface.h"
#include "MeshDescription.h"
#include "StaticMeshAttributes.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
using namespace AIWorld;

namespace {
using FLifeMesh=FParisProcMesh;
// Static mesh from the procedural builder; vertex colour carries the paint (M_ParisCloth reads it).
// Paint values are authored in display (sRGB-like) terms; the build stores vertex colour as sRGB and the
// material reads it back raw, so pre-linearise with gamma 2.2 to keep reds red and rattan brown.
UStaticMesh* BuildStatic(UObject* Outer,const FLifeMesh& M,UMaterialInterface* Mat){
    if(M.I.IsEmpty())return nullptr;
    FMeshDescription D;FStaticMeshAttributes A(D);A.Register();
    auto Pos=A.GetVertexPositions();auto Nrm=A.GetVertexInstanceNormals();auto Col=A.GetVertexInstanceColors();auto UV=A.GetVertexInstanceUVs();UV.SetNumChannels(1);
    TArray<FVertexID> Vs;Vs.Reserve(M.V.Num());for(const FVector& P:M.V){const FVertexID ID=D.CreateVertex();Pos[ID]=FVector3f(P);Vs.Add(ID);}
    const FPolygonGroupID G=D.CreatePolygonGroup();
    for(int32 I=0;I+2<M.I.Num();I+=3){TArray<FVertexInstanceID> T;for(int32 K=0;K<3;K++){const int32 Idx=M.I[I+K];const FVertexInstanceID VI=D.CreateVertexInstance(Vs[Idx]);Nrm[VI]=FVector3f(M.N[Idx]);Col[VI]=FVector4f(FMath::Pow(M.C[Idx].R,2.2f),FMath::Pow(M.C[Idx].G,2.2f),FMath::Pow(M.C[Idx].B,2.2f),1.f);UV.Set(VI,0,FVector2f(M.UV[Idx]));T.Add(VI);}D.CreatePolygon(G,T);}
    auto Mesh=NewObject<UStaticMesh>(Outer);Mesh->GetStaticMaterials().Add(FStaticMaterial(Mat));
    UStaticMesh::FBuildMeshDescriptionsParams Params;Params.bFastBuild=true;Params.bBuildSimpleCollision=false;
    const TArray<const FMeshDescription*> Ds{&D};return Mesh->BuildFromMeshDescriptions(Ds,Params)?Mesh:nullptr;
}
// A quad visible from both sides (the shared material is one-sided).
void Quad2(FLifeMesh& M,const FVector& A,const FVector& B,const FVector& C,const FVector& D){const FVector N=FVector::CrossProduct(B-A,D-A).GetSafeNormal();M.Face({A,B,C,D},N);M.Face({A,D,C,B},-N);}
void Disc(FLifeMesh& M,double X,double Y,double Z,double R,int32 Sides,bool Up){TArray<FVector> P;for(int32 K=0;K<Sides;K++){const double A=2*PI*K/Sides;P.Add(FVector(X+R*FMath::Cos(A),Y+R*FMath::Sin(A),Z));}M.Face(P,FVector(0,0,Up?1:-1));}
const FLinearColor Black(.025f,.025f,.025f),Marble(.70f,.68f,.64f),Chalk(.85f,.85f,.82f),Board(.03f,.035f,.03f);

FLifeMesh BistroTable(){FLifeMesh M;M.Col=Marble;M.Cone(0,0,70,73,31,31,20);Disc(M,0,0,73,31,20,true);Disc(M,0,0,70,31,20,false);M.Col=Black;M.Tube(FVector(0,0,4),FVector(0,0,70),3.2,8);M.Cone(0,0,0,4,22,17,14);Disc(M,0,0,4,17,14,true);return M;}
// Rattan bistro chair facing +Y (the street); the back is on the facade side.
FLifeMesh BistroChair(FLinearColor Weave){
    FLifeMesh M;const FLinearColor Frame(.20f,.11f,.05f);M.Col=Weave;M.Box(FVector(0,0,45),FVector(20,20,2.5));M.Box(FVector(0,-19,70),FVector(19,2,17));
    for(int32 K=0;K<5;K++){M.Col=(K%2)?Weave:Weave*.8f;M.Box(FVector(-16+K*8,-19.5f,70),FVector(1.2,2.4,17));}
    M.Col=Frame;for(double X:{-17.,17.})for(double Y:{-17.,17.})M.Tube(FVector(X,Y,0),FVector(X,Y*.95,43),1.7,6);
    for(double X:{-18.,18.})M.Tube(FVector(X,-19,43),FVector(X,-21,90),1.8,6);M.Tube(FVector(-18,-21,90),FVector(18,-21,90),1.8,6);
    M.Tube(FVector(-19,19,45),FVector(19,19,45),1.6,6);return M;
}
// Long terrace awning, 1 m wide (scaled along the facade), sloping out 2.8 m with a front valance.
FLifeMesh Awning(FLinearColor C){
    FLifeMesh M;M.Col=C;Quad2(M,FVector(-50,0,345),FVector(50,0,345),FVector(50,280,285),FVector(-50,280,285));
    Quad2(M,FVector(-50,280,285),FVector(50,280,285),FVector(50,280,250),FVector(-50,280,250));
    M.Col=FLinearColor(.80f,.78f,.70f);Quad2(M,FVector(-50,281,262),FVector(50,281,262),FVector(50,281,256),FVector(-50,281,256));
    M.Col=Black;M.Tube(FVector(-50,280,285),FVector(50,280,285),2,6);return M;
}
FLifeMesh AwningArm(){FLifeMesh M;M.Col=Black;M.Tube(FVector(0,0,330),FVector(0,278,286),2.5,6);M.Tube(FVector(0,0,250),FVector(0,180,300),1.8,6);return M;}
// Souvenir postcard spinner with four tiers of coloured cards.
FLifeMesh PostcardSpinner(){
    FLifeMesh M;FRandomStream R(3);M.Col=Black;M.Tube(FVector(0,0,0),FVector(0,0,175),1.6,8);for(double A:{0.,90.}){const FVector D=FRotator(0,A,0).Vector();M.Tube(-D*24+FVector(0,0,2),D*24+FVector(0,0,2),1.8,6);}
    for(int32 T=0;T<4;T++)for(int32 K=0;K<8;K++){const double A=2*PI*K/8;const FVector C(18*FMath::Cos(A),18*FMath::Sin(A),62+T*30);M.Col=FLinearColor(R.FRandRange(.15f,.9f),R.FRandRange(.15f,.8f),R.FRandRange(.1f,.8f));
        const FVector Out(FMath::Cos(A),FMath::Sin(A),0),Side(-Out.Y,Out.X,0);Quad2(M,C-Side*6-FVector(0,0,12),C+Side*6-FVector(0,0,12),C+Side*6+FVector(0,0,12),C-Side*6+FVector(0,0,12));}
    return M;
}
// Scarf / T-shirt rack: a chrome frame with bright hanging textiles.
FLifeMesh ScarfRack(){
    FLifeMesh M;FRandomStream R(7);const FLinearColor Chrome(.45f,.45f,.47f);M.Col=Chrome;for(double X:{-62.,62.}){M.Tube(FVector(X,0,0),FVector(X,0,158),1.6,8);M.Tube(FVector(X,-22,1),FVector(X,22,1),1.6,6);}M.Tube(FVector(-62,0,158),FVector(62,0,158),1.4,8);
    for(int32 K=0;K<15;K++){const double X=-56+K*8;M.Col=FLinearColor(R.FRandRange(.1f,.95f),R.FRandRange(.05f,.6f),R.FRandRange(.05f,.8f));const double L=R.FRandRange(45.f,85.f);M.Box(FVector(X,R.FRandRange(-3.f,3.f),158-L*.5),FVector(3.4,1.2,L*.5));}
    return M;
}
// Folding chalkboard menu (A-board).
FLifeMesh ABoard(FLinearColor FrameCol){
    FLifeMesh M;for(int32 S:{-1,1}){const FVector B0(-30,S*24,0),B1(30,S*24,0),T1(30,0,105),T0(-30,0,105);M.Col=FrameCol;Quad2(M,B0,B1,T1,T0);
        const FVector In=FVector(0,S*1.5,0);M.Col=Board;Quad2(M,FMath::Lerp(B0,T0,.1)+FVector(5,0,0)+In,FMath::Lerp(B1,T1,.1)-FVector(5,0,0)+In,FMath::Lerp(B1,T1,.88)-FVector(5,0,0)+In,FMath::Lerp(B0,T0,.88)+FVector(5,0,0)+In);
        M.Col=Chalk;for(int32 L=0;L<5;L++){const double T=.22+L*.13;const FVector P0=FMath::Lerp(B0,T0,T)+FVector(10,0,0)+In*2,P1=FMath::Lerp(B1,T1,T)-FVector(L%2?18:10,0,0)+In*2;Quad2(M,P0,P1,P1+FVector(0,0,1.6),P0+FVector(0,0,1.6));}}
    return M;
}
// Two folded halves give a broad leaf a bright ridge and a darker underside.
void PlanterLeaf(FLifeMesh& Mesh, const FVector& Base, double Angle, double Length,
    double Width, double Rise, const FLinearColor& Color){
    const FVector Forward(FMath::Cos(Angle),FMath::Sin(Angle),0);
    const FVector Across(-Forward.Y,Forward.X,0);
    const FVector Tip=Base+Forward*Length+FVector(0,0,Rise-3.0);
    const FVector Shoulder=Base+Forward*(Length*.47)+FVector(0,0,Rise*.72);
    const FVector Rib=Shoulder+FVector(0,0,1.25);
    for(int32 Sign : {-1,1}){
        const FVector Edge=Shoulder+Across*(Sign*Width*.5);
        for(const FVector& End : {Base,Tip}){
            FVector Normal=FVector::CrossProduct(Rib-End,Edge-End).GetSafeNormal();
            if(Normal.Z<0)Normal=-Normal;
            Mesh.Col=Color*(Sign<0?.93f:1.f);
            Mesh.Face({End,Rib,Edge},Normal);
            Mesh.Col=Color*.70f;
            Mesh.Face({End,Rib,Edge},-Normal);
        }
    }
}

FLifeMesh Planter(){
    FLifeMesh Mesh;
    FRandomStream WoodRandom(24031);
    const FLinearColor Oak(.46f,.34f,.23f), Edge(.34f,.25f,.17f), Iron(.23f,.21f,.18f);
    Mesh.Col=FLinearColor(.13f,.10f,.074f);
    for(double X : {-48.,48.})for(double Y : {-14.,14.}){
        Mesh.Box(FVector(X,Y,1.5),FVector(3.2,3.2,1.5));
    }
    Mesh.Box(FVector(0,0,28),FVector(52.5,17.5,25));
    Mesh.Col=FLinearColor(.21f,.17f,.12f);
    Mesh.Box(FVector(0,0,53),FVector(51.5,17,2.2));

    for(double Side : {-1.,1.}){
        for(int32 Slat=0;Slat<16;++Slat){
            const float Grain=WoodRandom.FRandRange(.77f,1.14f);
            Mesh.Col=Oak*Grain;
            Mesh.Box(FVector(-50.+Slat*(100./15.),Side*18.6,30),FVector(3.17,1.15,27));
        }
        for(int32 Slat=0;Slat<5;++Slat){
            Mesh.Col=Oak*WoodRandom.FRandRange(.79f,1.12f);
            Mesh.Box(FVector(Side*53.2,-14.4+Slat*7.2,30),FVector(1.25,3.42,27));
        }
        Mesh.Col=Edge;
        Mesh.Box(FVector(0,Side*18.2,57.8),FVector(55,1.8,2.2));
        Mesh.Box(FVector(Side*53.2,0,57.8),FVector(1.8,16.4,2.2));
        Mesh.Box(FVector(0,Side*17.9,4.4),FVector(54,1.9,1.5));
        Mesh.Col=Iron;
        for(double X : {-48.7,48.7}){
            Mesh.Box(FVector(X,Side*19.85,30),FVector(.74,.15,23));
            for(double Z : {11.,48.})Mesh.Box(FVector(X,Side*20.02,Z),FVector(1.12,.32,1.12));
        }
    }

    FRandomStream PlantRandom(5831);
    const FLinearColor Mature(.24f,.36f,.145f), NewGrowth(.43f,.53f,.23f);
    for(int32 Stem=0;Stem<7;++Stem){
        const FVector Root(-39.+Stem*13.,PlantRandom.FRandRange(-4.f,4.f),54.5);
        const FVector Crown=Root+FVector(PlantRandom.FRandRange(-1.7f,1.7f),
            PlantRandom.FRandRange(-1.7f,1.7f),PlantRandom.FRandRange(24.f,44.f));
        Mesh.Col=FLinearColor(.28f,.27f,.125f);
        Mesh.Tube(Root,Crown,.55,5);
        const double StartAngle=PlantRandom.FRandRange(0.f,2.f*PI);
        for(int32 Leaf=0;Leaf<16;++Leaf){
            const double Height=PlantRandom.FRandRange(.30f,1.f);
            const double Angle=StartAngle+Leaf*2.399963;
            const FVector At=FMath::Lerp(Root,Crown,Height);
            const FVector Base=At+FVector(FMath::Cos(Angle)*2.8,FMath::Sin(Angle)*2.8,2.);
            const FLinearColor Color=FMath::Lerp(Mature,NewGrowth,PlantRandom.FRandRange(0.f,.78f));
            Mesh.Col=Color*.72f;
            Mesh.Tube(At,Base,.28,4);
            const double Length=PlantRandom.FRandRange(6.5f,11.f);
            const double Width=PlantRandom.FRandRange(3.9f,6.2f);
            const double Rise=PlantRandom.FRandRange(-2.f,11.f);
            PlanterLeaf(Mesh,Base,Angle,Length,Width,Rise,Color);
        }
    }
    return Mesh;
}
bool IsFood(const FString& C){return C==TEXT("cafe")||C==TEXT("restaurant")||C==TEXT("bar")||C==TEXT("pub")||C==TEXT("fast_food")||C==TEXT("ice_cream")||C==TEXT("bakery")||C==TEXT("pastry")||C==TEXT("biergarten")||C==TEXT("confectionery");}
bool IsSouvenir(const FString& C){return C==TEXT("gift")||C==TEXT("souvenir")||C==TEXT("clothes")||C==TEXT("books")||C==TEXT("art")||C==TEXT("newsagent")||C==TEXT("variety_store")||C==TEXT("toys")||C==TEXT("bag")||C==TEXT("jewelry")||C==TEXT("shoes")||C==TEXT("tobacco")||C==TEXT("kiosk");}
uint32 Hash(const FString& S){return GetTypeHash(S);}
}

// Snap to the walkable GIS ground with the same query the pedestrian crowd uses (ECC_Pawn, upward-facing hit).
bool AParisStreetLife::SnapToGround(FVector& P,double Up,double Down) const {
    if(!GetWorld())return false;FHitResult Hit;FCollisionQueryParams Params;Params.AddIgnoredActor(this);
    // Ignore capsule obstacles (urns, bollards): only real ground and steps carry people and furniture.
    if(GetWorld()->LineTraceSingleByChannel(Hit,P+FVector(0,0,Up),P-FVector(0,0,Down),ECC_Pawn,Params)&&Hit.GetComponent()&&!Hit.GetComponent()->IsA<UCapsuleComponent>()&&Hit.Normal.Z>.7){P.Z=Hit.ImpactPoint.Z;return true;}
    if(Hit.GetComponent()&&Hit.GetComponent()->IsA<UCapsuleComponent>()){Params.AddIgnoredComponent(Hit.GetComponent());if(GetWorld()->LineTraceSingleByChannel(Hit,P+FVector(0,0,Up),P-FVector(0,0,Down),ECC_Pawn,Params)&&Hit.Normal.Z>.7&&!(Hit.GetComponent()&&Hit.GetComponent()->IsA<UCapsuleComponent>())){P.Z=Hit.ImpactPoint.Z;return true;}}
    return false;
}
AParisStreetLife::AParisStreetLife(){
    RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("StreetLifeRoot"));
    PrimaryActorTick.bCanEverTick=true;PrimaryActorTick.TickInterval=0.f;
}
UHierarchicalInstancedStaticMeshComponent* AParisStreetLife::AddPrototype(const FName& Key,UStaticMesh* Mesh,double CullCm){
    if(!Mesh)return nullptr;auto C=NewObject<UHierarchicalInstancedStaticMeshComponent>(this);C->SetupAttachment(RootComponent);C->SetStaticMesh(Mesh);
    C->SetCollisionEnabled(ECollisionEnabled::NoCollision);C->SetCanEverAffectNavigation(false);C->SetGenerateOverlapEvents(false);C->SetCullDistances(0,CullCm);
    C->SetCastShadow(!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoShadows")));C->ComponentTags.Add(TEXT("ParisStreetLife"));C->ComponentTags.Add(Key);
    C->RegisterComponent();AddInstanceComponent(C);Parts.Add(Key,C);return C;
}
bool AParisStreetLife::Initialize(AParisTwinScene* InScene,const TSharedPtr<FJsonObject>& Data){
    Scene=InScene;if(!Scene||!Data.IsValid())return false;
    auto Cloth=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisCloth.M_ParisCloth"));if(!Cloth)return false;
    // Storefront frames: the inferred canopy anchor on the facade and its yaw (X along the facade, +Y out to the street).
    TMap<FString,FTransform> Fronts;
    {FString Text;TSharedPtr<FJsonObject> Lux;
     if(FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("Data/paris-luxury.json")))&&FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Lux)&&Lux.IsValid())
        for(const auto& V:Array(Lux,TEXT("records"))){auto J=V->AsObject();if(String(J,TEXT("kind"))!=TEXT("canopy"))continue;const auto& P=Array(J,TEXT("anchor_cm"));if(P.Num()!=3)continue;
            Fronts.Add(String(J,TEXT("source_id")),FTransform(FRotator(0,Number(J,TEXT("yaw_degrees")),0),FVector(P[0]->AsNumber(),P[1]->AsNumber(),P[2]->AsNumber())));}}
    if(Fronts.IsEmpty())return false;
    const FLinearColor AwningColors[4]={FLinearColor(.50f,.04f,.03f),FLinearColor(.04f,.20f,.10f),FLinearColor(.03f,.06f,.22f),FLinearColor(.30f,.03f,.07f)};
    TArray<FTransform> Tables,ChairsA,ChairsB,Awnings[4],Arms,Spinners,Racks,BoardsW,BoardsR,Planters;
    for(const auto& V:Array(Data,TEXT("pick_features"))){
        auto F=V->AsObject();if(!F.IsValid()||String(F,TEXT("kind"))!=TEXT("business"))continue;const FString ID=String(F,TEXT("id"));const FTransform* Front=Fronts.Find(ID);if(!Front)continue;
        const auto P=Object(F,TEXT("properties"));const FString Cat=String(P,TEXT("category"));const bool Terrace=String(P,TEXT("outdoor_seating_tag"))==TEXT("yes");const uint32 H=Hash(ID);
        const FRotator Yaw=Front->Rotator();const FVector Along=Yaw.RotateVector(FVector(1,0,0)),Out=Yaw.RotateVector(FVector(0,1,0)),O=Front->GetLocation();
        auto At=[&](double X,double Y,double YawExtra=0,FVector Scale=FVector(1)){FVector P=O+Along*X+Out*Y;if(X!=0||Y!=0)SnapToGround(P,40,250);return FTransform(Yaw+FRotator(0,YawExtra,0),P,Scale);};
        if(Terrace&&IsFood(Cat)){
            TerraceCount++;TerraceFronts.Add(*Front);const int32 Ac=H%4;Awnings[Ac].Add(At(0,0,0,FVector(6.,1.,1.)));for(double X:{-290.,0.,290.})Arms.Add(At(X,0));
            for(int32 Row=0;Row<2;Row++)for(int32 K=-2;K<=2;K++){
                const double X=K*112+(Row?40:0),Y=105+Row*95;Tables.Add(At(X,Y));TableCount++;
                for(int32 S:{-1,1}){const FTransform Chair=At(X+S*30,Y-34);((H+K+Row+S)&1?ChairsA:ChairsB).Add(Chair);ChairCount++;
                    const uint32 Seat=HashCombine(H,GetTypeHash(Row*31+K*7+S));if(Seat%100u<(Row?30u:42u)){Seats.Add(FTransform(Yaw+FRotator(0,90,0),Chair.GetLocation()));SeatVariant.Add(Seat/100);}}
            }
            for(int32 K=0;K<3;K++){const double Y=330+K*55;AddTourist(O+Along*(-700+K*90)+Out*Y,O+Along*(700-K*80)+Out*Y,0,H+11*K,true);}
            Planters.Add(At(-370,140,90));Planters.Add(At(370,140,-90));((H>>3)&1?BoardsW:BoardsR).Add(At(420,250,20));
        }
        else if(IsFood(Cat)){((H>>3)&1?BoardsW:BoardsR).Add(At(-170+(H%60),125,(H%2)?15.:-15.));ShopDisplayCount++;}
        else if(IsSouvenir(Cat)){ShopFronts.Add(*Front);for(int32 K=0;K<2+int32(H%2);K++){const double X=-140+K*120+double(H%40);AddTourist(O+Along*X+Out*(105+(K%2)*45),O+Along*X+Out*(105+(K%2)*45),FRotator(0,Yaw.Yaw-90+(K%2?25:-20),0).Yaw,H+K,false);}Spinners.Add(At(115,62,double(H%90)));if(Cat!=TEXT("books")&&Cat!=TEXT("newsagent"))Racks.Add(At(-118,52));if(H%3==0)BoardsR.Add(At(0,150,10));ShopDisplayCount++;}
        else if(H%5<2){BoardsW.Add(At(-150,120,(H%2)?12.:-12.));ShopDisplayCount++;}
    }
    auto Fill=[&](const FName& Key,const FLifeMesh& M,const TArray<FTransform>& T,double Cull){if(T.IsEmpty())return;if(auto C=AddPrototype(Key,BuildStatic(this,M,Cloth),Cull))C->AddInstances(T,false,false,false);};
    Fill(TEXT("bistro_table"),BistroTable(),Tables,9000);Fill(TEXT("bistro_chair_a"),BistroChair(FLinearColor(.40f,.27f,.12f)),ChairsA,7000);Fill(TEXT("bistro_chair_b"),BistroChair(FLinearColor(.58f,.46f,.28f)),ChairsB,7000);
    for(int32 K=0;K<4;K++)Fill(FName(*FString::Printf(TEXT("terrace_awning_%d"),K)),Awning(AwningColors[K]),Awnings[K],20000);
    Fill(TEXT("terrace_awning_arm"),AwningArm(),Arms,9000);
    const FLifeMesh PlanterModel=Planter();
    Fill(TEXT("terrace_planter"),PlanterModel,Planters,9000);
    if(const auto PlanterPart=Parts.Find(TEXT("terrace_planter"))){
        UE_LOG(LogTemp,Display,TEXT("PARIS_TERRACE_PLANTERS_READY instances=%d triangles_per_model=%d"),
            (*PlanterPart)->GetInstanceCount(),PlanterModel.I.Num()/3);
    }
    Fill(TEXT("postcard_spinner"),PostcardSpinner(),Spinners,8000);Fill(TEXT("scarf_rack"),ScarfRack(),Racks,8000);
    Fill(TEXT("aboard_wood"),ABoard(FLinearColor(.22f,.12f,.05f)),BoardsW,7000);Fill(TEXT("aboard_red"),ABoard(FLinearColor(.55f,.03f,.03f)),BoardsR,7000);
    // Parvis Notre-Dame: tourists looking up at the west front and strolling across the square
    // (positions traced onto the GIS ground; anything landing on a roof or far below is rejected).
    {const double Ang=FMath::DegreesToRadians(26.98016352182363);const FVector Ax(FMath::Cos(Ang),FMath::Sin(Ang),0),Lat(-Ax.Y,Ax.X,0);const FVector West(13857.95,17129.73,-142.049);
     FRandomStream R(2026);int32 Placed=0;ParvisCount=0;
     for(int32 K=0;K<700&&Placed<260;K++){const double D=R.FRandRange(500.f,12000.f),L=R.FRandRange(-3200.f,3200.f);FVector P=West-Ax*D+Lat*L;FHitResult Hit;
        // Parvis ground is ~+50 cm (the front photo camera stands there); a hit far above means a roof or tree.
        P.Z=50; // square level; the real ground is traced when the tourist is first shown (collision streams in later)
        const bool Walk=R.FRand()<.45;FVector B=P;if(Walk){const FVector Dir=FRotator(0,R.FRandRange(0.f,360.f),0).Vector();B=P+Dir*R.FRandRange(600.f,1600.f);}
        const double Face=(Ax.Rotation().Yaw)+R.FRandRange(-35.f,35.f);AddTourist(P,B,Face,R.GetUnsignedInt(),Walk&&B!=P);Tourists.Last().Parvis=true;Placed++;ParvisCount++;}}
    // Seated customers: a pool of skinned Rocketbox avatars (MIT) moved to the nearest occupied chairs.
    {FString Text;TSharedPtr<FJsonObject> People;
     if(FParse::Param(FCommandLine::Get(),TEXT("ParisPhotoreal"))&&!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoPeople"))&&FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("Data/paris-people.json")))&&FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),People)&&People.IsValid()){
        TArray<TPair<USkeletalMesh*,TArray<UAnimSequence*>>> Avatars;
        for(const auto& V:Array(People,TEXT("avatars"))){auto J=V->AsObject();auto Clips=Object(J,TEXT("animations"));
            auto Mesh=LoadObject<USkeletalMesh>(nullptr,*String(J,TEXT("mesh")));auto Idle=LoadObject<UAnimSequence>(nullptr,*String(Clips,TEXT("idle")));auto Walk=LoadObject<UAnimSequence>(nullptr,*String(Clips,TEXT("walk")));auto Sit=LoadObject<UAnimSequence>(nullptr,*String(Clips,TEXT("sit")));
            if(Mesh&&Idle&&Walk&&Sit)Avatars.Add(TPair<USkeletalMesh*,TArray<UAnimSequence*>>(Mesh,TArray<UAnimSequence*>{Idle,Walk,Sit}));}
        if(!Avatars.IsEmpty()&&!Seats.IsEmpty()){
            for(int32& Vv:SeatVariant)Vv%=Avatars.Num();
            for(int32 I=0;I<FMath::Min(36,Seats.Num());I++){const auto& Av=Avatars[I%Avatars.Num()];
                auto M=NewObject<USkeletalMeshComponent>(this);M->SetupAttachment(RootComponent);M->SetSkeletalMeshAsset(Av.Key);M->SetCollisionEnabled(ECollisionEnabled::NoCollision);M->SetCanEverAffectNavigation(false);
                M->VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::OnlyTickPoseWhenRendered;M->bEnableUpdateRateOptimizations=true;M->SetCastShadow(!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoShadows")));
                M->SetAnimInstanceClass(UParisHumanAnimation::StaticClass());M->RegisterComponent();AddInstanceComponent(M);M->SetVisibility(false);
                Seated.Add(M);SlotSeat.Add(INDEX_NONE);SlotVariant.Add(I%Avatars.Num());}
            // Keep the avatar assets for re-dressing slots.
            for(int32 I=0;I<Seated.Num();I++){auto Anim=Cast<UParisHumanAnimation>(Seated[I]->GetAnimInstance());const auto& Av=Avatars[SlotVariant[I]];if(Anim){Anim->Idle=Av.Value[0];Anim->Walk=Av.Value[1];Anim->Sit=Av.Value[2];Anim->SpeedCm=0;Anim->SeatAlpha=1;}}
            // Seats only take slots whose avatar matches, so no re-dressing is needed at run time.
            for(int32 S=0;S<Seats.Num();S++)SeatVariant[S]=SeatVariant[S]%FMath::Min(Avatars.Num(),Seated.Num());
            for(auto& T:Tourists)T.Variant%=Avatars.Num();
            for(int32 I=0;I<FMath::Min(Avatars.Num()*6,Tourists.Num());I++){const auto& Av=Avatars[I%Avatars.Num()];
                auto M=NewObject<USkeletalMeshComponent>(this);M->SetupAttachment(RootComponent);M->SetSkeletalMeshAsset(Av.Key);M->SetCollisionEnabled(ECollisionEnabled::NoCollision);M->SetCanEverAffectNavigation(false);
                M->VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::OnlyTickPoseWhenRendered;M->bEnableUpdateRateOptimizations=true;M->SetCastShadow(!FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoShadows")));
                M->SetAnimInstanceClass(UParisHumanAnimation::StaticClass());M->RegisterComponent();AddInstanceComponent(M);M->SetVisibility(false);
                if(auto Anim=Cast<UParisHumanAnimation>(M->GetAnimInstance())){Anim->Idle=Av.Value[0];Anim->Walk=Av.Value[1];Anim->Sit=Av.Value[2];Anim->SeatAlpha=0;Anim->PersonIndex=1000+I;}
                Walkers.Add(M);WalkerTourist.Add(INDEX_NONE);WalkerVariant.Add(I%Avatars.Num());}
        }
     }}
    // Capture aid: -ParisTwinTerraceView=N frames the N-th terrace nearest the island centre with the street camera.
    {int32 View=-1;const bool ShopView=FParse::Value(FCommandLine::Get(),TEXT("ParisTwinShopView="),View);if(ShopView)TerraceFronts=ShopFronts;
     if((ShopView||FParse::Value(FCommandLine::Get(),TEXT("ParisTwinTerraceView="),View))&&TerraceFronts.Num()){
        TerraceFronts.Sort([&](const FTransform& A,const FTransform& B){return FVector::DistSquared2D(A.GetLocation(),Scene->QualityCentre)<FVector::DistSquared2D(B.GetLocation(),Scene->QualityCentre);});
        const FTransform& T=TerraceFronts[FMath::Clamp(View,0,TerraceFronts.Num()-1)];const FVector Along=T.Rotator().RotateVector(FVector(1,0,0)),Out=T.Rotator().RotateVector(FVector(0,1,0));
        const FVector Eye=T.GetLocation()+Out*900-Along*420+FVector(0,0,175),Look=T.GetLocation()+Out*150+FVector(0,0,120);
        for(TActorIterator<ACameraActor> It(GetWorld());It;++It)if(It->GetFName()==FName(TEXT("Camera_Paris_Street"))){It->SetActorLocationAndRotation(Eye,(Look-Eye).Rotation());break;}}}
    UE_LOG(LogTemp,Display,TEXT("PARIS_STREET_LIFE_READY terraces=%d tables=%d chairs=%d seats=%d shop_displays=%d seated_pool=%d tourists=%d parvis=%d tourist_pool=%d"),TerraceCount,TableCount,ChairCount,Seats.Num(),ShopDisplayCount,Seated.Num(),Tourists.Num(),ParvisCount,Walkers.Num());
    return true;
}
void AParisStreetLife::AddTourist(const FVector& A,const FVector& B,double Yaw,uint32 Seed,bool Walk){
    FParisTourist T;T.A=A;T.B=B;T.Yaw=Yaw;T.Walk=Walk&&FVector::Dist2D(A,B)>100;T.Variant=int32(Seed%997);T.Speed=95+double(Seed%40);T.Phase=double(Seed%1000)/1000.;Tourists.Add(T);
}
void AParisStreetLife::Tick(float DeltaSeconds){
    Super::Tick(DeltaSeconds);Clock+=DeltaSeconds;
    if(!bPropsSnapped&&Clock>3){bPropsSnapped=true;int32 Moved=0;
        for(auto& Pair:Parts){if(Pair.Key.ToString().StartsWith(TEXT("terrace_awning")))continue;auto C=Pair.Value;TArray<FTransform> Ts;Ts.SetNum(C->GetInstanceCount());
            for(int32 I=0;I<Ts.Num();I++){C->GetInstanceTransform(I,Ts[I],true);FVector P=Ts[I].GetLocation();if(SnapToGround(P,40,250)&&FMath::Abs(P.Z-Ts[I].GetLocation().Z)>1){Ts[I].SetLocation(P);Moved++;}}
            if(Ts.Num())C->BatchUpdateInstancesTransforms(0,Ts,true,true,true);}
        UE_LOG(LogTemp,Display,TEXT("PARIS_STREET_LIFE_GROUNDED moved=%d"),Moved);}Remaining-=DeltaSeconds;if(Remaining<=0){Remaining=.5;UpdateSeated();UpdateTourists(true);}
    UpdateTourists(false);
}
void AParisStreetLife::UpdateTourists(bool Reassign){
    if(Walkers.IsEmpty())return;
    auto Pose=[&](const FParisTourist& T,FVector& P,double& Yaw,double& Speed){
        if(!T.Walk){P=T.A;Yaw=T.Yaw;Speed=0;return;}
        const double Len=FVector::Dist(T.A,T.B),Cycle=2*Len/T.Speed;double U=FMath::Fmod(Clock/Cycle+T.Phase,1.);
        // Walk out, pause, walk back: a short idle at each end reads as browsing rather than pacing.
        const bool Back=U>.5;double S=Back?(U-.5)*2:U*2;S=FMath::Clamp((S-.08)/.84,0.,1.);
        P=Back?FMath::Lerp(T.B,T.A,S):FMath::Lerp(T.A,T.B,S);const FVector Dir=(Back?T.A-T.B:T.B-T.A);Yaw=Dir.Rotation().Yaw;Speed=(S>0&&S<1)?T.Speed:0;};
    if(Reassign){
        auto PC=GetWorld()?GetWorld()->GetFirstPlayerController():nullptr;if(!PC||!PC->PlayerCameraManager)return;const FVector Eye=PC->PlayerCameraManager->GetCameraLocation();
        const bool Show=!IsHidden()&&(!Scene||Scene->DetailQuality>0);
        TArray<int32> Near;for(int32 T=0;T<Tourists.Num();T++)if(!Tourists[T].bInvalid&&FVector::DistSquared(Tourists[T].A,Eye)<9000.*9000.)Near.Add(T);
        Near.Sort([&](int32 A,int32 B){return FVector::DistSquared(Tourists[A].A,Eye)<FVector::DistSquared(Tourists[B].A,Eye);});
        TArray<bool> Taken;Taken.Init(false,Walkers.Num());
        for(int32 T:Near){for(int32 I=0;I<Walkers.Num();I++)if(!Taken[I]&&WalkerVariant[I]==Tourists[T].Variant){Taken[I]=true;WalkerTourist[I]=T;if(!Tourists[T].bSnapped){auto& Tt=Tourists[T];Tt.bSnapped=true;const double Z0=Tt.A.Z;if(!SnapToGround(Tt.A,Tt.Parvis?300.:40.,900)||FMath::Abs(Tt.A.Z-Z0)>600){Tt.bInvalid=true;Taken[I]=false;WalkerTourist[I]=INDEX_NONE;break;}if(Tt.Walk&&(!SnapToGround(Tt.B,Tt.Parvis?300.:40.,900)||FMath::Abs(Tt.B.Z-Tt.A.Z)>60)){Tt.B=Tt.A;Tt.Walk=false;}else if(!Tt.Walk)Tt.B=Tt.A;}break;}}
        for(int32 I=0;I<Walkers.Num();I++){const bool On=Show&&Taken[I];if(!On)WalkerTourist[I]=INDEX_NONE;Walkers[I]->SetVisibility(On);Walkers[I]->SetComponentTickEnabled(On);}
    }
    for(int32 I=0;I<Walkers.Num();I++){const int32 T=WalkerTourist[I];if(T==INDEX_NONE)continue;FVector P;double Yaw,Speed;Pose(Tourists[T],P,Yaw,Speed);
        Walkers[I]->SetWorldLocationAndRotation(P,FRotator(0,Yaw,0));if(auto Anim=Cast<UParisHumanAnimation>(Walkers[I]->GetAnimInstance()))Anim->SpeedCm=Speed;}
}
void AParisStreetLife::UpdateSeated(){
    if(Seated.IsEmpty())return;auto PC=GetWorld()?GetWorld()->GetFirstPlayerController():nullptr;if(!PC||!PC->PlayerCameraManager)return;
    const FVector Eye=PC->PlayerCameraManager->GetCameraLocation();const bool Show=!IsHidden()&&(!Scene||Scene->DetailQuality>0);
    // Nearest occupied chairs within 55 m, then fill the slots whose avatar matches each seat.
    TArray<int32> Near;for(int32 S=0;S<Seats.Num();S++)if(FVector::DistSquared(Seats[S].GetLocation(),Eye)<5500.*5500.)Near.Add(S);
    Near.Sort([&](int32 A,int32 B){return FVector::DistSquared(Seats[A].GetLocation(),Eye)<FVector::DistSquared(Seats[B].GetLocation(),Eye);});
    TSet<int32> Wanted;TArray<bool> Taken;Taken.Init(false,Seated.Num());
    for(int32 S:Near){for(int32 I=0;I<Seated.Num();I++)if(!Taken[I]&&SlotVariant[I]==SeatVariant[S]){Taken[I]=true;Wanted.Add(S);if(SlotSeat[I]!=S){SlotSeat[I]=S;if(!SeatSnapped.Contains(S)){FVector P=Seats[S].GetLocation();if(SnapToGround(P,40,250))Seats[S].SetLocation(P);SeatSnapped.Add(S);}Seated[I]->SetWorldTransform(Seats[S]);}break;}}
    SeatedVisible=0;for(int32 I=0;I<Seated.Num();I++){const bool On=Show&&Taken[I];if(!On)SlotSeat[I]=INDEX_NONE;Seated[I]->SetVisibility(On);Seated[I]->SetComponentTickEnabled(On);SeatedVisible+=On;}
}
