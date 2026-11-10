#include "ParisNotreDame.h"
#include "ParisProcMesh.h"
#include "ParisChapelle.h"
#include "ParisDigitalTwin.h"
#include "ProceduralMeshComponent.h"
#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "GameFramework/PlayerController.h"
#include "Components/PointLightComponent.h"
#include "Engine/World.h"
#include "Materials/MaterialInterface.h"
#include "EngineUtils.h"
#include "GameFramework/Info.h"
#include "GameFramework/HUD.h"
#include "Engine/Light.h"
#include "Engine/PostProcessVolume.h"
#include "Engine/SkyLight.h"
#include "Engine/ExponentialHeightFog.h"

// Inferred reconstruction of the Notre-Dame upper interior. Local frame: X along the axis from the
// west front (X=0) toward the apse, Y = 0 on the nave centreline (+Y toward the south / sacristy),
// Z = 0 on the nave floor. Main dimensions: 33 m vault, 12 m main vessel, double aisles, side
// chapels, transept with north/south roses, five-bay choir, apse with double ambulatory.
namespace {
using FMesh=FParisProcMesh;
constexpr double NDWest=300,NDHM=600,NDHI=1100,NDHO=1650,NDHC=2350,NDTr=2650;
constexpr double NDArcSpring=800,NDArcCrown=1150,NDTrib0=1250,NDTribTop=1900,NDClere=1960,NDSpring=2450,NDCrown=3300;
constexpr double NDAisleSpring=800,NDAisleCrown=1180;
constexpr double NDCross0=7200,NDCross1=8400,NDApseX=11400,NDApseR=600,NDAmb1=1100,NDAmb2=1600,NDApseWall=2000;
double Arch(double T,double Spring,double Crown){return Spring+(Crown-Spring)*(1-FMath::Pow(FMath::Clamp(FMath::Abs(2*T-1),0.,1.),1.7));}
TArray<double> BayLines(){TArray<double> L;L.Add(NDWest);for(int32 K=0;K<=10;K++)L.Add(1500+570*K);for(int32 K=1;K<=5;K++)L.Add(NDCross1+600*K);return L;} // 300,1500..7200,9000..11400 (8400 via K=0 below)
FVector2D GlassUV(double T,double V){return FVector2D(.53+.14*FMath::Clamp(T,0.,1.),.86-.64*FMath::Clamp(V,0.,1.));}
FVector2D RoseUV(double A){return FVector2D(.53+.12*(.5+.5*FMath::Cos(A)),.29+.20*(.5-.5*FMath::Sin(A)));}
FVector Down(FVector N){return N.Z>0?-N:N;}
// Groin vault over an axis-aligned rectangle: the higher of the two pointed barrels, with ribs.
void GroinVault(FMesh& M,double X0,double X1,double Y0,double Y1,double Spring,double Crown,const FLinearColor& Web,const FLinearColor& Rib,int32 NX=10,int32 NY=12){
    auto Z=[&](double X,double Y){return FMath::Max(Arch((Y-Y0)/(Y1-Y0),Spring,Crown),Arch((X-X0)/(X1-X0),Spring,Crown));};
    auto P=[&](double X,double Y){return FVector(X,Y,Z(X,Y));};
    M.Col=Web;
    for(int32 IX=0;IX<NX;IX++)for(int32 IY=0;IY<NY;IY++){
        const double XA=FMath::Lerp(X0,X1,double(IX)/NX),XB=FMath::Lerp(X0,X1,double(IX+1)/NX),YA=FMath::Lerp(Y0,Y1,double(IY)/NY),YB=FMath::Lerp(Y0,Y1,double(IY+1)/NY);
        const FVector A=P(XA,YA),B=P(XB,YA),C=P(XB,YB),D=P(XA,YB);M.Face({A,B,C,D},Down(FVector::CrossProduct(B-A,D-A)));
    }
    M.Col=Rib;const double Cx=(X0+X1)*.5,Cy=(Y0+Y1)*.5;
    for(int32 Corner=0;Corner<4;Corner++){const double Px=(Corner&1)?X1:X0,Py=(Corner&2)?Y1:Y0;for(int32 K=0;K<12;K++){auto Q=[&](double T){const double X=FMath::Lerp(Px,Cx,T),Y=FMath::Lerp(Py,Cy,T);return FVector(X,Y,Z(X,Y)-7);};M.Tube(Q(K/12.),Q((K+1)/12.),8,6);}}
    for(double X:{X0,X1})for(int32 K=0;K<12;K++){const double YA=FMath::Lerp(Y0,Y1,K/12.),YB=FMath::Lerp(Y0,Y1,(K+1)/12.);M.Tube(FVector(X,YA,Z(X,YA)-8),FVector(X,YB,Z(X,YB)-8),11,6);}
    M.Cone(Cx,Cy,Z(Cx,Cy)-30,Z(Cx,Cy)-4,24,8,8);
}
// Annular-sector vault for the ambulatory (polar version of the groin vault).
void PolarVault(FMesh& M,double Cx,double T0,double T1,double R0,double R1,double Spring,double Crown,const FLinearColor& Web,const FLinearColor& Rib){
    auto P=[&](double U,double V){const double A=FMath::Lerp(T0,T1,U),R=FMath::Lerp(R0,R1,V);return FVector(Cx+R*FMath::Cos(A),R*FMath::Sin(A),FMath::Max(Arch(U,Spring,Crown),Arch(V,Spring,Crown)));};
    M.Col=Web;
    for(int32 IU=0;IU<6;IU++)for(int32 IV=0;IV<6;IV++){const FVector A=P(IU/6.,IV/6.),B=P((IU+1)/6.,IV/6.),C=P((IU+1)/6.,(IV+1)/6.),D=P(IU/6.,(IV+1)/6.);M.Face({A,B,C,D},Down(FVector::CrossProduct(B-A,D-A)));}
    M.Col=Rib;for(int32 Corner=0;Corner<4;Corner++){const double U=(Corner&1)?1:0,V=(Corner&2)?1:0;for(int32 K=0;K<8;K++){M.Tube(P(FMath::Lerp(U,.5,K/8.),FMath::Lerp(V,.5,K/8.))-FVector(0,0,6),P(FMath::Lerp(U,.5,(K+1)/8.),FMath::Lerp(V,.5,(K+1)/8.))-FVector(0,0,6),6,6);}}
}
// Vertical wall in the plane through A-B with a pointed opening from the floor to the arch;
// the solid spandrels between the arch and Top are fan-triangulated from the upper corners.
void ArcadeWall(FMesh& M,FVector2D A,FVector2D B,double Spring,double Crown,double Top,const FLinearColor& Moulding){
    auto P=[&](double T,double Zv){const FVector2D Q=A+(B-A)*T;return FVector(Q.X,Q.Y,Zv);};
    const FVector2D D=(B-A).GetSafeNormal();const FVector Nrm(-D.Y,D.X,0);
    TArray<FVector> L,R;L.Add(P(0,Top));R.Add(P(1,Top));
    for(int32 K=0;K<=10;K++){const double T=.5*K/10;L.Add(P(T,Arch(T,Spring,Crown)));R.Add(P(1-T,Arch(1-T,Spring,Crown)));}
    L.Add(P(.5,Top));R.Add(P(.5,Top));M.Face(L,Nrm);M.Face(R,Nrm);
    const FLinearColor Saved=M.Col;M.Col=Moulding;
    for(int32 K=0;K<16;K++)M.Tube(P(K/16.,Arch(K/16.,Spring,Crown)),P((K+1)/16.,Arch((K+1)/16.,Spring,Crown)),9,6);
    M.Col=Saved;
}
void Strip(FMesh& M,FVector2D A,FVector2D B,double Z0,double Z1){const FVector2D D=(B-A).GetSafeNormal();M.Face({FVector(A.X,A.Y,Z0),FVector(B.X,B.Y,Z0),FVector(B.X,B.Y,Z1),FVector(A.X,A.Y,Z1)},FVector(-D.Y,D.X,0));}
// Glass panel between A-B from Z0 with a pointed head following Arch(Spring,Crown).
void Lancet(FMesh& G,FVector2D A,FVector2D B,double Z0,double Spring,double Crown){
    TArray<FVector> P;TArray<FVector2D> U;const FVector2D D=(B-A).GetSafeNormal();
    P.Add(FVector(A.X,A.Y,Z0));U.Add(GlassUV(0,0));P.Add(FVector(B.X,B.Y,Z0));U.Add(GlassUV(1,0));
    for(int32 K=0;K<=16;K++){const double T=1-K/16.;const FVector2D Q=A+(B-A)*T;const double Zv=Arch(T,Spring,Crown);P.Add(FVector(Q.X,Q.Y,Zv));U.Add(GlassUV(T,(Zv-Z0)/(Crown-Z0)));}
    G.Face(P,FVector(-D.Y,D.X,0),U);
}
// Rose window: glass disc plus 3-D tracery (rim, spokes, inner ring and petals) in the plane spanned by Side/Up.
void Rose(FMesh& G,FMesh& S,FVector C,FVector Side,FVector Normal,double R,const FLinearColor& Tracery){
    TArray<FVector> P;TArray<FVector2D> U;const FVector Up(0,0,1);
    for(int32 K=0;K<64;K++){const double A=2*PI*K/64;P.Add(C+Side*(R*FMath::Cos(A))+Up*(R*FMath::Sin(A)));U.Add(RoseUV(A));}
    G.Face(P,Normal,U);
    S.Col=Tracery;const FVector In=-Normal*6;
    auto Ring=[&](double Rr,double Th,FVector Ctr){for(int32 K=0;K<48;K++){const double A=2*PI*K/48,B=2*PI*(K+1)/48;S.Tube(Ctr+In+Side*(Rr*FMath::Cos(A))+Up*(Rr*FMath::Sin(A)),Ctr+In+Side*(Rr*FMath::Cos(B))+Up*(Rr*FMath::Sin(B)),Th,6);}};
    Ring(R,16,C);Ring(R*.42,9,C);Ring(R*.18,7,C);
    for(int32 K=0;K<24;K++){const double A=2*PI*K/24;S.Tube(C+In+Side*(R*.18*FMath::Cos(A))+Up*(R*.18*FMath::Sin(A)),C+In+Side*(R*FMath::Cos(A))+Up*(R*FMath::Sin(A)),K%2?4:6,6);}
    for(int32 K=0;K<12;K++){const double A=2*PI*(K+.5)/12;const FVector Ctr=C+Side*(R*.70*FMath::Cos(A))+Up*(R*.70*FMath::Sin(A));for(int32 J=0;J<16;J++){const double a0=2*PI*J/16,a1=2*PI*(J+1)/16;S.Tube(Ctr+In+Side*(R*.16*FMath::Cos(a0))+Up*(R*.16*FMath::Sin(a0)),Ctr+In+Side*(R*.16*FMath::Cos(a1))+Up*(R*.16*FMath::Sin(a1)),3.5,5);}}
}
void Pier(FMesh& S,double X,double Y,double R,double Top,const FLinearColor& Stone,const FLinearColor& Cap){
    S.Col=Stone;S.Cone(X,Y,0,30,R*1.25,R*1.25,16);S.Cone(X,Y,30,Top,R,R,16);
    S.Col=Cap;S.Cone(X,Y,Top,Top+45,R,R*1.32,16);S.Box(FVector(X,Y,Top+55),FVector(R*1.35,R*1.35,10));
}
}

static void BuildNotreDame(FMesh& S,FMesh& G,FMesh& Bm,int32& Windows,int32& Piers,int32& Chairs){
    const FLinearColor Stone(.46f,.42f,.34f,.8f),StoneLight(.53f,.49f,.41f,.8f),StoneDark(.20f,.18f,.15f,.85f),Rib(.40f,.36f,.29f,.75f),Web(.50f,.46f,.38f,.85f);
    const FLinearColor Dark(.04f,.035f,.03f,.9f),Wood(.26f,.15f,.08f,.6f),Gold(.60f,.40f,.10f,.35f),Metal(.42f,.42f,.44f,.3f),Wax(.80f,.74f,.58f,.6f),Flame(1.f,.78f,.38f,0.f);
    TArray<double> L=BayLines();L.Insert(NDCross1,12); // 300,1500,...,7200,8400,9000,...,11400
    auto IsCrossing=[&](double X0){return FMath::IsNearlyEqual(X0,NDCross0,1.);};
    // ---- Floor: large pale/grey stone flags, plus a polar pattern in the apse and ambulatory.
    auto Tiles=[&](double X0,double X1,double Y0,double Y1){const double T=150;for(double X=X0;X<X1-1;X+=T)for(double Y=Y0;Y<Y1-1;Y+=T){const double XA=FMath::Min(X+T,X1),YA=FMath::Min(Y+T,Y1);const int32 K=FMath::FloorToInt(X/T)+FMath::FloorToInt((Y+5000)/T);S.Col=(K&1)?FLinearColor(.40f,.37f,.31f,.5f):FLinearColor(.25f,.23f,.20f,.5f);S.Face({FVector(X,Y,0),FVector(XA,Y,0),FVector(XA,YA,0),FVector(X,YA,0)},FVector(0,0,1));}};
    Tiles(NDWest,NDApseX,-NDHC,NDHC);Tiles(NDCross0,NDCross1,-NDTr,-NDHC);Tiles(NDCross0,NDCross1,NDHC,NDTr);
    for(int32 A=0;A<12;A++)for(int32 R=0;R<8;R++){
        const double T0=-PI*.5+PI*A/12,T1=-PI*.5+PI*(A+1)/12,R0=NDApseWall*R/8.,R1=NDApseWall*(R+1)/8.;
        auto P=[&](double T,double Rr){return FVector(NDApseX+Rr*FMath::Cos(T),Rr*FMath::Sin(T),0);};
        S.Col=((A+R)&1)?FLinearColor(.40f,.37f,.31f,.5f):FLinearColor(.25f,.23f,.20f,.5f);S.Face({P(T0,R1),P(T1,R1),P(T1,R0),P(T0,R0)},FVector(0,0,1));
    }
    // ---- Main vessel elevation (nave and choir): arcade, tribune gallery, clerestory, high vaults.
    for(int32 Bi=0;Bi+1<L.Num();Bi++){
        const double X0=L[Bi],X1=L[Bi+1],Xm=(X0+X1)*.5;
        if(IsCrossing(X0)){GroinVault(S,X0,X1,-NDHM,NDHM,NDSpring,NDCrown,Web,Rib,14,14);continue;}
        GroinVault(S,X0,X1,-NDHM,NDHM,NDSpring,NDCrown,Web,Rib,FMath::Max(6,int32((X1-X0)/60)),16);
        for(int32 Sign:{-1,1}){
            const double Y=Sign*NDHM;const FVector2D A(X0,Y),B(X1,Y),M(Xm,Y);
            S.Col=Stone;ArcadeWall(S,A,B,NDArcSpring,NDArcCrown,NDTrib0,Rib);
            S.Col=Stone;ArcadeWall(S,A,M,NDTrib0+170,NDTrib0+540,NDTribTop,Rib);ArcadeWall(S,M,B,NDTrib0+170,NDTrib0+540,NDTribTop,Rib);
            S.Col=StoneLight;S.Tube(FVector(Xm,Y,NDTrib0),FVector(Xm,Y,NDTrib0+190),12,8);
            S.Col=StoneDark;Strip(S,FVector2D(X0,Sign*(NDHM+430)),FVector2D(X1,Sign*(NDHM+430)),NDAisleCrown,NDTribTop+80); // dim tribune gallery behind the openings
            S.Face({FVector(X0,Y,NDTrib0),FVector(X1,Y,NDTrib0),FVector(X1,Sign*(NDHM+430),NDTrib0),FVector(X0,Sign*(NDHM+430),NDTrib0)},FVector(0,0,1));
            S.Face({FVector(X0,Y,NDTribTop+80),FVector(X1,Y,NDTribTop+80),FVector(X1,Sign*(NDHM+430),NDTribTop+80),FVector(X0,Sign*(NDHM+430),NDTribTop+80)},FVector(0,0,-1));
            S.Col=Stone;Strip(S,A,B,NDTribTop,NDClere);
            // Clerestory: two lancets and an oculus under the wall rib, filled with glass.
            const double Gy=Sign*(NDHM+14);
            {TArray<FVector> P;TArray<FVector2D> U;P.Add(FVector(X0+35,Gy,NDClere));U.Add(GlassUV(0,0));P.Add(FVector(X1-35,Gy,NDClere));U.Add(GlassUV(1,0));
             for(int32 K=0;K<=16;K++){const double T=1-K/16.;const double X=FMath::Lerp(X0+35,X1-35,T);const double Zv=Arch((X-X0)/(X1-X0),NDSpring,NDCrown)-12;P.Add(FVector(X,Gy,Zv));U.Add(GlassUV(T,(Zv-NDClere)/(NDCrown-NDClere)));}
             G.Face(P,FVector(0,-Sign,0),U);Windows++;}
            S.Col=StoneLight;const double Ty=Sign*(NDHM+6),Span=X1-X0;
            S.Tube(FVector(Xm,Ty,NDClere),FVector(Xm,Ty,Arch(.5,NDSpring,NDCrown)-Span*.42),7,8);
            for(int32 K=0;K<16;K++){auto Q=[&](double T){const double X=FMath::Lerp(X0+35,X1-35,T);return FVector(X,Ty,Arch((X-X0)/(X1-X0),NDSpring,NDCrown)-14);};S.Tube(Q(K/16.),Q((K+1)/16.),9,6);}
            {const double Cz=Arch(.5,NDSpring,NDCrown)-Span*.27,Cr=Span*.13;for(int32 K=0;K<24;K++){const double a0=2*PI*K/24,a1=2*PI*(K+1)/24;S.Tube(FVector(Xm+Cr*FMath::Cos(a0),Ty,Cz+Cr*FMath::Sin(a0)),FVector(Xm+Cr*FMath::Cos(a1),Ty,Cz+Cr*FMath::Sin(a1)),5,6);}}
            for(double T:{.25,.75}){const double X=FMath::Lerp(X0,X1,T);S.Tube(FVector(X,Ty,NDClere),FVector(X,Ty,NDClere+380),5,6);for(int32 K=0;K<8;K++)S.Tube(ParisArchPoint(X,Ty,NDClere+380,Span*.46,Span*.30,K/8.),ParisArchPoint(X,Ty,NDClere+380,Span*.46,Span*.30,(K+1)/8.),5,6);}
            // Aisle vaults (inner and outer) and side chapels, outer wall with chapel lancets.
            const double Ya=FMath::Min(Sign*NDHM,Sign*NDHI),Yb=FMath::Max(Sign*NDHM,Sign*NDHI),Yc=FMath::Min(Sign*NDHI,Sign*NDHO),Yd=FMath::Max(Sign*NDHI,Sign*NDHO),Ye=FMath::Min(Sign*NDHO,Sign*NDHC),Yf=FMath::Max(Sign*NDHO,Sign*NDHC);
            GroinVault(S,X0,X1,Ya,Yb,NDAisleSpring,NDAisleCrown,Web,Rib,6,6);
            GroinVault(S,X0,X1,Yc,Yd,NDAisleSpring,NDAisleCrown,Web,Rib,6,6);
            GroinVault(S,X0,X1,Ye,Yf,NDAisleSpring-60,NDAisleCrown-60,Web,Rib,6,6);
            S.Col=Stone;Strip(S,FVector2D(X0,Sign*NDHC),FVector2D(X1,Sign*NDHC),0,NDAisleCrown);
            S.Col=Stone;Strip(S,FVector2D(X0,Sign*NDHO),FVector2D(X1,Sign*NDHO),NDAisleCrown-60,NDAisleCrown);
            for(double T:{.27,.73}){const double X=FMath::Lerp(X0,X1,T),Hw=FMath::Min(110.,Span*.17);Lancet(G,FVector2D(X-Hw,Sign*(NDHC-8)),FVector2D(X+Hw,Sign*(NDHC-8)),280,760,1040);Windows++;}
            S.Col=Stone;S.Box(FVector(X0,Sign*(NDHO+NDHC)*.5,(NDAisleCrown-60)*.5),FVector(25,(NDHC-NDHO)*.5,(NDAisleCrown-60)*.5));
            // Choir enclosure: polychrome sculpted screen between the choir piers.
            if(X0>=NDCross1-1){S.Col=(Bi%2)?FLinearColor(.22f,.06f,.05f,.6f):FLinearColor(.05f,.08f,.20f,.6f);S.Box(FVector(Xm,Sign*(NDHM-4),150),FVector(Span*.5-80,12,150));S.Col=Gold;S.Box(FVector(Xm,Sign*(NDHM-6),305),FVector(Span*.5-80,15,8));
                for(int32 K=0;K<4;K++){S.Col=FLinearColor(.40f,.30f,.18f,.6f);S.Cone(X0+Span*(K+.5)/4,Sign*(NDHM-22),120,250,16,10,8);}}
        }
    }
    // ---- Piers: round nave columns (cantonnées at the crossing/tower), aisle rows, wall shafts to the vault.
    for(double X:L){
        if(FMath::IsNearlyEqual(X,NDWest,1.))continue;
        const bool Heavy=FMath::IsNearlyEqual(X,1500.,1.)||FMath::IsNearlyEqual(X,NDCross0,1.)||FMath::IsNearlyEqual(X,NDCross1,1.);
        for(int32 Sign:{-1,1}){
            Pier(S,X,Sign*NDHM,Heavy?105:68,NDArcSpring-55,Stone,StoneLight);Piers++;
            S.Col=StoneLight;for(double Off:{-18.,0.,18.})S.Tube(FVector(X+Off,Sign*(NDHM-30),Heavy?0:NDArcSpring),FVector(X+Off,Sign*(NDHM-30),NDSpring),Off==0?13:9,8);
            S.Box(FVector(X,Sign*(NDHM-30),NDSpring+10),FVector(42,22,12));
            if(FMath::IsNearlyEqual(X,NDCross0,1.)||FMath::IsNearlyEqual(X,NDCross1,1.))continue;
            Pier(S,X,Sign*NDHI,50,NDAisleSpring-50,Stone,StoneLight);Pier(S,X,Sign*NDHO,44,NDAisleSpring-110,Stone,StoneLight);Piers+=2;
            S.Col=Rib;for(int32 K=0;K<10;K++){const double YA=FMath::Lerp(NDHM,NDHO,K/10.),YB=FMath::Lerp(NDHM,NDHO,(K+1)/10.);auto Zr=[&](double Yv){const double T=Yv<NDHI?(Yv-NDHM)/(NDHI-NDHM):(Yv-NDHI)/(NDHO-NDHI);return Arch(T,NDAisleSpring,NDAisleCrown)-10;};S.Tube(FVector(X,Sign*YA,Zr(YA)),FVector(X,Sign*YB,Zr(YB)),10,6);}
        }
    }
    // ---- Transept arms: high vaults, east/west walls with clerestory, end walls with the great roses.
    for(int32 Sign:{-1,1}){
        for(int32 K=0;K<3;K++){
            const double Ya=NDHM+(NDTr-NDHM)*K/3.,Yb=NDHM+(NDTr-NDHM)*(K+1)/3.;const double Y0=FMath::Min(Sign*Ya,Sign*Yb),Y1=FMath::Max(Sign*Ya,Sign*Yb);
            GroinVault(S,NDCross0,NDCross1,Y0,Y1,NDSpring,NDCrown,Web,Rib,14,8);
            for(double X:{NDCross0,NDCross1}){
                const double Nx=X<NDCross1-1?1:-1;const FVector2D A(X,Y0),B(X,Y1);
                S.Col=Stone;Strip(S,A,B,NDAisleCrown,NDClere);
                if(Yb>NDHC+1){Strip(S,FVector2D(X,Sign*NDHC),FVector2D(X,Sign*NDTr),0,NDAisleCrown);}
                TArray<FVector> P;TArray<FVector2D> U;const double Gx=X+Nx*14;P.Add(FVector(Gx,Y0+35,NDClere));U.Add(GlassUV(0,0));P.Add(FVector(Gx,Y1-35,NDClere));U.Add(GlassUV(1,0));
                for(int32 J=0;J<=16;J++){const double T=1-J/16.;const double Yv=FMath::Lerp(Y0+35,Y1-35,T);const double Zv=Arch((Yv-Y0)/(Y1-Y0),NDSpring,NDCrown)-12;P.Add(FVector(Gx,Yv,Zv));U.Add(GlassUV(T,(Zv-NDClere)/(NDCrown-NDClere)));}
                G.Face(P,FVector(Nx,0,0),U);Windows++;
                S.Col=StoneLight;S.Tube(FVector(X+Nx*6,(Y0+Y1)*.5,NDClere),FVector(X+Nx*6,(Y0+Y1)*.5,Arch(.5,NDSpring,NDCrown)-200),7,8);
            }
            if(K<2)for(double X:{NDCross0,NDCross1}){S.Col=StoneLight;S.Tube(FVector(X,Sign*Yb,0),FVector(X,Sign*Yb,NDSpring),26,10);}
        }
        // End wall up to the wall rib, great rose, glazed triforium and portal.
        const double Yw=Sign*NDTr;S.Col=Stone;
        {TArray<FVector> P;P.Add(FVector(NDCross0,Yw,0));P.Add(FVector(NDCross1,Yw,0));for(int32 K=0;K<=16;K++){const double T=1-K/16.;P.Add(FVector(FMath::Lerp(NDCross0,NDCross1,T),Yw,Arch(T,NDSpring,NDCrown)));}S.Face(P,FVector(0,-Sign,0));}
        Rose(G,S,FVector(7800,Sign*(NDTr-12),2330),FVector(1,0,0),FVector(0,-Sign,0),540,StoneLight);Windows++;
        for(int32 K=0;K<9;K++){const double X=NDCross0+110+K*(1200-220)/8.;Lancet(G,FVector2D(X-42,Sign*(NDTr-12)),FVector2D(X+42,Sign*(NDTr-12)),1250,1620,1760);Windows++;S.Col=StoneLight;S.Tube(FVector(X+61,Sign*(NDTr-16),1240),FVector(X+61,Sign*(NDTr-16),1770),6,6);}
        S.Col=StoneLight;S.Box(FVector(7800,Sign*(NDTr-20),1235),FVector(560,14,10));S.Box(FVector(7800,Sign*(NDTr-20),1790),FVector(560,14,10));
        S.Col=Dark;{TArray<FVector> D;D.Add(FVector(7600,Sign*(NDTr-6),0));D.Add(FVector(8000,Sign*(NDTr-6),0));for(int32 K=0;K<=12;K++){const double T=1-K/12.;D.Add(FVector(FMath::Lerp(7600.,8000.,T),Sign*(NDTr-6),Arch(T,520,760)));}S.Face(D,FVector(0,-Sign,0));}
    }
    // ---- West end: wall to the vault, west rose, organ tribune with the great organ, portals; aisle west walls.
    S.Col=Stone;
    {TArray<FVector> P;P.Add(FVector(NDWest,-NDHM,0));P.Add(FVector(NDWest,NDHM,0));for(int32 K=0;K<=16;K++){const double T=1-K/16.;P.Add(FVector(NDWest,FMath::Lerp(-NDHM,NDHM,T),Arch(T,NDSpring,NDCrown)));}S.Face(P,FVector(1,0,0));}
    for(int32 Sign:{-1,1})Strip(S,FVector2D(NDWest,Sign*NDHM),FVector2D(NDWest,Sign*NDHC),0,NDAisleCrown);
    Rose(G,S,FVector(NDWest+12,0,2560),FVector(0,1,0),FVector(1,0,0),430,StoneLight);Windows++;
    S.Col=StoneLight;S.Box(FVector(NDWest+260,0,1190),FVector(260,NDHM-20,22));for(double Y=-560;Y<=560;Y+=40)S.Tube(FVector(NDWest+515,Y,1212),FVector(NDWest+515,Y,1300),5,6);S.Tube(FVector(NDWest+515,-570,1300),FVector(NDWest+515,570,1300),8,6);
    S.Col=Wood;S.Box(FVector(NDWest+110,0,1780),FVector(90,540,560));
    for(int32 Tw:{-1,0,1}){S.Box(FVector(NDWest+190,Tw*380,2220),FVector(30,110,140));S.Cone(NDWest+190,Tw*380,2360,2480,90,10,4);}
    S.Col=Metal;for(double Y=-500;Y<=500;Y+=30){const double H=380+220*FMath::Abs(FMath::Cos(Y/500*PI*1.5));S.Tube(FVector(NDWest+215,Y,1330),FVector(NDWest+215,Y,1330+H),11,8);S.Cone(NDWest+215,Y,1300,1330,3,11,8);}
    S.Col=Dark;for(double Y:{0.,-1400.,1400.}){const double Hw=Y==0?230:170;TArray<FVector> D;D.Add(FVector(NDWest+4,Y+Hw,0));D.Add(FVector(NDWest+4,Y-Hw,0));for(int32 K=0;K<=12;K++){const double T=K/12.;D.Add(FVector(NDWest+4,FMath::Lerp(Y-Hw,Y+Hw,T),Arch(T,Y==0?560:460,Y==0?820:680)));}S.Face(D,FVector(1,0,0));}
    // ---- Apse: seven piers on a semicircle, chord elevations, fan vault; double ambulatory and chapels.
    auto ApsePt=[&](double R,double T){return FVector2D(NDApseX+R*FMath::Cos(T),R*FMath::Sin(T));};
    const FVector Key(NDApseX,0,NDCrown);
    for(int32 K=0;K<6;K++){
        const double T0=-PI*.5+PI*K/6,T1=-PI*.5+PI*(K+1)/6;const FVector2D A=ApsePt(NDApseR,T0),B=ApsePt(NDApseR,T1),M=(A+B)*.5;
        S.Col=Stone;ArcadeWall(S,A,B,NDArcSpring,NDArcCrown+60,NDTrib0,Rib);
        ArcadeWall(S,A,B,NDTrib0+170,NDTrib0+540,NDTribTop,Rib);
        S.Col=StoneDark;{const FVector2D A2=ApsePt(NDApseR+430,T0),B2=ApsePt(NDApseR+430,T1);Strip(S,A2,B2,NDAisleCrown,NDTribTop+80);for(double Zg:{double(NDTrib0),NDTribTop+80.})S.Face({FVector(A.X,A.Y,Zg),FVector(B.X,B.Y,Zg),FVector(B2.X,B2.Y,Zg),FVector(A2.X,A2.Y,Zg)},FVector(0,0,Zg>NDTrib0?-1:1));}
        S.Col=Stone;Strip(S,A,B,NDTribTop,NDClere);
        {const FVector2D Rd=(M-FVector2D(NDApseX,0)).GetSafeNormal()*14;Lancet(G,A+(B-A)*.08+Rd,B+(B-A)*-.08+Rd,NDClere,NDSpring+60,NDCrown-150);Windows++;
         S.Col=StoneLight;S.Tube(FVector(M.X+Rd.X*.4,M.Y+Rd.Y*.4,NDClere),FVector(M.X+Rd.X*.4,M.Y+Rd.Y*.4,NDCrown-360),6,6);}
        // Fan vault from the key to the chord's wall rib.
        S.Col=Web;for(int32 J=0;J<16;J++){const FVector2D QA=A+(B-A)*(J/16.),QB=A+(B-A)*((J+1)/16.);const FVector P0(QA.X,QA.Y,Arch(J/16.,NDSpring,NDCrown-150)),P1(QB.X,QB.Y,Arch((J+1)/16.,NDSpring,NDCrown-150));S.Face({Key,P0,P1},Down(FVector::CrossProduct(P0-Key,P1-Key)));}
        S.Col=Rib;S.Tube(Key-FVector(0,0,8),FVector(A.X,A.Y,NDSpring),9,6);
        // Ambulatory: two rings of vaults and a ring of radiating chapels with lancets.
        for(int32 H=0;H<2;H++){const double Ts0=FMath::Lerp(T0,T1,H*.5),Ts1=FMath::Lerp(T0,T1,(H+1)*.5);
            PolarVault(S,NDApseX,Ts0,Ts1,NDApseR,NDAmb1,NDAisleSpring,NDAisleCrown,Web,Rib);PolarVault(S,NDApseX,Ts0,Ts1,NDAmb1,NDAmb2,NDAisleSpring,NDAisleCrown,Web,Rib);PolarVault(S,NDApseX,Ts0,Ts1,NDAmb2,NDApseWall,NDAisleSpring-60,NDAisleCrown-60,Web,Rib);
            const FVector2D WA=ApsePt(NDApseWall,Ts0),WB=ApsePt(NDApseWall,Ts1);S.Col=Stone;Strip(S,WA,WB,0,NDAisleCrown);
            const FVector2D In=(FVector2D(NDApseX,0)-(WA+WB)*.5).GetSafeNormal()*8;Lancet(G,WA+(WB-WA)*.25+In,WA+(WB-WA)*.75+In,280,760,1040);Windows++;
            Pier(S,ApsePt(NDAmb1,Ts1).X,ApsePt(NDAmb1,Ts1).Y,46,NDAisleSpring-50,Stone,StoneLight);Pier(S,ApsePt(NDAmb2,Ts1).X,ApsePt(NDAmb2,Ts1).Y,40,NDAisleSpring-110,Stone,StoneLight);Piers+=2;
            const FVector2D C=ApsePt((NDAmb2+NDApseWall)*.5,Ts1);S.Col=Stone;S.Box(FVector(C.X,C.Y,(NDAisleCrown-60)*.5),FVector(22,22,(NDAisleCrown-60)*.5));}
    }
    for(int32 K=1;K<6;K++){const FVector2D P=ApsePt(NDApseR,-PI*.5+PI*K/6);Pier(S,P.X,P.Y,60,NDArcSpring-55,Stone,StoneLight);Piers++;S.Col=StoneLight;S.Tube(FVector(P.X,P.Y,NDArcSpring),FVector(P.X,P.Y,NDSpring),14,8);}
    for(int32 Sign:{-1,1}){S.Col=Web;TArray<FVector> P;P.Add(Key);for(int32 K=0;K<=12;K++){const double Yv=Sign*NDHM*K/12.;P.Add(FVector(NDApseX,Yv,Arch(.5+Yv/(2*NDHM),NDSpring,NDCrown)));}S.Face(P,FVector(-1,0,0));}
    // ---- Furnishings: nave chairs, crossing altar, choir stalls, high altar with Pietà and cross, chandeliers.
    S.Col=Wood;
    for(double X=1750;X<6950;X+=92)for(int32 Sign:{-1,1})for(double Y=130;Y<545;Y+=52){S.Box(FVector(X,Sign*Y,46),FVector(20,20,3));S.Box(FVector(X+19,Sign*Y,76),FVector(2.5,20,30));S.Box(FVector(X,Sign*Y,22),FVector(17,17,22));Chairs++;}
    S.Col=StoneLight;S.Box(FVector(7800,0,18),FVector(520,560,18));S.Col=FLinearColor(.32f,.22f,.10f,.4f);S.Box(FVector(7800,0,130),FVector(110,240,95));
    S.Col=Wood;for(int32 Sign:{-1,1}){S.Box(FVector(9800,Sign*(NDHM-100),95),FVector(1050,55,95));S.Box(FVector(9800,Sign*(NDHM-60),250),FVector(1050,25,70));S.Box(FVector(9800,Sign*(NDHM-100),330),FVector(1050,70,10));}
    S.Col=StoneLight;S.Box(FVector(11050,0,22),FVector(420,520,22));S.Box(FVector(11050,0,130),FVector(70,220,88));
    S.Col=FLinearColor(.62f,.58f,.50f,.6f);S.Cone(11300,0,44,240,70,40,12);S.Cone(11300,0,240,300,26,22,10);S.Cone(11270,0,140,190,55,30,10);
    S.Col=Gold;S.Tube(FVector(11150,0,220),FVector(11150,0,720),7,8);S.Tube(FVector(11150,-110,600),FVector(11150,110,600),7,8);
    auto Chandelier=[&](double X,double Y,double Zc,double Rr,int32 Candles){
        S.Col=Gold;S.Tube(FVector(X,Y,NDCrown-120),FVector(X,Y,Zc),3,6);S.Cone(X,Y,Zc-10,Zc+10,18,18,8);
        for(int32 Ring=0;Ring<2;Ring++){const double R=Rr*(Ring?0.6:1.);const double Z=Zc+Ring*45;for(int32 K=0;K<16;K++){const double A0=2*PI*K/16,A1=2*PI*(K+1)/16;S.Tube(FVector(X+R*FMath::Cos(A0),Y+R*FMath::Sin(A0),Z),FVector(X+R*FMath::Cos(A1),Y+R*FMath::Sin(A1),Z),4,6);}
            for(int32 K=0;K<Candles;K++){const double A=2*PI*(K+Ring*.5)/Candles;const double CX=X+R*FMath::Cos(A),CY=Y+R*FMath::Sin(A);S.Col=Gold;S.Tube(FVector(X,Y,Zc),FVector(CX,CY,Z),2.5,5);S.Col=Wax;S.Tube(FVector(CX,CY,Z),FVector(CX,CY,Z+30),3,6);S.Col=Flame;S.Cone(CX,CY,Z+30,Z+44,3,.2,6);S.Col=Gold;}}
    };
    for(double X:{2300.,3500.,4700.,5900.})Chandelier(X,0,760,150,14);
    // ---- Daylight: soft parallel shafts from the sunlit south clerestory and the south rose, with faint floor pools.
    const FVector Ray=FVector(.30,-.62,-.72).GetSafeNormal();
    auto ToFloor=[&](const FVector& A){return A+Ray*((A.Z-2)/-Ray.Z);};
    auto Ribbon=[&](FVector A,FVector B,double W0,double W1,FLinearColor Col,float Gain){
        const FVector D=(B-A).GetSafeNormal();const FVector S1=FVector::CrossProduct(D,FVector::UpVector).GetSafeNormal(),S2=FVector::CrossProduct(D,S1).GetSafeNormal();
        Bm.Col=FLinearColor(Col.R,Col.G,Col.B,Gain/40.f);
        for(const FVector& Sd:{S1,S2})Bm.Face({A-Sd*(W0*.5),A+Sd*(W0*.5),B+Sd*(W1*.5),B-Sd*(W1*.5)},FVector(0,0,1),{FVector2D(0,0),FVector2D(0,1),FVector2D(1,1),FVector2D(1,0)});
        Bm.Col=FLinearColor(Col.R,Col.G,Col.B,Gain*1.1f/40.f);
        const FVector H=FVector(D.X,D.Y,0).GetSafeNormal(),Hs(-H.Y,H.X,0);const FVector C(B.X,B.Y,2);
        Bm.Face({C-H*220-Hs*W1*.6,C+H*220-Hs*W1*.6,C+H*220+Hs*W1*.6,C-H*220+Hs*W1*.6},FVector(0,0,1),{FVector2D(-1,0),FVector2D(1,0),FVector2D(1,1),FVector2D(-1,1)});
    };
    const FLinearColor Sun(1.f,.90f,.74f),Tints[4]={FLinearColor(.80f,.82f,1.f),FLinearColor(1.f,.80f,.72f),FLinearColor(.92f,.84f,1.f),FLinearColor(1.f,.92f,.78f)};
    int32 Ci=0;
    for(int32 Bi=1;Bi+1<L.Num();Bi++){const double X0=L[Bi],X1=L[Bi+1];if(IsCrossing(X0))continue;const FVector A((X0+X1)*.5,NDHM+14,2300);Ribbon(A,ToFloor(A),240,380,Tints[(Ci++)%4]*Sun,15.f);}
    for(double Off:{-260.,0.,260.}){const FVector A(7800+Off,NDTr-14,2330);Ribbon(A,ToFloor(A),260,420,Tints[(Ci++)%4]*Sun,13.f);}
}

AParisNotreDameInterior::AParisNotreDameInterior(){
    RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("NotreDameRoot"));
    PrimaryActorTick.bCanEverTick=true;PrimaryActorTick.TickInterval=.2f;
    auto MakeMesh=[this](const TCHAR* Name){auto M=CreateDefaultSubobject<UProceduralMeshComponent>(Name);M->SetupAttachment(RootComponent);M->SetCastShadow(false);M->SetVisibility(false);return M;};
    InnerSolid=MakeMesh(TEXT("NotreDameInnerSolid"));InnerGlass=MakeMesh(TEXT("NotreDameInnerGlass"));InnerBeams=MakeMesh(TEXT("NotreDameInnerBeams"));
    auto MakeCamera=[this](const TCHAR* Name,FVector From,FVector To,float Fov){auto C=CreateDefaultSubobject<UCameraComponent>(Name);C->SetupAttachment(RootComponent);C->SetRelativeLocation(From);C->SetRelativeRotation((To-From).Rotation());C->FieldOfView=Fov;C->SetAutoActivate(false);return C;};
    WestCamera=MakeCamera(TEXT("NotreDameWestCamera"),FVector(900,0,170),FVector(11400,0,1300),72);
    CrossingCamera=MakeCamera(TEXT("NotreDameCrossingCamera"),FVector(7800,-1500,170),FVector(7800,2650,2200),84);
    ChoirCamera=MakeCamera(TEXT("NotreDameChoirCamera"),FVector(6600,350,170),FVector(11400,0,1100),72);
    // Warm interior light: nave/choir high lights, crossing, transept arms, apse and aisles (procedural shells are not in the Lumen scene).
    const FVector Spots[]={FVector(900,0,2100),FVector(2100,0,2100),FVector(3300,0,2100),FVector(4500,0,2100),FVector(5700,0,2100),FVector(6900,0,2100),FVector(7800,0,2300),FVector(7800,-1800,1900),FVector(7800,1800,1900),FVector(9300,0,2100),FVector(10500,0,2100),FVector(11700,0,1500),
        FVector(2400,-1350,800),FVector(4800,-1350,800),FVector(2400,1350,800),FVector(4800,1350,800),FVector(9600,-1350,800),FVector(9600,1350,800),FVector(12400,0,800)};
    int32 Idx=0;for(const FVector& P:Spots){const bool Low=P.Z<1000;auto Lc=CreateDefaultSubobject<UPointLightComponent>(*FString::Printf(TEXT("NotreDameInnerLight%d"),Idx++));Lc->SetupAttachment(RootComponent);Lc->SetRelativeLocation(P);Lc->SetLightColor(FLinearColor(1.f,.86f,.68f));Lc->SetIntensityUnits(ELightUnits::Candelas);Lc->SetIntensity(Low?20000:70000);Lc->SetAttenuationRadius(Low?2200:3800);Lc->SetSourceRadius(80);Lc->SetCastShadows(false);Lc->SetVisibility(false);InnerLights.Add(Lc);}
}
bool AParisNotreDameInterior::Initialize(AParisTwinScene* InScene){
    Scene=InScene;if(!Scene||!Scene->SourceFeatureByID(TEXT("osm/way/201611261")))return false;
    // Frame from the OSM footprint: minimum-area rectangle axis (26.98 deg) and the centreline of the
    // west towers/nave (v = 7760 cm), west front at u = 20121 cm; floor at the landmark height.
    const double Ang=FMath::DegreesToRadians(26.98016352182363),U0=20121.09,V0=7760.;const double C=FMath::Cos(Ang),S=FMath::Sin(Ang);
    const FVector Origin(U0*C-V0*S,U0*S+V0*C,-142.049);SetActorLocationAndRotation(Origin,FRotator(0,FMath::RadiansToDegrees(Ang),0));
    auto InMat=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/ParisPhotoreal/SainteChapelle/M_SainteChapelleInterior.M_SainteChapelleInterior"));
    auto InGlass=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/ParisPhotoreal/SainteChapelle/M_SainteChapelleInnerGlass.M_SainteChapelleInnerGlass"));
    auto InBeam=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/ParisPhotoreal/SainteChapelle/M_SainteChapelleBeam.M_SainteChapelleBeam"));
    if(!InMat||!InGlass){UE_LOG(LogTemp,Warning,TEXT("PARIS_NOTREDAME_INTERIOR_MATERIALS_MISSING run Build-ParisChapelle.ps1"));return false;}
    FMesh IS,IG,IB;BuildNotreDame(IS,IG,IB,WindowCount,PierCount,ChairCount);
    IS.Apply(InnerSolid,InMat);IG.Apply(InnerGlass,InGlass);if(InBeam)IB.Apply(InnerBeams,InBeam);bInteriorBuilt=true;
    UE_LOG(LogTemp,Display,TEXT("PARIS_NOTREDAME_INTERIOR_READY windows=%d piers=%d chairs=%d solid_tris=%d glass_tris=%d beam_tris=%d"),WindowCount,PierCount,ChairCount,IS.I.Num()/3,IG.I.Num()/3,IB.I.Num()/3);
    return true;
}
bool AParisNotreDameInterior::IsCameraInside(const FVector& WorldLocation) const {
    const FVector L=GetActorTransform().InverseTransformPosition(WorldLocation);if(L.Z<-20||L.Z>NDCrown)return false;
    if(L.X>NDApseX)return FVector2D(L.X-NDApseX,L.Y).Size()<NDApseWall-15;
    const double Half=(L.X>NDCross0&&L.X<NDCross1)?NDTr-15:NDHC-15;return L.X>NDWest+10&&FMath::Abs(L.Y)<Half;
}
void AParisNotreDameInterior::Tick(float DeltaSeconds){
    Super::Tick(DeltaSeconds);if(!bInteriorBuilt)return;
    auto PC=GetWorld()?GetWorld()->GetFirstPlayerController():nullptr;const bool Inside=PC&&PC->PlayerCameraManager&&IsCameraInside(PC->PlayerCameraManager->GetCameraLocation());
    SetActorTickInterval(Inside?0.f:.2f);
    InnerSolid->SetVisibility(Inside);InnerGlass->SetVisibility(Inside);InnerBeams->SetVisibility(Inside);for(auto L:InnerLights)L->SetVisibility(Inside);
    if(Inside&&PC){if(auto Cam=Cast<AParisTwinCamera>(PC->GetPawn()))if(Cam->bEye&&PC->GetViewTarget()==Cam){
        FVector L=GetActorTransform().InverseTransformPosition(Cam->Target);L.Z=FMath::Clamp(L.Z,60.,NDCrown-300.);
        if(L.X>NDApseX){FVector2D R(L.X-NDApseX,L.Y);if(R.Size()>NDApseWall-80)R=R.GetSafeNormal()*(NDApseWall-80);L.X=NDApseX+R.X;L.Y=R.Y;}
        else{L.X=FMath::Max(L.X,NDWest+80);const double Half=(L.X>NDCross0&&L.X<NDCross1)?NDTr-80:NDHC-80;L.Y=FMath::Clamp(L.Y,-Half,Half);}
        Cam->Target=GetActorTransform().TransformPosition(L);}}
    if(Inside)ApplyParisInteriorLook(GetWorld(),InteriorISO,InteriorShutter);
    if(Inside!=bWasInside){
        bWasInside=Inside;UE_LOG(LogTemp,Display,TEXT("PARIS_NOTREDAME_INSIDE=%d"),Inside?1:0);
        // The GIS cathedral is several stacked volumes whose shared walls and roofs would stand inside the nave,
        // and other city actors (scanned facade, frontages) overlap it: hide everything else while inside.
        if(Inside){HiddenWorld.Reset();for(TActorIterator<AActor> It(GetWorld());It;++It){AActor* A=*It;if(A==this||A->IsHidden()||A->IsA<APawn>()||A->IsA<AController>()||A->IsA<AInfo>()||A->IsA<ALight>()||A->IsA<APostProcessVolume>()||A->IsA<ASkyLight>()||A->IsA<AExponentialHeightFog>()||A->IsA<APlayerCameraManager>()||A->IsA<AHUD>())continue;A->SetActorHiddenInGame(true);HiddenWorld.Add(A);}}
        else{for(auto& A:HiddenWorld)if(A.IsValid())A->SetActorHiddenInGame(false);HiddenWorld.Reset();if(Scene){Scene->ApplyEnvironmentPreset();Scene->ApplyDetailQuality();}}
    }
}
void AParisNotreDameInterior::ActivateView(APlayerController* PC,int32 Index){
    if(!PC||!bInteriorBuilt)return;ViewIndex=FMath::Clamp(Index,1,3);UCameraComponent* Cams[3]={WestCamera,CrossingCamera,ChoirCamera};
    for(int32 I=0;I<3;I++)Cams[I]->SetActive(I==ViewIndex-1);PC->SetViewTarget(this);if(PC->PlayerCameraManager)PC->PlayerCameraManager->SetGameCameraCutThisFrame();
}
void AParisNotreDameInterior::ToggleInterior(AParisTwinController* PC){
    if(!PC||!bInteriorBuilt)return;
    if(bWasInside){PC->Overview();return;}
    PC->ReturnToFree();auto Cam=Cast<AParisTwinCamera>(PC->GetPawn());if(!Cam)return;
    Cam->bEye=true;Cam->Target=GetActorTransform().TransformPosition(FVector(900,0,170));Cam->Yaw=GetActorRotation().Yaw;Cam->Pitch=6;PC->SetViewTarget(Cam);
}
