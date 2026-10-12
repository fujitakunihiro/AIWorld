#include "AIWorldScene.h"
#include "AIWorldResident.h"
#include "AIWorldPlayer.h"
#include "HttpModule.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "WebSocketsModule.h"
#include "Async/Async.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/SkyLight.h"
#include "Components/SkyAtmosphereComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "UnrealClient.h"
#include "Serialization/JsonSerializer.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Sound/SoundWaveProcedural.h"
#include "Kismet/GameplayStatics.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/PostProcessVolume.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/ConfigCacheIni.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
using namespace AIWorld;

AAIWorldScene::AAIWorldScene() {PrimaryActorTick.bCanEverTick=true;RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("WorldRoot"));}
void AAIWorldScene::BeginPlay() {
    Super::BeginPlay();
    GConfig->GetString(TEXT("AIWorld"),TEXT("ServerURL"),URL,GEngineIni);if(!URL.StartsWith(TEXT("http://"))&&!URL.StartsWith(TEXT("https://")))URL=TEXT("http://127.0.0.1:3001");
    FParse::Value(FCommandLine::Get(),TEXT("AIWorldServer="),URL);URL.RemoveFromEnd(TEXT("/"));
    Vertex=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_Vertex.M_Vertex"));
    Color=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_Color.M_Color"));
    Water=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_Water.M_Water"));
    LoadAssets();
    Effects=NewObject<UInstancedStaticMeshComponent>(this);AddInstanceComponent(Effects);Effects->SetupAttachment(RootComponent);Effects->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Sphere.Sphere")));Effects->SetMaterial(0,ColorMaterial(TEXT("#e6b977")));Effects->SetCollisionEnabled(ECollisionEnabled::NoCollision);Effects->SetCastShadow(false);Effects->RegisterComponent();
    Sun=GetWorld()->SpawnActor<ADirectionalLight>();Sun->GetLightComponent()->SetMobility(EComponentMobility::Movable);Sun->SetActorRotation(FRotator(-48,-35,0));
    auto SunComponent=CastChecked<UDirectionalLightComponent>(Sun->GetLightComponent());SunComponent->SetAtmosphereSunLight(true);SunComponent->SetLightSourceAngle(3);Sun->SetActorLocation(FVector(0,0,5000));
    GetWorld()->SpawnActor<ASkyAtmosphere>();
    Sky=GetWorld()->SpawnActor<ASkyLight>();Sky->GetLightComponent()->SetMobility(EComponentMobility::Movable);Sky->SetActorLocation(FVector(19200,19200,100000));Sky->GetLightComponent()->SetIntensity(1.4f);
    Sky->GetLightComponent()->RecaptureSky();
    Fog=GetWorld()->SpawnActor<AExponentialHeightFog>();Fog->GetComponent()->SetFogDensity(.007f);Fog->GetComponent()->SetFogHeightFalloff(.2f);
    auto Post=GetWorld()->SpawnActor<APostProcessVolume>();Post->bUnbound=true;
    auto& P=Post->Settings;P.bOverride_AutoExposureMethod=true;P.AutoExposureMethod=EAutoExposureMethod::AEM_Manual;
    P.bOverride_AutoExposureBias=true;P.AutoExposureBias=10;
    P.bOverride_AmbientOcclusionIntensity=true;P.AmbientOcclusionIntensity=.65f;
    P.bOverride_AmbientOcclusionRadius=true;P.AmbientOcclusionRadius=120;
    P.bOverride_BloomIntensity=true;P.BloomIntensity=.2f;
    P.bOverride_VignetteIntensity=true;P.VignetteIntensity=.18f;
    int32 Desired=1;GConfig->GetInt(TEXT("AIWorld"),TEXT("Quality"),Desired,GEngineIni);FParse::Value(FCommandLine::Get(),TEXT("AIWorldQuality="),Desired);SetQuality(Desired);
    FParse::Value(FCommandLine::Get(),TEXT("AIWorldLight="),LightPreview);
    FetchWorld();
}
void AAIWorldScene::EndPlay(const EEndPlayReason::Type Reason) {
    bEnded=true;if(Socket){Socket->OnClosed().Clear();Socket->OnConnectionError().Clear();Socket->OnMessage().Clear();Socket->OnConnected().Clear();Socket->Close();Socket.Reset();}Super::EndPlay(Reason);
}
void AAIWorldScene::LoadAssets() {
    FString Text;if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("Data/models.json")))){Status=TEXT("モデル未生成: Export-Unreal を実行してください。");return;}
    Assets=Parse(Text);if(!Assets)return;
    for(const auto& V:Array(Assets,TEXT("statics"))) {FMesh M;if(DecodeMesh(V->AsObject(),M))StaticModels.Add(NewMesh(M,Vertex));}
    auto Buildings=Object(Assets,TEXT("buildings"));if(Buildings)for(const auto& Pair:Buildings->Values) {
        auto& Parts=BuildingTemplates.FindOrAdd(FString(Pair.Key.ToView()));for(const auto& V:Pair.Value->AsArray()) {FNativePart Part;Part.Stage=Number(V->AsObject(),TEXT("stage"));if(DecodeMesh(V->AsObject(),Part.Mesh))Parts.Add(MoveTemp(Part));}
    }
    auto Prim=Object(Assets,TEXT("primitives"));if(Prim)for(const auto& Pair:Prim->Values){FMesh M;if(DecodeMesh(Pair.Value->AsObject(),M))Primitives.Add(FString(Pair.Key.ToView()),MoveTemp(M));}
}
UProceduralMeshComponent* AAIWorldScene::NewMesh(const FMesh& M,UMaterialInterface* Material,bool Shadow) {
    auto C=NewObject<UProceduralMeshComponent>(this);AddInstanceComponent(C);C->SetupAttachment(RootComponent);C->RegisterComponent();C->SetCollisionEnabled(ECollisionEnabled::NoCollision);C->SetCastShadow(Shadow);
    C->CreateMeshSection_LinearColor(0,M.Positions,M.Indices,M.Normals,{},M.Colors,{},false);C->SetMaterial(0,Material);return C;
}
UMaterialInstanceDynamic* AAIWorldScene::ColorMaterial(const FString& Hex) {
    if(auto Found=ColorMaterials.Find(Hex))return *Found;
    auto M=UMaterialInstanceDynamic::Create(Color,this);M->SetVectorParameterValue(TEXT("Tint"),FLinearColor(FColor::FromHex(Hex)));ColorMaterials.Add(Hex,M);return M;
}
void AAIWorldScene::FetchWorld() {
    if(bLoading || bEnded)return;bLoading=true;Status=TEXT("保存された世界を読み込んでいます…");
    auto Req=FHttpModule::Get().CreateRequest();Req->SetURL(URL+TEXT("/api/unreal/world"));Req->SetVerb(TEXT("GET"));Req->SetTimeout(30);
    TWeakObjectPtr<AAIWorldScene> Weak(this);
    Req->OnProcessRequestComplete().BindLambda([Weak](FHttpRequestPtr, FHttpResponsePtr Response,bool OK) {
        if(!Weak.IsValid() || Weak->bEnded)return;auto* Self=Weak.Get();Self->bLoading=false;
        if(!OK || !Response || Response->GetResponseCode()!=200){Self->Status=TEXT("シミュレーションに接続できません。起動スクリプトを実行してください。");Self->RetryAt=FPlatformTime::Seconds()+5;return;}
        auto J=Parse(Response->GetContentAsString());FString Error;if(!Self->Grid.Load(J,Error)){Self->Status=Error;Self->RetryAt=FPlatformTime::Seconds()+10;return;}
        const bool First=!Self->bReady;Self->SceneData=J;Self->bReady=true;
        auto Snapshot=Object(J,TEXT("snapshot"));Self->Grid.Restore(Array(Snapshot,TEXT("edits")));Self->Village=Object(Snapshot,TEXT("village"));Self->Time=Number(Snapshot,TEXT("time"));Self->Speed=Number(Snapshot,TEXT("speed"));Self->Revision=Number(Snapshot,TEXT("revision"));
        Self->SyncVillage();Self->RebuildNature();Self->AllDirty();Self->Connect();
        if(First){Self->ReadyAt=FPlatformTime::Seconds();if(auto PC=Cast<AAIWorldPlayer>(Self->GetWorld()->GetFirstPlayerController())){FString View;FParse::Value(FCommandLine::Get(),TEXT("AIWorldView="),View);if(View==TEXT("paris"))PC->FocusParis();else if(View==TEXT("all"))PC->FocusAll();else PC->FocusCamp();}}
        UE_LOG(LogTemp,Display,TEXT("AIWORLD_SCENE_READY size=%d residents=%d revision=%d"),Self->Grid.Size,Array(Self->Village,TEXT("residents")).Num(),Self->Revision);
    });Req->ProcessRequest();
}
void AAIWorldScene::Connect() {
    RetryAt=FPlatformTime::Seconds()+30;
    if(Socket){Socket->OnClosed().Clear();Socket->OnConnectionError().Clear();Socket->OnMessage().Clear();Socket->Close();}
    FString WS=URL;WS.ReplaceInline(TEXT("http://"),TEXT("ws://"));WS.ReplaceInline(TEXT("https://"),TEXT("wss://"));
    TMap<FString,FString> Headers;Headers.Add(TEXT("X-AI-World-Session"),String(SceneData,TEXT("nativeSession")));
    Socket=FWebSocketsModule::Get().CreateWebSocket(WS+TEXT("/native-socket"),TEXT(""),Headers);
    TWeakObjectPtr<AAIWorldScene> Weak(this);
    Socket->OnConnected().AddLambda([Weak]{if(Weak.IsValid()){Weak->bConnected=true;Weak->Failures=0;Weak->Status=TEXT("接続済み · 世界は自動保存されます");UE_LOG(LogTemp,Display,TEXT("AIWORLD_SOCKET_CONNECTED"));}});
    Socket->OnConnectionError().AddLambda([Weak](const FString& Error){if(Weak.IsValid()){Weak->bConnected=false;Weak->Status=TEXT("接続を再試行しています · ")+Error;Weak->RetryAt=FPlatformTime::Seconds()+FMath::Min(30.,2.*++Weak->Failures);if(auto PC=Cast<AAIWorldPlayer>(Weak->GetWorld()->GetFirstPlayerController()))PC->EditRejected();}});
    Socket->OnClosed().AddLambda([Weak](int32,const FString&,bool){if(Weak.IsValid() && !Weak->bEnded){Weak->bConnected=false;Weak->Status=TEXT("接続が切れました。保存済みの世界に再接続します。");Weak->RetryAt=FPlatformTime::Seconds()+3;if(auto PC=Cast<AAIWorldPlayer>(Weak->GetWorld()->GetFirstPlayerController()))PC->EditRejected();}});
    Socket->OnMessage().AddLambda([Weak](const FString& Text){AsyncTask(ENamedThreads::GameThread,[Weak,Text]{if(Weak.IsValid()&&!Weak->bEnded)Weak->Receive(Text);});});
    Socket->Connect();
}
void AAIWorldScene::Send(const FString& Command) {if(!Command.IsEmpty() && bConnected && Socket && Socket->IsConnected())Socket->Send(Command);else Reply=TEXT("接続が戻ってから操作してください。");}
void AAIWorldScene::Receive(const FString& Text) {
    auto J=Parse(Text);if(!J)return;const FString Type=String(J,TEXT("type"));
    if(Type==TEXT("snapshot")) {
        if(!bReady)return;Grid.Restore(Array(J,TEXT("edits")));Village=Object(J,TEXT("village"));Time=Number(J,TEXT("time"));Speed=Number(J,TEXT("speed"));Revision=Number(J,TEXT("revision"));SyncVillage();RebuildNature();AllDirty();
    } else if(Type==TEXT("village")) {Village=Object(J,TEXT("village"));Time=Number(J,TEXT("time"));Speed=Number(J,TEXT("speed"));SyncVillage();}
    else if(Type==TEXT("clock")){Time=Number(J,TEXT("time"));Speed=Number(J,TEXT("speed"));SyncVillage();}
    else if(Type==TEXT("edit") || Type==TEXT("terrain")) {
        const int32 Next=Number(J,TEXT("revision"));if(Next<=Revision)return;
        if(Next!=Revision+1){bConnected=false;FetchWorld();return;}Revision=Next;
        if(Type==TEXT("edit")) {auto Edit=Object(J,TEXT("edit"));DirtyEdit(Edit);if(auto PC=Cast<AAIWorldPlayer>(GetWorld()->GetFirstPlayerController()))PC->EditAccepted(Edit);}
        else for(const auto& V:Array(J,TEXT("edits")))DirtyEdit(V->AsObject());
        SyncMask();NextNature=FPlatformTime::Seconds()+.4;
    } else if(Type==TEXT("instruction-result") || Type==TEXT("conversation-result") || Type==TEXT("error")) {
        Reply=String(J,TEXT("message"));auto Chat=Object(J,TEXT("conversation"));if(Chat)Reply=String(Chat,TEXT("answer"));
        if(Type==TEXT("error"))if(auto PC=Cast<AAIWorldPlayer>(GetWorld()->GetFirstPlayerController()))PC->EditRejected();
    }
}
TSharedPtr<FJsonObject> AAIWorldScene::Resident(const FString& ID) const {for(const auto& V:Array(Village,TEXT("residents"))){auto R=V->AsObject();if(String(R,TEXT("id"))==ID)return R;}return nullptr;}
void AAIWorldScene::DirtyEdit(const TSharedPtr<FJsonObject>& E) {
    if(!Grid.Edit(E))return;const int32 X=Number(E,TEXT("x")),Z=Number(E,TEXT("z")),Count=Grid.Size/Grid.Chunk;
    for(int32 DZ=-1;DZ<=1;DZ++)for(int32 DX=-1;DX<=1;DX++) {const int32 CX=(X+DX)/Grid.Chunk,CZ=(Z+DZ)/Grid.Chunk;if(CX>=0&&CZ>=0&&CX<Count&&CZ<Count)Dirty.Add(CX+CZ*Count);}
}
void AAIWorldScene::AllDirty(){const int32 Count=Grid.Size/Grid.Chunk;for(int32 I=0;I<Count*Count;I++)Dirty.Add(I);}
void AAIWorldScene::BuildChunk(int32 Key) {
    const int32 Count=Grid.Size/Grid.Chunk;FMesh Solid,Sea;MeshChunk(Grid,Key%Count,Key/Count,bClassic,Solid,Sea);
    if(Terrain.Num()<=Key)Terrain.SetNum(Key+1);auto C=Terrain[Key];if(!C){C=NewMesh(Solid,Vertex,Quality>0);Terrain[Key]=C;}
    else C->CreateMeshSection_LinearColor(0,Solid.Positions,Solid.Indices,Solid.Normals,{},Solid.Colors,{},false);
    C->CreateMeshSection_LinearColor(1,Sea.Positions,Sea.Indices,Sea.Normals,{},Sea.Colors,{},false);C->SetMaterial(1,Water);
}
FMesh AAIWorldScene::Primitive(const FString& Name,const FVector& P,const FVector& Scale,const FLinearColor& Tint) const {
    FMesh M;auto T=Primitives.Find(Name);if(!T)return M;M=*T;
    for(auto& V:M.Positions)V=V*Scale+P;for(auto& C:M.Colors)C=Tint;
    for(auto& N:M.Normals)N=FVector(N.X/Scale.X,N.Y/Scale.Y,N.Z/Scale.Z).GetSafeNormal();return M;
}
void AAIWorldScene::DrawStructure(const FString& ID,const FString& Key,const FMesh& M) {
    if(StructureKeys.FindRef(ID)==Key)return;StructureKeys.Add(ID,Key);auto& C=Structures.FindOrAdd(ID);
    if(!C)C=NewMesh(M,Vertex);else C->CreateMeshSection_LinearColor(0,M.Positions,M.Indices,M.Normals,{},M.Colors,{},false);
    C->SetVisibility(!bClassic);
}
void AAIWorldScene::SyncVillage() {
    if(!Village || !Assets)return;TSet<FString> Live;
    const auto& Events=Array(Village,TEXT("events"));if(Events.Num()){auto E=Events.Last()->AsObject();const int32 Latest=Number(E,TEXT("id"));if(LastEvent>=0 && Latest>LastEvent)PlayEvent(String(E,TEXT("kind")));LastEvent=Latest;}
    for(const auto& V:Array(Village,TEXT("residents"))) {
        auto R=V->AsObject();const FString ID=String(R,TEXT("id"));Live.Add(ID);auto& A=Residents.FindOrAdd(ID);if(!A)A=GetWorld()->SpawnActor<AAIWorldResident>();A->Sync(this,R);
    }
    for(auto It=Residents.CreateIterator();It;++It)if(!Live.Contains(It.Key())){It.Value()->Destroy();It.RemoveCurrent();}
    TSet<FString> Active;
    for(const auto& V:Array(Village,TEXT("huts"))) {
        auto H=V->AsObject();const FString ID=String(H,TEXT("id")),Kind=String(H,TEXT("kind")),State=String(H,TEXT("status"));Active.Add(ID);
        const bool Complete=State==TEXT("complete");const double Progress=Complete?1.:Number(H,TEXT("progress"))/FMath::Max(1.,Number(H,TEXT("total")));
        const FVector P=Position(H);auto Crop=Object(H,TEXT("crop"));const double Growth=FMath::RoundToDouble(Number(Crop,TEXT("growth"))*10)/10;
        auto PC=Cast<AAIWorldPlayer>(GetWorld()->GetFirstPlayerController());auto R=PC?Resident(PC->Selected):nullptr;const FVector RP=Position(Object(R,TEXT("position")));
        const bool Cutaway=Kind!=TEXT("farm")&&PC&&PC->bFollow&&PC->View()&&PC->View()->Radius<5000&&R&&RP.X>P.X&&RP.X<P.X+400&&RP.Y>P.Y&&RP.Y<P.Y+400&&RP.Z>=P.Z-20&&RP.Z<P.Z+350;
        const FString Key=FString::Printf(TEXT("%s:%s:%f:%s:%f:%d:%d"),*Kind,*State,Progress,*String(Crop,TEXT("stage")),Growth,(int)Number(Crop,TEXT("remaining")),Cutaway?1:0);
        if(StructureKeys.FindRef(ID)==Key)continue;FMesh Mesh;
        bool Upgrade=false;H->TryGetBoolField(TEXT("upgrading"),Upgrade);
        if(auto Parts=BuildingTemplates.Find(Kind))for(const auto& Part:*Parts)if((Part.Stage<=Progress || Upgrade)&&!(Cutaway&&Part.Stage>=.7))Mesh.Append(Part.Mesh,P);
        if(Kind==TEXT("farm") && Complete && Crop && String(Crop,TEXT("stage"))!=TEXT("fallow")) {
            const int32 N=String(Crop,TEXT("stage"))==TEXT("ripe")?FMath::CeilToInt(Number(Crop,TEXT("remaining"))/32*9):9;
            for(int32 I=0;I<N;I++) {const FVector At=P+FVector(1+I%3,1+I/3,.12)*Unit;Mesh.Append(Primitive(TEXT("grass"),At,FVector(1.2,1.2,.5+Growth*1.5),FLinearColor(.3f,.45f,.18f)));Mesh.Append(Primitive(TEXT("cone"),At+FVector(0,0,80*(.25+Growth*.75)),FVector(.18,.18,.2+Growth*.3),FLinearColor(.65f,.48f,.16f)));}
        }
        DrawStructure(ID,Key,Mesh);
    }
    for(const auto& V:Array(Village,TEXT("nodes"))) {
        auto N=V->AsObject();const FString Kind=String(N,TEXT("kind"));if(Kind==TEXT("wood"))continue;
        const FString ID=String(N,TEXT("id"));Active.Add(ID);const double Fraction=FMath::RoundToDouble(Number(N,TEXT("remaining"))/FMath::Max(1.,Number(N,TEXT("capacity")))*4)/4;
        const FString Key=FString::Printf(TEXT("%s:%.2f"),*Kind,Fraction);if(StructureKeys.FindRef(ID)==Key)continue;FMesh Mesh;
        if(Number(N,TEXT("remaining"))>0){const FVector P=Position(Object(N,TEXT("position")));Mesh=Primitive(Kind==TEXT("stone")?TEXT("rock"):TEXT("round"),P+FVector(0,0,30),FVector(.6,.5,.4)*(.65+Fraction*.35),Kind==TEXT("stone")?BlockColor(3):BlockColor(6));
            if(Kind==TEXT("food"))for(int32 I=0;I<4;I++)Mesh.Append(Primitive(TEXT("round"),P+FVector((I-1.5)*20,36,48),FVector(.11),FLinearColor(.58f,.24f,.17f)));}
        DrawStructure(ID,Key,Mesh);
    }
    for(auto It=Structures.CreateIterator();It;++It)if(!Active.Contains(It.Key())){It.Value()->DestroyComponent();StructureKeys.Remove(It.Key());It.RemoveCurrent();}
    SyncMask();
}
void AAIWorldScene::SyncMask() {
    FString Signature;for(const auto& V:Array(Village,TEXT("huts"))){auto H=V->AsObject();bool Upgrade=false,Step=false;H->TryGetBoolField(TEXT("upgrading"),Upgrade);H->TryGetBoolField(TEXT("entranceStep"),Step);Signature+=FString::Printf(TEXT("%s:%s:%s:%g:%g:%g:%g:%d:%d;"),*String(H,TEXT("id")),*String(H,TEXT("kind")),*String(H,TEXT("status")),Number(H,TEXT("x")),Number(H,TEXT("y")),Number(H,TEXT("z")),Number(H,TEXT("progress")),Upgrade?1:0,Step?1:0);}
    if(Signature==MaskSignature && !Grid.Hidden.IsEmpty())return;MaskSignature=Signature;
    auto Old=Grid.Hidden;Grid.Hidden=Grid.StaticHidden;
    for(const auto& V:Array(Village,TEXT("huts"))) {
        auto H=V->AsObject();const int32 X=Number(H,TEXT("x")),Y=Number(H,TEXT("y")),Z=Number(H,TEXT("z"));const FString Kind=String(H,TEXT("kind"));
        TArray<FIntVector> Cells;
        auto Add=[&](int32 DX,int32 DY,int32 DZ){Cells.Add(FIntVector(X+DX,Y+DY,Z+DZ));};
        if(Kind==TEXT("farm")){for(int32 DX:{0,3})for(int32 DZ:{0,3})Add(DX,0,DZ);}
        else {for(int32 DZ=0;DZ<4;DZ++)for(int32 DX=0;DX<4;DX++)Add(DX,0,DZ);
            for(int32 DY=1;DY<=2;DY++)for(int32 DZ=0;DZ<4;DZ++)for(int32 DX=0;DX<4;DX++)if((DX==0||DX==3||DZ==0||DZ==3)&&!(DZ==3&&DX==1)&&!(DY==2&&(DX==0&&DZ==1||DX==3&&DZ==2)))Add(DX,DY,DZ);
            for(int32 DZ=0;DZ<4;DZ++)for(int32 DX=0;DX<4;DX++)Add(DX,3,DZ);
            for(int32 DZ=0;DZ<4;DZ++)for(int32 DX=1;DX<=2;DX++)Add(DX,4,DZ);
            bool Step=false;H->TryGetBoolField(TEXT("entranceStep"),Step);if(Step)Add(1,-1,4);
        }
        bool Upgrade=false;H->TryGetBoolField(TEXT("upgrading"),Upgrade);
        const int32 N=String(H,TEXT("status"))==TEXT("complete")||Upgrade?Cells.Num():FMath::Min(Cells.Num(),(int32)Number(H,TEXT("progress")));
        for(int32 I=0;I<N;I++){auto P=Cells[I];if(Grid.Inside(P.X,P.Y,P.Z))Grid.Hidden.Add(Grid.Index(P.X,P.Y,P.Z));}
    }
    const int32 Count=Grid.Size/Grid.Chunk;
    auto Mark=[&](int32 I){const int32 X=I%Grid.Size,Z=I/Grid.Size%Grid.Size;for(int32 DZ=-1;DZ<=1;DZ++)for(int32 DX=-1;DX<=1;DX++){int32 CX=FMath::Clamp((X+DX)/Grid.Chunk,0,Count-1),CZ=FMath::Clamp((Z+DZ)/Grid.Chunk,0,Count-1);Dirty.Add(CX+CZ*Count);}};
    for(int32 I:Old)if(!Grid.Hidden.Contains(I))Mark(I);for(int32 I:Grid.Hidden)if(!Old.Contains(I))Mark(I);
}
void AAIWorldScene::RebuildNature() {
    if(!SceneData)return;for(auto C:Nature)C->DestroyComponent();Nature.Reset();
    TMap<FString,UHierarchicalInstancedStaticMeshComponent*> Batches;
    auto Put=[&](const FString& Shape,const FString& Tint,const FVector& P,const FVector& S,bool Shadow=true) {
        const FString Key=Shape+Tint;auto& C=Batches.FindOrAdd(Key);if(!C){C=NewObject<UHierarchicalInstancedStaticMeshComponent>(this);AddInstanceComponent(C);C->SetupAttachment(RootComponent);C->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,*(TEXT("/Engine/BasicShapes/")+Shape+TEXT(".")+Shape)));C->SetMaterial(0,ColorMaterial(Tint));C->SetCollisionEnabled(ECollisionEnabled::NoCollision);C->SetCastShadow(Shadow&&Quality>0);C->RegisterComponent();Nature.Add(C);}C->AddInstance(FTransform(FQuat::Identity,P,S));
    };
    for(const auto& V:Array(SceneData,TEXT("trees"))) {
        auto T=V->AsObject();const auto& Hidden=Array(T,TEXT("hidden"));const auto& Expected=Array(T,TEXT("expected"));bool Valid=Hidden.Num()==Expected.Num();
        for(int32 I=0;I<Hidden.Num()&&Valid;I++){const int32 Cell=Hidden[I]->AsNumber();if(!Grid.Blocks.IsValidIndex(Cell)||Grid.Blocks[Cell]!=Expected[I]->AsNumber())Valid=false;}
        if(!Valid){for(const auto& H:Hidden)Grid.StaticHidden.Remove(H->AsNumber());continue;}
        for(const auto& H:Hidden)Grid.StaticHidden.Add(H->AsNumber());
        const FVector P=Position(T);const double H=Number(T,TEXT("height"));Put(TEXT("Cylinder"),TEXT("#987452"),P+FVector(0,0,H*43),FVector(.5,.5,H*.86));
        if(Number(T,TEXT("variant"))==0) {Put(TEXT("Sphere"),TEXT("#76965b"),P+FVector(0,0,(H+.3)*Unit),FVector(3.8,3.7,3.3));Put(TEXT("Sphere"),TEXT("#8aaa68"),P+FVector(-65,25,(H+1.25)*Unit),FVector(2.5,2.3,2));}
        else for(int32 I=0;I<3;I++)Put(TEXT("Cone"),TEXT("#648673"),P+FVector(0,0,(2.5+I*1.25)*Unit),FVector(3.5-I*.8,3.5-I*.8,2.9-I*.25));
    }
    if(Quality>0)for(const auto& V:Array(SceneData,TEXT("decorations"))) {
        auto D=V->AsObject();const FVector P=Position(D);const double S=Number(D,TEXT("scale"));const FString Kind=String(D,TEXT("kind"));
        if(Quality==1 && Number(D,TEXT("density"))>.04)continue;
        if(Kind==TEXT("rock"))Put(TEXT("Sphere"),TEXT("#a5aba0"),P+FVector(0,0,12),FVector(.66,.6,.5)*S,false);
        else Put(TEXT("Cone"),Kind==TEXT("flower")?TEXT("#e6bda2"):TEXT("#7d9754"),P+FVector(0,0,18),FVector(.12,.12,.36)*S,false);
    }
    for(auto C:Nature)C->SetVisibility(!bClassic);MaskSignature.Reset();SyncMask();
}
void AAIWorldScene::SetClassic(bool Value) {if(bClassic==Value)return;bClassic=Value;for(auto C:StaticModels)if(C)C->SetVisibility(!Value);for(auto C:Nature)if(C)C->SetVisibility(!Value);for(const auto& P:Structures)if(P.Value)P.Value->SetVisibility(!Value);AllDirty();}
void AAIWorldScene::SetQuality(int32 Value) {
    Quality=FMath::Clamp(Value,0,2);auto* PC=GetWorld()->GetFirstPlayerController();if(PC){PC->ConsoleCommand(FString::Printf(TEXT("sg.ShadowQuality %d"),Quality));PC->ConsoleCommand(FString::Printf(TEXT("r.ScreenPercentage %d"),Quality==0?65:Quality==1?80:100));PC->ConsoleCommand(FString::Printf(TEXT("r.AmbientOcclusionLevels %d"),Quality==0?0:Quality));}
    for(auto C:Terrain)if(C)C->SetCastShadow(Quality>0);for(auto C:StaticModels)if(C)C->SetCastShadow(Quality>0);RebuildNature();
}
void AAIWorldScene::PlayEvent(const FString& Kind) {
    const double Now=FPlatformTime::Seconds();if(!bSound||Now<NextSound)return;NextSound=Now+.4;
    const double Frequency=Kind==TEXT("construction")?660.:Kind==TEXT("harvest")?520.:Kind==TEXT("arrival")?880.:330.;
    auto Wave=NewObject<USoundWaveProcedural>();Wave->SetSampleRate(22050);Wave->NumChannels=1;Wave->Duration=.13f;Wave->bLooping=false;
    TArray<int16> Samples;Samples.SetNum(2866);for(int32 I=0;I<Samples.Num();I++){const double T=I/22050.;Samples[I]=FMath::RoundToInt(FMath::Sin(T*Frequency*2*PI)*FMath::Sin(PI*I/Samples.Num())*3000);}
    Wave->QueueAudio(reinterpret_cast<const uint8*>(Samples.GetData()),Samples.Num()*sizeof(int16));UGameplayStatics::SpawnSound2D(this,Wave,.15f);
}
void AAIWorldScene::Tick(float Delta) {
    Super::Tick(Delta);const double Now=FPlatformTime::Seconds();
    FPS=FMath::Lerp(FPS,1./FMath::Max(.0001f,Delta),.025);
    if(!bConnected && !bLoading && Now>RetryAt){RetryAt=Now+10;FetchWorld();}
    for(int32 I=0;I<3&&Dirty.Num();I++){auto It=Dirty.CreateIterator();const int32 Key=*It;It.RemoveCurrent();BuildChunk(Key);}
    if(NextNature>0 && Now>NextNature){NextNature=0;RebuildNature();}
    if(Effects && bReady && Speed>0) {
        if(Now>NextParticles){NextParticles=Now+.25;for(const auto& P:Residents){auto R=Resident(P.Key);const FString Action=String(R,TEXT("action"));if(Particles.Num()<160 && (Action==TEXT("building")||Action==TEXT("gathering")||Action==TEXT("farming"))){const double Angle=Now*5+Particles.Num();Particles.Add({P.Value->GetActorLocation()+FVector(0,35,55),FVector(FMath::Cos(Angle)*20,FMath::Sin(Angle)*20,45),0});}}}
        TArray<FTransform> Instances;for(int32 I=Particles.Num()-1;I>=0;I--){auto& P=Particles[I];P.Age+=Delta;if(P.Age>1){Particles.RemoveAtSwap(I);continue;}P.Position+=P.Velocity*Delta;Instances.Add(FTransform(FQuat::Identity,P.Position,FVector(.08*(1-P.Age))));}Effects->ClearInstances();Effects->AddInstances(Instances,false);
    }
    if(Sun && Now>NextLight){NextLight=Now+.5;const double Minute=LightPreview>=0?LightPreview:FMath::Fmod(Time,1440.),Angle=(Minute-360)/1440*2*PI,Day=FMath::Max(0.,FMath::Sin(Angle));
        Sun->SetActorRotation(FRotator(-FMath::Max(8.,Day*65),FMath::RadiansToDegrees(Angle)-90,0));Sun->GetLightComponent()->SetIntensity(.3+Day*10);
        Sun->GetLightComponent()->SetLightColor(FMath::Lerp(FLinearColor(1.f,.48f,.26f),FLinearColor(1.f,.92f,.78f),(float)FMath::Sqrt(Day)));
        Sky->GetLightComponent()->SetIntensity(.65+Day*.9);
        Fog->GetComponent()->SetFogInscatteringColor(FMath::Lerp(FLinearColor(.09f,.16f,.23f),FLinearColor(.66f,.76f,.78f),(float)Day));
    }
    if(bReady && ReadyAt>0 && !Dirty.Num()) {
        const double Age=Now-ReadyAt;double Duration=0;FParse::Value(FCommandLine::Get(),TEXT("AIWorldBenchmark="),Duration);
        if(!bSkyRecaptured && Age>3){bSkyRecaptured=true;Sky->GetLightComponent()->RecaptureSky();}
        if(Duration>0 && Age>10 && !bBenchmarkDone) {
            FrameTimes.Add(Delta*1000.);
            if(Age>=10+Duration){bBenchmarkDone=true;auto Report=MakeShared<FJsonObject>();double Sum=0;for(double D:FrameTimes)Sum+=D;FrameTimes.Sort();Report->SetNumberField(TEXT("fps"),FrameTimes.Num()*1000./FMath::Max(1.,Sum));Report->SetNumberField(TEXT("frameP95Ms"),FrameTimes[FMath::Clamp(FMath::CeilToInt(FrameTimes.Num()*.95)-1,0,FrameTimes.Num()-1)]);Report->SetNumberField(TEXT("frames"),FrameTimes.Num());Report->SetNumberField(TEXT("quality"),Quality);Report->SetNumberField(TEXT("residents"),Residents.Num());Report->SetNumberField(TEXT("chunks"),Terrain.Num());FString Text;FJsonSerializer::Serialize(Report,TJsonWriterFactory<>::Create(&Text));FFileHelper::SaveStringToFile(Text,*(FPaths::ProjectSavedDir()/TEXT("native-performance.json")));UE_LOG(LogTemp,Display,TEXT("AIWORLD_BENCHMARK %s"),*Text);}
        }
        if(!bCaptured && Age>15 && FParse::Param(FCommandLine::Get(),TEXT("AIWorldCapture"))){bCaptured=true;FScreenshotRequest::RequestScreenshot(FPaths::ProjectSavedDir()/TEXT("Screenshots/native-world.png"),true,false);}
        double ExitAfter=0;FParse::Value(FCommandLine::Get(),TEXT("AIWorldExitAfter="),ExitAfter);if(ExitAfter>0 && Age>ExitAfter)FPlatformMisc::RequestExit(false);
    }
}
