#!/usr/bin/env python3
"""Connect the studio plugin of this checkout to Antigravity (the app, the IDE and agy).

Usage: antigravity.py install | uninstall [--config DIR]

install    Copy plugins/studio of this checkout to ~/.gemini/config/plugins/studio, the
           one folder where the Antigravity IDE looks for plugins. It does not follow
           links, so this is a copy: after `git pull`, run install again. Restart
           Antigravity afterwards.
uninstall  Remove that copy. A folder this script did not create is left alone.

--config   The Antigravity settings folder (default: ~/.gemini/config).
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1] / "plugins" / "studio"
MARKER = ".installed-by-studio"  # names the checkout the copy came from


def link_target(path):
    """Where a junction or symlink points, or None for anything else."""
    try:
        return Path(os.readlink(path).removeprefix("\\\\?\\"))
    except (OSError, ValueError):
        return None


def remove(copy):
    """Remove an earlier copy, or a link from an earlier version, never the checkout."""
    if link_target(copy) is None:
        shutil.rmtree(copy)
    elif os.name == "nt":
        os.rmdir(copy)  # removes the junction, not the folder it points to
    else:
        copy.unlink()


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

    copy = Path(args.config).expanduser() / "plugins" / "studio"
    ours = link_target(copy) is not None or (copy / MARKER).is_file()
    if os.path.lexists(copy) and not ours:
        print(f"{copy} was not created by this script; move it away, then run again.",
              file=sys.stderr)
        return 1

    if args.action == "install":
        if os.path.lexists(copy):
            remove(copy)
        shutil.copytree(PLUGIN, copy, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (copy / MARKER).write_text(f"{PLUGIN}\n", encoding="utf-8")
        print(f"copied {PLUGIN} to {copy}")
        for line in warnings(copy.parent.parent):
            print(f"warning: {line}")
        print("Quit the Antigravity app and IDE completely and start them again.")
        return 0

    if not os.path.lexists(copy):
        print("studio was not installed")
        return 0
    remove(copy)
    print(f"removed {copy}")
    print("Quit the Antigravity app and IDE completely and start them again.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
