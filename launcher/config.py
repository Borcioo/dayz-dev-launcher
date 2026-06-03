"""Launcher config: own config.json, independent of bin/_config.bat."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path

_DAYZ = r"E:\Steam\steamapps\common\DayZ"

DEFAULTS = {
    "dayz_path": _DAYZ,
    "dayz_tools_path": r"E:\Steam\steamapps\common\DayZ Tools",
    "profiles_path": _DAYZ + r"\profiles",
    "client_profiles_path": _DAYZ + r"\profiles_client",
    "exe_debug": "DayZDiag_x64.exe",
    "exe_normal": "DayZServer_x64.exe",
    "client_exe_debug": "DayZDiag_x64.exe",
    "client_exe_normal": "DayZ_x64.exe",
    # mod homes only — NOT the DayZ install root (that surfaces vanilla DLC
    # like bliss/sakhal and workshop copies). Add !Workshop yourself if needed.
    "scan_roots": [r"P:\@Dependencies", r"P:\@PackedMods", "P:\\"],
    "port": 2302,
    "mission": "./mpmissions/dayzOffline.chernarusplus",
    "player_name": "DevMacie",
    "config_name": "serverDZ.cfg",
    "connect_ip": "127.0.0.1",  # client -connect target
    "mods": [],
    "logs_shown": ["script", "rpt", "adm", "client"],
    "mode": "debug",
    "mod_width_idx": 0,  # mods column width step (0=narrow 1=med 2=wide)
    "active_preset": "",  # name of the preset to load on startup ("" = none)
    # extra launch flags appended after the core args (editable in the UI).
    # core args (-server/-profiles/-mod/-config/-port/-mission/-connect/-name)
    # are always built from config; these are everything else.
    "server_params": ["-filePatching", "-dologs", "-adminLog", "-freezecheck"],
    "client_params": ["-window", "-nosplash", "-filePatching", "-doLogs",
                      "-scriptDebug=true"],
}

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config.json"


@dataclass
class Config:
    dayz_path: str
    dayz_tools_path: str
    profiles_path: str
    client_profiles_path: str
    exe_debug: str
    exe_normal: str
    client_exe_debug: str
    client_exe_normal: str
    scan_roots: list[str]
    port: int
    mission: str
    player_name: str
    config_name: str
    connect_ip: str = "127.0.0.1"
    mods: list[dict] = field(default_factory=list)
    logs_shown: list[str] = field(default_factory=list)
    mode: str = "debug"
    mod_width_idx: int = 0
    active_preset: str = ""
    server_params: list[str] = field(default_factory=list)
    client_params: list[str] = field(default_factory=list)


def load(path: Path = DEFAULT_PATH) -> Config:
    data = dict(DEFAULTS)
    path = Path(path)
    if path.exists():
        data.update(json.loads(path.read_text(encoding="utf-8")))
    # keep only known keys, fill any missing with defaults
    known = {k: data.get(k, DEFAULTS[k]) for k in DEFAULTS}
    return Config(**known)


def save(cfg: Config, path: Path = DEFAULT_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(cfg), indent=2), encoding="utf-8")


# scalar keys the user may edit via `dzl config set` or the TUI config screen.
# (Lists like scan_roots/mods have their own helpers; logs_shown/mode are UI state.)
EDITABLE_SCALARS = (
    "dayz_path", "dayz_tools_path", "profiles_path", "client_profiles_path",
    "exe_debug", "exe_normal", "client_exe_debug", "client_exe_normal",
    "port", "mission", "player_name", "config_name", "connect_ip",
)


def set_scalar(cfg: Config, key: str, value) -> Config:
    """Set one editable scalar field, coercing types. Raises KeyError for an
    unknown/non-editable key and ValueError if port isn't an int."""
    if key not in EDITABLE_SCALARS:
        raise KeyError(key)
    if key == "port":
        value = int(value)
    setattr(cfg, key, value)
    return cfg


def add_root(cfg: Config, path: str) -> Config:
    """Append a mod scan-root (no duplicates, order preserved)."""
    if path and path not in cfg.scan_roots:
        cfg.scan_roots.append(path)
    return cfg


def remove_root(cfg: Config, path: str) -> Config:
    cfg.scan_roots = [r for r in cfg.scan_roots if r != path]
    return cfg


# ---- named presets (per-project setups) ----
# A preset is a full config snapshot stored as presets/<name>.json next to the
# active config.json. Loading one makes it the active config.

_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.-]+")


def _safe_name(name: str) -> str:
    return _SAFE_NAME.sub("_", name.strip()) or "preset"


def presets_dir(path: Path = DEFAULT_PATH) -> Path:
    return Path(path).parent / "presets"


def list_presets(path: Path = DEFAULT_PATH) -> list[str]:
    d = presets_dir(path)
    return sorted(p.stem for p in d.glob("*.json")) if d.is_dir() else []


def save_preset(cfg: Config, name: str, path: Path = DEFAULT_PATH) -> Path:
    d = presets_dir(path)
    d.mkdir(parents=True, exist_ok=True)
    target = d / f"{_safe_name(name)}.json"
    target.write_text(json.dumps(asdict(cfg), indent=2), encoding="utf-8")
    return target


def load_preset(name: str, path: Path = DEFAULT_PATH) -> Config:
    """Load a preset into a Config (reuses load() so missing keys get defaults)."""
    target = presets_dir(path) / f"{_safe_name(name)}.json"
    if not target.exists():
        raise FileNotFoundError(name)
    return load(target)


def delete_preset(name: str, path: Path = DEFAULT_PATH) -> bool:
    target = presets_dir(path) / f"{_safe_name(name)}.json"
    if target.exists():
        target.unlink()
        return True
    return False


def preset_file(name: str, path: Path = DEFAULT_PATH) -> Path:
    return presets_dir(path) / f"{_safe_name(name)}.json"


def set_active_preset(name: str, config_path: Path = DEFAULT_PATH) -> None:
    """Persist the active-preset pointer into config.json (only the pointer)."""
    base = load(config_path)
    base.active_preset = name or ""
    save(base, config_path)


def resolve_active(config_path: Path = DEFAULT_PATH):
    """Resolve the working config + where edits should be saved.

    Reads config.json; if it points at a preset that still exists, that preset
    file is the working source (so startup loads the last activated preset).
    Otherwise config.json itself is the source. Returns
    (cfg, save_path, active_name)."""
    config_path = Path(config_path)
    base = load(config_path)
    name = base.active_preset
    if name:
        pf = preset_file(name, config_path)
        if pf.exists():
            return load(pf), pf, name
    return base, config_path, ""


def set_roots(cfg: Config, paths: list[str]) -> Config:
    """Replace the scan-root list wholesale (used by the TUI form); trims blanks
    and de-dupes while keeping order."""
    seen: list[str] = []
    for p in paths:
        p = p.strip()
        if p and p not in seen:
            seen.append(p)
    cfg.scan_roots = seen
    return cfg
