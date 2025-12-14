"""Tests for diagnostic and utility functions."""

import pytest
from unittest.mock import Mock, patch

from ubuntu_desktop_control.server import (
    get_screen_info,
    get_display_diagnostics,
    ScreenInfo,
    DiagnosticInfo,
)


class TestScreenInfo:
    """Test screen information query."""
    
    def test_get_screen_info_success(self, mock_pyautogui, mock_x11_env):
        """Test successful screen info retrieval."""
        mock_pyautogui.size.return_value = (1920, 1080)
        
        result = get_screen_info()
        
        assert result.success is True
        assert result.width == 1920
        assert result.height == 1080
        assert result.display_server == "x11"
    
    def test_get_screen_info_wayland(self, mock_pyautogui, monkeypatch):
        """Test screen info with Wayland display server."""
        monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
        mock_pyautogui.size.return_value = (2560, 1440)
        
        result = get_screen_info()
        
        assert result.success is True
        assert result.display_server == "wayland"
        assert result.warnings is not None
        assert any("wayland" in w.lower() for w in result.warnings)
    
    def test_get_screen_info_no_pyautogui(self, monkeypatch):
        """Test screen info when PyAutoGUI unavailable."""
        import ubuntu_desktop_control.server as server
        server._pyautogui = None
        server._pyautogui_error = "No display"
        
        result = get_screen_info()
        
        assert result.success is False
        assert result.error == "No display"


class TestDisplayDiagnostics:
    """Test display scaling diagnostics."""
    
    def test_diagnostics_no_scaling(self, mock_pyautogui, mock_x11_env):
        """Test diagnostics when no scaling is present."""
        mock_pyautogui.size.return_value = (1920, 1080)
        
        # Mock screenshot to return same dimensions
        with patch('ubuntu_desktop_control.server._get_screenshot_with_backend') as mock_backend:
            from PIL import Image
            test_img = Image.new('RGB', (1920, 1080), color='white')
            mock_backend.return_value = (test_img, 1920, 1080, None)
            
            result = get_display_diagnostics()
        
        assert result.success is True
        assert result.logical_width == 1920
        assert result.logical_height == 1080
        assert result.actual_screenshot_width == 1920
        assert result.actual_screenshot_height == 1080
        assert result.scaling_factor == 1.0
        assert result.has_scaling_mismatch is False
    
    def test_diagnostics_with_scaling(self, mock_pyautogui, mock_x11_env):
        """Test diagnostics when display scaling is present."""
        mock_pyautogui.size.return_value = (1920, 1080)
        
        # Mock screenshot to return 2x dimensions (HiDPI)
        with patch('ubuntu_desktop_control.server._get_screenshot_with_backend') as mock_backend:
            from PIL import Image
            test_img = Image.new('RGB', (3840, 2160), color='white')
            mock_backend.return_value = (test_img, 3840, 2160, None)
            
            result = get_display_diagnostics()
        
        assert result.success is True
        assert result.logical_width == 1920
        assert result.logical_height == 1080
        assert result.actual_screenshot_width == 3840
        assert result.actual_screenshot_height == 2160
        assert result.scaling_factor == 2.0
        assert result.has_scaling_mismatch is True
        assert result.recommendation is not None
    
    def test_diagnostics_display_server_warning(self, mock_pyautogui, monkeypatch):
        """Test that diagnostics warns about non-X11 display servers."""
        monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
        mock_pyautogui.size.return_value = (1920, 1080)
        
        with patch('ubuntu_desktop_control.server._get_screenshot_with_backend') as mock_backend:
            from PIL import Image
            test_img = Image.new('RGB', (1920, 1080), color='white')
            mock_backend.return_value = (test_img, 1920, 1080, None)
            
            result = get_display_diagnostics()
        
        assert result.success is True
        assert result.display_server == "wayland"
        assert result.warnings is not None
        assert any("wayland" in w.lower() for w in result.warnings)


# ============================================================================
# INTEGRATION TESTS (Real Dependencies)
# ============================================================================

class TestRealScreenInfo:
    """Integration tests using REAL display information."""
    
    @pytest.mark.integration
    def test_real_get_screen_info(self):
        """Test that we can actually get screen dimensions."""
        import os
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        result = get_screen_info()
        
        assert result.success is True
        assert result.width > 0
        assert result.height > 0
        assert result.display_server in ['x11', 'wayland', 'unknown']
    
    @pytest.mark.integration
    def test_real_display_diagnostics(self):
        """Test that diagnostics actually detect scaling."""
        import os
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        result = get_display_diagnostics()
        
        assert result.success is True
        assert result.scaling_factor > 0
        expected_scaling = result.actual_screenshot_width / result.logical_width
        assert abs(result.scaling_factor - expected_scaling) < 0.01


# ============================================================================
# GUI INTEGRATION TESTS (Test GUI Application)
# ============================================================================

class TestGUIScreenInfo:
    """Test screen information retrieval."""
    
    @pytest.mark.integration
    def test_get_screen_info(self, gui_ready):
        """Test getting screen information."""
        import os
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        from ubuntu_desktop_control.server import get_screen_info
        
        result = get_screen_info()
        
        assert result.success
        assert result.width > 0
        assert result.height > 0
        assert result.scaling_factor > 0
        
        print(f"✓ Screen info: {result.width}x{result.height} "
              f"(scale: {result.scaling_factor}, display: {result.display_server})")
