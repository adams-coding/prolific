param(
  [Parameter(Mandatory=$true)][string]$ConfigPath,
  [Parameter(Mandatory=$false)][int]$IntervalHours = 2,
  [Parameter(Mandatory=$false)][string]$TaskName = "ProlificGitActive",
  [Parameter(Mandatory=$false)][string]$AppRoot = "",
  [Parameter(Mandatory=$false)][string]$LogPath = ""
)

if ($IntervalHours -lt 1 -or $IntervalHours -gt 4) {
  throw "IntervalHours must be 1-4"
}

$ConfigPath = (Resolve-Path $ConfigPath).Path
$ConfigDir = Split-Path -Parent $ConfigPath
$RepoRoot = $AppRoot
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
  # scripts/ -> repo root
  $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
} else {
  $RepoRoot = (Resolve-Path $RepoRoot).Path
}

$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (!(Test-Path $VenvPython)) {
  throw "Expected virtualenv python not found: $VenvPython`nRun the UI/launcher once to create .venv, then re-run this installer."
}

# Log file (defaults next to config so it's easy to find)
if ([string]::IsNullOrWhiteSpace($LogPath)) {
  $LogPath = (Join-Path $ConfigDir "scheduler.log")
} else {
  $LogPath = (Resolve-Path (Split-Path -Parent $LogPath)).Path + "\" + (Split-Path -Leaf $LogPath)
}

# Always use the app's local venv so scheduled runs match the UI behavior.
# Also redirect stdout/stderr to a persistent log for debugging.
$Command = "cmd.exe /c `"`"$VenvPython`" -m prolific_agent.cli run --config `"$ConfigPath`" >> `"$LogPath`" 2>&1`""

Write-Host "Creating/Updating Scheduled Task: $TaskName"
Write-Host "Command: $Command"
Write-Host "IntervalHours: $IntervalHours"
Write-Host "AppRoot: $RepoRoot"
Write-Host "LogPath: $LogPath"

schtasks /Create /F /SC HOURLY /MO $IntervalHours /TN $TaskName /TR $Command | Out-Null

# Disable battery restrictions (best-effort, without fragile XML rewriting)
try {
  if (Get-Command Get-ScheduledTask -ErrorAction SilentlyContinue) {
    $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    $s = $t.Settings
    $s.DisallowStartIfOnBatteries = $false
    $s.StopIfGoingOnBatteries = $false
    Set-ScheduledTask -TaskName $TaskName -Settings $s | Out-Null
  } else {
    Write-Host "Note: ScheduledTasks module not available; skipping battery setting update."
  }
} catch {
  Write-Host "Note: Could not update battery settings (non-fatal): $($_.Exception.Message)"
}

Write-Host "Done. You can verify with:"
Write-Host "  schtasks /Query /TN $TaskName /V /FO LIST"
Write-Host "And check logs at:"
Write-Host "  $LogPath"


