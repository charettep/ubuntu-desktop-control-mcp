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
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


# pyautogui tries to connect to the display at import time. On headless systems
# or when permissions are restricted, that import can raise before the MCP
# server finishes initializing. We lazily import it inside the tools instead so
# the server can start and report a clear error to the caller.
_pyautogui = None
_pyautogui_error: Optional[str] = None

# Default folder inside workspace to save artifacts clients can read
_CAPTURE_DIR_NAME = "captures"


def _default_output_dir() -> str:
    """Return a workspace-local capture directory, creating it if missing."""
    base = os.getcwd()
    path = os.path.join(base, _CAPTURE_DIR_NAME)
    os.makedirs(path, exist_ok=True)
    return path


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

# Short-term caches to avoid hammering diagnostics/screen info when clients poll aggressively
_DIAG_CACHE: Optional[Tuple[float, Any]] = None  # (timestamp, DiagnosticInfo)
_SCREEN_INFO_CACHE: Optional[Tuple[float, Any]] = None  # (timestamp, ScreenInfo)


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def _safe_percent(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return _clamp(numerator / denominator, 0.0, 1.0)


def _element_cache_to_xy(
    *,
    elem: Dict[str, Any],
    screen_width: int,
    screen_height: int,
) -> Tuple[int, int]:
    """Resolve a cached element to logical (x, y) click coordinates.

    Supports both legacy cache entries (x/y) and new cache entries (x_percent/y_percent).
    """
    if "x_percent" in elem and "y_percent" in elem:
        x_percent = float(elem["x_percent"])
        y_percent = float(elem["y_percent"])
        x_percent = _clamp(x_percent, 0.0, 1.0)
        y_percent = _clamp(y_percent, 0.0, 1.0)
        return int(screen_width * x_percent), int(screen_height * y_percent)

    return int(elem.get("x", 0)), int(elem.get("y", 0))


def _get_cached_elements(pyautogui_module):
    """Return element cache if screen size matches; otherwise invalidate."""
    cache = getattr(click_screen, "_element_cache", None)
    if not cache:
        return None, None

    try:
        logical_w, logical_h = pyautogui_module.size()
    except Exception:
        logical_w, logical_h = None, None

    # New-style cache has meta and elements
    if isinstance(cache, dict) and "elements" in cache and "meta" in cache:
        meta = cache.get("meta", {})
        if logical_w and logical_h:
            if meta.get("logical_width") != logical_w or meta.get("logical_height") != logical_h:
                return None, None
        return cache.get("elements", {}), meta

    # Legacy cache: element_id -> data
    if isinstance(cache, dict):
        return cache, None

    return None, None


def _build_preferred_targets(
    *,
    elements: List["AccessibleElement"],
    element_map: Dict[int, Dict[str, Any]],
    logical_width: int,
    logical_height: int,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Rank likely targets (e.g., Firefox) to enable one-shot clicks."""
    keywords = ["firefox", "browser", "mozilla", "chrome", "web"]
    preferred_roles = {"icon", "push button", "menu item", "list item"}

    ranked: List[Tuple[float, Dict[str, Any]]] = []

    for elem in elements:
        cached = element_map.get(elem.id, {})
        name = (cached.get("name") or elem.name or "").strip()
        role = (cached.get("role") or elem.role or "").strip().lower()
        lname = name.lower()

        score = 0.0
        for kw in keywords:
            if kw in lname:
                score += 10.0
                if lname.startswith(kw):
                    score += 2.0
        if role in preferred_roles:
            score += 3.0
        if role and role.startswith("app"):
            score += 1.0

        x_percent = cached.get("x_percent")
        y_percent = cached.get("y_percent")
        if x_percent is None:
            x_percent = _safe_percent(elem.center_x, logical_width)
        if y_percent is None:
            y_percent = _safe_percent(elem.center_y, logical_height)

        # Slight preference for mid-sized targets
        area = max(1, cached.get("width") or elem.width) * max(1, cached.get("height") or elem.height)
        score += min(area / 20000.0, 5.0)

        ranked.append(
            (
                score,
                {
                    "id": elem.id,
                    "name": name,
                    "role": role,
                    "x_percent": x_percent,
                    "y_percent": y_percent,
                },
            )
        )

    ranked.sort(key=lambda t: (-t[0], t[1]["id"]))
    return [item for _, item in ranked[:limit] if _clamp(item["x_percent"], 0.0, 1.0) >= 0.0]


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
    grid_overlay_path: Optional[str] = Field(None, description="Path to screenshot with coordinate grid overlay")
    full_screenshot_path: Optional[str] = Field(None, description="Path to full screenshot (when quadrants generated)")
    top_left_path: Optional[str] = Field(None, description="Path to top-left quadrant")
    top_right_path: Optional[str] = Field(None, description="Path to top-right quadrant")
    bottom_left_path: Optional[str] = Field(None, description="Path to bottom-left quadrant")
    bottom_right_path: Optional[str] = Field(None, description="Path to bottom-right quadrant")
    width: Optional[int] = Field(None, description="Screen width in logical pixels (reported by OS)")
    height: Optional[int] = Field(None, description="Screen height in logical pixels (reported by OS)")
    actual_width: Optional[int] = Field(None, description="Actual screenshot width in physical pixels")
    actual_height: Optional[int] = Field(None, description="Actual screenshot height in physical pixels")
    scaling_factor: Optional[float] = Field(None, description="Detected display scaling factor (1.0 = no scaling)")
    scaling_warning: Optional[str] = Field(None, description="Warning if scaling mismatch detected")
    quadrant_info: Optional[str] = Field(None, description="Explanation of quadrant coordinate system")
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


class GUIElement(BaseModel):
    """Represents a detected UI element with its bounding box and center."""
    id: int
    x: int
    y: int
    width: int
    height: int
    center_x: int
    center_y: int
    area: int


class GUIElementMapResult(BaseModel):
    """Result of the GUI element mapping operation."""
    success: bool
    elements: List[GUIElement] = Field(default_factory=list, description="List of detected UI elements")
    count: int = Field(description="Total number of elements detected")
    debug_image_path: Optional[str] = Field(None, description="Path to the debug image with drawn contours")
    screenshot_path: Optional[str] = Field(None, description="Path to the screenshot used for detection")
    scaling_factor: Optional[float] = Field(None, description="Detected display scaling factor")
    warnings: Optional[List[str]] = Field(None, description="Non-fatal warnings")
    error: Optional[str] = Field(None, description="Error message if operation failed")


class AccessibleElement(BaseModel):
    """Represents a UI element from accessibility API."""
    id: int
    name: str
    role: str
    x: int
    y: int
    width: int
    height: int
    center_x: int
    center_y: int
    is_clickable: bool
    children_count: int = 0


class AnnotatedScreenshot(BaseModel):
    """Screenshot with detected elements and annotations."""
    success: bool
    screenshot_path: str = Field(description="Path to annotated screenshot with numbered elements")
    original_path: Optional[str] = Field(None, description="Path to original full-resolution screenshot")
    elements: List[AccessibleElement] = Field(default_factory=list, description="Detected accessible elements")
    element_map: Dict[int, Dict] = Field(default_factory=dict, description="Map of element ID to coordinates and metadata")
    display_width: int = Field(description="Width used for display (downsampled)")
    display_height: int = Field(description="Height used for display (downsampled)")
    actual_width: int = Field(description="Actual screen width")
    actual_height: int = Field(description="Actual screen height")
    scaling_info: str = Field(description="Explanation of coordinate scaling")
    suggested_targets: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Top recommended elements to click (id, name, role, x_percent, y_percent)",
    )
    warnings: Optional[List[str]] = Field(None, description="Non-fatal warnings")
    error: Optional[str] = Field(None, description="Error message if operation failed")


class WorkflowAction(BaseModel):
    """Single action in a workflow."""
    action: str = Field(description="Action type: screenshot, click, move, type, wait")
    element_id: Optional[int] = Field(None, description="Element ID to interact with")
    x_percent: Optional[float] = Field(None, description="X coordinate as percentage (0.0-1.0)")
    y_percent: Optional[float] = Field(None, description="Y coordinate as percentage (0.0-1.0)")
    text: Optional[str] = Field(None, description="Text to type")
    duration: Optional[float] = Field(None, description="Wait duration or animation duration")
    button: Optional[str] = Field(None, description="Mouse button: left, right, middle")


class WorkflowResult(BaseModel):
    """Result of workflow execution."""
    success: bool
    actions_completed: int
    total_actions: int
    results: List[Dict] = Field(default_factory=list, description="Results of each action")
    final_screenshot: Optional[str] = Field(None, description="Path to final screenshot")
    error: Optional[str] = Field(None, description="Error message if workflow failed")


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
    detect_elements: bool = True,
    output_dir: Optional[str] = None
) -> AnnotatedScreenshot:
    """
    Take an annotated screenshot with automatic element detection and downsampling.

    OPTIMIZED FOR LLM COMPUTER USE:
    - Automatically downsamples to 1280x720 for faster processing
    - Detects UI elements using accessibility API (AT-SPI)
    - Overlays numbered markers on each clickable element
    - Returns element map for direct interaction ("click element #5")
    
    This replaces the old multi-tool approach with a single optimized workflow.

    Args:
        detect_elements: Whether to detect and annotate UI elements (default: True).
                        If False, returns plain downsampled screenshot.
        output_dir: Directory for output files. Defaults to a workspace-local 'captures' folder.

    Returns:
        AnnotatedScreenshot with:
        - screenshot_path: Annotated image with numbered elements (1280x720)
        - original_path: Full-resolution original screenshot
        - elements: List of detected elements with names, roles, and coordinates
        - element_map: Direct coordinate lookup {element_id: {x, y, width, height}}
        - scaling_info: How to interpret coordinates

    Usage:
        result = take_screenshot()
        # LLM sees numbered elements in image
        # LLM responds: "Click element #3"
        click_element(element_id=3)
    """
    pyautogui = _get_pyautogui()
    if pyautogui is None:
        return AnnotatedScreenshot(
            success=False,
            screenshot_path="",
            display_width=0,
            display_height=0,
            actual_width=0,
            actual_height=0,
            scaling_info="",
            error=_pyautogui_error
        )

    warnings = _collect_env_warnings()

    try:
        # Logical screen dimensions (what PyAutoGUI uses for input coordinates)
        logical_width, logical_height = pyautogui.size()
        
        # Set output directory inside workspace so clients can read captures
        if output_dir is None:
            output_dir = _default_output_dir()
        else:
            os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Capture full-resolution screenshot (physical pixels)
        screenshot, img_width, img_height, backend_warning = _get_screenshot_with_backend(pyautogui)
        if backend_warning:
            warnings.append(backend_warning)

        scaling_factor, scaling_warning = _detect_scaling_factor(
            pyautogui,
            logical_size=(logical_width, logical_height),
            actual_size=(img_width, img_height),
        )
        if scaling_warning:
            warnings.append(scaling_warning)
        
        # Save original full-resolution version
        original_path = os.path.join(output_dir, f"screenshot_original_{timestamp}.png")
        screenshot.save(original_path)
        
        # Downsample to 1280x720 for LLM processing (huge speed improvement)
        from PIL import Image
        target_width = 1280
        target_height = 720
        
        # Calculate scaling to fit within target dimensions while maintaining aspect ratio
        width_ratio = target_width / img_width
        height_ratio = target_height / img_height
        # Avoid upscaling small screens (adds blur without adding detail)
        scale_ratio = min(width_ratio, height_ratio, 1.0)
        
        display_width = int(img_width * scale_ratio)
        display_height = int(img_height * scale_ratio)
        
        downsampled = screenshot.resize((display_width, display_height), Image.Resampling.LANCZOS)
        
        scaling_info = (
            f"Screenshot downsampled from {img_width}x{img_height} to {display_width}x{display_height}. "
            f"Click by element ID with click_screen(element_id=N) or by percentage with "
            f"click_screen(x_percent=0.5, y_percent=0.3). "
            f"Logical input size: {logical_width}x{logical_height}. "
            f"Detected scaling factor: {scaling_factor:.2f}x."
        )

        # Detect elements using AT-SPI if requested
        elements = []
        element_map = {}
        
        if detect_elements:
            try:
                # Try AT-SPI first (most accurate)
                import pyatspi
                
                def run_at_spi_scan() -> None:
                    nonlocal element_id
                    desktop = pyatspi.Registry.getDesktop(0)
                    for i in range(desktop.childCount):
                        try:
                            app = desktop.getChildAtIndex(i)
                            extract_elements(app, depth=0)
                        except Exception:
                            continue

                element_id = 1
                
                def extract_elements(node, depth: int = 0, max_depth: int = 10):
                    nonlocal element_id
                    if depth > max_depth or element_id > 50:  # Limit to 50 elements
                        return

                    # Get element info defensively (do not break recursion if one property fails)
                    try:
                        name = node.name or ""
                    except Exception:
                        name = ""

                    try:
                        role = node.getRoleName()
                    except Exception:
                        role = ""

                    interactive_roles = [
                        "push button",
                        "toggle button",
                        "check box",
                        "radio button",
                        "menu item",
                        "list item",
                        "link",
                        "entry",
                        "text",
                        "icon",
                    ]

                    if role in interactive_roles:
                        try:
                            comp = getattr(node, "component", None)
                            if comp:
                                ext = comp.getExtents(pyatspi.DESKTOP_COORDS)

                                if ext.width > 0 and ext.height > 0:
                                    # Filter out giant containers; they're rarely "clickable" targets
                                    if ext.width * ext.height <= int(img_width * img_height * 0.5):
                                        raw_center_x = ext.x + ext.width // 2
                                        raw_center_y = ext.y + ext.height // 2

                                        # Determine coordinate space heuristically
                                        if 0 <= raw_center_x <= logical_width and 0 <= raw_center_y <= logical_height:
                                            logical_center_x = int(raw_center_x)
                                            logical_center_y = int(raw_center_y)
                                            logical_x = int(ext.x)
                                            logical_y = int(ext.y)
                                            logical_w = int(ext.width)
                                            logical_h = int(ext.height)
                                        elif (
                                            0 <= raw_center_x <= img_width
                                            and 0 <= raw_center_y <= img_height
                                            and scaling_factor
                                        ):
                                            logical_center_x = int(raw_center_x / scaling_factor)
                                            logical_center_y = int(raw_center_y / scaling_factor)
                                            logical_x = int(ext.x / scaling_factor)
                                            logical_y = int(ext.y / scaling_factor)
                                            logical_w = int(ext.width / scaling_factor)
                                            logical_h = int(ext.height / scaling_factor)
                                        else:
                                            logical_center_x = -1
                                            logical_center_y = -1
                                            logical_x = 0
                                            logical_y = 0
                                            logical_w = 0
                                            logical_h = 0

                                        if 0 <= logical_center_x <= logical_width and 0 <= logical_center_y <= logical_height:
                                            x_percent = _safe_percent(logical_center_x, logical_width)
                                            y_percent = _safe_percent(logical_center_y, logical_height)

                                            children_count = 0
                                            try:
                                                children_count = int(getattr(node, "childCount", 0))
                                            except Exception:
                                                children_count = 0

                                            element = AccessibleElement(
                                                id=element_id,
                                                name=name or f"{role}",
                                                role=role,
                                                x=logical_x,
                                                y=logical_y,
                                                width=max(1, logical_w),
                                                height=max(1, logical_h),
                                                center_x=logical_center_x,
                                                center_y=logical_center_y,
                                                is_clickable=True,
                                                children_count=children_count,
                                            )
                                            elements.append(element)

                                            element_map[element_id] = {
                                                "x": logical_center_x,
                                                "y": logical_center_y,
                                                "width": max(1, logical_w),
                                                "height": max(1, logical_h),
                                                "name": name,
                                                "role": role,
                                                "x_percent": x_percent,
                                                "y_percent": y_percent,
                                            }
                                            element_id += 1
                        except Exception:
                            pass

                    # Recurse to children regardless of extraction errors above
                    try:
                        child_count = int(getattr(node, "childCount", 0))
                    except Exception:
                        child_count = 0
                    for i in range(child_count):
                        try:
                            child = node.getChildAtIndex(i)
                            extract_elements(child, depth + 1)
                        except Exception:
                            continue
                
                # Start extraction from all applications
                run_at_spi_scan()

                # AT-SPI can race during app startup; retry once if empty.
                if not elements:
                    import time

                    time.sleep(0.1)
                    element_id = 1
                    elements.clear()
                    element_map.clear()
                    run_at_spi_scan()
                
                if not elements:
                    warnings.append("AT-SPI found no elements, falling back to CV detection")
                    # Fall back to CV-based detection
                    elements, element_map = _fallback_cv_detection(
                        screenshot,
                        img_width,
                        img_height,
                        logical_width,
                        logical_height,
                    )
                    
            except ImportError:
                warnings.append("pyatspi not available, using CV-based detection")
                elements, element_map = _fallback_cv_detection(
                    screenshot,
                    img_width,
                    img_height,
                    logical_width,
                    logical_height,
                )
            except Exception as e:
                warnings.append(f"AT-SPI detection failed: {e}, using CV fallback")
                elements, element_map = _fallback_cv_detection(
                    screenshot,
                    img_width,
                    img_height,
                    logical_width,
                    logical_height,
                )
        
        # Create annotated version with numbered markers
        annotated = downsampled.copy()
        if elements:
            from PIL import ImageDraw, ImageFont
            draw = ImageDraw.Draw(annotated)
            
            # Try to load a font
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
            except Exception:
                font = ImageFont.load_default()
            
            for elem in elements:
                # Draw using percentage coordinates when available for best alignment
                cached = element_map.get(elem.id, {})
                x_percent = cached.get("x_percent")
                y_percent = cached.get("y_percent")
                if x_percent is not None and y_percent is not None:
                    x = int(display_width * float(x_percent))
                    y = int(display_height * float(y_percent))
                else:
                    # Fallback: treat element coordinates as logical and scale to downsampled
                    x = int(_safe_percent(elem.center_x, logical_width) * display_width)
                    y = int(_safe_percent(elem.center_y, logical_height) * display_height)
                
                # Draw circle marker
                radius = 12
                draw.ellipse([x - radius, y - radius, x + radius, y + radius], 
                           fill=(255, 0, 0, 200), outline=(255, 255, 255))
                
                # Draw element ID
                text = str(elem.id)
                bbox = draw.textbbox((x, y), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                draw.text((x - text_width // 2, y - text_height // 2), text, 
                         fill=(255, 255, 255), font=font)
        
        # Build suggested targets for one-shot selection (e.g., Firefox)
        suggested_targets = None
        if elements:
            suggested_targets = _build_preferred_targets(
                elements=elements,
                element_map=element_map,
                logical_width=logical_width,
                logical_height=logical_height,
            )

        # Save annotated screenshot
        annotated_path = os.path.join(output_dir, f"screenshot_annotated_{timestamp}.png")
        annotated.save(annotated_path)

        # Cache element map for click_screen to use, with metadata for invalidation
        if element_map:
            click_screen._element_cache = {
                "meta": {
                    "logical_width": logical_width,
                    "logical_height": logical_height,
                    "scaling_factor": scaling_factor,
                },
                "elements": element_map,
            }

        return AnnotatedScreenshot(
            success=True,
            screenshot_path=annotated_path,
            original_path=original_path,
            elements=elements,
            element_map=element_map,
            display_width=display_width,
            display_height=display_height,
            actual_width=img_width,
            actual_height=img_height,
            scaling_info=scaling_info,
            suggested_targets=suggested_targets,
            warnings=warnings or None
        )

    except Exception as e:
        return AnnotatedScreenshot(
            success=False,
            screenshot_path="",
            display_width=0,
            display_height=0,
            actual_width=0,
            actual_height=0,
            scaling_info="",
            error=f"Screenshot failed: {str(e)}",
            warnings=warnings or None
        )


def _fallback_cv_detection(
    screenshot,
    img_width: int,
    img_height: int,
    logical_width: Optional[int] = None,
    logical_height: Optional[int] = None,
) -> Tuple[List[AccessibleElement], Dict[int, Dict[str, Any]]]:
    """Fallback CV-based element detection when AT-SPI fails."""
    elements = []
    element_map = {}

    # Backward-compatible defaults: if logical size isn't supplied, assume 1:1
    logical_width = int(logical_width or img_width)
    logical_height = int(logical_height or img_height)
    
    try:
        import cv2
        import numpy as np
        
        # Convert PIL to OpenCV
        img_array = np.array(screenshot)
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        
        # Use Canny edge detection (fast, good for UI boundaries)
        edges = cv2.Canny(gray, 50, 150)

        # Connect gaps so buttons/inputs become single contours
        try:
            kernel = np.ones((3, 3), np.uint8)
            edges = cv2.dilate(edges, kernel, iterations=1)
        except Exception:
            pass

        # Find contours (pass 1)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # If Canny finds nothing, fall back to threshold-based segmentation
        if not contours:
            try:
                thresh = cv2.adaptiveThreshold(
                    gray,
                    255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY_INV,
                    31,
                    5,
                )
                kernel = np.ones((5, 5), np.uint8)
                closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=1)
                contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            except Exception:
                contours = []
        
        # Filter and sort by area
        MIN_WIDTH, MIN_HEIGHT = 20, 20
        valid_contours = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            area = w * h
            if area <= 100:
                continue
            if w < MIN_WIDTH or h < MIN_HEIGHT:
                continue
            if area >= int(img_width * img_height * 0.5):
                continue
            valid_contours.append((area, x, y, w, h))
        
        # Sort by area and take top 30
        valid_contours.sort(reverse=True)
        valid_contours = valid_contours[:30]
        
        element_id = 1
        for _, x, y, w, h in valid_contours:
            physical_center_x = x + w // 2
            physical_center_y = y + h // 2

            # Convert to percent of the screen, then to logical coords (robust to scaling)
            x_percent = _safe_percent(physical_center_x, img_width)
            y_percent = _safe_percent(physical_center_y, img_height)
            center_x = int(logical_width * x_percent)
            center_y = int(logical_height * y_percent)
            
            element = AccessibleElement(
                id=element_id,
                name=f"Element {element_id}",
                role="detected",
                x=int(logical_width * _safe_percent(x, img_width)),
                y=int(logical_height * _safe_percent(y, img_height)),
                width=max(1, int(logical_width * _safe_percent(w, img_width))),
                height=max(1, int(logical_height * _safe_percent(h, img_height))),
                center_x=center_x,
                center_y=center_y,
                is_clickable=True,
                children_count=0
            )
            elements.append(element)
            
            element_map[element_id] = {
                "x": center_x,
                "y": center_y,
                "width": element.width,
                "height": element.height,
                "name": f"Element {element_id}",
                "role": "detected",
                "x_percent": x_percent,
                "y_percent": y_percent,
            }
            
            element_id += 1
            
    except Exception:
        pass
    
    return elements, element_map


# ============================================================================
# OLD/DEPRECATED IMPLEMENTATIONS - For reference only, do not use
# ============================================================================
# The functions below (take_screenshot_old, click_screen_old) represent the
# old non-optimized approach before AT-SPI integration and percentage coords.
# They are kept for reference but should not be called.
# ============================================================================


# @mcp.tool()  # Commented out - replaced by optimized take_screenshot()
def click_screen_old(
    x: int,
    y: int,
    button: str = "left",
    clicks: int = 1,
    interval: float = 0.0,
    auto_scale: bool = False,
) -> MouseClickResult:
    """DEPRECATED: Use click_element() or click_screen() with percentage coordinates."""
    pass


@mcp.tool()
def click_screen(
    x_percent: Optional[float] = None,
    y_percent: Optional[float] = None,
    element_id: Optional[int] = None,
    button: str = "left",
    clicks: int = 1,
) -> MouseClickResult:
    """
    Click at screen location using PERCENTAGE coordinates or element ID.

    Preferred order:
    1) element_id from take_screenshot (best accuracy)
    2) x_percent/y_percent (resolution-agnostic fallback)

    Args:
        x_percent: X coordinate as percentage (0.0 = left edge, 1.0 = right edge)
        y_percent: Y coordinate as percentage (0.0 = top edge, 1.0 = bottom edge)
        element_id: ID of element from take_screenshot (overrides x_percent/y_percent)
        button: Mouse button: "left", "right", or "middle"
        clicks: Number of clicks (1 for single, 2 for double)

    Returns:
        MouseClickResult with success status

    Examples:
        - click_screen(element_id=3) - Click element #3 from screenshot
        - click_screen(x_percent=0.5, y_percent=0.5) - Click center of screen
        - click_screen(x_percent=0.02, y_percent=0.3, button="right") - Right click
    """
    pyautogui = _get_pyautogui()
    if pyautogui is None:
        return MouseClickResult(
            success=False,
            x=0,
            y=0,
            button=button,
            clicks=clicks,
            error=_pyautogui_error,
        )


@mcp.tool()
def click_first_match(
    name_substring: str,
    role_hint: Optional[str] = None,
) -> MouseClickResult:
    """
    Find the best-matching cached element by name/role and click it (uses element IDs).

    Intended for quick launches like "Firefox" without manual element_id lookup.
    If no cache exists, it will call take_screenshot(detect_elements=True) once.
    """
    pyautogui = _get_pyautogui()
    if pyautogui is None:
        return MouseClickResult(
            success=False,
            x=0,
            y=0,
            button="left",
            clicks=1,
            error=_pyautogui_error,
        )

    if not name_substring:
        return MouseClickResult(
            success=False,
            x=0,
            y=0,
            button="left",
            clicks=1,
            error="name_substring is required",
        )

    warnings = _collect_env_warnings()

    cached_elements, _ = _get_cached_elements(pyautogui)
    if not cached_elements:
        shot = take_screenshot(detect_elements=True)
        if not shot.success:
            return MouseClickResult(
                success=False,
                x=0,
                y=0,
                button="left",
                clicks=1,
                warnings=warnings or shot.warnings,
                error=shot.error or "Failed to detect elements",
            )
        cached_elements, _ = _get_cached_elements(pyautogui)

    if not cached_elements:
        return MouseClickResult(
            success=False,
            x=0,
            y=0,
            button="left",
            clicks=1,
            warnings=warnings or None,
            error="No elements available after screenshot; cannot match.",
        )

    target = name_substring.lower()
    role_hint_lower = role_hint.lower() if role_hint else None
    best_id = None
    best_score = -1.0

    for elem_id, data in cached_elements.items():
        name = str(data.get("name") or "").lower()
        role = str(data.get("role") or "").lower()

        score = 0.0
        if target in name:
            score += 10.0
            if name.startswith(target):
                score += 2.0
        if role_hint_lower:
            if role == role_hint_lower:
                score += 3.0
            elif role_hint_lower in role:
                score += 2.0

        if score <= 0:
            continue

        score += 0.1  # small bias to break ties
        if score > best_score:
            best_score = score
            best_id = elem_id

    if best_id is None:
        return MouseClickResult(
            success=False,
            x=0,
            y=0,
            button="left",
            clicks=1,
            warnings=warnings or None,
            error=f"No element matched '{name_substring}'.",
        )

    result = click_screen(element_id=best_id, button="left", clicks=1)
    if warnings:
        if result.warnings:
            result.warnings = list(result.warnings) + warnings
        else:
            result.warnings = warnings
    return result

    warnings = _collect_env_warnings()

    cached_elements, cache_meta = _get_cached_elements(pyautogui)
    cache_warning = None
    if cache_meta is None and getattr(click_screen, "_element_cache", None) and not cached_elements:
        cache_warning = "Element cache missing metadata; refresh with take_screenshot(detect_elements=True)."

    try:
        # Validate button
        valid_buttons = ["left", "right", "middle"]
        if button not in valid_buttons:
            return MouseClickResult(
                success=False,
                x=0,
                y=0,
                button=button,
                clicks=clicks,
                error=f"Invalid button. Must be one of: {valid_buttons}"
            )

        # Get screen dimensions
        screen_width, screen_height = pyautogui.size()
        
        # Determine click coordinates (logical)
        if element_id is not None:
            if not cached_elements:
                return MouseClickResult(
                    success=False,
                    x=0,
                    y=0,
                    button=button,
                    clicks=clicks,
                    warnings=warnings or None,
                    error="No element cache available. Run take_screenshot(detect_elements=True) first.",
                )

            if element_id not in cached_elements:
                return MouseClickResult(
                    success=False,
                    x=0,
                    y=0,
                    button=button,
                    clicks=clicks,
                    warnings=warnings or None,
                    error=f"Element {element_id} not found. Valid IDs: {list(cached_elements.keys())}",
                )

            elem = cached_elements[element_id]
            x, y = _element_cache_to_xy(elem=elem, screen_width=screen_width, screen_height=screen_height)
            
        elif x_percent is not None and y_percent is not None:
            # Use percentage coordinates
            if not (0.0 <= x_percent <= 1.0 and 0.0 <= y_percent <= 1.0):
                return MouseClickResult(
                    success=False,
                    x=0,
                    y=0,
                    button=button,
                    clicks=clicks,
                    error="Percentage coordinates must be between 0.0 and 1.0"
                )
            
            x = int(screen_width * x_percent)
            y = int(screen_height * y_percent)
        else:
            return MouseClickResult(
                success=False,
                x=0,
                y=0,
                button=button,
                clicks=clicks,
                error="Must provide either element_id or both x_percent and y_percent"
            )
        
        # Perform click
        pyautogui.click(x=x, y=y, clicks=clicks, button=button)

        if cache_warning:
            warnings = (warnings or []) + [cache_warning]

        return MouseClickResult(
            success=True,
            x=x,
            y=y,
            button=button,
            clicks=clicks,
            applied_scaling=None,
            scaling_warning=None,
            warnings=warnings or None,
        )

    except Exception as e:
        return MouseClickResult(
            success=False,
            x=0,
            y=0,
            button=button,
            clicks=clicks,
            error=f"Click failed: {str(e)}",
            warnings=warnings or None,
        )


# Initialize element cache on the function
click_screen._element_cache = {}


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
    global _SCREEN_INFO_CACHE

    # Serve cached success for a short window to avoid client polling spam
    if _SCREEN_INFO_CACHE:
        ts, cached = _SCREEN_INFO_CACHE
        if time.monotonic() - ts < 2.0 and getattr(cached, "success", False):
            return cached

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

        result = ScreenInfo(
            success=True,
            width=screen_width,
            height=screen_height,
            display_server=_safe_display_server(),
            scaling_factor=scaling_factor,
            warnings=warnings or None,
        )
        _SCREEN_INFO_CACHE = (time.monotonic(), result)
        return result
    except Exception as e:  # noqa: BLE001
        return ScreenInfo(
            success=False,
            display_server=_safe_display_server(),
            error=f"Failed to get screen info: {str(e)}",
            warnings=warnings or None,
        )


@mcp.tool()
def move_mouse(
    x_percent: Optional[float] = None,
    y_percent: Optional[float] = None,
    element_id: Optional[int] = None,
    duration: float = 0.0
) -> MouseClickResult:
    """
    Move mouse cursor to specified screen coordinates without clicking.

    Supports both percentage coordinates and element IDs (like click_screen).

    Args:
        x_percent: X coordinate as percentage (0.0 = left edge, 1.0 = right edge)
        y_percent: Y coordinate as percentage (0.0 = top edge, 1.0 = bottom edge)
        element_id: Element ID from take_screenshot (overrides percentages)
        duration: Time in seconds to animate the movement (0 for instant)

    Returns:
        MouseClickResult with success status (clicks will be 0)

    Examples:
        - move_mouse(x_percent=0.5, y_percent=0.3) - Move to center-top
        - move_mouse(element_id=5, duration=0.5) - Smoothly move to element #5
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

    cached_elements, cache_meta = _get_cached_elements(pyautogui)
    cache_warning = None
    if cache_meta is None and getattr(click_screen, "_element_cache", None) and not cached_elements:
        cache_warning = "Element cache missing metadata; refresh with take_screenshot(detect_elements=True)."

    x = 0
    y = 0

    try:
        screen_width, screen_height = pyautogui.size()
        
        # Determine coordinates
        if element_id is not None:
            if not cached_elements:
                return MouseClickResult(
                    success=False,
                    x=0,
                    y=0,
                    button="none",
                    clicks=0,
                    error="No element cache. Run take_screenshot(detect_elements=True) first.",
                )

            if element_id not in cached_elements:
                return MouseClickResult(
                    success=False,
                    x=0,
                    y=0,
                    button="none",
                    clicks=0,
                    error=f"Element {element_id} not found.",
                )

            elem = cached_elements[element_id]
            x, y = _element_cache_to_xy(elem=elem, screen_width=screen_width, screen_height=screen_height)
            
        elif x_percent is not None and y_percent is not None:
            if not (0.0 <= x_percent <= 1.0 and 0.0 <= y_percent <= 1.0):
                return MouseClickResult(
                    success=False,
                    x=0,
                    y=0,
                    button="none",
                    clicks=0,
                    error="Percentage coordinates must be between 0.0 and 1.0"
                )
            
            x = int(screen_width * x_percent)
            y = int(screen_height * y_percent)
        else:
            return MouseClickResult(
                success=False,
                x=0,
                y=0,
                button="none",
                clicks=0,
                error="Must provide either element_id or both x_percent and y_percent"
            )

        # Move mouse
        pyautogui.moveTo(x, y, duration=duration)

        if cache_warning:
            warnings = (warnings or []) + [cache_warning]

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
def drag_mouse(
    x: int,
    y: int,
    button: str = "left",
    duration: float = 0.5
) -> MouseClickResult:
    """
    Drag the mouse cursor to specific coordinates while holding a button.

    This tool performs a "click and drag" operation. It starts from the CURRENT
    mouse position and drags to the specified (x, y) coordinates.
    Useful for selecting text, moving windows, or drag-and-drop operations.

    Args:
        x: Target X coordinate in pixels
        y: Target Y coordinate in pixels
        button: Mouse button to hold down (default "left")
        duration: Time in seconds to perform the drag (default 0.5)

    Returns:
        MouseClickResult with success status

    Examples:
        - drag_mouse(x=500, y=300) - Drag from current pos to (500, 300)
    """
    pyautogui = _get_pyautogui()
    if pyautogui is None:
        return MouseClickResult(
            success=False,
            x=0, y=0, button=button, clicks=0,
            error=_pyautogui_error or "PyAutoGUI not available"
        )

    warnings = _collect_env_warnings()

    try:
        pyautogui.dragTo(x, y, duration=duration, button=button)

        return MouseClickResult(
            success=True,
            x=x,
            y=y,
            button=button,
            clicks=0,
            warnings=warnings or None,
        )
    except Exception as e:  # noqa: BLE001
        return MouseClickResult(
            success=False,
            x=x, y=y, button=button, clicks=0,
            error=f"Mouse drag failed: {str(e)}",
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
def press_hotkey(keys: List[str]) -> MouseClickResult:
    """
    Press a combination of keys simultaneously (e.g., Ctrl+Shift+C).

    This tool performs a hotkey combination. It presses the keys in order,
    holds them down, then releases them in reverse order.

    Args:
        keys: List of keys to press. Example: ["ctrl", "shift", "c"] or ["alt", "tab"]

    Returns:
        MouseClickResult with success status

    Examples:
        - press_hotkey(keys=["ctrl", "c"]) - Copy
        - press_hotkey(keys=["ctrl", "shift", "c"]) - Terminal Copy
        - press_hotkey(keys=["alt", "f4"]) - Close window
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
        pyautogui.hotkey(*keys)
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
            error=f"Hotkey failed: {str(e)}",
            warnings=warnings or None,
        )


@mcp.tool()
def execute_workflow(
    actions: List[Dict],
    take_final_screenshot: bool = True
) -> WorkflowResult:
    """
    Execute multiple actions in sequence for efficient multi-step workflows.

    OPTIMIZED FOR COMPLEX TASKS:
    This tool batches multiple actions (screenshot, click, type, wait) into one
    MCP call, reducing round-trip latency. Use for multi-step workflows like:
    - Opening an application and clicking through menus
    - Filling out multi-field forms
    - Navigating through a series of UI steps

    Args:
        actions: List of actions to execute. Each action is a dict with:
            - action: "screenshot" | "click" | "move" | "type" | "wait"
            - element_id: (optional) Element ID to interact with
            - x_percent: (optional) X coordinate as percentage
            - y_percent: (optional) Y coordinate as percentage
            - text: (optional) Text to type
            - duration: (optional) Wait duration in seconds
            - button: (optional) Mouse button ("left", "right", "middle")
        take_final_screenshot: Whether to take a screenshot after completion (default: True)

    Returns:
        WorkflowResult with:
        - success: Whether all actions completed successfully
        - actions_completed: Number of actions executed
        - results: List of individual action results
        - final_screenshot: Path to final screenshot (if enabled)

    Example:
        execute_workflow(actions=[
            {"action": "screenshot"},
            {"action": "click", "element_id": 3},
            {"action": "wait", "duration": 0.5},
            {"action": "type", "text": "Hello"},
            {"action": "click", "x_percent": 0.5, "y_percent": 0.8}
        ])
    """
    pyautogui = _get_pyautogui()
    if pyautogui is None:
        return WorkflowResult(
            success=False,
            actions_completed=0,
            total_actions=len(actions),
            error=_pyautogui_error
        )

    results = []
    completed = 0
    
    try:
        for i, action_dict in enumerate(actions):
            action_type = action_dict.get("action", "").lower()
            
            try:
                if action_type == "screenshot":
                    # Take screenshot with element detection
                    result = take_screenshot(
                        detect_elements=action_dict.get("detect_elements", True),
                        output_dir=action_dict.get("output_dir")
                    )
                    results.append({
                        "action": "screenshot",
                        "success": result.success,
                        "screenshot_path": result.screenshot_path if result.success else None,
                        "elements_detected": len(result.elements) if result.success else 0
                    })
                    
                elif action_type == "click":
                    # Click using element ID or percentage coordinates
                    result = click_screen(
                        x_percent=action_dict.get("x_percent"),
                        y_percent=action_dict.get("y_percent"),
                        element_id=action_dict.get("element_id"),
                        button=action_dict.get("button", "left"),
                        clicks=action_dict.get("clicks", 1)
                    )
                    results.append({
                        "action": "click",
                        "success": result.success,
                        "x": result.x if result.success else None,
                        "y": result.y if result.success else None
                    })
                    
                elif action_type == "move":
                    # Move mouse
                    result = move_mouse(
                        x_percent=action_dict.get("x_percent"),
                        y_percent=action_dict.get("y_percent"),
                        element_id=action_dict.get("element_id"),
                        duration=action_dict.get("duration", 0.0)
                    )
                    results.append({
                        "action": "move",
                        "success": result.success,
                        "x": result.x if result.success else None,
                        "y": result.y if result.success else None
                    })
                    
                elif action_type == "type":
                    # Type text
                    text = action_dict.get("text", "")
                    interval = action_dict.get("interval", 0.0)
                    result = type_text(text=text, interval=interval)
                    results.append({
                        "action": "type",
                        "success": result.success,
                        "text_length": len(text)
                    })
                    
                elif action_type == "wait":
                    # Wait/sleep
                    import time
                    duration = action_dict.get("duration", 0.5)
                    time.sleep(duration)
                    results.append({
                        "action": "wait",
                        "success": True,
                        "duration": duration
                    })
                    
                else:
                    results.append({
                        "action": action_type,
                        "success": False,
                        "error": f"Unknown action type: {action_type}"
                    })
                    continue
                
                # Check if action succeeded
                if results[-1]["success"]:
                    completed += 1
                else:
                    # Stop on failure
                    break
                    
            except Exception as e:
                results.append({
                    "action": action_type,
                    "success": False,
                    "error": str(e)
                })
                break
        
        # Take final screenshot if requested and all actions succeeded
        final_screenshot_path = None
        if take_final_screenshot and completed == len(actions):
            final_result = take_screenshot()
            if final_result.success:
                final_screenshot_path = final_result.screenshot_path
        
        return WorkflowResult(
            success=(completed == len(actions)),
            actions_completed=completed,
            total_actions=len(actions),
            results=results,
            final_screenshot=final_screenshot_path
        )
        
    except Exception as e:
        return WorkflowResult(
            success=False,
            actions_completed=completed,
            total_actions=len(actions),
            results=results,
            error=f"Workflow execution failed: {str(e)}"
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
    global _DIAG_CACHE

    # Serve cached success briefly to prevent repeated polling from clients
    if _DIAG_CACHE:
        ts, cached = _DIAG_CACHE
        if time.monotonic() - ts < 2.0 and getattr(cached, "success", False):
            return cached

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
                f"or use `convert_screenshot_coordinates` to convert screenshot pixels to logical click coordinates. "
                f"For example: screenshot (1000, 500) -> click ({int(1000/scaling_factor)}, {int(500/scaling_factor)}). "
                f"Alternatively, use take_screenshot(detect_elements=True) to click by element_id or by x_percent/y_percent."
            )
        else:
            recommendation = (
                "No display scaling detected. Screenshot coordinates should match "
                "screen coordinates directly."
            )

        result = DiagnosticInfo(
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
        _DIAG_CACHE = (time.monotonic(), result)
        return result

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
def map_GUI_elements_location(
    screenshot_path: Optional[str] = None,
    min_area: int = 100,
    max_area: Optional[int] = None,
    debug_output_path: Optional[str] = None
) -> GUIElementMapResult:
    """
    Analyze a screenshot to detect and map GUI elements (buttons, inputs, etc.) using Computer Vision.

    This tool uses edge detection (Canny) and contour analysis to identify potential UI elements.
    It returns a list of "hit boxes" (x, y, width, height) and their center coordinates.
    This is useful for finding clickable elements when you don't know their exact coordinates.

    Args:
        screenshot_path: Path to an existing screenshot. If None, takes a new screenshot.
        min_area: Minimum area (width * height) for a contour to be considered a UI element. Default 100.
        max_area: Optional maximum area to filter out large containers or full screen.
        debug_output_path: Path to save a debug image with drawn contours.

    Returns:
        GUIElementMapResult containing the list of detected elements.
    """
    pyautogui = _get_pyautogui()
    warnings = _collect_env_warnings()

    captured_path: Optional[str] = None
    scaling_factor = 1.0

    try:
        import cv2
        import numpy as np
    except ImportError:
        return GUIElementMapResult(
            success=False,
            elements=[],
            count=0,
            error="OpenCV (cv2) or NumPy not installed. Please install 'opencv-python' and 'numpy'."
        )

    try:
        # 1. Get Screenshot
        if screenshot_path:
            if not os.path.exists(screenshot_path):
                return GUIElementMapResult(
                    success=False,
                    elements=[],
                    count=0,
                    error=f"File not found: {screenshot_path}",
                    screenshot_path=os.path.abspath(screenshot_path),
                )
            image = cv2.imread(screenshot_path)
            if image is None:
                return GUIElementMapResult(
                    success=False,
                    elements=[],
                    count=0,
                    error=f"Failed to load image: {screenshot_path}",
                    screenshot_path=os.path.abspath(screenshot_path),
                )
            captured_path = os.path.abspath(screenshot_path)
            
            # Detect scaling if possible (requires pyautogui)
            if pyautogui:
                screen_width, screen_height = pyautogui.size()
                h, w = image.shape[:2]
                scaling_factor, scaling_warning = _detect_scaling_factor(
                    pyautogui,
                    logical_size=(screen_width, screen_height),
                    actual_size=(w, h)
                )
                if scaling_warning:
                    warnings.append(scaling_warning)
        else:
            if pyautogui is None:
                return GUIElementMapResult(
                    success=False,
                    elements=[],
                    count=0,
                    error=_pyautogui_error,
                )
            
            # Take new screenshot
            pil_image, actual_w, actual_h, backend_warning = _get_screenshot_with_backend(pyautogui)
            if backend_warning:
                warnings.append(backend_warning)

            # Persist the captured screenshot so clients can inspect it
            capture_dir = _default_output_dir()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            captured_path = os.path.join(capture_dir, f"screenshot_elements_{timestamp}.png")
            try:
                pil_image.save(captured_path)
            except Exception as save_exc:  # noqa: BLE001 - best-effort persistence
                warnings.append(f"Failed to save screenshot to {captured_path}: {save_exc}")
                captured_path = None
            
            # Convert PIL to OpenCV (RGB -> BGR)
            image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
            
            screen_width, screen_height = pyautogui.size()
            scaling_factor, scaling_warning = _detect_scaling_factor(
                pyautogui,
                logical_size=(screen_width, screen_height),
                actual_size=(actual_w, actual_h)
            )
            if scaling_warning:
                warnings.append(scaling_warning)

        # 2. Process Image (Edge Detection)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply Canny edge detection
        edges = cv2.Canny(gray, 50, 150)
        
        # Dilate edges to connect gaps
        kernel = np.ones((3, 3), np.uint8)
        dilated = cv2.dilate(edges, kernel, iterations=1)
        
        # Find contours
        contours, hierarchy = cv2.findContours(dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        detected_elements = []
        element_id = 1
        
        # Prepare debug image if requested
        debug_image = None
        if debug_output_path:
            debug_image = image.copy()

        for contour in contours:
            # Get bounding box
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            
            # Filter by area
            if area < min_area:
                continue
            if max_area and area > max_area:
                continue
                
            # Calculate center
            center_x = x + w // 2
            center_y = y + h // 2
            
            # Add to list
            element = GUIElement(
                id=element_id,
                x=x,
                y=y,
                width=w,
                height=h,
                center_x=center_x,
                center_y=center_y,
                area=area
            )
            detected_elements.append(element)
            
            # Draw on debug image
            if debug_image is not None:
                cv2.rectangle(debug_image, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.circle(debug_image, (center_x, center_y), 2, (0, 0, 255), -1)
                cv2.putText(debug_image, str(element_id), (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
            element_id += 1

        # Save debug image
        saved_debug_path = None
        if debug_output_path and debug_image is not None:
            # Ensure directory exists
            os.makedirs(os.path.dirname(os.path.abspath(debug_output_path)), exist_ok=True)
            cv2.imwrite(debug_output_path, debug_image)
            saved_debug_path = debug_output_path

        return GUIElementMapResult(
            success=True,
            elements=detected_elements,
            count=len(detected_elements),
            debug_image_path=saved_debug_path,
            screenshot_path=captured_path,
            scaling_factor=scaling_factor,
            warnings=warnings or None
        )

    except Exception as e:
        return GUIElementMapResult(
            success=False,
            elements=[],
            count=0,
            error=f"Detection failed: {str(e)}",
            screenshot_path=captured_path,
            warnings=warnings or None
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
        Report display_server, logical size (width/height), scaling_factor, and any warnings.
        Prefer clicking by element ID from `take_screenshot` or by percentage with `click_screen(x_percent=..., y_percent=...)`.
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
    path_hint = f"output_dir={output_path}" if output_path else "the default output directory"
    return _prompt_text(
        f"""
        Goal: {goal}. Call `take_screenshot(detect_elements=True)` (use {path_hint}).
        Return screenshot_path, original_path, display_width/height, actual_width/height, and any warnings.
        List 2-3 concise observations relevant to the goal and suggest a next step (click by element_id or click by percentage).
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
    path_hint = f"output_dir={output_path}" if output_path else "the default output directory"
    return _prompt_text(
        f"""
        Goal: {goal_text}. Call `take_screenshot(detect_elements=True)` ({path_hint}).
        Focus your analysis on region '{region}' (descriptive guidance; `take_screenshot` currently captures the full screen).
        Return screenshot_path, any warnings, and a short summary of what is visible in that region.
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
        Provide the exact `click_screen` call to run next (use x_percent/y_percent derived from logical coords if you want resolution independence).
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
        If coordinate_source is 'screenshot', first convert with `convert_screenshot_coordinates` to get logical_x/logical_y.
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
    path_hint = f"output_dir={output_path}" if output_path else "the default output directory"
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
        Run `get_display_diagnostics` to confirm scaling, then call `take_screenshot(detect_elements=True)` and work with element IDs or x_percent/y_percent.
        If the intended spot is visible, propose corrected percentage coords and the exact `click_screen` call.
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
        Goal: {goal}. 1) Capture context with `take_screenshot(detect_elements=True)` ({dir_hint}).
        2) Identify the control described by {hint_text}, selecting precise percentage coordinates (use `convert_screenshot_coordinates` if starting from screenshot pixels).
        3) Provide the exact `click_screen` call (prefer element_id or percentage coordinates) and flag any risks.
        4) Recommend a quick verification capture after the action.
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


# @mcp.tool()
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


# @mcp.tool()
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


# @mcp.tool()
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


# @mcp.tool()
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


# @mcp.tool()
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


# @mcp.tool()
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


# @mcp.tool()
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


# @mcp.tool()
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


def main():
    """Entry point for the MCP server."""
    mcp.run()

if __name__ == "__main__":
    main()
