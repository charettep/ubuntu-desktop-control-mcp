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
        output_dir: Directory for output files. Defaults to /tmp.

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
        # Get screen dimensions
        actual_width, actual_height = pyautogui.size()
        
        # Set output directory
        if output_dir is None:
            output_dir = "/tmp"
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Capture full-resolution screenshot
        screenshot, img_width, img_height, backend_warning = _get_screenshot_with_backend(pyautogui)
        if backend_warning:
            warnings.append(backend_warning)
        
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
        scale_ratio = min(width_ratio, height_ratio)
        
        display_width = int(img_width * scale_ratio)
        display_height = int(img_height * scale_ratio)
        
        downsampled = screenshot.resize((display_width, display_height), Image.Resampling.LANCZOS)
        
        scaling_info = (
            f"Screenshot downsampled from {img_width}x{img_height} to {display_width}x{display_height}. "
            f"All coordinates are in PERCENTAGE format (0.0-1.0). "
            f"Use click_element(element_id=N) or click_screen(x_percent=0.5, y_percent=0.3)."
        )

        # Detect elements using AT-SPI if requested
        elements = []
        element_map = {}
        
        if detect_elements:
            try:
                # Try AT-SPI first (most accurate)
                import pyatspi
                
                desktop = pyatspi.Registry.getDesktop(0)
                element_id = 1
                
                def extract_elements(node, depth=0, max_depth=10):
                    nonlocal element_id
                    if depth > max_depth or element_id > 50:  # Limit to 50 elements
                        return
                    
                    try:
                        # Get element info
                        name = node.name or ""
                        role = node.getRoleName()
                        
                        # Focus on interactive elements
                        interactive_roles = [
                            'push button', 'icon', 'menu item', 'check box',
                            'radio button', 'text', 'entry', 'link', 'list item',
                            'toggle button', 'application', 'frame'
                        ]
                        
                        if role in interactive_roles and node.component:
                            # Get position and size
                            ext = node.component.getExtents(pyatspi.DESKTOP_COORDS)
                            
                            if ext.width > 0 and ext.height > 0:
                                # Check if element is visible on screen
                                if 0 <= ext.x < img_width and 0 <= ext.y < img_height:
                                    center_x = ext.x + ext.width // 2
                                    center_y = ext.y + ext.height // 2
                                    
                                    element = AccessibleElement(
                                        id=element_id,
                                        name=name or f"{role}",
                                        role=role,
                                        x=ext.x,
                                        y=ext.y,
                                        width=ext.width,
                                        height=ext.height,
                                        center_x=center_x,
                                        center_y=center_y,
                                        is_clickable=True,
                                        children_count=node.childCount
                                    )
                                    elements.append(element)
                                    
                                    # Store in element map
                                    element_map[element_id] = {
                                        "x": center_x,
                                        "y": center_y,
                                        "width": ext.width,
                                        "height": ext.height,
                                        "name": name,
                                        "role": role
                                    }
                                    
                                    element_id += 1
                        
                        # Recurse to children
                        for i in range(node.childCount):
                            try:
                                child = node.getChildAtIndex(i)
                                extract_elements(child, depth + 1)
                            except:
                                continue
                                
                    except Exception:
                        pass
                
                # Start extraction from all applications
                for i in range(desktop.childCount):
                    try:
                        app = desktop.getChildAtIndex(i)
                        extract_elements(app, depth=0)
                    except:
                        continue
                
                if not elements:
                    warnings.append("AT-SPI found no elements, falling back to CV detection")
                    # Fall back to CV-based detection
                    elements, element_map = _fallback_cv_detection(screenshot, img_width, img_height)
                    
            except ImportError:
                warnings.append("pyatspi not available, using CV-based detection")
                elements, element_map = _fallback_cv_detection(screenshot, img_width, img_height)
            except Exception as e:
                warnings.append(f"AT-SPI detection failed: {e}, using CV fallback")
                elements, element_map = _fallback_cv_detection(screenshot, img_width, img_height)
        
        # Create annotated version with numbered markers
        annotated = downsampled.copy()
        if elements:
            from PIL import ImageDraw, ImageFont
            draw = ImageDraw.Draw(annotated)
            
            # Try to load a font
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
            except:
                font = ImageFont.load_default()
            
            for elem in elements:
                # Scale coordinates to downsampled image
                x = int(elem.center_x * scale_ratio)
                y = int(elem.center_y * scale_ratio)
                
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
        
        # Save annotated screenshot
        annotated_path = os.path.join(output_dir, f"screenshot_annotated_{timestamp}.png")
        annotated.save(annotated_path)

        # Cache element map for click_screen to use
        if element_map:
            click_screen._element_cache = element_map

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


def _fallback_cv_detection(screenshot, img_width, img_height):
    """Fallback CV-based element detection when AT-SPI fails."""
    elements = []
    element_map = {}
    
    try:
        import cv2
        import numpy as np
        
        # Convert PIL to OpenCV
        img_array = np.array(screenshot)
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        
        # Use Canny edge detection (more reliable than adaptive threshold)
        edges = cv2.Canny(gray, 50, 150)
        
        # Find contours
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter and sort by area
        MIN_WIDTH, MIN_HEIGHT = 20, 20
        valid_contours = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > 100:  # Minimum area threshold
                x, y, w, h = cv2.boundingRect(cnt)
                # Focus on UI-sized elements
                if w >= MIN_WIDTH and h >= MIN_HEIGHT and area < (img_width * img_height * 0.5):
                    valid_contours.append((area, x, y, w, h))
        
        # Sort by area and take top 30
        valid_contours.sort(reverse=True)
        valid_contours = valid_contours[:30]
        
        element_id = 1
        for _, x, y, w, h in valid_contours:
            center_x = x + w // 2
            center_y = y + h // 2
            
            element = AccessibleElement(
                id=element_id,
                name=f"Element {element_id}",
                role="detected",
                x=x,
                y=y,
                width=w,
                height=h,
                center_x=center_x,
                center_y=center_y,
                is_clickable=True,
                children_count=0
            )
            elements.append(element)
            
            element_map[element_id] = {
                "x": center_x,
                "y": center_y,
                "width": w,
                "height": h,
                "name": f"Element {element_id}",
                "role": "detected"
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

    OPTIMIZED APPROACH - Use one of these methods:
    1. Click by element ID (from take_screenshot): click_screen(element_id=5)
    2. Click by percentage: click_screen(x_percent=0.5, y_percent=0.3)

    Percentage coordinates are resolution-agnostic and work across different displays.
    Element IDs come from numbered markers in annotated screenshots.

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

    warnings = _collect_env_warnings()

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
        
        # Determine click coordinates
        if element_id is not None:
            # Use cached element coordinates from last screenshot
            if not hasattr(click_screen, '_element_cache'):
                return MouseClickResult(
                    success=False,
                    x=0,
                    y=0,
                    button=button,
                    clicks=clicks,
                    error="No element cache available. Take a screenshot first."
                )
            
            if element_id not in click_screen._element_cache:
                return MouseClickResult(
                    success=False,
                    x=0,
                    y=0,
                    button=button,
                    clicks=clicks,
                    error=f"Element {element_id} not found. Valid IDs: {list(click_screen._element_cache.keys())}"
                )
            
            elem = click_screen._element_cache[element_id]
            x = elem['x']
            y = elem['y']
            
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

    try:
        screen_width, screen_height = pyautogui.size()
        
        # Determine coordinates
        if element_id is not None:
            if not hasattr(click_screen, '_element_cache'):
                return MouseClickResult(
                    success=False,
                    x=0,
                    y=0,
                    button="none",
                    clicks=0,
                    error="No element cache. Take a screenshot first."
                )
            
            if element_id not in click_screen._element_cache:
                return MouseClickResult(
                    success=False,
                    x=0,
                    y=0,
                    button="none",
                    clicks=0,
                    error=f"Element {element_id} not found."
                )
            
            elem = click_screen._element_cache[element_id]
            x = elem['x']
            y = elem['y']
            
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
                return GUIElementMapResult(success=False, elements=[], count=0, error=f"File not found: {screenshot_path}")
            image = cv2.imread(screenshot_path)
            if image is None:
                return GUIElementMapResult(success=False, elements=[], count=0, error=f"Failed to load image: {screenshot_path}")
            
            # Detect scaling if possible (requires pyautogui)
            scaling_factor = 1.0
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
                return GUIElementMapResult(success=False, elements=[], count=0, error=_pyautogui_error)
            
            # Take new screenshot
            pil_image, actual_w, actual_h, backend_warning = _get_screenshot_with_backend(pyautogui)
            if backend_warning:
                warnings.append(backend_warning)
            
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
            scaling_factor=scaling_factor,
            warnings=warnings or None
        )

    except Exception as e:
        return GUIElementMapResult(
            success=False,
            elements=[],
            count=0,
            error=f"Detection failed: {str(e)}",
            warnings=warnings or None
        )


# @mcp.tool()  # Deprecated - merged into take_screenshot
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


# @mcp.tool()  # Deprecated - merged into take_screenshot
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


# @mcp.tool()
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
