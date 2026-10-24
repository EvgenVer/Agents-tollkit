#!/usr/bin/env python3
"""Connect the studio plugin of this checkout to Antigravity (the app, the IDE and agy).

Usage: antigravity.py install | uninstall [--config DIR]

install    Register plugins/studio in ~/.gemini/config/plugins.json, keeping other entries.
           Restart Antigravity afterwards. `git pull` in this checkout updates the plugin.
uninstall  Remove that registration.

--config   The Antigravity settings folder (default: ~/.gemini/config).
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

PLUGINS = Path(__file__).resolve().parents[1] / "plugins"
ENTRY = {"path": PLUGINS.as_posix(), "include_only": ["studio"]}


def same_folder(entry):
    try:
        return Path(str(entry.get("path", ""))).expanduser().resolve() == PLUGINS
    except (OSError, AttributeError):
        return False


def load(path):
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or not isinstance(data.get("entries", []), list):
        raise ValueError("expected an object with an entries list")
    return data


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
    target = config / "plugins.json"
    try:
        data = load(target)
    except ValueError as error:
        print(f"{target} is not valid ({error}); fix or move it, then run again.",
              file=sys.stderr)
        return 1
    entries = [entry for entry in data.get("entries", []) if not same_folder(entry)]

    if args.action == "install":
        data["entries"] = entries + [ENTRY]
        config.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"registered {PLUGINS / 'studio'} in {target}")
        for line in warnings(config):
            print(f"warning: {line}")
        print("Restart the Antigravity app and IDE to load it.")
        return 0

    if not target.exists() or len(entries) == len(data.get("entries", [])):
        print("studio was not registered")
        return 0
    data["entries"] = entries
    if data == {"entries": []}:
        target.unlink()
        print(f"removed {target}")
    else:
        target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"removed studio from {target}")
    print("Restart the Antigravity app and IDE to unload it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
