# Scripts

## UI
- Launch (CLI subcommand): `prolific-agent ui`
- Launch (direct entry point): `prolific-agent-ui`
  - Note: on some Linux distros you may need to install Tkinter (e.g., package `python3-tk`).
  - Warning: Do NOT watch entire drives or very large folders; this can cause high CPU/memory usage.

## Windows (Scheduled Task)
- Install:
  - `powershell -ExecutionPolicy Bypass -File scripts\\install_windows.ps1 -ConfigPath "C:\\path\\to\\config.toml" -IntervalHours 2`
- Uninstall:
  - `powershell -ExecutionPolicy Bypass -File scripts\\uninstall_windows.ps1`

## Linux (systemd user timer)
- Install:
  - `bash scripts/install_linux.sh "$HOME/.prolific/config.toml" 2`
- Uninstall:
  - `bash scripts/uninstall_linux.sh`


