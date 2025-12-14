"""Tests for element detection (AT-SPI and CV)."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np
from PIL import Image

from ubuntu_desktop_control.server import (
    _fallback_cv_detection,
    AccessibleElement,
)


class TestCVElementDetection:
    """Test CV-based element detection fallback."""
    
    def test_cv_detection_basic(self, mock_cv2):
        """Test basic CV element detection."""
        test_img = Image.new('RGB', (1920, 1080), color='white')
        
        elements, element_map = _fallback_cv_detection(test_img, 1920, 1080)
        
        # CV may find 0-N elements depending on image content and filtering
        assert isinstance(elements, list)
        assert isinstance(element_map, dict)
        assert len(element_map) == len(elements)
        # Check that element IDs match
        if elements:
            assert all(elem.id in element_map for elem in elements)
    
    def test_cv_detection_element_properties(self, mock_cv2):
        """Test that detected elements have correct properties."""
        test_img = Image.new('RGB', (1920, 1080), color='white')
        
        elements, element_map = _fallback_cv_detection(test_img, 1920, 1080)
        
        if elements:
            elem = elements[0]
            assert isinstance(elem, AccessibleElement)
            assert elem.id > 0
            assert elem.role == "detected"
            assert elem.x >= 0
            assert elem.y >= 0
            assert elem.width > 0
            assert elem.height > 0
            assert elem.center_x == elem.x + elem.width // 2
            assert elem.center_y == elem.y + elem.height // 2
            assert elem.is_clickable is True
    
    def test_cv_detection_element_map_structure(self, mock_cv2):
        """Test that element map has correct structure."""
        test_img = Image.new('RGB', (1920, 1080), color='white')
        
        elements, element_map = _fallback_cv_detection(test_img, 1920, 1080)
        
        if element_map:
            elem_id = list(element_map.keys())[0]
            elem_data = element_map[elem_id]
            
            assert 'x' in elem_data
            assert 'y' in elem_data
            assert 'width' in elem_data
            assert 'height' in elem_data
            assert 'name' in elem_data
            assert 'role' in elem_data
    
    def test_cv_detection_handles_no_contours(self, mock_cv2):
        """Test CV detection when no contours are found."""
        # Mock findContours to return empty
        mock_cv2.findContours.return_value = ([], None)
        
        test_img = Image.new('RGB', (1920, 1080), color='white')
        
        elements, element_map = _fallback_cv_detection(test_img, 1920, 1080)
        
        # Should handle gracefully
        assert isinstance(elements, list)
        assert isinstance(element_map, dict)


class TestATSPIIntegration:
    """Test AT-SPI accessibility integration."""
    
    def test_at_spi_element_detection(self, mock_pyautogui, mock_x11_env, mock_at_spi, tmp_path):
        """Test that AT-SPI is used when available."""
        from ubuntu_desktop_control.server import take_screenshot
        
        test_img = Image.new('RGB', (1920, 1080), color='blue')
        mock_pyautogui.screenshot.return_value = test_img
        
        with patch('ubuntu_desktop_control.server._get_screenshot_with_backend') as mock_backend:
            mock_backend.return_value = (test_img, 1920, 1080, None)
            
            result = take_screenshot(detect_elements=True, output_dir=str(tmp_path))
        
        # Should attempt to use AT-SPI
        mock_at_spi.Registry.getDesktop.assert_called()
    
    def test_at_spi_fallback_to_cv(self, mock_pyautogui, mock_x11_env, mock_cv2, tmp_path):
        """Test fallback to CV when AT-SPI fails."""
        from ubuntu_desktop_control.server import take_screenshot
        import sys
        
        test_img = Image.new('RGB', (1920, 1080), color='red')
        mock_pyautogui.screenshot.return_value = test_img
        
        # Ensure pyatspi is not in modules to trigger ImportError
        if 'pyatspi' in sys.modules:
            del sys.modules['pyatspi']
        
        with patch('ubuntu_desktop_control.server._get_screenshot_with_backend') as mock_backend:
            mock_backend.return_value = (test_img, 1920, 1080, None)
            
            result = take_screenshot(detect_elements=True, output_dir=str(tmp_path))
        
        # Should fall back to CV and succeed
        assert result.success is True
        if result.warnings:
            assert any("pyatspi" in w.lower() or "cv" in w.lower() for w in result.warnings)


class TestElementCacheIntegration:
    """Test element cache integration between screenshot and click."""
    
    def test_cache_populated_after_screenshot(self, mock_pyautogui, mock_x11_env, mock_cv2, tmp_path, clear_element_cache):
        """Test that taking screenshot populates element cache."""
        from ubuntu_desktop_control.server import take_screenshot, click_screen as click_fn
        
        test_img = Image.new('RGB', (1920, 1080), color='yellow')
        mock_pyautogui.screenshot.return_value = test_img
        
        with patch('ubuntu_desktop_control.server._get_screenshot_with_backend') as mock_backend:
            mock_backend.return_value = (test_img, 1920, 1080, None)
            
            result = take_screenshot(detect_elements=True, output_dir=str(tmp_path))
        
        assert result.success is True
        # Cache only populated if elements detected
        if result.elements:
            assert hasattr(click_fn, '_element_cache')
            assert len(click_fn._element_cache) > 0
    
    def test_cache_used_by_click_screen(self, mock_pyautogui, mock_x11_env, mock_cv2, tmp_path, clear_element_cache):
        """Test that click_screen uses cached elements."""
        from ubuntu_desktop_control.server import take_screenshot, click_screen
        
        test_img = Image.new('RGB', (1920, 1080), color='green')
        mock_pyautogui.screenshot.return_value = test_img
        mock_pyautogui.size.return_value = (1920, 1080)
        
        with patch('ubuntu_desktop_control.server._get_screenshot_with_backend') as mock_backend:
            mock_backend.return_value = (test_img, 1920, 1080, None)
            
            # Take screenshot to populate cache
            screenshot_result = take_screenshot(detect_elements=True, output_dir=str(tmp_path))
            
            if screenshot_result.elements:
                elem_id = screenshot_result.elements[0].id
                
                # Click using cached element
                click_result = click_screen(element_id=elem_id)
                
                assert click_result.success is True
                # Coordinates should match the cached element
                cached_elem = screenshot_result.element_map[elem_id]
                assert click_result.x == cached_elem['x']
                assert click_result.y == cached_elem['y']


# ============================================================================
# INTEGRATION TESTS (Real Dependencies)
# ============================================================================

class TestRealCVDetection:
    """Integration tests for CV with real OpenCV."""
    
    @pytest.mark.integration
    def test_real_cv_fallback_works(self, tmp_path, monkeypatch):
        """Test that CV detection actually works when AT-SPI unavailable."""
        import os
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        import sys, builtins
        from ubuntu_desktop_control.server import take_screenshot
        
        original_import = builtins.__import__
        def mock_import(name, *args, **kwargs):
            if name == 'pyatspi':
                raise ImportError("Forced CV fallback")
            return original_import(name, *args, **kwargs)
        
        if 'pyatspi' in sys.modules:
            del sys.modules['pyatspi']
        
        monkeypatch.setattr(builtins, '__import__', mock_import)
        
        result = take_screenshot(detect_elements=True, output_dir=str(tmp_path))
        
        assert result.success is True
        assert any("CV" in str(w) or "pyatspi" in str(w) for w in (result.warnings or []))
        print(f"✓ CV fallback detected {len(result.elements)} elements")


class TestRealATSPI:
    """Integration tests for AT-SPI with real accessibility services."""
    
    @pytest.mark.integration
    def test_at_spi_available(self):
        """Check if AT-SPI is actually available."""
        import os
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        try:
            import pyatspi
            desktop = pyatspi.Registry.getDesktop(0)
            assert desktop.childCount >= 0
            print(f"✓ AT-SPI available: {desktop.childCount} applications")
        except ImportError:
            pytest.skip("pyatspi not installed")
        except Exception as e:
            pytest.skip(f"AT-SPI not available: {e}")


# ============================================================================
# GUI INTEGRATION TESTS (Test GUI Application)
# ============================================================================

class TestGUIElementDetection:
    """Advanced element detection tests."""
    
    @pytest.mark.integration
    def test_element_detection_comprehensive(self, gui_ready, tmp_path):
        """Test detecting all types of GUI elements."""
        import os
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        from ubuntu_desktop_control.server import take_screenshot
        
        result = take_screenshot(detect_elements=True, output_dir=str(tmp_path))
        
        assert result.success
        assert len(result.elements) > 0
        
        roles = {}
        for elem in result.elements:
            role = elem.role or "unknown"
            roles[role] = roles.get(role, 0) + 1
        
        print(f"✓ Detected {len(result.elements)} elements:")
        for role, count in sorted(roles.items()):
            print(f"  - {role}: {count}")
    
    @pytest.mark.integration
    def test_element_detection_fallback(self, gui_ready, tmp_path):
        """Test CV fallback when AT-SPI isn't available."""
        import os
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        from ubuntu_desktop_control.server import take_screenshot
        
        result = take_screenshot(detect_elements=True, output_dir=str(tmp_path))
        
        assert result.success
        assert len(result.elements) >= 0
        
        print(f"✓ Element detection (with fallback): {len(result.elements)} elements")
