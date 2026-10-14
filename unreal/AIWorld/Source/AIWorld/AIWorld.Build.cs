using UnrealBuildTool;
public class AIWorld : ModuleRules {
    public AIWorld(ReadOnlyTargetRules Target) : base(Target) {
        PCHUsage = PCHUsageMode.NoPCHs;
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine", "InputCore", "ProceduralMeshComponent", "HTTP", "WebSockets", "Json", "Slate", "SlateCore" });
        RuntimeDependencies.Add("$(ProjectDir)/Content/Data/models.json", StagedFileType.NonUFS);
        if (System.IO.File.Exists(System.IO.Path.Combine(ModuleDirectory, "../../Content/Data/paris-digital-twin.json")))
            RuntimeDependencies.Add("$(ProjectDir)/Content/Data/paris-digital-twin.json", StagedFileType.NonUFS);
    }
}
