"""Pytest configuration and shared fixtures."""

import os
import sys
from unittest.mock import Mock, MagicMock
import pytest
from PIL import Image
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture
def mock_pyautogui(monkeypatch):
    """Mock PyAutoGUI to avoid X11 dependencies."""
    mock_pag = Mock()
    mock_pag.size.return_value = (1920, 1080)
    mock_pag.position.return_value = (960, 540)
    mock_pag.click = Mock()
    mock_pag.moveTo = Mock()
    mock_pag.dragTo = Mock()
    mock_pag.write = Mock()
    mock_pag.press = Mock()
    mock_pag.hotkey = Mock()
    
    # Mock screenshot
    mock_screenshot = Mock()
    mock_screenshot.size = (1920, 1080)
    mock_screenshot.save = Mock()
    mock_screenshot.crop = Mock(return_value=mock_screenshot)
    mock_screenshot.copy = Mock(return_value=mock_screenshot)
    mock_screenshot.resize = Mock(return_value=mock_screenshot)
    mock_pag.screenshot.return_value = mock_screenshot
    
    # Inject into the module's lazy loader
    import ubuntu_desktop_control.server as server
    server._pyautogui = mock_pag
    server._pyautogui_error = None
    
    return mock_pag


@pytest.fixture
def mock_x11_env(monkeypatch):
    """Mock X11 environment variables."""
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setenv("XAUTHORITY", "/home/user/.Xauthority")
    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")


@pytest.fixture
def sample_screenshot():
    """Create a sample screenshot image for testing."""
    # Create a simple test image
    img = Image.new('RGB', (1920, 1080), color='white')
    return img


@pytest.fixture
def mock_at_spi(monkeypatch):
    """Mock AT-SPI (accessibility) for element detection."""
    mock_pyatspi = MagicMock()
    
    # Mock desktop
    mock_desktop = MagicMock()
    mock_desktop.childCount = 2
    
    # Mock application
    mock_app = MagicMock()
    mock_app.childCount = 3
    mock_app.name = "Test App"
    mock_app.getRoleName.return_value = "application"
    
    # Mock button element
    mock_button = MagicMock()
    mock_button.name = "OK Button"
    mock_button.getRoleName.return_value = "push button"
    mock_button.childCount = 0
    mock_button.component = MagicMock()
    
    # Mock extents
    mock_extents = MagicMock()
    mock_extents.x = 100
    mock_extents.y = 200
    mock_extents.width = 80
    mock_extents.height = 30
    mock_button.component.getExtents.return_value = mock_extents
    
    # Setup hierarchy
    mock_desktop.getChildAtIndex = Mock(side_effect=lambda i: mock_app if i == 0 else MagicMock())
    mock_app.getChildAtIndex = Mock(side_effect=lambda i: mock_button if i == 0 else MagicMock())
    
    mock_pyatspi.Registry.getDesktop.return_value = mock_desktop
    mock_pyatspi.DESKTOP_COORDS = 0
    
    # Inject mock
    sys.modules['pyatspi'] = mock_pyatspi
    
    yield mock_pyatspi
    
    # Cleanup
    if 'pyatspi' in sys.modules:
        del sys.modules['pyatspi']


@pytest.fixture
def mock_cv2(monkeypatch):
    """Mock OpenCV for CV-based element detection."""
    mock_cv = MagicMock()
    
    # Mock findContours to return some test contours
    contour1 = np.array([[[100, 100]], [[200, 100]], [[200, 200]], [[100, 200]]])
    contour2 = np.array([[[300, 300]], [[400, 300]], [[400, 400]], [[300, 400]]])
    mock_cv.findContours.return_value = ([contour1, contour2], None)
    
    # Mock boundingRect
    mock_cv.boundingRect.side_effect = lambda c: (
        (100, 100, 100, 100) if len(c) == 4 else (300, 300, 100, 100)
    )
    
    # Mock other functions
    mock_cv.cvtColor.return_value = np.zeros((1080, 1920), dtype=np.uint8)
    mock_cv.adaptiveThreshold.return_value = np.zeros((1080, 1920), dtype=np.uint8)
    mock_cv.morphologyEx.return_value = np.zeros((1080, 1920), dtype=np.uint8)
    mock_cv.ones.return_value = np.ones((5, 5), dtype=np.uint8)
    
    # Color conversion constants
    mock_cv.COLOR_RGB2BGR = 4
    mock_cv.COLOR_BGR2GRAY = 6
    mock_cv.ADAPTIVE_THRESH_GAUSSIAN_C = 1
    mock_cv.THRESH_BINARY_INV = 1
    mock_cv.MORPH_CLOSE = 3
    mock_cv.RETR_EXTERNAL = 0
    mock_cv.CHAIN_APPROX_SIMPLE = 2
    
    sys.modules['cv2'] = mock_cv
    
    yield mock_cv
    
    if 'cv2' in sys.modules:
        del sys.modules['cv2']


@pytest.fixture
def clear_element_cache():
    """Clear element cache between tests."""
    from ubuntu_desktop_control.server import click_screen
    if hasattr(click_screen, '_element_cache'):
        delattr(click_screen, '_element_cache')
    yield
    if hasattr(click_screen, '_element_cache'):
        delattr(click_screen, '_element_cache')


# ============================================================================
# Test GUI Fixtures (for comprehensive integration testing)
# ============================================================================

@pytest.fixture(scope='session')
def test_gui_app():
    """Launch the test GUI application for integration tests.
    
    This provides a controlled, deterministic GUI environment for testing
    all MCP capabilities with real PyAutoGUI, AT-SPI, and user interactions.
    """
    import os
    if not os.environ.get('DISPLAY'):
        pytest.skip("No DISPLAY available - cannot launch test GUI")
    
    try:
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtCore import QTimer
    except ImportError:
        pytest.skip("PyQt5 not installed - cannot launch test GUI")
    
    from tests.gui.test_gui_app import launch_test_gui
    import time
    
    # Launch GUI in separate thread
    app, window = launch_test_gui()
    
    # Process events to ensure window is fully rendered
    app.processEvents()
    time.sleep(1)  # Give window time to fully render
    
    yield {'app': app, 'window': window}
    
    # Cleanup
    window.close()
    app.quit()


@pytest.fixture
def gui_ready(test_gui_app):
    """Ensure test GUI is ready and process pending events."""
    import time
    app = test_gui_app['app']
    window = test_gui_app['window']
    
    # Ensure window is visible and on top
    window.raise_()
    window.activateWindow()
    
    # Process all pending events
    app.processEvents()
    
    # Reset window state for test
    window.last_button_clicked = None
    window.text_input.clear()
    window.click_result.setText('No button clicked yet')
    window.click_result.setStyleSheet("font-size: 16px; padding: 10px; background-color: yellow;")
    
    app.processEvents()
    
    # Small delay so user can see the GUI state before test starts
    time.sleep(0.3)
    
    yield window
    
    # Process events after test and pause so user can see result
    app.processEvents()
    time.sleep(0.3)
