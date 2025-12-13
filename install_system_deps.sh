#!/bin/bash
# Installation script for Ubuntu Desktop Control MCP Server system dependencies

echo "Installing system dependencies for Ubuntu Desktop Control MCP Server..."
echo ""

# Check if running on Ubuntu/Debian
if ! command -v apt &> /dev/null; then
    echo "Error: This script requires apt package manager (Ubuntu/Debian)"
    exit 1
fi

# Check display server
DISPLAY_SERVER="${XDG_SESSION_TYPE:-unknown}"
echo "Detected display server: $DISPLAY_SERVER"

if [ "$DISPLAY_SERVER" != "x11" ]; then
    echo "Warning: This server is designed for X11. You're running $DISPLAY_SERVER"
    echo "PyAutoGUI may not work properly on Wayland."
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Install packages
echo ""
echo "Installing required packages..."
sudo apt update
sudo apt install -y \
    python3-xlib \
    python3-tk \
    python3-dev \
    scrot \
    gnome-screenshot

echo ""
echo "✓ System dependencies installed successfully!"
echo ""
echo "Next steps:"
echo "1. Activate the virtual environment:"
echo "   source .venv/bin/activate"
echo "2. Test the server:"
echo "   python3 test_server.py"
echo "3. Configure your MCP client (see config-examples/)"
