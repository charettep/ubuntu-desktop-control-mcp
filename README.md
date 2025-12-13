# Ubuntu Desktop Control MCP Server

An MCP (Model Context Protocol) server that enables LLMs to control your Ubuntu desktop by taking screenshots and sending mouse clicks. This allows AI assistants to visually interact with your desktop applications.

## Features

- 📸 **Screenshot Capture**: Take full or partial screenshots of your desktop
- 🖱️ **Mouse Control**: Click at specific pixel coordinates (left, right, middle button)
- 🖥️ **Screen Info**: Query screen dimensions and display server type
- 🎯 **Mouse Movement**: Move cursor to specific positions with optional animation
- 🔍 **Display Scaling Detection**: Automatically detect and report HiDPI/scaling mismatches
- 🎛️ **Auto Coordinate Handling**: Optional auto-scaling clicks plus a converter to map screenshot pixels to click coordinates
- 🐛 **Coordinate Debugging**: Grid overlay and quadrant tools to visualize coordinate systems (configurable grid size)
- 📊 **Diagnostics**: Detailed scaling factor analysis, warnings, and recommendations

## Requirements

### System Requirements
- Ubuntu Linux (or other Debian-based distro)
- X11 display server (GNOME on X11, Xfce, etc.)
- Python 3.9 or higher

### System Dependencies

**Quick Install** - Run the provided installation script:

```bash
chmod +x install_system_deps.sh
./install_system_deps.sh
```

**Manual Install** - Or install packages manually:

```bash
sudo apt update
sudo apt install -y python3-xlib scrot python3-tk python3-dev gnome-screenshot
```

**Note**: These packages are required for PyAutoGUI to work on Linux:
- `python3-xlib`: X11 library for Python
- `scrot`: Screenshot utility (fallback)
- `gnome-screenshot`: GNOME screenshot tool (primary on GNOME desktops)
- `python3-tk`: Tkinter for GUI operations
- `python3-dev`: Python development headers

**Optional performance boost:** `pip install mss` to enable a faster screenshot backend (the server falls back to PyAutoGUI if it isn't installed).

## Installation

### 1. Clone or Download

```bash
cd /home/p/1_Projects/1_Docs/mcp/ubuntu-desktop-control-mcp
```

### 2. Install Python Dependencies

The virtual environment is already created. Just activate it and install:

```bash
source .venv/bin/activate
pip install -e .
```

If starting fresh, create the venv first:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 3. Verify Installation

Run the comprehensive test suite:

```bash
source .venv/bin/activate
python3 test_server.py
```

Expected output:
```
✓ PyAutoGUI imported successfully
✓ Server tools imported successfully
✓ Screen Info: Resolution 2560x1440, Display Server: x11
✓ Screenshot captured successfully
✓ Mouse moved to center
✓ All tests passed!
```

**Verified on:** Ubuntu 22.04 LTS, GNOME on X11, Python 3.10, Screen Resolution 2560x1440

## Configuration

**📖 For complete installation commands, see [INSTALL_COMMANDS.md](INSTALL_COMMANDS.md)**

### Claude Code CLI

**Quick Install:**
```bash
claude mcp add --transport stdio ubuntu-desktop-control -- \
  /home/p/1_Projects/1_Docs/mcp/ubuntu-desktop-control-mcp/.venv/bin/python3 \
  /home/p/1_Projects/1_Docs/mcp/ubuntu-desktop-control-mcp/server.py
```

**Or** manually add to your `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ubuntu-desktop-control": {
      "command": "/home/p/1_Projects/1_Docs/mcp/ubuntu-desktop-control-mcp/.venv/bin/python3",
      "args": [
        "/home/p/1_Projects/1_Docs/mcp/ubuntu-desktop-control-mcp/server.py"
      ]
    }
  }
}
```

**Important:** Use the virtual environment's Python to ensure all dependencies are available.

Or use the automated installation:

```bash
cd /home/p/1_Projects/1_Docs/mcp/ubuntu-desktop-control-mcp
source .venv/bin/activate
mcp install server.py --name "ubuntu-desktop-control"
```

### VS Code Insiders

**Quick Install:**
```bash
code-insiders --add-mcp '{"ubuntu-desktop-control":{"command":"/home/p/1_Projects/1_Docs/mcp/ubuntu-desktop-control-mcp/.venv/bin/python3","args":["/home/p/1_Projects/1_Docs/mcp/ubuntu-desktop-control-mcp/server.py"]}}'
```

**Or** manually add to your VS Code settings (`.vscode/settings.json` or user settings):

```json
{
  "mcp.servers": {
    "ubuntu-desktop-control": {
      "command": "/home/p/1_Projects/1_Docs/mcp/ubuntu-desktop-control-mcp/.venv/bin/python3",
      "args": [
        "/home/p/1_Projects/1_Docs/mcp/ubuntu-desktop-control-mcp/server.py"
      ]
    }
  }
}
```

### Codex CLI

**Quick Install:**
```bash
codex mcp add ubuntu-desktop-control -- \
  /home/p/1_Projects/1_Docs/mcp/ubuntu-desktop-control-mcp/.venv/bin/python3 \
  /home/p/1_Projects/1_Docs/mcp/ubuntu-desktop-control-mcp/server.py
```

**Or** manually add to your Codex configuration file (`~/.config/codex/config.toml` or `config.json`):

```json
{
  "mcpServers": {
    "ubuntu-desktop-control": {
      "command": "/home/p/1_Projects/1_Docs/mcp/ubuntu-desktop-control-mcp/.venv/bin/python3",
      "args": [
        "/home/p/1_Projects/1_Docs/mcp/ubuntu-desktop-control-mcp/server.py"
      ]
    }
  }
}
```

## Available Tools

### 1. `take_screenshot`

Captures a screenshot of the desktop.

**Parameters:**
- `output_path` (optional): Custom path for screenshot file. Defaults to `/tmp/screenshot_TIMESTAMP.png`
- `region` (optional): Region to capture as "x,y,width,height". Defaults to full screen

**Returns:**
- `success`: Boolean indicating if screenshot was successful
- `file_path`: Path to the saved screenshot file
- `width`, `height`: Logical screen dimensions in pixels
- `actual_width`, `actual_height`: Physical screenshot dimensions
- `scaling_factor`: Detected scaling factor
- `warnings`: Non-fatal environment/scaling warnings (e.g., Wayland session)
- `error`: Error message if failed

**Examples:**
```python
# Full screen to temp file
take_screenshot()

# Save to specific location
take_screenshot(output_path="/tmp/my_desktop.png")

# Capture specific region (800x600 starting at 100,100)
take_screenshot(region="100,100,800,600")
```

### 2. `click_screen`

Sends mouse click at specified coordinates.

**Parameters:**
- `x`: X coordinate in pixels (required)
- `y`: Y coordinate in pixels (required)
- `button`: Mouse button - "left", "right", or "middle" (default: "left")
- `clicks`: Number of clicks - 1 for single, 2 for double (default: 1)
- `interval`: Seconds between clicks if clicks > 1 (default: 0.0)
- `auto_scale`: If true, divides incoming coordinates by the detected scaling factor so you can pass screenshot coordinates directly

**Returns:**
- `success`: Boolean indicating if click succeeded
- `x`, `y`: Coordinates where click was performed
- `button`, `clicks`: Click details
- `applied_scaling`: Scaling factor used when `auto_scale=True`
- `warnings`: Non-fatal environment/scaling warnings
- `error`: Error message if failed

**Examples:**
```python
# Single left click
click_screen(x=500, y=300)

# Right click
click_screen(x=500, y=300, button="right")

# Double click
click_screen(x=500, y=300, clicks=2, interval=0.1)

# Use screenshot coordinates directly
click_screen(x=1500, y=900, auto_scale=True)
```

### 3. `get_screen_info`

Gets screen dimensions and display server info.

**Returns:**
- `success`: Boolean
- `width`, `height`: Screen dimensions in pixels
- `display_server`: Display server type ("x11" or "wayland")
- `scaling_factor`: Detected scaling factor
- `warnings`: Non-fatal environment/scaling warnings

**Example:**
```python
get_screen_info()
# Returns: {"success": true, "width": 1920, "height": 1080, "display_server": "x11", "scaling_factor": 1.0}
```

### 4. `move_mouse`

Moves mouse cursor to specified coordinates without clicking.

**Parameters:**
- `x`: X coordinate in pixels (required)
- `y`: Y coordinate in pixels (required)
- `duration`: Animation duration in seconds (default: 0.0 for instant)

**Returns:**
- `success`: Boolean indicating if move succeeded
- `x`, `y`: Target coordinates
- `error`: Error message if failed

**Examples:**
```python
# Instant move
move_mouse(x=500, y=300)

# Smooth animated move
move_mouse(x=500, y=300, duration=0.5)
```

### 5. `get_display_diagnostics`

Gets detailed diagnostic information about display scaling and coordinate systems.

**Returns:**
- `success`: Boolean
- `logical_width`, `logical_height`: Screen dimensions reported by OS
- `actual_screenshot_width`, `actual_screenshot_height`: Actual screenshot pixel dimensions
- `scaling_factor`: Detected scaling factor (1.0 = no scaling, 2.0 = 2x, etc.)
- `has_scaling_mismatch`: Whether scaling is detected
- `display_server`: Display server type
- `recommendation`: Specific advice for fixing coordinate issues
- `warnings`: Non-fatal environment/scaling warnings

**Example:**
```python
diagnostics = get_display_diagnostics()
print(f"Scaling factor: {diagnostics.scaling_factor}x")
print(diagnostics.recommendation)
```

**Use this when:**
- Clicks are landing in the wrong position
- You suspect display scaling is causing issues
- You need to understand the coordinate system

### 6. `convert_screenshot_coordinates`

Converts screenshot pixel coordinates to logical coordinates for `click_screen`, using the detected scaling factor.

**Parameters:**
- `screenshot_x`: X coordinate from the screenshot (pixels)
- `screenshot_y`: Y coordinate from the screenshot (pixels)

**Returns:**
- `logical_x`, `logical_y`: Coordinates to send to `click_screen`
- `scaling_factor`: Scaling factor used
- `warnings`: Non-fatal environment/scaling warnings
- `error`: Error message if conversion failed

**Example:**
```python
result = convert_screenshot_coordinates(screenshot_x=1500, screenshot_y=900)
click_screen(x=result.logical_x, y=result.logical_y)
```

### 7. `screenshot_with_grid`

Takes a screenshot with a coordinate grid overlay for debugging positioning.

**Parameters:**
- `output_path` (optional): Custom path for screenshot file
- `grid_size`: Distance between grid lines in pixels (minimum 10, default 100)

**Returns:**
- ScreenshotResult with annotated screenshot showing coordinate grid

**Examples:**
```python
# Default 100px grid
screenshot_with_grid()

# Finer 50px grid
screenshot_with_grid(grid_size=50)

# Custom output path
screenshot_with_grid(output_path="/tmp/debug.png", grid_size=200)
```

**Use this when:**
- You need to visualize the exact coordinate system
- Debugging click position issues
- Understanding the relationship between screenshot and screen coordinates

### 8. `screenshot_quadrants`

Splits a screenshot into four quadrant images, each with a coordinate grid showing full-screen logical coordinates. Useful for high-res displays where one image is too dense for vision analysis.

**Parameters:**
- `output_dir` (optional): Directory to save images (default: `/tmp`)
- `grid_size`: Distance between grid lines in pixels (minimum 10, default 100)

**Returns:**
- `full_screenshot_path` plus four quadrant image paths
- `scaling_factor`: Detected scaling
- `quadrant_info`: Explanation of the split and grid usage
- `warnings`: Non-fatal environment/scaling warnings

**Examples:**
```python
# Default 100px grid
screenshot_quadrants()

# Denser grid
screenshot_quadrants(grid_size=50)
```

**Use this when:**
- Screens are high resolution and single-image analysis is noisy
- You want easier OCR/icon detection per quadrant
- You need grid labels that map directly to `click_screen` coordinates

## Understanding Display Scaling

### The Problem

On HiDPI/high-resolution displays with scaling enabled, there can be a mismatch between:
- **Logical pixels**: What the OS and PyAutoGUI report (e.g., 1920x1080)
- **Physical pixels**: The actual screenshot resolution (e.g., 3840x2160 on 2x scaling)

This causes clicks to land at the wrong position when analyzing screenshots.

### How to Detect Scaling Issues

1. **Automatic Detection**: All screenshot and click tools now include scaling warnings
2. **Manual Diagnostics**: Use `get_display_diagnostics()` to check scaling factor
3. **Visual Debugging**: Use `screenshot_with_grid()` to see the coordinate system

### How to Fix Coordinate Mismatches

**Method 1: Auto-scale clicks**
```python
# Pass screenshot coordinates directly; server divides by scaling factor
click_screen(x=1500, y=900, auto_scale=True)
```

**Method 2: Convert first, then click**
```python
convert = convert_screenshot_coordinates(screenshot_x=1500, screenshot_y=900)
click_screen(x=convert.logical_x, y=convert.logical_y)
```

**Method 3: Manually adjust before clicking**
```python
# Take screenshot and get scaling info
result = take_screenshot()
scaling_factor = result.scaling_factor  # e.g., 2.0

# If you identify something at pixel (1000, 500) in the screenshot
screenshot_x, screenshot_y = 1000, 500

# Convert to logical coordinates for clicking
click_x = int(screenshot_x / scaling_factor)  # 500
click_y = int(screenshot_y / scaling_factor)  # 250

# Click at corrected position
click_screen(x=click_x, y=click_y)
```

**Method 4: Use Grid Overlay**
```python
# Take screenshot with coordinate grid
screenshot_with_grid(grid_size=100)

# The grid shows LOGICAL coordinates directly
# Read the labels on the grid to find the correct click position
```

**Method 5: Check Diagnostics First**
```python
# Get diagnostic information
diag = get_display_diagnostics()
print(diag.recommendation)

# If scaling_factor is 1.0, no adjustment needed
# If scaling_factor is 2.0, divide screenshot coords by 2 (or use auto_scale)
```

### Common Scaling Scenarios

| Display Setup | Logical Size | Physical Size | Scaling Factor | Fix |
|--------------|-------------|---------------|----------------|-----|
| No scaling | 1920x1080 | 1920x1080 | 1.0x | No adjustment needed |
| 2x scaling (200%) | 1920x1080 | 3840x2160 | 2.0x | Divide coords by 2 |
| 1.5x scaling (150%) | 1920x1080 | 2880x1620 | 1.5x | Divide coords by 1.5 |
| Fractional (125%) | 1920x1080 | 2400x1350 | 1.25x | Divide coords by 1.25 |

## Testing

### Using MCP Inspector

Test your server with the MCP Inspector:

```bash
cd /home/p/1_Projects/1_Docs/mcp/ubuntu-desktop-control-mcp
source .venv/bin/activate
npx @modelcontextprotocol/inspector python3 server.py
```

This opens a web interface where you can test all tools interactively.

### Manual Testing

Create a test script:

```python
#!/usr/bin/env python3
from server import take_screenshot, click_screen, get_screen_info

# Get screen info
info = get_screen_info()
print(f"Screen: {info.width}x{info.height}, Server: {info.display_server}")

# Take screenshot
result = take_screenshot()
print(f"Screenshot saved to: {result.file_path}")

# Click at center of screen
click_result = click_screen(x=info.width//2, y=info.height//2)
print(f"Click success: {click_result.success}")
```

## Usage Examples

### Example 1: Opening an Application

```
User: "Take a screenshot and then click on the Firefox icon"

LLM:
1. Calls take_screenshot() to see the desktop
2. Analyzes image to locate Firefox icon at coordinates (x=150, y=50)
3. Calls click_screen(x=150, y=50) to launch Firefox
4. Calls take_screenshot() to verify Firefox opened
```

### Example 2: Filling a Form

```
User: "Open the login form and enter my credentials"

LLM:
1. Calls take_screenshot() to see current state
2. Identifies username field at (400, 300)
3. Calls click_screen(x=400, y=300) to focus field
4. Uses keyboard input tools to type username
5. Identifies password field and repeats
6. Clicks submit button
```

### Example 3: Monitoring Application

```
User: "Take screenshots every 30 seconds and tell me when the download completes"

LLM:
1. Periodically calls take_screenshot()
2. Analyzes each screenshot for download progress
3. Reports when "Download Complete" appears
```

## Security Considerations

⚠️ **Important Security Notes:**

1. **Full Desktop Access**: This server gives the LLM complete control over your mouse and ability to see your screen
2. **Sensitive Information**: Screenshots may capture passwords, personal data, or confidential information
3. **Unintended Actions**: Automated clicks could trigger unintended actions (closing windows, deleting files, etc.)

**Recommendations:**
- Only use with trusted LLM clients
- Review screenshot output paths to ensure sensitive data isn't leaked
- Consider running in a sandboxed or VM environment for testing
- Add confirmation prompts for destructive actions in your LLM client configuration

## Troubleshooting

### Clicks Landing in Wrong Position

**Symptoms:**
- Mouse clicks don't hit the intended target
- Clicks are offset from where they should be
- Coordinates from screenshot analysis don't work

**Diagnosis:**
```python
# Check for display scaling
from server import get_display_diagnostics
diag = get_display_diagnostics()
print(diag.recommendation)
```

**Solutions:**

1. **Use the diagnostic tool:**
   ```bash
   # The tool will tell you the exact scaling factor and how to adjust
   ```

2. **Take a grid screenshot:**
   ```python
   from server import screenshot_with_grid
   screenshot_with_grid(grid_size=50)
   # Open the screenshot to see logical coordinates overlaid
   ```

3. **Apply scaling correction:**
   ```python
   # If scaling_factor is 2.0 and you see something at (1000, 500) in screenshot
   result = take_screenshot()
   scaling = result.scaling_factor

   # Divide by scaling factor before clicking
   click_screen(x=int(1000/scaling), y=int(500/scaling))
   ```

4. **Check display settings:**
   ```bash
   # Verify your display scaling in GNOME Settings
   gnome-control-center display

   # Or check via xrandr
   xrandr --current
   ```

### PyAutoGUI Import Error

```bash
ImportError: No module named 'pyautogui'
```

**Solution**: Activate virtual environment and install dependencies:
```bash
source .venv/bin/activate
pip install pyautogui pillow
```

### X11 Library Missing

```bash
ImportError: No module named 'Xlib'
```

**Solution**: Install system dependencies:
```bash
sudo apt install python3-xlib
```

### Screenshot Tool Missing

```bash
scrot: command not found
```

**Solution**: Install scrot:
```bash
sudo apt install scrot
```

### Wayland Warning

If you're on Wayland instead of X11, PyAutoGUI may not work properly. Check with:
```bash
echo $XDG_SESSION_TYPE
```

If it shows "wayland", you may need to:
1. Switch to X11 session (logout, select "GNOME on Xorg" at login screen)
2. Or use alternative libraries designed for Wayland

### Permission Denied Errors

If clicks or screenshots fail due to permissions:
```bash
# Ensure your user has access to X11 display
xhost +local:
```

## Performance Notes

- **Screenshot Latency**: ~50-100ms per screenshot on typical hardware
- **Click Latency**: ~10-20ms per click
- **File Sizes**: PNG screenshots are typically 500KB-2MB depending on screen resolution
- **Optional Speed-Up**: Install `mss` to use the faster capture backend; the server automatically falls back to PyAutoGUI if it's absent

## Contributing

Suggestions for improvements:
- Add keyboard input tools
- Add screen recording capability
- Support for multi-monitor setups
- Add OCR for text extraction from screenshots
- Add image comparison tools

## License

MIT License - Feel free to modify and distribute

## Acknowledgments

- Built with [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- Uses [PyAutoGUI](https://github.com/asweigart/pyautogui) for desktop control
- Inspired by browser automation tools like Playwright and Selenium

## Sources

- [PyAutoGUI Screenshot Documentation](https://pyautogui.readthedocs.io/en/latest/screenshot.html)
- [PyAutoGUI PyPI](https://pypi.org/project/PyAutoGUI/)
- [pyscreenshot GitHub](https://github.com/ponty/pyscreenshot)
- [PyScreeze GitHub](https://github.com/asweigart/pyscreeze)
