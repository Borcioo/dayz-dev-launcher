"""Textual TUI: mod checkboxes + order, mode/target toggles, live log panes."""
from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button, Checkbox, DirectoryTree, Header, Input, Label, OptionList, RichLog,
    Static, TextArea,
)
from textual.worker import Worker, get_current_worker

from . import config as config_mod
from . import launch as launch_mod
from . import logs as logs_mod
from . import mods as mods_mod

# lines of a pre-existing (previous-session) log to replay before following
TAIL_HISTORY = 200


def _first_existing_dir(start: str) -> str:
    """Closest existing directory at/above `start`, falling back to its drive
    or C:\\ — DirectoryTree needs a real path to root at."""
    p = Path(start) if start else Path("C:/")
    for cand in (p, *p.parents):
        if cand.is_dir():
            return str(cand)
    return str(p.anchor or "C:/")


class BrowseScreen(ModalScreen):
    """Filesystem picker (DirectoryTree). Dismisses with the chosen path string
    or None. `pick` is 'dir' or 'file' (just labelling — both are selectable)."""

    CSS = """
    BrowseScreen { align: center middle; }
    #browsebox {
        width: 80%; max-width: 110; height: 80%;
        border: round $accent; background: $surface; padding: 1 2;
    }
    #browse-nav { height: auto; }
    #browse-nav Input { width: 1fr; }
    #browse-nav Button { width: auto; margin-left: 1; }
    #browse-drives { height: auto; }
    #browse-drives Button { width: auto; margin-right: 1; min-width: 6; }
    #browse-tree { height: 1fr; border: round $primary; }
    #browse-sel { color: $text-muted; height: 1; }
    #browsebtns { height: auto; align-horizontal: right; }
    #browsebtns Button { margin-left: 2; }
    """
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, start: str, pick: str = "dir"):
        super().__init__()
        self.root = _first_existing_dir(start)
        self.pick = pick
        self.selected = None

    @staticmethod
    def _drives() -> list[str]:
        import string
        return [f"{c}:\\" for c in string.ascii_uppercase
                if Path(f"{c}:\\").exists()]

    def compose(self) -> ComposeResult:
        with Vertical(id="browsebox"):
            yield Label(f"Select a {self.pick} — click to pick, then Use")
            with Horizontal(id="browse-nav"):
                yield Button("⬆ Up", id="browse-up")
                yield Input(self.root, id="browse-path")
                yield Button("Go", id="browse-go")
            with Horizontal(id="browse-drives"):
                for d in self._drives():
                    yield Button(d.rstrip("\\"), id=f"drive-{d[0]}")
            yield DirectoryTree(self.root, id="browse-tree")
            yield Label(self.root, id="browse-sel")
            with Horizontal(id="browsebtns"):
                yield Button("Use", variant="success", id="browse-use")
                yield Button("Cancel", id="browse-cancel")

    def _pick(self, path) -> None:
        self.selected = str(path)
        self.query_one("#browse-sel", Label).update(self.selected)

    def _reroot(self, path) -> None:
        p = Path(path)
        if not p.is_dir():
            self.notify(f"not a folder: {path}", severity="error")
            return
        self.root = str(p)
        tree = self.query_one("#browse-tree", DirectoryTree)
        tree.path = self.root
        tree.reload()
        self.query_one("#browse-path", Input).value = self.root

    def on_directory_tree_directory_selected(self, event) -> None:
        self._pick(event.path)

    def on_directory_tree_file_selected(self, event) -> None:
        self._pick(event.path)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "browse-path":
            self._reroot(event.value)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "browse-up":
            self._reroot(Path(self.root).parent)
        elif bid == "browse-go":
            self._reroot(self.query_one("#browse-path", Input).value)
        elif bid and bid.startswith("drive-"):
            self._reroot(f"{bid[len('drive-'):]}:\\")
        elif bid == "browse-use":
            self.dismiss(self.selected)
        else:
            self.dismiss(None)


class ConfigScreen(ModalScreen):
    """Edit install paths, port and mod scan-roots without touching the JSON.
    Mutates the shared cfg in place and dismisses True when saved."""

    CSS = """
    ConfigScreen { align: center middle; }
    #cfgform {
        width: 80%; max-width: 100; height: 80%;
        border: round $accent; background: $surface; padding: 1 2;
    }
    #cfgform Input { margin-bottom: 1; }
    #cfgform .cfgrow { height: auto; }
    #cfgform .cfgrow Input { width: 1fr; }
    #cfgform .cfgrow Button { width: 6; margin-left: 1; }
    #cfg-roots { height: 8; }
    #cfgbtns { height: auto; align-horizontal: right; margin-top: 1; }
    #cfgbtns Button { margin-left: 2; }
    """
    BINDINGS = [("escape", "cancel", "Cancel")]

    DIR_KEYS = {"dayz_path", "dayz_tools_path", "profiles_path",
                "client_profiles_path"}
    # file fields — picker stores just the filename (resolved at launch time)
    FILE_KEYS = {"exe_debug", "exe_normal", "client_exe_debug",
                 "client_exe_normal", "config_name"}

    # (config key, human label) — every editable scalar
    SCALARS = [
        ("dayz_path", "DayZ install dir"),
        ("dayz_tools_path", "DayZ Tools dir"),
        ("profiles_path", "Server profiles dir"),
        ("client_profiles_path", "Client profiles dir"),
        ("exe_debug", "Server exe (debug)"),
        ("exe_normal", "Server exe (normal)"),
        ("client_exe_debug", "Client exe (debug)"),
        ("client_exe_normal", "Client exe (normal)"),
        ("config_name", "Server config (-config)"),
        ("port", "Port"),
        ("mission", "Mission"),
        ("player_name", "Player name"),
    ]

    def __init__(self, cfg: config_mod.Config):
        super().__init__()
        self.cfg = cfg

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="cfgform"):
            yield Label("CONFIG  —  Esc to cancel, Save to apply")
            for key, lbl in self.SCALARS:
                yield Label(lbl)
                inp = Input(value=str(getattr(self.cfg, key)), id=f"cfg-{key}")
                if key in self.DIR_KEYS or key in self.FILE_KEYS or key == "mission":
                    with Horizontal(classes="cfgrow"):
                        yield inp
                        yield Button("📁", id=f"browse-{key}")
                else:
                    yield inp
            yield Label("Mod scan-roots (one folder per line)")
            yield TextArea("\n".join(self.cfg.scan_roots), id="cfg-roots")
            with Horizontal(id="cfgbtns"):
                yield Button("Add folder…", id="roots-add")
                yield Button("Save", variant="success", id="cfg-save")
                yield Button("Cancel", variant="error", id="cfg-cancel")

    def action_cancel(self) -> None:
        self.dismiss(False)

    def _set_input(self, key: str, path) -> None:
        if path:
            self.query_one(f"#cfg-{key}", Input).value = path

    def _set_filename(self, key: str, path) -> None:
        # exe fields store just the filename (they live in the DayZ dir, the
        # spawn cwd). The server config can live anywhere, so keep its path:
        # relative to the DayZ dir when under it, absolute otherwise — a bare
        # filename would otherwise be looked for in the spawn cwd and fail.
        if not path:
            return
        if key == "config_name":
            p = Path(path)
            try:
                val = str(p.relative_to(Path(self.cfg.dayz_path)))
            except ValueError:
                val = str(p)
        else:
            val = Path(path).name
        self.query_one(f"#cfg-{key}", Input).value = val

    def _set_mission(self, path) -> None:
        """Store the mission as DayZ wants it: relative to the DayZ dir with
        forward slashes (./mpmissions/...) when it sits under the install."""
        if not path:
            return
        p = Path(path)
        try:
            val = "./" + p.relative_to(Path(self.cfg.dayz_path)).as_posix()
        except ValueError:
            val = str(p)
        self.query_one("#cfg-mission", Input).value = val

    def _add_root_line(self, path) -> None:
        if not path:
            return
        ta = self.query_one("#cfg-roots", TextArea)
        existing = [ln for ln in ta.text.splitlines() if ln.strip()]
        if path not in existing:
            existing.append(path)
        ta.text = "\n".join(existing)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid and bid.startswith("browse-"):
            key = bid[len("browse-"):]
            if key == "mission":
                start = str(Path(self.cfg.dayz_path) / "mpmissions")
                self.app.push_screen(BrowseScreen(start, "dir"), self._set_mission)
            elif key in self.FILE_KEYS:
                self.app.push_screen(BrowseScreen(self.cfg.dayz_path, "file"),
                                     lambda p, k=key: self._set_filename(k, p))
            else:
                cur = self.query_one(f"#cfg-{key}", Input).value
                self.app.push_screen(BrowseScreen(cur, "dir"),
                                     lambda p, k=key: self._set_input(k, p))
            return
        if bid == "roots-add":
            self.app.push_screen(BrowseScreen("", "dir"), self._add_root_line)
            return
        if bid == "cfg-cancel":
            self.dismiss(False)
            return
        for key, lbl in self.SCALARS:
            value = self.query_one(f"#cfg-{key}", Input).value
            try:
                config_mod.set_scalar(self.cfg, key, value)
            except ValueError:
                self.notify(f"{lbl} must be a number", severity="error")
                return
        roots = self.query_one("#cfg-roots", TextArea).text.splitlines()
        config_mod.set_roots(self.cfg, roots)
        self.dismiss(True)


class PresetScreen(ModalScreen):
    """Pick a preset to Load/Delete, or type a name and Save the current setup.
    Dismisses with (action, name) where action is load|save|delete, or None."""

    CSS = """
    PresetScreen { align: center middle; }
    #presetbox {
        width: 60%; max-width: 80; height: auto; max-height: 80%;
        border: round $accent; background: $surface; padding: 1 2;
    }
    #preset-list { height: auto; max-height: 12; margin-bottom: 1; }
    #preset-name { margin-bottom: 1; }
    #presetbtns { height: auto; align-horizontal: right; }
    #presetbtns Button { margin-left: 2; }
    """
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, names: list[str]):
        super().__init__()
        self.names = names

    def compose(self) -> ComposeResult:
        with Vertical(id="presetbox"):
            yield Label("PRESETS — select to Load/Delete, or type a name to Save")
            yield OptionList(*self.names, id="preset-list")
            yield Input(placeholder="new preset name (for Save)", id="preset-name")
            with Horizontal(id="presetbtns"):
                yield Button("Load", variant="primary", id="p-load")
                yield Button("Save", variant="success", id="p-save")
                yield Button("Delete", variant="error", id="p-del")
                yield Button("Cancel", id="p-cancel")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _selected(self):
        ol = self.query_one("#preset-list", OptionList)
        if ol.highlighted is None:
            return None
        return ol.get_option_at_index(ol.highlighted).prompt

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "p-cancel":
            self.dismiss(None)
            return
        if bid == "p-save":
            name = self.query_one("#preset-name", Input).value.strip() or self._selected()
            if not name:
                self.notify("type a name to save", severity="error")
                return
            self.dismiss(("save", name))
            return
        sel = self._selected()
        if not sel:
            self.notify("select a preset first", severity="error")
            return
        self.dismiss((("load" if bid == "p-load" else "delete"), sel))


class ParamsScreen(ModalScreen):
    """Edit a target's extra launch flags (one per line). Dismisses with the new
    list, or None on cancel."""

    CSS = """
    ParamsScreen { align: center middle; }
    #paramsbox {
        width: 70%; max-width: 90; height: auto;
        border: round $accent; background: $surface; padding: 1 2;
    }
    #params-text { height: 10; margin-bottom: 1; }
    #paramsbtns { height: auto; align-horizontal: right; }
    #paramsbtns Button { margin-left: 2; }
    """
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, label: str, params: list[str]):
        super().__init__()
        self.label_text = label
        self.params = params

    def compose(self) -> ComposeResult:
        with Vertical(id="paramsbox"):
            yield Label(f"{self.label_text} PARAMS — one flag per line "
                        "(core -mod/-port/etc. are added automatically)")
            yield TextArea("\n".join(self.params), id="params-text")
            with Horizontal(id="paramsbtns"):
                yield Button("Save", variant="success", id="params-save")
                yield Button("Cancel", id="params-cancel")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "params-cancel":
            self.dismiss(None)
            return
        lines = [ln.strip() for ln in
                 self.query_one("#params-text", TextArea).text.splitlines()]
        self.dismiss([ln for ln in lines if ln])


class OpenScreen(ModalScreen):
    """Pick a configured folder to open in Explorer. Dismisses with the chosen
    path, or None on cancel."""

    CSS = """
    OpenScreen { align: center middle; }
    #openbox {
        width: 60%; max-width: 80; height: auto;
        border: round $accent; background: $surface; padding: 1 2;
    }
    #open-list { height: auto; max-height: 10; }
    """
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, items: list[tuple[str, str]]):
        super().__init__()
        self.items = items  # (label, path)

    def compose(self) -> ComposeResult:
        with Vertical(id="openbox"):
            yield Label("OPEN FOLDER — Enter to open in Explorer, Esc to cancel")
            yield OptionList(*[f"{lbl}   {path}" for lbl, path in self.items],
                             id="open-list")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(self.items[event.option_index][1])


class DzlApp(App):
    CSS = """
    #main { height: 1fr; }
    #modcol { width: 15%; min-width: 26; }
    #mod-searchrow { height: 3; margin-bottom: 1; }
    #mod-search { width: 1fr; border: round $accent; background: transparent; }
    #mod-search:focus { border: round $accent-lighten-1; }
    #mod-clear {
        width: 5; min-width: 5; height: 3; margin-left: 1;
        border: round $accent; background: transparent;
    }
    #mods { border: round $accent; height: 1fr; overflow-x: auto; }
    #right { width: 1fr; }
    #bottom { height: auto; }
    #preview { border: round $warning; height: auto; max-height: 8; padding: 0 1; }
    #preview-text { color: $text-muted; width: auto; }
    .pane { border: round $primary; height: 1fr; }
    .pane:focus { border: round $accent; }
    .pane.collapsed { height: 3; }  /* title bar only */
    #bar { border: round $secondary; height: auto; padding: 0 1; }
    #controls { height: auto; border: round $secondary; }
    #controls .ctlrow { height: auto; align-vertical: middle; margin-bottom: 1; }
    #controls .ctlrow:last-of-type { margin-bottom: 0; }
    #controls .grp { width: 8; color: $text-muted; text-style: bold; }
    #controls Button {
        min-width: 9; height: 1; border: none; margin: 0 1 0 0;
    }
    #keybar { dock: bottom; height: auto; background: $panel; padding: 0 1; }
    """
    TITLE = "dzl"
    SUB_TITLE = "DayZ dev launcher"
    # grouped, ordered key bar (replaces the flat Footer)
    KEYBAR = (
        "[b $success]SRV[/] s·start x·stop r·restart"
        "   [b $success]CLI[/] ^s·start ^x·stop ^r·restart"
        "   [b $accent]MODS[/] t·side ^↑/^↓·order a·rescan /·search f·enabled =·width ^Home/^End·top/bottom"
        "   [b $primary]LOG[/] z·collapse ^↑/^↓·move w·window"
        "   [b $warning]SET[/] d·mode c·config p·presets o·open · q·quit"
    )
    BINDINGS = [
        # server
        ("s", "start", "server start"),
        ("x", "stop", "server stop"),
        ("r", "restart", "server restart"),
        # client (Ctrl mirrors the server keys)
        ("ctrl+s", "start_client", "client start"),
        ("ctrl+x", "stop_client", "client stop"),
        ("ctrl+r", "restart_client", "client restart"),
        # mods
        ("t", "cycle_side", "side"),
        ("ctrl+up", "move_up", "move up"),
        ("ctrl+down", "move_down", "move down"),
        ("/", "search", "search mods"),
        ("f", "filter_enabled", "enabled only"),
        ("=", "cycle_width", "widen mods"),
        ("ctrl+home", "move_top", "move to top"),
        ("ctrl+end", "move_bottom", "move to bottom"),
        ("z", "toggle_collapse", "collapse pane"),
        ("w", "pop_log", "log in new window"),
        # settings
        ("d", "toggle_mode", "debug/normal"),
        ("a", "rescan", "rescan mods"),
        ("c", "config", "config"),
        ("p", "preset", "presets"),
        ("o", "open", "open folder"),
        ("q", "quit", "quit"),
    ]

    def __init__(self, cfg: config_mod.Config, save_path: Path,
                 config_path: Path, active_preset: str = ""):
        super().__init__()
        self.cfg = cfg
        self.save_path = save_path      # where edits persist (preset or config)
        self.config_path = config_path  # config.json (holds the active pointer)
        self.active_preset = active_preset
        self.mode = cfg.mode
        # scan on open so the list is current (saved loadout + newly-found mods,
        # the new ones disabled). Press 'a' to rescan after changing scan-roots.
        self.mod_list = mods_mod.merge(cfg.mods, mods_mod.discover(cfg.scan_roots))
        self.mod_filter = ""        # substring filter
        self.enabled_only = False   # show only enabled mods
        self.mod_width_idx = cfg.mod_width_idx % 3  # persisted width step

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            with Vertical(id="modcol"):
                with Horizontal(id="mod-searchrow"):
                    yield Input(placeholder="filter mods…", id="mod-search")
                    yield Button("✕", id="mod-clear")
                with VerticalScroll(id="mods"):
                    for i in self._visible_indices():
                        m = self.mod_list[i]
                        yield Checkbox(self._mod_label(i, m), value=m.enabled,
                                       id=f"mod-{i}")
            with Vertical(id="right"):
                yield Static(self._status_text(), id="bar")
                for which in self.cfg.logs_shown:
                    yield RichLog(id=f"log-{which}", classes="pane", markup=False,
                                  highlight=False, wrap=False)
        # full-width bottom strip: live argv preview + the start/stop controls
        with Vertical(id="bottom"):
            with VerticalScroll(id="preview"):
                yield Static(self._preview_text(), id="preview-text")
            with Vertical(id="controls"):
                with Horizontal(classes="ctlrow"):
                    yield Label("SERVER", classes="grp")
                    yield Button("Start", id="srv-start", variant="success")
                    yield Button("Stop", id="srv-stop", variant="error")
                    yield Button("Restart", id="srv-restart")
                    yield Button("Params", id="srv-params")
                with Horizontal(classes="ctlrow"):
                    yield Label("CLIENT", classes="grp")
                    yield Button("Start", id="cli-start", variant="success")
                    yield Button("Stop", id="cli-stop", variant="error")
                    yield Button("Restart", id="cli-restart")
                    yield Button("Params", id="cli-params")
        yield Static(self.KEYBAR, id="keybar")

    def on_mount(self) -> None:
        self.sub_title = f"{self.mode} mode"
        self.query_one("#modcol").styles.width = self._MOD_WIDTHS[self.mod_width_idx]
        self.query_one("#mod-search", Input).border_title = "search mods"
        self.query_one("#mods").border_title = "mods"
        self.query_one("#bar", Static).border_title = "status"
        self._refresh_preview()
        self.set_interval(1.5, self._refresh_status)
        for which in self.cfg.logs_shown:
            pane = self.query_one(f"#log-{which}", RichLog)
            pane.can_focus = True  # so it can be selected for z / move
            pane.border_title = f"{which.upper()}  ·z ·^↑↓"
            self._tail_into(which)
        # don't auto-focus the filter Input (first focusable) — keep focus on
        # the app so single-key shortcuts work until the user clicks the box.
        self.call_after_refresh(self.set_focus, None)

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        # toggling a mod changes the launch argv -> keep the preview live
        self._refresh_preview()

    # ---- helpers ----
    def _status_text(self) -> str:
        procs = launch_mod.read_procs(self.config_path)

        def fmt(t):
            info = procs.get(t)
            return f"UP ({info['source']})" if info else "down"

        return (f"mode: {self.mode}   port: {self.cfg.port}   "
                f"server: {fmt('server')}   client: {fmt('client')}")

    def _refresh_status(self) -> None:
        self.query_one("#bar", Static).update(self._status_text())

    @staticmethod
    def _mod_label(i: int, m: mods_mod.Mod) -> str:
        # leading number = load order; tag marks server-only / client-only mods.
        # NB: avoid [..] — a str label is parsed as Textual markup and would eat
        # the bracketed tag; <..> is safe.
        tag = {"both": "", "server": "  <SRV>", "client": "  <CLI>"}[m.side]
        return f"{i + 1:>2}. {m.name}{tag}" + ("  (MISSING)" if m.missing else "")

    def _sync_checkbox_state(self) -> None:
        """Reflect current checkbox values back into mod_list. No-op before
        mount, when the checkbox widgets don't exist yet."""
        for i, m in enumerate(self.mod_list):
            try:
                m.enabled = self.query_one(f"#mod-{i}", Checkbox).value
            except Exception:
                pass  # not mounted yet; keep the value from merge()

    def _enabled_selection(self) -> list[dict]:
        """Persisted selection = only the enabled mods, in order. Disabled mods
        are rediscovered as disabled next run, so storing them would just leave
        stale '(MISSING)' rows when scan-roots change."""
        self._sync_checkbox_state()
        return [{"path": m.path, "enabled": True, "side": m.side}
                for m in self.mod_list if m.enabled and not m.missing]

    def _preview_text(self) -> str:
        """The exact commands Start/Client would run, from the live selection."""
        cfg = replace(self.cfg, mods=self._enabled_selection())
        srv = (f"{launch_mod.server_exe(cfg, self.mode)} "
               + " ".join(launch_mod.build_args(self.mode, "server", cfg)))
        cli = (f"{launch_mod.client_exe(cfg, self.mode)} "
               + " ".join(launch_mod.build_args(self.mode, "client", cfg)))
        return f"SERVER  {srv}\n\nCLIENT  {cli}"

    def _refresh_preview(self) -> None:
        preview = self.query_one("#preview", VerticalScroll)
        preview.border_title = f"launch params · {self.mode}"
        self.query_one("#preview-text", Static).update(self._preview_text())

    def _sync_mods_from_ui(self) -> None:
        self.cfg.mods = self._enabled_selection()
        self.cfg.mode = self.mode
        config_mod.save(self.cfg, self.save_path)

    def _tail_into(self, which: str) -> None:
        log = self.query_one(f"#log-{which}", RichLog)
        log.write(f"waiting for {which} log…")

        def pump():
            # resolve() returns the newest matching log by mtime. Re-resolve in
            # a loop so a fresh log created by a (re)start supersedes the one we
            # were following — otherwise the pane would stay stuck on the old
            # session's file. The worker's cancellation flag stops every phase
            # so the thread exits cleanly on app quit even while a log is idle.
            worker = get_current_worker()
            first = True  # the log present at startup is a previous session
            while not worker.is_cancelled:
                current = logs_mod.resolve(self.cfg.profiles_path, self.cfg.client_profiles_path).get(which)
                if current is None:
                    time.sleep(0.5)
                    continue
                # previous-session log: replay only the tail for context; a log
                # that appears later is this session's -> show it in full.
                history = TAIL_HISTORY if first else None
                first = False
                self.call_from_thread(log.write, f"--- {current.name} ---")

                def superseded() -> bool:
                    return (
                        worker.is_cancelled
                        or logs_mod.resolve(self.cfg.profiles_path, self.cfg.client_profiles_path).get(which) != current
                    )

                for line in logs_mod.tail_lines(current, should_stop=superseded,
                                                history=history):
                    self.call_from_thread(log.write, line)
                # tail returned: cancelled, or a newer log appeared -> re-resolve

        self.run_worker(pump, thread=True, name=f"tail-{which}")

    _MOD_WIDTHS = ("15%", "35%", "60%")

    def action_cycle_width(self) -> None:
        self.mod_width_idx = (self.mod_width_idx + 1) % len(self._MOD_WIDTHS)
        self.query_one("#modcol").styles.width = self._MOD_WIDTHS[self.mod_width_idx]
        self.cfg.mod_width_idx = self.mod_width_idx
        config_mod.save(self.cfg, self.save_path)

    # ---- actions ----
    def action_start(self) -> None:
        self._sync_mods_from_ui()
        launch_mod.spawn(self.mode, "server", self.cfg,
                         source="tui", config_path=self.config_path)
        self._refresh_status()

    def action_start_client(self) -> None:
        self._sync_mods_from_ui()
        launch_mod.spawn(self.mode, "client", self.cfg,
                         source="tui", config_path=self.config_path)
        self._refresh_status()

    def action_stop(self) -> None:
        launch_mod.stop_target("server", self.cfg, self.config_path)
        self._refresh_status()

    def action_restart(self) -> None:
        self._sync_mods_from_ui()
        launch_mod.restart_server(self.mode, self.cfg,
                                  config_path=self.config_path, source="tui")
        self._refresh_status()

    def action_stop_client(self) -> None:
        launch_mod.stop_target("client", self.cfg, self.config_path)
        self._refresh_status()

    def action_restart_client(self) -> None:
        self._sync_mods_from_ui()
        launch_mod.stop_target("client", self.cfg, self.config_path)
        launch_mod.spawn(self.mode, "client", self.cfg,
                         source="tui", config_path=self.config_path)
        self._refresh_status()

    # control-bar buttons -> the matching action (keyboard still works too)
    _BTN_ACTIONS = {
        "srv-start": "start", "srv-stop": "stop", "srv-restart": "restart",
        "cli-start": "start_client", "cli-stop": "stop_client",
        "cli-restart": "restart_client",
    }

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "mod-clear":
            self._clear_filter()
            return
        if bid in ("srv-params", "cli-params"):
            self._open_params("server" if bid == "srv-params" else "client")
            return
        action = self._BTN_ACTIONS.get(bid)
        if action:
            getattr(self, f"action_{action}")()

    def _open_params(self, target: str) -> None:
        current = (self.cfg.server_params if target == "server"
                   else self.cfg.client_params)
        self.push_screen(
            ParamsScreen(target.upper(), list(current)),
            lambda result: self._apply_params(target, result),
        )

    def _apply_params(self, target: str, result) -> None:
        if result is None:
            return
        if target == "server":
            self.cfg.server_params = result
        else:
            self.cfg.client_params = result
        config_mod.save(self.cfg, self.save_path)
        self._refresh_preview()
        self.notify(f"{target} params updated")

    def action_toggle_mode(self) -> None:
        self.mode = "normal" if self.mode == "debug" else "debug"
        self.sub_title = f"{self.mode} mode"
        self._refresh_status()
        self._refresh_preview()  # mode flips -filePatching etc. in the argv

    def action_move_up(self) -> None:
        self._move_focused(-1)

    def action_move_down(self) -> None:
        self._move_focused(1)

    def _move_focused(self, delta: int) -> None:
        # context-aware: a focused log pane moves panes; otherwise a mod moves
        if self._focused_log_which():
            self._move_pane(delta)
        else:
            self.run_worker(self._move(delta), exclusive=True)

    def action_toggle_collapse(self) -> None:
        which = self._focused_log_which()
        if which:
            self.query_one(f"#log-{which}", RichLog).toggle_class("collapsed")

    def action_pop_log(self) -> None:
        which = self._focused_log_which()
        if not which:
            self.notify("focus a log pane first (Tab/click)", severity="warning")
            return
        path = logs_mod.resolve(self.cfg.profiles_path,
                                self.cfg.client_profiles_path).get(which)
        if path and launch_mod.open_log_window(path):
            self.notify(f"{which} log opened in a new window")
        else:
            self.notify(f"no {which} log file yet", severity="error")

    def _focused_log_which(self):
        w = self.focused
        if isinstance(w, RichLog) and w.id and w.id.startswith("log-"):
            return w.id[len("log-"):]
        return None

    def _move_pane(self, delta: int) -> None:
        """Reorder the focused log pane up/down, persist logs_shown, keep tails."""
        which = self._focused_log_which()
        order = list(self.cfg.logs_shown)
        i = order.index(which)
        j = i + delta
        if not (0 <= j < len(order)):
            return
        order[i], order[j] = order[j], order[i]
        self.cfg.logs_shown = order
        config_mod.save(self.cfg, self.save_path)
        # re-sequence the existing widgets (move_child, so tail workers survive)
        right = self.query_one("#right")
        anchor = self.query_one("#bar", Static)
        for name in order:
            pane = self.query_one(f"#log-{name}", RichLog)
            right.move_child(pane, after=anchor)
            anchor = pane
        self.query_one(f"#log-{which}", RichLog).focus()

    def action_rescan(self) -> None:
        self.run_worker(self._rescan(), exclusive=True)

    def action_search(self) -> None:
        # search box is always visible; '/' just jumps focus into it
        self.query_one("#mod-search", Input).focus()

    def action_filter_enabled(self) -> None:
        self.enabled_only = not self.enabled_only
        self.run_worker(self._rebuild_mod_widgets(), exclusive=True)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "mod-search":
            self.mod_filter = event.value
            self.run_worker(self._rebuild_mod_widgets(), exclusive=True)

    def _clear_filter(self) -> None:
        self.query_one("#mod-search", Input).value = ""
        self.mod_filter = ""
        self.set_focus(None)
        self.run_worker(self._rebuild_mod_widgets(), exclusive=True)

    def on_key(self, event) -> None:
        if event.key == "escape":
            inp = self.query_one("#mod-search", Input)
            if inp.has_focus or self.mod_filter:
                self._clear_filter()
                event.stop()

    def action_cycle_side(self) -> None:
        """Cycle the focused mod's side: both -> server -> client -> both.
        Only one label changes, so update it in place (no full rebuild)."""
        i = self._focused_mod_index()
        if i is None:
            return
        self._sync_checkbox_state()
        m = self.mod_list[i]
        m.side = mods_mod.SIDES[(mods_mod.SIDES.index(m.side) + 1) % len(mods_mod.SIDES)]
        self.query_one(f"#mod-{i}", Checkbox).label = self._mod_label(i, m)
        self._sync_mods_from_ui()
        self._refresh_preview()

    def action_preset(self) -> None:
        self.push_screen(
            PresetScreen(config_mod.list_presets(self.config_path)), self._on_preset
        )

    def _on_preset(self, result) -> None:
        if not result:
            return
        action, name = result
        if action == "save":
            self._sync_mods_from_ui()  # capture live checkbox/side selection
            config_mod.save_preset(self.cfg, name, self.config_path)
            self.notify(f"saved preset '{name}'")
        elif action == "delete":
            config_mod.delete_preset(name, self.config_path)
            if self.active_preset == name:
                config_mod.set_active_preset("", self.config_path)
            self.notify(f"deleted preset '{name}'")
        elif action == "load":
            self.run_worker(self._apply_preset(name), exclusive=True)

    async def _apply_preset(self, name: str) -> None:
        try:
            cfg = config_mod.load_preset(name, self.config_path)
        except FileNotFoundError:
            self.notify(f"no preset '{name}'", severity="error")
            return
        # make it the active source: flip the pointer in config.json and route
        # future saves to the preset file. Tail workers read self.cfg.* live, so
        # they pick up new profile paths on their next poll.
        config_mod.set_active_preset(name, self.config_path)
        self.active_preset = name
        self.save_path = config_mod.preset_file(name, self.config_path)
        self.cfg = cfg
        self.mode = cfg.mode
        await self._rebuild_scanned()
        self.sub_title = f"{self.mode} mode"
        self.notify(f"loaded preset '{name}'")

    def action_open(self) -> None:
        items = [
            ("DayZ install", self.cfg.dayz_path),
            ("Server profiles", self.cfg.profiles_path),
            ("Client profiles", self.cfg.client_profiles_path),
            ("Config / presets", str(Path(self.config_path).parent)),
        ]
        # plus the mod scan-root folders (the dirs that contain the mods)
        items += [(f"scan-root · {r}", r) for r in self.cfg.scan_roots]
        self.push_screen(OpenScreen(items), self._on_open)

    def _on_open(self, path) -> None:
        if not path:
            return
        if launch_mod.open_folder(path):
            self.notify(f"opened {path}")
        else:
            self.notify(f"folder not found: {path}", severity="error")

    def action_config(self) -> None:
        self.push_screen(ConfigScreen(self.cfg), self._on_config_closed)

    def _on_config_closed(self, saved: bool) -> None:
        if not saved:
            return
        config_mod.save(self.cfg, self.save_path)
        # scan-roots/paths may have changed -> rescan so the list is current
        self.run_worker(self._rescan(), exclusive=True)

    # ---- reorder / rebuild ----
    def _visible_indices(self):
        """Indices into self.mod_list that pass the current filter."""
        out = []
        for i, m in enumerate(self.mod_list):
            if self.enabled_only and not m.enabled:
                continue
            if self.mod_filter and self.mod_filter.lower() not in m.name.lower():
                continue
            out.append(i)
        return out

    def _focused_mod_index(self):
        w = self.focused
        if isinstance(w, Checkbox) and w.id and w.id.startswith("mod-"):
            return int(w.id.split("-", 1)[1])
        return None

    async def _rebuild_mod_widgets(self) -> None:
        await self.query("#mods Checkbox").remove()
        box = self.query_one("#mods", VerticalScroll)
        await box.mount_all([
            Checkbox(self._mod_label(i, self.mod_list[i]),
                     value=self.mod_list[i].enabled, id=f"mod-{i}")
            for i in self._visible_indices()
        ])

    async def _move(self, delta: int) -> None:
        """Move the focused mod up/down in the load order, persist, re-focus."""
        i = self._focused_mod_index()
        if i is None:
            return
        j = i + delta
        if not (0 <= j < len(self.mod_list)):
            return
        self._sync_checkbox_state()  # don't lose toggles while reordering
        self.mod_list[i], self.mod_list[j] = self.mod_list[j], self.mod_list[i]
        await self._rebuild_mod_widgets()
        self.query_one(f"#mod-{j}", Checkbox).focus()
        self._sync_mods_from_ui()  # persist the new order (enabled selection)
        self._refresh_preview()

    async def _move_to(self, where: str) -> None:
        i = self._focused_mod_index()
        if i is None:
            return
        self._sync_checkbox_state()
        m = self.mod_list.pop(i)
        j = 0 if where == "top" else len(self.mod_list)
        self.mod_list.insert(j, m)
        await self._rebuild_mod_widgets()
        self.query_one(f"#mod-{j}", Checkbox).focus()
        self._sync_mods_from_ui()
        self._refresh_preview()

    def action_move_top(self) -> None:
        self.run_worker(self._move_to("top"), exclusive=True)

    def action_move_bottom(self) -> None:
        self.run_worker(self._move_to("bottom"), exclusive=True)

    async def _show_mod_list(self, mod_list) -> None:
        self.mod_list = mod_list
        await self._rebuild_mod_widgets()
        self._refresh_status()
        self._refresh_preview()

    async def _rebuild_scanned(self) -> None:
        """Rebuild the list = current cfg.mods merged with a fresh scan."""
        discovered = mods_mod.discover(self.cfg.scan_roots)
        await self._show_mod_list(mods_mod.merge(self.cfg.mods, discovered))

    async def _rescan(self) -> None:
        """On-demand scan: keep current UI enables, then re-scan the roots."""
        # an enabled mod the scan no longer finds is kept and flagged MISSING.
        self.cfg.mods = self._enabled_selection()
        await self._rebuild_scanned()
        self.notify(f"rescanned {len(self.cfg.scan_roots)} root(s)")


def run_tui(cfg: config_mod.Config, save_path: Path, config_path: Path,
            active_preset: str = "") -> None:
    DzlApp(cfg, save_path, config_path, active_preset).run()
