"""Mod discovery and ordering. List order IS the load order."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


SIDES = ("both", "server", "client")


@dataclass
class Mod:
    path: str
    name: str
    enabled: bool
    missing: bool
    side: str = "both"  # both | server (-serverMod) | client (client -mod only)


def _is_mod(child: Path) -> bool:
    """A loadable DayZ mod, regardless of @-prefix:

    - packed mods carry an ``addons/`` folder (built .pbo content);
    - source mods loaded via filePatching carry a root ``config.cpp`` *and* a
      ``scripts/`` tree (the modded Enforce scripts).

    Keying on content (not the name) skips ``@``-named *container* dirs
    (``@Dependencies`` has neither marker; ``@PackedMods`` only ``mod.cpp``) and
    unpacked vanilla dumps that happen to carry a ``config.cpp`` but no
    ``scripts/`` (e.g. a depbo'd ``P:\\scripts`` or ``P:\\bin``), while still
    finding plain-named dev mods like a ``DayZLootFW`` junction.
    """
    if (child / "addons").is_dir():
        return True
    return (child / "config.cpp").is_file() and (child / "scripts").is_dir()


def discover(scan_roots: list[str]) -> list[str]:
    """Return absolute paths of every immediate sub-dir that looks like a mod."""
    found: list[str] = []
    for root in scan_roots:
        rootp = Path(root)
        if not rootp.is_dir():
            continue
        for child in sorted(rootp.iterdir()):
            if child.is_dir() and _is_mod(child):
                found.append(str(child))
    return found


def _name(path: str) -> str:
    return path.replace("/", "\\").rstrip("\\").rsplit("\\", 1)[-1]


def merge(saved: list[dict], discovered: list[str]) -> list[Mod]:
    """Saved order/enabled wins; new mods appended (disabled); missing flagged."""
    disc = set(discovered)
    saved_paths = {m["path"] for m in saved}
    result: list[Mod] = []
    for m in saved:
        side = m.get("side", "both")
        result.append(
            Mod(
                path=m["path"],
                name=_name(m["path"]),
                enabled=bool(m.get("enabled", False)),
                missing=m["path"] not in disc,
                side=side if side in SIDES else "both",
            )
        )
    for p in discovered:
        if p not in saved_paths:
            result.append(Mod(path=p, name=_name(p), enabled=False, missing=False))
    return result
