# Changelog

## Unreleased

### Profiles always persist
- A **`default` profile is seeded and activated on first run**, so your mods,
  paths and params are saved from the start — no need to manually create a
  profile first for changes to stick.
- **Saving a preset now also activates it** (in the TUI and via `dzl preset
  save`), so the setup you just saved is the one loaded next session.
- `dzl status` and the TUI status bar show the active profile, and both read it
  without you having to load it first.
- The active profile is remembered between sessions (unchanged behaviour, now
  reliably reached because there is always an active profile).

## 0.2.1

### Fixed
- BattlEye failed to init in normal mode with custom cfg/profiles paths:
  new `dayz_server_path` option points at the dedicated DayZ Server install;
  the server now launches from that directory (exe, cwd, `-profiles=`
  relativization). Empty (default) keeps the old single-install behavior;
  debug mode is unaffected. (user report)

## 0.2.0 — human + AI collaboration, mods UX, fully editable launch

### Human + tool work on the same launcher
- The TUI and the `dzl` CLI now share one live source of truth (a small on-disk
  state file). Start the server from a terminal or a script and the open TUI
  reflects it within a second or two; stop it from the TUI and the CLI sees it.
- The status bar shows who started what — server/client running state plus
  whether it came from the TUI or the CLI.
- Stop and restart target the exact process that was started, so in debug mode
  (where the server and client are the same executable) one no longer takes the
  other down.
- New `dzl status` command (human text or machine-readable JSON) gives the whole
  setup — running state, paths, enabled mods, newest log files — in one call.
- New one-shot log read (`dzl logs <type> --lines N`) prints the tail and exits,
  instead of following forever.
- A Claude Code skill (with an installer) teaches an AI assistant the CLI and the
  collaboration model, so it can run the server and read logs for you while you
  watch in the TUI.

### Mods list — built for large load orders
- Search/filter the mod list, with an always-visible filter box, a clear button,
  and an "enabled only" toggle.
- Move a mod straight to the top or bottom of the load order.
- Widen the mod column (cycles through a few widths, remembered between
  sessions) with horizontal scrolling so long names are readable.

### Launch command — nothing hardcoded
- Launch flags are now kept per mode, so dev (debug) and production (normal) each
  have their own set, with a Reset-to-defaults in the editor.
- The client connect IP is editable.
- The executables, server config and profile folders accept custom paths, not
  just names inside the DayZ install — so pieces living in other folders work.

### Fixes & polish
- The `-server` flag is only used for the diagnostic build; the dedicated server
  no longer rejects launching with certain mods.
- Custom paths for the server config and profile folders now work when they live
  outside the DayZ install.
- The launch-params preview wraps and scrolls instead of cutting off long
  commands.
- The mod filter box no longer steals focus on startup (single-key shortcuts
  work again) and matches the rest of the UI.

## 0.1.0 — initial public release
- Terminal launcher for a local DayZ modding setup: checkbox mod selection with
  load order and per-mod side (server / client / both), start/stop/restart of the
  server and client, live log panes, editable launch params, a config screen with
  a filesystem picker, and named per-project presets.
- Hybrid CLI: no arguments opens the TUI; with flags it runs and exits.
- One-line web installer, `setup.bat`, and an uninstaller.
