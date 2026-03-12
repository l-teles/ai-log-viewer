# ai-session-log-viewer

A local web UI for browsing and understanding **GitHub Copilot**, **Claude Code**, and **VS Code Chat** agent session logs.

AI coding agents produce rich session logs (JSONL events, workspace metadata,
rewind snapshots, chat session JSON). This tool turns those raw files into a readable,
interactive timeline so you can review what happened — the user prompts, assistant
reasoning, tool calls, sub-agent activity, errors, and file snapshots — all in one place.

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

---

## Features

- **Multi-source support** — browse sessions from GitHub Copilot, Claude Code, and
  VS Code Chat side by side, with color-coded source badges (purple for Claude,
  orange for Copilot, green for VS Code Chat).
- **Dashboard homepage** — session counts per source, directory paths, search bar,
  and source filters to quickly find what you need.
- **Session index** — lists every session found, with summary, repo/cwd,
  branch, model, and timestamps.
- **Interactive timeline** — color-coded conversation view with:
  - User messages (with file attachments)
  - Assistant responses (rendered Markdown, expandable reasoning/thinking)
  - Tool calls & results (expandable arguments / output)
  - Sub-agent launches & completions
  - System notifications (auto-detected from XML context tags)
  - Errors
- **Statistics sidebar** — message counts, token usage, tool breakdown with visual
  bars, model name, and rewind snapshot history.
- **Filters everywhere** — filter by source (Claude / Copilot / VS Code Chat) on the homepage,
  filter by event type (User / Assistant / Tools / Sub-Agents / Errors) in sessions.
- **Search** — full-text search across session names, branches, directories, and models.
- **Dark / Light mode** — toggle between themes with one click; preference is
  persisted in `localStorage`.
- **JSON API** — programmatic access at `/api/sessions` and
  `/api/session/<id>/events`.
- **Security** — UUID & backup-hash validation, path-traversal protection,
  Content-Security-Policy headers, localhost-only by default.

## Quick start

### Install from source

```bash
git clone https://github.com/l-teles/ai-log-viewer.git
cd ai-log-viewer
pip install .
```

### Install from PyPI

```bash
pip install ai-log-viewer
```

### Run

```bash
# Auto-detect default directories for all sources
ai-log-viewer

# Specify directories explicitly
ai-log-viewer --copilot-dir ~/.copilot/session-state/ --claude-dir ~/.claude/projects/ --vscode-dir "~/Library/Application Support/Code/User/"

# Or use the module directly
python -m ai_log_viewer
```

Then open **http://127.0.0.1:5000** in your browser.

### Default directories

| Source         | macOS / Linux default                                 | Windows default                          | Override flag    | Env variable      |
|----------------|-------------------------------------------------------|------------------------------------------|------------------|--------------------|
| GitHub Copilot | `~/.copilot/session-state/`                           | `%LOCALAPPDATA%\github-copilot\session-state` | `--copilot-dir`  | `COPILOT_LOG_DIR`  |
| Claude Code    | `~/.claude/projects/`                                 | `%LOCALAPPDATA%\claude\projects`         | `--claude-dir`   | `CLAUDE_LOG_DIR`   |
| VS Code Chat   | `~/Library/Application Support/Code/User/` (macOS) / `~/.config/Code/User/` (Linux) | `%APPDATA%\Code\User`  | `--vscode-dir`   | `VSCODE_LOG_DIR`   |

### Options

```
usage: ai-log-viewer [-h] [--copilot-dir DIR] [--claude-dir DIR]
                          [--vscode-dir DIR] [-p PORT] [--host HOST]
                          [--debug] [-V] [log_dir]

positional arguments:
  log_dir               Directory containing Copilot session log folders
                        (default: ~/.copilot/session-state/)

options:
  --copilot-dir DIR     Directory containing Copilot session log folders
                        (overrides positional arg)
  --claude-dir DIR      Directory containing Claude Code session logs
                        (default: ~/.claude/projects/)
  --vscode-dir DIR      Directory containing VS Code Chat session logs
                        (default: platform-dependent)
  -p, --port PORT       Port to listen on (default: 5000)
  --host HOST           Host to bind to (default: 127.0.0.1)
  --debug               Run in Flask debug mode (local development only)
  -V, --version         Show version and exit
```

## Expected directory layouts

### GitHub Copilot (`~/.copilot/session-state/`)

```
session-state/
├── 4e71aaa0-f131-41fd-aeee-8bcaa5efb315/
│   ├── workspace.yaml          # Session metadata
│   ├── events.jsonl            # Conversation event stream
│   ├── checkpoints/
│   │   └── index.md
│   └── rewind-snapshots/
│       ├── index.json          # Snapshot manifest
│       └── backups/            # File content snapshots
│           ├── ff627b50b0554488-1773312027139
│           └── ...
├── 8b3c9d7d-60f7-4e4c-a442-eb2ee7ee68e2/
│   └── ...
└── ...
```

### Claude Code (`~/.claude/projects/`)

```
projects/
├── -Users-you-project-alpha/
│   ├── a1b2c3d4-e5f6-7890-abcd-ef1234567890.jsonl
│   ├── d4c3b2a1-f6e5-0987-dcba-0987654321fe.jsonl
│   └── ...
├── -Users-you-project-beta/
│   └── ...
└── ...
```

Each `.jsonl` file is a single session containing user/assistant/system events
with tool calls, thinking blocks, and usage metadata.

### VS Code Chat (`~/Library/Application Support/Code/User/`)

```
User/
├── workspaceStorage/
│   ├── abc123hash/
│   │   ├── workspace.json            # Maps to project folder
│   │   └── chatSessions/
│   │       ├── 88ca1adb-bf72-4478-9982-6886cb99785e.json
│   │       └── ...
│   └── ...
└── globalStorage/
    └── emptyWindowChatSessions/
        ├── 3a9ae123-2cbe-4c1d-b5af-3d4cd1f0ad2e.jsonl
        └── ...
```

Each `.json` file is a single chat session with user messages, assistant responses,
tool call rounds, and timing metadata.

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Lint
ruff check src/ tests/

# Test
pytest
```

## Security

- **Localhost only** — binds to `127.0.0.1` by default; never expose to the public
  internet without authentication.
- **Input validation** — session IDs must be valid UUIDs; backup hashes are validated
  against a strict pattern.
- **Path-traversal protection** — resolved file paths are verified via
  `Path.relative_to()` to stay within the configured log directory.
- **HTML sanitization** — Markdown output is sanitized to strip dangerous tags
  (`<script>`, `<iframe>`, etc.) and event handler attributes.
- **Security headers** — `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, and `Content-Security-Policy` are set on every response.
- **No debug in production** — debug mode is off by default and must be explicitly
  enabled via `--debug`.
- **Dependency monitoring** — Dependabot is configured for automated security updates.

## License

[MIT](LICENSE)
