from launcher.config import load
from launcher import launch as launch_mod
from launcher.launch import build_args, mod_paths_string, open_folder, open_log_window


def _cfg(tmp_path):
    cfg = load(tmp_path / "config.json")
    cfg.mods = [
        {"path": "P:\\@CF", "enabled": True},
        {"path": "P:\\@COT", "enabled": False},
        {"path": "P:\\DayZLootFW", "enabled": True},
    ]
    return cfg


def test_mod_paths_string_only_enabled_no_trailing_semicolon(tmp_path):
    s = mod_paths_string(_cfg(tmp_path))
    assert s == "P:\\@CF;P:\\DayZLootFW"
    assert not s.endswith(";")


def test_server_debug_includes_filepatching(tmp_path):
    args = build_args("debug", "server", _cfg(tmp_path))
    assert "-server" in args
    assert "-filePatching" in args
    assert "-mod=P:\\@CF;P:\\DayZLootFW" in args
    assert f"-port=2302" in args
    assert "-profiles=profiles" in args


def _cfg_sides(tmp_path):
    cfg = load(tmp_path / "config.json")
    cfg.mods = [
        {"path": "P:\\@CF", "enabled": True, "side": "both"},
        {"path": "P:\\@Admin", "enabled": True, "side": "server"},
        {"path": "P:\\@UI", "enabled": True, "side": "client"},
    ]
    return cfg


def test_server_splits_mod_and_servermod(tmp_path):
    args = build_args("debug", "server", _cfg_sides(tmp_path))
    assert "-mod=P:\\@CF" in args                 # only 'both' mods in -mod
    assert "-serverMod=P:\\@Admin" in args        # server-only -> -serverMod
    assert "@UI" not in " ".join(args)            # client-only never on server


def test_client_mod_includes_client_only_no_servermod(tmp_path):
    args = build_args("debug", "client", _cfg_sides(tmp_path))
    mod = next(a for a in args if a.startswith("-mod="))
    assert "@CF" in mod and "@UI" in mod          # both + client-only
    assert "@Admin" not in mod                    # server-only not on client
    assert not any(a.startswith("-serverMod") for a in args)


def test_client_uses_separate_profiles_dir(tmp_path):
    # client must not share the server's profiles dir, or their logs collide
    server = build_args("debug", "server", _cfg(tmp_path))
    client = build_args("debug", "client", _cfg(tmp_path))
    assert "-profiles=profiles" in server
    assert "-profiles=profiles_client" in client
    assert "-profiles=profiles" not in client


def test_build_args_appends_editable_params(tmp_path):
    cfg = _cfg(tmp_path)
    cfg.server_params = ["-customFlag", "-freezecheck"]
    cfg.client_params = ["-window", "-myClientFlag"]
    srv = build_args("debug", "server", cfg)
    cli = build_args("debug", "client", cfg)
    assert srv[-2:] == ["-customFlag", "-freezecheck"]  # appended after core
    assert "-server" in srv
    assert cli[-2:] == ["-window", "-myClientFlag"]
    assert "-connect=127.0.0.1" in cli


def test_client_includes_connect_and_name(tmp_path):
    args = build_args("debug", "client", _cfg(tmp_path))
    assert "-connect=127.0.0.1" in args
    assert "-name=DevMacie" in args
    assert "-window" in args
    assert "-server" not in args


def test_open_folder_missing_returns_false(tmp_path):
    assert open_folder(tmp_path / "nope") is False


def test_open_folder_existing_calls_startfile(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(launch_mod.os, "startfile",
                        lambda p: seen.setdefault("p", p), raising=False)
    assert open_folder(tmp_path) is True
    assert seen["p"] == str(tmp_path)


def test_open_log_window_missing_returns_false(tmp_path):
    assert open_log_window(tmp_path / "nope.log") is False


def test_open_log_window_spawns_for_existing(tmp_path, monkeypatch):
    f = tmp_path / "script_x.log"
    f.write_text("hi")
    calls = {}
    monkeypatch.setattr(launch_mod.subprocess, "Popen",
                        lambda *a, **k: calls.setdefault("a", (a, k)))
    assert open_log_window(f) is True
    cmd = calls["a"][0][0]
    assert "Get-Content" in cmd and str(f) in cmd


from launcher.launch import (
    procs_path, read_procs, write_proc, clear_proc, is_pid_alive,
)


def test_procs_path_next_to_config(tmp_path):
    cfg_path = tmp_path / "config.json"
    assert procs_path(cfg_path) == tmp_path / ".dzl-procs.json"


def test_write_read_clear_proc(tmp_path):
    cfg_path = tmp_path / "config.json"
    import os
    from launcher.launch import pid_image
    real_exe = pid_image(os.getpid()) or "python.exe"
    write_proc(cfg_path, "server", os.getpid(), "debug", "tui", real_exe)
    procs = read_procs(cfg_path)
    assert procs["server"]["pid"] == os.getpid()
    assert procs["server"]["source"] == "tui"
    clear_proc(cfg_path, "server")
    assert "server" not in read_procs(cfg_path)


def test_read_procs_reconciles_dead_pid(tmp_path, monkeypatch):
    cfg_path = tmp_path / "config.json"
    write_proc(cfg_path, "server", 999999, "debug", "cli", "DayZDiag_x64.exe")
    monkeypatch.setattr(launch_mod, "pid_image", lambda pid: None)
    assert read_procs(cfg_path) == {}


def test_read_procs_drops_recycled_pid_wrong_exe(tmp_path, monkeypatch):
    cfg_path = tmp_path / "config.json"
    write_proc(cfg_path, "server", 4242, "debug", "cli", "DayZDiag_x64.exe")
    monkeypatch.setattr(launch_mod, "pid_image", lambda pid: "notepad.exe")
    assert read_procs(cfg_path) == {}


def test_read_procs_missing_or_corrupt_is_empty(tmp_path):
    cfg_path = tmp_path / "config.json"
    assert read_procs(cfg_path) == {}
    procs_path(cfg_path).write_text("{ broken", encoding="utf-8")
    assert read_procs(cfg_path) == {}


def test_spawn_records_statefile(tmp_path, monkeypatch):
    cfg = load(tmp_path / "config.json")
    cfg.mods = [{"path": "P:\\@CF", "enabled": True, "side": "both"}]

    class FakePopen:
        def __init__(self, *a, **k): self.pid = 31337

    monkeypatch.setattr(launch_mod.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(launch_mod, "pid_image", lambda pid: "DayZDiag_x64.exe")
    launch_mod.spawn("debug", "server", cfg, source="cli",
                     config_path=tmp_path / "config.json")
    procs = launch_mod.read_procs(tmp_path / "config.json")
    assert procs["server"]["pid"] == 31337
    assert procs["server"]["source"] == "cli"
    assert procs["server"]["exe"] == "DayZDiag_x64.exe"


def test_stop_target_kills_recorded_pid(tmp_path, monkeypatch):
    cfg = load(tmp_path / "config.json")
    launch_mod.write_proc(tmp_path / "config.json", "server", 4242,
                          "debug", "cli", "DayZDiag_x64.exe")
    killed = {}
    monkeypatch.setattr(launch_mod.subprocess, "run",
                        lambda *a, **k: killed.setdefault("args", a[0]))
    launch_mod.stop_target("server", cfg, tmp_path / "config.json")
    assert "/PID" in killed["args"] and "4242" in killed["args"]
    assert "server" not in _json_load(tmp_path / "config.json")


def _json_load(cfg_path):
    import json
    p = cfg_path.parent / ".dzl-procs.json"
    return json.loads(p.read_text()) if p.exists() else {}


def test_server_flag_only_in_debug(tmp_path):
    cfg = _cfg(tmp_path)
    assert "-server" in build_args("debug", "server", cfg)
    assert "-server" not in build_args("normal", "server", cfg)


def test_profiles_relative_when_under_dayz(tmp_path):
    cfg = load(tmp_path / "config.json")
    cfg.dayz_path = r"E:\DayZ"
    cfg.profiles_path = r"E:\DayZ\profiles"
    args = build_args("debug", "server", cfg)
    assert "-profiles=profiles" in args


def test_profiles_absolute_when_outside_dayz(tmp_path):
    cfg = load(tmp_path / "config.json")
    cfg.dayz_path = r"E:\DayZ"
    cfg.profiles_path = r"D:\custom\prof"
    args = build_args("debug", "server", cfg)
    assert r"-profiles=D:\custom\prof" in args


def test_client_uses_configurable_connect_ip(tmp_path):
    cfg = _cfg(tmp_path)
    cfg.connect_ip = "10.0.0.5"
    assert "-connect=10.0.0.5" in build_args("debug", "client", cfg)
