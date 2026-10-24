#!/usr/bin/env python3
"""Connect the studio plugin of this checkout to Antigravity (the app, the IDE and agy).

Usage: antigravity.py install | uninstall [--config DIR]

install    Link ~/.gemini/config/plugins/studio to plugins/studio of this checkout (a
           junction on Windows, a symlink elsewhere). The IDE finds plugins only in that
           folder. Restart Antigravity afterwards; `git pull` here updates the plugin.
uninstall  Remove that link. The checkout itself is left alone.

--config   The Antigravity settings folder (default: ~/.gemini/config).
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1] / "plugins" / "studio"


def link_target(path):
    """Where a junction or symlink points, or None for anything else."""
    try:
        target = os.readlink(path)
    except (OSError, ValueError):
        return None
    return Path(target.removeprefix("\\\\?\\")).resolve()


def make_link(link):
    link.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":  # a junction needs no administrator rights, unlike a symlink
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(PLUGIN)],
                                capture_output=True, text=True)
        if result.returncode != 0:
            raise OSError((result.stderr or result.stdout).strip())
    else:
        link.symlink_to(PLUGIN, target_is_directory=True)


def remove_link(link):
    """Remove only the link itself: deleting the folder tree would empty the checkout."""
    if os.name == "nt":
        os.rmdir(link)
    else:
        link.unlink()


def warnings(config):
    """Problems that would stop the hooks from running, as lines to print."""
    found = []
    python = shutil.which("python")
    if not python:
        found.append("`python` is not on PATH, and the hooks run `python`. Install Python 3 "
                     "and tick \"Add python.exe to PATH\", or the hooks do nothing.")
    elif "WindowsApps" in python:
        found.append(f"`python` resolves to the Microsoft Store stub ({python}). Install "
                     "Python 3 from python.org, or the hooks do nothing.")
    if not shutil.which("git"):
        found.append("`git` is not on PATH; the studio skills need it.")
    try:
        enabled = json.loads((config / "config.json").read_text(encoding="utf-8-sig"))
        if enabled.get("plugins", {}).get("studio", {}).get("enabled") is False:
            found.append("studio is switched off in Antigravity: turn it on in the plugin "
                         "settings or run `agy plugin enable studio`.")
    except (OSError, ValueError, AttributeError):
        pass
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description="Connect studio to Antigravity.")
    parser.add_argument("action", choices=["install", "uninstall"])
    parser.add_argument("--config", default=str(Path.home() / ".gemini" / "config"),
                        help="Antigravity settings folder (default: ~/.gemini/config)")
    args = parser.parse_args(argv)

    config = Path(args.config).expanduser()
    link = config / "plugins" / "studio"
    target = link_target(link)
    if os.path.lexists(link) and target is None:
        print(f"{link} exists and is not a link; move it away, then run again.",
              file=sys.stderr)
        return 1

    if args.action == "install":
        if target != PLUGIN:
            if target is not None:
                remove_link(link)
            make_link(link)
        print(f"linked {link} -> {PLUGIN}")
        for line in warnings(config):
            print(f"warning: {line}")
        print("Quit the Antigravity app and IDE completely and start them again.")
        return 0

    if target is None:
        print("studio was not installed")
        return 0
    if target != PLUGIN:
        print(f"{link} points to another copy ({target}); left as it is.", file=sys.stderr)
        return 1
    remove_link(link)
    print(f"removed {link}")
    print("Quit the Antigravity app and IDE completely and start them again.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
