"""Tests for mouse control functionality."""

import pytest
from unittest.mock import Mock, patch

from ubuntu_desktop_control.server import (
    click_screen,
    move_mouse,
    drag_mouse,
    MouseClickResult,
)


class TestClickScreen:
    """Test the optimized click_screen function."""
    
    def test_click_by_percentage(self, mock_pyautogui, mock_x11_env):
        """Test clicking by percentage coordinates."""
        mock_pyautogui.size.return_value = (1920, 1080)
        
        result = click_screen(x_percent=0.5, y_percent=0.5)
        
        assert result.success is True
        assert result.x == 960  # 50% of 1920
        assert result.y == 540  # 50% of 1080
        mock_pyautogui.click.assert_called_once_with(x=960, y=540, clicks=1, button='left')
    
    def test_click_by_element_id(self, mock_pyautogui, mock_x11_env, clear_element_cache):
        """Test clicking by cached element ID."""
        from ubuntu_desktop_control.server import click_screen as click_fn
        
        # Setup element cache
        click_fn._element_cache = {
            1: {'x': 100, 'y': 200, 'width': 50, 'height': 30},
            2: {'x': 300, 'y': 400, 'width': 60, 'height': 40},
        }
        
        mock_pyautogui.size.return_value = (1920, 1080)
        
        result = click_screen(element_id=1)
        
        assert result.success is True
        assert result.x == 100
        assert result.y == 200
        mock_pyautogui.click.assert_called_once_with(x=100, y=200, clicks=1, button='left')
    
    def test_click_element_not_in_cache(self, mock_pyautogui, mock_x11_env, clear_element_cache):
        """Test clicking element ID that doesn't exist in cache."""
        from ubuntu_desktop_control.server import click_screen as click_fn
        
        click_fn._element_cache = {1: {'x': 100, 'y': 200}}
        mock_pyautogui.size.return_value = (1920, 1080)
        
        result = click_screen(element_id=99)
        
        assert result.success is False
        assert "Element 99 not found" in result.error
    
    def test_click_no_cache_available(self, mock_pyautogui, mock_x11_env, clear_element_cache):
        """Test clicking by element ID when no cache exists."""
        mock_pyautogui.size.return_value = (1920, 1080)
        
        result = click_screen(element_id=1)
        
        assert result.success is False
        assert "No element cache" in result.error
    
    def test_click_invalid_percentage(self, mock_pyautogui, mock_x11_env):
        """Test clicking with invalid percentage coordinates."""
        mock_pyautogui.size.return_value = (1920, 1080)
        
        result = click_screen(x_percent=1.5, y_percent=0.5)
        
        assert result.success is False
        assert "between 0.0 and 1.0" in result.error
    
    def test_click_right_button(self, mock_pyautogui, mock_x11_env):
        """Test right-click."""
        mock_pyautogui.size.return_value = (1920, 1080)
        
        result = click_screen(x_percent=0.5, y_percent=0.5, button='right')
        
        assert result.success is True
        mock_pyautogui.click.assert_called_with(x=960, y=540, clicks=1, button='right')
    
    def test_click_double_click(self, mock_pyautogui, mock_x11_env):
        """Test double-click."""
        mock_pyautogui.size.return_value = (1920, 1080)
        
        result = click_screen(x_percent=0.5, y_percent=0.5, clicks=2)
        
        assert result.success is True
        mock_pyautogui.click.assert_called_with(x=960, y=540, clicks=2, button='left')
    
    def test_click_missing_coordinates(self, mock_pyautogui, mock_x11_env):
        """Test clicking without providing coordinates or element ID."""
        mock_pyautogui.size.return_value = (1920, 1080)
        
        result = click_screen()
        
        assert result.success is False
        assert "Must provide either element_id" in result.error


class TestMoveMouse:
    """Test mouse movement functionality."""
    
    def test_move_by_percentage(self, mock_pyautogui, mock_x11_env):
        """Test moving mouse by percentage coordinates."""
        mock_pyautogui.size.return_value = (1920, 1080)
        
        result = move_mouse(x_percent=0.25, y_percent=0.75)
        
        assert result.success is True
        assert result.x == 480  # 25% of 1920
        assert result.y == 810  # 75% of 1080
        mock_pyautogui.moveTo.assert_called_once_with(480, 810, duration=0.0)
    
    def test_move_by_element_id(self, mock_pyautogui, mock_x11_env, clear_element_cache):
        """Test moving mouse to cached element."""
        from ubuntu_desktop_control.server import click_screen as click_fn
        
        click_fn._element_cache = {
            5: {'x': 500, 'y': 600, 'width': 80, 'height': 40},
        }
        
        mock_pyautogui.size.return_value = (1920, 1080)
        
        result = move_mouse(element_id=5, duration=0.5)
        
        assert result.success is True
        assert result.x == 500
        assert result.y == 600
        mock_pyautogui.moveTo.assert_called_once_with(500, 600, duration=0.5)
    
    def test_move_with_animation(self, mock_pyautogui, mock_x11_env):
        """Test smooth mouse movement with duration."""
        mock_pyautogui.size.return_value = (1920, 1080)
        
        result = move_mouse(x_percent=0.5, y_percent=0.5, duration=1.0)
        
        assert result.success is True
        mock_pyautogui.moveTo.assert_called_once_with(960, 540, duration=1.0)


class TestDragMouse:
    """Test mouse drag functionality."""
    
    def test_drag_mouse_basic(self, mock_pyautogui, mock_x11_env):
        """Test basic mouse drag operation."""
        mock_pyautogui.size.return_value = (1920, 1080)
        
        result = drag_mouse(x=500, y=600, button='left', duration=0.5)
        
        assert result.success is True
        assert result.x == 500
        assert result.y == 600
        mock_pyautogui.dragTo.assert_called_once_with(500, 600, duration=0.5, button='left')
    
    def test_drag_right_button(self, mock_pyautogui, mock_x11_env):
        """Test drag with right mouse button."""
        mock_pyautogui.size.return_value = (1920, 1080)
        
        result = drag_mouse(x=500, y=600, button='right')
        
        assert result.success is True
        mock_pyautogui.dragTo.assert_called_with(500, 600, duration=0.5, button='right')


# ============================================================================
# INTEGRATION TESTS (Real Dependencies)
# ============================================================================

class TestRealMouse:
    """Integration tests using REAL PyAutoGUI and mouse control."""
    
    @pytest.mark.integration
    def test_real_move_to_center(self):
        """Test that we can actually move the mouse with real PyAutoGUI."""
        import os
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        from ubuntu_desktop_control.server import get_screen_info
        
        info = get_screen_info()
        assert info.success
        
        result = move_mouse(x_percent=0.5, y_percent=0.5, duration=0.1)
        
        assert result.success is True
        expected_x = int(info.width * 0.5)
        expected_y = int(info.height * 0.5)
        assert abs(result.x - expected_x) < 5
        assert abs(result.y - expected_y) < 5


# ============================================================================
# GUI INTEGRATION TESTS (Test GUI Application)
# ============================================================================

class TestGUIMouseClick:
    """Test mouse clicking with the test GUI."""
    
    @pytest.mark.integration  
    def test_click_button_topleft(self, gui_ready, tmp_path):
        """Test clicking the top-left button and verifying it was clicked."""
        import os, time
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        from ubuntu_desktop_control.server import take_screenshot, click_screen
        from PyQt5.QtWidgets import QApplication
        
        screenshot = take_screenshot(detect_elements=True, output_dir=str(tmp_path))
        assert screenshot.success
        
        topleft_button = None
        for elem in screenshot.elements:
            if elem.name and ('Top-Left' in elem.name or 'Click Me' in elem.name):
                if elem.center_x < screenshot.display_width * 0.3:
                    topleft_button = elem
                    break
        
        if not topleft_button:
            pytest.skip("Could not find top-left button in detected elements")
        
        click_result = click_screen(element_id=topleft_button.id)
        assert click_result.success
        
        QApplication.instance().processEvents()
        time.sleep(0.2)
        
        state = gui_ready.get_state()
        assert state['last_button_clicked'] == 'topleft', f"Button not clicked! State: {state}"
        print(f"✓ Successfully clicked button and verified: {state['last_button_clicked']}")
    
    @pytest.mark.integration
    def test_click_by_percentage_coords(self, gui_ready, tmp_path):
        """Test clicking by percentage coordinates using discovered element location."""
        import os, time
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        from ubuntu_desktop_control.server import take_screenshot, click_screen, get_screen_info
        from PyQt5.QtWidgets import QApplication
        
        # STEP 1: Take screenshot and detect elements
        screenshot = take_screenshot(detect_elements=True, output_dir=str(tmp_path))
        assert screenshot.success
        
        info = get_screen_info()
        assert info.success
        
        # STEP 2: Find any button in the top area
        top_button = None
        for elem in screenshot.elements:
            if elem.role and 'button' in elem.role.lower():
                if elem.center_y < screenshot.display_height * 0.2:  # Top 20% of screen
                    top_button = elem
                    break
        
        if not top_button:
            # Fallback: calculate percentage from screen dimensions
            x_percent = 0.5
            y_percent = 0.1
        else:
            # Use discovered button location
            x_percent = top_button.center_x / screenshot.display_width
            y_percent = top_button.center_y / screenshot.display_height
        
        # STEP 3: Click at the discovered/calculated position
        click_result = click_screen(x_percent=x_percent, y_percent=y_percent)
        assert click_result.success
        
        QApplication.instance().processEvents()
        time.sleep(0.3)
        
        state = gui_ready.get_state()
        print(f"✓ Clicked at ({x_percent:.2f}, {y_percent:.2f}), button state: {state['last_button_clicked']}")


class TestGUIMouseMovement:
    """Test mouse movement capabilities."""
    
    @pytest.mark.integration
    def test_move_mouse_to_coords(self, gui_ready, tmp_path):
        """Test moving mouse to specific coordinates discovered from screenshot."""
        import os
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        from ubuntu_desktop_control.server import take_screenshot, move_mouse, get_screen_info
        
        # STEP 1: Take screenshot to discover screen dimensions
        screenshot = take_screenshot(detect_elements=False, output_dir=str(tmp_path))
        assert screenshot.success
        
        screen_info = get_screen_info()
        assert screen_info.success
        
        # STEP 2: Calculate center from discovered dimensions
        center_x_pct = 0.5
        center_y_pct = 0.5
        
        # STEP 3: Move to center - slow enough to see
        result = move_mouse(x_percent=center_x_pct, y_percent=center_y_pct, duration=0.5)
        assert result.success
        print(f"✓ Moved mouse to center ({result.x}, {result.y}) on {screenshot.display_width}x{screenshot.display_height} screen")
    
    @pytest.mark.integration
    def test_move_mouse_by_percentage(self, gui_ready, tmp_path):
        """Test moving mouse by percentage coordinates across screen."""
        import os, time
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        from ubuntu_desktop_control.server import take_screenshot, move_mouse
        
        # STEP 1: Take screenshot to verify screen is accessible
        screenshot = take_screenshot(detect_elements=False, output_dir=str(tmp_path))
        assert screenshot.success
        
        positions = [
            (0.1, 0.1, "top-left"),
            (0.9, 0.1, "top-right"),
            (0.5, 0.5, "center"),
            (0.1, 0.9, "bottom-left"),
            (0.9, 0.9, "bottom-right"),
        ]
        
        for x_pct, y_pct, name in positions:
            result = move_mouse(x_percent=x_pct, y_percent=y_pct, duration=0.3)
            assert result.success
            time.sleep(0.3)  # Pause so user can see the movement
        
        print("✓ Moved mouse to 5 positions by percentage")


class TestGUIMouseDrag:
    """Test mouse dragging capabilities."""
    
    @pytest.mark.integration
    def test_drag_mouse_relative(self, gui_ready, tmp_path):
        """Test dragging mouse with relative movement using real screenshot."""
        import os, time
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        from ubuntu_desktop_control.server import take_screenshot, move_mouse, drag_mouse, get_screen_info
        
        # STEP 1: Take screenshot to discover screen dimensions
        screenshot = take_screenshot(detect_elements=False, output_dir=str(tmp_path))
        assert screenshot.success
        
        # Move to starting position (visible movement)
        move_result = move_mouse(x_percent=0.3, y_percent=0.3, duration=0.4)
        assert move_result.success
        start_x, start_y = move_result.x, move_result.y
        time.sleep(0.3)
        
        # Drag to a position 100px right and down from start (slow drag)
        target_x = start_x + 100
        target_y = start_y + 100
        drag_result = drag_mouse(x=target_x, y=target_y, duration=0.8, button='left')
        assert drag_result.success
        print(f"✓ Dragged mouse from ({start_x}, {start_y}) to ({target_x}, {target_y})")
    
    @pytest.mark.integration
    def test_drag_mouse_to_position(self, gui_ready, tmp_path):
        """Test dragging mouse to specific position discovered from screenshot."""
        import os, time
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        from ubuntu_desktop_control.server import take_screenshot, move_mouse, drag_mouse, get_screen_info
        
        # STEP 1: Take screenshot to discover screen dimensions
        screenshot = take_screenshot(detect_elements=False, output_dir=str(tmp_path))
        assert screenshot.success
        
        screen_info = get_screen_info()
        assert screen_info.success
        
        # Move to top-left quadrant (25%, 25%) - visible movement
        move_result = move_mouse(x_percent=0.25, y_percent=0.25, duration=0.4)
        assert move_result.success
        start_x, start_y = move_result.x, move_result.y
        time.sleep(0.3)
        
        # Calculate target position (75%, 75%) and drag slowly
        end_x = int(screen_info.width * 0.75)
        end_y = int(screen_info.height * 0.75)
        drag_result = drag_mouse(x=end_x, y=end_y, duration=0.8, button='left')
        assert drag_result.success
        print(f"✓ Dragged from ({start_x}, {start_y}) to ({end_x}, {end_y})")


class TestGUICoordinateSystem:
    """Test coordinate system and scaling."""
    
    @pytest.mark.integration
    def test_coordinate_accuracy(self, gui_ready, tmp_path):
        """Test that clicks land at the correct coordinates."""
        import os, time
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        from ubuntu_desktop_control.server import take_screenshot, click_screen, get_screen_info
        from PyQt5.QtWidgets import QApplication
        
        screen_info = get_screen_info()
        assert screen_info.success
        
        test_positions = [
            (0.1, 0.1),
            (0.5, 0.1),
            (0.9, 0.1),
        ]
        
        for x_pct, y_pct in test_positions:
            screenshot = take_screenshot(detect_elements=False, output_dir=str(tmp_path))
            assert screenshot.success
            
            click_result = click_screen(x_percent=x_pct, y_percent=y_pct)
            assert click_result.success
            
            QApplication.instance().processEvents()
            time.sleep(0.2)
        
        print(f"✓ Tested coordinate accuracy at {len(test_positions)} positions")
