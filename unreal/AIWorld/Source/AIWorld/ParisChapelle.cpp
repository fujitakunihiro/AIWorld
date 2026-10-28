#include "ParisChapelle.h"
#include "ParisDigitalTwin.h"
#include "ProceduralMeshComponent.h"
#include "KismetProceduralMeshLibrary.h"
#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "GameFramework/PlayerController.h"
#include "Engine/World.h"
#include "Materials/MaterialInterface.h"
#include "WorldProtocol.h"
using namespace AIWorld;
namespace {
struct ChapelMesh {
    TArray<FVector> V,N;TArray<int32> I;TArray<FVector2D> UV;TArray<FProcMeshTangent> T;TArray<FLinearColor> C;
    void Face(const TArray<FVector>& Points,FVector Normal,const TArray<FVector2D>& Coords={}){
        if(Points.Num()<3)return;Normal.Normalize();int32 Base=V.Num();
        for(int32 J=0;J<Points.Num();J++){V.Add(Points[J]);N.Add(Normal);UV.Add(Coords.IsValidIndex(J)?Coords[J]:FVector2D::ZeroVector);T.Add(FProcMeshTangent(1,0,0));C.Add(FLinearColor::White);}
        const bool Reverse=FVector::DotProduct(FVector::CrossProduct(Points[1]-Points[0],Points[2]-Points[0]),Normal)>0;
        for(int32 J=1;J<Points.Num()-1;J++){I.Add(Base);I.Add(Base+(Reverse?J+1:J));I.Add(Base+(Reverse?J:J+1));}
    }
    void Box(FVector Center,FVector Half){TArray<FVector> V0,N0;TArray<int32> I0;TArray<FVector2D> U0;TArray<FProcMeshTangent> T0;UKismetProceduralMeshLibrary::GenerateBoxMesh(Half,V0,I0,N0,U0,T0);int32 Base=V.Num();for(auto P:V0)V.Add(P+Center);for(auto X:I0)I.Add(Base+X);N.Append(N0);UV.Append(U0);T.Append(T0);for(int32 J=0;J<V0.Num();J++)C.Add(FLinearColor::White);}
    void Tube(FVector A,FVector B,double Radius,int32 Sides=8){
        FVector D=(B-A).GetSafeNormal();if(D.IsNearlyZero())return;FVector U=FVector::CrossProduct(D,FMath::Abs(D.Z)<.8?FVector::UpVector:FVector::RightVector).GetSafeNormal(),W=FVector::CrossProduct(D,U).GetSafeNormal();
        for(int32 J=0;J<Sides;J++){double T0=2*PI*J/Sides,T1=2*PI*(J+1)/Sides;FVector R0=U*FMath::Cos(T0)+W*FMath::Sin(T0),R1=U*FMath::Cos(T1)+W*FMath::Sin(T1);Face({A+R0*Radius,A+R1*Radius,B+R1*Radius,B+R0*Radius},(R0+R1).GetSafeNormal());}
    }
    void Cone(double X,double Y,double Z0,double Z1,double R0,double R1,int32 Sides=8){
        for(int32 J=0;J<Sides;J++){double A=2*PI*J/Sides,B=2*PI*(J+1)/Sides;FVector P0(X+R0*FMath::Cos(A),Y+R0*FMath::Sin(A),Z0),P1(X+R0*FMath::Cos(B),Y+R0*FMath::Sin(B),Z0),P2(X+R1*FMath::Cos(B),Y+R1*FMath::Sin(B),Z1),P3(X+R1*FMath::Cos(A),Y+R1*FMath::Sin(A),Z1);FVector N0(FMath::Cos((A+B)/2),FMath::Sin((A+B)/2),(R0-R1)/(Z1-Z0));Face({P0,P1,P2,P3},N0);}
    }
    void Apply(UProceduralMeshComponent* M,UMaterialInterface* Mat){M->CreateMeshSection_LinearColor(0,V,I,N,UV,C,T,false);M->SetMaterial(0,Mat);M->SetCollisionEnabled(ECollisionEnabled::NoCollision);M->SetCanEverAffectNavigation(false);}
};
// Graceful pointed arch, as an inferred stone profile; units are cm.
FVector ArchPoint(double X,double Y,double Base,double Width,double Rise,double T){const double H=Width*.5;const double XX=(2*T-1)*H;const double Height=Rise*(1-FMath::Pow(FMath::Abs(XX)/H,1.7));return FVector(X+XX,Y,Base+Height);}
}
AParisChapelleDetail::AParisChapelleDetail(){
    RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("ChapelleRoot"));
    Stone=CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("ChapelleStone"));Stone->SetupAttachment(RootComponent);
    Glass=CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("ChapelleStainedGlass"));Glass->SetupAttachment(RootComponent);Glass->SetCastShadow(false);
    Roof=CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("ChapelleRoof"));Roof->SetupAttachment(RootComponent);
    Camera=CreateDefaultSubobject<UCameraComponent>(TEXT("ChapelleCamera"));Camera->SetupAttachment(RootComponent);FVector Offset(8500,-7200,6300);Camera->SetRelativeLocation(Offset);Camera->SetRelativeRotation((FVector(0,0,3500)-Offset).Rotation());Camera->FieldOfView=75;
}
bool AParisChapelleDetail::Initialize(AParisTwinScene* InScene){
    Scene=InScene;if(!Scene)return false;auto Feature=Scene->SourceFeatureByID(TEXT("osm/relation/3344870"));if(!Feature)return false;
    UMaterialInterface* StoneMat=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_Paris_Limestone.M_Paris_Limestone"));
    UMaterialInterface* RoofMat=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_Paris_Roof_Slate.M_Paris_Roof_Slate"));
    UMaterialInterface* GlassMat=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/ParisPhotoreal/SainteChapelle/M_SainteChapelleWindows.M_SainteChapelleWindows"));
    if(!StoneMat||!RoofMat||!GlassMat)return false;
    // The frame is computed once from the OSM footprint minimum rectangle. The
    // terrain anchor uses the existing landmark. These do not move GIS collision.
    const auto& Rings=Array(Feature,TEXT("polygons_cm"));if(Rings.IsEmpty())return false;
    const auto& Polygon=Rings[0]->AsArray();if(Polygon.IsEmpty())return false;const auto& Ring=Polygon[0]->AsArray();if(Ring.IsEmpty())return false;const auto& Point=Ring[0]->AsArray();if(Point.Num()<2||FMath::Abs(Point[0]->AsNumber()+13798.841)>1||FMath::Abs(Point[1]->AsNumber()+7883.714)>1)return false;
    FVector Ground(-15173.6394325,-7772.3607886,-229.779);const FVector Axis(-.86824143464,-.49614192644,0);
    SetActorLocationAndRotation(Ground,Axis.Rotation());
    ChapelMesh S,G,R;
    // Approximate nave window faces; source photograph is from the interior,
    // reused for appearance only, not a claim of exact historical panels.
    for(int32 Sign:{-1,1}){
        const double Y=Sign*690.;
        for(double X:{-1080.,-320.,440.,1200.}){
            const double Width=410,Bottom=780,Spring=1840,Rise=430;TArray<FVector> P;TArray<FVector2D> U;
            P.Add(FVector(X-Width/2,Y,Bottom));P.Add(FVector(X+Width/2,Y,Bottom));
            for(int32 I=16;I>=0;I--)P.Add(ArchPoint(X,Y,Spring,Width,Rise,double(I)/16));
            for(const auto& Pt:P)U.Add(FVector2D(.53+(Pt.X-(X-Width/2))/Width*.14,.86-(Pt.Z-Bottom)/(Spring+Rise-Bottom)*.64));
            G.Face(P,FVector(0,Sign,0),U);WindowCount++;
            const double Outer=Y+Sign*12;
            for(double Offset:{-205.,-103.,0.,103.,205.})S.Tube(FVector(X+Offset,Outer,Bottom),FVector(X+Offset,Outer,Spring),Offset==0?13:10,8);
            S.Tube(FVector(X-205,Outer,Bottom),FVector(X+205,Outer,Bottom),14,8);
            S.Tube(FVector(X-205,Outer,Spring),FVector(X+205,Outer,Spring),8,8);
            for(int32 K=0;K<16;K++)S.Tube(ArchPoint(X,Outer,Spring,Width,Rise,K/16.),ArchPoint(X,Outer,Spring,Width,Rise,(K+1)/16.),15,8);
            for(int32 K=0;K<12;K++){double A=2*PI*K/12,B=2*PI*(K+1)/12;S.Tube(FVector(X+70*FMath::Cos(A),Outer,1980+70*FMath::Sin(A)),FVector(X+70*FMath::Cos(B),Outer,1980+70*FMath::Sin(B)),9,8);}
        }
        for(double X:{-1460.,-700.,60.,820.,1580.}){
            const double Y0=Sign*760;S.Box(FVector(X,Y0,1160),FVector(47,100,1160));S.Box(FVector(X,Sign*825,720),FVector(74,80,720));S.Box(FVector(X,Y0,2350),FVector(75,120,35));
            S.Cone(X,Y0,2385,2780,90,15,4);S.Cone(X,Y0,2780,2910,15,0,4);ButtressCount++;
        }
        S.Box(FVector(0,Sign*710,710),FVector(1660,35,35));S.Box(FVector(0,Sign*710,2310),FVector(1660,35,30));
    }
    // Seven-sided apse; panels and tracery are fitted to an inferred local
    // envelope, while their dimensions follow the published window dossier.
    for(int32 Bay=0;Bay<7;Bay++){
        const double Angle=PI*.5+PI*(Bay+.5)/7.;const FVector Radial(FMath::Cos(Angle),FMath::Sin(Angle),0),Tangent(-Radial.Y,Radial.X,0);const FVector Centre=FVector(-1280,0,0)+Radial*745.;
        const double Width=190,Bottom=780,Spring=1835,Rise=290;TArray<FVector> Points;TArray<FVector2D> UV;
        auto Place=[&](double X,double Z,double Out){return Centre+Tangent*X+Radial*Out+FVector(0,0,Z);};
        Points.Add(Place(-Width/2,Bottom,0));Points.Add(Place(Width/2,Bottom,0));
        for(int32 K=16;K>=0;K--){auto Q=ArchPoint(0,0,Spring,Width,Rise,double(K)/16);Points.Add(Place(Q.X,Q.Z,0));}
        for(const auto& Q:Points){double X=FVector::DotProduct(Q-Centre,Tangent);UV.Add(FVector2D(.53+(X+Width/2)/Width*.14,.86-(Q.Z-Bottom)/(Spring+Rise-Bottom)*.64));}
        G.Face(Points,Radial,UV);WindowCount++;
        for(double Offset:{-95.,0.,95.})S.Tube(Place(Offset,Bottom,12),Place(Offset,Spring,12),10,8);
        S.Tube(Place(-95,Bottom,12),Place(95,Bottom,12),12,8);
        for(int32 K=0;K<16;K++){auto A=ArchPoint(0,0,Spring,Width,Rise,K/16.),B=ArchPoint(0,0,Spring,Width,Rise,(K+1)/16.);S.Tube(Place(A.X,A.Z,12),Place(B.X,B.Z,12),12,8);}
    }
    for(int32 B=0;B<=7;B++){double A=PI*.5+PI*B/7.;double X=-1280+785*FMath::Cos(A),Y=785*FMath::Sin(A);S.Box(FVector(X,Y,1160),FVector(35,35,1160));S.Cone(X,Y,2320,2780,56,0,6);ButtressCount++;}
    // West rose and real 3-D tracery, placed over the retained GIS mass.
    const double Front=2080,RoseZ=1770,RoseR=375;TArray<FVector> P;TArray<FVector2D> U;
    for(int32 K=0;K<48;K++){double A=2*PI*K/48;P.Add(FVector(Front,RoseR*FMath::Cos(A),RoseZ+RoseR*FMath::Sin(A)));U.Add(FVector2D(.53+.12*(.5+.5*FMath::Cos(A)),.29+.20*(.5-.5*FMath::Sin(A))));}
    G.Face(P,FVector(1,0,0),U);
    for(int32 K=0;K<48;K++){double A=2*PI*K/48,B=2*PI*(K+1)/48;S.Tube(FVector(Front+12,RoseR*FMath::Cos(A),RoseZ+RoseR*FMath::Sin(A)),FVector(Front+12,RoseR*FMath::Cos(B),RoseZ+RoseR*FMath::Sin(B)),22,8);}
    for(int32 K=0;K<16;K++){double A=2*PI*K/16;S.Tube(FVector(Front+15,0,RoseZ),FVector(Front+15,RoseR*FMath::Cos(A),RoseZ+RoseR*FMath::Sin(A)),8,8);}
    for(double Y:{-490.,490.}){S.Box(FVector(Front+35,Y,1100),FVector(65,65,1100));S.Cone(Front+35,Y,2200,2800,80,10,4);}
    // A steep slate roof and the iconic 75 m spire. The detailed roof profile
    // and sculpture are inferred; source gutter and OSM collision stay intact.
    for(int32 Side:{-1,1}){R.Face({FVector(-1800,0,3310),FVector(1730,0,3310),FVector(1730,Side*660,2340),FVector(-1800,Side*660,2340)},FVector(0,Side*.83,.57));}
    S.Face({FVector(1730,-660,2340),FVector(1730,660,2340),FVector(1730,0,3310)},FVector(1,0,0));
    S.Face({FVector(-1800,660,2340),FVector(-1800,-660,2340),FVector(-1800,0,3310)},FVector(-1,0,0));
    S.Cone(0,0,3000,3600,250,230,8);S.Cone(0,0,3600,4240,230,180,8);R.Cone(0,0,4240,7250,190,8,8);S.Cone(0,0,7250,7500,25,0,8);
    for(int32 J=0;J<8;J++){double A=2*PI*J/8;double X=235*FMath::Cos(A),Y=235*FMath::Sin(A);S.Cone(X,Y,3470,4140,38,20,6);S.Cone(X,Y,4140,4390,25,0,6);S.Tube(FVector(X,Y,3480),FVector(X,Y,4180),12,6);}
    for(double Z:{3400.,3700.,4050.})S.Cone(0,0,Z,Z+30,265,265,8);
    for(auto& Color:R.C)Color=FLinearColor(FColor::FromHex(TEXT("596679")));
    SpireHeightCm=7500;S.Apply(Stone,StoneMat);G.Apply(Glass,GlassMat);R.Apply(Roof,RoofMat);bReady=true;Sync();return true;
}
void AParisChapelleDetail::Sync(){if(Scene)SetActorHiddenInGame(!bReady||Scene->DetailQuality==0||Scene->bFootprints||Scene->bLevels||Scene->bIssues||!Scene->bDetailedSurfaces);}
void AParisChapelleDetail::ActivateView(APlayerController* PC){if(PC){PC->SetViewTarget(this);if(PC->PlayerCameraManager)PC->PlayerCameraManager->SetGameCameraCutThisFrame();}}
