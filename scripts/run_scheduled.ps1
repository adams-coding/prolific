# Launcher for scheduled runs. Run with: powershell -WindowStyle Hidden -File run_scheduled.ps1 -ConfigPath "..." -LogPath "..." -AppRoot "..."
# Used by install_windows.ps1 so the task runs with no visible window.
param(
  [Parameter(Mandatory=$true)][string]$ConfigPath,
  [Parameter(Mandatory=$true)][string]$LogPath,
  [Parameter(Mandatory=$true)][string]$AppRoot
)
$python = Join-Path $AppRoot ".venv\Scripts\python.exe"
& $python -m prolific_agent.cli run --config $ConfigPath *>> $LogPath
