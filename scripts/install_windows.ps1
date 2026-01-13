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

# Disable battery restrictions (default schtasks settings can prevent running on battery)
try {
  $xml = schtasks /Query /TN $TaskName /XML 2>$null
  if ($LASTEXITCODE -eq 0 -and $xml) {
    $xml2 = $xml
    # Flip existing flags if present
    $xml2 = $xml2 -replace "<DisallowStartIfOnBatteries>true</DisallowStartIfOnBatteries>", "<DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>"
    $xml2 = $xml2 -replace "<StopIfGoingOnBatteries>true</StopIfGoingOnBatteries>", "<StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>"
    # Ensure flags exist (insert if missing)
    if ($xml2 -notmatch "<DisallowStartIfOnBatteries>") {
      $xml2 = $xml2 -replace "</Settings>", "  <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>`n</Settings>"
    }
    if ($xml2 -notmatch "<StopIfGoingOnBatteries>") {
      $xml2 = $xml2 -replace "</Settings>", "  <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>`n</Settings>"
    }

    $tmp = Join-Path $env:TEMP ("prolific-task-" + [Guid]::NewGuid().ToString() + ".xml")
    Set-Content -Path $tmp -Value $xml2 -Encoding UTF8
    schtasks /Create /F /TN $TaskName /XML $tmp | Out-Null
    Remove-Item -Force $tmp -ErrorAction SilentlyContinue
  }
} catch {
  # Non-fatal: task still installed; log will capture failures.
}

Write-Host "Done. You can verify with:"
Write-Host "  schtasks /Query /TN $TaskName /V /FO LIST"
Write-Host "And check logs at:"
Write-Host "  $LogPath"


