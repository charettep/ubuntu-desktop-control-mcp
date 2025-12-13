# Ubuntu Desktop Control MCP Server

An MCP (Model Context Protocol) server that enables LLMs to control your Ubuntu desktop by taking screenshots and sending mouse clicks. This allows AI assistants to visually interact with your desktop applications.

## Features

- 📸 **Screenshot Capture**: Take full or partial screenshots of the desktop
- 🖱️ **Mouse Control**: Click at specific pixel coordinates (left, right, middle button)
- ⌨️ **Keyboard Control**: Type text and press keys
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

#### From PyPI (Recommended)
```bash
pip install ubuntu-desktop-control
```

#### From Source
```bash
# Clone repository
git clone https://github.com/charettep/ubuntu-desktop-control-mcp.git
cd ubuntu-desktop-control-mcp

# Install system dependencies (requires sudo)
chmod +x install_system_deps.sh
./install_system_deps.sh

# Install Python dependencies
pip install -e .
```

## Configuration

### Claude Code
<details>
<summary>Installation Methods</summary>

#### Method 1: CLI (Recommended)
```bash
claude mcp add --transport stdio ubuntu-desktop-control -- \
  ubuntu-desktop-control
```

#### Method 2: Manual Config
Edit `~/.claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "ubuntu-desktop-control": {
      "command": "ubuntu-desktop-control",
      "args": []
    }
  }
}
```
</details>

### VS Code Insiders
<details>
<summary>Installation Methods</summary>

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
      "command": "ubuntu-desktop-control",
      "args": []
    }
  }
}
```
</details>

### Codex CLI
<details>
<summary>Installation Methods</summary>

#### Method 1: CLI
```bash
codex mcp add ubuntu-desktop-control -- \
  ubuntu-desktop-control
```

#### Method 2: Manual Config
Edit `~/.config/codex/config.toml`:
```toml
[mcp_servers.ubuntu-desktop-control]
type = "stdio"
command = "ubuntu-desktop-control"
args = []
```
</details>

## Tools

### Core Capabilities
| Tool | Description |
|------|-------------|
| `take_screenshot` | Capture the desktop or a specific region to a file. |
| `click_screen` | Click at specific coordinates. Supports auto-scaling for HiDPI displays. |
| `move_mouse` | Move the cursor to coordinates without clicking. |
| `drag_mouse` | Drag the cursor to coordinates while holding a mouse button. |
| `type_text` | Type text using the keyboard. |
| `press_key` | Press a specific key (e.g., 'enter', 'esc'). |
| `press_hotkey` | Press a combination of keys simultaneously (e.g., Ctrl+Shift+C). |
| `get_screen_info` | Get screen dimensions and display server type (X11/Wayland). |
| `get_display_diagnostics` | Troubleshoot scaling and coordinate mismatches. |
| `screenshot_with_grid` | Capture screen with a coordinate grid overlay for precise positioning. |
| `screenshot_quadrants` | Split screen into 4 quadrants for easier analysis of high-res displays. |
| `convert_screenshot_coordinates` | Convert pixels from a screenshot to logical click coordinates. |
| `list_prompt_templates` | List available prompt templates (for clients without native prompt support). |

### Prompt Rendering Tools
These tools allow clients without native prompt support (like Codex CLI) to render prompt templates as text.

| Tool | Description |
|------|-------------|
| `render_prompt_baseline_display_check` | Render the baseline display check prompt. |
| `render_prompt_capture_full_desktop` | Render the full desktop capture prompt. |
| `render_prompt_capture_region_for_task` | Render the region capture prompt. |
| `render_prompt_grid_overlay_snapshot` | Render the grid overlay prompt. |
| `render_prompt_quadrant_scan` | Render the quadrant scan prompt. |
| `render_prompt_convert_screenshot_coordinates` | Render the coordinate conversion prompt. |
| `render_prompt_safe_click` | Render the safe click prompt. |
| `render_prompt_hover_and_capture` | Render the hover and capture prompt. |
| `render_prompt_coordinate_mismatch_recovery` | Render the mismatch recovery prompt. |
| `render_prompt_end_to_end_capture_and_act` | Render the end-to-end workflow prompt. |

## Prompts

| Prompt | Description |
|--------|-------------|
| `baseline_display_check` | Check display settings and scaling before starting tasks. |
| `capture_full_desktop` | Capture and summarize the full desktop state. |
| `capture_region_for_task` | Capture a specific region for detailed inspection. |
| `grid_overlay_snapshot` | Capture with grid to identify precise coordinates. |
| `quadrant_scan` | Analyze high-res screens using quadrants. |
| `safe_click` | Perform a click with safety checks and scaling awareness. |
| `hover_and_capture` | Hover to reveal UI elements, then capture. |
| `coordinate_mismatch_recovery` | Diagnose and fix missed clicks. |
| `end_to_end_capture_and_act` | Plan and execute a full interaction loop. |

## Configuration & Customization

### Environment Variables

The server relies on standard Linux/X11 environment variables to locate and interact with the desktop session.

| Variable | Description | Default |
|----------|-------------|---------|
| `DISPLAY` | X11 display identifier. Required for the server to know *which* screen to control. | `:0` |
| `XDG_SESSION_TYPE` | Used to detect if running on X11 or Wayland. | `unknown` |
| `XAUTHORITY` | Path to X11 authority file. Required if running from a different user context (e.g., sudo, docker) or over SSH. | `~/.Xauthority` |

### Passing Environment Variables

You can customize these variables in your MCP client configuration.

#### Claude Desktop (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "ubuntu-desktop-control": {
      "command": "ubuntu-desktop-control",
      "args": [],
      "env": {
        "DISPLAY": ":0",
        "XAUTHORITY": "/home/user/.Xauthority"
      }
    }
  }
}
```

#### VS Code (`.vscode/mcp.json`)
```json
{
  "servers": {
    "ubuntu-desktop-control": {
      "command": "ubuntu-desktop-control",
      "args": [],
      "env": {
        "DISPLAY": ":0"
      }
    }
  }
}
```

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
