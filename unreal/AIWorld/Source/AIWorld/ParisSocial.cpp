#include "ParisPedestrians.h"
#include "GameFramework/Pawn.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"

static void SocialHistory(FParisPedestrian& A,const FString& Text){A.RecentActions.Add(Text);if(A.RecentActions.Num()>4)A.RecentActions.RemoveAt(0);}

bool AParisPedestrianCrowd::SocialVisible(int32 A,int32 B) const {
    const auto& P=Agents[A];const auto& Q=Agents[B];
    if(FMath::Abs(P.Position.Z-Q.Position.Z)>40||FVector::DistSquared2D(P.Position,Q.Position)<125.*125||FVector::DistSquared2D(P.Position,Q.Position)>SocialRange*SocialRange)return false;
    FCollisionQueryParams Params;Params.AddIgnoredActor(this);
    // Dynamic traffic must also hide a neighbour across a passing vehicle.
    // Actor visibility geometry is used; no new route or crossing is inferred.
    if(auto PC=GetWorld()->GetFirstPlayerController())if(PC->GetPawn())Params.AddIgnoredActor(PC->GetPawn());
    FHitResult Hit;return !GetWorld()->LineTraceSingleByChannel(Hit,P.Position+FVector(0,0,P.SeatBlend>.5?118:155),Q.Position+FVector(0,0,Q.SeatBlend>.5?118:155),ECC_Visibility,Params);
}
void AParisPedestrianCrowd::EndSocial(int32 Index){
    if(!Agents.IsValidIndex(Index))return;auto& A=Agents[Index];const int32 Partner=A.SocialPartner;if(Partner<0)return;
    const bool Completed=A.SocialRemaining<=0;
    const FString History=Completed?TEXT("Greeting finished; resuming activity"):TEXT("Greeting interrupted; resuming activity");
    A.SocialPartner=-1;A.SocialRemaining=0;A.SocialCooldown=SocialCooldown;SocialHistory(A,History);
    if(Visits.IsValidIndex(A.Visit)&&A.VisitStage==3)A.Yaw=Visits[A.Visit].SeatRoute>=0?Visits[A.Visit].SeatYaw:Visits[A.Visit].FacingYaw;
    else Routes[A.Route].Sample(A.Distance,A.Direction,&A.Yaw);
    if(Agents.IsValidIndex(Partner)&&Agents[Partner].SocialPartner==Index){Agents[Partner].SocialPartner=-1;Agents[Partner].SocialRemaining=0;Agents[Partner].SocialCooldown=SocialCooldown;SocialHistory(Agents[Partner],History);
        auto& B=Agents[Partner];if(Visits.IsValidIndex(B.Visit)&&B.VisitStage==3)B.Yaw=Visits[B.Visit].SeatRoute>=0?Visits[B.Visit].SeatYaw:Visits[B.Visit].FacingYaw;else Routes[B.Route].Sample(B.Distance,B.Direction,&B.Yaw);}
    if(Completed)SocialCompleted++;
}
void AParisPedestrianCrowd::UpdateSocial(double Delta){
    if(!bSocial)return;
    for(int32 I=0;I<Agents.Num();I++){auto& A=Agents[I];A.SocialCooldown=FMath::Max(0.,A.SocialCooldown-Delta);
        if(A.SocialPartner>=0){A.SocialRemaining=FMath::Max(0.,A.SocialRemaining-Delta);if(A.SocialRemaining<=0||A.bVisitAborted||!SocialVisible(I,A.SocialPartner))EndSocial(I);}}
    SocialAccumulator+=Delta;if(SocialAccumulator<1)return;SocialAccumulator=0;
    auto Eligible=[&](const FParisPedestrian& A){return A.SocialPartner<0&&A.SocialCooldown<=0&&!A.bVisitAborted&&A.SeatBlend<.001&&(A.VisitStage==0||A.VisitStage==1||A.VisitStage==3)&&!(A.VisitStage==3&&A.Wait<4);};
    // Stable index order, bounded 512-person population, one partner each.
    // Stop only for a stationary neighbour; two streams do not halt to chat.
    for(int32 I=0;I<Agents.Num();I++){auto& A=Agents[I];
        const bool SeatedReady=A.VisitStage==3&&A.SeatBlend>.999&&A.Wait>=4;
        if(!(Eligible(A)|| (SeatedReady&&A.SocialPartner<0&&A.SocialCooldown<=0)))continue;
        int32 Best=-1;double Distance=SocialRange*SocialRange;
        for(int32 J=I+1;J<Agents.Num();J++){const auto& B=Agents[J];const bool OtherSeated=B.VisitStage==3&&B.SeatBlend>.999&&B.Wait>=4&&B.SocialPartner<0&&B.SocialCooldown<=0;
            if(!(Eligible(B)||OtherSeated)||(A.VisitStage!=3&&B.VisitStage!=3&&A.Wait<=0&&B.Wait<=0))continue;
            const double D=FVector::DistSquared2D(A.Position,B.Position);if(D<Distance&&SocialVisible(I,J)){Distance=D;Best=J;}}
        if(Best<0)continue;auto& B=Agents[Best];A.SocialPartner=Best;B.SocialPartner=I;A.SocialRemaining=B.SocialRemaining=SocialDuration;A.Moving=B.Moving=false;
        A.SocialLine=TEXT("Bonjour !");B.SocialLine=TEXT("Bonne journee !");
        // Seated hips retain chair orientation; standing neighbours turn.
        if(A.SeatBlend<.001)A.Yaw=(B.Position-A.Position).Rotation().Yaw;if(B.SeatBlend<.001)B.Yaw=(A.Position-B.Position).Rotation().Yaw;
        SocialHistory(A,TEXT("Greeting ")+B.ID+TEXT(": ")+A.SocialLine);SocialHistory(B,TEXT("Replying to ")+A.ID+TEXT(": ")+B.SocialLine);SocialStarted++;
    }
}
