using UnrealBuildTool;
public class AIWorld : ModuleRules {
    public AIWorld(ReadOnlyTargetRules Target) : base(Target) {
        PCHUsage = PCHUsageMode.NoPCHs;
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine", "InputCore", "ProceduralMeshComponent", "HTTP", "WebSockets", "Json", "Slate", "SlateCore" });
        RuntimeDependencies.Add("$(ProjectDir)/Content/Data/models.json", StagedFileType.NonUFS);
    }
}
