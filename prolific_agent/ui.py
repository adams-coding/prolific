from __future__ import annotations

import os
from pathlib import Path
import platform
import threading
import time
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import subprocess
import importlib

from prolific_agent.config import AgentConfig, default_config_path, load_config
import prolific_agent.run_cycle
import prolific_agent.viz


def _safe_int(s: str, fallback: int) -> int:
    try:
        return int(s.strip())
    except Exception:
        return fallback


class ProlificAgentUI(tk.Tk):
    def __init__(self, config_path: Path | None = None) -> None:
        super().__init__()
        self.title("Prolific: Git Active")
        self.geometry("860x640")

        self.config_path = config_path or default_config_path()

        # Form variables
        self.watch_paths: list[str] = []
        self.repo_path_var = tk.StringVar()
        self.interval_var = tk.StringVar(value="2")
        self.branch_var = tk.StringVar(value="main")
        self.remote_var = tk.StringVar(value="origin")
        self.push_var = tk.BooleanVar(value=True)
        self.excludes_var = tk.StringVar(value="")

        self._build()
        self._load_if_exists()

    def _build(self) -> None:
        pad = {"padx": 10, "pady": 6}

        frm = tk.Frame(self)
        frm.pack(fill="both", expand=False)

        # Config path row
        row0 = tk.Frame(frm)
        row0.pack(fill="x", **pad)
        tk.Label(row0, text="Config path:").pack(side="left")
        tk.Label(row0, text=str(self.config_path), fg="#555").pack(side="left", padx=8)

        # Watch folders
        row_watch = tk.Frame(frm)
        row_watch.pack(fill="x", **pad)
        tk.Label(row_watch, text="Watch folders (metadata only):").pack(anchor="w")

        warn = (
            "Warning: Do NOT add entire drives or very large folders. "
            "This can cause high CPU/memory usage."
        )
        tk.Label(row_watch, text=warn, fg="#b00020").pack(anchor="w", pady=(2, 6))

        row_watch2 = tk.Frame(frm)
        row_watch2.pack(fill="x", **pad)
        self.watch_list = tk.Listbox(row_watch2, height=4)
        self.watch_list.pack(side="left", fill="both", expand=True)
        btns = tk.Frame(row_watch2)
        btns.pack(side="left", padx=8)
        tk.Button(btns, text="Add…", command=self._add_watch).pack(fill="x")
        tk.Button(btns, text="Remove", command=self._remove_watch).pack(fill="x", pady=4)
        # Repo path
        self._path_row(frm, "Git repo folder (reports/viz):", self.repo_path_var, self._choose_repo, pad)

        # Interval / branch / remote
        row3 = tk.Frame(frm)
        row3.pack(fill="x", **pad)
        tk.Label(row3, text="Interval hours (1-4):").pack(side="left")
        tk.Entry(row3, width=6, textvariable=self.interval_var).pack(side="left", padx=6)
        tk.Label(row3, text="Branch:").pack(side="left", padx=12)
        tk.Entry(row3, width=12, textvariable=self.branch_var).pack(side="left", padx=6)
        tk.Label(row3, text="Remote:").pack(side="left", padx=12)
        tk.Entry(row3, width=12, textvariable=self.remote_var).pack(side="left", padx=6)
        tk.Checkbutton(row3, text="Push", variable=self.push_var).pack(side="left", padx=12)

        # Excludes
        row5 = tk.Frame(frm)
        row5.pack(fill="x", **pad)
        tk.Label(row5, text="Exclude globs (comma-separated):").pack(side="left")
        tk.Entry(row5, textvariable=self.excludes_var).pack(side="left", fill="x", expand=True, padx=6)

        # Buttons
        row6 = tk.Frame(frm)
        row6.pack(fill="x", **pad)
        tk.Button(row6, text="Save config", command=self._save_config).pack(side="left")
        tk.Button(row6, text="Run now", command=self._run_now).pack(side="left", padx=8)
        tk.Button(row6, text="Test scheduler", command=self._test_scheduler).pack(side="left", padx=8)
        tk.Button(row6, text="Installer help", command=self._installer_help).pack(side="left", padx=8)

        # Output
        out_frame = tk.Frame(self)
        out_frame.pack(fill="both", expand=True, padx=10, pady=10)
        tk.Label(out_frame, text="Output:").pack(anchor="w")
        self.output = scrolledtext.ScrolledText(out_frame, height=18)
        self.output.pack(fill="both", expand=True)

        self._log("Ready. This app never reads file contents; it only uses file metadata (size/mtime/extensions).")

    def _path_row(self, parent: tk.Widget, label: str, var: tk.StringVar, choose_cb, pad) -> None:
        row = tk.Frame(parent)
        row.pack(fill="x", **pad)
        tk.Label(row, text=label).pack(side="left")
        tk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True, padx=6)
        tk.Button(row, text="Browse…", command=choose_cb).pack(side="left")

    def _choose_scan(self) -> None:
        self._add_watch()

    def _add_watch(self) -> None:
        d = filedialog.askdirectory(title="Select watch folder")
        if not d:
            return
        d = str(Path(d).expanduser())
        if d in self.watch_paths:
            return
        self.watch_paths.append(d)
        self._refresh_watch_list()

    def _remove_watch(self) -> None:
        sel = list(self.watch_list.curselection())
        if not sel:
            return
        idx = int(sel[0])
        if 0 <= idx < len(self.watch_paths):
            self.watch_paths.pop(idx)
            self._refresh_watch_list()

    def _choose_repo(self) -> None:
        d = filedialog.askdirectory(title="Select git repo folder")
        if d:
            self.repo_path_var.set(d)

    def _load_if_exists(self) -> None:
        if not self.config_path.exists():
            self._log(f"No config found at {self.config_path}. Fill fields and click Save config.")
            return
        try:
            cfg = load_config(self.config_path)
        except Exception as e:
            self._log(f"Failed to load config: {e}")
            return

        self.watch_paths = [str(p) for p in cfg.scan_paths]
        self._refresh_watch_list()
        self.repo_path_var.set(str(cfg.repo_path))
        self.interval_var.set(str(cfg.interval_hours))
        self.branch_var.set(cfg.branch)
        self.remote_var.set(cfg.remote)
        self.push_var.set(bool(cfg.push))
        self.excludes_var.set(", ".join(cfg.exclude_globs))
        self._log(f"Loaded config: {self.config_path}")

    def _refresh_watch_list(self) -> None:
        self.watch_list.delete(0, "end")
        for p in self.watch_paths:
            self.watch_list.insert("end", p)

    def _current_cfg(self) -> AgentConfig:
        scan_paths = [Path(p).expanduser() for p in self.watch_paths]
        repo_path = Path(self.repo_path_var.get()).expanduser()
        excludes = [g.strip() for g in self.excludes_var.get().split(",") if g.strip()]
        cfg = AgentConfig(
            scan_paths=scan_paths,
            repo_path=repo_path,
            interval_hours=_safe_int(self.interval_var.get(), 2),
            branch=self.branch_var.get().strip() or "main",
            remote=self.remote_var.get().strip() or "origin",
            push=bool(self.push_var.get()),
            bubble_metric="net_loc",
            exclude_globs=excludes,
        )
        cfg.validate()
        return cfg

    def _save_config(self) -> None:
        try:
            cfg = self._current_cfg()
        except Exception as e:
            messagebox.showerror("Invalid config", str(e))
            return

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(cfg.to_toml(), encoding="utf-8")
        self._log(f"Saved config: {self.config_path}")
        if messagebox.askyesno(
            "Install background schedule?",
            "Do you want to install background scheduling now?\n\n"
            "This will create a Windows Scheduled Task or a Linux systemd timer so it runs automatically.",
        ):
            self._installer_help(run_now=True)

    def _run_now(self) -> None:
        try:
            self._log("=== Run now button clicked ===")
            
            try:
                cfg = self._current_cfg()
            except Exception as e:
                self._log(f"Config validation failed: {e}")
                messagebox.showerror("Invalid config", str(e))
                return

            # Check if this is the first run
            from prolific_agent.config import default_state_dir
            state_dir = default_state_dir()
            marker_path = state_dir / "known_projects.json"
            is_first_run = not marker_path.exists()

            if is_first_run:
                self._log("=" * 60)
                self._log("FIRST RUN DETECTED")
                self._log("This run will establish a baseline for all existing folders.")
                self._log("No activity events will be created on this first run.")
                self._log("Changes will be detected starting from the NEXT run.")
                self._log("(including auto scheduled runs)")
                self._log("=" * 60)

            self._log("Running.. this may take a minute")
            self.update()  # Force UI update to show the message immediately
            
            try:
                # Hot-reload generator modules so you don't have to restart the UI after code updates.
                # This is safe because the agent is single-user/single-process and run cycles are short.
                importlib.reload(prolific_agent.viz)
                prolific_agent.run_cycle = importlib.reload(prolific_agent.run_cycle)
                result = prolific_agent.run_cycle.run_once(cfg)
            except Exception as e:
                self._log(f"Run failed: {e}")
                import traceback
                self._log(traceback.format_exc())
                messagebox.showerror("Run failed", str(e))
                return

            self._log(f"event_id={result.get('event_id')}")
            self._log(f"net_loc_estimate={result.get('net_loc_estimate')}")
            self._log(f"churn_loc_estimate={result.get('churn_loc_estimate')}")
            self._log(f"total_delta_bytes={result.get('total_delta_bytes')}")
            self._log(f"report_json={result.get('report_json')}")
            self._log(f"report_md={result.get('report_md')}")
            self._log(f"viz_events={result.get('viz_events')}")
            git = result.get("git") or {}
            if isinstance(git, dict):
                self._log(f"git_message={git.get('message')}")
                if git.get("error"):
                    self._log(f"git_error={git.get('error')}")
            self._log("Done.")
        except Exception as e:
            self._log(f"FATAL ERROR in _run_now: {e}")
            import traceback
            self._log(traceback.format_exc())
            messagebox.showerror("Fatal error", str(e))

    def _test_scheduler(self) -> None:
        """
        Run a one-off Scheduled Task that executes the same command as the scheduler.

        This helps validate that the Scheduled Task environment (python/venv/git auth)
        matches what "Run now" does.
        """
        if platform.system() != "Windows":
            messagebox.showinfo("Not supported", "Test scheduler is only supported on Windows.")
            return

        try:
            cfg = self._current_cfg()
        except Exception as e:
            messagebox.showerror("Invalid config", str(e))
            return

        app_root = Path(__file__).resolve().parents[1]
        venv_python = app_root / ".venv" / "Scripts" / "python.exe"
        if not venv_python.exists():
            messagebox.showerror(
                "Missing .venv",
                f"Expected venv python not found:\n{venv_python}\n\n"
                "Run the Windows launcher once to create .venv, then try again.",
            )
            return

        # Use a dedicated test log so it's easy to inspect.
        state_dir = Path(os.path.expanduser("~")) / ".prolific"
        state_dir.mkdir(parents=True, exist_ok=True)
        log_path = state_dir / "scheduler_test.log"

        task_name = f"ProlificGitActive_Test_{int(time.time())}"
        cmd = (
            f'cmd.exe /c ""{venv_python}" -m prolific_agent.cli run --config "{self.config_path}" '
            f'>> "{log_path}" 2>&1"'
        )

        def run_test() -> None:
            def ui_log(msg: str) -> None:
                self.after(0, lambda: self._log(msg))

            def run_hidden(args: list[str]) -> subprocess.CompletedProcess[str]:
                kwargs = {"text": True, "capture_output": True, "check": False}
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
                return subprocess.run(args, **kwargs)

            ui_log("=== Test scheduler ===")
            ui_log(f"Scheduling one-off task: {task_name}")
            ui_log(f"Log file: {log_path}")

            # Ensure log file exists so missing execution is obvious.
            try:
                log_path.write_text("", encoding="utf-8")
            except Exception:
                pass

            cp_create = run_hidden(
                [
                    "schtasks",
                    "/Create",
                    "/F",
                    "/SC",
                    "ONCE",
                    # Use a dummy schedule time/date; we force-run it immediately via /Run.
                    "/SD",
                    "01/01/2000",
                    "/ST",
                    "00:00",
                    "/TN",
                    task_name,
                    "/TR",
                    cmd,
                ]
            )
            if cp_create.returncode != 0:
                ui_log(f"[test_scheduler] schtasks create failed: {cp_create.stderr.strip()}")
                self.after(
                    0,
                    lambda: messagebox.showerror("Test scheduler failed", cp_create.stderr.strip() or "schtasks create failed"),
                )
                return

            # Force-run immediately to avoid locale-specific date format issues.
            ui_log("Forcing the task to run now (schtasks /Run)...")
            cp_run = run_hidden(["schtasks", "/Run", "/TN", task_name])
            if cp_run.returncode != 0:
                ui_log(f"[test_scheduler] schtasks run failed: {cp_run.stderr.strip()}")

            # Poll until the run finishes (or timeout).
            # 267011 = has not yet run, 267009 = currently running.
            ui_log("Waiting for task to execute and finish (up to ~180s)...")
            deadline = time.time() + 180
            last_result_line = None
            status_line = None
            while time.time() < deadline:
                cp_q = run_hidden(["schtasks", "/Query", "/TN", task_name, "/V", "/FO", "LIST"])
                if cp_q.returncode == 0 and cp_q.stdout:
                    lines_all = [ln.strip() for ln in cp_q.stdout.splitlines() if ln.strip()]
                    status_line = next((ln for ln in lines_all if ln.startswith("Status:")), None)
                    last_result_line = next((ln for ln in lines_all if ln.startswith("Last Result:")), None)

                    # If still running, keep waiting.
                    if last_result_line and "267009" in last_result_line:
                        time.sleep(3)
                        continue

                    # If it has run and is no longer running, stop polling.
                    if last_result_line and "267011" not in last_result_line:
                        break

                time.sleep(3)

            cp_query = run_hidden(["schtasks", "/Query", "/TN", task_name, "/V", "/FO", "LIST"])
            if cp_query.returncode == 0 and cp_query.stdout:
                # Pull the key fields for quick visibility.
                lines = [ln.strip() for ln in cp_query.stdout.splitlines() if ln.strip()]
                for key in ("Last Run Time:", "Last Result:", "Task To Run:"):
                    hit = next((ln for ln in lines if ln.startswith(key)), None)
                    if hit:
                        ui_log(f"[test_scheduler] {hit}")
            else:
                ui_log(f"[test_scheduler] schtasks query failed: {cp_query.stderr.strip()}")

            # Delete the test task (only after we've given it time to finish).
            _ = run_hidden(["schtasks", "/Delete", "/F", "/TN", task_name])

            # Tail the log for quick diagnosis.
            try:
                if log_path.exists():
                    tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-60:]
                    ui_log("=== scheduler_test.log (tail) ===")
                    for ln in tail:
                        ui_log(ln)
            except Exception as e:
                ui_log(f"[test_scheduler] failed to read log: {e}")

            ui_log("=== Test scheduler done ===")

        threading.Thread(target=run_test, daemon=True).start()

    def _installer_help(self, run_now: bool = False) -> None:
        sysname = platform.system().lower()
        scripts_dir = Path(__file__).resolve().parents[1] / "scripts"

        interval = self.interval_var.get().strip() or "2"

        if "windows" in sysname:
            # Pass AppRoot so the Scheduled Task uses THIS repo's .venv (consistent with UI).
            app_root = str(scripts_dir.parent)
            install_cmd = (
                f'powershell -ExecutionPolicy Bypass -File "{scripts_dir / "install_windows.ps1"}" '
                f'-ConfigPath "{self.config_path}" -IntervalHours {interval} -AppRoot "{app_root}"'
            )
            uninstall_cmd = f'powershell -ExecutionPolicy Bypass -File "{scripts_dir / "uninstall_windows.ps1"}"'
            title = "Windows Scheduled Task"
        else:
            # Third arg is app root (repo root), so systemd runs the same .venv if present.
            app_root = str(scripts_dir.parent)
            install_cmd = f'bash "{scripts_dir / "install_linux.sh"}" "{self.config_path}" {interval} "{app_root}"'
            uninstall_cmd = f'bash "{scripts_dir / "uninstall_linux.sh"}"'
            title = "Linux systemd user timer"

        # Dialog with copy/run
        dlg = tk.Toplevel(self)
        dlg.title(f"Install scheduling — {title}")
        dlg.geometry("760x360")

        tk.Label(
            dlg,
            text=(
                "This will install background scheduling so the agent runs automatically.\n"
                "Nothing is installed unless you confirm and run it."
            ),
            justify="left",
        ).pack(anchor="w", padx=12, pady=10)

        tk.Label(dlg, text="Install command:").pack(anchor="w", padx=12)
        txt = scrolledtext.ScrolledText(dlg, height=4)
        txt.pack(fill="x", expand=False, padx=12, pady=6)
        txt.insert("end", install_cmd + "\n")
        txt.configure(state="disabled")

        tk.Label(dlg, text="Uninstall command:").pack(anchor="w", padx=12)
        txt2 = scrolledtext.ScrolledText(dlg, height=3)
        txt2.pack(fill="x", expand=False, padx=12, pady=6)
        txt2.insert("end", uninstall_cmd + "\n")
        txt2.configure(state="disabled")

        btn_row = tk.Frame(dlg)
        btn_row.pack(fill="x", padx=12, pady=10)

        def copy_install() -> None:
            self.clipboard_clear()
            self.clipboard_append(install_cmd)
            self._log("Copied install command to clipboard.")

        def run_install() -> None:
            if not messagebox.askyesno(
                "Confirm install",
                "Run the install command now?\n\nThis will modify your OS scheduler.",
                parent=dlg,
            ):
                return
            try:
                # Execute via shell so quoting matches the displayed command.
                kwargs = {"shell": True, "text": True, "capture_output": True}
                if platform.system() == "Windows":
                    kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
                cp = subprocess.run(install_cmd, **kwargs)
                self._log(f"[install] exit={cp.returncode}")
                if cp.stdout:
                    self._log(cp.stdout.strip())
                if cp.stderr:
                    self._log(cp.stderr.strip())
                if cp.returncode == 0:
                    messagebox.showinfo("Installed", "Scheduling installed successfully.", parent=dlg)
                else:
                    messagebox.showerror(
                        "Install failed",
                        "Install command failed. See Output for details.",
                        parent=dlg,
                    )
            except Exception as e:
                self._log(f"[install] failed: {e}")
                messagebox.showerror("Install failed", str(e), parent=dlg)

        tk.Button(btn_row, text="Copy install command", command=copy_install).pack(side="left")
        tk.Button(btn_row, text="Run install now", command=run_install).pack(side="left", padx=8)
        tk.Button(btn_row, text="Close", command=dlg.destroy).pack(side="right")

        # Optionally auto-run (still requires confirmation prompt above).
        if run_now:
            dlg.after(50, run_install)

    def _log(self, line: str) -> None:
        self.output.insert("end", line.rstrip() + "\n")
        self.output.see("end")


def launch(config_path: Path | None = None) -> None:
    # Tkinter import errors on some minimal Linux installs (missing python3-tk).
    # We surface a clean message instead of a stack trace.
    try:
        app = ProlificAgentUI(config_path=config_path)
    except Exception as e:
        raise SystemExit(f"Failed to start UI: {e}") from e
    app.mainloop()


