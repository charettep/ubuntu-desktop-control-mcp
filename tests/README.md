# Tests

Each test module contains BOTH types of tests:
1. **Unit Tests** (mocked) - Fast, no dependencies, verify logic
2. **Integration Tests** (real, marked with `@pytest.mark.integration`) - Slower, require X11/display, verify actual functionality

## Test Organization

Tests are organized by feature, with both unit and integration tests in the same file:

- **test_screenshot.py** - Screenshot tests (mocked + real)
- **test_mouse.py** - Mouse control tests (mocked + real)
- **test_keyboard.py** - Keyboard tests (mocked + real keyboard is skipped)
- **test_workflow.py** - Workflow batching tests (mocked + real)
- **test_element_detection.py** - Element detection tests (mocked + real CV/AT-SPI)
- **test_diagnostics.py** - Screen info tests (mocked + real)

## Running Tests

Install pytest and run:

```bash
# Install test dependencies
pip install pytest pytest-cov

# Run ONLY unit tests (fast, mocked, no display needed) - DEFAULT for CI/CD
pytest -m "not integration"

# Run ALL tests (including integration tests that need X11)
DISPLAY=:1 pytest

# Run ONLY integration tests (requires display)
DISPLAY=:1 pytest -m integration

# Run with coverage (unit tests only)
pytest -m "not integration" --cov=ubuntu_desktop_control --cov-report=html

# Run specific test file (both unit and integration)
DISPLAY=:1 pytest tests/test_screenshot.py

# Run only unit tests from specific file
pytest tests/test_screenshot.py -m "not integration"

# Run only integration tests from specific file
DISPLAY=:1 pytest tests/test_screenshot.py -m integration

# Run with verbose output
pytest -v

# Run with output capture disabled (see print statements)
pytest -s
```

## Test Structure

Each test module contains **both unit and integration tests** side-by-side:

### Unit Tests (Mocked - Fast)
- Use fixtures from **conftest.py** (`mock_pyautogui`, `mock_x11_env`, `mock_at_spi`, `mock_cv2`)
- Run without X11/display
- Verify code logic is correct
- Fast (<2 seconds for 56 tests)
- Perfect for CI/CD

### Integration Tests (Real - Requires Display)
- Marked with `@pytest.mark.integration`
- Located at the bottom of each test module
- Use REAL PyAutoGUI, X11, AT-SPI, OpenCV
- Actually interact with the desktop
- Prove end-to-end functionality works
- Catch real-world bugs that mocks miss

## Example: test_screenshot.py

```python
# Top: Unit tests with mocks
class TestTakeScreenshot:
    def test_screenshot_basic_success(self, mock_pyautogui, ...):
        # Fast mocked test

# Bottom: Integration tests with real dependencies  
class TestRealScreenshot:
    @pytest.mark.integration
    def test_real_screenshot_capture(self, tmp_path):
        # Slow real test - actually captures screenshot
```

## Benefits of This Organization

✅ **Co-located**: See both mocked and real tests for each feature in one file  
✅ **Easy comparison**: Compare mocked vs real behavior side-by-side  
✅ **Maintainability**: Update both test types when changing a feature  
✅ **Selective running**: Use markers to run only what you need  

## Test Strategy

**Unit Tests (mocked)**:
- ✅ Fast feedback during development
- ✅ Run in CI/CD without display
- ✅ Verify code logic is correct
- ❌ Don't prove it actually works with real PyAutoGUI/X11

**Integration Tests (real)**:
- ✅ Verify it actually works end-to-end
- ✅ Catch issues with real dependencies (like the CV detection bug!)
- ✅ Prove screenshots, mouse, keyboard actually function
- ❌ Slower (~3 seconds total)
- ❌ Require X11 display
- ⚠️ May move mouse cursor during tests

**Best Practice**: 
- Development: `pytest -m "not integration"` (fast unit tests only)
- Pre-commit: `DISPLAY=:1 pytest` (all tests)
- CI/CD: Unit tests always, integration tests optional

## Coverage Goals

Target: >80% code coverage for core functionality
- Screenshot tools: >90%
- Mouse/keyboard tools: >85%
- Element detection: >75%
- Workflow batching: >80%
