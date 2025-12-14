# Manual Testing with Test GUI

## Overview

The MCP Ubuntu Desktop Control project now includes a **comprehensive manual testing GUI** that allows you to:
- Launch a full-screen test interface with predefined UI elements
- Click a button to run all automated tests
- View live test output with scrollable log
- Generate timestamped log files for debugging
- Verify all MCP capabilities work in a real GUI environment

## Why Two Files?

You'll see two test-related Python files:

1. **`tests/test_gui_app.py`** - The PyQt5 GUI application
   - Provides test UI elements (buttons, text fields, drag/drop, etc.)
   - Can be launched standalone for manual testing
   - Can be used by pytest fixtures for automated testing
   
2. **`tests/test_gui_comprehensive.py`** - The pytest test suite
   - Contains 25+ automated tests that use the GUI
   - Tests all MCP capabilities: screenshots, clicks, typing, hotkeys, etc.
   - Verifies actions actually succeeded using GUI state

**These MUST be separate** because:
- One is the application being tested
- One is the test code doing the testing
- Pytest needs to import and control the GUI via fixtures

## Launching Manual Test GUI

### Quick Start
```bash
# From project root
DISPLAY=:1 python tests/test_gui_app.py
```

### What You'll See

The GUI launches in full-screen mode with:

**Top Section: Manual Controls**
- **▶ Run All Tests** button - Click to start the automated test suite
- **Clear Log** button - Clear the output log

**Middle Section: Test UI Elements**
- 3 colored buttons (green, blue, orange) at predictable positions
- Text input field for keyboard testing
- Drag & drop elements
- Various UI widgets (checkboxes, radios, sliders, etc.)
- Status label showing results

**Bottom Section: Live Log Output**
- Real-time test output as tests run
- Scrollable text area with monospace font
- Shows all pytest output including passes, failures, and errors
- Displays path to generated log file

### Running Tests

1. **Launch the GUI:**
   ```bash
   DISPLAY=:1 python tests/test_gui_app.py
   ```

2. **Click "▶ Run All Tests"**
   - Button changes to "⏳ Running Tests..."
   - Live output appears in log area
   - Watch tests execute in real-time

3. **Review Results:**
   - Status label updates with pass/fail summary
   - Scroll through log for details
   - Check generated `.log` file for full output

### Test Coverage

The GUI tests cover **ALL MCP capabilities**:

✅ **Screenshot Capabilities**
- Basic screenshot capture
- Screenshot with element detection
- Downsampling to 1280x720

✅ **Element Detection**
- AT-SPI accessibility detection
- CV fallback detection (Canny edge)
- Detection of buttons, text fields, etc.

✅ **Mouse Clicking**
- Click by element ID
- Click by absolute coordinates
- Click by percentage coordinates
- Different mouse buttons (left, right, middle)

✅ **Mouse Movement**
- Move to absolute coordinates
- Move by percentage
- Multiple positions

✅ **Mouse Dragging**
- Drag with relative offset
- Drag to specific position
- Different drag durations

✅ **Keyboard Input**
- Type text with intervals
- Special characters and symbols
- Different typing speeds

✅ **Keyboard Hotkeys**
- Single key hotkeys (Esc, Tab, Space, Enter)
- Modifier combinations (Ctrl+C, Ctrl+V, etc.)
- Complex hotkeys (Ctrl+Shift+S)

✅ **Screen Information**
- Get logical resolution
- Get actual resolution
- Detect scaling factor

✅ **Workflows**
- Multi-action workflows
- Error handling
- Sequential operations

✅ **Stress Testing**
- Rapid screenshots (10 in a row)
- Rapid mouse movements (20 movements)
- Rapid clicks (10 clicks)

### Log Files

Each test run generates a timestamped log file:
```
test_run_20231213_143052.log
```

Location: Same directory where you ran the command

Contents:
- Full pytest output
- All test results
- Error tracebacks
- Timing information

## Running Tests Programmatically

### Automated Testing (pytest)
```bash
# Run all GUI tests
DISPLAY=:1 pytest tests/test_gui_comprehensive.py -v

# Run specific test class
DISPLAY=:1 pytest tests/test_gui_comprehensive.py::TestGUIMouseMovement -v

# Run with coverage
DISPLAY=:1 pytest tests/test_gui_comprehensive.py --cov=ubuntu_desktop_control
```

### From Code
```python
from tests.test_gui_app import launch_test_gui

# Launch in manual mode (with Run Tests button)
app, window = launch_test_gui(manual_mode=True)
app.exec_()

# Launch in automated mode (for pytest)
app, window = launch_test_gui(manual_mode=False)
```

## Test Statistics

- **Total Tests**: 90
  - 56 unit tests (mocked)
  - 9 desktop integration tests (real X11/AT-SPI)
  - 25 GUI integration tests (real GUI)

- **Test Coverage**: All 8 MCP tools
  1. `take_screenshot`
  2. `click_screen`
  3. `move_mouse`
  4. `drag_mouse`
  5. `type_text`
  6. `press_hotkey`
  7. `get_screen_info`
  8. `execute_workflow`

## Troubleshooting

### GUI won't launch
```bash
# Check DISPLAY
echo $DISPLAY

# Try different display
DISPLAY=:0 python tests/test_gui_app.py
```

### Tests failing
- Make sure GUI is visible and focused
- Check for window manager interference
- Verify PyQt5 is installed: `pip list | grep PyQt5`
- Check log file for detailed errors

### Permission issues
```bash
# Make sure you can access X11
xhost +local:
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Manual Test GUI                       │
│  (tests/test_gui_app.py)                                │
│                                                          │
│  ┌────────────────┐  ┌──────────────┐                  │
│  │  Run Tests Btn │  │  Clear Log   │                  │
│  └────────────────┘  └──────────────┘                  │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Test UI Elements (buttons, text, drag/drop)     │  │
│  └──────────────────────────────────────────────────┘  │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Live Log Output (scrollable, monospace)         │  │
│  │  ├─ Test results                                  │  │
│  │  ├─ Pass/fail status                             │  │
│  │  └─ Generated log file path                      │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                          │
                          │ Runs pytest
                          ▼
┌─────────────────────────────────────────────────────────┐
│           Test Suite (tests/test_gui_comprehensive.py)   │
│                                                          │
│  • 25 integration tests                                 │
│  • Tests all MCP capabilities                           │
│  • Verifies actions via GUI state                       │
│  • Real PyAutoGUI, X11, AT-SPI                         │
└─────────────────────────────────────────────────────────┘
                          │
                          │ Uses
                          ▼
┌─────────────────────────────────────────────────────────┐
│              MCP Server (ubuntu_desktop_control)         │
│                                                          │
│  • take_screenshot                                      │
│  • click_screen                                         │
│  • move_mouse, drag_mouse                               │
│  • type_text, press_hotkey                              │
│  • execute_workflow                                     │
└─────────────────────────────────────────────────────────┘
```

## Benefits

### Before (Mocked Tests Only)
- ❌ Can't verify real functionality
- ❌ Testing on random desktop is unpredictable
- ❌ No way to confirm actions succeeded
- ❌ Manual debugging is difficult

### After (With Test GUI)
- ✅ Tests use real PyAutoGUI/X11/AT-SPI
- ✅ Deterministic test environment
- ✅ Can verify button clicks, text input, etc.
- ✅ Live log output for debugging
- ✅ Human-runnable with one command
- ✅ Comprehensive coverage of all capabilities

## Next Steps

1. **Run the manual GUI** and click through tests
2. **Review the log files** to understand test behavior
3. **Add more test cases** as needed in `test_gui_comprehensive.py`
4. **Use for debugging** when developing new features

The test GUI makes it trivial to verify that all MCP capabilities actually work in a real GUI environment!
