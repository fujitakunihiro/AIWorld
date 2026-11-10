#pragma once
// Small procedural-mesh builder shared by the landmark interiors (Sainte-Chapelle, Notre-Dame).
// Vertex colour RGB is the base colour and vertex alpha the roughness / material flag
// (see bake-paris-chapelle-interior.py); units are cm in the actor's local frame.
#include "CoreMinimal.h"
#include "ProceduralMeshComponent.h"
#include "KismetProceduralMeshLibrary.h"
#include "Materials/MaterialInterface.h"

struct FParisProcMesh {
    TArray<FVector> V,N;TArray<int32> I;TArray<FVector2D> UV;TArray<FProcMeshTangent> T;TArray<FLinearColor> C;FLinearColor Col=FLinearColor::White;
    // Convex (or star-shaped from the first point) polygon, fan-triangulated from Points[0].
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
// Graceful pointed arch profile (inferred stone profile): T in [0,1] runs across the span.
inline FVector ParisArchPoint(double X,double Y,double Base,double Width,double Rise,double T){const double H=Width*.5;const double XX=(2*T-1)*H;const double Height=Rise*(1-FMath::Pow(FMath::Abs(XX)/H,1.7));return FVector(X+XX,Y,Base+Height);}
