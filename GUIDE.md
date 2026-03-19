# py-see-claude — Setup Guide for Beginners

## What is this?

If you use **Claude Code** (the AI coding assistant in your terminal), you've probably had the problem of opening a bunch of sessions across different projects and losing track of what's running where.

**py-see-claude** is a tiny Python app that gives you a dashboard showing all your Claude Code sessions in one place — which projects they're in, whether they're actively working, and lets you click to jump to that terminal.

> Based on the original [see-claude](https://github.com/lukejbyrne/see-claude) by [@lukejbyrne](https://github.com/lukejbyrne), rewritten in Python.

---

## Before You Start

You need **one** of these installed:

### Option A: Python (direct install)

Check if you have Python 3.11+:

1. Open **Terminal** (press `Cmd + Space`, type "Terminal", hit Enter)
2. Type this and press Enter:

   ```bash
   python3 --version
   ```

3. If you see `Python 3.11.x` or higher, you're good
4. If not, install Python from **<https://python.org>** or use Homebrew: `brew install python`

### Option B: Docker (no Python needed)

If you have Docker installed, you can skip Python entirely. Check:

```bash
docker --version
```

---

## Installation

### Method 1: With uv (fastest)

```bash
git clone <repo-url>
cd py-see-claude
uv run py-see-claude
```

### Method 2: With pip

```bash
git clone <repo-url>
cd py-see-claude
pip install .
py-see-claude
```

### Method 3: With Docker (Linux only)

```bash
git clone <repo-url>
cd py-see-claude
docker build -t py-see-claude .
docker run --rm -p 3456:3456 --pid=host \
  --user "$(id -u):$(id -g)" \
  -v "$HOME/.claude:/home/app/.claude:ro" \
  py-see-claude
```

You should see:

```bash
  py-see-claude running at http://localhost:3456
```

Now open your browser and go to **<http://localhost:3456>**

---

## What You'll See

A dark screen with a count of your active Claude Code sessions. Each session shows up as a little computer monitor displaying:

- **Project name** — the folder Claude is working in
- **Status** — green (actively working), yellow (thinking), grey (idle)
- **Stats** — CPU usage, memory, how long it's been running

**Click any session** to expand it with full conversation history.

Switch to **pixel view** for a fun office scene with animated characters at desks.

The dashboard refreshes automatically, so you can leave it open.

---

## Stopping the Dashboard

To stop it, go to the Terminal where you started it and press `Ctrl + C`.

## Running It Again Later

```bash
cd py-see-claude
uv run py-see-claude
```

Or if using Docker:

```bash
docker run --rm -p 3456:3456 --pid=host \
  --user "$(id -u):$(id -g)" \
  -v "$HOME/.claude:/home/app/.claude:ro" \
  py-see-claude
```

Then open **<http://localhost:3456>** in your browser.

---

## Troubleshooting

**"command not found: python3"**
→ You need to install Python (see the "Before You Start" section above)

**"address already in use"**
→ The dashboard is already running somewhere. Either find that Terminal tab or run: `kill $(lsof -ti:3456)` then try again.

**No sessions showing up**
→ Make sure you have at least one Claude Code session running in a Terminal tab. The dashboard only detects the CLI version of Claude Code.

**Click doesn't switch Terminal tabs**
→ The click-to-focus feature uses AppleScript and only works with the built-in macOS Terminal app. If you use iTerm2 or another terminal, it won't switch tabs automatically (but the dashboard still works for monitoring).

**Docker can't see Claude sessions (macOS)**
→ Docker on macOS can't access host processes. Use `uv run py-see-claude` directly instead.

---

That's it. No accounts, no API keys, zero runtime dependencies. Just clone, run, and see all your Claudes.
