# dzl — DayZ dev launcher

A fast terminal launcher for a **local DayZ modding setup**. Pick mods with
checkboxes, set load order and per-mod side (server / client / both), start &
stop the server and client, and watch the logs live — all from one TUI, instead
of hand-editing `.bat` files and `-mod=` strings.

It's a single Python/[Textual](https://textual.textualize.io/) app. No install,
no admin, no background service — just a venv and a `.bat` shim.

> Windows-only (it drives `DayZDiag_x64.exe` / `DayZServer_x64.exe` and uses
> Explorer / PowerShell for a few conveniences).

---

## Why

Vanilla DayZ dev means juggling `serverDZ.cfg`, a long `-mod=` list (order
matters, quoting bites), separate client/server `-profiles`, and tailing log
files by hand. `dzl` turns all of that into a checklist + buttons and keeps the
exact launch command visible before you hit Start.

## What it does

- **Auto-discovers mods** from your scan-roots (a folder is a mod if it has an
  `addons/` dir, or a `config.cpp` + `scripts/` — so packed mods *and* unpacked
  filePatching dev mods are found; container/junk folders are skipped).
- **Checkbox selection + load order** (`Ctrl+↑/↓`) — the list order is the
  `-mod=` order.
- **Per-mod side**: `both` (→ both `-mod=`), `server` (→ `-serverMod=`),
  `client` (→ client `-mod=` only).
- **Start / Stop / Restart** the server and client independently (tracked by
  PID, so stopping one leaves the other up).
- **Live log panes** (script / RPT / ADM / client) that follow the newest file
  and switch to a fresh log when you restart. Collapse / reorder / pop a log
  out into its own window.
- **Editable launch params** per target (the `-filePatching`, `-window`, … flags
  are config, not hardcoded).
- **Config screen** with a filesystem picker for every path, and **named
  presets** to switch between projects.
- **Hybrid CLI**: no args → TUI; with flags → run and exit (scriptable).

---

## Requirements

- **Windows 10/11**
- **Python 3.11+** on `PATH` (`python --version`)
- A **DayZ install** (Steam) and, for debug/hot-reload, **DayZ Tools**
  (provides `DayZDiag_x64.exe`). Normal mode uses `DayZServer_x64.exe`.
- Your mods on disk (e.g. a `P:\` work drive with `@CF`, `@COT`, your mod, …).

`dzl` does **not** download or build mods — it launches what you already have.
For packing PBOs use DayZ Tools / your existing build step.

## Install

**Easy way:** download the repo (green **Code → Download ZIP**, then extract;
or `git clone`), then **double-click `setup.bat`**. It checks Python, creates
the virtual environment and installs everything. When it finishes, double-click
`dzl.bat` to start.

**Manual way:**

```powershell
git clone https://github.com/Borcioo/dayz-dev-launcher.git
cd dayz-dev-launcher
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Either way the `dzl.bat` shim uses `.venv` automatically. (You still need
Python 3.11+ installed — see [Requirements](#requirements).)

## Run

```powershell
dzl.bat                       # opens the full TUI
```

First run creates `config.json` with sensible defaults. Open the **config
screen** (key `c`) to point it at your DayZ install, profiles, port and
scan-roots — every path field has a 📁 browse button, so you don't type paths.

Non-interactive (scriptable) usage:

```powershell
dzl.bat mods                  # print the current selection
dzl.bat start --debug         # start server (DayZDiag, filePatching)
dzl.bat start --debug --client
dzl.bat start --normal        # DayZServer (needs packed PBOs)
dzl.bat stop --client
dzl.bat restart
dzl.bat logs script           # tail a log to stdout (Ctrl+C to stop)
dzl.bat config                # print the whole config as JSON
dzl.bat config set port 2402
dzl.bat config add-root D:\my\mods
dzl.bat preset save chernarus-hc
dzl.bat preset load chernarus-hc
```

## TUI layout

- **Left** — the mod list (checkbox = enabled, number = load order, `<SRV>` /
  `<CLI>` = side).
- **Right** — status bar + live log panes.
- **Bottom** — the exact SERVER and CLIENT launch commands (updates live), then
  the Start / Stop / Restart / Params controls for each.

## Keys

```
server   s start · x stop · r restart
client   Ctrl+S start · Ctrl+X stop · Ctrl+R restart   (Ctrl mirrors server)
mods     t cycle side · Ctrl+↑/↓ reorder · a rescan
logs     (focus a pane with Tab/click) z collapse · Ctrl+↑/↓ move · w pop out
other    d debug/normal · c config · p presets · o open a folder · q quit
```

The control rows at the bottom mirror these as buttons, plus **Params** to edit
each target's launch flags.

## Config & presets

- `config.json` (gitignored) holds your paths, port, mission, mod selection,
  log layout and launch params. Edit it in the `c` screen, via `dzl config …`,
  or by hand.
- **Presets** (`presets/<name>.json`, gitignored) are full config snapshots —
  one per project/map. Loading one makes it the active config (the launcher
  remembers the last one and loads it on startup). Manage them with `p` in the
  TUI or `dzl preset save|load|rm|list`.

## How the launch command is built

| Part | Source |
|------|--------|
| `-mod=` / `-serverMod=` | the mod checkboxes + per-mod side |
| `-profiles=` | server / client profiles dirs (separate, so logs don't collide) |
| `-config=`, `-port=`, `-mission=`, `-name=` | config fields |
| `-server`, `-connect=127.0.0.1` | fixed (server marker / local connect) |
| everything else (`-filePatching`, `-window`, …) | editable **Params** per target |

The mode toggle (`debug`/`normal`) only selects the exe.

## FAQ

**Does this work on Linux/Mac?**
No — it launches Windows DayZ executables and uses a few Windows-only bits
(Explorer, PowerShell, `tasklist`/`taskkill`).

**Do I need DayZ Tools?**
For **debug** mode (hot-reload via filePatching) yes — that's `DayZDiag_x64.exe`.
**Normal** mode uses the regular `DayZServer_x64.exe` and packed PBOs.

**The mod list shows folders I don't want (vanilla DLC, etc.).**
Those came from a scan-root pointing at your DayZ install. Remove that root in
the `c` config screen (or `dzl config rm-root "<path>"`). Defaults scan only mod
homes, not the install.

**My dev mod (no `@` prefix) isn't found.**
It's detected if it has `addons/` **or** `config.cpp` + a `scripts/` folder. Make
sure its parent is in your scan-roots.

**Server won't start in `normal` mode.**
Normal mode uses `DayZServer_x64.exe` and won't filePatch — your mods must be
packed PBOs, and you should drop `-filePatching` / `-scriptDebug` from the
server/client **Params** (those need a diag build).

**`dzl.bat` says the venv is missing.**
Run the two setup commands under [Install](#install). The venv lives in `.venv`
and is gitignored (per-machine).

**Logs pane is empty.**
It shows `waiting for … log` until the server/client writes one. On open it
replays only the last ~200 lines of the previous session; a fresh run is shown
in full.

**TUI doesn't fill my terminal / looks small.**
Resize your terminal window/pane — Textual fills whatever size the terminal
reports.

## Tests

```powershell
.venv\Scripts\python.exe -m pytest tests -v
```

## License

[GNU GPLv3](LICENSE) — free to use, study, modify and share. Derivatives and
distributed copies must remain under the GPL and ship their source.
