"""Entry point: ``python -m copilot_log_viewer [LOG_DIR]``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .app import create_app
from .parser import discover_sessions as copilot_discover
from .claude_parser import discover_sessions as claude_discover


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="copilot-log-viewer",
        description="Browse AI agent session logs (GitHub Copilot and Claude Code) in a local web UI.",
    )
    parser.add_argument(
        "log_dir",
        nargs="?",
        default=None,
        help="Directory containing Copilot session log folders (default: ~/.copilot/session-state/)",
    )
    parser.add_argument(
        "--copilot-dir",
        default=None,
        help="Directory containing Copilot session log folders (overrides positional arg)",
    )
    parser.add_argument(
        "--claude-dir",
        default=None,
        help="Directory containing Claude Code session logs (default: ~/.claude/projects/)",
    )
    parser.add_argument(
        "-p", "--port",
        type=int,
        default=5000,
        help="Port to listen on (default: 5000)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Run in Flask debug mode (do NOT use in production)",
    )
    parser.add_argument(
        "-V", "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    args = parser.parse_args(argv)

    # Resolve Copilot directory
    copilot_dir = args.copilot_dir or args.log_dir
    if copilot_dir is None:
        default = Path.home() / ".copilot" / "session-state"
        copilot_dir = str(default) if default.is_dir() else "."
    copilot_path = Path(copilot_dir).resolve()

    # Resolve Claude directory
    claude_dir = args.claude_dir
    if claude_dir is None:
        claude_dir = str(Path.home() / ".claude" / "projects")
    claude_path = Path(claude_dir).resolve()

    copilot_sessions = copilot_discover(copilot_path) if copilot_path.is_dir() else []
    claude_sessions = claude_discover(claude_path) if claude_path.is_dir() else []

    print(f"AI Session Log Viewer v{__version__}")
    print()
    print(f"Copilot: {copilot_path} ({len(copilot_sessions)} sessions)")
    for s in copilot_sessions[:5]:
        print(f"  - {s['summary']} ({s['id'][:8]}...)")
    if len(copilot_sessions) > 5:
        print(f"  ... and {len(copilot_sessions) - 5} more")
    print()
    print(f"Claude:  {claude_path} ({len(claude_sessions)} sessions)")
    for s in claude_sessions[:5]:
        print(f"  - {s['summary']} ({s['id'][:8]}...)")
    if len(claude_sessions) > 5:
        print(f"  ... and {len(claude_sessions) - 5} more")
    print()
    print(f"Open http://{args.host}:{args.port} in your browser")
    print()

    app = create_app(copilot_path, claude_path)
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
