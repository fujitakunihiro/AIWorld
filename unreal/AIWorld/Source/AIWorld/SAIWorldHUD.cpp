#include "SAIWorldHUD.h"
#include "AIWorldPlayer.h"
#include "AIWorldScene.h"
#include "WorldProtocol.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Input/SButton.h"
#include "Styling/CoreStyle.h"
#include "Serialization/JsonSerializer.h"
#include "AIWorldResident.h"
#include "Rendering/DrawElements.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "UnrealClient.h"
using namespace AIWorld;
TSharedRef<SWidget> SAIWorldHUD::Text(const FString& Label,int32 Size){auto F=Font;F.Size=Size;return SNew(STextBlock).Text(FText::FromString(Label)).Font(F).ColorAndOpacity(FLinearColor(.94f,.9f,.8f)).AutoWrapText(true);}
TSharedRef<SWidget> SAIWorldHUD::Button(const FString& Label,TFunction<void()> Action){return SNew(SButton).ButtonStyle(&ButtonStyle).ContentPadding(FMargin(10,7)).OnClicked_Lambda([Action]{Action();return FReply::Handled();})[Text(Label,13)];}
void SAIWorldHUD::Construct(const FArguments& Args){
    Owner=Args._Owner;Font=FCoreStyle::GetDefaultFontStyle("Regular",14);ButtonStyle=FCoreStyle::Get().GetWidgetStyle<FButtonStyle>("Button");
    ButtonStyle.Normal.TintColor=FSlateColor(FLinearColor(.09f,.14f,.16f));ButtonStyle.Hovered.TintColor=FSlateColor(FLinearColor(.25f,.32f,.3f));ButtonStyle.Pressed.TintColor=FSlateColor(FLinearColor(.3f,.35f,.25f));
    auto Controls=SNew(SHorizontalBox);
    for(const auto& Name:{TEXT("村"),TEXT("パリ"),TEXT("全景")}) {const FString N=Name;Controls->AddSlot().AutoWidth().Padding(2)[Button(N,[this,N]{if(auto P=Owner.Get()){if(N==TEXT("村"))P->FocusCamp();else if(N==TEXT("パリ"))P->FocusParis();else P->FocusAll();}})];}
    for(int32 Speed:{0,1,5,20})Controls->AddSlot().AutoWidth().Padding(2)[Button(Speed?FString::Printf(TEXT("%d×"),Speed):TEXT("停止"),[this,Speed]{if(auto P=Owner.Get())if(auto W=P->World())W->Send(SpeedCommand(Speed));})];
    Controls->AddSlot().AutoWidth().Padding(2)[Button(TEXT("メニュー"),[this]{bMenu=!bMenu;if(!bMenu&&Owner.IsValid()&&Owner->EditMode!=0)Owner->SetEdit(0);BuildPanel();})];
    auto InputRow=SNew(SHorizontalBox);
    InputRow->AddSlot().FillWidth(1)[SAssignNew(Input,SEditableTextBox).Font(Font).ForegroundColor(FLinearColor(.97f,.93f,.85f)).BackgroundColor(FLinearColor(.015f,.035f,.04f)).HintText(FText::FromString(TEXT("例: 畑を1面作って / ミオに木材を集めて"))).OnTextCommitted_Lambda([this](const FText&,ETextCommit::Type Type){if(Type==ETextCommit::OnEnter)Submit();})];
    InputRow->AddSlot().AutoWidth().Padding(4,0)[Button(TEXT("送信"),[this]{Submit();})];
    InputRow->AddSlot().AutoWidth()[Button(TEXT("指示 / 会話"),[this]{bConversation=!bConversation;})];
    ChildSlot[SNew(SOverlay)
        +SOverlay::Slot().HAlign(HAlign_Left).VAlign(VAlign_Top).Padding(14)[SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush")).BorderBackgroundColor(FLinearColor(.025f,.06f,.07f,.88f)).Padding(10)[SNew(SVerticalBox)
            +SVerticalBox::Slot().AutoHeight()[SNew(STextBlock).Font(Font).ColorAndOpacity(FLinearColor(.97f,.92f,.8f)).Text_Lambda([this]{return FText::FromString(Owner.IsValid()?Owner->Summary():TEXT("AI WORLD"));})]
            +SVerticalBox::Slot().AutoHeight().Padding(0,4,0,0)[SNew(STextBlock).Font(FCoreStyle::GetDefaultFontStyle("Regular",11)).ColorAndOpacity(FLinearColor(.65f,.8f,.77f)).Text_Lambda([this]{auto W=Owner.IsValid()?Owner->World():nullptr;return FText::FromString(W?W->Status:TEXT("読み込み中"));})]]]
        +SOverlay::Slot().HAlign(HAlign_Right).VAlign(VAlign_Top).Padding(14)[SAssignNew(Toolbar,SBox)[Controls]]
        +SOverlay::Slot().HAlign(HAlign_Right).VAlign(VAlign_Top).Padding(14,68,14,100)[SAssignNew(Panel,SBox).WidthOverride(360).MaxDesiredHeight(650).Visibility_Lambda([this]{return bMenu?EVisibility::Visible:EVisibility::Collapsed;})]
        +SOverlay::Slot().HAlign(HAlign_Left).VAlign(VAlign_Bottom).Padding(14)[SAssignNew(Bottom,SBox).WidthOverride(580)[SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush")).BorderBackgroundColor(FLinearColor(.025f,.06f,.07f,.9f)).Padding(10)[SNew(SVerticalBox)
            +SVerticalBox::Slot().AutoHeight()[SNew(STextBlock).Font(Font).ColorAndOpacity(FLinearColor(.85f,.8f,.65f)).Text_Lambda([this]{auto P=Owner.Get();auto W=P?P->World():nullptr;auto R=W?W->Resident(P->Selected):nullptr;return FText::FromString(bConversation?TEXT("会話 → ")+(R?String(R,TEXT("name")):TEXT("住民を選択")):TEXT("村への指示 · 外部API不要"));})]
            +SVerticalBox::Slot().AutoHeight().Padding(0,6)[InputRow]
            +SVerticalBox::Slot().AutoHeight()[SNew(STextBlock).Font(FCoreStyle::GetDefaultFontStyle("Regular",12)).ColorAndOpacity(FLinearColor(.85f,.9f,.85f)).AutoWrapText(true).Text_Lambda([this]{auto W=Owner.IsValid()?Owner->World():nullptr;return FText::FromString(W?W->Reply:TEXT(""));})]
            +SVerticalBox::Slot().AutoHeight().Padding(0,5,0,0)[Text(TEXT("右ドラッグ: 回転  /  WASD・中ドラッグ: 移動  /  ホイール: ズーム  /  左クリック: 住民"),10)]]]]];
}
bool SAIWorldHUD::BlocksWorldInput() const{return Input&&Input->HasKeyboardFocus() || Panel&&bMenu&&Panel->IsHovered() || Toolbar&&Toolbar->IsHovered() || Bottom&&Bottom->IsHovered();}
void SAIWorldHUD::Submit(){if(Owner.IsValid()&&Input){Owner->SendText(Input->GetText().ToString(),bConversation);Input->SetText(FText::GetEmpty());}}
void SAIWorldHUD::ShowResident(){bMenu=true;Page=TEXT("住民");BuildPanel();}
void SAIWorldHUD::Tick(const FGeometry& G,double Time,float Delta){SCompoundWidget::Tick(G,Time,Delta);if(bMenu&&Time>RefreshAt){RefreshAt=Time+5;const float Offset=Scroll?Scroll->GetScrollOffset():0;BuildPanel();if(Scroll)Scroll->SetScrollOffset(Offset);}}
int32 SAIWorldHUD::OnPaint(const FPaintArgs& Args,const FGeometry& G,const FSlateRect& Culling,FSlateWindowElementList& Elements,int32 Layer,const FWidgetStyle& Style,bool Enabled) const {
    auto P=Owner.Get();auto W=P?P->World():nullptr;
    if(P&&W&&GEngine&&GEngine->GameViewport&&GEngine->GameViewport->Viewport){const FIntPoint View=GEngine->GameViewport->Viewport->GetSizeXY();
        for(const auto& Pair:W->People()){auto R=W->Resident(Pair.Key);auto Speech=Object(R,TEXT("speech"));if(!Speech||Number(Speech,TEXT("until"))<=Number(W->Village,TEXT("elapsed")))continue;FVector2D Pos;
            if(!P->ProjectWorldLocationToScreen(Pair.Value->GetActorLocation()+FVector(0,0,195),Pos))continue;
            Pos=Pos/FVector2D(FMath::Max(1,View.X),FMath::Max(1,View.Y))*G.GetLocalSize();if(Pos.X<0||Pos.Y<0||Pos.X>G.GetLocalSize().X||Pos.Y>G.GetLocalSize().Y)continue;
            FString Label=String(R,TEXT("name"))+TEXT(": ")+String(Speech,TEXT("text")).Left(40);if(Label.Len()>22)Label.InsertAt(22,TEXT("\n"));const FVector2D Size(270,Label.Contains(TEXT("\n"))?48:30);Pos-=FVector2D(135,Size.Y);
            FSlateDrawElement::MakeBox(Elements,Layer,G.ToPaintGeometry(Size,FSlateLayoutTransform(Pos)),FCoreStyle::Get().GetBrush("WhiteBrush"),ESlateDrawEffect::None,FLinearColor(.035f,.075f,.07f,.9f));auto F=Font;F.Size=12;
            FSlateDrawElement::MakeText(Elements,Layer+1,G.ToPaintGeometry(Size,FSlateLayoutTransform(Pos+FVector2D(8,5))),Label,F,ESlateDrawEffect::None,FLinearColor(.97f,.93f,.8f));
        }
    }
    return SCompoundWidget::OnPaint(Args,G,Culling,Elements,Layer+2,Style,Enabled);
}
void SAIWorldHUD::BuildPanel(){if(!Panel)return;auto P=Owner.Get();auto W=P?P->World():nullptr;auto Body=SNew(SVerticalBox);auto Tabs=SNew(SHorizontalBox);
    for(const auto& Name:{TEXT("住民"),TEXT("仕事"),TEXT("歴史"),TEXT("設定")}){const FString N=Name;Tabs->AddSlot().FillWidth(1).Padding(2)[Button(N,[this,N]{Page=N;BuildPanel();})];}
    Body->AddSlot().AutoHeight()[Tabs];
    if(W){
        if(Page==TEXT("住民")){
            for(const auto& V:Array(W->Village,TEXT("residents"))){auto R=V->AsObject();const FString ID=String(R,TEXT("id"));Body->AddSlot().AutoHeight().Padding(0,3)[Button(String(R,TEXT("name"))+TEXT(" · ")+String(R,TEXT("job"))+TEXT(" · ")+String(R,TEXT("action")),[this,ID]{if(Owner.IsValid())Owner->Select(ID);})];}
            Body->AddSlot().AutoHeight().Padding(0,10)[SNew(STextBlock).Font(Font).ColorAndOpacity(FLinearColor(.9f,.91f,.85f)).AutoWrapText(true).Text_Lambda([this]{return FText::FromString(Owner.IsValid()?Owner->Detail():TEXT(""));})];
        }else if(Page==TEXT("仕事")){
            auto C=Object(W->Village,TEXT("civilization"));Body->AddSlot().AutoHeight().Padding(0,6)[Text(FString::Printf(TEXT("文明レベル %.0f · 収穫 %.0f回"),Number(C,TEXT("level")),Number(C,TEXT("harvests"))))];
            for(const auto& V:Array(W->Village,TEXT("issues")))Body->AddSlot().AutoHeight().Padding(0,5)[Text(V->AsString())];
            for(const auto& V:Array(W->Village,TEXT("tasks"))){auto T=V->AsObject();auto Cost=Object(T,TEXT("requiredResources"));auto Reserved=Object(T,TEXT("reservedResources"));FString Assigned;for(const auto& ID:Array(T,TEXT("assignees"))){auto R=W->Resident(ID->AsString());Assigned+=String(R,TEXT("name"))+TEXT(" ");}
                Body->AddSlot().AutoHeight().Padding(0,5)[Button(FString::Printf(TEXT("%s · %s  %.0f/%.0f\n担当 %s\n木材 %.0f / 石材 %.0f (予約 %.0f / %.0f)\n%s"),*String(T,TEXT("title")),*String(T,TEXT("status")),Number(T,TEXT("progress")),Number(T,TEXT("total")),*Assigned,Number(Cost,TEXT("wood")),Number(Cost,TEXT("stone")),Number(Reserved,TEXT("wood")),Number(Reserved,TEXT("stone")),*String(T,TEXT("failure"))),[this,T]{if(Owner.IsValid())Owner->FocusItem(T);})];}
            for(const auto& V:Array(W->Village,TEXT("instructions"))){auto R=V->AsObject();FString JSON;FJsonSerializer::Serialize(R.ToSharedRef(),TJsonWriterFactory<>::Create(&JSON));Body->AddSlot().AutoHeight().Padding(0,6)[Text(String(R,TEXT("text"))+TEXT("\n")+JSON,11)];}
        }else if(Page==TEXT("歴史")){
            const auto& Events=Array(W->Village,TEXT("chronicle"));for(int32 I=Events.Num()-1;I>=FMath::Max(0,Events.Num()-40);I--){auto E=Events[I]->AsObject();const int32 M=Number(E,TEXT("time"));Body->AddSlot().AutoHeight().Padding(0,4)[Button(FString::Printf(TEXT("%d日 %02d:%02d · %s\n%s"),M/1440+1,M/60%24,M%60,*String(E,TEXT("kind")),*String(E,TEXT("text"))),[this,E]{if(Owner.IsValid())Owner->FocusItem(E);})];}
            auto Archive=Object(W->Village,TEXT("archive"));Body->AddSlot().AutoHeight()[Text(FString::Printf(TEXT("過去の出来事: %.0f件を要約して保存"),Number(Archive,TEXT("count"))),12)];
        }else{
            Body->AddSlot().AutoHeight().Padding(0,8)[Text(TEXT("描画品質"),17)];auto Q=SNew(SHorizontalBox);const TCHAR* Labels[]={TEXT("低"),TEXT("中"),TEXT("高")};for(int32 I=0;I<3;I++)Q->AddSlot().FillWidth(1).Padding(2)[Button(Labels[I],[this,I]{if(Owner.IsValid())if(auto World=Owner->World())World->SetQuality(I);})];Body->AddSlot().AutoHeight()[Q];
            Body->AddSlot().AutoHeight().Padding(0,6)[Button(bClassic?TEXT("ジオラマ表示へ"):TEXT("ボクセル表示へ"),[this]{bClassic=!bClassic;if(Owner.IsValid())if(auto World=Owner->World())World->SetClassic(bClassic||Owner->EditMode!=0);BuildPanel();})];
            Body->AddSlot().AutoHeight().Padding(0,6)[Button(W->bSound?TEXT("効果音: ON"):TEXT("効果音: OFF"),[this]{if(Owner.IsValid())if(auto World=Owner->World())World->bSound=!World->bSound;BuildPanel();})];
            Body->AddSlot().AutoHeight()[Text(FString::Printf(TEXT("描画 %.1f fps · %d×%d 世界"),W->FPS,W->Grid.Size,W->Grid.Size),12)];
            Body->AddSlot().AutoHeight().Padding(0,8)[Text(TEXT("光のプレビュー (世界の時計は継続)"),13)];auto Lights=SNew(SHorizontalBox);const TCHAR* LightNames[]={TEXT("世界"),TEXT("昼"),TEXT("夕"),TEXT("夜")};const int32 LightTimes[]={-1,720,1050,1320};for(int32 I=0;I<4;I++)Lights->AddSlot().FillWidth(1).Padding(2)[Button(LightNames[I],[this,T=LightTimes[I]]{if(Owner.IsValid())if(auto World=Owner->World())World->LightPreview=T;})];Body->AddSlot().AutoHeight()[Lights];
            Body->AddSlot().AutoHeight().Padding(0,8)[Text(TEXT("地形編集"),17)];auto E=SNew(SHorizontalBox);E->AddSlot().FillWidth(1)[Button(TEXT("観察"),[this]{if(Owner.IsValid())Owner->SetEdit(0);})];E->AddSlot().FillWidth(1)[Button(TEXT("消す"),[this]{if(Owner.IsValid())Owner->SetEdit(-1);})];E->AddSlot().FillWidth(1)[Button(TEXT("戻す"),[this]{if(Owner.IsValid())Owner->Undo();})];Body->AddSlot().AutoHeight()[E];
            const TCHAR* Names[]={TEXT("草"),TEXT("土"),TEXT("石"),TEXT("砂"),TEXT("木材"),TEXT("葉"),TEXT("レンガ")};const int32 Blocks[]={1,2,3,4,5,6,8};for(int32 I=0;I<7;I++)Body->AddSlot().AutoHeight().Padding(0,3)[Button(FString(Names[I])+TEXT("を置く"),[this,I,Block=Blocks[I]]{if(Owner.IsValid())Owner->SetEdit(1,Block);})];
            Body->AddSlot().AutoHeight().Padding(0,8)[Text(TEXT("自動保存: シミュレーションのSQLiteに保存。再接続で復元します。\n建物・橋・住民の足場は保護されます。\n日本語の指示と会話はローカルで処理します。\nV: 村 / P: パリ / Home: 全景"),12)];
        }
    }
    Panel->SetContent(SNew(SBorder).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush")).BorderBackgroundColor(FLinearColor(.025f,.06f,.07f,.96f)).Padding(12)[SAssignNew(Scroll,SScrollBox)+SScrollBox::Slot()[Body]]);
}
