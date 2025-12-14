# System Instructions for Claude (Anthropic)

## ⚠️ CRITICAL: NO SUMMARY DOCUMENTS

**NEVER create summary documents, change logs, or documentation files to track your work.**

❌ **ABSOLUTELY FORBIDDEN:**
- Creating files like `CHANGES.md`, `SUMMARY.md`, `FIX_SUMMARY.md`, `WORK_LOG.md`, `REFACTORING.md`
- Documenting routine changes in new markdown files after completing work
- Creating "summary" files to track what you did
- Adding documentation files unless explicitly requested

✅ **REQUIRED INSTEAD:**
- Communicate all changes, fixes, and progress directly in your response text
- Update existing documentation (README.md, CONTRIBUTING.md) ONLY when it becomes outdated
- Create new documentation files ONLY when user explicitly requests it

The `.claude/` folder exists for architectural decisions and major refactoring documentation, **not** for routine work summaries. If you find yourself wanting to create a summary document, stop and just include that information in your response instead.

---

## Project Context

This is an MCP (Model Context Protocol) server for Ubuntu desktop automation:

**Core Capabilities:**
- Screenshot capture with accessibility element detection (AT-SPI + OpenCV fallback)
- Mouse control: click, move, drag with percentage or absolute coordinates
- Keyboard input: type text, press hotkeys, multi-key combinations
- Workflow execution: batch multiple actions in one MCP call
- Screen diagnostics: resolution, scaling, display server detection

**Technology Stack:**
- Python 3.10+ with FastMCP framework
- PyAutoGUI for input simulation
- AT-SPI (assistive technology) for element detection
- OpenCV as fallback for visual element detection
- Supports both X11 and Wayland display servers

## Claude's Strengths - Leverage Them

### Long-Context Analysis
- Understand entire file contents before making changes
- Trace dependencies across multiple files
- Identify patterns and inconsistencies in large codebases
- Connect related code scattered across the project

### Root Cause Analysis
- Don't just fix symptoms - understand WHY the problem exists
- Trace errors back to their origin (design decisions, API changes, assumptions)
- Identify related issues that might surface later
- Document architectural insights in code comments (not separate files!)

### Systematic Debugging
1. Read error messages and stack traces completely
2. Identify the actual API/data structure being used
3. Compare with test assumptions to find mismatches
4. Fix not just the failing test but all instances of the pattern
5. Verify fixes align with actual implementation

### Pattern Recognition
- Spot recurring mistakes (wrong field names, API misuse)
- Identify where documentation diverges from implementation
- Find similar code that might have the same bug
- Suggest refactorings to prevent future issues

## Implementation Philosophy

### Act, Don't Describe
- Implement changes immediately rather than only suggesting
- Make tool calls (read_file, replace_string_in_file) directly
- If user intent is unclear, infer most useful action and proceed
- Continue until request is completely resolved
- Don't stop when uncertain - research and deduce the right approach

### Verify Assumptions
- Never trust comments or old documentation - read the actual code
- Check real API signatures before using them
- Grep for actual usage patterns in the codebase
- Trace imports to find the source of truth

### Multi-Step Tasks
- Use manage_todo_list for complex work
- Mark tasks in-progress before starting
- Mark completed immediately after finishing each one
- Provide brief progress updates between parallel operations

## Testing Philosophy

### Realistic GUI Tests
GUI tests must simulate actual LLM agent behavior:

**The Pattern:**
1. **Discover** - Take screenshot with element detection
2. **Analyze** - Search elements by role, name, or position
3. **Act** - Use element IDs or percentage coordinates
4. **Verify** - Check state or take another screenshot

**Example:**
```python
# 1. DISCOVER
screenshot = take_screenshot(detect_elements=True)
assert screenshot.success

# 2. ANALYZE
submit_button = None
for elem in screenshot.elements:
    if elem.role == 'button' and 'Submit' in elem.name:
        # Found it!
        submit_button = elem
        break

if not submit_button:
    # Provide debugging output
    print(f"Available elements: {[(e.name, e.role) for e in screenshot.elements]}")
    pytest.skip("Could not find submit button")

# 3. ACT
click_result = click_screen(element_id=submit_button.id)
assert click_result.success

# 4. VERIFY
time.sleep(0.2)  # Allow GUI to update
state = gui_ready.get_state()
assert state['form_submitted'] == True
```

### Why This Matters
- Tests prove the MCP tools work for real AI agents
- Agents can't hardcode coordinates - they must discover elements
- Element detection is the critical capability that makes automation possible
- If tests don't follow this pattern, they're not testing the real use case

### Test Organization
- **Unit tests**: Test individual functions in isolation
- **Integration tests**: Test tool interactions and workflows
- **GUI tests**: Test with real GUI using `gui_ready` fixture
- **GUI components**: Only in `tests/gui/` (test app, dialogs, runner)
- **Actual tests**: In `tests/test_*.py` files

## API Reference - Know The Truth

### Critical: Verify Before Using
Don't trust documentation or assumptions. Always check actual code:

```bash
# Find the real function signature
grep -n "def drag_mouse" server.py

# Find the real model fields
grep -n "class ScreenInfo" server.py
```

### Known Correct APIs

**ScreenInfo Model:**
```python
class ScreenInfo:
    width: int           # Screen width in pixels
    height: int          # Screen height in pixels
    display_server: str  # "x11" or "wayland"
    scaling_factor: float
```
❌ NOT `logical_width` or `logical_height` (those are in DiagnosticInfo)

**drag_mouse Function:**
```python
def drag_mouse(
    x: int,              # Target X (absolute coordinate)
    y: int,              # Target Y (absolute coordinate)
    button: str = "left",
    duration: float = 0.5
) -> MouseClickResult:
```
❌ NOT `x_offset`, `y_offset`, `to_x`, or `to_y`
✅ Parameters are TARGET coordinates (where to drag TO)
✅ Starts from current mouse position

**Workflow Actions:**
```python
Supported: "screenshot", "click", "move", "type", "wait"
```
❌ NOT `"move_mouse"` - use `"move"`
✅ Wait uses `"duration"` parameter, not `"seconds"`

### Common Pitfalls

1. **Confusing DiagnosticInfo with ScreenInfo**
   - DiagnosticInfo: `logical_width`, `logical_height`, `actual_screenshot_width`
   - ScreenInfo: `width`, `height`, `scaling_factor`

2. **Assuming offset parameters exist**
   - Many GUI libraries use offsets, but this API uses absolute coordinates

3. **Not checking actual implementation**
   - Comments and docs can be outdated
   - Read the source code to be certain

## Code Quality

### Python Standards
- Type hints on all function parameters and returns
- Docstrings with Args and Returns sections
- Meaningful variable names (not single letters except i, j in loops)
- Keep functions under 50 lines when possible
- One responsibility per function

### Error Handling in MCP Tools
```python
@server.tool()
def my_tool(param: str) -> ResultModel:
    """Tool description."""
    try:
        # Implementation
        return ResultModel(success=True, data=result)
    except Exception as e:
        return ResultModel(
            success=False,
            error=f"Failed: {str(e)}"
        )
```

- Never raise exceptions to MCP client
- Always return result model with success field
- Provide helpful error messages
- Include warnings array for non-fatal issues

## Debugging Workflow

### Systematic Approach
1. **Read the error completely** - don't skim
2. **Identify the failing line** - look at stack trace
3. **Check assumptions** - grep for actual API/model definitions
4. **Find all instances** - don't just fix one occurrence
5. **Understand root cause** - why did this happen?
6. **Verify the fix** - read affected code to ensure correctness

### Environment Issues
- Check `DISPLAY` environment variable for X11
- Check `WAYLAND_DISPLAY` for Wayland
- Verify AT-SPI daemon is running: `ps aux | grep at-spi`
- Check system dependencies are installed

## File Organization

```
ubuntu-desktop-control-mcp/
├── server.py                    # Main MCP server implementation
├── tests/
│   ├── conftest.py              # Pytest fixtures
│   ├── test_screenshot.py       # Screenshot tool tests + GUI tests
│   ├── test_mouse.py            # Mouse tool tests + GUI tests
│   ├── test_keyboard.py         # Keyboard tool tests + GUI tests
│   ├── test_workflow.py         # Workflow tool tests + GUI tests
│   ├── test_diagnostics.py      # Diagnostic tool tests + GUI tests
│   └── gui/                     # GUI components ONLY
│       ├── test_gui_app.py      # Main test window
│       ├── test_dialogs.py      # Test selector and report dialogs
│       └── test_runner_helper.py # Test discovery and execution
├── client-config/               # Configuration examples
│   ├── Claude Code/
│   ├── Codex/
│   └── VS Code/
└── prompts/                     # Example prompts for using MCP server
```

## Key Commands

```bash
# Activate virtual environment
source .venv/bin/activate

# Run all tests
pytest

# Run with coverage
pytest --cov=ubuntu_desktop_control --cov-report=html

# Run GUI test application
DISPLAY=:1 python3 tests/gui/test_gui_app.py

# Check for syntax errors
python3 -m py_compile tests/test_*.py

# Install system dependencies
bash install_system_deps.sh
```

## Remember

### Primary Rules
1. **Never create summary documents** - communicate directly in responses
2. **Verify all assumptions** - read actual code, not comments
3. **Follow realistic test patterns** - discover elements, don't hardcode
4. **Fix root causes** - understand why, not just what
5. **Act immediately** - implement, don't just suggest

### When In Doubt
- Grep for the actual function/class definition
- Read the implementation, not just the docstring
- Check how it's used elsewhere in the codebase
- Test your assumptions before making changes

### Quality Over Speed
- Understand the full context before editing
- Fix all instances of a problem, not just one
- Ensure changes align with project architecture
- Leave the code better than you found it
