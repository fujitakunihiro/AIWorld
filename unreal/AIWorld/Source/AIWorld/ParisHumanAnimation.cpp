#include "ParisHumanAnimation.h"
#include "Animation/AnimInstanceProxy.h"
#include "Animation/AnimNode_SequencePlayer.h"
#include "Animation/AnimSequence.h"
#include "AnimNodes/AnimNode_TwoWayBlend.h"

class FParisHumanProxy : public FAnimInstanceProxy {
    FAnimNode_SequencePlayer_Standalone Idle,Walk,Run,Sit;
    FAnimNode_TwoWayBlend Gait,Locomotion,Seating;
    float WalkingAlpha=0,RunningAlpha=0,SeatAlpha=0;
    int32 PersonIndex=INDEX_NONE;
public:
    explicit FParisHumanProxy(UAnimInstance* Instance):FAnimInstanceProxy(Instance){
        Gait.A.SetLinkNode(&Walk);Gait.B.SetLinkNode(&Run);
        Locomotion.A.SetLinkNode(&Idle);Locomotion.B.SetLinkNode(&Gait);
        Seating.A.SetLinkNode(&Locomotion);Seating.B.SetLinkNode(&Sit);
    }
    virtual void Initialize(UAnimInstance* Instance) override {
        FAnimInstanceProxy::Initialize(Instance);
        Seating.Initialize_AnyThread(FAnimationInitializeContext(this));
    }
    virtual void PreUpdate(UAnimInstance* Instance,float Delta) override {
        FAnimInstanceProxy::PreUpdate(Instance,Delta);
        const auto Human=CastChecked<UParisHumanAnimation>(Instance);
        Idle.SetSequence(Human->Idle);Walk.SetSequence(Human->Walk);Run.SetSequence(Human->Run?Human->Run:Human->Walk);Sit.SetSequence(Human->Sit?Human->Sit:Human->Idle);
        Idle.SetLoopAnimation(true);Walk.SetLoopAnimation(true);Run.SetLoopAnimation(true);Sit.SetLoopAnimation(true);
        const float Target=Human->SpeedCm>1?1.f:0.f;
        WalkingAlpha=FMath::FInterpTo(WalkingAlpha,Target,Delta,8.f);
        const float RunTarget=Human->Run?FMath::GetMappedRangeValueClamped(FVector2D(Human->RunStartSpeedCm,Human->FullRunSpeedCm),FVector2D(0,1),Human->SpeedCm):0;
        RunningAlpha=FMath::FInterpTo(RunningAlpha,RunTarget,Delta,10.f);Gait.Alpha=RunningAlpha;
        SeatAlpha=FMath::Clamp(Human->SeatAlpha,0.f,1.f);
        Locomotion.Alpha=WalkingAlpha;Seating.Alpha=SeatAlpha;
        Walk.SetPlayRate(FMath::Clamp(Human->SpeedCm/FMath::Max(40.f,Human->NominalSpeedCm),.65f,1.8f));
        Run.SetPlayRate(FMath::Clamp(Human->SpeedCm/FMath::Max(100.f,Human->NominalRunSpeedCm),.65f,1.5f));
        if(PersonIndex!=Human->PersonIndex){
            PersonIndex=Human->PersonIndex;
            for(auto Player:{&Idle,&Walk,&Run,&Sit})if(Player->GetSequence())
                Player->SetAccumulatedTime(FMath::Fmod(FMath::Max(0,PersonIndex)*.371f,Player->GetSequence()->GetPlayLength()));
        }
    }
    virtual void UpdateAnimationNode(const FAnimationUpdateContext& Context) override {
        UpdateCounter.Increment();Seating.Update_AnyThread(Context);
    }
    virtual void CacheBones() override { Seating.CacheBones_AnyThread(FAnimationCacheBonesContext(this)); }
    virtual bool Evaluate(FPoseContext& Output) override { Seating.Evaluate_AnyThread(Output);return true; }
};
FAnimInstanceProxy* UParisHumanAnimation::CreateAnimInstanceProxy(){return new FParisHumanProxy(this);}
void UParisHumanAnimation::DestroyAnimInstanceProxy(FAnimInstanceProxy* Proxy){delete Proxy;}
