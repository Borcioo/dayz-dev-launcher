"""Build the launch argv (pure) and manage server/client processes."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from .config import Config


def procs_path(config_path) -> Path:
    """The PID statefile lives next to config.json."""
    return Path(config_path).parent / ".dzl-procs.json"


def pid_image(pid: int):
    """Return the image (exe) name for a PID, or None if not running."""
    out = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
        capture_output=True, text=True,
    )
    line = out.stdout.strip()
    if not line or line.upper().startswith("INFO:"):
        return None
    return line.split('","')[0].strip('"')


def is_pid_alive(pid: int) -> bool:
    return pid_image(pid) is not None


def read_procs(config_path) -> dict:
    """Load the statefile and reconcile: keep only entries whose PID is still
    alive AND still the recorded exe. Missing/corrupt -> {}."""
    p = procs_path(config_path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    live = {}
    changed = False
    for target, info in data.items():
        try:
            pid = int(info["pid"])
        except (KeyError, TypeError, ValueError):
            changed = True
            continue
        img = pid_image(pid)
        if img is not None and img.lower() == str(info.get("exe", "")).lower():
            live[target] = info
        else:
            changed = True
    if changed:
        _write_procs(config_path, live)
    return live


def _write_procs(config_path, data: dict) -> None:
    p = procs_path(config_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def write_proc(config_path, target: str, pid: int, mode: str,
               source: str, exe: str) -> None:
    data = {}
    p = procs_path(config_path)
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                data = {}
        except (ValueError, OSError):
            data = {}
    data[target] = {"pid": pid, "mode": mode, "source": source, "exe": exe}
    _write_procs(config_path, data)


def clear_proc(config_path, target: str) -> None:
    p = procs_path(config_path)
    if not p.exists():
        return
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return
    if isinstance(data, dict) and target in data:
        del data[target]
        _write_procs(config_path, data)


def open_folder(path) -> bool:
    """Open a folder in Windows Explorer. Returns False if it doesn't exist."""
    p = Path(path)
    if not p.is_dir():
        return False
    os.startfile(str(p))  # noqa: S606 (Windows-only launcher)
    return True


def open_log_window(path, tail: int = 200) -> bool:
    """Pop a log out into its own console that follows it (PowerShell
    Get-Content -Wait). Returns False if the file doesn't exist yet."""
    p = Path(path)
    if not p.is_file():
        return False
    ps = f"Get-Content -LiteralPath '{p}' -Wait -Tail {tail}"
    subprocess.Popen(  # noqa: S602 (Windows console pop-out)
        f'start "dzl log: {p.name}" powershell -NoExit -Command "{ps}"',
        shell=True,
    )
    return True


def mod_paths_string(cfg: Config) -> str:
    """``;``-joined enabled mod paths (all sides). No quotes, no trailing ';'."""
    enabled = [m["path"] for m in cfg.mods if m.get("enabled")]
    return ";".join(enabled)


def _join(paths: list[str]) -> str:
    return ";".join(paths)


def mods_for_target(cfg: Config, target: str) -> list[str]:
    """The ``-mod=`` list for a target, by per-mod side:
    - server gets ``both`` mods (server-only go to ``-serverMod``);
    - client gets ``both`` + ``client``-only mods."""
    out = []
    for m in cfg.mods:
        if not m.get("enabled"):
            continue
        side = m.get("side", "both")
        if target == "server" and side == "both":
            out.append(m["path"])
        elif target == "client" and side in ("both", "client"):
            out.append(m["path"])
    return out


def server_only_mods(cfg: Config) -> list[str]:
    """Enabled mods flagged server-side only -> DayZ ``-serverMod=``."""
    return [m["path"] for m in cfg.mods
            if m.get("enabled") and m.get("side", "both") == "server"]


def server_exe(cfg: Config, mode: str) -> str:
    return cfg.exe_debug if mode == "debug" else cfg.exe_normal


def client_exe(cfg: Config, mode: str) -> str:
    return cfg.client_exe_debug if mode == "debug" else cfg.client_exe_normal


def build_args(mode: str, target: str, cfg: Config) -> list[str]:
    """Full argv for a (mode, target). Core args are built from config; the rest
    are the editable cfg.server_params / cfg.client_params. Pure: no side
    effects. (mode selects the exe elsewhere; it doesn't change the args here.)"""
    # -profiles is relative to the DayZ dir (spawn cwd); use each configured
    # dir's basename so server and client write to separate profile trees and
    # their logs never collide.
    server_profiles = Path(cfg.profiles_path).name
    client_profiles = Path(cfg.client_profiles_path).name
    if target == "server":
        args = [
            "-server",
            f"-profiles={server_profiles}",
            f"-mod={_join(mods_for_target(cfg, 'server'))}",
            f"-config={cfg.config_name}",
            f"-port={cfg.port}",
        ]
        server_only = server_only_mods(cfg)
        if server_only:
            args.append(f"-serverMod={_join(server_only)}")
        return args + list(cfg.server_params)
    if target == "client":
        args = [
            f"-profiles={client_profiles}",
            f"-mod={_join(mods_for_target(cfg, 'client'))}",
            f"-mission={cfg.mission}",
            "-connect=127.0.0.1",
            f"-port={cfg.port}",
            f"-name={cfg.player_name}",
        ]
        return args + list(cfg.client_params)
    raise ValueError(f"unknown target: {target}")


# ---- process lifecycle (manually verified; thin wrappers over subprocess) ----

def is_running(exe: str) -> bool:
    out = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {exe}"],
        capture_output=True, text=True,
    )
    return exe.lower() in out.stdout.lower()


def stop(exe: str) -> None:
    subprocess.run(["taskkill", "/F", "/IM", exe], capture_output=True, text=True)


def spawn(mode: str, target: str, cfg: Config, *, source: str = "cli",
          config_path=None) -> subprocess.Popen:
    exe = server_exe(cfg, mode) if target == "server" else client_exe(cfg, mode)
    cmd = [str(Path(cfg.dayz_path) / exe), *build_args(mode, target, cfg)]
    proc = subprocess.Popen(cmd, cwd=cfg.dayz_path)
    if config_path is not None:
        write_proc(config_path, target, proc.pid, mode, source, exe)
    return proc


def _raw_procs(config_path) -> dict:
    """Read the statefile as-is without any live-PID reconciliation."""
    p = procs_path(config_path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, ValueError, OSError):
        return {}


def stop_target(target: str, cfg: Config, config_path) -> None:
    """Stop a target by the PID recorded in the statefile (works no matter who
    started it; required in debug where server and client share DayZDiag). Falls
    back to image-name kill if nothing is recorded."""
    procs = _raw_procs(config_path)
    info = procs.get(target)
    if info:
        subprocess.run(["taskkill", "/F", "/PID", str(info["pid"])],
                       capture_output=True, text=True)
    else:
        mode = (info or {}).get("mode", cfg.mode)
        exe = server_exe(cfg, mode) if target == "server" else client_exe(cfg, mode)
        stop(exe)
    clear_proc(config_path, target)


def restart_server(mode: str, cfg: Config, config_path=None,
                   source: str = "cli") -> subprocess.Popen:
    if config_path is not None:
        stop_target("server", cfg, config_path)
    else:
        stop(server_exe(cfg, mode))
    return spawn(mode, "server", cfg, source=source, config_path=config_path)
