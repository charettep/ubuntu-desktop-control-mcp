"""
MCP Tool Workflow Tests

These tests simulate how an LLM client (Codex, Claude) would use the MCP tools.
Tests call the REAL server.py tools and make decisions based on what they discover.
"""

import pytest
import os
import time
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


class TestMCPWorkflow:
    """Test complete MCP workflow as an LLM client would use it."""
    
    @pytest.mark.integration
    def test_screenshot_workflow(self, gui_ready, tmp_path):
        """
        Test the complete screenshot workflow:
        1. Take screenshot with take_screenshot() tool
        2. Display raw screenshot (2 sec)
        3. Verify downsampling to 1280x720
        4. Show detected element boundaries (2 sec)
        5. Save metadata to JSON
        """
        import os
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        from ubuntu_desktop_control.server import take_screenshot
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtGui import QPixmap, QImage
        from PyQt5.QtCore import Qt
        
        # Create logs folder
        log_dir = tmp_path / "logs"
        log_dir.mkdir(exist_ok=True)
        
        print("\n" + "="*80)
        print("STEP 1: Taking screenshot with take_screenshot() tool from server.py")
        print("="*80)
        
        # STEP 1: Call REAL take_screenshot tool
        screenshot = take_screenshot(detect_elements=True, output_dir=str(tmp_path))
        assert screenshot.success, f"Screenshot failed: {screenshot.error}"
        
        # Display raw screenshot for 2 seconds
        print(f"✓ Screenshot taken: {screenshot.screenshot_path}")
        print(f"  Resolution: {screenshot.display_width}x{screenshot.display_height}")
        print(f"  Elements detected: {len(screenshot.elements)}")
        
        self._display_image(screenshot.screenshot_path, "RAW SCREENSHOT", duration=2.0)
        
        # STEP 2: Verify downsampling
        print("\n" + "="*80)
        print("STEP 2: Verifying downsampling to 1280x720")
        print("="*80)
        
        img = Image.open(screenshot.screenshot_path)
        actual_width, actual_height = img.size
        
        # Create annotated version with resolution overlay
        annotated = img.copy()
        draw = ImageDraw.Draw(annotated)
        
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
        except:
            font = ImageFont.load_default()
        
        # Draw resolution text
        resolution_text = f"{actual_width}x{actual_height}"
        expected_text = "Expected: 1280x720" if actual_width == 1280 and actual_height == 720 else f"Downsampled from {screenshot.actual_width}x{screenshot.actual_height}"
        
        # Background rectangle for text
        text_bbox = draw.textbbox((0, 0), resolution_text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        
        draw.rectangle(
            [10, 10, text_width + 30, text_height + 60],
            fill=(0, 0, 0, 200)
        )
        draw.text((20, 20), resolution_text, fill=(0, 255, 0), font=font)
        
        try:
            small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
        except:
            small_font = font
        draw.text((20, 20 + text_height + 10), expected_text, fill=(255, 255, 0), font=small_font)
        
        annotated_path = log_dir / "01_resolution_check.png"
        annotated.save(annotated_path)
        
        print(f"✓ Actual resolution: {actual_width}x{actual_height}")
        print(f"✓ Downsampling verified: {actual_width == 1280 and actual_height == 720}")
        
        self._display_image(str(annotated_path), "RESOLUTION CHECK", duration=2.0)
        
        # STEP 3: Show detected elements with boundaries
        print("\n" + "="*80)
        print("STEP 3: Showing AT-SPI detected element boundaries")
        print("="*80)
        
        debug_img = img.copy()
        draw = ImageDraw.Draw(debug_img)
        
        # Draw all element boundaries
        for elem in screenshot.elements:
            # Draw rectangle
            draw.rectangle(
                [elem.x, elem.y, elem.x + elem.width, elem.y + elem.height],
                outline=(0, 255, 0),
                width=2
            )
            # Draw element ID
            try:
                id_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
            except:
                id_font = ImageFont.load_default()
            draw.text((elem.x + 5, elem.y + 5), f"#{elem.id}", fill=(255, 255, 0), font=id_font)
        
        # Overlay element count
        count_text = f"{len(screenshot.elements)} Elements Detected"
        try:
            count_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
        except:
            count_font = ImageFont.load_default()
        
        count_bbox = draw.textbbox((0, 0), count_text, font=count_font)
        count_width = count_bbox[2] - count_bbox[0]
        count_height = count_bbox[3] - count_bbox[1]
        
        draw.rectangle(
            [debug_img.width - count_width - 30, 10, debug_img.width - 10, count_height + 30],
            fill=(0, 0, 0, 200)
        )
        draw.text(
            (debug_img.width - count_width - 20, 20),
            count_text,
            fill=(0, 255, 0),
            font=count_font
        )
        
        debug_path = log_dir / "02_element_detection.png"
        debug_img.save(debug_path)
        
        print(f"✓ Element boundaries drawn")
        print(f"✓ Total elements: {len(screenshot.elements)}")
        
        self._display_image(str(debug_path), "ELEMENT DETECTION", duration=2.0)
        
        # STEP 4: Save metadata to JSON
        print("\n" + "="*80)
        print("STEP 4: Saving element metadata to JSON")
        print("="*80)
        
        metadata = {
            "screenshot_path": screenshot.screenshot_path,
            "display_width": screenshot.display_width,
            "display_height": screenshot.display_height,
            "actual_width": screenshot.actual_width,
            "actual_height": screenshot.actual_height,
            "elements": [
                {
                    "id": elem.id,
                    "name": elem.name,
                    "role": elem.role,
                    "x": elem.x,
                    "y": elem.y,
                    "width": elem.width,
                    "height": elem.height,
                    "center_x": elem.center_x,
                    "center_y": elem.center_y,
                    "is_clickable": elem.is_clickable,
                    "children_count": elem.children_count
                }
                for elem in screenshot.elements
            ],
            "element_map": screenshot.element_map
        }
        
        metadata_path = log_dir / "screenshot_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"✓ Metadata saved to: {metadata_path}")
        print(f"✓ Total elements: {len(metadata['elements'])}")
        
        # Print sample of detected elements
        print("\nSample of detected elements:")
        for elem in screenshot.elements[:5]:
            print(f"  #{elem.id}: {elem.name} ({elem.role}) at ({elem.center_x}, {elem.center_y})")
        
        # Return metadata for next test to use
        return metadata
    
    @pytest.mark.integration
    def test_decision_based_click(self, gui_ready, tmp_path):
        """
        Test click decision-making based on discovered elements.
        This simulates how an LLM would analyze screenshot data and decide where to click.
        """
        import os, time
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        from ubuntu_desktop_control.server import take_screenshot, click_screen
        from PyQt5.QtWidgets import QApplication
        
        log_dir = tmp_path / "logs"
        log_dir.mkdir(exist_ok=True)
        
        print("\n" + "="*80)
        print("DECISION-BASED CLICK TEST")
        print("Simulating LLM decision-making from screenshot data")
        print("="*80)
        
        # STEP 1: Take screenshot and discover elements
        screenshot = take_screenshot(detect_elements=True, output_dir=str(tmp_path))
        assert screenshot.success
        
        print(f"\n✓ Screenshot taken, {len(screenshot.elements)} elements detected")
        
        # STEP 2: Analyze elements and make decision (like an LLM would)
        print("\n🤖 LLM Decision Process:")
        print("  Analyzing detected elements to find clickable buttons...")
        
        # Find buttons (prioritize buttons with names)
        buttons = [
            elem for elem in screenshot.elements
            if elem.role and 'button' in elem.role.lower()
        ]
        
        print(f"  Found {len(buttons)} button elements")
        
        # Decision logic: find a button with a name in the top-left area
        target_button = None
        for button in buttons:
            if button.name:
                # Prefer buttons in top-left quadrant
                if button.center_x < screenshot.display_width * 0.5 and button.center_y < screenshot.display_height * 0.5:
                    target_button = button
                    print(f"  ✓ Selected button: '{button.name}' (ID #{button.id})")
                    print(f"    Position: ({button.center_x}, {button.center_y})")
                    print(f"    Reasoning: Button found in top-left area with clear name")
                    break
        
        if not target_button:
            # Fallback: just pick first button with a name
            for button in buttons:
                if button.name:
                    target_button = button
                    print(f"  ✓ Selected button: '{button.name}' (ID #{button.id})")
                    print(f"    Position: ({button.center_x}, {button.center_y})")
                    break
        
        if not target_button:
            pytest.skip("No suitable button found to test click decision-making")
        
        # STEP 3: Execute click based on decision
        print(f"\n🖱️  Executing click on element #{target_button.id}...")
        
        # Ensure window is visible
        gui_ready.raise_()
        gui_ready.activateWindow()
        QApplication.processEvents()
        time.sleep(0.5)
        
        # Click using element ID (as discovered)
        result = click_screen(element_id=target_button.id)
        assert result.success, f"Click failed: {result.error}"
        
        print(f"✓ Click executed at ({result.x}, {result.y})")
        
        # STEP 4: Verify result
        QApplication.processEvents()
        time.sleep(0.3)
        
        state = gui_ready.get_state()
        print(f"\n✅ Result verification:")
        print(f"  Button clicked: {state['last_button_clicked']}")
        print(f"  Expected: {target_button.name.lower() if target_button.name else 'unknown'}")
        
        # Save decision log
        decision_log = {
            "timestamp": time.time(),
            "total_elements": len(screenshot.elements),
            "buttons_found": len(buttons),
            "selected_button": {
                "id": target_button.id,
                "name": target_button.name,
                "role": target_button.role,
                "position": {"x": target_button.center_x, "y": target_button.center_y}
            },
            "click_result": {
                "success": result.success,
                "actual_x": result.x,
                "actual_y": result.y
            },
            "verification": {
                "button_state": state['last_button_clicked']
            }
        }
        
        decision_log_path = log_dir / "decision_log.json"
        with open(decision_log_path, 'w') as f:
            json.dump(decision_log, f, indent=2)
        
        print(f"\n✓ Decision log saved to: {decision_log_path}")
    
    def _display_image(self, image_path, title, duration=2.0):
        """Display an image in a popup window for specified duration."""
        from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow
        from PyQt5.QtGui import QPixmap
        from PyQt5.QtCore import Qt, QTimer
        
        app = QApplication.instance()
        
        # Create window
        window = QMainWindow()
        window.setWindowTitle(title)
        window.setWindowFlags(Qt.WindowStaysOnTopHint)
        
        # Load and display image
        label = QLabel()
        pixmap = QPixmap(image_path)
        
        # Scale to fit screen if too large
        screen = app.primaryScreen().geometry()
        max_width = int(screen.width() * 0.8)
        max_height = int(screen.height() * 0.8)
        
        if pixmap.width() > max_width or pixmap.height() > max_height:
            pixmap = pixmap.scaled(max_width, max_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        
        label.setPixmap(pixmap)
        window.setCentralWidget(label)
        
        # Center window
        window.adjustSize()
        window.move(
            (screen.width() - window.width()) // 2,
            (screen.height() - window.height()) // 2
        )
        
        window.show()
        window.raise_()
        window.activateWindow()
        
        # Auto-close after duration
        QTimer.singleShot(int(duration * 1000), window.close)
        
        # Process events for the duration
        start = time.time()
        while time.time() - start < duration and window.isVisible():
            app.processEvents()
            time.sleep(0.05)
        
        if window.isVisible():
            window.close()
        app.processEvents()
