#!/usr/bin/env python3
"""
Ubuntu Desktop Control MCP Server

Provides tools for LLMs to control Ubuntu desktop via screenshots and mouse clicks.
Designed for X11-based GNOME desktop environments.

Requirements:
- Python 3.9+
- X11 display server
- System packages: python3-xlib, scrot
"""

import os
import shutil
import textwrap
from datetime import datetime
from typing import Dict, List, Optional, Tuple


# pyautogui tries to connect to the display at import time. On headless systems
# or when permissions are restricted, that import can raise before the MCP
# server finishes initializing. We lazily import it inside the tools instead so
# the server can start and report a clear error to the caller.
_pyautogui = None
_pyautogui_error: Optional[str] = None


def _get_pyautogui():
    """Load pyautogui lazily and capture any import/display errors."""
    global _pyautogui, _pyautogui_error

    if _pyautogui or _pyautogui_error:
        return _pyautogui

    try:
        import pyautogui as _pyautogui_module

        _pyautogui = _pyautogui_module
        return _pyautogui
    except Exception as exc:  # noqa: BLE001 - surface any startup issue
        _pyautogui_error = (
            "PyAutoGUI unavailable. Ensure an X11 display is accessible: "
            f"{exc}"
        )
        return None

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field


# Initialize FastMCP server
mcp = FastMCP("ubuntu-desktop-control")


def _safe_display_server() -> str:
    """Return the display server name with a sane default."""
    return os.environ.get("XDG_SESSION_TYPE", "unknown").lower()


# Non-fatal warnings about the runtime environment
def _collect_env_warnings() -> List[str]:
    """Collect non-fatal environment warnings to return with results."""
    warnings: List[str] = []
    display_server = _safe_display_server()
    if display_server != "x11":
        warnings.append(
            f"Display server is '{display_server}'. PyAutoGUI works best on X11; Wayland may block screenshots/clicks."
        )

    if not shutil.which("gnome-screenshot") and not shutil.which("scrot"):
        warnings.append(
            "Neither gnome-screenshot nor scrot found; PyAutoGUI may fail to capture screenshots."
        )

    return warnings


def _prompt_text(template: str) -> str:
    """Dedent and strip prompt template text for registration."""
    return textwrap.dedent(template).strip()


# Cache for scaling factor detection (factor, logical size, actual size)
_scaling_factor_cache: Optional[Tuple[float, Tuple[int, int], Tuple[int, int]]] = None


def _detect_scaling_factor(
    pyautogui_module,
    logical_size: Optional[Tuple[int, int]] = None,
    actual_size: Optional[Tuple[int, int]] = None,
    force_refresh: bool = False,
) -> Tuple[float, Optional[str]]:
    """
    Detect display scaling factor by comparing logical vs physical screenshot size.

    Returns a tuple of (factor, warning). Warning is None when no issues.
    """
    global _scaling_factor_cache

    if _scaling_factor_cache and not force_refresh and logical_size is None and actual_size is None:
        return _scaling_factor_cache[0], None

    try:
        logical_w, logical_h = logical_size or pyautogui_module.size()

        # Take a quick screenshot if caller didn't provide one
        if actual_size is None:
            actual_w, actual_h = pyautogui_module.screenshot().size
        else:
            actual_w, actual_h = actual_size

        if logical_w <= 0 or logical_h <= 0:
            return 1.0, "Logical screen size reported as zero; assuming 1.0x scaling"

        factor_w = actual_w / logical_w
        factor_h = actual_h / logical_h
        factor = round((factor_w + factor_h) / 2.0, 4)

        # Cache result with sizes to avoid repeated screenshots
        _scaling_factor_cache = (factor, (logical_w, logical_h), (actual_w, actual_h))

        warning = None
        if abs(factor - 1.0) > 0.01:
            warning = (
                f"Display scaling detected ({factor:.2f}x). Logical: "
                f"{logical_w}x{logical_h}, Screenshot: {actual_w}x{actual_h}."
            )

        return factor, warning
    except Exception as exc:  # noqa: BLE001 - propagate as warning only
        return 1.0, f"Scaling detection failed; assuming 1.0x: {exc}"


def _get_screenshot_with_backend(pyautogui_module):
    """
    Capture a screenshot using mss if available (faster), else fall back to PyAutoGUI.

    Returns (image, width, height, warning)
    """
    try:
        import mss  # type: ignore
        from PIL import Image

        with mss.mss() as sct:
            monitor = sct.monitors[0]
            raw = sct.grab(monitor)
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            return img, raw.width, raw.height, None
    except Exception as exc:  # noqa: BLE001
        warning = None
        if "mss" in str(exc).lower():
            warning = f"mss capture failed, using PyAutoGUI screenshot: {exc}"

    image = pyautogui_module.screenshot()
    width, height = image.size
    return image, width, height, warning


class ScreenshotResult(BaseModel):
    """Result of a screenshot operation"""
    success: bool
    file_path: Optional[str] = Field(None, description="Absolute path to screenshot file")
    width: Optional[int] = Field(None, description="Screen width in logical pixels (reported by OS)")
    height: Optional[int] = Field(None, description="Screen height in logical pixels (reported by OS)")
    actual_width: Optional[int] = Field(None, description="Actual screenshot width in physical pixels")
    actual_height: Optional[int] = Field(None, description="Actual screenshot height in physical pixels")
    scaling_factor: Optional[float] = Field(None, description="Detected display scaling factor (1.0 = no scaling)")
    scaling_warning: Optional[str] = Field(None, description="Warning if scaling mismatch detected")
    warnings: Optional[List[str]] = Field(None, description="Non-fatal warnings about environment or scaling")
    error: Optional[str] = Field(None, description="Error message if operation failed")


class MouseClickResult(BaseModel):
    """Result of a mouse click operation"""
    success: bool
    x: int = Field(description="X coordinate where click was performed (logical pixels)")
    y: int = Field(description="Y coordinate where click was performed (logical pixels)")
    button: str = Field(description="Mouse button that was clicked")
    clicks: int = Field(description="Number of clicks performed")
    applied_scaling: Optional[float] = Field(None, description="Scaling factor auto-applied to incoming coordinates")
    scaling_warning: Optional[str] = Field(None, description="Warning if display scaling may affect accuracy")
    warnings: Optional[List[str]] = Field(None, description="Non-fatal warnings about environment or scaling")
    error: Optional[str] = Field(None, description="Error message if operation failed")


class ScreenInfo(BaseModel):
    """Information about the screen/display"""
    success: bool
    width: Optional[int] = Field(None, description="Screen width in pixels")
    height: Optional[int] = Field(None, description="Screen height in pixels")
    display_server: str = Field(description="Display server type (X11 or Wayland)")
    scaling_factor: Optional[float] = Field(None, description="Detected display scaling factor (1.0 = no scaling)")
    warnings: Optional[List[str]] = Field(None, description="Non-fatal warnings about environment or scaling")
    error: Optional[str] = Field(None, description="Error message if operation failed")


class DiagnosticInfo(BaseModel):
    """Detailed diagnostic information for troubleshooting coordinate issues"""
    success: bool
    logical_width: Optional[int] = Field(None, description="Screen width in logical pixels (what PyAutoGUI reports)")
    logical_height: Optional[int] = Field(None, description="Screen height in logical pixels (what PyAutoGUI reports)")
    actual_screenshot_width: Optional[int] = Field(None, description="Actual screenshot width in physical pixels")
    actual_screenshot_height: Optional[int] = Field(None, description="Actual screenshot height in physical pixels")
    scaling_factor: Optional[float] = Field(None, description="Detected scaling factor (actual/logical)")
    has_scaling_mismatch: bool = Field(description="True if scaling != 1.0")
    display_server: str = Field(description="Display server type (x11, wayland, unknown)")
    recommendation: Optional[str] = Field(None, description="Recommendation for fixing coordinate issues")
    warnings: Optional[List[str]] = Field(None, description="Non-fatal warnings about environment or scaling")
    error: Optional[str] = Field(None, description="Error message if operation failed")


class QuadrantScreenshotResult(BaseModel):
    """Result of a quadrant screenshot operation"""
    success: bool
    full_screenshot_path: Optional[str] = Field(None, description="Path to full screenshot")
    top_left_path: Optional[str] = Field(None, description="Path to top-left quadrant (x: 0 to mid_x, y: 0 to mid_y)")
    top_right_path: Optional[str] = Field(None, description="Path to top-right quadrant (x: mid_x to max_x, y: 0 to mid_y)")
    bottom_left_path: Optional[str] = Field(None, description="Path to bottom-left quadrant (x: 0 to mid_x, y: mid_y to max_y)")
    bottom_right_path: Optional[str] = Field(None, description="Path to bottom-right quadrant (x: mid_x to max_x, y: mid_y to max_y)")
    scaling_factor: Optional[float] = Field(None, description="Display scaling factor")
    quadrant_info: Optional[str] = Field(None, description="Explanation of quadrant coordinate system")
    warnings: Optional[List[str]] = Field(None, description="Non-fatal warnings about environment or scaling")
    error: Optional[str] = Field(None, description="Error message if operation failed")


class CoordinateConversionResult(BaseModel):
    """Result of converting screenshot coordinates to logical click coordinates"""
    success: bool
    screenshot_x: int = Field(description="X coordinate in screenshot pixels")
    screenshot_y: int = Field(description="Y coordinate in screenshot pixels")
    logical_x: Optional[int] = Field(None, description="Converted X coordinate for click_screen")
    logical_y: Optional[int] = Field(None, description="Converted Y coordinate for click_screen")
    scaling_factor: Optional[float] = Field(None, description="Scaling factor used for conversion")
    warnings: Optional[List[str]] = Field(None, description="Non-fatal warnings about environment or scaling")
    error: Optional[str] = Field(None, description="Error message if conversion failed")


class PromptTemplateSummary(BaseModel):
    """Metadata for an MCP prompt template."""
    name: str = Field(description="Prompt identifier")
    title: str = Field(description="Prompt title")
    description: str = Field(description="Short description of what the prompt is for")


class PromptTemplateResult(PromptTemplateSummary):
    """Rendered MCP prompt text for clients without prompt support."""
    prompt: str = Field(description="Rendered prompt text")


class PromptTemplatesResult(BaseModel):
    """Collection of available prompt templates exposed as tools."""
    templates: List[PromptTemplateSummary] = Field(
        description="Available prompt templates"
    )


@mcp.tool()
def take_screenshot(
    output_path: Optional[str] = None,
    region: Optional[str] = None
) -> ScreenshotResult:
    """
    Take a screenshot of the Ubuntu desktop and save it to a file.

    This tool captures the current state of the desktop display, allowing the LLM
    to "see" what's on screen. The screenshot is saved as a PNG file.

    Args:
        output_path: Optional custom path for the screenshot file. If not provided,
                    a temporary file will be created in /tmp with a timestamped name.
                    Example: "/tmp/my_screenshot.png"
        region: Optional region to capture in format "x,y,width,height".
                Example: "100,100,800,600" captures 800x600 area starting at (100,100).
                If not provided, captures the entire screen.

    Returns:
        ScreenshotResult with file path, dimensions, and success status

    Examples:
        - take_screenshot() - Captures entire screen to temp file
        - take_screenshot(output_path="/tmp/desktop.png") - Saves to specific location
        - take_screenshot(region="0,0,1920,1080") - Captures specific region
    """
    pyautogui = _get_pyautogui()
    if pyautogui is None:
        return ScreenshotResult(success=False, error=_pyautogui_error)

    warnings = _collect_env_warnings()
    scaling_warning = None

    try:
        # Get logical screen size
        screen_width, screen_height = pyautogui.size()

        # Generate output path if not provided
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"/tmp/screenshot_{timestamp}.png"

        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        # Parse region if provided
        screenshot_region = None
        if region:
            try:
                x, y, width, height = map(int, region.split(','))
                if width <= 0 or height <= 0:
                    return ScreenshotResult(
                        success=False,
                        error="Region width/height must be positive"
                    )
                screenshot_region = (x, y, width, height)
            except (ValueError, TypeError) as e:
                return ScreenshotResult(
                    success=False,
                    error=f"Invalid region format. Use 'x,y,width,height': {str(e)}"
                )

        # Take screenshot using the fastest available backend
        if screenshot_region:
            screenshot = pyautogui.screenshot(region=screenshot_region)
            actual_width, actual_height = screenshot.size
            backend_warning = None
        else:
            screenshot, actual_width, actual_height, backend_warning = _get_screenshot_with_backend(pyautogui)
            if backend_warning:
                warnings.append(backend_warning)

        # Detect scaling factor using known sizes
        scaling_factor, scaling_warning = _detect_scaling_factor(
            pyautogui,
            logical_size=(screen_width, screen_height),
            actual_size=(actual_width, actual_height),
        )

        # Save screenshot
        screenshot.save(output_path)

        return ScreenshotResult(
            success=True,
            file_path=output_path,
            width=screen_width,
            height=screen_height,
            actual_width=actual_width,
            actual_height=actual_height,
            scaling_factor=scaling_factor,
            scaling_warning=scaling_warning,
            warnings=warnings or None,
        )

    except Exception as e:  # noqa: BLE001
        warnings = warnings or None
        return ScreenshotResult(
            success=False,
            error=f"Screenshot failed: {str(e)}",
            warnings=warnings,
        )


@mcp.tool()
def click_screen(
    x: int,
    y: int,
    button: str = "left",
    clicks: int = 1,
    interval: float = 0.0,
    auto_scale: bool = False,
) -> MouseClickResult:
    """
    Send mouse click at specified screen coordinates.

    This tool allows the LLM to interact with the desktop by clicking at specific
    pixel locations. Use in combination with take_screenshot to identify where to click.

    Args:
        x: X coordinate in pixels (0 is left edge of screen)
        y: Y coordinate in pixels (0 is top edge of screen)
        button: Mouse button to click. Options: "left", "right", "middle"
        clicks: Number of clicks to perform (1 for single click, 2 for double click)
        interval: Seconds to wait between clicks if clicks > 1
        auto_scale: If True, divides incoming coordinates by detected scaling factor
                    so callers can pass screenshot coordinates measured on screenshots.

    Returns:
        MouseClickResult with success status and click details

    Examples:
        - click_screen(x=500, y=300) - Single left click at (500, 300)
        - click_screen(x=500, y=300, button="right") - Right click
        - click_screen(x=500, y=300, clicks=2, interval=0.1) - Double click
        - click_screen(x=1500, y=900, auto_scale=True) - Use screenshot coords directly

    Safety Notes:
        - Coordinates outside screen bounds will fail
        - Consider adding delay before critical clicks to allow UI to update
        - Use get_screen_info() to verify screen dimensions first
    """
    pyautogui = _get_pyautogui()
    if pyautogui is None:
        return MouseClickResult(
            success=False,
            x=x,
            y=y,
            button=button,
            clicks=clicks,
            error=_pyautogui_error,
        )

    warnings = _collect_env_warnings()

    try:
        # Validate button type
        valid_buttons = ["left", "right", "middle"]
        if button not in valid_buttons:
            return MouseClickResult(
                success=False,
                x=x,
                y=y,
                button=button,
                clicks=clicks,
                error=f"Invalid button '{button}'. Must be one of: {valid_buttons}"
            )

        # Validate coordinates are within screen bounds
        screen_width, screen_height = pyautogui.size()
        if x < 0 or y < 0:
            return MouseClickResult(
                success=False,
                x=x,
                y=y,
                button=button,
                clicks=clicks,
                error=f"Coordinates ({x}, {y}) are negative; provide logical screen coordinates",
                warnings=warnings or None,
            )

        scaling_factor, scaling_warning = _detect_scaling_factor(pyautogui)

        # Optional auto-scaling to allow screenshot coordinates directly
        applied_scaling = None
        if auto_scale and scaling_factor not in (None, 0):
            applied_scaling = scaling_factor
            x = int(x / scaling_factor)
            y = int(y / scaling_factor)

        # Validate against bounds after scaling
        if x >= screen_width or y >= screen_height:
            return MouseClickResult(
                success=False,
                x=x,
                y=y,
                button=button,
                clicks=clicks,
                error=f"Coordinates ({x}, {y}) out of screen bounds (0-{screen_width}, 0-{screen_height})",
                scaling_warning=scaling_warning,
                warnings=warnings or None,
            )

        # Perform the click
        pyautogui.click(x=x, y=y, clicks=clicks, interval=interval, button=button)

        return MouseClickResult(
            success=True,
            x=x,
            y=y,
            button=button,
            clicks=clicks,
            applied_scaling=applied_scaling,
            scaling_warning=scaling_warning,
            warnings=warnings or None,
        )

    except Exception as e:  # noqa: BLE001
        return MouseClickResult(
            success=False,
            x=x,
            y=y,
            button=button,
            clicks=clicks,
            error=f"Click failed: {str(e)}",
            scaling_warning=scaling_warning,
            warnings=warnings or None,
        )


@mcp.tool()
def get_screen_info() -> ScreenInfo:
    """
    Get information about the screen/display.

    Returns screen dimensions and display server type. Use this before taking
    screenshots or clicking to understand the coordinate system.

    Returns:
        ScreenInfo with width, height, and display server type

    Example:
        - get_screen_info() - Returns screen dimensions and X11/Wayland info
    """
    pyautogui = _get_pyautogui()
    if pyautogui is None:
        return ScreenInfo(
            success=False,
            display_server=_safe_display_server(),
            error=_pyautogui_error or "PyAutoGUI not installed",
        )

    warnings = _collect_env_warnings()

    try:
        screen_width, screen_height = pyautogui.size()
        scaling_factor, scaling_warning = _detect_scaling_factor(pyautogui)
        if scaling_warning:
            warnings.append(scaling_warning)

        return ScreenInfo(
            success=True,
            width=screen_width,
            height=screen_height,
            display_server=_safe_display_server(),
            scaling_factor=scaling_factor,
            warnings=warnings or None,
        )
    except Exception as e:  # noqa: BLE001
        return ScreenInfo(
            success=False,
            display_server=_safe_display_server(),
            error=f"Failed to get screen info: {str(e)}",
            warnings=warnings or None,
        )


@mcp.tool()
def move_mouse(x: int, y: int, duration: float = 0.0) -> MouseClickResult:
    """
    Move mouse cursor to specified screen coordinates without clicking.

    This tool moves the mouse pointer to a specific location, useful for
    hovering over UI elements or positioning before a click.

    Args:
        x: X coordinate in pixels (0 is left edge of screen)
        y: Y coordinate in pixels (0 is top edge of screen)
        duration: Time in seconds to animate the movement (0 for instant)

    Returns:
        MouseClickResult with success status (clicks will be 0)

    Examples:
        - move_mouse(x=500, y=300) - Instantly move to (500, 300)
        - move_mouse(x=500, y=300, duration=0.5) - Smoothly move over 0.5 seconds
    """
    pyautogui = _get_pyautogui()
    if pyautogui is None:
        return MouseClickResult(
            success=False,
            x=x,
            y=y,
            button="none",
            clicks=0,
            error=_pyautogui_error,
        )

    warnings = _collect_env_warnings()

    try:
        # Validate coordinates
        screen_width, screen_height = pyautogui.size()
        if x < 0 or x >= screen_width or y < 0 or y >= screen_height:
            return MouseClickResult(
                success=False,
                x=x,
                y=y,
                button="none",
                clicks=0,
                error=f"Coordinates ({x}, {y}) out of bounds (0-{screen_width}, 0-{screen_height})",
                warnings=warnings or None,
            )

        # Move mouse
        pyautogui.moveTo(x, y, duration=duration)

        return MouseClickResult(
            success=True,
            x=x,
            y=y,
            button="none",
            clicks=0,
            warnings=warnings or None,
        )

    except Exception as e:  # noqa: BLE001
        return MouseClickResult(
            success=False,
            x=x,
            y=y,
            button="none",
            clicks=0,
            error=f"Mouse move failed: {str(e)}",
            warnings=warnings or None,
        )


@mcp.tool()
def type_text(text: str, interval: float = 0.0) -> MouseClickResult:
    """
    Type text using the keyboard.

    This tool types the specified text string. It can be used to enter data into
    forms, search bars, or terminal windows.

    Args:
        text: The string of text to type.
        interval: Seconds to wait between each key press (default 0.0).

    Returns:
        MouseClickResult with success status (reused model for simplicity)

    Examples:
        - type_text(text="Hello World") - Types "Hello World" instantly
        - type_text(text="ls -la", interval=0.1) - Types slowly
    """
    pyautogui = _get_pyautogui()
    if pyautogui is None:
        return MouseClickResult(
            success=False,
            x=0,
            y=0,
            button="none",
            clicks=0,
            error=_pyautogui_error,
        )

    warnings = _collect_env_warnings()

    try:
        pyautogui.write(text, interval=interval)
        return MouseClickResult(
            success=True,
            x=0,
            y=0,
            button="none",
            clicks=0,
            warnings=warnings or None,
        )
    except Exception as e:  # noqa: BLE001
        return MouseClickResult(
            success=False,
            x=0,
            y=0,
            button="none",
            clicks=0,
            error=f"Type text failed: {str(e)}",
            warnings=warnings or None,
        )


@mcp.tool()
def press_key(key: str) -> MouseClickResult:
    """
    Press a specific key on the keyboard.

    This tool presses a single key. Useful for navigation (arrows, enter, esc)
    or shortcuts.

    Args:
        key: The name of the key to press. Examples: 'enter', 'esc', 'left', 'f1', 'a'.
             See pyautogui documentation for full list of valid key names.

    Returns:
        MouseClickResult with success status

    Examples:
        - press_key(key="enter")
        - press_key(key="esc")
    """
    pyautogui = _get_pyautogui()
    if pyautogui is None:
        return MouseClickResult(
            success=False,
            x=0,
            y=0,
            button="none",
            clicks=0,
            error=_pyautogui_error,
        )

    warnings = _collect_env_warnings()

    try:
        pyautogui.press(key)
        return MouseClickResult(
            success=True,
            x=0,
            y=0,
            button="none",
            clicks=0,
            warnings=warnings or None,
        )
    except Exception as e:  # noqa: BLE001
        return MouseClickResult(
            success=False,
            x=0,
            y=0,
            button="none",
            clicks=0,
            error=f"Press key failed: {str(e)}",
            warnings=warnings or None,
        )


@mcp.tool()
def get_display_diagnostics() -> DiagnosticInfo:
    """
    Get detailed diagnostic information about display scaling and coordinate systems.

    This tool helps troubleshoot coordinate mismatch issues by comparing logical
    screen dimensions (what the OS reports) with actual screenshot dimensions.

    Use this tool when:
    - Clicks are landing in the wrong position
    - Screenshot coordinates don't match screen coordinates
    - You suspect display scaling is causing issues

    Returns:
        DiagnosticInfo with scaling factor, dimensions, and recommendations
    """
    pyautogui = _get_pyautogui()
    if pyautogui is None:
        return DiagnosticInfo(
            success=False,
            has_scaling_mismatch=False,
            display_server=_safe_display_server(),
            error=_pyautogui_error or "PyAutoGUI not installed",
        )

    warnings = _collect_env_warnings()

    try:
        # Get logical screen size
        logical_width, logical_height = pyautogui.size()

        # Take test screenshot to get actual dimensions (fastest backend)
        screenshot, actual_width, actual_height, backend_warning = _get_screenshot_with_backend(pyautogui)
        if backend_warning:
            warnings.append(backend_warning)

        # Detect scaling factor
        scaling_factor, scaling_warning = _detect_scaling_factor(
            pyautogui,
            logical_size=(logical_width, logical_height),
            actual_size=(actual_width, actual_height),
            force_refresh=True,
        )
        has_scaling_mismatch = abs(scaling_factor - 1.0) > 0.01 if scaling_factor else False

        display_server = _safe_display_server()

        if scaling_warning:
            warnings.append(scaling_warning)

        # Generate recommendation
        if has_scaling_mismatch:
            recommendation = (
                f"Display scaling is active ({scaling_factor:.2f}x). "
                f"Divide screenshot coordinates by {scaling_factor:.2f} before clicking, "
                f"or set auto_scale=True in click_screen. "
                f"For example: screenshot (1000, 500) -> click ({int(1000/scaling_factor)}, {int(500/scaling_factor)}). "
                f"Alternatively, use screenshot_with_grid to visualize logical coordinates."
            )
        else:
            recommendation = (
                "No display scaling detected. Screenshot coordinates should match "
                "screen coordinates directly."
            )

        return DiagnosticInfo(
            success=True,
            logical_width=logical_width,
            logical_height=logical_height,
            actual_screenshot_width=actual_width,
            actual_screenshot_height=actual_height,
            scaling_factor=scaling_factor,
            has_scaling_mismatch=has_scaling_mismatch,
            display_server=display_server,
            recommendation=recommendation,
            warnings=warnings or None,
        )

    except Exception as e:  # noqa: BLE001
        return DiagnosticInfo(
            success=False,
            has_scaling_mismatch=False,
            display_server=_safe_display_server(),
            error=f"Failed to get diagnostics: {str(e)}",
            warnings=warnings or None,
        )


@mcp.tool()
def convert_screenshot_coordinates(
    screenshot_x: int,
    screenshot_y: int,
) -> CoordinateConversionResult:
    """
    Convert screenshot pixel coordinates to logical coordinates suitable for click_screen().

    Use this when you have coordinates measured on the saved screenshot and want the exact
    logical coordinates to click (accounting for display scaling).
    """
    pyautogui = _get_pyautogui()
    if pyautogui is None:
        return CoordinateConversionResult(
            success=False,
            screenshot_x=screenshot_x,
            screenshot_y=screenshot_y,
            error=_pyautogui_error or "PyAutoGUI not installed",
        )

    warnings = _collect_env_warnings()

    try:
        logical_w, logical_h = pyautogui.size()
        screenshot_img, actual_w, actual_h, backend_warning = _get_screenshot_with_backend(pyautogui)
        if backend_warning:
            warnings.append(backend_warning)
        # Avoid unused variable warning
        _ = screenshot_img

        scaling_factor, scaling_warning = _detect_scaling_factor(
            pyautogui,
            logical_size=(logical_w, logical_h),
            actual_size=(actual_w, actual_h),
        )
        if scaling_warning:
            warnings.append(scaling_warning)

        if scaling_factor in (None, 0):
            return CoordinateConversionResult(
                success=False,
                screenshot_x=screenshot_x,
                screenshot_y=screenshot_y,
                error="Could not detect scaling factor",
                warnings=warnings or None,
            )

        logical_x = int(screenshot_x / scaling_factor)
        logical_y = int(screenshot_y / scaling_factor)

        return CoordinateConversionResult(
            success=True,
            screenshot_x=screenshot_x,
            screenshot_y=screenshot_y,
            logical_x=logical_x,
            logical_y=logical_y,
            scaling_factor=scaling_factor,
            warnings=warnings or None,
        )

    except Exception as exc:  # noqa: BLE001
        return CoordinateConversionResult(
            success=False,
            screenshot_x=screenshot_x,
            screenshot_y=screenshot_y,
            error=f"Conversion failed: {exc}",
            warnings=warnings or None,
        )


@mcp.tool()
def screenshot_with_grid(
    output_path: Optional[str] = None,
    grid_size: int = 100
) -> ScreenshotResult:
    """
    Take a screenshot with a coordinate grid overlay for debugging positioning issues.

    This tool captures the screen and overlays a semi-transparent red grid with coordinate
    labels showing LOGICAL pixel positions (the coordinates to use with click_screen).

    IMPORTANT: The grid labels show the coordinates you should use directly with click_screen().
    If scaling is active, the labels automatically account for it - just read the numbers
    and use them as-is in click_screen(x=<value>, y=<value>).

    Grid interpretation:
    - Red grid lines: Semi-transparent, won't heavily obscure content
    - "x=N" labels: Appear at top of vertical lines - use this X coordinate for clicking
    - "y=N" labels: Appear at left of horizontal lines - use this Y coordinate for clicking
    - Grid spacing: `grid_size` pixels (minimum 10, default 100)
    - All labels are clean multiples of grid size for easy reading

    If display scaling is active (e.g. 2x HiDPI), the grid automatically shows logical
    coordinates. For example, if you see "x=500" on the grid, use click_screen(x=500)
    regardless of the actual screenshot pixel position.

    Args:
        output_path: Optional custom path for screenshot file
        grid_size: Distance between grid lines in pixels (minimum 10, default 100)

    Returns:
        ScreenshotResult with annotated screenshot showing coordinate grid
        - scaling_factor: Shows if display scaling is active
        - scaling_warning: Explains the coordinate system if scaling detected

    Examples:
        - screenshot_with_grid() - Grid at x=0,100,200... y=0,100,200...
        - screenshot_with_grid(output_path="/tmp/debug.png") - Save to specific location
    """
    pyautogui = _get_pyautogui()
    if pyautogui is None:
        return ScreenshotResult(success=False, error=_pyautogui_error)

    warnings = _collect_env_warnings()

    try:
        from PIL import ImageDraw

        # Get screen size
        screen_width, screen_height = pyautogui.size()

        # Take screenshot (fastest backend)
        screenshot, actual_width, actual_height, backend_warning = _get_screenshot_with_backend(pyautogui)
        if backend_warning:
            warnings.append(backend_warning)

        # Detect scaling
        scaling_factor, scaling_warning = _detect_scaling_factor(
            pyautogui,
            logical_size=(screen_width, screen_height),
            actual_size=(actual_width, actual_height),
        )
        if scaling_warning:
            warnings.append(scaling_warning)

        # Create a drawing context
        draw = ImageDraw.Draw(screenshot)

        # Honor grid_size, clamp to sensible minimum
        increment = max(10, grid_size)

        # Calculate logical screen dimensions
        logical_width = int(actual_width / scaling_factor) if scaling_factor else actual_width
        logical_height = int(actual_height / scaling_factor) if scaling_factor else actual_height

        # Draw vertical grid lines at clean multiples (x=0, increment, 2*increment, ...)
        x_positions = []
        logical_x = 0
        while logical_x <= logical_width:
            x = int(logical_x * scaling_factor) if scaling_factor else logical_x
            x_positions.append((x, logical_x))
            logical_x += increment

        # Always add the right edge
        if x_positions and x_positions[-1][0] != actual_width - 1:
            x_positions.append((actual_width - 1, logical_width - 1))

        for x, logical_x in x_positions:
            draw.line([(x, 0), (x, actual_height - 1)], fill=(255, 0, 0, 64), width=1)
            text = f"x={logical_x}"
            text_bbox = draw.textbbox((x + 2, 2), text)
            draw.rectangle(text_bbox, fill=(0, 0, 0, 120))
            draw.text((x + 2, 2), text, fill=(255, 120, 120))

        # Draw horizontal grid lines at clean multiples (y=0, increment, 2*increment, ...)
        y_positions = []
        logical_y = 0
        while logical_y <= logical_height:
            y = int(logical_y * scaling_factor) if scaling_factor else logical_y
            y_positions.append((y, logical_y))
            logical_y += increment

        # Always add the bottom edge
        if y_positions and y_positions[-1][0] != actual_height - 1:
            y_positions.append((actual_height - 1, logical_height - 1))

        for y, logical_y in y_positions:
            draw.line([(0, y), (actual_width - 1, y)], fill=(255, 0, 0, 64), width=1)
            text = f"y={logical_y}"
            text_bbox = draw.textbbox((2, y + 2), text)
            draw.rectangle(text_bbox, fill=(0, 0, 0, 120))
            draw.text((2, y + 2), text, fill=(255, 120, 120))

        # Generate output path if not provided
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"/tmp/screenshot_grid_{timestamp}.png"

        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        # Save annotated screenshot
        screenshot.save(output_path)

        return ScreenshotResult(
            success=True,
            file_path=output_path,
            width=screen_width,
            height=screen_height,
            actual_width=actual_width,
            actual_height=actual_height,
            scaling_factor=scaling_factor,
            scaling_warning=scaling_warning,
            warnings=warnings or None,
        )

    except ImportError:
        return ScreenshotResult(
            success=False,
            error="PIL (Pillow) not available for drawing grid overlay",
            warnings=warnings or None,
        )
    except Exception as e:  # noqa: BLE001
        return ScreenshotResult(
            success=False,
            error=f"Screenshot with grid failed: {str(e)}",
            warnings=warnings or None,
        )


@mcp.tool()
def screenshot_quadrants(
    output_dir: Optional[str] = None,
    grid_size: int = 100
) -> QuadrantScreenshotResult:
    """
    Take a screenshot and split it into 4 quadrant images for better LLM analysis.

    This tool solves the problem of high-resolution displays being difficult for LLMs to
    analyze by splitting one large screenshot into 4 smaller, more detailed quadrant views.
    Each quadrant has a semi-transparent coordinate grid showing the FULL SCREEN coordinates,
    making it easy to identify click positions across the entire display.

    WHY USE THIS:
    - High-res displays (2560x1440+) are hard for vision models to analyze in detail
    - 4 smaller images provide better "pixel density" for OCR and icon recognition
    - Each quadrant maintains absolute screen coordinates for accurate clicking
    - Transparent grid overlays don't obscure content

    QUADRANT LAYOUT:
    ┌─────────────┬─────────────┐
    │  top_left   │  top_right  │
    │  (x: 0→mid) │  (x: mid→max│
    │  (y: 0→mid) │  (y: 0→mid) │
    ├─────────────┼─────────────┤
    │ bottom_left │bottom_right │
    │  (x: 0→mid) │  (x: mid→max│
    │  (y: mid→max│  (y: mid→max│
    └─────────────┴─────────────┘

    COORDINATE SYSTEM:
    All grid labels show FULL SCREEN logical coordinates. If you see "x=1500" in the
    top_right quadrant, use click_screen(x=1500) directly - no math needed!

    Args:
        output_dir: Directory to save quadrant images. Defaults to /tmp
        grid_size: Distance between grid lines in pixels (minimum 10, default 100)

    Returns:
        QuadrantScreenshotResult with paths to all 4 quadrant images plus full screenshot
        - Each quadrant image is 1/4 the resolution (easier for LLM vision)
        - Grid labels show absolute screen coordinates at your chosen increment
        - scaling_factor indicates if HiDPI scaling is active

    Examples:
        - screenshot_quadrants() - Save to /tmp with 100px grid
        - screenshot_quadrants(output_dir="/home/user/Desktop", grid_size=50) - Finer grid

    USAGE TIP: After calling this tool, analyze each quadrant image to find UI elements.
    The grid coordinates work directly with click_screen() - no conversion needed!
    """
    pyautogui = _get_pyautogui()
    if pyautogui is None:
        return QuadrantScreenshotResult(success=False, error=_pyautogui_error)

    warnings = _collect_env_warnings()

    try:
        from PIL import ImageDraw

        # Get screen info
        screen_width, screen_height = pyautogui.size()
        screenshot, actual_width, actual_height, backend_warning = _get_screenshot_with_backend(pyautogui)
        if backend_warning:
            warnings.append(backend_warning)

        scaling_factor, scaling_warning = _detect_scaling_factor(
            pyautogui,
            logical_size=(screen_width, screen_height),
            actual_size=(actual_width, actual_height),
        )
        if scaling_warning:
            warnings.append(scaling_warning)

        # Set output directory
        if output_dir is None:
            output_dir = "/tmp"

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Generate timestamp for unique filenames
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save full screenshot
        full_path = os.path.join(output_dir, f"screenshot_full_{timestamp}.png")
        screenshot.save(full_path)

        # Calculate midpoints
        mid_x_actual = actual_width // 2
        mid_y_actual = actual_height // 2
        mid_x_logical = screen_width // 2
        mid_y_logical = screen_height // 2

        # Define quadrants (in screenshot pixel coordinates)
        quadrants = {
            'top_left': (0, 0, mid_x_actual, mid_y_actual, 0, 0, mid_x_logical, mid_y_logical),
            'top_right': (mid_x_actual, 0, actual_width, mid_y_actual, mid_x_logical, 0, screen_width, mid_y_logical),
            'bottom_left': (0, mid_y_actual, mid_x_actual, actual_height, 0, mid_y_logical, mid_x_logical, screen_height),
            'bottom_right': (mid_x_actual, mid_y_actual, actual_width, actual_height, mid_x_logical, mid_y_logical, screen_width, screen_height)
        }

        quadrant_paths = {}

        increment = max(10, grid_size)

        # Process each quadrant
        for name, (x1, y1, x2, y2, log_x1, log_y1, log_x2, log_y2) in quadrants.items():
            quadrant_img = screenshot.crop((x1, y1, x2, y2))
            draw = ImageDraw.Draw(quadrant_img)

            quad_width, quad_height = quadrant_img.size

            # Vertical grid lines
            x_positions = []
            start_logical_x = (log_x1 // increment) * increment
            if start_logical_x < log_x1:
                start_logical_x += increment

            logical_x = start_logical_x
            while logical_x <= log_x2:
                actual_x_on_screen = int(logical_x * scaling_factor) if scaling_factor else logical_x
                x = actual_x_on_screen - x1
                if 0 <= x < quad_width:
                    x_positions.append((x, logical_x))
                logical_x += increment

            edge_x = quad_width - 1
            edge_logical_x = int((x1 + edge_x) / scaling_factor) if scaling_factor else (x1 + edge_x)
            if not x_positions or x_positions[-1][0] != edge_x:
                x_positions.append((edge_x, edge_logical_x))

            for x, logical_x in x_positions:
                draw.line([(x, 0), (x, quad_height - 1)], fill=(255, 0, 0, 50), width=1)
                text = f"x={logical_x}"
                text_bbox = draw.textbbox((x + 2, 2), text)
                draw.rectangle(text_bbox, fill=(0, 0, 0, 120))
                draw.text((x + 2, 2), text, fill=(255, 120, 120))

            # Horizontal grid lines
            y_positions = []
            start_logical_y = (log_y1 // increment) * increment
            if start_logical_y < log_y1:
                start_logical_y += increment

            logical_y = start_logical_y
            while logical_y <= log_y2:
                actual_y_on_screen = int(logical_y * scaling_factor) if scaling_factor else logical_y
                y = actual_y_on_screen - y1
                if 0 <= y < quad_height:
                    y_positions.append((y, logical_y))
                logical_y += increment

            edge_y = quad_height - 1
            edge_logical_y = int((y1 + edge_y) / scaling_factor) if scaling_factor else (y1 + edge_y)
            if not y_positions or y_positions[-1][0] != edge_y:
                y_positions.append((edge_y, edge_logical_y))

            for y, logical_y in y_positions:
                draw.line([(0, y), (quad_width - 1, y)], fill=(255, 0, 0, 50), width=1)
                text = f"y={logical_y}"
                text_bbox = draw.textbbox((2, y + 2), text)
                draw.rectangle(text_bbox, fill=(0, 0, 0, 120))
                draw.text((2, y + 2), text, fill=(255, 120, 120))

            quadrant_path = os.path.join(output_dir, f"screenshot_{name}_{timestamp}.png")
            quadrant_img.save(quadrant_path)
            quadrant_paths[name] = quadrant_path

        sf_str = f"{scaling_factor:.2f}" if scaling_factor is not None else "1.00"
        quadrant_info = (
            f"Screen split at logical coordinates: x={mid_x_logical}, y={mid_y_logical}. "
            f"Grid labels show FULL SCREEN coordinates - use values directly with click_screen(). "
            f"Scaling factor: {sf_str}x, grid every {increment}px."
        )

        return QuadrantScreenshotResult(
            success=True,
            full_screenshot_path=full_path,
            top_left_path=quadrant_paths['top_left'],
            top_right_path=quadrant_paths['top_right'],
            bottom_left_path=quadrant_paths['bottom_left'],
            bottom_right_path=quadrant_paths['bottom_right'],
            scaling_factor=scaling_factor,
            quadrant_info=quadrant_info,
            warnings=warnings or None,
        )

    except ImportError:
        return QuadrantScreenshotResult(
            success=False,
            error="PIL (Pillow) not available for image processing",
            warnings=warnings or None,
        )
    except Exception as e:  # noqa: BLE001
        return QuadrantScreenshotResult(
            success=False,
            error=f"Quadrant screenshot failed: {str(e)}",
            warnings=warnings or None,
        )


# MCP prompt templates


@mcp.prompt(
    name="baseline_display_check",
    title="Baseline display and scaling check",
    description="Collect display server, sizing, and scaling warnings before interacting with the desktop.",
)
def prompt_baseline_display_check(task_hint: Optional[str] = None) -> str:
    """Prompt template guiding baseline diagnostics."""
    target = task_hint or "the requested task"
    return _prompt_text(
        f"""
        Before working on {target}, call `get_screen_info` and `get_display_diagnostics`.
        Report display_server, logical size, scaling_factor, scaling_warning, and any environment warnings.
        Recommend whether to use `auto_scale` or a grid overlay (`screenshot_with_grid`) before clicking.
        """
    )


@mcp.prompt(
    name="capture_full_desktop",
    title="Capture full desktop screenshot",
    description="Capture a full-screen screenshot and summarize what is visible before acting.",
)
def prompt_capture_full_desktop(
    goal: str,
    output_path: Optional[str] = None,
) -> str:
    """Prompt template for full desktop capture."""
    path_hint = f"output_path={output_path}" if output_path else "the default output path"
    return _prompt_text(
        f"""
        Goal: {goal}. Call `take_screenshot` for the full screen (use {path_hint}).
        Return file_path, logical and actual sizes, scaling_factor, and any warnings.
        List 2-3 concise observations relevant to the goal and suggest a next step (grid overlay, quadrants, or a targeted click).
        """
    )


@mcp.prompt(
    name="capture_region_for_task",
    title="Capture region screenshot",
    description="Grab a focused region screenshot to inspect a specific UI area.",
)
def prompt_capture_region_for_task(
    region: str,
    goal: Optional[str] = None,
    output_path: Optional[str] = None,
) -> str:
    """Prompt template for region capture with validation guidance."""
    goal_text = goal or "this task"
    path_hint = f"output_path={output_path}" if output_path else "the default output path"
    return _prompt_text(
        f"""
        Goal: {goal_text}. Validate region '{region}' uses x,y,width,height with positive width/height;
        if invalid, fall back to full-screen capture and mention the fallback.
        Call `take_screenshot` with that region and {path_hint}.
        Return file_path, sizes, scaling_factor/warnings, and a short summary of what is visible in that region.
        """
    )


@mcp.prompt(
    name="grid_overlay_snapshot",
    title="Grid overlay screenshot for coordinates",
    description="Capture a grid-annotated screenshot to make click coordinates explicit.",
)
def prompt_grid_overlay_snapshot(
    goal: str,
    grid_size: Optional[int] = None,
    output_path: Optional[str] = None,
) -> str:
    """Prompt template for grid overlay capture."""
    grid_hint = f"grid_size={grid_size}" if grid_size is not None else "the default grid size"
    path_hint = f"output_path={output_path}" if output_path else "the default output path"
    return _prompt_text(
        f"""
        Goal: {goal}. Call `screenshot_with_grid` using {grid_hint} and {path_hint}.
        Return file_path, scaling_factor/warnings, and remind that grid labels are logical coordinates for `click_screen`.
        If the target is visible, list 1-3 candidate logical coordinates to click.
        """
    )


@mcp.prompt(
    name="quadrant_scan",
    title="Quadrant scan for high-resolution UIs",
    description="Split the screen into grid-labeled quadrants to inspect dense interfaces and plan clicks.",
)
def prompt_quadrant_scan(
    goal: str,
    grid_size: Optional[int] = None,
    output_dir: Optional[str] = None,
) -> str:
    """Prompt template for quadrant-based inspection."""
    grid_hint = f"grid_size={grid_size}" if grid_size is not None else "the default grid size"
    dir_hint = f"output_dir={output_dir}" if output_dir else "the default directory"
    return _prompt_text(
        f"""
        Goal: {goal}. Call `screenshot_quadrants` using {grid_hint} and {dir_hint}.
        Return full_screenshot_path plus quadrant paths, scaling_factor/warnings, and note that grid labels are full-screen logical coordinates.
        Point out which quadrant likely contains the target and propose exact logical coordinates to click or hover.
        """
    )


@mcp.prompt(
    name="convert_screenshot_coordinates",
    title="Convert screenshot pixels to logical click coords",
    description="Turn coordinates measured on a screenshot into logical positions for click_screen.",
)
def prompt_convert_screenshot_coordinates(
    screenshot_x: int,
    screenshot_y: int,
    note: Optional[str] = None,
) -> str:
    """Prompt template for converting screenshot coordinates."""
    target_note = note or "the target"
    return _prompt_text(
        f"""
        You measured a screenshot coordinate at ({screenshot_x}, {screenshot_y}) for {target_note}.
        Call `convert_screenshot_coordinates` and return logical_x/logical_y, scaling_factor, and warnings.
        Provide the exact `click_screen` call to run next, using auto_scale only if the caller prefers to keep screenshot coordinates.
        """
    )


@mcp.prompt(
    name="safe_click",
    title="Safely perform a click",
    description="Perform a guarded click with scaling awareness and post-click confirmation guidance.",
)
def prompt_safe_click(
    x: int,
    y: int,
    coordinate_source: str,
    button: str = "left",
    clicks: int = 1,
    reason: Optional[str] = None,
) -> str:
    """Prompt template for scaling-aware click execution."""
    rationale = reason or "the requested action"
    return _prompt_text(
        f"""
        Reason: {rationale}. Prepare to click at ({x}, {y}) using button={button} and clicks={clicks}.
        If coordinate_source is 'screenshot', enable auto_scale and note the applied scaling; if 'logical', keep auto_scale false.
        If unsure, grab a quick `screenshot_with_grid` first and ask for confirmation.
        Call `click_screen` accordingly and return success, applied_scaling, and any warnings.
        Suggest taking a follow-up screenshot if verification is needed.
        """
    )


@mcp.prompt(
    name="hover_and_capture",
    title="Hover to reveal UI then capture",
    description="Move the mouse to a target location to reveal hover state, then capture evidence.",
)
def prompt_hover_and_capture(
    x: int,
    y: int,
    duration: float = 0.0,
    goal: Optional[str] = None,
    output_path: Optional[str] = None,
) -> str:
    """Prompt template for hover then capture workflows."""
    goal_text = goal or "the target UI"
    path_hint = f"output_path={output_path}" if output_path else "the default output path"
    return _prompt_text(
        f"""
        Goal: {goal_text}. Move the cursor with `move_mouse` to ({x}, {y}) using duration={duration}.
        Avoid clicking. After the hover settles, call `take_screenshot` ({path_hint}) so the hover state is captured.
        Return the screenshot path, any warnings, and a brief note on whether the target UI reacted.
        """
    )


@mcp.prompt(
    name="coordinate_mismatch_recovery",
    title="Recover from coordinate mismatch",
    description="Diagnose why a click landed wrong and propose corrected coordinates.",
)
def prompt_coordinate_mismatch_recovery(
    target_description: str,
    last_click_x: Optional[int] = None,
    last_click_y: Optional[int] = None,
    observed_offset: Optional[str] = None,
) -> str:
    """Prompt template for troubleshooting misaligned clicks."""
    click_text = (
        f"({last_click_x}, {last_click_y})"
        if last_click_x is not None and last_click_y is not None
        else "unknown coordinates"
    )
    offset_text = observed_offset or "unspecified offset"
    return _prompt_text(
        f"""
        You attempted to click {target_description} at {click_text} and it missed (offset: {offset_text}).
        Run `get_display_diagnostics` to confirm scaling, then capture `screenshot_with_grid` to anchor logical coordinates.
        If the intended spot is visible, propose corrected logical coords and the exact `click_screen` call (use auto_scale only if using screenshot-measured coords).
        Keep safety first and suggest reconfirming with a quick screenshot after the next attempt.
        """
    )


@mcp.prompt(
    name="end_to_end_capture_and_act",
    title="End-to-end capture and action",
    description="Plan a safe workflow: inspect, pick coordinates, click, and verify the result.",
)
def prompt_end_to_end_capture_and_act(
    goal: str,
    target_hint: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> str:
    """Prompt template for full capture-plan-act-verify loops."""
    hint_text = target_hint or "the target control"
    dir_hint = f"output_dir={output_dir}" if output_dir else "the default directory"
    return _prompt_text(
        f"""
        Goal: {goal}. 1) Capture context with `screenshot_quadrants` ({dir_hint}); if the UI is simple, `take_screenshot` is fine.
        2) Identify the control described by {hint_text}, selecting precise logical coordinates (use `convert_screenshot_coordinates` if starting from screenshot pixels).
        3) Provide the exact `click_screen` call (enable auto_scale only when using screenshot-derived coordinates) and flag any risks.
        4) Recommend a quick verification capture (grid or regular screenshot) after the action.
        """
    )


_PROMPT_TEMPLATE_META: Dict[str, Dict[str, str]] = {
    "baseline_display_check": {
        "title": "Baseline display and scaling check",
        "description": "Collect display server, sizing, and scaling warnings before interacting with the desktop.",
    },
    "capture_full_desktop": {
        "title": "Capture full desktop screenshot",
        "description": "Capture a full-screen screenshot and summarize what is visible before acting.",
    },
    "capture_region_for_task": {
        "title": "Capture region screenshot",
        "description": "Grab a focused region screenshot to inspect a specific UI area.",
    },
    "grid_overlay_snapshot": {
        "title": "Grid overlay screenshot for coordinates",
        "description": "Capture a grid-annotated screenshot to make click coordinates explicit.",
    },
    "quadrant_scan": {
        "title": "Quadrant scan for high-resolution UIs",
        "description": "Split the screen into grid-labeled quadrants to inspect dense interfaces and plan clicks.",
    },
    "convert_screenshot_coordinates": {
        "title": "Convert screenshot pixels to logical click coords",
        "description": "Turn coordinates measured on a screenshot into logical positions for click_screen.",
    },
    "safe_click": {
        "title": "Safely perform a click",
        "description": "Perform a guarded click with scaling awareness and post-click confirmation guidance.",
    },
    "hover_and_capture": {
        "title": "Hover to reveal UI then capture",
        "description": "Move the mouse to a target location to reveal hover state, then capture evidence.",
    },
    "coordinate_mismatch_recovery": {
        "title": "Recover from coordinate mismatch",
        "description": "Diagnose why a click landed wrong and propose corrected coordinates.",
    },
    "end_to_end_capture_and_act": {
        "title": "End-to-end capture and action",
        "description": "Plan a safe workflow: inspect, pick coordinates, click, and verify the result.",
    },
}


@mcp.tool()
def list_prompt_templates() -> PromptTemplatesResult:
    """List available prompt templates for clients without prompt support."""
    templates = [
        PromptTemplateSummary(
            name=name,
            title=meta["title"],
            description=meta["description"],
        )
        for name, meta in _PROMPT_TEMPLATE_META.items()
    ]
    return PromptTemplatesResult(templates=templates)


@mcp.tool()
def render_prompt_baseline_display_check(
    task_hint: Optional[str] = None,
) -> PromptTemplateResult:
    """Expose baseline display check prompt for Codex CLI as a tool."""
    meta = _PROMPT_TEMPLATE_META["baseline_display_check"]
    return PromptTemplateResult(
        name="baseline_display_check",
        title=meta["title"],
        description=meta["description"],
        prompt=prompt_baseline_display_check(task_hint),
    )


@mcp.tool()
def render_prompt_capture_full_desktop(
    goal: str,
    output_path: Optional[str] = None,
) -> PromptTemplateResult:
    """Expose full desktop capture prompt as a tool."""
    meta = _PROMPT_TEMPLATE_META["capture_full_desktop"]
    return PromptTemplateResult(
        name="capture_full_desktop",
        title=meta["title"],
        description=meta["description"],
        prompt=prompt_capture_full_desktop(goal=goal, output_path=output_path),
    )


@mcp.tool()
def render_prompt_capture_region_for_task(
    region: str,
    goal: Optional[str] = None,
    output_path: Optional[str] = None,
) -> PromptTemplateResult:
    """Expose region capture prompt as a tool."""
    meta = _PROMPT_TEMPLATE_META["capture_region_for_task"]
    return PromptTemplateResult(
        name="capture_region_for_task",
        title=meta["title"],
        description=meta["description"],
        prompt=prompt_capture_region_for_task(
            region=region,
            goal=goal,
            output_path=output_path,
        ),
    )


@mcp.tool()
def render_prompt_grid_overlay_snapshot(
    goal: str,
    grid_size: Optional[int] = None,
    output_path: Optional[str] = None,
) -> PromptTemplateResult:
    """Expose grid overlay prompt as a tool."""
    meta = _PROMPT_TEMPLATE_META["grid_overlay_snapshot"]
    return PromptTemplateResult(
        name="grid_overlay_snapshot",
        title=meta["title"],
        description=meta["description"],
        prompt=prompt_grid_overlay_snapshot(
            goal=goal,
            grid_size=grid_size,
            output_path=output_path,
        ),
    )


@mcp.tool()
def render_prompt_quadrant_scan(
    goal: str,
    grid_size: Optional[int] = None,
    output_dir: Optional[str] = None,
) -> PromptTemplateResult:
    """Expose quadrant scan prompt as a tool."""
    meta = _PROMPT_TEMPLATE_META["quadrant_scan"]
    return PromptTemplateResult(
        name="quadrant_scan",
        title=meta["title"],
        description=meta["description"],
        prompt=prompt_quadrant_scan(
            goal=goal,
            grid_size=grid_size,
            output_dir=output_dir,
        ),
    )


@mcp.tool()
def render_prompt_convert_screenshot_coordinates(
    screenshot_x: int,
    screenshot_y: int,
    note: Optional[str] = None,
) -> PromptTemplateResult:
    """Expose coordinate conversion prompt as a tool."""
    meta = _PROMPT_TEMPLATE_META["convert_screenshot_coordinates"]
    return PromptTemplateResult(
        name="convert_screenshot_coordinates",
        title=meta["title"],
        description=meta["description"],
        prompt=prompt_convert_screenshot_coordinates(
            screenshot_x=screenshot_x,
            screenshot_y=screenshot_y,
            note=note,
        ),
    )


@mcp.tool()
def render_prompt_safe_click(
    x: int,
    y: int,
    coordinate_source: str,
    button: str = "left",
    clicks: int = 1,
    reason: Optional[str] = None,
) -> PromptTemplateResult:
    """Expose safe click prompt as a tool."""
    meta = _PROMPT_TEMPLATE_META["safe_click"]
    return PromptTemplateResult(
        name="safe_click",
        title=meta["title"],
        description=meta["description"],
        prompt=prompt_safe_click(
            x=x,
            y=y,
            coordinate_source=coordinate_source,
            button=button,
            clicks=clicks,
            reason=reason,
        ),
    )


@mcp.tool()
def render_prompt_hover_and_capture(
    x: int,
    y: int,
    duration: float = 0.0,
    goal: Optional[str] = None,
    output_path: Optional[str] = None,
) -> PromptTemplateResult:
    """Expose hover and capture prompt as a tool."""
    meta = _PROMPT_TEMPLATE_META["hover_and_capture"]
    return PromptTemplateResult(
        name="hover_and_capture",
        title=meta["title"],
        description=meta["description"],
        prompt=prompt_hover_and_capture(
            x=x,
            y=y,
            duration=duration,
            goal=goal,
            output_path=output_path,
        ),
    )


@mcp.tool()
def render_prompt_coordinate_mismatch_recovery(
    target_description: str,
    last_click_x: Optional[int] = None,
    last_click_y: Optional[int] = None,
    observed_offset: Optional[str] = None,
) -> PromptTemplateResult:
    """Expose coordinate mismatch recovery prompt as a tool."""
    meta = _PROMPT_TEMPLATE_META["coordinate_mismatch_recovery"]
    return PromptTemplateResult(
        name="coordinate_mismatch_recovery",
        title=meta["title"],
        description=meta["description"],
        prompt=prompt_coordinate_mismatch_recovery(
            target_description=target_description,
            last_click_x=last_click_x,
            last_click_y=last_click_y,
            observed_offset=observed_offset,
        ),
    )


@mcp.tool()
def render_prompt_end_to_end_capture_and_act(
    goal: str,
    target_hint: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> PromptTemplateResult:
    """Expose end-to-end capture and action prompt as a tool."""
    meta = _PROMPT_TEMPLATE_META["end_to_end_capture_and_act"]
    return PromptTemplateResult(
        name="end_to_end_capture_and_act",
        title=meta["title"],
        description=meta["description"],
        prompt=prompt_end_to_end_capture_and_act(
            goal=goal,
            target_hint=target_hint,
            output_dir=output_dir,
        ),
    )


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
