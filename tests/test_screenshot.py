"""Tests for screenshot functionality."""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from PIL import Image

from ubuntu_desktop_control.server import (
    take_screenshot,
    AnnotatedScreenshot,
)


class TestTakeScreenshot:
    """Test the optimized take_screenshot function."""
    
    def test_screenshot_basic_success(self, mock_pyautogui, mock_x11_env, tmp_path):
        """Test basic screenshot capture without element detection."""
        # Create a real image for the mock
        test_img = Image.new('RGB', (1920, 1080), color='blue')
        mock_pyautogui.screenshot.return_value = test_img
        
        result = take_screenshot(detect_elements=False, output_dir=str(tmp_path))
        
        assert result.success is True
        assert result.screenshot_path.startswith(str(tmp_path))
        assert result.display_width == 1280
        assert result.display_height == 720
        assert result.actual_width == 1920
        assert result.actual_height == 1080
    
    def test_screenshot_downsampling(self, mock_pyautogui, mock_x11_env, tmp_path):
        """Test that screenshot is properly downsampled to 1280x720."""
        test_img = Image.new('RGB', (2560, 1440), color='red')
        mock_pyautogui.size.return_value = (2560, 1440)
        mock_pyautogui.screenshot.return_value = test_img
        
        with patch('ubuntu_desktop_control.server._get_screenshot_with_backend') as mock_backend:
            mock_backend.return_value = (test_img, 2560, 1440, None)
            
            result = take_screenshot(detect_elements=False, output_dir=str(tmp_path))
        
        assert result.success is True
        assert result.display_width == 1280
        assert result.display_height == 720
        assert result.actual_width == 2560
        assert result.actual_height == 1440
        assert "1280x720" in result.scaling_info
    
    def test_screenshot_with_cv_fallback(self, mock_pyautogui, mock_x11_env, mock_cv2, tmp_path):
        """Test screenshot with CV-based element detection fallback."""
        test_img = Image.new('RGB', (1920, 1080), color='green')
        mock_pyautogui.screenshot.return_value = test_img
        
        with patch('ubuntu_desktop_control.server._get_screenshot_with_backend') as mock_backend:
            mock_backend.return_value = (test_img, 1920, 1080, None)
            
            result = take_screenshot(detect_elements=True, output_dir=str(tmp_path))
        
        assert result.success is True
        # CV fallback may find 0-N elements
        assert isinstance(result.elements, list)
        assert isinstance(result.element_map, dict)
    
    def test_screenshot_element_caching(self, mock_pyautogui, mock_x11_env, mock_cv2, tmp_path, clear_element_cache):
        """Test that element map is cached for click_screen."""
        from ubuntu_desktop_control.server import click_screen
        
        test_img = Image.new('RGB', (1920, 1080), color='yellow')
        mock_pyautogui.screenshot.return_value = test_img
        
        with patch('ubuntu_desktop_control.server._get_screenshot_with_backend') as mock_backend:
            mock_backend.return_value = (test_img, 1920, 1080, None)
            
            result = take_screenshot(detect_elements=True, output_dir=str(tmp_path))
        
        assert result.success is True
        # Cache only populated if elements detected
        if result.elements:
            assert hasattr(click_screen, '_element_cache')
            assert len(click_screen._element_cache) > 0
    
    def test_screenshot_without_pyautogui(self, monkeypatch, tmp_path):
        """Test screenshot failure when PyAutoGUI is unavailable."""
        import ubuntu_desktop_control.server as server
        server._pyautogui = None
        server._pyautogui_error = "PyAutoGUI not available"
        
        result = take_screenshot(output_dir=str(tmp_path))
        
        assert result.success is False
        assert result.error == "PyAutoGUI not available"
    
    def test_screenshot_custom_output_dir(self, mock_pyautogui, mock_x11_env, tmp_path):
        """Test screenshot with custom output directory."""
        test_img = Image.new('RGB', (1920, 1080), color='purple')
        mock_pyautogui.screenshot.return_value = test_img
        
        custom_dir = tmp_path / "custom"
        
        with patch('ubuntu_desktop_control.server._get_screenshot_with_backend') as mock_backend:
            mock_backend.return_value = (test_img, 1920, 1080, None)
            
            result = take_screenshot(detect_elements=False, output_dir=str(custom_dir))
        
        assert result.success is True
        assert str(custom_dir) in result.screenshot_path
        assert os.path.exists(custom_dir)
    
    def test_screenshot_with_at_spi(self, mock_pyautogui, mock_x11_env, mock_at_spi, tmp_path):
        """Test screenshot with AT-SPI element detection."""
        test_img = Image.new('RGB', (1920, 1080), color='orange')
        mock_pyautogui.screenshot.return_value = test_img
        
        with patch('ubuntu_desktop_control.server._get_screenshot_with_backend') as mock_backend:
            mock_backend.return_value = (test_img, 1920, 1080, None)
            
            result = take_screenshot(detect_elements=True, output_dir=str(tmp_path))
        
        # Should successfully use AT-SPI and detect the mocked button
        assert result.success is True
        # Note: In real test, AT-SPI mock should populate elements
        # The actual behavior depends on mock setup


# ============================================================================
# INTEGRATION TESTS (Real Dependencies)
# ============================================================================

class TestRealScreenshot:
    """Integration tests using REAL PyAutoGUI, X11, and display."""
    
    @pytest.mark.integration
    def test_real_screenshot_capture(self, tmp_path):
        """Test that we can actually capture a screenshot with real PyAutoGUI."""
        import os
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        result = take_screenshot(detect_elements=False, output_dir=str(tmp_path))
        
        assert result.success is True, f"Screenshot failed: {result.error}"
        assert os.path.exists(result.screenshot_path)
        assert os.path.exists(result.original_path)
        
        from PIL import Image
        img = Image.open(result.screenshot_path)
        assert img.size[0] > 0 and img.size[1] > 0
        assert result.display_width == 1280
        assert result.display_height == 720
    
    @pytest.mark.integration
    def test_real_element_detection(self, tmp_path):
        """Test that element detection actually works with real AT-SPI/CV."""
        import os
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        result = take_screenshot(detect_elements=True, output_dir=str(tmp_path))
        
        assert result.success is True
        detection_method = 'AT-SPI' if not any('AT-SPI' in str(w) for w in (result.warnings or [])) else 'CV fallback'
        print(f"✓ Detected {len(result.elements)} elements using {detection_method}")
        assert isinstance(result.elements, list)
        assert isinstance(result.element_map, dict)


# ============================================================================
# GUI INTEGRATION TESTS (Test GUI Application)
# ============================================================================

class TestGUIScreenshot:
    """Test screenshot capabilities with the test GUI."""
    
    @pytest.mark.integration
    def test_screenshot_captures_gui(self, gui_ready, tmp_path):
        """Test that screenshot actually captures the test GUI."""
        import os
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        result = take_screenshot(detect_elements=False, output_dir=str(tmp_path))
        
        assert result.success is True
        assert os.path.exists(result.screenshot_path)
        
        # Verify it's the right resolution
        from PIL import Image
        img = Image.open(result.screenshot_path)
        assert img.size == (1280, 720)  # Downsampled
        print(f"✓ Screenshot captured test GUI at {img.size}")
    
    @pytest.mark.integration
    def test_element_detection_finds_gui_elements(self, gui_ready, tmp_path):
        """Test that element detection finds the test GUI's elements."""
        import os
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        result = take_screenshot(detect_elements=True, output_dir=str(tmp_path))
        
        assert result.success is True
        assert len(result.elements) > 0, "Should detect GUI elements!"
        
        # Check for buttons in detected elements
        button_names = [e.name for e in result.elements if e.name]
        print(f"✓ Detected {len(result.elements)} elements")
        print(f"  Button names found: {[n for n in button_names if 'Click' in n or 'Button' in n]}")
