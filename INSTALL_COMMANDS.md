# MCP Server Installation Commands

Quick reference for installing the Ubuntu Desktop Control MCP server to each client.

## Prerequisites

Make sure the server is installed and tested first:

```bash
cd ubuntu-desktop-control-mcp
source .venv/bin/activate
python3 test_server.py  # Should show all tests passing
```

---

## Claude Code

### Method 1: Using CLI (Recommended)

```bash
claude mcp add --transport stdio ubuntu-desktop-control -- \
  /path/to/ubuntu-desktop-control-mcp/.venv/bin/python3 \
  /path/to/ubuntu-desktop-control-mcp/server.py
```

**Verify Installation:**
```bash
claude mcp list
```

Expected output should include `ubuntu-desktop-control`.

**Get Details:**
```bash
claude mcp get ubuntu-desktop-control
```

**Remove (if needed):**
```bash
claude mcp remove ubuntu-desktop-control
```

### Method 2: Manual Configuration

Edit `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ubuntu-desktop-control": {
      "command": "/path/to/ubuntu-desktop-control-mcp/.venv/bin/python3",
      "args": [
        "/path/to/ubuntu-desktop-control-mcp/server.py"
      ]
    }
  }
}
```

---

## VS Code Insiders

### Method 1: Using MCP Commands (Recommended)

1. Open VS Code Insiders
2. Press `Ctrl+Shift+P` (Command Palette)
3. Run: `MCP: Open Workspace Folder Configuration`
4. This creates/opens `.vscode/mcp.json`
5. Add the server configuration (see below)

### Method 2: Manual Configuration

Create or edit `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "ubuntu-desktop-control": {
      "type": "stdio",
      "command": "/path/to/ubuntu-desktop-control-mcp/.venv/bin/python3",
      "args": [
        "/path/to/ubuntu-desktop-control-mcp/server.py"
      ]
    }
  }
}
```

**For user-level configuration** (available in all workspaces):
1. Press `Ctrl+Shift+P` (Command Palette)
2. Run: `MCP: Open User Configuration`
3. Add the same configuration as above

**Note:** The `"type": "stdio"` field is **required** for stdio transport.

---

## Codex CLI

### Method 1: Using CLI (Recommended)

```bash
codex mcp add ubuntu-desktop-control -- \
  /path/to/ubuntu-desktop-control-mcp/.venv/bin/python3 \
  /path/to/ubuntu-desktop-control-mcp/server.py
```

**Verify Installation:**
```bash
codex mcp list
```

Expected output should include `ubuntu-desktop-control`.

**Get Details:**
```bash
codex mcp get ubuntu-desktop-control
```

**Remove (if needed):**
```bash
codex mcp remove ubuntu-desktop-control
```

### Method 2: Manual Configuration

Edit `~/.codex/config.toml`:

Add to the `[mcp_servers]` section:

```toml
[mcp_servers.ubuntu-desktop-control]
type = "stdio"
command = "/path/to/ubuntu-desktop-control-mcp/.venv/bin/python3"
args = ["/path/to/ubuntu-desktop-control-mcp/server.py"]
```

**Note:** The `type = "stdio"` field is **required** for stdio transport in TOML format.

**Alternative JSON format** (if your Codex uses JSON config):

```json
{
  "mcpServers": {
    "ubuntu-desktop-control": {
      "type": "stdio",
      "command": "/path/to/ubuntu-desktop-control-mcp/.venv/bin/python3",
      "args": [
        "/path/to/ubuntu-desktop-control-mcp/server.py"
      ]
    }
  }
}
```

**Note:** The `"type": "stdio"` field is **required** for stdio transport in JSON format.

---

## Quick Copy-Paste Commands

### Quick Setup Commands

**Claude Code:**
```bash
claude mcp add --transport stdio ubuntu-desktop-control -- \
  /path/to/ubuntu-desktop-control-mcp/.venv/bin/python3 \
  /path/to/ubuntu-desktop-control-mcp/server.py
```

**VS Code Insiders:**
Create `.vscode/mcp.json` with:
```json
{
  "servers": {
    "ubuntu-desktop-control": {
      "type": "stdio",
      "command": "/path/to/ubuntu-desktop-control-mcp/.venv/bin/python3",
      "args": ["/path/to/ubuntu-desktop-control-mcp/server.py"]
    }
  }
}
```

**Codex CLI:**
```bash
codex mcp add ubuntu-desktop-control -- \
  /path/to/ubuntu-desktop-control-mcp/.venv/bin/python3 \
  /path/to/ubuntu-desktop-control-mcp/server.py
```

Or add to `~/.codex/config.toml`:
```toml
[mcp_servers.ubuntu-desktop-control]
type = "stdio"
command = "/path/to/ubuntu-desktop-control-mcp/.venv/bin/python3"
args = ["/path/to/ubuntu-desktop-control-mcp/server.py"]
```

---

## Verification

After installation, verify the server is accessible:

### Claude Code
```bash
# Start a session and test
claude
# Then type: "List available MCP tools"
# Should see: take_screenshot, click_screen, get_screen_info, move_mouse
```

### VS Code Insiders
1. Open VS Code Insiders
2. Open Command Palette (`Ctrl+Shift+P`)
3. Run: `MCP: List Servers`
4. Should see `ubuntu-desktop-control` listed
5. Or check the Chat view - MCP tools should be available

### Codex CLI
```bash
codex
# Then ask: "What MCP tools are available?"
# Should see the 4 desktop control tools listed
```

---

## Troubleshooting

### Server Not Found

**Problem:** Client can't find the server

**Solution:** Verify paths are absolute:
```bash
# Check Python path exists
ls -la /path/to/ubuntu-desktop-control-mcp/.venv/bin/python3

# Check server.py exists
ls -la /path/to/ubuntu-desktop-control-mcp/server.py
```

### Server Fails to Start

**Problem:** Server starts but fails immediately

**Solution:** Test manually:
```bash
source /path/to/ubuntu-desktop-control-mcp/.venv/bin/activate
python3 /path/to/ubuntu-desktop-control-mcp/server.py
# Should start and wait for input (use Ctrl+C to exit)
```

### Tools Not Available

**Problem:** Server connected but tools not showing

**Solution:** Check server logs in client (varies by client):
- **Claude Code:** Use `--debug` flag
- **VS Code:** Check Output panel → MCP
- **Codex:** Use `-c debug_mode=true`

### Permission Errors

**Problem:** "Permission denied" when taking screenshots

**Solution:** Verify system dependencies:
```bash
dpkg -l | grep -E "gnome-screenshot|python3-xlib"
# Should show installed packages
```

---

## Environment Variables (Optional)

If you need to pass environment variables to the server:

### Claude Code
```bash
claude mcp add --transport stdio ubuntu-desktop-control \
  --env DISPLAY=:0 \
  -- /path/to/ubuntu-desktop-control-mcp/.venv/bin/python3 \
     /path/to/ubuntu-desktop-control-mcp/server.py
```

### Codex
```bash
codex mcp add ubuntu-desktop-control \
  --env DISPLAY=:0 \
  -- /path/to/ubuntu-desktop-control-mcp/.venv/bin/python3 \
     /path/to/ubuntu-desktop-control-mcp/server.py
```

### VS Code / Manual Config
Add to the server configuration:
```json
{
  "command": "...",
  "args": [...],
  "env": {
    "DISPLAY": ":0"
  }
}
```

---

## Uninstallation

### Remove from Claude Code
```bash
claude mcp remove ubuntu-desktop-control
```

### Remove from Codex
```bash
codex mcp remove ubuntu-desktop-control
```

### Remove from VS Code
Manually delete the `ubuntu-desktop-control` entry from your settings JSON.

---

## Summary

**Recommended method for each client:**

- ✅ **Claude Code:** `claude mcp add --transport stdio` (CLI command)
- ✅ **VS Code Insiders:** Create `.vscode/mcp.json` with `"type": "stdio"`
- ✅ **Codex CLI:** `codex mcp add` (CLI command) or edit `~/.codex/config.toml` with `type = "stdio"`

**Important:** All stdio configurations **must** include the `type` field:
- VS Code/Insiders: `"type": "stdio"` (JSON)
- Codex TOML: `type = "stdio"` (TOML)
- Codex JSON: `"type": "stdio"` (JSON)

All three clients can use the same server instance simultaneously!
