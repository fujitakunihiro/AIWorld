#include "ParisRuntimeMesh.h"
#include "WorldProtocol.h"
#include "Misc/Crc.h"
using namespace AIWorld;

static uint32 ParisU32(const TArray<uint8>& Bytes,int64 Offset){
    const int32 I=int32(Offset);return uint32(Bytes[I])|(uint32(Bytes[I+1])<<8)|(uint32(Bytes[I+2])<<16)|(uint32(Bytes[I+3])<<24);
}
static float ParisFloat(const TArray<uint8>& Bytes,int64 Offset){const uint32 Bits=ParisU32(Bytes,Offset);float Value;FMemory::Memcpy(&Value,&Bits,4);return Value;}
static bool ParisSize(const TSharedPtr<FJsonObject>& J,const TCHAR* Key,int64& Value){
    double D;if(!J.IsValid()||!J->TryGetNumberField(Key,D)||!FMath::IsFinite(D)||D<0||D>512.*1024*1024||FMath::FloorToDouble(D)!=D)return false;Value=int64(D);return true;
}
bool ValidateParisMeshBlob(const TSharedPtr<FJsonObject>& Metadata,const TArray<uint8>& Blob,FString& Error){
    int64 Expected=0,Count=0;
    if(!Metadata.IsValid()||String(Metadata,TEXT("file"))!=TEXT("paris-digital-twin-meshes.bin")||String(Metadata,TEXT("format"))!=TEXT("paris_mesh_le_v1")||!ParisSize(Metadata,TEXT("bytes"),Expected)||!ParisSize(Metadata,TEXT("mesh_count"),Count)||Expected!=Blob.Num()||Blob.Num()<16||FMemory::Memcmp(Blob.GetData(),"PARISM01",8)||ParisU32(Blob,8)!=1||ParisU32(Blob,12)!=Count||Number(Metadata,TEXT("vertex_stride"))!=28){Error=TEXT("Invalid Paris runtime mesh header/size");return false;}
    const FString CRC=FString::Printf(TEXT("%08x"),FCrc::MemCrc32(Blob.GetData(),Blob.Num()));
    if(!CRC.Equals(String(Metadata,TEXT("crc32")),ESearchCase::IgnoreCase)){Error=TEXT("Paris runtime mesh checksum mismatch; run offline prepare");return false;}return true;
}
bool ReadParisMeshArrays(const TSharedPtr<FJsonObject>& Object,const TArray<uint8>& Blob,FParisMeshArrays& Out,FString& Error){
    Out=FParisMeshArrays();auto Buffer=AIWorld::Object(Object,TEXT("mesh_buffer"));
    if(Buffer.IsValid()){
        int64 Offset=0,Vertices=0,Indices=0,Bytes=0;
        if(!ParisSize(Buffer,TEXT("offset"),Offset)||!ParisSize(Buffer,TEXT("vertex_count"),Vertices)||!ParisSize(Buffer,TEXT("index_count"),Indices)||!ParisSize(Buffer,TEXT("byte_length"),Bytes)||Offset<16||Vertices<1||Vertices>1000000||Indices>6000000||Indices%3||Bytes!=Vertices*28+Indices*4||Offset+Bytes>Blob.Num()){Error=TEXT("Invalid Paris runtime mesh range");return false;}
        Out.Positions.Reserve(int32(Vertices));Out.Normals.Reserve(int32(Vertices));Out.Colors.Reserve(int32(Vertices));Out.Indices.Reserve(int32(Indices));
        for(int64 I=0;I<Vertices;I++){const int32 P=int32(Offset+I*28);const FVector Position(ParisFloat(Blob,P),ParisFloat(Blob,P+4),ParisFloat(Blob,P+8)),Normal(ParisFloat(Blob,P+12),ParisFloat(Blob,P+16),ParisFloat(Blob,P+20));
            if(Position.ContainsNaN()||Normal.ContainsNaN()){Error=TEXT("Nonfinite Paris runtime vertex");return false;}Out.Positions.Add(Position);Out.Normals.Add(Normal);Out.Colors.Add(FLinearColor(FColor(Blob[P+24],Blob[P+25],Blob[P+26],Blob[P+27])));
        }
        for(int64 I=0;I<Indices;I++){const uint32 Index=ParisU32(Blob,Offset+Vertices*28+I*4);if(Index>=Vertices){Error=TEXT("Paris runtime index out of range");return false;}Out.Indices.Add(int32(Index));}return true;
    }
    // Explicit legacy fallback for comparison and older offline snapshots.
    const auto& Points=Array(Object,TEXT("positions_cm"));const auto& Normals=Array(Object,TEXT("normals"));const auto& Colors=Array(Object,TEXT("vertex_colors"));const auto& Indices=Array(Object,TEXT("indices"));
    if(Points.IsEmpty()||Points.Num()>1000000||Points.Num()!=Normals.Num()||Indices.Num()%3){Error=TEXT("Invalid legacy Paris mesh arrays");return false;}
    const FLinearColor Color(FColor::FromHex(String(Object,TEXT("color"))));
    for(int32 I=0;I<Points.Num();I++){
        const auto& P=Points[I]->AsArray();const auto& N=Normals[I]->AsArray();if(P.Num()!=3||N.Num()!=3){Error=TEXT("Invalid legacy Paris vertex");return false;}
        const FVector Position(P[0]->AsNumber(),P[1]->AsNumber(),P[2]->AsNumber()),Normal(N[0]->AsNumber(),N[1]->AsNumber(),N[2]->AsNumber());
        if(Position.ContainsNaN()||Normal.ContainsNaN()){Error=TEXT("Nonfinite legacy Paris vertex");return false;}Out.Positions.Add(Position);Out.Normals.Add(Normal);Out.Colors.Add(Colors.IsValidIndex(I)?FLinearColor(FColor::FromHex(Colors[I]->AsString())):Color);
    }
    for(const auto& I:Indices){const double N=I->AsNumber();if(!FMath::IsFinite(N)||N<0||N>=Points.Num()||FMath::FloorToDouble(N)!=N){Error=TEXT("Invalid legacy Paris index");return false;}Out.Indices.Add(int32(N));}return true;
}
