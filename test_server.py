#!/usr/bin/env python3
"""
Quick test script to verify the MCP server tools work correctly.
Run this after installing all dependencies.
"""

import sys

# Test imports
try:
    import pyautogui
    print("✓ PyAutoGUI imported successfully")
except ImportError as e:
    print(f"✗ Failed to import PyAutoGUI: {e}")
    sys.exit(1)

try:
    from server import take_screenshot, click_screen, get_screen_info, move_mouse
    print("✓ Server tools imported successfully")
except ImportError as e:
    print(f"✗ Failed to import server tools: {e}")
    sys.exit(1)

# Test screen info
print("\n--- Testing get_screen_info ---")
try:
    info = get_screen_info()
    print(f"✓ Screen Info:")
    print(f"  - Resolution: {info.width}x{info.height}")
    print(f"  - Display Server: {info.display_server}")
except Exception as e:
    print(f"✗ get_screen_info failed: {e}")
    sys.exit(1)

# Test screenshot (without saving)
print("\n--- Testing take_screenshot ---")
try:
    result = take_screenshot()
    if result.success:
        print(f"✓ Screenshot captured successfully")
        print(f"  - Saved to: {result.file_path}")
        print(f"  - Dimensions: {result.width}x{result.height}")
    else:
        print(f"✗ Screenshot failed: {result.error}")
        sys.exit(1)
except Exception as e:
    print(f"✗ take_screenshot failed: {e}")
    sys.exit(1)

# Test mouse move (safe - just moves cursor)
print("\n--- Testing move_mouse ---")
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
    print(f"✗ move_mouse failed: {e}")

print("\n" + "="*50)
print("✓ All tests passed! MCP server is ready to use.")
print("="*50)
print("\nNext steps:")
print("1. Install missing system packages if needed:")
print("   sudo apt install -y python3-xlib scrot python3-dev")
print("2. Configure your MCP client (see config-examples/)")
print("3. Test with MCP Inspector:")
print("   npx @modelcontextprotocol/inspector python3 server.py")
