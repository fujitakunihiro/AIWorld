#include "ParisShopfrontSigns.h"
#include "ParisDigitalTwin.h"
#include "ParisStreetMeshes.h"
#include "WorldProtocol.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Camera/PlayerCameraManager.h"
#include "GameFramework/PlayerController.h"
#include "Materials/MaterialInterface.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
using namespace AIWorld;

namespace {
FString ShopCategory(const FString& Category){
    if(Category==TEXT("cafe"))return TEXT("CAFÉ");
    if(Category==TEXT("restaurant"))return TEXT("RESTAURANT");
    if(Category==TEXT("bar"))return TEXT("BAR");
    if(Category==TEXT("bakery"))return TEXT("BOULANGERIE");
    if(Category==TEXT("books"))return TEXT("LIBRAIRIE");
    if(Category==TEXT("florist"))return TEXT("FLEURISTE");
    if(Category==TEXT("clothes"))return TEXT("MODE");
    if(Category==TEXT("gift"))return TEXT("BOUTIQUE");
    if(Category==TEXT("fast_food"))return TEXT("RESTAURATION");
    if(Category==TEXT("supermarket"))return TEXT("SUPERMARCHÉ");
    if(Category==TEXT("convenience"))return TEXT("ALIMENTATION");
    return TEXT("COMMERCE");
}
bool ReadPosition(const TSharedPtr<FJsonValue>& Value,FVector& Position){
    if(!Value.IsValid()||Value->Type!=EJson::Array)return false;const auto& A=Value->AsArray();
    double X,Y,Z;if(A.Num()!=3||!A[0]->TryGetNumber(X)||!A[1]->TryGetNumber(Y)||!A[2]->TryGetNumber(Z)||!FMath::IsFinite(X)||!FMath::IsFinite(Y)||!FMath::IsFinite(Z))return false;
    Position=FVector(X,Y,Z);return true;
}
UStaticMesh* BuildProduceMesh(UObject* Outer,UMaterialInterface* Material,const TCHAR* Color=TEXT("#80a640")){
    auto Model=MakeShared<FJsonObject>();TArray<TSharedPtr<FJsonValue>> Positions,Normals,Indices;
    constexpr int32 Rings=8,Segments=12;
    auto VectorValue=[](double X,double Y,double Z){TArray<TSharedPtr<FJsonValue>> A;A.Add(MakeShared<FJsonValueNumber>(X));A.Add(MakeShared<FJsonValueNumber>(Y));A.Add(MakeShared<FJsonValueNumber>(Z));return MakeShared<FJsonValueArray>(A);};
    for(int32 R=0;R<=Rings;R++)for(int32 S=0;S<Segments;S++){
        const double Lat=PI*(double(R)/Rings-.5),Lon=2*PI*S/Segments;const FVector N(FMath::Cos(Lat)*FMath::Cos(Lon),FMath::Cos(Lat)*FMath::Sin(Lon),FMath::Sin(Lat));
        Positions.Add(VectorValue(N.X*50,N.Y*50,N.Z*50));Normals.Add(VectorValue(N.X,N.Y,N.Z));
    }
    for(int32 R=0;R<Rings;R++)for(int32 S=0;S<Segments;S++){
        const int32 A=R*Segments+S,B=R*Segments+(S+1)%Segments,C=B+Segments,D=A+Segments;
        // The poles have coincident vertices; omit degenerate triangles there.
        if(R>0)for(int32 I:{A,B,D})Indices.Add(MakeShared<FJsonValueNumber>(I));
        if(R<Rings-1)for(int32 I:{B,C,D})Indices.Add(MakeShared<FJsonValueNumber>(I));
    }
    Model->SetArrayField(TEXT("positions_cm"),Positions);Model->SetArrayField(TEXT("normals"),Normals);Model->SetArrayField(TEXT("indices"),Indices);Model->SetStringField(TEXT("color"),Color);
    return BuildParisStreetMesh(Outer,Model,Material);
}
UStaticMesh* BuildBookMesh(UObject* Outer,UMaterialInterface* Material){
    auto Model=MakeShared<FJsonObject>();TArray<TSharedPtr<FJsonValue>> Positions,Normals,Indices;
    auto Push=[](TArray<TSharedPtr<FJsonValue>>& A,const FVector& V){TArray<TSharedPtr<FJsonValue>> N;N.Add(MakeShared<FJsonValueNumber>(V.X));N.Add(MakeShared<FJsonValueNumber>(V.Y));N.Add(MakeShared<FJsonValueNumber>(V.Z));A.Add(MakeShared<FJsonValueArray>(N));};
    const FVector V[8]={{-50,-50,-50},{50,-50,-50},{50,50,-50},{-50,50,-50},{-50,-50,50},{50,-50,50},{50,50,50},{-50,50,50}};
    const int32 F[6][4]={{0,3,2,1},{4,5,6,7},{0,1,5,4},{1,2,6,5},{2,3,7,6},{3,0,4,7}};
    for(const auto& Face:F){const FVector Normal=FVector::CrossProduct(V[Face[1]]-V[Face[0]],V[Face[2]]-V[Face[0]]).GetSafeNormal();const int32 Base=Positions.Num();for(int32 I:Face){Push(Positions,V[I]);Push(Normals,Normal);}for(int32 I:{0,1,2,0,2,3})Indices.Add(MakeShared<FJsonValueNumber>(Base+I));}
    Model->SetArrayField(TEXT("positions_cm"),Positions);Model->SetArrayField(TEXT("normals"),Normals);Model->SetArrayField(TEXT("indices"),Indices);Model->SetStringField(TEXT("color"),TEXT("#47687c"));return BuildParisStreetMesh(Outer,Model,Material);
}
}
AParisShopfrontSigns::AParisShopfrontSigns(){
    RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("ShopfrontRoot"));
    PrimaryActorTick.bCanEverTick=true;
}
bool AParisShopfrontSigns::Initialize(AParisTwinScene* InScene,const TSharedPtr<FJsonObject>& Data){
    Scene=InScene;if(!Scene||!Data.IsValid())return false;
    auto Cube=LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cube.Cube"));
    auto Wood=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisWood.M_ParisWood"));
    auto Iron=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisCastIron.M_ParisCastIron"));
    auto Cloth=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Materials/M_ParisCloth.M_ParisCloth"));
    if(!Cube||!Wood||!Iron||!Cloth)return false;
    auto Sphere=BuildProduceMesh(this,Cloth);auto Blossom=BuildProduceMesh(this,Cloth,TEXT("#ed5680"));auto Bread=BuildProduceMesh(this,Cloth,TEXT("#dfaa58"));auto Book=BuildBookMesh(this,Cloth);if(!Sphere||!Blossom||!Bread||!Book)return false;
    TArray<FTransform> Transforms,Boards,Crates,Fruit,Pots,Stems,Blossoms,FlowerCentres,BakeryShelves,Loaves,BookShelves,Books;
    for(const auto& Value:Array(Data,TEXT("pick_features"))){auto Item=Value->AsObject();if(String(Item,TEXT("kind"))!=TEXT("business"))continue;
        const auto Props=Object(Item,TEXT("properties"));FVector Position;
        if(!ReadPosition(Item->TryGetField(TEXT("point_cm")),Position))continue;
        double Yaw=Number(Props,TEXT("facade_yaw_degrees"));if(!FMath::IsFinite(Yaw))continue;
        FString Name=String(Props,TEXT("name"));Name.TrimStartAndEndInline();
        if(Name.IsEmpty())continue;
        Name.ReplaceInline(TEXT("\n"),TEXT(" "));Name.ReplaceInline(TEXT("\r"),TEXT(" "));
        if(Name.Len()>30)Name=Name.Left(27)+TEXT("...");
        const FRotator Rotation(0,Yaw,0);const FVector Out=Rotation.RotateVector(FVector(0,1,0));
        const FString Category=String(Props,TEXT("category"));const bool Restaurant=Category==TEXT("restaurant"),Grocery=Category==TEXT("supermarket")||Category==TEXT("convenience");
        FShop Shop{Position+Out*14+FVector(0,0,320),Yaw,Name,ShopCategory(Category),Restaurant,Grocery};
        Shops.Add(Shop);Transforms.Emplace(Rotation,Shop.Position,FVector(2.9,.10,.48));
        const FVector Along=Rotation.RotateVector(FVector(1,0,0));
        if(Restaurant)Boards.Emplace(Rotation,Position+Along*112+Out*22+FVector(0,0,145),FVector(.50,.08,.78));
        if(Grocery){
            Crates.Emplace(Rotation,Position-Along*101+Out*37+FVector(0,0,52),FVector(.85,.36,.22));
            for(int32 X=0;X<3;X++)for(int32 Y=0;Y<2;Y++)Fruit.Emplace(Rotation,Position+Along*(-125+X*24)+Out*(28+Y*17)+FVector(0,0,68),FVector(.16));
        }
        if(Category==TEXT("florist")){
            for(int32 Pot=0;Pot<3;Pot++){
                const double X=-130+Pot*40;Pots.Emplace(Rotation,Position+Along*X+Out*38+FVector(0,0,48),FVector(.30,.29,.30));
                for(int32 Flower=0;Flower<3;Flower++){
                    const double Offset=(Flower-1)*8,Height=77+(Flower%2)*8;const FVector Base=Position+Along*(X+Offset)+Out*(34+Flower*4);
                    Stems.Emplace(Rotation,Base+FVector(0,0,Height-10),FVector(.025,.025,.30));const FVector Head=Base+FVector(0,0,Height+5);
                    for(int32 Petal=0;Petal<5;Petal++){const double Angle=2*PI*Petal/5;Blossoms.Emplace(Rotation,Head+Along*(4.5*FMath::Cos(Angle))+FVector(0,0,4.5*FMath::Sin(Angle)),FVector(.07,.04,.07));}
                    FlowerCentres.Emplace(Rotation,Head+Out*3,FVector(.05));
                }
            }
        }
        if(Category==TEXT("bakery")){
            BakeryShelves.Emplace(Rotation,Position-Along*101+Out*37+FVector(0,0,52),FVector(.90,.36,.22));
            for(int32 I=0;I<4;I++)Loaves.Emplace(Rotation,Position+Along*(-126+I*17)+Out*38+FVector(0,0,68),FVector(.10,.22,.10));
        }
        if(Category==TEXT("books")){
            BookShelves.Emplace(Rotation,Position-Along*101+Out*28+FVector(0,0,74),FVector(.90,.25,.06));
            for(int32 I=0;I<5;I++)Books.Emplace(Rotation,Position+Along*(-129+I*14)+Out*29+FVector(0,0,92),FVector(.10,.12,.32));
        }
    }
    if(Shops.IsEmpty()||Shops.Num()>2000)return false;
    Panels=NewObject<UHierarchicalInstancedStaticMeshComponent>(this);AddInstanceComponent(Panels);Panels->SetupAttachment(RootComponent);
    Panels->SetStaticMesh(Cube);Panels->SetMaterial(0,Wood);Panels->SetCollisionEnabled(ECollisionEnabled::NoCollision);Panels->SetCanEverAffectNavigation(false);
    Panels->SetCastShadow(false);Panels->SetCullDistances(5000,7500);Panels->ComponentTags.Add(TEXT("ParisShopfrontPanels"));Panels->RegisterComponent();Panels->AddInstances(Transforms,false,false,false);
    auto AddVisual=[&](UStaticMesh* Mesh,UMaterialInterface* Material,const TArray<FTransform>& Items,const TCHAR* Tag){
        auto Group=NewObject<UHierarchicalInstancedStaticMeshComponent>(this);AddInstanceComponent(Group);Group->SetupAttachment(RootComponent);Group->SetStaticMesh(Mesh);Group->SetMaterial(0,Material);
        Group->SetCollisionEnabled(ECollisionEnabled::NoCollision);Group->SetCanEverAffectNavigation(false);Group->SetCastShadow(false);Group->SetCullDistances(5000,7500);Group->ComponentTags.Add(FName(Tag));Group->RegisterComponent();Group->AddInstances(Items,false,false,false);return Group;
    };
    MenuBoards=AddVisual(Cube,Iron,Boards,TEXT("ParisRestaurantMenus"));ProduceCrates=AddVisual(Cube,Wood,Crates,TEXT("ParisGroceryCrates"));Produce=AddVisual(Sphere,Cloth,Fruit,TEXT("ParisGroceryProduce"));
    AddVisual(Cube,Wood,Pots,TEXT("ParisShopFlorist"));AddVisual(Sphere,Cloth,Stems,TEXT("ParisShopFlorist"));AddVisual(Blossom,Cloth,Blossoms,TEXT("ParisShopFlorist"));AddVisual(Bread,Cloth,FlowerCentres,TEXT("ParisShopFlorist"));
    AddVisual(Cube,Wood,BakeryShelves,TEXT("ParisShopBakery"));AddVisual(Bread,Cloth,Loaves,TEXT("ParisShopBakery"));AddVisual(Cube,Wood,BookShelves,TEXT("ParisShopBookshop"));AddVisual(Book,Cloth,Books,TEXT("ParisShopBookshop"));
    // Only nearby names use text components; all other shops share one instanced panel.
    for(int32 I=0;I<24;I++)for(int32 Line=0;Line<3;Line++){
        auto Text=NewObject<UTextRenderComponent>(this);AddInstanceComponent(Text);Text->SetupAttachment(RootComponent);Text->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Text->SetCanEverAffectNavigation(false);Text->SetCastShadow(false);Text->SetHorizontalAlignment(EHTA_Center);Text->SetVerticalAlignment(EVRTA_TextCenter);
        Text->SetTextRenderColor(FColor(238,222,185));Text->SetWorldSize(Line==0?22.f:12.f);Text->SetVisibility(false);Text->RegisterComponent();
        (Line==0?Names:Line==1?Categories:Menus).Add(Text);
    }
    UpdateSigns();return true;
}
void AParisShopfrontSigns::Tick(float DeltaSeconds){Super::Tick(DeltaSeconds);Remaining-=DeltaSeconds;if(Remaining<=0){Remaining=.5;UpdateSigns();}}
void AParisShopfrontSigns::UpdateSigns(){
    if(!Scene||!Panels)return;const bool Show=Scene->bStreetDetails&&Scene->DetailQuality>0&&!Scene->bFootprints&&!Scene->bLevels&&!Scene->bIssues;
    Panels->SetVisibility(Show);MenuBoards->SetVisibility(Show);ProduceCrates->SetVisibility(Show);Produce->SetVisibility(Show);
    TArray<UHierarchicalInstancedStaticMeshComponent*> Details;GetComponents(Details);for(auto Part:Details)if(Part->ComponentHasTag(TEXT("ParisShopFlorist"))||Part->ComponentHasTag(TEXT("ParisShopBakery"))||Part->ComponentHasTag(TEXT("ParisShopBookshop")))Part->SetVisibility(Show);
    for(auto Text:Names)Text->SetVisibility(false);for(auto Text:Categories)Text->SetVisibility(false);for(auto Text:Menus)Text->SetVisibility(false);
    auto PC=GetWorld()?GetWorld()->GetFirstPlayerController():nullptr;if(!Show||!PC||!PC->PlayerCameraManager)return;
    const FVector Eye=PC->PlayerCameraManager->GetCameraLocation();TArray<TPair<double,int32>> Nearby;
    for(int32 I=0;I<Shops.Num();I++){const double Distance=FVector::DistSquared(Eye,Shops[I].Position);if(Distance<FMath::Square(4500.))Nearby.Emplace(Distance,I);}
    Nearby.Sort([](const auto& A,const auto& B){return A.Key<B.Key;});
    for(int32 I=0;I<FMath::Min(Nearby.Num(),Names.Num());I++){
        const auto& Shop=Shops[Nearby[I].Value];const FRotator Facing(0,Shop.Yaw+90,0);const FVector Out=Facing.Vector();
        auto Set=[&](UTextRenderComponent* Text,const FString& Label,double Height){Text->SetText(FText::FromString(Label));Text->SetXScale(FMath::Min(1.,260./FMath::Max(1.,Label.Len()*13.)));Text->SetWorldLocation(Shop.Position+Out*7+FVector(0,0,Height));Text->SetWorldRotation(Facing);Text->SetVisibility(true);};
        Set(Names[I],Shop.Name,8);Set(Categories[I],Shop.Category,-12);
        if(Shop.Restaurant){const FVector Along=FRotator(0,Shop.Yaw,0).Vector();auto Text=Menus[I];Text->SetText(FText::FromString(TEXT("MENU\nDU JOUR")));Text->SetXScale(1);Text->SetWorldLocation(Shop.Position+Along*112+Out*13+FVector(0,0,-175));Text->SetWorldRotation(Facing);Text->SetVisibility(true);}
    }
}
