# Prolific: Git Active

## Prolific App

I am a prolific coder!

I am often coding for 12 hours or more a day.

But my GitHub doesn't reflect this because I often test locally and many things never make it to GitHub.

But seeing all those blank spaces in my GitHub activity makes me look lazy.

To fix this I made the Prolific app.

Just download and let it know which folder you code your projects in.

Each time you start a new project, it will detect the new folder.

Each time you modify files, add files, delete files, create other assets, Prolific will detect the changes.

Every 1-4 hours, it will push an anonymized report to the git repo of your choice. (creating activity on githubs contributions calendar)

After the first run (baseline), it will run automatically (including scheduled runs) and push a report on what you have been doing (no details).

It also creates a nice little bubblemap with each project being a node on the bubblemap.

It will identify the languages you are coding in based on file extension and color code bubblemap items accordingly.

![Prolific bubblemap visualization](prolific-visualization.png)

## Privacy model 
- **Never reads file contents** (no parsing, no hashing contents, no string searching).
- Scans use **metadata only**: size (bytes), mtime, is_dir, extension.
- Reports committed to git contain **aggregates only** (no file names/paths).
- Watch folders are represented as **pseudonymous project IDs** (e.g. `Project-1a2b3c4d5e`), not real folder names/paths.

## Important warning (performance)
Do **not** watch entire drives (e.g. `C:\` or `/`) or very large folders (like your whole home directory). That can cause excessive CPU/memory usage and long scans. Prefer **specific project folders** and use excludes.

## What gets committed to git
Inside your configured repo, the agent writes:
- `reports/YYYY-MM-DD/HHmmss.json` (aggregated event)
- `reports/YYYY-MM-DD/HHmmss.md` (human summary)
- `docs/index.html` + `docs/events.json` (GitHub Pages site)
- `viz/index.html` + `viz/events.json` (local copy; same content)

## Set up the repo to push reports to (required)
You need a **separate git repo** (public or private) where the agent will commit the `reports/` and `viz/` folders.

### Recommended approach (GitHub)
1. Create a new empty repo on GitHub (private is fine), e.g. `prolific-activity`.
2. Clone it locally (pick any folder you want).
3. Make sure `git push` works from that folder (auth is required).

#### Windows example (PowerShell)
```powershell
cd C:\path\to
git clone https://github.com/YOUR_USER/prolific-activity.git
cd .\prolific-activity
git status
git commit --allow-empty -m "Initialize activity repo"
git push -u origin main
```

#### Linux example
```bash
cd /path/to
git clone https://github.com/YOUR_USER/prolific-activity.git
cd prolific-activity
git status
git commit --allow-empty -m "Initialize activity repo"
git push -u origin main
```

Notes:
- If your default branch is `master` (or anything else), set `agent.branch` in the config to match.
- For authentication:
  - HTTPS usually requires a GitHub token (PAT) or your OS credential manager.
  - SSH requires an SSH key loaded for your GitHub account.

## How estimation works (no content reads)
- **Languages used**: inferred by file extension (e.g. `.py`, `.ts`, `.js`).
- **Estimated LOC**: derived from **byte deltas** only, using `bytes_per_loc` (slightly optimistic defaults; configurable per language).

## Requirements
- Python **3.11+**
- `git` installed (for commit/push)
- UI: Tkinter (included on Windows/macOS Python; on some Linux distros you may need package `python3-tk`)

## Install
You have two ways to install/run:

### Option A (recommended): one-click UI launcher (no commands)

#### Windows
- Install **Python 3.11+** (from python.org). During install, check **“Add Python to PATH”**.
- Then **double‑click**:
  - `Launch-Prolific-Git-Active.bat`

This will create a local `.venv/`, install the app, and open the UI.

#### Linux
- Ensure `python3` is installed.
- Run:

```bash
chmod +x ./launch-ui.sh
./launch-ui.sh
```

### Option B: manual install (CLI/UI entry points)
From the project folder:

```bash
pip install -e .
```

## Quick start (CLI)
Create config (repeat `--scan-path` to watch multiple folders):

### Linux example

```bash
prolific-agent init \
  --scan-path "/path/to/project1" \
  --scan-path "/path/to/project2" \
  --repo-path "/path/to/activity-report-repo"
```

### Windows example (PowerShell)

```powershell
prolific-agent init `
  --scan-path "C:\path\to\project1" `
  --scan-path "C:\path\to\project2" `
  --repo-path "C:\path\to\activity-report-repo"
```

Run one cycle:

```bash
prolific-agent run
```

Check config:

```bash
prolific-agent status
```

## Quick start (UI)
Launch:

```bash
prolific-agent ui
```

Or:

```bash
prolific-agent-ui
```

In the UI you can add/remove watch folders, save config, and click **Run now**.

## Scheduling (background)
Scheduling is **manual by design**: installing a background timer/service modifies your OS (Scheduled Task / systemd). We provide scripts, but you choose when to run them.

## Enable the bubblemap on GitHub Pages
The interactive bubblemap is generated as a small static site in `docs/`.

![Prolific bubblemap visualization](prolific-visualization.png)

### GitHub Pages setup (repo settings)
1. Go to your activity repo on GitHub → **Settings** → **Pages**.
2. Under **Build and deployment**:
   - Source: **Deploy from a branch**
   - Branch: your branch (usually `main`)
   - Folder: **/docs**
3. Save. After it deploys, your bubblemap will be at your repo’s GitHub Pages URL.

If you don’t see updates immediately, wait a minute and refresh (Pages deployments are not instant).

### Windows Scheduled Task
- Scripts: `scripts/install_windows.ps1`, `scripts/uninstall_windows.ps1`
- Install example (PowerShell):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1 `
  -ConfigPath "$HOME\.prolific\config.toml" `
  -IntervalHours 2
```

- Uninstall example:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\uninstall_windows.ps1
```

### Linux systemd user timer
- Scripts: `scripts/install_linux.sh`, `scripts/uninstall_linux.sh`
- Install example:

```bash
bash scripts/install_linux.sh "$HOME/.prolific/config.toml" 2
```

- Uninstall example:

```bash
bash scripts/uninstall_linux.sh
```

Usage examples are in `scripts/README.md`.

## Configuration
Default config location:
- `~/.prolific/config.toml`

Key fields:
- `agent.scan_paths`: list of folders to watch
- `agent.repo_path`: target git repo for reports/viz
- `agent.exclude_globs`: exclude patterns (recommended)
- `agent.bytes_per_loc`: per-language calibration
- `agent.push`: set false to commit without pushing
- `agent.branch` / `agent.remote`: git target

## Troubleshooting
- **Push fails**: the run still commits locally and logs the push error to `~/.prolific/agent.log`. Next run will retry pushing the newer commit.
- **Nothing committed**: if `reports/` and `viz/` didn’t change, there’s nothing to commit (or the repo isn’t a valid git repo).
- **Linux UI fails to start**: install Tkinter (commonly `python3-tk`) and retry.

