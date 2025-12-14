#!/bin/bash
# Quick launcher for the MCP Integration Test GUI

# Detect display
if [ -z "$DISPLAY" ]; then
    echo "No DISPLAY environment variable set."
    echo "Trying common displays..."
    
    for disp in :0 :1; do
        if xdpyinfo -display $disp >/dev/null 2>&1; then
            export DISPLAY=$disp
            echo "Using DISPLAY=$DISPLAY"
            break
        fi
    done
    
    if [ -z "$DISPLAY" ]; then
        echo "ERROR: Could not find a running X11 display"
        echo "Please set DISPLAY manually, e.g.: DISPLAY=:1 $0"
        exit 1
    fi
fi

echo "========================================"
echo "MCP Integration Test GUI"
echo "========================================"
echo ""
echo "This will launch a full-screen GUI with:"
echo "  - Test UI elements (buttons, text fields, etc.)"
echo "  - 'Run All Tests' button"
echo "  - Live log output"
echo "  - Log file generation"
echo ""
echo "Press ESC to exit fullscreen"
echo "Close window to quit"
echo ""
echo "Starting..."
echo ""

# Activate venv if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Run the GUI
python tests/test_gui_app.py
