import json
import pytest
from launcher.config import (
    Config, load, save, DEFAULTS,
    set_scalar, add_root, remove_root, set_roots,
    save_preset, load_preset, list_presets, delete_preset,
    resolve_active, set_active_preset, preset_file, ensure_default,
)


def test_load_missing_file_returns_defaults(tmp_path):
    cfg = load(tmp_path / "config.json")
    assert cfg.port == DEFAULTS["port"]
    assert cfg.mode == "debug"
    assert cfg.mods == []


def test_save_then_load_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    cfg = load(path)
    cfg.port = 2402
    cfg.mods = [{"path": "P:\\@CF", "enabled": True}]
    save(cfg, path)

    again = load(path)
    assert again.port == 2402
    assert again.mods == [{"path": "P:\\@CF", "enabled": True}]


def test_save_writes_valid_json(tmp_path):
    path = tmp_path / "config.json"
    save(load(path), path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "scan_roots" in data


def test_set_scalar_coerces_port_and_rejects_unknown(tmp_path):
    cfg = load(tmp_path / "config.json")
    set_scalar(cfg, "port", "2402")
    assert cfg.port == 2402  # coerced to int
    set_scalar(cfg, "dayz_path", r"D:\Games\DayZ")
    assert cfg.dayz_path == r"D:\Games\DayZ"
    with pytest.raises(KeyError):
        set_scalar(cfg, "mods", [])  # not an editable scalar


def test_add_and_remove_root_dedupe(tmp_path):
    cfg = load(tmp_path / "config.json")
    cfg.scan_roots = []
    add_root(cfg, r"P:\@Mods")
    add_root(cfg, r"P:\@Mods")  # dup ignored
    add_root(cfg, r"D:\dev")
    assert cfg.scan_roots == [r"P:\@Mods", r"D:\dev"]
    remove_root(cfg, r"P:\@Mods")
    assert cfg.scan_roots == [r"D:\dev"]


def test_set_roots_trims_blanks_and_dedupes(tmp_path):
    cfg = load(tmp_path / "config.json")
    set_roots(cfg, ["  P:\\a  ", "", "P:\\b", "P:\\a", "   "])
    assert cfg.scan_roots == ["P:\\a", "P:\\b"]


def test_preset_save_list_load_delete(tmp_path):
    path = tmp_path / "config.json"
    cfg = load(path)
    cfg.port = 2500
    cfg.mods = [{"path": "P:\\@CF", "enabled": True, "side": "both"}]
    save_preset(cfg, "Project A", path)

    assert list_presets(path) == ["Project_A"]   # name sanitized

    loaded = load_preset("Project A", path)
    assert loaded.port == 2500
    assert loaded.mods == cfg.mods

    assert delete_preset("Project A", path) is True
    assert list_presets(path) == []


def test_load_missing_preset_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_preset("nope", tmp_path / "config.json")


def test_resolve_active_falls_back_to_config(tmp_path):
    path = tmp_path / "config.json"
    cfg = load(path)
    cfg.port = 2200
    save(cfg, path)
    rcfg, save_path, name = resolve_active(path)
    assert name == ""
    assert rcfg.port == 2200
    assert save_path == path


def test_resolve_active_uses_pointed_preset(tmp_path):
    path = tmp_path / "config.json"
    cfg = load(path)
    cfg.port = 2700
    save_preset(cfg, "proj", path)
    set_active_preset("proj", path)
    rcfg, save_path, name = resolve_active(path)
    assert name == "proj"
    assert rcfg.port == 2700
    assert save_path == preset_file("proj", path)


def test_resolve_active_ignores_dangling_pointer(tmp_path):
    path = tmp_path / "config.json"
    set_active_preset("ghost", path)  # points at a preset that doesn't exist
    _, save_path, name = resolve_active(path)
    assert name == ""
    assert save_path == path


def test_ensure_default_seeds_and_activates_on_first_run(tmp_path):
    path = tmp_path / "config.json"
    cfg = load(path)
    cfg.port = 2345
    save(cfg, path)
    name = ensure_default(path)
    assert name == "default"
    assert "default" in list_presets(path)
    # active pointer persisted, and it captured the current config
    rcfg, save_path, active = resolve_active(path)
    assert active == "default"
    assert rcfg.port == 2345
    assert save_path == preset_file("default", path)


def test_ensure_default_is_noop_when_preset_already_active(tmp_path):
    path = tmp_path / "config.json"
    save_preset(load(path), "proj", path)
    set_active_preset("proj", path)
    assert ensure_default(path) == "proj"
    assert "default" not in list_presets(path)


def test_ensure_default_is_noop_when_presets_exist_but_none_active(tmp_path):
    path = tmp_path / "config.json"
    save_preset(load(path), "proj", path)  # exists, but not active
    assert ensure_default(path) == ""       # don't override the user's choice
    assert "default" not in list_presets(path)


def test_ensure_default_idempotent(tmp_path):
    path = tmp_path / "config.json"
    ensure_default(path)
    ensure_default(path)  # second call must not re-seed or clobber
    assert list_presets(path) == ["default"]


def test_dayz_server_path_defaults_empty(tmp_path):
    cfg = load(tmp_path / "config.json")
    assert cfg.dayz_server_path == ""


def test_dayz_server_path_missing_in_old_config(tmp_path):
    # configs saved before this key existed must load with the default
    path = tmp_path / "config.json"
    save(load(path), path)
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["dayz_server_path"]
    path.write_text(json.dumps(data), encoding="utf-8")
    assert load(path).dayz_server_path == ""


def test_dayz_server_path_is_editable_scalar(tmp_path):
    cfg = load(tmp_path / "config.json")
    set_scalar(cfg, "dayz_server_path", r"E:\Steam\steamapps\common\DayZServer")
    assert cfg.dayz_server_path == r"E:\Steam\steamapps\common\DayZServer"
