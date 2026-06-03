# dzl — DayZ dev launcher

[![CI](https://github.com/Borcioo/dayz-dev-launcher/actions/workflows/ci.yml/badge.svg)](https://github.com/Borcioo/dayz-dev-launcher/actions/workflows/ci.yml)
[![CodeQL](https://github.com/Borcioo/dayz-dev-launcher/actions/workflows/codeql.yml/badge.svg)](https://github.com/Borcioo/dayz-dev-launcher/actions/workflows/codeql.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Platform](https://img.shields.io/badge/platform-Windows-blue)
![License](https://img.shields.io/badge/license-GPLv3-blue)

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

## Is it safe to run?

It's **100% readable source** — Python plus a couple of `.bat`/`.ps1` scripts,
no binaries, nothing compiled or obfuscated. You can read every line on GitHub.

- The install one-liner just downloads and runs [`install.ps1`](install.ps1) —
  open it first if you like, or use the manual `git clone` route instead.
- Every push runs the **CI** (tests) and **CodeQL** (security scan) workflows —
  see the badges above.
- It only touches: your `config.json`/`presets/` (local), your user `PATH`
  (the `dzl` command), and it launches the DayZ executables you point it at. It
  doesn't phone home or download anything except its Python dependencies from
  PyPI during setup.

## Requirements

- **Windows 10/11**
- **Python 3.11+** on `PATH` (`python --version`)
- A **DayZ install** (Steam) and, for debug/hot-reload, **DayZ Tools**
  (provides `DayZDiag_x64.exe`). Normal mode uses `DayZServer_x64.exe`.
- Your mods on disk (e.g. a `P:\` work drive with `@CF`, `@COT`, your mod, …).

`dzl` does **not** download or build mods — it launches what you already have.
For packing PBOs use DayZ Tools / your existing build step.

## Install

**One-liner (recommended).** Paste this into PowerShell — it checks Python
(offering a winget install), downloads dzl to `%LOCALAPPDATA%\dzl`, sets up the
venv, and adds `dzl` to your PATH:

```powershell
powershell -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/Borcioo/dayz-dev-launcher/main/install.ps1 | iex"
```

Then open a new terminal and run `dzl`. (Re-run the same line anytime to
update — it won't add duplicate PATH entries; if it finds an old dzl on your
PATH it offers to replace it.)

Custom install folder — set `DZL_DIR` first:

```powershell
$env:DZL_DIR='D:\tools\dzl'; powershell -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/Borcioo/dayz-dev-launcher/main/install.ps1 | iex"
```

**Download + double-click:** grab the repo (green **Code → Download ZIP**, then extract;
or `git clone`), then **double-click `setup.bat`**. It checks Python (and, if
it's missing, *offers* to install it via `winget` — your choice, or it points
you to python.org), creates the virtual environment, installs everything, and
adds the folder to your user PATH. Then **open a new terminal and just run
`dzl`** — or double-click `dzl.bat`. (Keep the folder where it is; PATH points
at it.)

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

After `setup.bat`, from any new terminal:

```powershell
dzl                           # opens the full TUI
```

(or double-click `dzl.bat` in the folder; `dzl.bat` also works if you didn't
add it to PATH)

First run creates `config.json` with sensible defaults. Open the **config
screen** (key `c`) to point it at your DayZ install, profiles, port and
scan-roots — every path field has a 📁 browse button, so you don't type paths.

Non-interactive (scriptable) usage:

```powershell
dzl mods                      # print the current selection
dzl start --debug             # start server (DayZDiag, filePatching)
dzl start --debug --client
dzl start --normal            # DayZServer (needs packed PBOs)
dzl stop --client
dzl restart
dzl logs script               # tail a log to stdout (Ctrl+C to stop)
dzl logs script --lines 100   # print the last N lines and exit (no follow)
dzl status                    # running state + paths + mods + logs
dzl status --json             # ...machine-readable (for tools/agents)
dzl config                    # print the whole config as JSON
dzl config set port 2402
dzl config add-root D:\my\mods
dzl preset save chernarus-hc
dzl preset load chernarus-hc
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
mods     t cycle side · Ctrl+↑/↓ reorder · Ctrl+Home/End to top/bottom
         a rescan · / search · f enabled-only · = widen column
logs     (focus a pane with Tab/click) z collapse · Ctrl+↑/↓ move · w pop out
other    d debug/normal · c config · p presets · o open a folder · q quit
```

The control rows at the bottom mirror these as buttons, plus **Params** to edit
each target's launch flags.

## Human + tool, same launcher

The CLI and the TUI share one source of truth (a `.dzl-procs.json` statefile next
to your config), so you can drive the launcher from a terminal/script while the
TUI is open and both stay in sync. The status bar shows who started what —
`server: UP (cli)` vs `(tui)` — and Stop works on a server started from either
side (it kills by PID). `dzl status --json` + `dzl logs <which> --lines N` give a
script or an AI assistant the full picture (paths, mods, running state, log
files) and a one-shot log read, without it needing to hunt for anything.

**Claude Code skill:** `skill/` ships a skill that teaches an assistant the
`dzl` CLI and the collaboration model, so it can start/restart the server and
read logs for you while you watch in the TUI. Install it once with
`powershell -ExecutionPolicy Bypass -File skill\install.ps1` and start a new
Claude Code session.

## Config & presets

- `config.json` (gitignored) holds your paths, port, mission, mod selection,
  log layout and launch params. Edit it in the `c` screen, via `dzl config …`,
  or by hand.
- **Presets / profiles** (`presets/<name>.json`, gitignored) are full config
  snapshots — one per project/map. There's always an **active profile**: a
  `default` is seeded on first run, so your edits persist immediately without
  any manual save. **Saving a preset activates it**, and loading one switches the
  active profile; the launcher remembers it and loads it on startup. The active
  profile is shown in the status bar and in `dzl status`. Manage them with `p` in
  the TUI or `dzl preset save|load|rm|list`.

## How the launch command is built

| Part | Source |
|------|--------|
| `-mod=` / `-serverMod=` | the mod checkboxes + per-mod side |
| `-profiles=` | server / client profiles dirs (separate, so logs don't collide) |
| `-config=`, `-port=`, `-mission=`, `-name=`, `-connect=` | config fields (paths, port, player name, connect IP — all editable) |
| everything else (`-filePatching`, `-window`, …) | editable **Params**, kept per target **and per mode** |

`-server` is the only fixed flag, and only in **debug** (the diagnostic build
runs as a server with it; the dedicated `DayZServer_x64.exe` must not get it).
The mode toggle (`debug`/`normal`) selects the exe **and** which set of Params
applies — so dev and production keep separate flags. The **Params** editor edits
the current mode's set and has a **Reset** to restore that mode's defaults.

Paths to the executables, the server config and the profile folders can be
absolute (point at files in another folder), not just names inside the DayZ dir.

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
Normal mode uses `DayZServer_x64.exe`, which is the dedicated server — it needs
packed PBOs and no diag-only flags. Params are per-mode, so the **normal** set
already leaves out `-filePatching` / `-scriptDebug` by default; if you added them
yourself, remove them (open **Params** while in normal mode).

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

## Uninstall

From your install folder (or `%LOCALAPPDATA%\dzl`):

```powershell
powershell -ExecutionPolicy Bypass -File uninstall.ps1
```

or one line:

```powershell
powershell -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/Borcioo/dayz-dev-launcher/main/uninstall.ps1 | iex"
```

It asks before removing anything, offers to **keep (back up) your config and
presets**, removes the `dzl` PATH entry and the folder, and leaves Python
untouched.

## Tests

```powershell
.venv\Scripts\python.exe -m pytest tests -v
```

## License

[GNU GPLv3](LICENSE) — free to use, study, modify and share. Derivatives and
distributed copies must remain under the GPL and ship their source.
