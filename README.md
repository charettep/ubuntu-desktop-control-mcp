# Ubuntu Desktop Control MCP Server

An MCP (Model Context Protocol) server that enables LLMs to control your Ubuntu desktop by taking screenshots and sending mouse clicks. This allows AI assistants to visually interact with your desktop applications.

## Features

- 📸 **Screenshot Capture**: Take full or partial screenshots of the desktop
- 🖱️ **Mouse Control**: Click at specific pixel coordinates (left, right, middle button)
- 🖥️ **Screen Info**: Query screen dimensions and display server type
- 🎯 **Mouse Movement**: Move cursor to specific positions with optional animation
- 🔍 **Display Scaling Detection**: Automatically detect and report HiDPI/scaling mismatches
- 🎛️ **Auto Coordinate Handling**: Optional auto-scaling clicks plus a converter to map screenshot pixels to click coordinates
- 🐛 **Coordinate Debugging**: Grid overlay and quadrant tools to visualize coordinate systems
- 📊 **Diagnostics**: Detailed scaling factor analysis, warnings, and recommendations

## Quick Start

### 1. Prerequisites
- Ubuntu Linux (X11 required, Wayland not fully supported)
- Python 3.9+

### 2. Installation

```bash
# Clone repository
git clone https://github.com/charettep/ubuntu-desktop-control-mcp.git
cd ubuntu-desktop-control-mcp

# Install system dependencies (requires sudo)
chmod +x install_system_deps.sh
./install_system_deps.sh

# Install Python dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Verify installation
python3 test_server.py
```

## Configuration

<details>
<summary><strong>Claude Code</strong></summary>

#### Method 1: CLI (Recommended)
```bash
claude mcp add --transport stdio ubuntu-desktop-control -- \
  /path/to/ubuntu-desktop-control-mcp/.venv/bin/python3 \
  /path/to/ubuntu-desktop-control-mcp/server.py
```

#### Method 2: Manual Config
Edit `~/.claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "ubuntu-desktop-control": {
      "command": "/path/to/ubuntu-desktop-control-mcp/.venv/bin/python3",
      "args": ["/path/to/ubuntu-desktop-control-mcp/server.py"]
    }
  }
}
```
</details>

<details>
<summary><strong>VS Code Insiders</strong></summary>

#### Method 1: MCP Command
1. Open Command Palette (`Ctrl+Shift+P`)
2. Run `MCP: Open Workspace Folder Configuration`
3. Add the server configuration below.

#### Method 2: Manual Config
Create `.vscode/mcp.json` in your workspace:
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
</details>

<details>
<summary><strong>Codex CLI</strong></summary>

#### Method 1: CLI
```bash
codex mcp add ubuntu-desktop-control -- \
  /path/to/ubuntu-desktop-control-mcp/.venv/bin/python3 \
  /path/to/ubuntu-desktop-control-mcp/server.py
```

#### Method 2: Manual Config
Edit `~/.config/codex/config.toml`:
```toml
[mcp_servers.ubuntu-desktop-control]
type = "stdio"
command = "/path/to/ubuntu-desktop-control-mcp/.venv/bin/python3"
args = ["/path/to/ubuntu-desktop-control-mcp/server.py"]
```
</details>

## Available Tools

| Tool | Purpose |
|------|---------|
| `take_screenshot` | Capture desktop image (full or region) |
| `click_screen` | Click at coordinates (supports auto-scaling) |
| `get_screen_info` | Get screen dimensions and display server type |
| `move_mouse` | Move cursor to specific positions |
| `get_display_diagnostics` | Analyze display scaling and coordinate systems |
| `convert_screenshot_coordinates` | Map screenshot pixels to logical click coordinates |
| `screenshot_with_grid` | Debugging: Screenshot with coordinate grid overlay |
| `screenshot_quadrants` | Debugging: Split screen into 4 grids for high-res displays |

<details>
<summary><strong>View Detailed Tool Documentation</strong></summary>

### `take_screenshot`
Captures a screenshot of the desktop.
- **Parameters**: `output_path` (optional), `region` (optional "x,y,w,h")
- **Returns**: Image path, dimensions, scaling factor

### `click_screen`
Sends mouse click at specified coordinates.
- **Parameters**: `x`, `y`, `button` (left/right/middle), `clicks`, `interval`, `auto_scale`
- **Example**: `click_screen(x=500, y=300, auto_scale=True)`

### `get_screen_info`
Gets screen dimensions and display server info.

### `move_mouse`
Moves mouse cursor without clicking.
- **Parameters**: `x`, `y`, `duration`

### `get_display_diagnostics`
Returns detailed scaling info and recommendations for fixing coordinate mismatches.

### `convert_screenshot_coordinates`
Helper to convert physical screenshot pixels to logical click coordinates.

### `screenshot_with_grid` & `screenshot_quadrants`
Visual debugging tools that overlay coordinate grids on screenshots.
</details>

## Display Scaling & Coordinates

If clicks land in the wrong place, you likely have a HiDPI display scaling mismatch (e.g., logical 1920x1080 vs physical 3840x2160).

**Solutions:**
1. **Auto-scale**: Use `click_screen(..., auto_scale=True)` to let the server handle it.
2. **Diagnostics**: Run `get_display_diagnostics()` to see the scaling factor.
3. **Grid**: Use `screenshot_with_grid()` to see the *logical* coordinates you should use.

## Troubleshooting

<details>
<summary><strong>Common Issues</strong></summary>

- **"Screenshot failed"**: Ensure `gnome-screenshot` or `scrot` is installed (`sudo apt install gnome-screenshot`).
- **"PyAutoGUI not installed"**: Ensure you are using the `.venv` python.
- **Wayland Issues**: This server requires X11. Check with `echo $XDG_SESSION_TYPE`. If "wayland", switch to "GNOME on Xorg" at login.
- **Permission Denied**: Run `xhost +local:` if you have X11 permission issues.

</details>

## Security

⚠️ **Warning**: This server gives LLMs full control over your mouse and visibility of your screen.
- Only use with trusted clients.
- Be aware screenshots may capture sensitive data.
- Automated clicks can be destructive.

## License

MIT License
