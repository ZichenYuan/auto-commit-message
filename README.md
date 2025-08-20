# commit-buddy – an MCP server for smart Git commits

Generate Conventional-Commits style messages from `git diff`, and (optionally) `git add/commit/push` — all exposed as **Model Context Protocol (MCP)** tools for your editor agents.

---

## ✨ Features

* `get_git_diff` — return a redacted, unified git diff (staged-only or full working tree)
* `stage_all` — stage changes (optionally by pattern)
* `generate_commit_message` — LLM-generated message (Conventional Commits) from the diff
* `commit_and_push` — commit locally and optionally push, with safe guards and dry-run

Built with **Python** + **FastMCP** (stdio transport). Optional LLM generation via **OpenAI**.

---

## ✅ Requirements

* Python 3.9+
* Git installed and configured (SSH or credential manager)
* (Optional) OpenAI API key if you want auto message generation

---

## 🧰 Install (local)

```bash
# clone & enter the project
cd /ABSOLUTE/PATH/TO/auto-commit-message

# create & activate venv
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# install deps
pip install fastmcp openai       # add python-dotenv if you want auto .env loading
```

> Tip: keep your venv activated when developing/running locally.

---

## 🔐 Environment configuration

Create a `.env` (or export vars in your shell). Start from `.env.example`:

```bash
# Required for message generation
OPENAI_API_KEY=sk-REPLACE_ME

# Optional tuning
COMMIT_BUDDY_OPENAI_MODEL=gpt-4o-mini
COMMIT_BUDDY_TEMPERATURE=0.2
COMMIT_BUDDY_MAX_DIFF_CHARS=200000

# Safety: absolute repo paths allowed to run git commands in (colon-separated on macOS/Linux)
# Leave blank to disable scoping during local dev
COMMIT_BUDDY_ALLOWED_ROOTS=/ABS/PATH/TO/auto-commit-message
```

> **Never commit real API keys.** Use `.env.example` in version control and keep your own `.env` ignored.

---

## ▶️ Run & Inspect (MCP Inspector / stdio)

1. Install Inspector (Node.js required):

   ```bash
   npm install -g @modelcontextprotocol/inspector
   ```
2. Start Inspector against your server:

   ```bash
   mcp-inspector --config inspector.config.json --server commit-buddy
   ```

   Example `inspector.config.json`:

   ```json
   {
     "mcpServers": {
       "commit-buddy": {
         "command": "python3",
         "args": ["/ABS/PATH/TO/auto-commit-message/server.py"],
         "env": {
           "OPENAI_API_KEY": "sk-REPLACE_ME",
           "COMMIT_BUDDY_ALLOWED_ROOTS": "/ABS/PATH/TO/auto-commit-message"
         }
       }
     }
   }
   ```
3. In the Inspector UI → **Connect**, then test the tools (start with `commit_and_push` + `{"dry_run": true}`).

---

## 🧩 Configure in editors

### Cursor (built-in MCP)

Open **Settings → Open Settings (JSON)** and add:

```json
{
  "mcp.servers": {
    "commit-buddy": {
      "command": "/ABS/PATH/TO/auto-commit-message/.venv/bin/python",
      "args": ["/ABS/PATH/TO/auto-commit-message/server.py"],
      "cwd": "/ABS/PATH/TO/auto-commit-message",
      "env": {
        "OPENAI_API_KEY": "sk-REPLACE_ME",
        "COMMIT_BUDDY_ALLOWED_ROOTS": "/ABS/PATH/TO/auto-commit-message"
      }
    }
  }
}
```

Reload Cursor or toggle the server entry.

### VS Code via **Cline** extension (recommended)

Add to VS Code **settings.json**:

```json
{
  "cline.mcpServers": {
    "commit-buddy": {
      "command": "/ABS/PATH/TO/auto-commit-message/.venv/bin/python",
      "args": ["/ABS/PATH/TO/auto-commit-message/server.py"],
      "cwd": "/ABS/PATH/TO/auto-commit-message",
      "env": {
        "OPENAI_API_KEY": "sk-REPLACE_ME",
        "COMMIT_BUDDY_ALLOWED_ROOTS": "/ABS/PATH/TO/auto-commit-message"
      }
    }
  }
}
```

Open Cline, go to **Tools**, and you’ll see `commit-buddy` tools.

### VS Code via **Continue.dev**

```json
{
  "continue.mcpServers": {
    "commit-buddy": {
      "command": "/ABS/PATH/TO/auto-commit-message/.venv/bin/python",
      "args": ["/ABS/PATH/TO/auto-commit-message/server.py"],
      "cwd": "/ABS/PATH/TO/auto-commit-message",
      "env": {
        "OPENAI_API_KEY": "sk-REPLACE_ME",
        "COMMIT_BUDDY_ALLOWED_ROOTS": "/ABS/PATH/TO/auto-commit-message"
      }
    }
  }
}
```

---

## 🧪 Quick test flow

1. Make an edit in your repo.
2. `stage_all` → stage changes (optional if you already staged).
3. `get_git_diff` → confirm the diff.
4. `generate_commit_message` → get a Conventional Commit message.
5. `commit_and_push` with `{ "dry_run": true }` → preview.
6. Re-run with `dry_run=false` (and `push=true` if you want to push).

> If you want pushes to `main/master` to be blocked, set `allow_main_push=false` in the tool call.

---

## 🛠️ Troubleshooting

* **Red dot in editor**: use absolute paths for `command`, `args[0]`, and `cwd`. Prefer the venv interpreter path.
* **ModuleNotFoundError**: you’re not using the venv Python. Point `command` to `.venv/bin/python`.
* **Not a git repository**: set the tool `path` to your repo root.
* **Path not allowed**: set `COMMIT_BUDDY_ALLOWED_ROOTS` to include the repo (absolute path) or leave it blank during dev.
* **Push fails**: configure a remote (`git remote -v`) and working SSH creds.

---

## 🔒 Security

* Do **not** hardcode real secrets in repo or settings. Prefer per-user editor settings or OS keychain.
* Consider setting `COMMIT_BUDDY_ALLOWED_ROOTS` in production to lock down filesystem access.

---

## 📜 License

MIT (or your choice).
