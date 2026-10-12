#include "WorldProtocol.h"
#include "Misc/Base64.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace AIWorld {
TSharedPtr<FJsonObject> Parse(const FString& Text) { TSharedPtr<FJsonObject> J; FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), J); return J; }
FString String(const TSharedPtr<FJsonObject>& J, const FString& Key) { FString V; if (J) J->TryGetStringField(Key, V); return V; }
double Number(const TSharedPtr<FJsonObject>& J, const FString& Key, double Fallback) { double V = Fallback; if (J) J->TryGetNumberField(Key, V); return V; }
TSharedPtr<FJsonObject> Object(const TSharedPtr<FJsonObject>& J, const FString& Key) { const TSharedPtr<FJsonObject>* V = nullptr; return J && J->TryGetObjectField(Key, V) ? *V : nullptr; }
const TArray<TSharedPtr<FJsonValue>>& Array(const TSharedPtr<FJsonObject>& J, const FString& Key) { static const TArray<TSharedPtr<FJsonValue>> Empty; const TArray<TSharedPtr<FJsonValue>>* V = nullptr; return J && J->TryGetArrayField(Key, V) ? *V : Empty; }
FVector Position(const TSharedPtr<FJsonObject>& J) { return FVector(Number(J, TEXT("x")), Number(J, TEXT("z")), Number(J, TEXT("y"))) * Unit; }
bool FGrid::Inside(int32 X, int32 Y, int32 Z) const { return X >= 0 && Z >= 0 && Y >= 0 && X < Size && Z < Size && Y < Height; }
int32 FGrid::Index(int32 X, int32 Y, int32 Z) const { return X + Size * (Z + Size * Y); }
uint8 FGrid::Get(int32 X, int32 Y, int32 Z, bool Mask) const { if (!Inside(X,Y,Z)) return 0; const int32 I = Index(X,Y,Z); return Mask && Hidden.Contains(I) ? 0 : Blocks[I]; }
bool FGrid::Load(const TSharedPtr<FJsonObject>& J, FString& Error) {
    const int32 S = Number(J,TEXT("size")), H = Number(J,TEXT("height")), C = Number(J,TEXT("chunk"));
    TArray<uint8> Decoded;
    if (!J || Number(J,TEXT("format")) != 1 || S <= 0 || S > 1024 || H <= 0 || H > 128 || C != 32 || !FBase64::Decode(String(J,TEXT("base")),Decoded) || Decoded.Num() != S*S*H) { Error = TEXT("世界データの形式が不正です。"); return false; }
    for (uint8 B : Decoded) if (B > 8) { Error = TEXT("世界データの素材が不正です。"); return false; }
    Size=S; Height=H; Chunk=C; Base=MoveTemp(Decoded); Blocks=Base; StaticHidden.Reset();
    for (const auto& V : Array(J,TEXT("hidden"))) { const int32 I = V->AsNumber(); if (I>=0 && I<Blocks.Num()) StaticHidden.Add(I); }
    Hidden=StaticHidden; return true;
}
bool FGrid::Edit(const TSharedPtr<FJsonObject>& J) {
    const int32 X=Number(J,TEXT("x"),-1), Y=Number(J,TEXT("y"),-1), Z=Number(J,TEXT("z"),-1), B=Number(J,TEXT("block"),-1);
    if (!Inside(X,Y,Z) || B<0 || B>8) return false; Blocks[Index(X,Y,Z)]=B; return true;
}
void FGrid::Restore(const TArray<TSharedPtr<FJsonValue>>& Edits) { Blocks=Base; for (const auto& V : Edits) Edit(V->AsObject()); }
FLinearColor BlockColor(uint8 B) {
    static const TCHAR* Palette[] = {TEXT("ffffff"),TEXT("849a63"),TEXT("987555"),TEXT("a5aba0"),TEXT("d8c798"),TEXT("987452"),TEXT("76965b"),TEXT("609caa"),TEXT("b9785d")};
    return FLinearColor(FColor::FromHex(Palette[FMath::Min<int32>(B,8)]));
}
void FMesh::Append(const FMesh& M, const FVector& Offset) { const int32 Start=Positions.Num(); for (const auto& P:M.Positions) Positions.Add(P+Offset); Normals.Append(M.Normals); Colors.Append(M.Colors); for (int32 I:M.Indices) Indices.Add(Start+I); }
static bool Floats(const FString& Base64,TArray<float>& Out) { TArray<uint8> Bytes; if (!FBase64::Decode(Base64,Bytes) || Bytes.Num()%4) return false; Out.SetNum(Bytes.Num()/4); if(Bytes.Num()) FMemory::Memcpy(Out.GetData(),Bytes.GetData(),Bytes.Num()); return true; }
bool DecodeMesh(const TSharedPtr<FJsonObject>& J, FMesh& Out) {
    TArray<float> P,N,C; TArray<uint8> IB;
    if (!Floats(String(J,TEXT("positions")),P) || P.Num()%3 || !Floats(String(J,TEXT("normals")),N) || !Floats(String(J,TEXT("colors")),C) || !FBase64::Decode(String(J,TEXT("indices")),IB) || IB.Num()%12) return false;
    if (N.Num()!=0 && N.Num()!=P.Num() || C.Num()!=0 && C.Num()!=P.Num()) return false;
    const FLinearColor Color(FColor::FromHex(String(J,TEXT("color"))));
    for(int32 I=0;I<P.Num();I+=3) {
        if(!FMath::IsFinite(P[I]) || !FMath::IsFinite(P[I+1]) || !FMath::IsFinite(P[I+2])) return false;
        Out.Positions.Add(FVector(P[I],P[I+2],P[I+1])*Unit);
        Out.Normals.Add(N.Num()?FVector(N[I],N[I+2],N[I+1]):FVector::UpVector);
        Out.Colors.Add(C.Num()?FLinearColor(C[I],C[I+1],C[I+2]):Color);
    }
    Out.Indices.SetNum(IB.Num()/4); if(IB.Num()) FMemory::Memcpy(Out.Indices.GetData(),IB.GetData(),IB.Num());
    for(int32 I:Out.Indices) if(I<0 || I>=Out.Positions.Num()) return false;
    return true;
}
void MeshChunk(const FGrid& G, int32 CX, int32 CZ, bool Classic, FMesh& Solid, FMesh& Water) {
    const int32 Dims[]={G.Chunk,G.Height,G.Chunk}, O[]={CX*G.Chunk,0,CZ*G.Chunk};
    for(int32 D=0;D<3;D++) for(int32 Sign : {-1,1}) {
        const int32 U=(D+1)%3,V=(D+2)%3;
        for(int32 Slice=0;Slice<Dims[D];Slice++) {
            TArray<uint8> Mask; Mask.SetNumZeroed(Dims[U]*Dims[V]);
            for(int32 J=0;J<Dims[V];J++) for(int32 I=0;I<Dims[U];I++) {
                int32 P[]={O[0],O[1],O[2]}; P[D]+=Slice;P[U]+=I;P[V]+=J;
                const uint8 A=G.Get(P[0],P[1],P[2],!Classic);P[D]+=Sign;const uint8 B=G.Get(P[0],P[1],P[2],!Classic);
                if(A && (!B || A!=7 && B==7)) Mask[I+J*Dims[U]]=A;
            }
            for(int32 J=0;J<Dims[V];J++) for(int32 I=0;I<Dims[U];) {
                const uint8 B=Mask[I+J*Dims[U]]; if(!B){I++;continue;} int32 W=1,H=1;
                while(I+W<Dims[U] && Mask[I+W+J*Dims[U]]==B)W++;
                while(J+H<Dims[V]) { bool Match=true;for(int32 K=0;K<W;K++)if(Mask[I+K+(J+H)*Dims[U]]!=B){Match=false;break;} if(!Match)break;H++; }
                FMesh& M=B==7?Water:Solid;const int32 Start=M.Positions.Num();
                for(const FIntPoint& UV:{FIntPoint(0,0),FIntPoint(W,0),FIntPoint(W,H),FIntPoint(0,H)}) {
                    int32 P[]={O[0],O[1],O[2]};P[D]+=Slice+(Sign>0?1:0);P[U]+=I+UV.X;P[V]+=J+UV.Y;
                    double Normal[]={0,0,0};Normal[D]=Sign;
                    M.Positions.Add(FVector(P[0],P[2],P[1])*Unit);M.Normals.Add(FVector(Normal[0],Normal[2],Normal[1]));
                    FLinearColor Color=BlockColor(B); if(B==7)Color=FMath::Lerp(FLinearColor(.04f,.16f,.22f),Color,FMath::Clamp((P[1]-2.f)/5.f,0.f,1.f));
                    M.Colors.Add(Color);
                }
                const int32 Pos[]={0,1,2,0,2,3},Neg[]={0,2,1,0,3,2};for(int32 K=0;K<6;K++)M.Indices.Add(Start+(Sign>0?Pos[K]:Neg[K]));
                for(int32 R=0;R<H;R++)for(int32 K=0;K<W;K++)Mask[I+K+(J+R)*Dims[U]]=0; I+=W;
            }
        }
    }
}
static FString Encode(const TSharedRef<FJsonObject>& J) { FString S;FJsonSerializer::Serialize(J,TJsonWriterFactory<>::Create(&S));return S; }
FString SpeedCommand(int32 Speed) { if(Speed!=0 && Speed!=1 && Speed!=5 && Speed!=20)return TEXT("");auto J=MakeShared<FJsonObject>();J->SetStringField(TEXT("type"),TEXT("speed"));J->SetNumberField(TEXT("speed"),Speed);return Encode(J); }
FString TextCommand(const FString& Text,const FString& Resident) {auto J=MakeShared<FJsonObject>();J->SetStringField(TEXT("type"),Resident.IsEmpty()?TEXT("instruction"):TEXT("conversation"));J->SetStringField(TEXT("id"),FGuid::NewGuid().ToString(EGuidFormats::DigitsWithHyphensLower));J->SetStringField(TEXT("text"),Text);if(!Resident.IsEmpty())J->SetStringField(TEXT("residentId"),Resident);return Encode(J);}
FString EditCommand(int32 X,int32 Y,int32 Z,uint8 Block,uint8 Expected) {auto J=MakeShared<FJsonObject>();J->SetStringField(TEXT("type"),TEXT("edit"));J->SetNumberField(TEXT("x"),X);J->SetNumberField(TEXT("y"),Y);J->SetNumberField(TEXT("z"),Z);J->SetNumberField(TEXT("block"),Block);J->SetNumberField(TEXT("expected"),Expected);return Encode(J);}
}
