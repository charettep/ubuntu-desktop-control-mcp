# Repository Guidelines

## Project Structure & Module Organization
- `server.py`: FastMCP server exposing desktop control tools (screenshots, clicks, movement, scaling diagnostics).
- `test_server.py`: Smoke test that imports the tools, captures a screenshot, and moves the mouse.
- `config-examples/`: Ready-to-copy client configs for Claude Code, Codex, and VS Code MCP integrations.
- Docs: `README.md`, `QUICKSTART.md`, and `INSTALL_COMMANDS.md` cover install, usage, and scaling notes.

## Build, Test, and Development Commands
```bash
# setup (if not already): create/activate venv and install editable
python3 -m venv .venv && source .venv/bin/activate
pip install -e .[dev]

# run server with MCP inspector
npx @modelcontextprotocol/inspector python3 server.py

# quick verification
python3 test_server.py
```
- Use `pip install mss` for faster screenshots; falls back to PyAutoGUI otherwise.

## Coding Style & Naming Conventions
- Python 3.9+; follow PEP 8 with 4-space indentation and type hints for tool inputs/outputs.
- Prefer explicit function names for MCP tools (`take_screenshot`, `click_screen`, `move_mouse`) and keep return shapes as Pydantic models for clarity.
- Add short docstrings for new tools and reuse the lazy import/error-handling patterns already in `server.py`.

## Testing Guidelines
- Primary check: `python3 test_server.py` (requires X11 and screenshot capability). Run after dependency changes or new tool additions.
- For additional coverage, wrap new logic in small unit helpers and add `pytest`-style assertions to `test_server.py` (pytest is available via `[dev]` extras).
- Ensure tests tolerate missing optional backends by surfacing warnings instead of raising where possible.

## Commit & Pull Request Guidelines
- Write imperative, specific subjects (e.g., `Add scaling warning to screenshot result`). Include a short body when behavior changes or dependencies shift.
- In PRs, describe the scenario you tested (`test_server.py` output, MCP inspector runs) and note any environment constraints (X11 vs Wayland, required packages).
- Update docs/config snippets when adding or renaming tools so config examples stay accurate.

## Security & Configuration Tips
- The server assumes X11; Wayland may block screenshots/clicks—note this in reviews and test on X11 when validating changes.
- Avoid embedding secrets in sample configs; paths in `config-examples/` should remain generic or point to the local venv binary only.
- When modifying coordinate handling, call out any scaling assumptions so downstream clients can adjust.
