#include "ParisChapelle.h"
#include "ParisDigitalTwin.h"
#include "ProceduralMeshComponent.h"
#include "KismetProceduralMeshLibrary.h"
#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "GameFramework/PlayerController.h"
#include "Engine/World.h"
#include "Components/PointLightComponent.h"
#include "Engine/PostProcessVolume.h"
#include "EngineUtils.h"
#include "Engine/SkyLight.h"
#include "Components/SkyLightComponent.h"
#include "Engine/DirectionalLight.h"
#include "Components/DirectionalLightComponent.h"
#include "Engine/ExponentialHeightFog.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Materials/MaterialInterface.h"
#include "WorldProtocol.h"
using namespace AIWorld;
namespace {
struct ChapelMesh {
    TArray<FVector> V,N;TArray<int32> I;TArray<FVector2D> UV;TArray<FProcMeshTangent> T;TArray<FLinearColor> C;FLinearColor Col=FLinearColor::White;
    void Face(const TArray<FVector>& Points,FVector Normal,const TArray<FVector2D>& Coords={}){
        if(Points.Num()<3)return;Normal.Normalize();int32 Base=V.Num();
        for(int32 J=0;J<Points.Num();J++){V.Add(Points[J]);N.Add(Normal);UV.Add(Coords.IsValidIndex(J)?Coords[J]:FVector2D::ZeroVector);T.Add(FProcMeshTangent(1,0,0));C.Add(Col);}
        const bool Reverse=FVector::DotProduct(FVector::CrossProduct(Points[1]-Points[0],Points[2]-Points[0]),Normal)>0;
        for(int32 J=1;J<Points.Num()-1;J++){I.Add(Base);I.Add(Base+(Reverse?J+1:J));I.Add(Base+(Reverse?J:J+1));}
    }
    void Box(FVector Center,FVector Half){TArray<FVector> V0,N0;TArray<int32> I0;TArray<FVector2D> U0;TArray<FProcMeshTangent> T0;UKismetProceduralMeshLibrary::GenerateBoxMesh(Half,V0,I0,N0,U0,T0);int32 Base=V.Num();for(auto P:V0)V.Add(P+Center);for(auto X:I0)I.Add(Base+X);N.Append(N0);UV.Append(U0);T.Append(T0);for(int32 J=0;J<V0.Num();J++)C.Add(Col);}
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

// ---- Upper-chapel interior (inferred reconstruction; proportions follow the
// published description: four bays, seven-sided apse, 15 windows, blue vault with
// gold stars, west rose). Local frame: X along the nave toward the west rose.
constexpr double InFloor=520,InWallY=600,InSpring=1700,InCrown=2300,InBayPitch=760,InApseX=-1460,InApseR=600;
constexpr double InPiers[5]={-1460,-700,60,820,1580};
double VaultA(double Y){return InSpring+(InCrown-InSpring)*(1-FMath::Pow(FMath::Min(FMath::Abs(Y)/InWallY,1.),1.7));}
double VaultB(double X,double Cx){return InSpring+(InCrown-InSpring)*(1-FMath::Pow(FMath::Min(FMath::Abs(X-Cx)/(InBayPitch*.5),1.),1.7));}
double Formeret(double U){return InSpring+(InCrown-InSpring)*(1-FMath::Pow(FMath::Abs(2*U-1),1.7));}
FVector2D RoseUV(double A){return FVector2D(.53+.12*(.5+.5*FMath::Cos(A)),.29+.20*(.5-.5*FMath::Sin(A)));}
void BuildInterior(ChapelMesh& S,ChapelMesh& G,ChapelMesh& Vt,int32& Windows){
    const FLinearColor Stone(.40f,.33f,.22f,.85f),Gold(.60f,.38f,.07f,.38f),Red(.30f,.025f,.025f,.5f),Blue(.015f,.03f,.22f,.5f),Dark(.04f,.025f,.02f,.7f);
    auto ApsePier=[](int32 B){const double A=PI*.5+PI*B/7.;return FVector(InApseX+InApseR*FMath::Cos(A),InApseR*FMath::Sin(A),0);};
    // Floor: alternating tiles, polished stone.
    for(int32 IX=0;IX<40;IX++)for(int32 IY=0;IY<16;IY++){
        const double X0=InPiers[0]+IX*76,X1=X0+76,Y0=-InWallY+IY*75,Y1=Y0+75;
        S.Col=((IX+IY)%2)?FLinearColor(.30f,.18f,.09f,.9f):FLinearColor(.10f,.06f,.04f,.9f);
        if(FMath::Abs(Y0+37.5)<80)S.Col=(IX%2)?FLinearColor(.30f,.025f,.025f,.8f):FLinearColor(.015f,.03f,.22f,.8f);
        S.Face({FVector(X0,Y0,InFloor),FVector(X1,Y0,InFloor),FVector(X1,Y1,InFloor),FVector(X0,Y1,InFloor)},FVector(0,0,1));
    }
    for(int32 B=0;B<7;B++)for(int32 Ring=0;Ring<3;Ring++){
        const FVector P0=ApsePier(B)-FVector(InApseX,0,0),P1=ApsePier(B+1)-FVector(InApseX,0,0);const double R0=Ring/3.,R1=(Ring+1)/3.;const FVector O(InApseX,0,InFloor);
        S.Col=((B+Ring)%2)?FLinearColor(.30f,.18f,.09f,.9f):FLinearColor(.10f,.06f,.04f,.9f);
        S.Face({O+P0*R0,O+P1*R0,O+P1*R1,O+P0*R1},FVector(0,0,1));
    }
    // Side walls behind the glass, dado arcature, backlit windows, piers and colonettes.
    for(int32 Sign:{-1,1}){
        S.Col=Stone;S.Face({FVector(InPiers[0],Sign*(InWallY+4),InFloor),FVector(InPiers[4],Sign*(InWallY+4),InFloor),FVector(InPiers[4],Sign*(InWallY+4),InCrown),FVector(InPiers[0],Sign*(InWallY+4),InCrown)},FVector(0,-Sign,0));
        for(int32 Bay=0;Bay<4;Bay++){
            const double Cx=InPiers[Bay]+InBayPitch*.5,Y=Sign*(InWallY-2);
            S.Col=Gold;
            for(double Off:{-250.,0.,250.}){
                for(int32 K=0;K<12;K++)S.Tube(ArchPoint(Cx+Off,Y,640,200,125,K/12.),ArchPoint(Cx+Off,Y,640,200,125,(K+1)/12.),4,6);
                for(double Leg:{-100.,100.})S.Tube(FVector(Cx+Off+Leg,Y,InFloor+10),FVector(Cx+Off+Leg,Y,640),4,6);
            }
            S.Tube(FVector(InPiers[Bay],Y,778),FVector(InPiers[Bay+1],Y,778),9,6);S.Tube(FVector(InPiers[Bay],Y,InFloor+8),FVector(InPiers[Bay+1],Y,InFloor+8),9,6);
            const double Half=345;TArray<FVector> P;TArray<FVector2D> U;P.Add(FVector(Cx-Half,Sign*InWallY,780));P.Add(FVector(Cx+Half,Sign*InWallY,780));
            for(int32 K=0;K<=16;K++){const double X=Cx+Half-2*Half*K/16.;P.Add(FVector(X,Sign*InWallY,VaultB(X,Cx)));}
            for(const auto& Pt:P)U.Add(FVector2D(.53+(Pt.X-(Cx-Half))/(2*Half)*.14,.86-(Pt.Z-780)/(InCrown-780)*.64));
            G.Face(P,FVector(0,-Sign,0),U);Windows++;
            S.Col=Gold;const double Yf=Sign*(InWallY-4);
            for(int32 K=0;K<16;K++){const double X0=Cx+Half-2*Half*K/16.,X1=Cx+Half-2*Half*(K+1)/16.;S.Tube(FVector(X0,Yf,VaultB(X0,Cx)),FVector(X1,Yf,VaultB(X1,Cx)),6,6);}
            for(double Off:{-Half,-115.,0.,115.,Half})S.Tube(FVector(Cx+Off,Yf,780),FVector(Cx+Off,Yf,VaultB(Cx+Off,Cx)),Off==0?5:4,6);
            for(double Z:{1100.,1450.,1800.,2100.})S.Tube(FVector(Cx-Half,Yf,Z),FVector(Cx+Half,Yf,Z),3.5,6);
            for(int32 K=0;K<4;K++){const double A=PI*.5*K+PI*.25;const FVector Ctr(Cx+50*FMath::Cos(A),Yf,1990+50*FMath::Sin(A));for(int32 J=0;J<10;J++){const double a0=2*PI*J/10,a1=2*PI*(J+1)/10;S.Tube(Ctr+FVector(40*FMath::Cos(a0),0,40*FMath::Sin(a0)),Ctr+FVector(40*FMath::Cos(a1),0,40*FMath::Sin(a1)),2.5,5);}}
        }
        for(int32 Pi=0;Pi<5;Pi++){
            const double X=InPiers[Pi],Y=Sign*(InWallY-12);int32 K=0;
            for(double Off:{-20.,0.,20.}){S.Col=(K%3==0)?Red:(K%3==1)?Gold:Blue;S.Tube(FVector(X+Off,Y,InFloor),FVector(X+Off,Y,InSpring),Off==0?11:8,8);K++;}
            S.Col=Gold;S.Box(FVector(X,Y,InSpring+12),FVector(34,24,12));S.Box(FVector(X,Y,InFloor+12),FVector(34,24,12));
        }
    }
    // Apse: seven faceted bays, each with its own lancet window and a fan vault.
    const FVector Crown(InApseX,0,InCrown);
    for(int32 B=0;B<7;B++){
        const FVector P0=ApsePier(B),P1=ApsePier(B+1),Mid=(P0+P1)*.5;const FVector Radial=FVector(Mid.X-InApseX,Mid.Y,0).GetSafeNormal(),Tangent(-Radial.Y,Radial.X,0);
        const double Chord=(P1-P0).Size();const FVector Out=Radial*4;
        S.Col=Stone;S.Face({P0+Out+FVector(0,0,InFloor),P1+Out+FVector(0,0,InFloor),P1+Out+FVector(0,0,InCrown),P0+Out+FVector(0,0,InCrown)},-Radial);
        const double Half=Chord*.5-26;TArray<FVector> P;TArray<FVector2D> U;
        auto Place=[&](double X,double Z){return FVector(Mid.X,Mid.Y,0)+Tangent*X+FVector(0,0,Z);};
        P.Add(Place(-Half,780));P.Add(Place(Half,780));
        for(int32 K=0;K<=16;K++){const double X=Half-2*Half*K/16.;P.Add(Place(X,Formeret(.5+X/Chord)));}
        for(const auto& Pt:P){const double X=FVector::DotProduct(Pt-FVector(Mid.X,Mid.Y,0),Tangent);U.Add(FVector2D(.53+(X+Half)/(2*Half)*.14,.86-(Pt.Z-780)/(InCrown-780)*.64));}
        G.Face(P,-Radial,U);Windows++;
        S.Col=Gold;
        for(int32 K=0;K<16;K++){const double X0=Half-2*Half*K/16.,X1=Half-2*Half*(K+1)/16.;S.Tube(Place(X0,Formeret(.5+X0/Chord))-Radial*4,Place(X1,Formeret(.5+X1/Chord))-Radial*4,5,6);}
        for(double Off:{-Half,0.,Half})S.Tube(Place(Off,780)-Radial*4,Place(Off,Formeret(.5+Off/Chord))-Radial*4,Off==0?4:5,6);
        for(double Z:{1100.,1500.,1900.})S.Tube(Place(-Half,Z)-Radial*4,Place(Half,Z)-Radial*4,3.5,6);
        for(int32 K=0;K<16;K++){
            const FVector Q0=FVector(P0.X,P0.Y,0)+(P1-P0)*(K/16.)+FVector(0,0,Formeret(K/16.)),Q1=FVector(P0.X,P0.Y,0)+(P1-P0)*((K+1)/16.)+FVector(0,0,Formeret((K+1)/16.));
            FVector N=FVector::CrossProduct(Q0-Crown,Q1-Crown);if(N.Z>0)N=-N;Vt.Face({Crown,Q0,Q1},N);
        }
    }
    S.Col=Gold;
    for(int32 B=0;B<=7;B++){
        const FVector P=ApsePier(B);S.Col=Gold;S.Tube(Crown-FVector(0,0,8),FVector(P.X,P.Y,InSpring),7,6);
        const FVector Radial(FMath::Cos(PI*.5+PI*B/7.),FMath::Sin(PI*.5+PI*B/7.),0),Side(-Radial.Y,Radial.X,0);int32 K=0;
        for(double Off:{-14.,14.}){S.Col=(K++%2)?Red:Blue;S.Tube(FVector(P.X,P.Y,InFloor)-Radial*14+Side*Off,FVector(P.X,P.Y,InSpring)-Radial*14+Side*Off,8,8);}
    }
    S.Col=Gold;S.Cone(InApseX,0,InCrown-36,InCrown-4,30,6,8);
    // Nave: groin-vaulted webs (ceiling = higher of the transverse and longitudinal pointed arches).
    for(int32 Bay=0;Bay<4;Bay++){
        const double Cx=InPiers[Bay]+InBayPitch*.5;
        for(int32 IX=0;IX<14;IX++)for(int32 IY=0;IY<24;IY++){
            const double X0=Cx-InBayPitch*.5+InBayPitch*IX/14.,X1=Cx-InBayPitch*.5+InBayPitch*(IX+1)/14.,Y0=-InWallY+2*InWallY*IY/24.,Y1=-InWallY+2*InWallY*(IY+1)/24.;
            const FVector A(X0,Y0,FMath::Max(VaultA(Y0),VaultB(X0,Cx))),B(X1,Y0,FMath::Max(VaultA(Y0),VaultB(X1,Cx))),Cc(X1,Y1,FMath::Max(VaultA(Y1),VaultB(X1,Cx))),D(X0,Y1,FMath::Max(VaultA(Y1),VaultB(X0,Cx)));
            FVector N=FVector::CrossProduct(B-A,D-A);if(N.Z>0)N=-N;Vt.Face({A,B,Cc,D},N);
        }
        S.Col=Gold;
        for(int32 Corner=0;Corner<4;Corner++){
            const double Px=(Corner&1)?InPiers[Bay+1]:InPiers[Bay],Py=(Corner&2)?InWallY:-InWallY;
            for(int32 K=0;K<14;K++){auto Pt=[&](double T){const double X=Px+(Cx-Px)*T,Y=Py*(1-T);return FVector(X,Y,FMath::Max(VaultA(Y),VaultB(X,Cx))-6);};S.Tube(Pt(K/14.),Pt((K+1)/14.),6.5,6);}
        }
        S.Cone(Cx,0,InCrown-34,InCrown-4,26,6,8);
    }
    S.Col=Gold;S.Tube(FVector(InPiers[0],0,InCrown-6),FVector(InPiers[4],0,InCrown-6),8,8);
    for(int32 Pi=0;Pi<5;Pi++){S.Col=(Pi%2)?Blue:Gold;for(int32 K=0;K<24;K++){const double Y0=-InWallY+2*InWallY*K/24.,Y1=-InWallY+2*InWallY*(K+1)/24.;S.Tube(FVector(InPiers[Pi],Y0,VaultA(Y0)-7),FVector(InPiers[Pi],Y1,VaultA(Y1)-7),9,8);}}
    // West end: wall, great rose, tracery, tribune balcony and portal.
    S.Col=Stone;S.Face({FVector(InPiers[4]+4,InWallY,InFloor),FVector(InPiers[4]+4,-InWallY,InFloor),FVector(InPiers[4]+4,-InWallY,InCrown),FVector(InPiers[4]+4,InWallY,InCrown)},FVector(-1,0,0));
    const double RoseZ=1650,RoseR=330;TArray<FVector> Rose;TArray<FVector2D> RoseU;
    for(int32 K=0;K<48;K++){const double A=2*PI*K/48;Rose.Add(FVector(InPiers[4],RoseR*FMath::Cos(A),RoseZ+RoseR*FMath::Sin(A)));RoseU.Add(RoseUV(A));}
    G.Face(Rose,FVector(-1,0,0),RoseU);Windows++;
    S.Col=Gold;
    for(int32 K=0;K<48;K++){const double A=2*PI*K/48,B=2*PI*(K+1)/48;S.Tube(FVector(InPiers[4]-4,RoseR*FMath::Cos(A),RoseZ+RoseR*FMath::Sin(A)),FVector(InPiers[4]-4,RoseR*FMath::Cos(B),RoseZ+RoseR*FMath::Sin(B)),9,6);}
    for(int32 K=0;K<16;K++){const double A=2*PI*K/16;S.Tube(FVector(InPiers[4]-4,0,RoseZ),FVector(InPiers[4]-4,RoseR*FMath::Cos(A),RoseZ+RoseR*FMath::Sin(A)),4.5,6);}
    for(int32 K=0;K<16;K++){const double A=2*PI*(K+.5)/16;const FVector Ctr(InPiers[4]-4,RoseR*.62*FMath::Cos(A),RoseZ+RoseR*.62*FMath::Sin(A));for(int32 J=0;J<10;J++){const double a0=2*PI*J/10,a1=2*PI*(J+1)/10;S.Tube(Ctr+FVector(0,56*FMath::Cos(a0),56*FMath::Sin(a0)),Ctr+FVector(0,56*FMath::Cos(a1),56*FMath::Sin(a1)),3,5);}}
    S.Box(FVector(InPiers[4]-30,0,1010),FVector(30,430,14));S.Box(FVector(InPiers[4]-52,0,1055),FVector(6,430,28));
    for(double Y=-420;Y<=420;Y+=42)S.Tube(FVector(InPiers[4]-52,Y,1000),FVector(InPiers[4]-52,Y,1085),4,6);
    S.Tube(FVector(InPiers[4]-52,-430,1085),FVector(InPiers[4]-52,430,1085),7,6);
    for(double Y:{-420.,420.})S.Tube(FVector(InPiers[4]-30,Y,InFloor),FVector(InPiers[4]-30,Y,1000),14,8);
    S.Col=Dark;{TArray<FVector> Door;Door.Add(FVector(InPiers[4]-2,130,InFloor));Door.Add(FVector(InPiers[4]-2,-130,InFloor));for(int32 K=0;K<=12;K++){const double Y=-130+260*K/12.;Door.Add(FVector(InPiers[4]-2,Y,900+170*(1-FMath::Pow(FMath::Abs(Y)/130,1.7))));}S.Face(Door,FVector(-1,0,0));}
    // Apse dais and gilt reliquary canopy.
    S.Col=Gold;S.Box(FVector(-1750,0,InFloor+22),FVector(250,330,22));
    for(double X:{-1930.,-1570.})for(double Y:{-240.,240.})S.Tube(FVector(X,Y,InFloor+44),FVector(X,Y,InFloor+600),14,8);
    for(double X:{-1930.,-1570.})S.Tube(FVector(X,-240,InFloor+600),FVector(X,240,InFloor+600),11,8);
    for(double Y:{-240.,240.})S.Tube(FVector(-1930,Y,InFloor+600),FVector(-1570,Y,InFloor+600),11,8);
    S.Cone(-1750,0,InFloor+600,InFloor+980,300,8,4);
    S.Col=Red;S.Box(FVector(-1750,0,InFloor+80),FVector(110,60,36));
    const FLinearColor Skin(.55f,.40f,.20f,.45f),Flame(1.f,.78f,.38f,0.f),Wax(.80f,.74f,.58f,.6f);
    // Twelve apostle statues on brackets with pointed hoods, standing against the piers (inferred from the published photographs).
    auto Statue=[&](double X,double Y,double Z,FLinearColor Robe){
        S.Col=Gold;S.Box(FVector(X,Y,Z-14),FVector(26,26,10));
        S.Col=Robe;S.Cone(X,Y,Z,Z+150,24,13,10);
        S.Col=Gold;S.Cone(X,Y,Z+110,Z+120,17,17,10);
        S.Col=Skin;S.Cone(X,Y,Z+150,Z+176,10,9,8);
        S.Col=Gold;S.Cone(X,Y,Z+186,Z+189,19,19,10);
        S.Cone(X,Y,Z+250,Z+330,24,2,6);
        S.Tube(FVector(X-20,Y,Z+250),FVector(X+20,Y,Z+250),4,6);
    };
    for(int32 Sign:{-1,1})for(int32 Pi=0;Pi<5;Pi++)Statue(InPiers[Pi],Sign*(InWallY-52),InFloor+300,(Pi%2)?Red:Blue);
    for(int32 B=1;B<=6;B++){const FVector P=ApsePier(B);const FVector R=FVector(P.X-InApseX,P.Y,0).GetSafeNormal();Statue(P.X-R.X*44,P.Y-R.Y*44,InFloor+300,(B%2)?Blue:Red);}
    // Pier diapering: gilt fleuron bands up each shaft.
    S.Col=Gold;
    for(int32 Sign:{-1,1})for(int32 Pi=0;Pi<5;Pi++)for(double Z=InFloor+90;Z<InSpring-40;Z+=70){if(FMath::Abs(Z-(InFloor+300))<120)continue;S.Box(FVector(InPiers[Pi],Sign*(InWallY-24),Z),FVector(9,15,7));S.Box(FVector(InPiers[Pi],Sign*(InWallY-24),Z+35),FVector(15,9,5));}
    // Painted dado behind the blind arcade: alternating red and blue lozenge panels with gilt centres.
    for(int32 Sign:{-1,1})for(int32 Bay=0;Bay<4;Bay++){
        const double Cx=InPiers[Bay]+InBayPitch*.5,Y=Sign*(InWallY-8);
        for(double Off:{-250.,0.,250.}){
            S.Col=(((int32)(Off/250)+Bay)%2)?Blue:Red;S.Face({FVector(Cx+Off-96,Y,InFloor+12),FVector(Cx+Off+96,Y,InFloor+12),FVector(Cx+Off+96,Y,700),FVector(Cx+Off-96,Y,700)},FVector(0,-Sign,0));
            S.Col=Gold;S.Tube(FVector(Cx+Off,Y-3,InFloor+30),FVector(Cx+Off+60,Y-3,InFloor+95),3,5);S.Tube(FVector(Cx+Off+60,Y-3,InFloor+95),FVector(Cx+Off,Y-3,InFloor+160),3,5);S.Tube(FVector(Cx+Off,Y-3,InFloor+160),FVector(Cx+Off-60,Y-3,InFloor+95),3,5);S.Tube(FVector(Cx+Off-60,Y-3,InFloor+95),FVector(Cx+Off,Y-3,InFloor+30),3,5);
        }
    }
    // Candelabra chandeliers hanging on chains from the vault.
    auto Chandelier=[&](double X,double Y,double Zc,double Rr,int32 Candles){
        S.Col=Gold;S.Tube(FVector(X,Y,Zc+420),FVector(X,Y,Zc),2.5,5);S.Cone(X,Y,Zc-8,Zc+8,14,14,8);
        for(int32 K=0;K<12;K++){const double A0=2*PI*K/12,A1=2*PI*(K+1)/12;S.Tube(FVector(X+Rr*FMath::Cos(A0),Y+Rr*FMath::Sin(A0),Zc),FVector(X+Rr*FMath::Cos(A1),Y+Rr*FMath::Sin(A1),Zc),3.5,5);}
        for(int32 K=0;K<Candles;K++){const double A=2*PI*K/Candles;const double CX=X+Rr*FMath::Cos(A),CY=Y+Rr*FMath::Sin(A);
            S.Col=Gold;S.Tube(FVector(X,Y,Zc),FVector(CX,CY,Zc+10),2.2,5);S.Tube(FVector(CX,CY,Zc),FVector(CX,CY,Zc+20),3,5);
            S.Col=Wax;S.Tube(FVector(CX,CY,Zc+20),FVector(CX,CY,Zc+44),2.4,6);
            S.Col=Flame;S.Cone(CX,CY,Zc+44,Zc+56,2.6,.2,6);}
    };
    for(int32 Sign:{-1,1}){for(double X:{-1060.,-300.,460.,1200.})Chandelier(X,Sign*330,1130,70,8);}
    Chandelier(-1750,-330,1050,60,6);Chandelier(-1750,330,1050,60,6);
    // Reliquary tabernacle: steep gabled canopy with crocketed pinnacles over the dais, framing the central window.
    S.Col=Gold;
    for(int32 K=0;K<12;K++){auto Gable=[&](double T){return FVector(-1570,-240+480*T,InFloor+600+(1-FMath::Pow(FMath::Abs(2*T-1),1.4))*340);};S.Tube(Gable(K/12.),Gable((K+1)/12.),7,6);}
    for(double Y:{-240.,240.}){S.Cone(-1570,Y,InFloor+600,InFloor+840,18,3,6);S.Cone(-1570,Y,InFloor+840,InFloor+900,7,0.5,6);}
    for(double Y:{-120.,0.,120.}){const double H=InFloor+600+(1-FMath::Pow(FMath::Abs(Y)/240.,1.4))*340;S.Tube(FVector(-1570,Y,InFloor+600),FVector(-1570,Y,H),4,6);for(int32 Cr=1;Cr<4;Cr++)S.Box(FVector(-1570,Y,InFloor+600+(H-InFloor-600)*Cr/4.),FVector(8,8,8));}
    S.Cone(-1570,0,InFloor+940,InFloor+1010,8,.5,6);
    S.Col=Blue;S.Face({FVector(-1572,-228,InFloor+604),FVector(-1572,228,InFloor+604),FVector(-1572,0,InFloor+930)},FVector(1,0,0));
    S.Col=Gold;for(double Y:{-170.,0.,170.})S.Cone(-1572,Y,InFloor+620,InFloor+700,2,2,4);
    // Kneeling angels beneath the canopy.
    for(double Y:{-110.,110.}){S.Col=Wax;S.Cone(-1560,Y,InFloor+640,InFloor+720,22,12,8);S.Col=Skin;S.Cone(-1560,Y,InFloor+720,InFloor+745,9,8,8);S.Col=Gold;S.Box(FVector(-1560,Y+(Y>0?-30:30),InFloor+700),FVector(6,34,14));S.Box(FVector(-1560,Y+(Y>0?30:-30),InFloor+700),FVector(6,34,14));}
}
}
AParisChapelleDetail::AParisChapelleDetail(){
    RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("ChapelleRoot"));
    Stone=CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("ChapelleStone"));Stone->SetupAttachment(RootComponent);
    Glass=CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("ChapelleStainedGlass"));Glass->SetupAttachment(RootComponent);Glass->SetCastShadow(false);
    Roof=CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("ChapelleRoof"));Roof->SetupAttachment(RootComponent);
    Camera=CreateDefaultSubobject<UCameraComponent>(TEXT("ChapelleCamera"));Camera->SetupAttachment(RootComponent);FVector Offset(8500,-7200,6300);Camera->SetRelativeLocation(Offset);Camera->SetRelativeRotation((FVector(0,0,3500)-Offset).Rotation());Camera->FieldOfView=75;
    PrimaryActorTick.bCanEverTick=true;PrimaryActorTick.TickInterval=.2f;
    InnerSolid=CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("ChapelleInnerSolid"));InnerSolid->SetupAttachment(RootComponent);InnerSolid->SetVisibility(false);
    InnerGlass=CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("ChapelleInnerGlass"));InnerGlass->SetupAttachment(RootComponent);InnerGlass->SetCastShadow(false);InnerGlass->SetVisibility(false);
    InnerVault=CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("ChapelleInnerVault"));InnerVault->SetupAttachment(RootComponent);InnerVault->SetVisibility(false);
    auto MakeCamera=[this](const TCHAR* Name,FVector From,FVector To,float Fov){auto C=CreateDefaultSubobject<UCameraComponent>(Name);C->SetupAttachment(RootComponent);C->SetRelativeLocation(From);C->SetRelativeRotation((To-From).Rotation());C->FieldOfView=Fov;C->SetAutoActivate(false);return C;};
    WestCamera=MakeCamera(TEXT("ChapelleWestCamera"),FVector(-1250,0,700),FVector(1580,0,1350),76);
    ApseCamera=MakeCamera(TEXT("ChapelleApseCamera"),FVector(1150,0,700),FVector(-2000,0,1300),76);
    WindowCamera=MakeCamera(TEXT("ChapelleWindowCamera"),FVector(-150,-300,690),FVector(300,600,1500),84);
    // Warm gilt candlelight plus cool/rose tints borrowed from the glass; positions follow the bays and apse.
    const FLinearColor Tints[7]={FLinearColor(1.f,.74f,.46f),FLinearColor(.62f,.52f,1.f),FLinearColor(1.f,.52f,.40f),FLinearColor(.55f,.65f,1.f),FLinearColor(1.f,.74f,.46f),FLinearColor(1.f,.62f,.42f),FLinearColor(.70f,.58f,1.f)};
    const FVector Spots[7]={FVector(-1250,0,1450),FVector(-650,0,1450),FVector(-50,0,1450),FVector(550,0,1450),FVector(1150,0,1450),FVector(-1850,0,1350),FVector(-1750,0,900)};
    for(int32 I=0;I<7;I++){auto L=CreateDefaultSubobject<UPointLightComponent>(*FString::Printf(TEXT("ChapelleInnerLight%d"),I));L->SetupAttachment(RootComponent);L->SetRelativeLocation(Spots[I]);L->SetLightColor(Tints[I]);L->SetIntensityUnits(ELightUnits::Candelas);L->SetIntensity(I==6?30000:90000);L->SetAttenuationRadius(3200);L->SetSourceRadius(80);L->SetCastShadows(false);L->SetVisibility(false);InnerLights.Add(L);}
}
void AParisChapelleDetail::Tick(float DeltaSeconds){
    Super::Tick(DeltaSeconds);if(!bInteriorBuilt)return;
    // Interior meshes and lights are drawn only while the viewer is inside, so the exterior view pays nothing.
    auto PC=GetWorld()?GetWorld()->GetFirstPlayerController():nullptr;const bool Inside=PC&&PC->GetViewTarget()==this&&ViewIndex>0;
    InnerSolid->SetVisibility(Inside);InnerGlass->SetVisibility(Inside);InnerVault->SetVisibility(Inside);for(auto L:InnerLights)L->SetVisibility(Inside);
    // The scene uses fixed daylight camera exposure (ISO100, 1/125s); the nave is
    // a candle-and-glass interior, so switch to a dark-adapted exposure while inside.
    if(Inside!=bWasInside){
        bWasInside=Inside;
        for(TActorIterator<APostProcessVolume> It(GetWorld());It;++It)if(It->ActorHasTag(TEXT("ParisPhotoEnvironment"))){
            auto& P=It->Settings;
            if(Inside){if(!bSavedExposure){SavedISO=P.CameraISO;SavedShutter=P.CameraShutterSpeed;bSavedExposure=true;}P.bOverride_CameraISO=true;P.CameraISO=400.f;P.bOverride_CameraShutterSpeed=true;P.CameraShutterSpeed=30.f;}
            else if(bSavedExposure){P.CameraISO=SavedISO;P.CameraShutterSpeed=SavedShutter;bSavedExposure=false;}
        }
        // Outdoor sun, sky and haze would leak through the shell mesh and wash out the nave.
        for(TActorIterator<ASkyLight> It(GetWorld());It;++It)if(It->ActorHasTag(TEXT("ParisPhotoEnvironment")))It->GetLightComponent()->SetVisibility(!Inside);
        for(TActorIterator<ADirectionalLight> It(GetWorld());It;++It)if(It->ActorHasTag(TEXT("ParisPhotoEnvironment")))It->GetLightComponent()->SetVisibility(!Inside);
        for(TActorIterator<AExponentialHeightFog> It(GetWorld());It;++It)if(It->ActorHasTag(TEXT("ParisPhotoEnvironment")))It->GetComponent()->SetVisibility(!Inside);
    }
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
    SpireHeightCm=7500;S.Apply(Stone,StoneMat);G.Apply(Glass,GlassMat);R.Apply(Roof,RoofMat);
    {
        auto InMat=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/ParisPhotoreal/SainteChapelle/M_SainteChapelleInterior.M_SainteChapelleInterior"));
        auto InGlass=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/ParisPhotoreal/SainteChapelle/M_SainteChapelleInnerGlass.M_SainteChapelleInnerGlass"));
        auto InVault=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/ParisPhotoreal/SainteChapelle/M_SainteChapelleVault.M_SainteChapelleVault"));
        if(InMat&&InGlass&&InVault){ChapelMesh IS,IG,IV;int32 InnerWindows=0;BuildInterior(IS,IG,IV,InnerWindows);IS.Apply(InnerSolid,InMat);IG.Apply(InnerGlass,InGlass);IV.Apply(InnerVault,InVault);bInteriorBuilt=true;UE_LOG(LogTemp,Display,TEXT("PARIS_CHAPELLE_INTERIOR_READY windows=%d solid_tris=%d vault_tris=%d"),InnerWindows,IS.I.Num()/3,IV.I.Num()/3);}
        else UE_LOG(LogTemp,Warning,TEXT("PARIS_CHAPELLE_INTERIOR_MATERIALS_MISSING run Build-ParisChapelle.ps1"));
    }
    bReady=true;Sync();return true;
}
void AParisChapelleDetail::Sync(){if(Scene)SetActorHiddenInGame(!bReady||Scene->DetailQuality==0||Scene->bFootprints||Scene->bLevels||Scene->bIssues||!Scene->bDetailedSurfaces);}
void AParisChapelleDetail::ActivateView(APlayerController* PC,int32 Index){
    if(!PC)return;if(Index>0&&!bInteriorBuilt)Index=0;ViewIndex=FMath::Clamp(Index,0,3);
    UCameraComponent* Cams[4]={Camera,WestCamera,ApseCamera,WindowCamera};for(int32 I=0;I<4;I++)if(Cams[I])Cams[I]->SetActive(I==ViewIndex);
    PC->SetViewTarget(this);if(PC->PlayerCameraManager)PC->PlayerCameraManager->SetGameCameraCutThisFrame();
}
bool AParisChapelleDetail::CycleView(APlayerController* PC){if(!bInteriorBuilt||ViewIndex>=3)return false;ActivateView(PC,ViewIndex+1);return true;}
