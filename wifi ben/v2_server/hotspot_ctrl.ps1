param(
    [string]$Action = "get",
    [string]$SSID = "",
    [string]$Password = ""
)

[Windows.System.UserProfile.LockScreen,Windows.System.UserProfile,ContentType=WindowsRuntime] | Out-Null
Add-Type -AssemblyName System.Runtime.WindowsRuntime

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
Function AwaitOperation($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(15000) | Out-Null
    return $netTask.Result
}

$asAction = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction' })[0]
Function AwaitAction($WinRtTask) {
    $netTask = $asAction.Invoke($null, @($WinRtTask))
    $netTask.Wait(15000) | Out-Null
}

$connectionProfile = [Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime]::GetInternetConnectionProfile()
if ($null -eq $connectionProfile) {
    Write-Output '{"success":false,"error":"No internet connection profile found."}'
    exit
}

$tm = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]::CreateFromConnectionProfile($connectionProfile)

if ($Action -eq "get") {
    $cfg = $tm.GetCurrentAccessPointConfiguration()
    $is_on = ($tm.TetheringOperationalState -eq [Windows.Networking.NetworkOperators.TetheringOperationalState]::On)
    $obj = @{
        success = $true
        active = $is_on
        state = $tm.TetheringOperationalState.ToString()
        ssid = $cfg.Ssid
        password = $cfg.Passphrase
    }
    Write-Output ($obj | ConvertTo-Json -Compress)
    exit
}

if ($Action -eq "set") {
    $cfg = $tm.GetCurrentAccessPointConfiguration()
    if ($SSID) { $cfg.Ssid = $SSID }
    if ($Password -and $Password.Length -ge 8) { $cfg.Passphrase = $Password }
    
    AwaitAction ($tm.ConfigureAccessPointAsync($cfg))

    $was_on = ($tm.TetheringOperationalState -eq [Windows.Networking.NetworkOperators.TetheringOperationalState]::On)
    if ($was_on) {
        # Restart to apply new SSID and Password to RF broadcast
        AwaitOperation ($tm.StopTetheringAsync()) ([Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult]) | Out-Null
        Start-Sleep -Milliseconds 800
        $res = AwaitOperation ($tm.StartTetheringAsync()) ([Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult])
    }

    $cfgNow = $tm.GetCurrentAccessPointConfiguration()
    $is_on = ($tm.TetheringOperationalState -eq [Windows.Networking.NetworkOperators.TetheringOperationalState]::On)
    $obj = @{
        success = $true
        active = $is_on
        ssid = $cfgNow.Ssid
        password = $cfgNow.Passphrase
    }
    Write-Output ($obj | ConvertTo-Json -Compress)
    exit
}

if ($Action -eq "start") {
    $res = AwaitOperation ($tm.StartTetheringAsync()) ([Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult])
    $is_on = ($tm.TetheringOperationalState -eq [Windows.Networking.NetworkOperators.TetheringOperationalState]::On)
    $cfg = $tm.GetCurrentAccessPointConfiguration()
    $obj = @{
        success = ($res.Status -eq [Windows.Networking.NetworkOperators.TetheringOperationStatus]::Success)
        active = $is_on
        status = $res.Status.ToString()
        ssid = $cfg.Ssid
        password = $cfg.Passphrase
    }
    Write-Output ($obj | ConvertTo-Json -Compress)
    exit
}

if ($Action -eq "stop") {
    $res = AwaitOperation ($tm.StopTetheringAsync()) ([Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult])
    $is_on = ($tm.TetheringOperationalState -eq [Windows.Networking.NetworkOperators.TetheringOperationalState]::On)
    $obj = @{
        success = $true
        active = $is_on
    }
    Write-Output ($obj | ConvertTo-Json -Compress)
    exit
}
