from launcher.mods import Mod, discover, merge


def _mk_mod(root, *names):
    """Create dirs that look like real mods (each has an addons/ subdir)."""
    for n in names:
        (root / n / "addons").mkdir(parents=True)


def _mk_plain(root, *names):
    """Create dirs WITHOUT addons/ (containers / non-mods)."""
    for n in names:
        (root / n).mkdir(parents=True)


def test_discover_finds_packed_mods_skips_containers(tmp_path):
    _mk_mod(tmp_path, "@CF", "@COT")              # have addons/ -> mods
    _mk_plain(tmp_path, "notamod", "@Dependencies")  # no markers -> skipped
    (tmp_path / "@PackedMods").mkdir()
    (tmp_path / "@PackedMods" / "mod.cpp").write_text("")  # mod.cpp only -> skipped
    found = discover([str(tmp_path)])
    names = sorted(p.rsplit("\\", 1)[-1].rsplit("/", 1)[-1] for p in found)
    assert names == ["@CF", "@COT"]


def test_discover_finds_source_mod_by_config_and_scripts(tmp_path):
    # dev mod loaded via filePatching: no @, no addons/, has config.cpp + scripts/
    (tmp_path / "DayZLootFW" / "scripts").mkdir(parents=True)
    (tmp_path / "DayZLootFW" / "config.cpp").write_text("")
    found = discover([str(tmp_path)])
    assert [p.rsplit("\\", 1)[-1].rsplit("/", 1)[-1] for p in found] == ["DayZLootFW"]


def test_discover_skips_vanilla_dump_config_without_scripts(tmp_path):
    # unpacked vanilla dir: config.cpp but NO scripts/ subdir -> not a mod
    (tmp_path / "scripts").mkdir()  # named 'scripts' but it IS the dump root
    (tmp_path / "scripts" / "config.cpp").write_text("")
    (tmp_path / "scripts" / "3_game").mkdir()  # children, not a scripts/ subdir
    found = discover([str(tmp_path)])
    assert found == []


def test_discover_skips_missing_roots(tmp_path):
    found = discover([str(tmp_path / "nope")])
    assert found == []


def test_merge_preserves_saved_order_and_enabled():
    saved = [
        {"path": "P:\\@CF", "enabled": True},
        {"path": "P:\\@COT", "enabled": False},
    ]
    discovered = ["P:\\@COT", "P:\\@CF", "P:\\@New"]
    result = merge(saved, discovered)
    assert [m.path for m in result] == ["P:\\@CF", "P:\\@COT", "P:\\@New"]
    assert [m.enabled for m in result] == [True, False, False]
    assert [m.missing for m in result] == [False, False, False]


def test_merge_flags_missing_saved_mod():
    saved = [{"path": "P:\\@Gone", "enabled": True}]
    result = merge(saved, [])
    assert result[0].missing is True
    assert result[0].enabled is True


def test_merge_reads_side_defaulting_to_both():
    saved = [
        {"path": "P:\\@A", "enabled": True, "side": "server"},
        {"path": "P:\\@B", "enabled": True},          # no side -> both
        {"path": "P:\\@C", "enabled": True, "side": "bogus"},  # invalid -> both
    ]
    result = merge(saved, ["P:\\@A", "P:\\@B", "P:\\@C"])
    assert [m.side for m in result] == ["server", "both", "both"]
