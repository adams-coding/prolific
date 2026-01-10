param(
  [Parameter(Mandatory=$true)][string]$ConfigPath,
  [Parameter(Mandatory=$false)][int]$IntervalHours = 2,
  [Parameter(Mandatory=$false)][string]$TaskName = "ProlificGitActive",
  [Parameter(Mandatory=$false)][string]$AppRoot = ""
)

if ($IntervalHours -lt 1 -or $IntervalHours -gt 4) {
  throw "IntervalHours must be 1-4"
}

$ConfigPath = (Resolve-Path $ConfigPath).Path
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

# Always use the app's local venv so scheduled runs match the UI behavior.
$Command = "`"$VenvPython`" -m prolific_agent.cli run --config `"$ConfigPath`""

Write-Host "Creating/Updating Scheduled Task: $TaskName"
Write-Host "Command: $Command"
Write-Host "IntervalHours: $IntervalHours"
Write-Host "AppRoot: $RepoRoot"

schtasks /Create /F /SC HOURLY /MO $IntervalHours /TN $TaskName /TR $Command | Out-Null

Write-Host "Done. You can verify with:"
Write-Host "  schtasks /Query /TN $TaskName /V /FO LIST"


