using UnrealBuildTool;
public class AIWorldEditorTarget : TargetRules {
    public AIWorldEditorTarget(TargetInfo Target) : base(Target) {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.V7;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8;
        ExtraModuleNames.Add("AIWorld");
    }
}
