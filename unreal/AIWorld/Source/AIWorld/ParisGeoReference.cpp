#include "ParisGeoReference.h"
#include "WorldProtocol.h"
#include <cmath>

namespace {
constexpr double LambertSemiMajor=6378137.,Flattening=1./298.257222101;
constexpr double Rad=3.14159265358979323846/180.;
struct FLambert {
    double E=std::sqrt(Flattening*(2-Flattening)),N,F,Rho0;
    double T(double Phi) const {
        const double S=E*std::sin(Phi);
        return std::tan(3.14159265358979323846/4-Phi/2)/std::pow((1-S)/(1+S),E/2);
    }
    double M(double Phi) const {return std::cos(Phi)/std::sqrt(1-E*E*std::pow(std::sin(Phi),2));}
    FLambert(){N=std::log(M(44*Rad)/M(49*Rad))/std::log(T(44*Rad)/T(49*Rad));F=M(44*Rad)/(N*std::pow(T(44*Rad),N));Rho0=LambertSemiMajor*F*std::pow(T(46.5*Rad),N);}
};
const FLambert& Lambert(){static const FLambert L;return L;}
}
FVector2D FParisGeoReference::Project(const FVector2D& LL) {
    const auto& L=Lambert();const double Rho=LambertSemiMajor*L.F*std::pow(L.T(LL.Y*Rad),L.N),Theta=L.N*(LL.X-3)*Rad;
    return FVector2D(700000+Rho*std::sin(Theta),6600000+L.Rho0-Rho*std::cos(Theta));
}
FVector2D FParisGeoReference::Unproject(const FVector2D& EN) {
    const auto& L=Lambert();const double X=EN.X-700000,Y=L.Rho0-(EN.Y-6600000);
    const double T=std::pow(std::hypot(X,Y)/(LambertSemiMajor*L.F),1/L.N);
    double Phi=3.14159265358979323846/2-2*std::atan(T);
    for(int I=0;I<12;I++){const double S=L.E*std::sin(Phi);const double Next=3.14159265358979323846/2-2*std::atan(T*std::pow((1-S)/(1+S),L.E/2));if(std::abs(Next-Phi)<1e-14){Phi=Next;break;}Phi=Next;}
    return FVector2D(3+std::atan2(X,Y)/(L.N*Rad),Phi/Rad);
}
bool FParisGeoReference::Load(const TSharedPtr<FJsonObject>& G) {
    using namespace AIWorld;
    if(!G||String(G,TEXT("projected_crs"))!=TEXT("EPSG:2154")||String(G,TEXT("units"))!=TEXT("cm")||String(G,TEXT("axes"))!=TEXT("X=east, Y=south, Z=up"))return false;
    bool Cesium=true;if(!G->TryGetBoolField(TEXT("cesium_transform_applied"),Cesium)||Cesium)return false;
    const auto& EN=Array(G,TEXT("projected_origin_m"));const auto& LL=Array(G,TEXT("wgs84_origin"));
    if(EN.Num()!=2||LL.Num()!=2)return false;
    OriginProjected=FVector2D(EN[0]->AsNumber(),EN[1]->AsNumber());
    return !OriginProjected.ContainsNaN()&&(OriginProjected-Project(FVector2D(LL[0]->AsNumber(),LL[1]->AsNumber()))).Size()<.01;
}
FVector2D FParisGeoReference::ProjectedFromUE(const FVector& P) const {return OriginProjected+FVector2D(P.X/100,-P.Y/100);}
FVector2D FParisGeoReference::WGS84FromUE(const FVector& P) const {return Unproject(ProjectedFromUE(P));}
FVector FParisGeoReference::ToUE(const FVector2D& LL) const {const auto Delta=Project(LL)-OriginProjected;return FVector(Delta.X*100,-Delta.Y*100,0);}
