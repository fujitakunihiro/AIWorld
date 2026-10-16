param([string]$ReportPath='')
$ErrorActionPreference='Stop'
if(-not $ReportPath){$ReportPath=Join-Path $PSScriptRoot '..\..\docs\paris-gpu-capabilities.json'}
# Read-only D3D12 capability queries. No shaders, textures, renderer settings,
# driver installation or changes to an already running game.
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class ParisD3D12Probe {
    [DllImport("d3d12.dll", CallingConvention=CallingConvention.StdCall)]
    private static extern int D3D12CreateDevice(IntPtr adapter, uint minimumLevel, ref Guid iid, out IntPtr device);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    private delegate int CheckFeature(IntPtr device, uint feature, IntPtr data, uint size);
    public static int[] Query(IntPtr device,uint feature,int[] values) {
        IntPtr data=Marshal.AllocHGlobal(values.Length*4);
        try {
            Marshal.Copy(values,0,data,values.Length);
            IntPtr table=Marshal.ReadIntPtr(device);
            var check=(CheckFeature)Marshal.GetDelegateForFunctionPointer(Marshal.ReadIntPtr(table,13*IntPtr.Size),typeof(CheckFeature));
            if(check(device,feature,data,(uint)(values.Length*4))<0)return null;
            Marshal.Copy(data,values,0,values.Length);return values;
        } finally {Marshal.FreeHGlobal(data);}
    }
    public static IntPtr Open() {
        Guid iid=new Guid("189819f1-1db6-4b57-be54-1821339b85f7");IntPtr device;
        Marshal.ThrowExceptionForHR(D3D12CreateDevice(IntPtr.Zero,0xb000,ref iid,out device));return device;
    }
    public static void Close(IntPtr device){Marshal.Release(device);}
}
'@
$report=[ordered]@{
    format='paris_gpu_probe_v1'
    run_utc=(Get-Date).ToUniversalTime().ToString('o')
    gpu=@(Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion)
    method='D3D12CreateDevice(default adapter, FL11_0) + ID3D12Device.CheckFeatureSupport'
    d3d12_device_created=$false
    shader_model=$null
    shader_model_query_ceiling='6.8'
    wave_ops=$null
    int64_shader_ops=$null
    atomic_int64_typed_resource=$null
    atomic_int64_group_shared=$null
    raytracing_tier=$null
    unified_memory=$null
    engine_dx12_render_tested=$false
    note='Device capabilities are prerequisites, not proof that UE Nanite/Lumen/VSM were enabled, built or performant.'
}
$device=[IntPtr]::Zero
try {
    $device=[ParisD3D12Probe]::Open();$report.d3d12_device_created=$true
    foreach($model in @(0x68,0x67,0x66,0x65,0x64,0x63,0x62,0x61,0x60)){
        $result=[ParisD3D12Probe]::Query($device,7,@($model))
        if($null -ne $result){$report.shader_model=('{0}.{1}' -f ($result[0] -shr 4),($result[0] -band 15));break}
    }
    $options=[ParisD3D12Probe]::Query($device,8,@(0,0,0,0,0,0))
    if($null -ne $options){$report.wave_ops=[bool]$options[0];$report.int64_shader_ops=[bool]$options[5]}
    $atomics=[ParisD3D12Probe]::Query($device,37,@(0,0,0,0,0,0))
    if($null -ne $atomics){$report.atomic_int64_typed_resource=[bool]$atomics[2];$report.atomic_int64_group_shared=[bool]$atomics[3]}
    $ray=[ParisD3D12Probe]::Query($device,27,@(0,0,0))
    if($null -ne $ray){$report.raytracing_tier=switch($ray[2]){0 {'unsupported'} 10 {'1.0'} 11 {'1.1'} default {"unknown:$($ray[2])"}}}
    $architecture=[ParisD3D12Probe]::Query($device,16,@(0,0,0,0,0))
    if($null -ne $architecture){$report.unified_memory=[bool]$architecture[2]}
}catch{$report['query_error']=$_.Exception.Message}
finally{if($device -ne [IntPtr]::Zero){[ParisD3D12Probe]::Close($device)}}
New-Item -ItemType Directory -Path (Split-Path ([IO.Path]::GetFullPath($ReportPath))) -Force | Out-Null
$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ReportPath -Encoding utf8
Get-Content -LiteralPath $ReportPath
