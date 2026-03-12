"""Flask application for the AI Session Log Viewer."""

from __future__ import annotations

import json
import re
from pathlib import Path

import markdown
from flask import Flask, render_template, jsonify, abort, request, Response
from markupsafe import Markup

from .parser import (
    discover_sessions as copilot_discover,
    parse_events as copilot_parse_events,
    parse_snapshots,
    parse_workspace,
    build_conversation as copilot_build_conversation,
    compute_stats as copilot_compute_stats,
    ts_display,
    ts_relative,
    duration_between,
)
from . import claude_parser

# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

# Session IDs are UUIDs — enforce that to prevent path traversal.
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# Backup hash filenames: hex-timestamp
_BACKUP_HASH_RE = re.compile(r"^[0-9a-f]{16}-\d{13}$")


def _validate_session_id(session_id: str) -> None:
    if not _UUID_RE.match(session_id):
        abort(400, description="Invalid session ID format")


def _validate_backup_hash(backup_hash: str) -> None:
    if not _BACKUP_HASH_RE.match(backup_hash):
        abort(400, description="Invalid backup hash format")


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

def md_to_html(text: str) -> str:
    if not text:
        return ""
    return markdown.markdown(
        text,
        extensions=["fenced_code", "tables", "codehilite", "nl2br"],
        extension_configs={"codehilite": {"css_class": "codehilite", "guess_lang": False}},
    )


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(
    log_dir: str | Path | None = None,
    claude_dir: str | Path | None = None,
) -> Flask:
    """Create and configure the Flask application.

    Parameters
    ----------
    log_dir:
        Root directory containing Copilot session folders.
        Falls back to ``COPILOT_LOG_DIR`` env var, then ``"."``.
    claude_dir:
        Root directory containing Claude Code project/session logs.
        Falls back to ``CLAUDE_LOG_DIR`` env var, then ``~/.claude/projects/``.
    """
    import os

    if log_dir is None:
        log_dir = os.environ.get("COPILOT_LOG_DIR", ".")
    copilot_path = Path(log_dir).resolve()

    if claude_dir is None:
        claude_dir = os.environ.get("CLAUDE_LOG_DIR", str(Path.home() / ".claude" / "projects"))
    claude_path = Path(claude_dir).resolve()

    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / "templates"),
    )

    # -- Security configuration ----------------------------------------------
    app.config["DEBUG"] = False
    app.config["TESTING"] = False
    app.config["SECRET_KEY"] = os.urandom(32)
    app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024  # 1 MB

    # -- Unified session index -----------------------------------------------
    # Maps session_id -> {"source": "copilot"|"claude", "path": str, ...}
    def _build_session_index() -> tuple[list[dict], dict[str, dict]]:
        copilot_sessions = copilot_discover(copilot_path)
        for s in copilot_sessions:
            s.setdefault("source", "copilot")

        claude_sessions = claude_parser.discover_sessions(claude_path)
        # claude sessions already have source="claude"

        all_sessions = copilot_sessions + claude_sessions
        all_sessions.sort(key=lambda s: s.get("created_at", ""), reverse=True)

        index = {}
        for s in all_sessions:
            index[s["id"]] = s

        return all_sessions, index

    # -- Security headers (after every response) -----------------------------
    @app.after_request
    def _security_headers(response: Response) -> Response:
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "frame-ancestors 'none'"
        )
        return response

    # -- Routes --------------------------------------------------------------

    @app.route("/")
    def index():
        sessions, _ = _build_session_index()
        copilot_count = sum(1 for s in sessions if s.get("source") != "claude")
        claude_count = sum(1 for s in sessions if s.get("source") == "claude")
        return render_template(
            "index.html",
            sessions=sessions,
            copilot_dir=str(copilot_path),
            claude_dir=str(claude_path),
            copilot_count=copilot_count,
            claude_count=claude_count,
        )

    @app.route("/session/<session_id>")
    def session_view(session_id: str):
        _validate_session_id(session_id)

        _, session_index = _build_session_index()
        session_info = session_index.get(session_id)
        if not session_info:
            abort(404)

        source = session_info.get("source", "copilot")

        if source == "claude":
            session_file = Path(session_info["path"])
            events = claude_parser.parse_events(session_file)
            conversation = claude_parser.build_conversation(events)
            stats = claude_parser.compute_stats(events)
            ws = claude_parser.extract_workspace(events)
            snapshots = {}
        else:
            session_dir = copilot_path / session_id
            if not session_dir.is_dir():
                abort(404)
            ws = parse_workspace(session_dir)
            events = copilot_parse_events(session_dir)
            conversation = copilot_build_conversation(events)
            stats = copilot_compute_stats(events)
            snapshots = parse_snapshots(session_dir)

        return render_template(
            "session.html",
            ws=ws,
            session_id=session_id,
            conversation=conversation,
            stats=stats,
            snapshots=snapshots,
            source=source,
            ts_display=ts_display,
            ts_relative=ts_relative,
            duration_between=duration_between,
            md_to_html=md_to_html,
            json=json,
            isinstance=isinstance,
            str=str,
            len=len,
            list=list,
            dict=dict,
            Markup=Markup,
        )

    # -- JSON API ------------------------------------------------------------

    @app.route("/api/sessions")
    def api_sessions():
        sessions, _ = _build_session_index()
        return jsonify(sessions)

    @app.route("/api/session/<session_id>/events")
    def api_events(session_id: str):
        _validate_session_id(session_id)

        _, session_index = _build_session_index()
        session_info = session_index.get(session_id)
        if not session_info:
            abort(404)

        if session_info.get("source") == "claude":
            events = claude_parser.parse_events(Path(session_info["path"]))
        else:
            session_dir = copilot_path / session_id
            if not session_dir.is_dir():
                abort(404)
            events = copilot_parse_events(session_dir)

        return jsonify(events)

    @app.route("/api/session/<session_id>/backup/<backup_hash>")
    def api_backup(session_id: str, backup_hash: str):
        _validate_session_id(session_id)
        _validate_backup_hash(backup_hash)
        backup_file = copilot_path / session_id / "rewind-snapshots" / "backups" / backup_hash
        # Resolve and verify the path stays within the log directory.
        resolved = backup_file.resolve()
        if not str(resolved).startswith(str(copilot_path)):
            abort(403)
        if not resolved.is_file():
            abort(404)
        content = resolved.read_text(errors="replace")
        return content, 200, {"Content-Type": "text/plain; charset=utf-8"}

    return app
