using UnrealBuildTool;
public class AIWorldTarget : TargetRules {
    public AIWorldTarget(TargetInfo Target) : base(Target) {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.V7;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8;
        ExtraModuleNames.Add("AIWorld");
    }
}
