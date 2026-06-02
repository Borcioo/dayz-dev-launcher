"""Hybrid entrypoint: no subcommand -> TUI; subcommands -> run & exit."""
from __future__ import annotations

from pathlib import Path

import click

from . import config as config_mod
from . import launch as launch_mod
from . import logs as logs_mod


@click.group(invoke_without_command=True)
@click.option("--config", "config_path", default=None, help="Path to config.json")
@click.pass_context
def cli(ctx, config_path):
    config_path = Path(config_path) if config_path else config_mod.DEFAULT_PATH
    # working config comes from the active preset if one is set, else config.json;
    # edits are saved back to that same source (save_path).
    cfg, save_path, active = config_mod.resolve_active(config_path)
    ctx.obj = {
        "config_path": config_path, "save_path": save_path,
        "cfg": cfg, "active": active,
    }
    if ctx.invoked_subcommand is None:
        from .tui import run_tui
        run_tui(cfg, save_path, config_path, active)


@cli.command(help="List the current ordered mod selection.")
@click.pass_context
def mods(ctx):
    for m in ctx.obj["cfg"].mods:
        mark = "[x]" if m.get("enabled") else "[ ]"
        side = m.get("side", "both")
        tag = "" if side == "both" else f"  ({side})"
        click.echo(f"{mark} {m['path']}{tag}")


@cli.command(help="Start the server (and optionally client).")
@click.option("--debug/--normal", "debug", default=True)
@click.option("--client", is_flag=True, help="Also start the client.")
@click.option("--dry-run", is_flag=True, help="Print argv, don't spawn.")
@click.pass_context
def start(ctx, debug, client, dry_run):
    cfg = ctx.obj["cfg"]
    config_path = ctx.obj["config_path"]
    mode = "debug" if debug else "normal"
    targets = ["server"] + (["client"] if client else [])
    for target in targets:
        args = launch_mod.build_args(mode, target, cfg)
        if dry_run:
            exe = (launch_mod.server_exe if target == "server"
                   else launch_mod.client_exe)(cfg, mode)
            click.echo(f"{exe} " + " ".join(args))
        else:
            launch_mod.spawn(mode, target, cfg, source="cli", config_path=config_path)
            click.echo(f"started {target} ({mode})")


@cli.command(help="Stop server (and client with --client).")
@click.option("--debug/--normal", "debug", default=True)
@click.option("--client", is_flag=True)
@click.pass_context
def stop(ctx, debug, client):
    cfg = ctx.obj["cfg"]
    config_path = ctx.obj["config_path"]
    launch_mod.stop_target("server", cfg, config_path)
    click.echo("stopped server")
    if client:
        launch_mod.stop_target("client", cfg, config_path)
        click.echo("stopped client")


@cli.command(help="Restart the server.")
@click.option("--debug/--normal", "debug", default=True)
@click.pass_context
def restart(ctx, debug):
    cfg = ctx.obj["cfg"]
    launch_mod.restart_server("debug" if debug else "normal", cfg,
                              config_path=ctx.obj["config_path"], source="cli")
    click.echo("restarted server")


@cli.command(name="logs", help="Tail a log to stdout: script|rpt|adm|client.")
@click.argument("which", type=click.Choice(["script", "rpt", "adm", "client"]))
@click.option("--lines", "lines", type=int, default=None,
              help="Print the last N lines and exit (no follow).")
@click.pass_context
def logs_cmd(ctx, which, lines):
    cfg = ctx.obj["cfg"]
    path = logs_mod.resolve(cfg.profiles_path, cfg.client_profiles_path).get(which)
    if not path:
        where = cfg.client_profiles_path if which == "client" else cfg.profiles_path
        click.echo(f"no {which} log found in {where}")
        return
    if lines is not None:
        for line in logs_mod.last_lines(path, lines):
            click.echo(line)
        return
    try:
        for line in logs_mod.tail_lines(path):
            click.echo(line)
    except KeyboardInterrupt:
        pass


@cli.command(help="Show running state, paths, mods and log files.")
@click.option("--json", "as_json", is_flag=True, help="Machine-readable output.")
@click.pass_context
def status(ctx, as_json):
    import json as _json
    from pathlib import Path as _P
    cfg = ctx.obj["cfg"]
    config_path = ctx.obj["config_path"]
    procs = launch_mod.read_procs(config_path)

    def target_state(t):
        info = procs.get(t)
        if not info:
            return {"state": "down", "source": None, "mode": None, "pid": None}
        return {"state": "up", "source": info.get("source"),
                "mode": info.get("mode"), "pid": info.get("pid")}

    logs = {k: (str(v) if v else None) for k, v in
            logs_mod.resolve(cfg.profiles_path, cfg.client_profiles_path).items()}
    data = {
        "mode": cfg.mode,
        "port": cfg.port,
        "active_preset": ctx.obj["active"] or None,
        "server": target_state("server"),
        "client": target_state("client"),
        "paths": {
            "dayz_path": cfg.dayz_path,
            "profiles_path": cfg.profiles_path,
            "client_profiles_path": cfg.client_profiles_path,
            "config_dir": str(_P(config_path).parent),
            "presets_dir": str(config_mod.presets_dir(config_path)),
        },
        "mods": [{"path": m["path"], "side": m.get("side", "both")}
                 for m in cfg.mods if m.get("enabled")],
        "logs": logs,
    }
    if as_json:
        click.echo(_json.dumps(data, indent=2))
        return
    s, c = data["server"], data["client"]
    click.echo(f"mode {data['mode']} | port {data['port']}"
               + (f" | preset {data['active_preset']}" if data['active_preset'] else ""))
    click.echo(f"server: {s['state']}" + (f" ({s['source']}, pid {s['pid']})" if s['state']=='up' else ""))
    click.echo(f"client: {c['state']}" + (f" ({c['source']}, pid {c['pid']})" if c['state']=='up' else ""))
    click.echo("paths:")
    for k, v in data["paths"].items():
        click.echo(f"  {k}: {v}")
    click.echo(f"mods ({len(data['mods'])} enabled):")
    for m in data["mods"]:
        tag = "" if m["side"] == "both" else f"  ({m['side']})"
        click.echo(f"  {m['path']}{tag}")
    click.echo("logs:")
    for k, v in data["logs"].items():
        click.echo(f"  {k}: {v or '(none)'}")


@cli.group(name="config", invoke_without_command=True,
           help="View/edit launcher config (paths, scan-roots, port).")
@click.pass_context
def config_cmd(ctx):
    if ctx.invoked_subcommand is None:
        import dataclasses
        import json as _json
        click.echo(_json.dumps(dataclasses.asdict(ctx.obj["cfg"]), indent=2))


@config_cmd.command(name="path", help="Print the config.json location.")
@click.pass_context
def config_path(ctx):
    click.echo(str(ctx.obj["config_path"]))


@config_cmd.command(name="add-root", help="Add a folder to scan for mods.")
@click.argument("folder")
@click.pass_context
def config_add_root(ctx, folder):
    cfg = ctx.obj["cfg"]
    config_mod.add_root(cfg, folder)
    config_mod.save(cfg, ctx.obj["save_path"])
    for r in cfg.scan_roots:
        click.echo(r)


@config_cmd.command(name="rm-root", help="Remove a mod scan-root folder.")
@click.argument("folder")
@click.pass_context
def config_rm_root(ctx, folder):
    cfg = ctx.obj["cfg"]
    config_mod.remove_root(cfg, folder)
    config_mod.save(cfg, ctx.obj["save_path"])
    for r in cfg.scan_roots:
        click.echo(r)


@config_cmd.command(name="set", help="Set a scalar key, e.g. dzl config set port 2402.")
@click.argument("key")
@click.argument("value")
@click.pass_context
def config_set(ctx, key, value):
    cfg = ctx.obj["cfg"]
    try:
        config_mod.set_scalar(cfg, key, value)
    except KeyError:
        raise click.ClickException(
            f"unknown/non-editable key '{key}'. editable: "
            + ", ".join(config_mod.EDITABLE_SCALARS)
        )
    except ValueError:
        raise click.ClickException(f"'{key}' must be a number")
    config_mod.save(cfg, ctx.obj["save_path"])
    click.echo(f"{key} = {getattr(cfg, key)}")


@cli.group(name="preset", invoke_without_command=True,
           help="Save/load named config presets (per-project setups).")
@click.pass_context
def preset_cmd(ctx):
    if ctx.invoked_subcommand is None:
        active = ctx.obj["active"]
        for n in config_mod.list_presets(ctx.obj["config_path"]):
            click.echo(f"* {n}" if n == active else f"  {n}")
        if not config_mod.list_presets(ctx.obj["config_path"]):
            click.echo("(no presets)")


@preset_cmd.command(name="save", help="Save the current config as a preset.")
@click.argument("name")
@click.pass_context
def preset_save(ctx, name):
    target = config_mod.save_preset(ctx.obj["cfg"], name, ctx.obj["config_path"])
    click.echo(f"saved preset -> {target}")


@preset_cmd.command(name="load",
                    help="Make a preset active (loaded on startup and for edits).")
@click.argument("name")
@click.pass_context
def preset_load(ctx, name):
    config_path = ctx.obj["config_path"]
    if name not in config_mod.list_presets(config_path):
        raise click.ClickException(
            f"no preset '{name}'. have: "
            + (", ".join(config_mod.list_presets(config_path)) or "(none)")
        )
    config_mod.set_active_preset(name, config_path)  # just flip the pointer
    click.echo(f"active preset -> '{name}'")


@preset_cmd.command(name="rm", help="Delete a preset.")
@click.argument("name")
@click.pass_context
def preset_rm(ctx, name):
    config_path = ctx.obj["config_path"]
    if config_mod.delete_preset(name, config_path):
        if ctx.obj["active"] == name:
            config_mod.set_active_preset("", config_path)  # clear dangling pointer
        click.echo(f"deleted preset '{name}'")
    else:
        raise click.ClickException(f"no preset '{name}'")


def main():
    cli()
