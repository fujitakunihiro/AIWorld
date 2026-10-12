#pragma once
#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Layout/SScrollBox.h"
class AAIWorldPlayer;
class SAIWorldHUD : public SCompoundWidget {
public:
    SLATE_BEGIN_ARGS(SAIWorldHUD){} SLATE_ARGUMENT(AAIWorldPlayer*,Owner) SLATE_END_ARGS()
    void Construct(const FArguments& Args);
    virtual void Tick(const FGeometry& G,double Time,float Delta) override;
    virtual int32 OnPaint(const FPaintArgs& Args,const FGeometry& Geometry,const FSlateRect& Culling,FSlateWindowElementList& Elements,int32 Layer,const FWidgetStyle& Style,bool Enabled) const override;
    bool BlocksWorldInput() const;
    bool ClassicPreferred() const{return bClassic;}
    void ShowResident();
private:
    TWeakObjectPtr<AAIWorldPlayer> Owner;
    TSharedPtr<SBox> Panel,Toolbar,Bottom;
    TSharedPtr<SEditableTextBox> Input;
    TSharedPtr<SScrollBox> Scroll;
    FButtonStyle ButtonStyle;
    FSlateFontInfo Font;
    FString Page=TEXT("住民");
    bool bMenu=false,bConversation=false,bClassic=false;
    double RefreshAt=0;
    TSharedRef<SWidget> Button(const FString& Label,TFunction<void()> Action);
    TSharedRef<SWidget> Text(const FString& Label,int32 Size=14);
    void BuildPanel();void Submit();
};
