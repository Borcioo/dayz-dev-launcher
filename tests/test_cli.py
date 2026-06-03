from click.testing import CliRunner
from launcher.cli import cli
from launcher.config import save, load, resolve_active


def _seed(tmp_path):
    cfg = load(tmp_path / "config.json")
    cfg.mods = [{"path": "P:\\@CF", "enabled": True},
                {"path": "P:\\@COT", "enabled": False}]
    save(cfg, tmp_path / "config.json")
    return tmp_path / "config.json"


def test_mods_lists_selection(tmp_path):
    path = _seed(tmp_path)
    res = CliRunner().invoke(cli, ["--config", str(path), "mods"])
    assert res.exit_code == 0
    assert "@CF" in res.output
    assert "[x]" in res.output  # enabled marker
    assert "[ ]" in res.output  # disabled marker


def test_start_dry_run_prints_argv(tmp_path):
    path = _seed(tmp_path)
    res = CliRunner().invoke(
        cli, ["--config", str(path), "start", "--debug", "--dry-run"]
    )
    assert res.exit_code == 0
    assert "-server" in res.output
    assert "-filePatching" in res.output
    assert "-mod=P:\\@CF" in res.output


def test_config_show_outputs_json(tmp_path):
    path = _seed(tmp_path)
    res = CliRunner().invoke(cli, ["--config", str(path), "config"])
    assert res.exit_code == 0
    assert '"scan_roots"' in res.output
    assert '"port"' in res.output


def test_config_add_and_rm_root_persist(tmp_path):
    # edits flow to the active profile (a 'default' is seeded on first run), so
    # check the effective config via resolve_active, not config.json directly.
    path = _seed(tmp_path)
    r = CliRunner()
    add = r.invoke(cli, ["--config", str(path), "config", "add-root", "D:\\dev\\mods"])
    assert add.exit_code == 0
    assert "D:\\dev\\mods" in resolve_active(path)[0].scan_roots  # persisted
    rm = r.invoke(cli, ["--config", str(path), "config", "rm-root", "D:\\dev\\mods"])
    assert rm.exit_code == 0
    assert "D:\\dev\\mods" not in resolve_active(path)[0].scan_roots


def test_config_set_port_and_reject_unknown(tmp_path):
    path = _seed(tmp_path)
    r = CliRunner()
    ok = r.invoke(cli, ["--config", str(path), "config", "set", "port", "2402"])
    assert ok.exit_code == 0
    assert resolve_active(path)[0].port == 2402  # saved into the active profile
    bad = r.invoke(cli, ["--config", str(path), "config", "set", "bogus", "x"])
    assert bad.exit_code != 0  # ClickException


def test_preset_save_activates(tmp_path):
    # saving a preset makes it active (so the setup actually sticks next session).
    path = _seed(tmp_path)
    r = CliRunner()
    s = r.invoke(cli, ["--config", str(path), "preset", "save", "alpha"])
    assert s.exit_code == 0
    assert load(path).active_preset == "alpha"        # pointer flipped on save
    assert "* alpha" in r.invoke(cli, ["--config", str(path), "preset"]).output


def test_preset_load_switches_active_profile(tmp_path):
    path = _seed(tmp_path)
    r = CliRunner()
    # alpha @2600 (save activates it), beta @2700 (edit lands in the active beta)
    r.invoke(cli, ["--config", str(path), "config", "set", "port", "2600"])
    r.invoke(cli, ["--config", str(path), "preset", "save", "alpha"])
    r.invoke(cli, ["--config", str(path), "preset", "save", "beta"])
    r.invoke(cli, ["--config", str(path), "config", "set", "port", "2700"])
    # switching the pointer changes the effective config back to alpha's snapshot
    ld = r.invoke(cli, ["--config", str(path), "preset", "load", "alpha"])
    assert ld.exit_code == 0
    assert load(path).active_preset == "alpha"
    cfg, _, name = resolve_active(path)
    assert name == "alpha" and cfg.port == 2600
    assert resolve_active(path)  # beta kept 2700
    r.invoke(cli, ["--config", str(path), "preset", "load", "beta"])
    assert resolve_active(path)[0].port == 2700
    # load unknown -> error
    bad = r.invoke(cli, ["--config", str(path), "preset", "load", "ghost"])
    assert bad.exit_code != 0


def test_config_edits_go_to_active_preset(tmp_path):
    path = _seed(tmp_path)
    r = CliRunner()
    r.invoke(cli, ["--config", str(path), "preset", "save", "alpha"])
    r.invoke(cli, ["--config", str(path), "preset", "load", "alpha"])
    # with alpha active, a config edit must persist into the PRESET, not base
    r.invoke(cli, ["--config", str(path), "config", "set", "port", "2750"])
    cfg, _, name = resolve_active(path)
    assert name == "alpha" and cfg.port == 2750


import json as _json


def test_status_json_shape(tmp_path):
    path = _seed(tmp_path)
    res = CliRunner().invoke(cli, ["--config", str(path), "status", "--json"])
    assert res.exit_code == 0
    data = _json.loads(res.output)
    assert data["server"]["state"] == "down"
    assert "dayz_path" in data["paths"]
    assert "mods" in data and "logs" in data
    assert data["port"] == load(path).port


def test_logs_lines_oneshot(tmp_path):
    path = _seed(tmp_path)
    cfg = load(path)
    prof = tmp_path / "prof"; prof.mkdir()
    (prof / "script_x.log").write_text("a\nb\nc\n", encoding="utf-8")
    cfg.profiles_path = str(prof); save(cfg, path)
    res = CliRunner().invoke(cli, ["--config", str(path), "logs", "script", "--lines", "2"])
    assert res.exit_code == 0
    assert res.output.strip().splitlines() == ["b", "c"]
