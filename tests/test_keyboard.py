"""Tests for keyboard control functionality."""

import pytest
from unittest.mock import Mock

from ubuntu_desktop_control.server import (
    type_text,
    press_key,
    press_hotkey,
    MouseClickResult,
)


class TestTypeText:
    """Test text typing functionality."""
    
    def test_type_text_basic(self, mock_pyautogui, mock_x11_env):
        """Test basic text typing."""
        result = type_text(text="Hello World")
        
        assert result.success is True
        mock_pyautogui.write.assert_called_once_with("Hello World", interval=0.0)
    
    def test_type_text_with_interval(self, mock_pyautogui, mock_x11_env):
        """Test typing with delay between characters."""
        result = type_text(text="Slow", interval=0.1)
        
        assert result.success is True
        mock_pyautogui.write.assert_called_once_with("Slow", interval=0.1)
    
    def test_type_empty_string(self, mock_pyautogui, mock_x11_env):
        """Test typing empty string."""
        result = type_text(text="")
        
        assert result.success is True
        mock_pyautogui.write.assert_called_once_with("", interval=0.0)
    
    def test_type_special_characters(self, mock_pyautogui, mock_x11_env):
        """Test typing special characters."""
        result = type_text(text="!@#$%^&*()")
        
        assert result.success is True
        mock_pyautogui.write.assert_called_once_with("!@#$%^&*()", interval=0.0)


class TestPressKey:
    """Test single key press functionality."""
    
    def test_press_enter(self, mock_pyautogui, mock_x11_env):
        """Test pressing Enter key."""
        result = press_key(key="enter")
        
        assert result.success is True
        mock_pyautogui.press.assert_called_once_with("enter")
    
    def test_press_escape(self, mock_pyautogui, mock_x11_env):
        """Test pressing Escape key."""
        result = press_key(key="esc")
        
        assert result.success is True
        mock_pyautogui.press.assert_called_once_with("esc")
    
    def test_press_arrow_key(self, mock_pyautogui, mock_x11_env):
        """Test pressing arrow keys."""
        result = press_key(key="left")
        
        assert result.success is True
        mock_pyautogui.press.assert_called_once_with("left")
    
    def test_press_function_key(self, mock_pyautogui, mock_x11_env):
        """Test pressing function keys."""
        result = press_key(key="f1")
        
        assert result.success is True
        mock_pyautogui.press.assert_called_once_with("f1")


class TestPressHotkey:
    """Test hotkey combination functionality."""
    
    def test_press_ctrl_c(self, mock_pyautogui, mock_x11_env):
        """Test Ctrl+C hotkey."""
        result = press_hotkey(keys=["ctrl", "c"])
        
        assert result.success is True
        mock_pyautogui.hotkey.assert_called_once_with("ctrl", "c")
    
    def test_press_ctrl_shift_c(self, mock_pyautogui, mock_x11_env):
        """Test Ctrl+Shift+C hotkey."""
        result = press_hotkey(keys=["ctrl", "shift", "c"])
        
        assert result.success is True
        mock_pyautogui.hotkey.assert_called_once_with("ctrl", "shift", "c")
    
    def test_press_alt_tab(self, mock_pyautogui, mock_x11_env):
        """Test Alt+Tab hotkey."""
        result = press_hotkey(keys=["alt", "tab"])
        
        assert result.success is True
        mock_pyautogui.hotkey.assert_called_once_with("alt", "tab")
    
    def test_press_single_key_as_hotkey(self, mock_pyautogui, mock_x11_env):
        """Test single key passed as hotkey."""
        result = press_hotkey(keys=["shift"])
        
        assert result.success is True
        mock_pyautogui.hotkey.assert_called_once_with("shift")


# ============================================================================
# INTEGRATION TESTS (Real Dependencies)
# ============================================================================

class TestRealKeyboard:
    """Integration tests using REAL PyAutoGUI keyboard control."""
    
    @pytest.mark.integration
    @pytest.mark.skip(reason="Skipped by default - actually types keys")
    def test_real_press_shift(self):
        """Test pressing a safe key with real PyAutoGUI."""
        import os
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        result = press_key(key='shift')
        assert result.success is True


# ============================================================================
# GUI INTEGRATION TESTS (Test GUI Application)
# ============================================================================

class TestGUIKeyboard:
    """Test keyboard input with the test GUI."""
    
    @pytest.mark.integration
    def test_type_text_into_field(self, gui_ready, tmp_path):
        """Test typing text into the input field."""
        import os, time
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        from ubuntu_desktop_control.server import take_screenshot, click_screen, type_text
        from PyQt5.QtWidgets import QApplication
        
        screenshot = take_screenshot(detect_elements=True, output_dir=str(tmp_path))
        assert screenshot.success
        
        # Find text field by role (text/entry/edit) or by name
        text_field = None
        for elem in screenshot.elements:
            # Check role first
            if elem.role and ('text' in elem.role.lower() or 'entry' in elem.role.lower() or 'edit' in elem.role.lower()):
                text_field = elem
                break
            # Check name as fallback
            if elem.name and ('type' in elem.name.lower() or 'input' in elem.name.lower()):
                text_field = elem
                break
        
        if not text_field:
            # Print available elements for debugging
            print(f"Available elements: {[(e.name, e.role) for e in screenshot.elements]}")
            pytest.skip("Could not find text field")
        
        click_result = click_screen(element_id=text_field.id)
        assert click_result.success
        
        QApplication.instance().processEvents()
        time.sleep(0.2)
        
        test_text = "Hello MCP Test!"
        type_result = type_text(text=test_text, interval=0.08)  # Slower typing so it's visible
        assert type_result.success
        
        QApplication.instance().processEvents()
        time.sleep(0.5)  # Longer pause to see the result
        
        state = gui_ready.get_state()
        assert test_text in state['text_input'], f"Text not typed! Got: {state['text_input']}"
        print(f"✓ Successfully typed and verified: {state['text_input']}")
    
    @pytest.mark.integration
    def test_copy_paste_workflow(self, gui_ready, tmp_path):
        """Test the full copy-paste workflow."""
        import os
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        from ubuntu_desktop_control.server import press_hotkey
        
        result = press_hotkey(keys=['ctrl', 'c'])
        assert result.success
        print("✓ Hotkey test passed (Ctrl+C)")


class TestGUIHotkeys:
    """Test keyboard hotkey combinations."""
    
    @pytest.mark.integration
    def test_single_hotkey(self, gui_ready):
        """Test single key hotkeys."""
        import os, time
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        from ubuntu_desktop_control.server import press_hotkey
        
        keys_to_test = ['escape', 'tab', 'space', 'enter']
        
        for key in keys_to_test:
            result = press_hotkey(keys=[key])
            assert result.success
            time.sleep(0.2)  # Pause so user can see each key press
        
        print(f"✓ Tested {len(keys_to_test)} single key hotkeys")
    
    @pytest.mark.integration
    def test_modifier_hotkeys(self, gui_ready):
        """Test modifier key combinations."""
        import os, time
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        from ubuntu_desktop_control.server import press_hotkey
        
        hotkeys = [
            (['ctrl', 'c'], 'copy'),
            (['ctrl', 'v'], 'paste'),
            (['ctrl', 'x'], 'cut'),
            (['ctrl', 'a'], 'select all'),
            (['ctrl', 'z'], 'undo'),
            (['ctrl', 'shift', 's'], 'save as'),
            (['alt', 'tab'], 'switch window'),
        ]
        
        for keys, description in hotkeys:
            result = press_hotkey(keys=keys)
            assert result.success
            time.sleep(0.1)
        
        print(f"✓ Tested {len(hotkeys)} modifier hotkey combinations")


class TestGUITypingAdvanced:
    """Advanced keyboard typing tests."""
    
    @pytest.mark.integration
    def test_type_special_characters(self, gui_ready, tmp_path):
        """Test typing special characters and symbols."""
        import os, time
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        from ubuntu_desktop_control.server import take_screenshot, click_screen, type_text, press_hotkey
        from PyQt5.QtWidgets import QApplication
        
        screenshot = take_screenshot(detect_elements=True, output_dir=str(tmp_path))
        assert screenshot.success
        
        # Find text field by role (text/entry/edit) or by name
        text_field = None
        for elem in screenshot.elements:
            # Check role first
            if elem.role and ('text' in elem.role.lower() or 'entry' in elem.role.lower() or 'edit' in elem.role.lower()):
                text_field = elem
                break
            # Check name as fallback
            if elem.name and ('type' in elem.name.lower() or 'input' in elem.name.lower()):
                text_field = elem
                break
        
        if not text_field:
            # Print available elements for debugging
            print(f"Available elements: {[(e.name, e.role) for e in screenshot.elements]}")
            pytest.skip("Could not find text field")
        
        click_result = click_screen(element_id=text_field.id)
        assert click_result.success
        QApplication.instance().processEvents()
        time.sleep(0.2)
        
        special_text = 'Test!@#$%^&*()_+-={}[]|:;"\'<>,.?/'
        result = type_text(text=special_text, interval=0.02)
        assert result.success
        
        QApplication.instance().processEvents()
        time.sleep(0.3)
        
        state = gui_ready.get_state()
        print(f"✓ Typed special characters: {special_text[:20]}...")
    
    @pytest.mark.integration
    def test_type_with_intervals(self, gui_ready, tmp_path):
        """Test typing with different intervals."""
        import os, time
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        from ubuntu_desktop_control.server import type_text
        
        intervals = [0.0, 0.01, 0.05]
        
        for interval in intervals:
            result = type_text(text="Speed test", interval=interval)
            assert result.success
            time.sleep(0.2)
        
        print(f"✓ Tested typing with {len(intervals)} different intervals")
