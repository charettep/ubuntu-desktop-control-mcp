#!/usr/bin/env python3
"""
Quick test script to verify the MCP server tools work correctly.
Run this after installing all dependencies.
"""

import sys
import os
import time

# Test imports
try:
    import pyautogui
    print("✓ PyAutoGUI imported successfully")
except ImportError as e:
    print(f"✗ Failed to import PyAutoGUI: {e}")
    sys.exit(1)

try:
    import mss
    print("✓ mss imported successfully (fast screenshot backend)")
except ImportError as e:
    print(f"⚠ Failed to import mss: {e} (will fall back to slower PyAutoGUI)")

try:
    from server import (
        take_screenshot, 
        click_screen, 
        get_screen_info, 
        move_mouse, 
        drag_mouse,
        type_text, 
        press_key, 
        press_hotkey,
        get_display_diagnostics,
        screenshot_with_grid,
        screenshot_quadrants,
        convert_screenshot_coordinates,
        list_prompt_templates
    )
    print("✓ Server tools imported successfully")
except ImportError as e:
    print(f"✗ Failed to import server tools: {e}")
    sys.exit(1)

# Helper to print section headers
def print_header(title):
    print(f"\n--- Testing {title} ---")

# 1. Test screen info
print_header("get_screen_info")
try:
    info = get_screen_info()
    if info.success:
        print(f"✓ Screen Info:")
        print(f"  - Resolution: {info.width}x{info.height}")
        print(f"  - Display Server: {info.display_server}")
        print(f"  - Scaling Factor: {info.scaling_factor}")
    else:
        print(f"✗ get_screen_info failed: {info.error}")
        sys.exit(1)
except Exception as e:
    print(f"✗ get_screen_info raised exception: {e}")
    sys.exit(1)

# 2. Test screenshot (without saving)
print_header("take_screenshot")
try:
    result = take_screenshot()
    if result.success:
        print(f"✓ Screenshot captured successfully")
        print(f"  - Saved to: {result.file_path}")
        print(f"  - Dimensions: {result.width}x{result.height}")
        # Clean up
        if result.file_path and os.path.exists(result.file_path):
            os.remove(result.file_path)
    else:
        print(f"✗ Screenshot failed: {result.error}")
except Exception as e:
    print(f"✗ take_screenshot raised exception: {e}")

# 3. Test mouse move (safe - just moves cursor)
print_header("move_mouse")
try:
    # Move to center of screen
    center_x = info.width // 2
    center_y = info.height // 2
    result = move_mouse(x=center_x, y=center_y)
    if result.success:
        print(f"✓ Mouse moved to ({center_x}, {center_y})")
    else:
        print(f"✗ Mouse move failed: {result.error}")
except Exception as e:
    print(f"✗ move_mouse raised exception: {e}")

# 4. Test click_screen (safe - click center)
print_header("click_screen")
try:
    # Click center (harmless usually)
    result = click_screen(x=center_x, y=center_y, clicks=1)
    if result.success:
        print(f"✓ Clicked at ({center_x}, {center_y})")
    else:
        print(f"✗ Click failed: {result.error}")
except Exception as e:
    print(f"✗ click_screen raised exception: {e}")

# 5. Test drag_mouse
print_header("drag_mouse")
try:
    # Drag small distance from center
    result = drag_mouse(x=center_x + 50, y=center_y + 50, duration=0.2)
    if result.success:
        print(f"✓ Dragged mouse to ({center_x + 50}, {center_y + 50})")
    else:
        print(f"✗ Drag failed: {result.error}")
except Exception as e:
    print(f"✗ drag_mouse raised exception: {e}")

# 6. Test type_text
print_header("type_text")
try:
    # Type empty string or harmless key
    result = type_text(text="", interval=0.0)
    if result.success:
        print(f"✓ Typed text successfully")
    else:
        print(f"✗ Type text failed: {result.error}")
except Exception as e:
    print(f"✗ type_text raised exception: {e}")

# 7. Test press_key
print_header("press_key")
try:
    # Press shift (harmless)
    result = press_key(key="shift")
    if result.success:
        print(f"✓ Pressed 'shift' key")
    else:
        print(f"✗ Press key failed: {result.error}")
except Exception as e:
    print(f"✗ press_key raised exception: {e}")

# 8. Test press_hotkey
print_header("press_hotkey")
try:
    # Press shift (harmless combo)
    result = press_hotkey(keys=["shift"])
    if result.success:
        print(f"✓ Pressed hotkey ['shift']")
    else:
        print(f"✗ Press hotkey failed: {result.error}")
except Exception as e:
    print(f"✗ press_hotkey raised exception: {e}")

# 9. Test get_display_diagnostics
print_header("get_display_diagnostics")
try:
    diag = get_display_diagnostics()
    if diag.success:
        print(f"✓ Diagnostics retrieved")
        print(f"  - Logical: {diag.logical_width}x{diag.logical_height}")
        print(f"  - Actual: {diag.actual_screenshot_width}x{diag.actual_screenshot_height}")
        print(f"  - Scaling Mismatch: {diag.has_scaling_mismatch}")
    else:
        print(f"✗ Diagnostics failed: {diag.error}")
except Exception as e:
    print(f"✗ get_display_diagnostics raised exception: {e}")

# 10. Test screenshot_with_grid
print_header("screenshot_with_grid")
try:
    result = screenshot_with_grid()
    if result.success:
        print(f"✓ Grid screenshot captured")
        print(f"  - Path: {result.file_path}")
        # Clean up
        if result.file_path and os.path.exists(result.file_path):
            os.remove(result.file_path)
    else:
        print(f"✗ Grid screenshot failed: {result.error}")
except Exception as e:
    print(f"✗ screenshot_with_grid raised exception: {e}")

# 11. Test screenshot_quadrants
print_header("screenshot_quadrants")
try:
    result = screenshot_quadrants()
    if result.success:
        print(f"✓ Quadrant screenshots captured")
        print(f"  - Full: {result.full_screenshot_path}")
        print(f"  - Top Left: {result.top_left_path}")
        # Clean up
        paths = [
            result.full_screenshot_path,
            result.top_left_path,
            result.top_right_path,
            result.bottom_left_path,
            result.bottom_right_path
        ]
        for p in paths:
            if p and os.path.exists(p):
                os.remove(p)
    else:
        print(f"✗ Quadrant screenshots failed: {result.error}")
except Exception as e:
    print(f"✗ screenshot_quadrants raised exception: {e}")

# 12. Test convert_screenshot_coordinates
print_header("convert_screenshot_coordinates")
try:
    result = convert_screenshot_coordinates(screenshot_x=100, screenshot_y=100)
    if result.success:
        print(f"✓ Coordinates converted")
        print(f"  - Input: (100, 100)")
        print(f"  - Logical: ({result.logical_x}, {result.logical_y})")
    else:
        print(f"✗ Coordinate conversion failed: {result.error}")
except Exception as e:
    print(f"✗ convert_screenshot_coordinates raised exception: {e}")

# 13. Test list_prompt_templates
print_header("list_prompt_templates")
try:
    result = list_prompt_templates()
    print(f"✓ Found {len(result.templates)} templates")
    for t in result.templates[:3]: # Print first 3
        print(f"  - {t.name}: {t.title}")
    if len(result.templates) > 3:
        print(f"  - ... and {len(result.templates) - 3} more")
except Exception as e:
    print(f"✗ list_prompt_templates raised exception: {e}")


print("\n" + "="*50)
print("✓ All tests completed.")
print("="*50)
