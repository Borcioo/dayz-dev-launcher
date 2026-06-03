---
name: dzl-launcher
description: >-
  Drive a local DayZ dev server and client through the `dzl` CLI to test a mod.
  Use this WHENEVER you're working on a DayZ mod and need to (re)start the server
  or client, check whether it's running, or read its logs — even if the user
  doesn't say "dzl" by name. Triggers: "test my mod", "start/restart the server",
  "is the server up", "check the script log / RPT for errors", "why did the
  server crash", "load my mods and run it", or any DayZ Enforce Script / config
  iteration where you'd otherwise hunt for log files or launch the game by hand.
  `dzl` and the user's TUI share live state, so the user sees what you do and can
  stop it — prefer driving the server through `dzl` over ad-hoc taskkill/launch.
---

# dzl — DayZ dev launcher (CLI control)

`dzl` is a terminal launcher for a local DayZ modding setup (the user installs it
from https://github.com/Borcioo/dayz-dev-launcher). It manages the local **server**
and **client**, knows where everything lives (mods, profiles, logs, config), and
exposes a CLI so an assistant can drive it. The user usually has the **TUI** open
too — both the TUI and your CLI calls read/write the same on-disk state, so you
collaborate instead of stepping on each other.

## Why prefer dzl over launching by hand

- It builds the exact launch command from the user's config (mods + load order +
  per-mod side, profiles, port, mission, exe, params). You don't have to know any
  of that — ask `dzl` instead.
- Server and client are tracked by PID in a shared statefile. When you start the
  server, the user's open TUI shows `server: UP (cli)` within ~1.5s and its logs
  stream. When the user clicks Stop, your next `dzl status` shows `down`. One
  source of truth.
- So: don't `taskkill DayZDiag` or assemble `-mod=...` yourself. Use the commands
  below. The user stays in control (they can always Stop from the TUI).

## Running dzl from a shell (read this first)

`dzl` is a Windows `.bat`. A normal terminal (PowerShell/cmd) finds it on PATH,
but some shells — notably the **Git Bash** that Claude Code's Bash tool uses —
won't run a bare `.bat`, so `dzl status` there fails with `command not found`.
Invoke it through cmd instead:

```
cmd /c "dzl status --json"
cmd /c "dzl start --debug"
```

In Git Bash specifically, use a double slash so the flag isn't path-mangled:
`cmd //c "dzl status --json"`. If plain `dzl ...` works in your shell, just use
that. Last resort (default install location): `cmd //c "%LOCALAPPDATA%\dzl\dzl.bat status"`.

The command examples below are written as `dzl <args>` for readability — wrap
them in `cmd //c "..."` when your shell can't run the bare `.bat`.

## First thing to run: get your bearings

Before doing anything, grab the full picture in one call:

```
dzl status --json
```

Returns JSON with: `server`/`client` state (`up`/`down` + `source` + `pid`),
`mode` (debug/normal), `port`, `active_preset`, every important `paths`
(`dayz_path`, `profiles_path`, `client_profiles_path`, `config_dir`,
`presets_dir`), the enabled `mods` (path + side, in load order), and the newest
`logs` file per type (`script`/`rpt`/`adm`/`client`). Parse this instead of
searching the filesystem — it's the canonical context for the user's setup.

`dzl status` (no `--json`) prints the same as readable text.

## Run / stop / restart

`debug` mode = `DayZDiag_x64.exe` with filePatching (hot-reload, the normal dev
loop). `normal` mode = the dedicated `DayZServer_x64.exe` (needs packed PBOs).

```
dzl start --debug            # start the server (dev). Add --client to also launch the client.
dzl start --debug --client
dzl start --normal           # production server build
dzl stop                     # stop the server (add --client to also stop the client)
dzl restart                  # stop + start the server
dzl start --debug --dry-run  # print the exact argv WITHOUT launching (good for sanity-checking)
```

`stop`/`restart` kill by the recorded PID, so they target exactly the process
that was started (in debug the server and client are the same exe, so PID
matters). Starting marks the process `source: cli` so the user can tell it was
you.

## Read logs (one-shot — don't tail forever)

```
dzl logs script --lines 200   # last N lines of the script log, then exit
dzl logs rpt --lines 100      # engine/RPT (crashes, missing classes, unbinarized configs)
dzl logs adm --lines 50       # admin log (connects, kills)
dzl logs client --lines 100   # client-side script log
```

ALWAYS pass `--lines N` for one-shot output. Plain `dzl logs <which>` *follows*
the file (like `tail -f`) and will block — that's for a human in a terminal, not
for you. The newest log file is resolved automatically (and re-resolved after a
restart), so you don't need a path.

What to look for: `script` for your `Print()`/`PrintFormat()` output and Enforce
Script errors (look for `Error`, `Can't compile`, `Unknown command`); `rpt` for
engine-level failures (`Cannot open object`, missing class, `binarize`).

## The dev-test loop

A typical "I changed my mod, test it" cycle:

1. `dzl status --json` — confirm config (enabled mods, mode) and whether it's already running.
2. `dzl restart` (or `dzl start --debug` if down) — (re)launch with the current mods. filePatching means script changes hot-reload, but a config/PBO change needs a restart.
3. Wait a few seconds for boot, then `dzl logs script --lines 150` — look for your mod loading and any errors.
4. If you need the engine side, `dzl logs rpt --lines 100`.
5. Report findings to the user. Leave the server running unless they ask to stop, or `dzl stop` when done.

The user may also have the TUI open and watch all this live — that's expected and good.

## Config & presets (read freely; write carefully)

You can inspect and tweak config without opening the TUI:

```
dzl config                       # whole config as JSON
dzl config set port 2402         # set a scalar (paths, port, player_name, connect_ip, exe names, config_name)
dzl config add-root D:\my\mods   # add a folder to scan for mods
dzl config rm-root  D:\my\mods
dzl mods                         # list the enabled mod selection (path + side)
dzl preset                       # list presets (per-project setups)
dzl preset load chernarus-hc     # make a preset active (loads on next start; also what the TUI uses)
dzl preset save dev-snapshot     # snapshot the current config as a preset
```

Editing config: prefer small, explicit changes the user asked for. The TUI does
**not** hot-reload config you change from the CLI — if the user has it open,
mention they may need to reopen it (or press `a` to rescan mods) to see your
edits. Two people editing config at once = last-write-wins, so coordinate.

## Guardrails

- Don't fabricate the launch command or kill DayZ processes directly — go through
  `dzl` so the shared state and the user's TUI stay correct.
- `start` actually launches the game server (real process, real resources). Do it
  when the user is testing, not speculatively. Use `--dry-run` if you only want
  to see the argv.
- Windows-only. If `dzl` isn't on PATH, it's at the user's install dir
  (`%LOCALAPPDATA%\dzl\dzl.bat` by default) — or they haven't installed it.
- The user can always Stop from the TUI; respect that they're in control.
