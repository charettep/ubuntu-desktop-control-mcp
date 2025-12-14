"""
Test GUI Application for Integration Testing

This PyQt5 app provides a controlled environment for testing all MCP capabilities:
- Buttons at known positions for click testing
- Text fields for keyboard input testing
- Drag & drop for mouse drag testing
- Labels to verify actions succeeded
- Various UI elements for detection testing

Can be used in two modes:
1. Automated: Launched by pytest fixtures for automated testing
2. Manual: Run directly to get a GUI with "Run Tests" button and live log output
"""

import sys
import os
import subprocess
import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QLabel, 
    QLineEdit, QTextEdit, QVBoxLayout, QHBoxLayout, QGridLayout,
    QCheckBox, QRadioButton, QComboBox, QSlider, QProgressBar,
    QSplitter, QScrollArea
)
from PyQt5.QtCore import Qt, QMimeData, QPoint, QThread, pyqtSignal
from PyQt5.QtGui import QDrag, QPalette, QColor, QTextCursor


class DraggableLabel(QLabel):
    """Label that can be dragged."""
    
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("background-color: lightblue; padding: 10px; border: 2px solid blue;")
        self.setFixedSize(100, 50)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.pos()
    
    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            return
        
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(self.text())
        drag.setMimeData(mime_data)
        drag.exec_(Qt.MoveAction)


class DropZone(QLabel):
    """Label that accepts drops."""
    
    def __init__(self, parent=None):
        super().__init__("Drop Here", parent)
        self.setAcceptDrops(True)
        self.setStyleSheet("background-color: lightgray; padding: 20px; border: 2px dashed gray;")
        self.setFixedSize(200, 100)
        self.setAlignment(Qt.AlignCenter)
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
            self.setStyleSheet("background-color: lightgreen; padding: 20px; border: 2px dashed green;")
    
    def dragLeaveEvent(self, event):
        self.setStyleSheet("background-color: lightgray; padding: 20px; border: 2px dashed gray;")
    
    def dropEvent(self, event):
        self.setText(f"Dropped: {event.mimeData().text()}")
        self.setStyleSheet("background-color: lightgreen; padding: 20px; border: 2px solid green;")
        event.acceptProposedAction()


class TestRunner(QThread):
    """Thread to run pytest tests without blocking the GUI."""
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(int, int, int)  # passed, failed, skipped
    
    def __init__(self, test_file=None):
        super().__init__()
        self.test_file = test_file or "tests/test_gui_comprehensive.py"
        self.log_file = None
        
    def run(self):
        """Run pytest and emit log output."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = f"test_run_{timestamp}.log"
        
        self.log_signal.emit(f"=== Starting Test Run at {datetime.datetime.now()} ===\n")
        self.log_signal.emit(f"Log file: {self.log_file}\n")
        self.log_signal.emit(f"Test file: {self.test_file}\n\n")
        
        try:
            # Run pytest with verbose output
            cmd = [
                sys.executable, "-m", "pytest",
                self.test_file,
                "-v", "-s",
                "--tb=short",
                f"--log-file={self.log_file}"
            ]
            
            self.log_signal.emit(f"Command: {' '.join(cmd)}\n\n")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            passed = failed = skipped = 0
            
            for line in process.stdout:
                self.log_signal.emit(line)
                
                # Parse test results
                if " PASSED" in line:
                    passed += 1
                elif " FAILED" in line:
                    failed += 1
                elif " SKIPPED" in line:
                    skipped += 1
            
            process.wait()
            
            self.log_signal.emit(f"\n=== Test Run Complete ===\n")
            self.log_signal.emit(f"Results: {passed} passed, {failed} failed, {skipped} skipped\n")
            self.log_signal.emit(f"Full log saved to: {self.log_file}\n")
            
            self.finished_signal.emit(passed, failed, skipped)
            
        except Exception as e:
            self.log_signal.emit(f"\nERROR: {str(e)}\n")
            self.finished_signal.emit(0, 0, 0)


class TestGUIApp(QMainWindow):
    """Main test GUI application with all testable elements."""
    
    def __init__(self, manual_mode=False):
        super().__init__()
        self.manual_mode = manual_mode
        self.test_runner = None
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle('🎯 MCP TEST GUI - WATCH THIS WINDOW 🎯')
        
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        
        # If in manual mode, create split view with test controls and log
        if self.manual_mode:
            splitter = QSplitter(Qt.Vertical)
            
            # Top: Test elements
            test_elements_widget = QWidget()
            layout = QVBoxLayout(test_elements_widget)
            
            # Manual mode controls at the very top
            controls_layout = QHBoxLayout()
            
            self.run_tests_btn = QPushButton('▶ Run All Tests')
            self.run_tests_btn.setFixedHeight(50)
            self.run_tests_btn.setStyleSheet(
                "background-color: #4CAF50; color: white; font-size: 16px; font-weight: bold;"
            )
            self.run_tests_btn.clicked.connect(self.run_tests)
            controls_layout.addWidget(self.run_tests_btn)
            
            self.clear_log_btn = QPushButton('Clear Log')
            self.clear_log_btn.setFixedHeight(50)
            self.clear_log_btn.clicked.connect(self.clear_log)
            controls_layout.addWidget(self.clear_log_btn)
            
            layout.addLayout(controls_layout)
            
            # Add test elements below
            self.add_test_elements(layout)
            
            splitter.addWidget(test_elements_widget)
            
            # Bottom: Log output
            log_widget = QWidget()
            log_layout = QVBoxLayout(log_widget)
            
            log_label = QLabel('Test Output Log:')
            log_label.setStyleSheet("font-size: 14px; font-weight: bold;")
            log_layout.addWidget(log_label)
            
            self.log_output = QTextEdit()
            self.log_output.setReadOnly(True)
            self.log_output.setStyleSheet(
                "background-color: #1E1E1E; color: #D4D4D4; font-family: monospace; font-size: 11px;"
            )
            log_layout.addWidget(self.log_output)
            
            splitter.addWidget(log_widget)
            splitter.setSizes([400, 400])  # Initial split
            
            main_layout.addWidget(splitter)
            
            self.append_log("GUI Ready. Click 'Run All Tests' to start testing.\n")
            self.append_log(f"Working directory: {os.getcwd()}\n\n")
        else:
            # Automated mode - just test elements
            layout = main_layout
            self.add_test_elements(layout)
    
    def add_test_elements(self, layout):
        
        # =================================================================
        # Section 1: Click Testing (Top-left area)
        # =================================================================
        click_section = QHBoxLayout()
        
        # Button 1 - Top-left corner (predictable position)
        self.btn_topleft = QPushButton('Click Me (Top-Left)', self)
        self.btn_topleft.setFixedSize(200, 60)
        self.btn_topleft.setStyleSheet("background-color: #4CAF50; font-size: 14px; font-weight: bold;")
        self.btn_topleft.clicked.connect(lambda: self.button_clicked('topleft'))
        click_section.addWidget(self.btn_topleft)
        
        # Button 2 - Top-center
        self.btn_center = QPushButton('Click Me (Center)', self)
        self.btn_center.setFixedSize(200, 60)
        self.btn_center.setStyleSheet("background-color: #2196F3; font-size: 14px; font-weight: bold;")
        self.btn_center.clicked.connect(lambda: self.button_clicked('center'))
        click_section.addWidget(self.btn_center)
        
        # Button 3 - Top-right
        self.btn_topright = QPushButton('Click Me (Top-Right)', self)
        self.btn_topright.setFixedSize(200, 60)
        self.btn_topright.setStyleSheet("background-color: #FF9800; font-size: 14px; font-weight: bold;")
        self.btn_topright.clicked.connect(lambda: self.button_clicked('topright'))
        click_section.addWidget(self.btn_topright)
        
        # Result label for click testing
        self.click_result = QLabel('No button clicked yet')
        self.click_result.setStyleSheet("font-size: 16px; padding: 10px; background-color: yellow;")
        self.click_result.setFixedHeight(50)
        
        layout.addLayout(click_section)
        layout.addWidget(self.click_result)
        
        # =================================================================
        # Section 2: Keyboard Testing (Text Input)
        # =================================================================
        keyboard_section = QVBoxLayout()
        
        keyboard_label = QLabel('Keyboard Testing:')
        keyboard_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 20px;")
        keyboard_section.addWidget(keyboard_label)
        
        # Text input field for typing
        self.text_input = QLineEdit(self)
        self.text_input.setPlaceholderText('Type here or paste text (CTRL+V)')
        self.text_input.setFixedHeight(50)
        self.text_input.setStyleSheet("font-size: 16px; padding: 5px;")
        self.text_input.textChanged.connect(self.text_input_changed)
        keyboard_section.addWidget(self.text_input)
        
        # Text with selectable content for copy testing
        self.copy_source = QLabel('Select and copy this text: TESTDATA123')
        self.copy_source.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.copy_source.setStyleSheet("font-size: 14px; padding: 10px; background-color: #E3F2FD; border: 1px solid blue;")
        keyboard_section.addWidget(self.copy_source)
        
        # Result label for keyboard testing
        self.keyboard_result = QLabel('Text input: (empty)')
        self.keyboard_result.setStyleSheet("font-size: 14px; padding: 10px; background-color: #FFF3E0;")
        keyboard_section.addWidget(self.keyboard_result)
        
        layout.addLayout(keyboard_section)
        
        # =================================================================
        # Section 3: Drag & Drop Testing
        # =================================================================
        drag_section = QHBoxLayout()
        
        drag_label = QLabel('Drag & Drop Testing:')
        drag_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 20px;")
        layout.addWidget(drag_label)
        
        # Draggable item
        self.draggable = DraggableLabel('Drag Me!', self)
        drag_section.addWidget(self.draggable)
        
        # Drop zone
        self.drop_zone = DropZone(self)
        drag_section.addWidget(self.drop_zone)
        
        drag_section.addStretch()
        layout.addLayout(drag_section)
        
        # =================================================================
        # Section 4: Various UI Elements (for detection testing)
        # =================================================================
        elements_section = QGridLayout()
        
        elements_label = QLabel('UI Elements (for detection):')
        elements_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 20px;")
        layout.addWidget(elements_label)
        
        # Checkbox
        self.checkbox = QCheckBox('Test Checkbox', self)
        self.checkbox.setStyleSheet("font-size: 12px;")
        elements_section.addWidget(self.checkbox, 0, 0)
        
        # Radio buttons
        self.radio1 = QRadioButton('Option 1', self)
        self.radio2 = QRadioButton('Option 2', self)
        elements_section.addWidget(self.radio1, 0, 1)
        elements_section.addWidget(self.radio2, 0, 2)
        
        # Combo box
        self.combo = QComboBox(self)
        self.combo.addItems(['Item 1', 'Item 2', 'Item 3'])
        elements_section.addWidget(self.combo, 1, 0)
        
        # Slider
        self.slider = QSlider(Qt.Horizontal, self)
        self.slider.setMinimum(0)
        self.slider.setMaximum(100)
        self.slider.setValue(50)
        elements_section.addWidget(self.slider, 1, 1, 1, 2)
        
        # Progress bar
        self.progress = QProgressBar(self)
        self.progress.setValue(75)
        elements_section.addWidget(self.progress, 2, 0, 1, 3)
        
        layout.addLayout(elements_section)
        
        # =================================================================
        # Section 5: Test Status Display
        # =================================================================
        self.status_label = QLabel('Status: Ready for testing')
        self.status_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; padding: 15px; "
            "background-color: #4CAF50; color: white; margin-top: 20px;"
        )
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Add log output area for automated mode too
        if not self.manual_mode:
            self.log_output = QTextEdit(self)
            self.log_output.setReadOnly(True)
            self.log_output.setMaximumHeight(150)
            self.log_output.setStyleSheet(
                "background-color: #1E1E1E; color: #D4D4D4; "
                "font-family: 'Courier New', monospace; font-size: 11px; padding: 5px;"
            )
            layout.addWidget(self.log_output)
        
        # Store state for verification
        self.last_button_clicked = None
        self.last_text_input = ""
        self.drop_received = False
        
        # Set window properties - keep as normal window for visibility
        # Don't maximize or fullscreen automatically - let caller decide
    
    def append_log(self, text):
        """Append text to log output."""
        if self.manual_mode and hasattr(self, 'log_output'):
            self.log_output.append(text)
            self.log_output.moveCursor(QTextCursor.End)
            QApplication.processEvents()
    
    def clear_log(self):
        """Clear the log output."""
        if self.manual_mode and hasattr(self, 'log_output'):
            self.log_output.clear()
            self.append_log("Log cleared.\n\n")
    
    def run_tests(self):
        """Run the pytest test suite."""
        if self.test_runner and self.test_runner.isRunning():
            self.append_log("Tests are already running!\n")
            return
        
        self.run_tests_btn.setEnabled(False)
        self.run_tests_btn.setText("⏳ Running Tests...")
        self.append_log("\n" + "="*80 + "\n")
        
        # Create and start test runner thread
        self.test_runner = TestRunner()
        self.test_runner.log_signal.connect(self.append_log)
        self.test_runner.finished_signal.connect(self.tests_finished)
        self.test_runner.start()
    
    def tests_finished(self, passed, failed, skipped):
        """Handle test completion."""
        self.run_tests_btn.setEnabled(True)
        self.run_tests_btn.setText("▶ Run All Tests")
        
        # Update status label
        total = passed + failed + skipped
        if failed == 0:
            color = "#4CAF50"  # Green
            status = "✓ ALL TESTS PASSED"
        else:
            color = "#F44336"  # Red
            status = f"✗ {failed} TEST(S) FAILED"
        
        self.status_label.setStyleSheet(
            f"font-size: 18px; font-weight: bold; padding: 15px; "
            f"background-color: {color}; color: white;"
        )
        self.status_label.setText(
            f"{status} | Total: {total} | Passed: {passed} | Failed: {failed} | Skipped: {skipped}"
        )
        
    def button_clicked(self, button_name):
        """Handle button clicks and update state."""
        self.last_button_clicked = button_name
        self.click_result.setText(f'Button clicked: {button_name.upper()}')
        self.click_result.setStyleSheet(
            f"font-size: 16px; padding: 10px; background-color: #4CAF50; color: white;"
        )
        self.status_label.setText(f'✓ Button "{button_name}" was clicked successfully!')
        
        # Force immediate visual update
        self.click_result.repaint()
        self.status_label.repaint()
        QApplication.processEvents()
        
    def text_input_changed(self, text):
        """Handle text input changes."""
        self.last_text_input = text
        self.keyboard_result.setText(f'Text input: {text if text else "(empty)"}')
        if text:
            self.keyboard_result.setStyleSheet(
                "font-size: 14px; padding: 10px; background-color: #4CAF50; color: white;"
            )
    
    def get_state(self):
        """Get current state for verification in tests."""
        return {
            'last_button_clicked': self.last_button_clicked,
            'text_input': self.text_input.text(),
            'checkbox_checked': self.checkbox.isChecked(),
            'slider_value': self.slider.value(),
            'combo_current': self.combo.currentText(),
            'drop_zone_text': self.drop_zone.text(),
        }


def launch_test_gui(manual_mode=False):
    """Launch the test GUI application.
    
    Args:
        manual_mode: If True, launches with manual testing UI (Run Tests button, log output)
                    If False, launches basic GUI for automated pytest testing
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    window = TestGUIApp(manual_mode=manual_mode)
    window.show()
    
    return app, window


if __name__ == '__main__':
    # When run directly, show test selector dialog first
    print("Launching MCP Integration Test Suite...")
    
    from tests.gui.test_dialogs import TestSelectorDialog, TestReportDialog
    from tests.gui.test_runner_helper import discover_gui_tests, run_selected_tests
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # Step 1: Show test selector dialog
    available_tests = discover_gui_tests()
    selector = TestSelectorDialog(available_tests)
    
    if selector.exec_() != TestSelectorDialog.Accepted:
        print("Test execution cancelled by user.")
        sys.exit(0)
    
    selected_tests = selector.selected_tests
    print(f"User selected {len(selected_tests)} tests to run.")
    
    # Step 2: Launch test GUI in a visible window (not fullscreen to avoid overlap)
    window = TestGUIApp(manual_mode=False)
    window.resize(1200, 800)
    window.move(100, 100)  # Position away from edges
    window.show()
    window.raise_()  # Bring to front
    window.activateWindow()  # Make it the active window
    app.processEvents()
    
    import time
    time.sleep(0.5)  # Give window time to fully render
    
    # Step 3: Add progress indicator to GUI
    window.status_label.setText(f"Running {len(selected_tests)} tests...")
    window.status_label.setStyleSheet(
        "font-size: 16px; font-weight: bold; padding: 15px; "
        "background-color: #2196F3; color: white;"
    )
    app.processEvents()
    
    # Step 4: Set up progress tracking
    window.progress.setMaximum(len(selected_tests))
    window.progress.setValue(0)
    
    def progress_callback(msg):
        # Extract test number from message like "[3/24] Running..."
        import re
        match = re.match(r'\[(\d+)/\d+\]', msg)
        if match:
            test_num = int(match.group(1))
            window.progress.setValue(test_num)
        
        # Update status label
        window.status_label.setText(msg)
        window.status_label.repaint()
        
        # Add to log output
        if hasattr(window, 'log_output'):
            window.log_output.append(msg)
            window.log_output.moveCursor(QTextCursor.End)
        
        app.processEvents()
    
    # Run selected tests
    results = run_selected_tests(selected_tests, progress_callback)
    
    # Step 5: Show completion message briefly
    passed = sum(1 for _, p, _, _, _ in results if p)
    failed = len(results) - passed
    window.status_label.setText(f"Tests complete! {passed} passed, {failed} failed")
    window.status_label.setStyleSheet(
        f"font-size: 16px; font-weight: bold; padding: 15px; "
        f"background-color: {'#4CAF50' if failed == 0 else '#F44336'}; color: white;"
    )
    window.status_label.repaint()
    app.processEvents()
    
    # Give user a moment to see the final status
    import time
    time.sleep(1.0)
    
    # Step 6: Close test GUI
    window.close()
    app.processEvents()
    
    # Step 7: Show results dialog
    report = TestReportDialog(results)
    report.show()
    report.raise_()
    report.activateWindow()
    
    # Run event loop until dialog closes
    app.exec_()
    
    sys.exit(0)
