# Quick Start Guide

Get your Ubuntu Desktop Control MCP server up and running in 5 minutes.

## Prerequisites Check

Verify you're on X11 (required for this MCP server):

```bash
echo $XDG_SESSION_TYPE
```

Expected output: `x11` ✓

If you see `wayland`, you'll need to switch to X11 session (logout and select "GNOME on Xorg" at login screen).

## Installation (3 Steps)

### Step 1: Install System Dependencies

```bash
cd ubuntu-desktop-control-mcp
./install_system_deps.sh
```

This installs: `python3-xlib`, `scrot`, `gnome-screenshot`, `python3-tk`, `python3-dev`

### Step 2: Install Python Packages

```bash
source .venv/bin/activate
pip install -e .
```

### Step 3: Test Installation

```bash
python3 test_server.py
```

Expected output:
```
✓ PyAutoGUI imported successfully
✓ Server tools imported successfully
✓ Screen Info: Resolution 2560x1440, Display Server: x11
✓ Screenshot captured successfully
✓ Mouse moved to (1280, 720)
✓ All tests passed!
```

## Configuration

### For Claude Code

Add to `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ubuntu-desktop-control": {
      "command": "python3",
      "args": [
        "/path/to/ubuntu-desktop-control-mcp/server.py"
      ]
    }
  }
}
```

Or use automatic installation:

```bash
source .venv/bin/activate
mcp install server.py --name "ubuntu-desktop-control"
```

### For VS Code Insiders

Add to Settings (JSON):

```json
{
  "mcp.servers": {
    "ubuntu-desktop-control": {
      "command": "python3",
      "args": [
        "/path/to/ubuntu-desktop-control-mcp/server.py"
      ]
    }
  }
}
```

### For Codex CLI

Add to `~/.config/codex/config.toml`:

```toml
[mcp_servers.ubuntu-desktop-control]
type = "stdio"
command = "python3"
args = ["/path/to/ubuntu-desktop-control-mcp/server.py"]
```

## Test with MCP Inspector

```bash
npx @modelcontextprotocol/inspector python3 server.py
```

This opens a web UI where you can:
- View all available tools
- Test each tool with sample parameters
- See the structured output

## Available Tools Summary

| Tool | Purpose | Example |
|------|---------|---------|
| `take_screenshot` | Capture desktop image | `take_screenshot()` |
| `click_screen` | Click at coordinates | `click_screen(x=500, y=300)` |
| `get_screen_info` | Get screen dimensions | `get_screen_info()` |
| `move_mouse` | Move cursor | `move_mouse(x=100, y=100)` |

## Example Usage in LLM Conversation

**User**: "Take a screenshot of my desktop and click on the Firefox icon"

**LLM Response**:
1. Calls `take_screenshot()` → receives `/tmp/screenshot_20231212_143022.png`
2. Analyzes image to find Firefox icon at pixel (150, 50)
3. Calls `click_screen(x=150, y=50)` → clicks Firefox
4. Calls `take_screenshot()` → verifies Firefox opened

## Troubleshooting

### "Screenshot failed" error

Install gnome-screenshot:
```bash
sudo apt install gnome-screenshot
```

### "PyAutoGUI not installed"

Activate venv and reinstall:
```bash
source .venv/bin/activate
pip install pyautogui pillow
```

### "Coordinates out of bounds"

Check your screen size first:
```bash
python3 -c "from server import get_screen_info; print(get_screen_info())"
```

## Security Note

⚠️ This server gives LLMs full control over your mouse and can see your screen. Only use with trusted LLM clients and be aware that:
- Screenshots may capture sensitive information
- Automated clicks could trigger unintended actions
- Consider testing in a VM or non-production environment first

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Check [config-examples/](config-examples/) for client configuration templates
- Explore more advanced features in the tool documentation
