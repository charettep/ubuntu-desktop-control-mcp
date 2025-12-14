# System Instructions for OpenAI Agents

## ⚠️ CRITICAL: NO SUMMARY DOCUMENTS

**NEVER create summary documents, change logs, or documentation files to track your work.**

❌ **FORBIDDEN:**
- Creating files like `CHANGES.md`, `SUMMARY.md`, `FIX_SUMMARY.md`, `WORK_LOG.md`
- Documenting routine changes in new markdown files
- Creating "summary" files after completing tasks
- Adding files to document what you just did

✅ **REQUIRED:**
- Communicate all changes directly in your response text
- Only update existing documentation when it becomes outdated
- Only create new documentation files when explicitly requested by user

The `.claude/` folder is for architectural decisions and major refactoring docs ONLY, not routine work summaries.

---

## Project Context

This is an MCP (Model Context Protocol) server for Ubuntu desktop control. It provides tools for:
- Screenshot capture with element detection (AT-SPI + OpenCV)
- Mouse control (click, move, drag)
- Keyboard input (type text, hotkeys)
- Workflow execution (batched multi-step operations)
- Screen diagnostics

## Code Quality Standards

### Implementation Focus
- Implement changes rather than only suggesting them
- If user intent is unclear, infer the most useful action and proceed
- Make tool calls (file edits, reads) immediately rather than describing them
- Continue working until request is completely resolved

### Python Best Practices
- Use type hints for all function parameters and returns
- Follow PEP 8 style guidelines
- Keep functions focused and single-purpose
- Use meaningful variable names (no single letters except loop counters)

### Testing Requirements
- Write tests for all new functionality
- Use pytest with fixtures from `conftest.py`
- Maintain 3-layer test structure: unit → integration → GUI
- GUI tests must use realistic screenshot-based element discovery

## MCP Tool Development

### Tool Patterns
```python
@server.tool()
def tool_name(
    required_param: Type,
    optional_param: Type = default
) -> ResultModel:
    """Concise one-line description.
    
    Detailed explanation of what the tool does,
    when to use it, and important behaviors.
    
    Args:
        required_param: Description
        optional_param: Description (default: value)
    
    Returns:
        ResultModel with success status and data
    """
    # Implementation
```

### Error Handling
- Always return result models, never raise exceptions to client
- Set `success=False` and populate `error` field
- Include helpful error messages for debugging
- Collect environment warnings (DISPLAY, WAYLAND, etc.)

## Testing Guidelines

### Realistic GUI Tests
All GUI tests must follow the real LLM workflow:

1. **Take Screenshot** with element detection:
   ```python
   screenshot = take_screenshot(detect_elements=True)
   ```

2. **Find Elements** by role, name, or position:
   ```python
   button = None
   for elem in screenshot.elements:
       if elem.role == 'button' and 'Submit' in elem.name:
           button = elem
           break
   ```

3. **Interact** using element IDs (not hardcoded coords):
   ```python
   click_screen(element_id=button.id)
   ```

4. **Verify** the action succeeded:
   ```python
   state = gui_ready.get_state()
   assert state['expected_result']
   ```

### Test Organization
- Unit tests in `tests/test_*.py` - test individual functions
- Integration tests in same files - test tool interactions
- GUI tests in `tests/test_*.py` using `gui_ready` fixture
- GUI components only in `tests/gui/` folder

## Debugging Workflow

1. Check error messages and stack traces
2. Verify environment variables (DISPLAY, WAYLAND_DISPLAY)
3. Test with minimal reproducible case
4. Use print statements or logging for diagnostics
5. Check system dependencies (at-spi2-core, xdotool, pyautogui)

## API Reference Quick Guide

### Correct Usage
✅ `ScreenInfo.width` and `.height`
✅ `drag_mouse(x=target_x, y=target_y)` - absolute coordinates
✅ Workflow action: `"move"` (not "move_mouse")
✅ Workflow wait: `{"action": "wait", "duration": 0.5}`

### Common Mistakes
❌ `ScreenInfo.logical_width` - doesn't exist (use `width`)
❌ `drag_mouse(x_offset=100)` - no offset params (use absolute x, y)
❌ `drag_mouse(to_x=100)` - no to_x param (use x, y)
❌ Workflow action: `"move_mouse"` - use `"move"`
❌ Workflow wait: `"seconds"` param - use `"duration"`

## File Organization

- `server.py` - Main MCP server with all tools
- `tests/` - All test files
- `tests/gui/` - GUI components only (test app, dialogs, runner)
- `client-config/` - Configuration examples for different clients
- `prompts/` - Prompt examples for using the MCP server

## Key Commands

```bash
# Run all tests
pytest

# Run GUI tests with test application
DISPLAY=:1 python3 tests/gui/test_gui_app.py

# Run with coverage
pytest --cov=ubuntu_desktop_control --cov-report=html

# Install system dependencies
bash install_system_deps.sh
```

## Remember

- **Never create summary documents** - communicate changes in responses
- Implement changes immediately rather than suggesting
- Use realistic element discovery in GUI tests
- Follow the 3-layer test structure
- Always use correct API signatures (check actual code, not assumptions)
