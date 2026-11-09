#include "ParisMinimap.h"
#include "ParisDigitalTwin.h"
#include "ParisWalker.h"
#include "WorldProtocol.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "CanvasItem.h"
#include "Camera/PlayerCameraManager.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
using namespace AIWorld;
namespace {
struct FMapLayer{TArray<FVector2D> Points;FLinearColor Color;TArray<FCanvasUVTri> Pixels;};
struct FMapData{FVector4 Bounds;TArray<FMapLayer> Layers;TArray<FVector> Landmarks;FVector2D CachedOrigin=FVector2D::ZeroVector;float CachedSize=-1;int32 Triangles=0;};
TMap<TWeakObjectPtr<AParisTwinScene>,FMapData> Maps;
TMap<TWeakObjectPtr<AHUD>,bool> Hidden;
void Tile(UCanvas* C,const FVector2D& P,const FVector2D& Size,const FLinearColor& Color){FCanvasTileItem Item(P,Size,Color);Item.BlendMode=SE_BLEND_Translucent;C->Canvas->DrawItem(Item);}
void Label(UCanvas* C,const FString& Text,float X,float Y,float Scale=1){FCanvasTextItem Item(FVector2D(X,Y),FText::FromString(Text),GEngine->GetSmallFont(),FLinearColor::White);Item.Scale=FVector2D(Scale,Scale);C->Canvas->DrawItem(Item);}
FCanvasUVTri Triangle(const FVector2D& A,const FVector2D& B,const FVector2D& C,const FLinearColor& Color){FCanvasUVTri T;T.V0_Pos=A;T.V1_Pos=B;T.V2_Pos=C;T.V0_UV=T.V1_UV=T.V2_UV=FVector2D::ZeroVector;T.V0_Color=T.V1_Color=T.V2_Color=Color;return T;}
}
FVector2D ParisMapPoint(const FVector& P,const FVector4& B){return FVector2D((P.X-B.X)/(B.Z-B.X),(P.Y-B.Y)/(B.W-B.Y));}
FParisMapRect ParisMinimapRect(AHUD* HUD,float Width,float Height){
    if(!HUD||Width<480||Height<320||FParse::Param(FCommandLine::Get(),TEXT("ParisTwinNoMinimap"))||Hidden.FindRef(HUD))return {};
    const float Size=FMath::Clamp(FMath::Min(Width*.23f,Height*.32f),128.f,224.f);return {Width-Size-36,12,Size};
}
void ToggleParisMinimap(AHUD* HUD){if(!HUD)return;for(auto It=Hidden.CreateIterator();It;++It)if(!It.Key().IsValid())It.RemoveCurrent();Hidden.Add(HUD,!Hidden.FindRef(HUD));}
void InitializeParisMinimap(AParisTwinScene* Scene,const TSharedPtr<FJsonObject>& Source){
    for(auto It=Maps.CreateIterator();It;++It)if(!It.Key().IsValid())It.RemoveCurrent();if(!Scene||!Source)return;
    FString Text;TSharedPtr<FJsonObject> Data;if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("Data/paris-minimap.json")))||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Data)||!Data)return;
    if(String(Data,TEXT("format"))!=TEXT("paris_vector_minimap_v1")||String(Data,TEXT("source_scene_sha256"))!=String(Source,TEXT("source_scene_sha256")))return;
    FParisGeoReference Reference;if(!Reference.Load(Object(Data,TEXT("georeference")))||(Reference.OriginProjected-Scene->GeoReference.OriginProjected).Size()>.001)return;
    const auto& B=Array(Data,TEXT("bounds_cm"));if(B.Num()!=4)return;FMapData Map;Map.Bounds=FVector4(B[0]->AsNumber(),B[1]->AsNumber(),B[2]->AsNumber(),B[3]->AsNumber());if(Map.Bounds.Z<=Map.Bounds.X||Map.Bounds.W<=Map.Bounds.Y)return;
    for(auto V:Array(Data,TEXT("groups"))){auto J=V->AsObject();const auto& Color=Array(J,TEXT("color"));if(Color.Num()!=3)return;FMapLayer Layer;Layer.Color=FLinearColor(FColor(Color[0]->AsNumber(),Color[1]->AsNumber(),Color[2]->AsNumber()));
        for(auto T:Array(J,TEXT("triangles_cm"))){if(T->AsArray().Num()!=3)return;for(auto P:T->AsArray()){const auto& A=P->AsArray();if(A.Num()!=2)return;FVector2D Point(A[0]->AsNumber(),A[1]->AsNumber());if(Point.ContainsNaN())return;Layer.Points.Add(Point);}Map.Triangles++;}Map.Layers.Add(MoveTemp(Layer));}
    for(auto V:Array(Data,TEXT("landmarks"))){const auto& P=Array(V->AsObject(),TEXT("ue_cm"));if(P.Num()==3)Map.Landmarks.Add(FVector(P[0]->AsNumber(),P[1]->AsNumber(),P[2]->AsNumber()));}
    Maps.Add(Scene,MoveTemp(Map));
}
FVector ParisMapObserver(AParisTwinScene* S,FRotator& Direction,FString& Name){
    FVector P=S->SceneCentre;auto PC=S->GetWorld()->GetFirstPlayerController();Name=TEXT("カメラ");if(!PC)return P;PC->GetPlayerViewPoint(P,Direction);
    if(auto Walker=Cast<AParisWalker>(PC->GetPawn())){P=Walker->GetActorLocation();Name=TEXT("現在地");}
    else if(auto Camera=Cast<AParisTwinCamera>(PC->GetViewTarget()))if(!Camera->bEye){P=Camera->Target;Name=TEXT("視点中心");}
    return P;
}
void DrawParisMinimap(AHUD* HUD,UCanvas* C,AParisTwinScene* S){
    if(!C||!C->Canvas||!S)return;auto R=ParisMinimapRect(HUD,C->SizeX,C->SizeY);if(!R.IsValid())return;
    Tile(C,{R.X,R.Y},{R.Size+20,R.Size+65},FLinearColor(.012f,.025f,.038f,.94f));Label(C,TEXT("PARIS   /   MAP [8]"),R.X+10,R.Y+7);
    auto Map=Maps.Find(S);if(!Map){Label(C,TEXT("地図データ未生成"),R.X+10,R.Y+35);return;}
    const FVector2D Origin(R.X+10,R.Y+29);Tile(C,Origin,{R.Size,R.Size},FLinearColor(.025f,.043f,.055f));
    if(Map->CachedOrigin!=Origin||Map->CachedSize!=R.Size){
        for(auto& Layer:Map->Layers){Layer.Pixels.Reset();for(int32 I=0;I<Layer.Points.Num();I+=3){FVector2D P[3];for(int32 J=0;J<3;J++)P[J]=Origin+ParisMapPoint(FVector(Layer.Points[I+J],0),Map->Bounds)*R.Size;Layer.Pixels.Add(Triangle(P[0],P[1],P[2],Layer.Color));}}
        Map->CachedOrigin=Origin;Map->CachedSize=R.Size;
    }
    for(const auto& Layer:Map->Layers)if(!Layer.Pixels.IsEmpty())C->K2_DrawTriangle(nullptr,Layer.Pixels);
    for(int32 I=0;I<Map->Landmarks.Num();I++){auto P=Origin+ParisMapPoint(Map->Landmarks[I],Map->Bounds)*R.Size;Tile(C,P-FVector2D(3,3),{6,6},FLinearColor(1.f,.62f,.12f));Label(C,FString::FromInt(I+1),P.X+4,P.Y-5,.8f);}
    FRotator Rotation;FString Name;const FVector Observer=ParisMapObserver(S,Rotation,Name);auto UV=ParisMapPoint(Observer,Map->Bounds);const bool Outside=UV.X<0||UV.X>1||UV.Y<0||UV.Y>1;
    UV.X=FMath::Clamp(UV.X,.035,.965);UV.Y=FMath::Clamp(UV.Y,.035,.965);const auto P=Origin+UV*R.Size;const double A=FMath::DegreesToRadians(Rotation.Yaw);const FVector2D Forward(FMath::Cos(A),FMath::Sin(A)),Right(-Forward.Y,Forward.X);
    TArray<FCanvasUVTri> Arrow;Arrow.Add(Triangle(P+Forward*10,P-Forward*7+Right*6,P-Forward*7-Right*6,FLinearColor::Black));Arrow.Add(Triangle(P+Forward*7,P-Forward*5+Right*4,P-Forward*5-Right*4,FLinearColor(.12f,.95f,1.f)));C->K2_DrawTriangle(nullptr,Arrow);
    Label(C,TEXT("N ↑"),R.X+R.Size-24,R.Y+32,.85f);const float Scale=10000.f/(Map->Bounds.Z-Map->Bounds.X)*R.Size;Tile(C,{Origin.X+5,Origin.Y+R.Size-10},{Scale,2},FLinearColor::White);Label(C,TEXT("100m"),Origin.X+5,Origin.Y+R.Size-25,.7f);
    Label(C,Name+(Outside?TEXT("（範囲外）"):TEXT("")),R.X+10,R.Y+R.Size+34,.85f);Label(C,TEXT("1 ND   2 Chapelle   3 St-Michel"),R.X+10,R.Y+R.Size+49,.68f);
}
void AddParisMinimapStats(AParisTwinScene* S,const TSharedPtr<FJsonObject>& Report){auto Map=Maps.Find(S);Report->SetBoolField(TEXT("minimap_ready"),Map!=nullptr);Report->SetNumberField(TEXT("minimap_triangles"),Map?Map->Triangles:0);FRotator R;FString Name;auto P=ParisMapObserver(S,R,Name);Report->SetStringField(TEXT("minimap_observer"),Name);Report->SetNumberField(TEXT("minimap_x_cm"),P.X);Report->SetNumberField(TEXT("minimap_y_cm"),P.Y);}
