"""
Test Selection and Report Dialogs

This module provides GUI dialogs for:
1. Test selection before running (with checkboxes)
2. Detailed test report after completion
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QTextEdit, QSplitter,
    QCheckBox, QWidget, QScrollArea, QGroupBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class TestSelectorDialog(QDialog):
    """Dialog for selecting which tests to run."""
    
    def __init__(self, available_tests, parent=None):
        super().__init__(parent)
        self.available_tests = available_tests  # List of (module, class, test_name, description)
        self.selected_tests = []
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle('MCP Test Suite - Select Tests to Run')
        self.setMinimumSize(800, 600)
        
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel('Select Tests to Execute')
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Instructions
        instructions = QLabel(
            'Check the tests you want to run. The test GUI will launch and execute them.'
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #666; padding: 10px;")
        layout.addWidget(instructions)
        
        # Select All / Deselect All buttons
        select_buttons = QHBoxLayout()
        self.select_all_btn = QPushButton('✓ Select All')
        self.select_all_btn.clicked.connect(self.select_all)
        select_buttons.addWidget(self.select_all_btn)
        
        self.deselect_all_btn = QPushButton('✗ Deselect All')
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        select_buttons.addWidget(self.deselect_all_btn)
        
        select_buttons.addStretch()
        layout.addLayout(select_buttons)
        
        # Test list with checkboxes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        self.test_checkboxes = []
        current_class = None
        
        for module, test_class, test_name, description in self.available_tests:
            # Group by test class
            class_key = f"{module}.{test_class}"
            if class_key != current_class:
                current_class = class_key
                class_label = QLabel(f"\n{test_class}")
                class_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #2196F3;")
                scroll_layout.addWidget(class_label)
            
            # Checkbox for each test
            checkbox = QCheckBox(f"{test_name}")
            checkbox.setChecked(True)  # Default: all selected
            checkbox.setToolTip(description)
            checkbox.setStyleSheet("padding: 5px;")
            
            # Store test info with checkbox
            checkbox.test_info = (module, test_class, test_name, description)
            self.test_checkboxes.append(checkbox)
            
            scroll_layout.addWidget(checkbox)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        # Count label
        self.count_label = QLabel()
        self.count_label.setStyleSheet("font-size: 11px; color: #666; padding: 5px;")
        layout.addWidget(self.count_label)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.cancel_btn = QPushButton('Cancel')
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        button_layout.addStretch()
        
        self.start_btn = QPushButton('▶ START TESTS')
        self.start_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; font-size: 14px; "
            "font-weight: bold; padding: 10px; min-width: 200px;"
        )
        self.start_btn.clicked.connect(self.start_tests)
        button_layout.addWidget(self.start_btn)
        
        layout.addLayout(button_layout)
        
        # Initialize count label (now that start_btn exists)
        self.update_count()
        
        # Connect checkboxes to update count
        for cb in self.test_checkboxes:
            cb.stateChanged.connect(self.update_count)
    
    def select_all(self):
        """Select all test checkboxes."""
        for cb in self.test_checkboxes:
            cb.setChecked(True)
    
    def deselect_all(self):
        """Deselect all test checkboxes."""
        for cb in self.test_checkboxes:
            cb.setChecked(False)
    
    def update_count(self):
        """Update the count label."""
        selected = sum(1 for cb in self.test_checkboxes if cb.isChecked())
        total = len(self.test_checkboxes)
        self.count_label.setText(f"Selected: {selected} / {total} tests")
        self.start_btn.setEnabled(selected > 0)
    
    def start_tests(self):
        """Start the selected tests."""
        self.selected_tests = [
            cb.test_info for cb in self.test_checkboxes if cb.isChecked()
        ]
        self.accept()


class TestReportDialog(QDialog):
    """Dialog showing detailed test results after completion."""
    
    def __init__(self, test_results, parent=None):
        super().__init__(parent)
        self.test_results = test_results  # List of (test_name, passed, duration, error, traceback)
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle('MCP Test Suite - Test Results Report')
        self.setMinimumSize(900, 700)
        
        layout = QVBoxLayout(self)
        
        # Summary header
        passed = sum(1 for _, p, _, _, _ in self.test_results if p)
        failed = len(self.test_results) - passed
        total = len(self.test_results)
        
        summary_widget = QWidget()
        summary_widget.setStyleSheet(
            f"background-color: {'#4CAF50' if failed == 0 else '#F44336'}; "
            f"color: white; padding: 20px; border-radius: 5px;"
        )
        summary_layout = QVBoxLayout(summary_widget)
        
        result_text = "✓ ALL TESTS PASSED!" if failed == 0 else f"✗ {failed} TEST(S) FAILED"
        result_label = QLabel(result_text)
        result_font = QFont()
        result_font.setPointSize(18)
        result_font.setBold(True)
        result_label.setFont(result_font)
        result_label.setAlignment(Qt.AlignCenter)
        summary_layout.addWidget(result_label)
        
        stats_label = QLabel(f"Total: {total} | Passed: {passed} | Failed: {failed}")
        stats_font = QFont()
        stats_font.setPointSize(12)
        stats_label.setFont(stats_font)
        stats_label.setAlignment(Qt.AlignCenter)
        summary_layout.addWidget(stats_label)
        
        layout.addWidget(summary_widget)
        
        # Test details
        details_label = QLabel("Test Details:")
        details_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 20px;")
        layout.addWidget(details_label)
        
        # Scrollable text area with results
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setStyleSheet(
            "background-color: #F5F5F5; font-family: monospace; font-size: 11px;"
        )
        
        # Build detailed report
        report_html = "<html><body style='font-family: monospace;'>"
        
        for test_name, passed, duration, error, traceback in self.test_results:
            if passed:
                report_html += f"<div style='background-color: #E8F5E9; padding: 10px; margin: 5px; border-left: 4px solid #4CAF50;'>"
                report_html += f"<b style='color: #4CAF50;'>✓ PASSED:</b> {test_name}<br>"
                report_html += f"<span style='color: #666;'>Duration: {duration:.2f}s</span><br>"
                report_html += f"<span style='color: #555;'>Test executed successfully and all assertions passed.</span>"
                report_html += "</div>"
            else:
                report_html += f"<div style='background-color: #FFEBEE; padding: 10px; margin: 5px; border-left: 4px solid #F44336;'>"
                report_html += f"<b style='color: #F44336;'>✗ FAILED:</b> {test_name}<br>"
                report_html += f"<span style='color: #666;'>Duration: {duration:.2f}s</span><br><br>"
                
                # Error details
                report_html += f"<b>Error:</b><br>"
                report_html += f"<pre style='background-color: #FFF; padding: 10px; border: 1px solid #DDD;'>{self._html_escape(error)}</pre>"
                
                if traceback:
                    report_html += f"<br><b>Traceback:</b><br>"
                    report_html += f"<pre style='background-color: #FFF; padding: 10px; border: 1px solid #DDD; font-size: 10px;'>{self._html_escape(traceback)}</pre>"
                
                # Diagnostic suggestions
                report_html += f"<br><b>💡 How to Fix:</b><br>"
                report_html += self._get_fix_suggestions(test_name, error)
                report_html += "</div>"
        
        report_html += "</body></html>"
        
        self.details_text.setHtml(report_html)
        layout.addWidget(self.details_text)
        
        # Close button
        close_btn = QPushButton('Close')
        close_btn.setStyleSheet("padding: 10px; min-width: 100px;")
        close_btn.clicked.connect(self.accept)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)
    
    def _html_escape(self, text):
        """Escape HTML special characters."""
        if not text:
            return ""
        return (str(text)
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#39;'))
    
    def _get_fix_suggestions(self, test_name, error):
        """Generate fix suggestions based on test name and error."""
        suggestions = []
        error_str = str(error).lower()
        
        # Common error patterns
        if 'display' in error_str or 'x11' in error_str:
            suggestions.append("• Ensure DISPLAY environment variable is set (e.g., DISPLAY=:1)")
            suggestions.append("• Check that X11 server is running")
            suggestions.append("• Try: <code>xhost +local:</code>")
        
        if 'element' in error_str and 'not found' in error_str:
            suggestions.append("• Element detection may have failed - try with detect_elements=True")
            suggestions.append("• GUI elements may not be accessible via AT-SPI")
            suggestions.append("• Check that the test GUI is actually visible on screen")
        
        if 'timeout' in error_str or 'took too long' in error_str:
            suggestions.append("• System may be slow - try increasing timeout values")
            suggestions.append("• Check for CPU/memory resource issues")
        
        if 'click' in test_name.lower() and 'assert' in error_str:
            suggestions.append("• Click may have landed in wrong position due to scaling")
            suggestions.append("• Try running get_screen_info() to check scaling factor")
            suggestions.append("• Ensure test GUI is in fullscreen mode")
        
        if 'type' in test_name.lower() or 'keyboard' in test_name.lower():
            suggestions.append("• Text field may not have focus - check if click worked")
            suggestions.append("• Keyboard input may be intercepted by window manager")
            suggestions.append("• Try increasing delay between keystrokes (interval parameter)")
        
        if 'drag' in test_name.lower():
            suggestions.append("• Drag & drop may need longer duration")
            suggestions.append("• Check that start and end coordinates are correct")
            suggestions.append("• Some widgets may not support drag & drop")
        
        if 'screenshot' in test_name.lower():
            suggestions.append("• Ensure gnome-screenshot or scrot is installed")
            suggestions.append("• Check file permissions for output directory")
            suggestions.append("• Verify DISPLAY variable points to correct screen")
        
        # Default suggestion if no specific matches
        if not suggestions:
            suggestions.append("• Check test logs for more details")
            suggestions.append("• Verify all system dependencies are installed")
            suggestions.append("• Try running the test in isolation to see if it's an interaction issue")
        
        return "<ul style='margin-left: 20px;'>" + "".join(f"<li>{s}</li>" for s in suggestions) + "</ul>"
