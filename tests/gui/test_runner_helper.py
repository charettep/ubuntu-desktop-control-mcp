"""
Test Discovery and Execution Helper

This module helps discover and run GUI integration tests from all test modules.
"""

import pytest
import sys
import os
from typing import List, Tuple
import time
import traceback as tb


def discover_gui_tests() -> List[Tuple[str, str, str, str]]:
    """
    Discover all GUI integration tests from test modules.
    
    Returns:
        List of (module_name, class_name, test_name, description) tuples
    """
    tests = []
    
    # Manually define all GUI tests with descriptions
    # Format: (module, class, test_method, description)
    
    # Screenshot tests
    tests.extend([
        ("test_screenshot", "TestGUIScreenshot", "test_screenshot_captures_gui",
         "Capture screenshot of test GUI and verify resolution"),
        ("test_screenshot", "TestGUIScreenshot", "test_element_detection_finds_gui_elements",
         "Detect UI elements in test GUI using AT-SPI/CV"),
    ])
    
    # Mouse click tests
    tests.extend([
        ("test_mouse", "TestGUIMouseClick", "test_click_button_topleft",
         "Click top-left button and verify click was registered"),
        ("test_mouse", "TestGUIMouseClick", "test_click_by_percentage_coords",
         "Click using percentage coordinates"),
    ])
    
    # Mouse movement tests
    tests.extend([
        ("test_mouse", "TestGUIMouseMovement", "test_move_mouse_to_coords",
         "Move mouse to absolute coordinates"),
        ("test_mouse", "TestGUIMouseMovement", "test_move_mouse_by_percentage",
         "Move mouse to 5 positions using percentages"),
    ])
    
    # Mouse drag tests
    tests.extend([
        ("test_mouse", "TestGUIMouseDrag", "test_drag_mouse_relative",
         "Drag mouse with relative offset"),
        ("test_mouse", "TestGUIMouseDrag", "test_drag_mouse_to_position",
         "Drag mouse to specific position"),
    ])
    
    # Keyboard tests
    tests.extend([
        ("test_keyboard", "TestGUIKeyboard", "test_type_text_into_field",
         "Type text into input field and verify"),
        ("test_keyboard", "TestGUIKeyboard", "test_copy_paste_workflow",
         "Test Ctrl+C and Ctrl+V hotkeys"),
    ])
    
    # Hotkey tests
    tests.extend([
        ("test_keyboard", "TestGUIHotkeys", "test_single_hotkey",
         "Test single key hotkeys (Esc, Tab, Space, Enter)"),
        ("test_keyboard", "TestGUIHotkeys", "test_modifier_hotkeys",
         "Test modifier combinations (Ctrl+C, Ctrl+V, etc.)"),
    ])
    
    # Advanced typing tests
    tests.extend([
        ("test_keyboard", "TestGUITypingAdvanced", "test_type_special_characters",
         "Type special characters and symbols"),
        ("test_keyboard", "TestGUITypingAdvanced", "test_type_with_intervals",
         "Test different typing speeds"),
    ])
    
    # Workflow tests
    tests.extend([
        ("test_workflow", "TestGUIWorkflow", "test_complete_interaction_workflow",
         "Execute multi-step workflow"),
        ("test_workflow", "TestGUIWorkflowAdvanced", "test_multi_action_workflow",
         "Execute 5-step workflow with screenshots and mouse movement"),
        ("test_workflow", "TestGUIWorkflowAdvanced", "test_workflow_with_errors",
         "Test workflow error handling"),
    ])
    
    # Element detection tests
    tests.extend([
        ("test_element_detection", "TestGUIElementDetection", "test_element_detection_comprehensive",
         "Detect all types of GUI elements and categorize by role"),
        ("test_element_detection", "TestGUIElementDetection", "test_element_detection_fallback",
         "Test CV fallback when AT-SPI unavailable"),
    ])
    
    # Screen info tests
    tests.extend([
        ("test_diagnostics", "TestGUIScreenInfo", "test_get_screen_info",
         "Get screen resolution and scaling factor"),
    ])
    
    # Coordinate system tests
    tests.extend([
        ("test_mouse", "TestGUICoordinateSystem", "test_coordinate_accuracy",
         "Test click accuracy at different screen positions"),
    ])
    
    # Stress tests
    tests.extend([
        ("test_workflow", "TestGUIStressTest", "test_rapid_screenshots",
         "Take 10 screenshots rapidly and measure performance"),
        ("test_workflow", "TestGUIStressTest", "test_rapid_mouse_movements",
         "Perform 20 rapid mouse movements"),
        ("test_workflow", "TestGUIStressTest", "test_rapid_clicks",
         "Perform 10 rapid clicks on same button"),
    ])
    
    # MCP Workflow tests (realistic LLM client simulation)
    tests.extend([
        ("test_mcp_workflow", "TestMCPWorkflow", "test_screenshot_workflow",
         "Complete MCP screenshot workflow with visual feedback"),
        ("test_mcp_workflow", "TestMCPWorkflow", "test_decision_based_click",
         "Decision-based click using discovered elements (LLM simulation)"),
    ])
    
    return tests


def run_selected_tests(selected_tests: List[Tuple[str, str, str, str]], gui_callback=None):
    """
    Run selected tests and return results.
    
    Args:
        selected_tests: List of (module, class, test, description) tuples
        gui_callback: Optional callback function to call for progress updates
    
    Returns:
        List of (test_name, passed, duration, error, traceback) tuples
    """
    import datetime
    
    results = []
    
    # Get the project root directory (two levels up from this file)
    tests_gui_dir = os.path.dirname(os.path.abspath(__file__))
    tests_dir = os.path.dirname(tests_gui_dir)
    project_root = os.path.dirname(tests_dir)
    
    # Create log file in .pytest_cache/logs/
    log_dir = os.path.join(project_root, '.pytest_cache', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"test_run_{timestamp}.log")
    
    # Ensure project root is in path
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    # Change to project root so pytest paths work correctly
    original_cwd = os.getcwd()
    os.chdir(project_root)
    
    # Write log header
    with open(log_file, 'w') as f:
        f.write(f"=== MCP Test Suite Run - {datetime.datetime.now()} ===\n")
        f.write(f"Selected {len(selected_tests)} tests to run\n\n")
    
    total_tests = len(selected_tests)
    
    for idx, (module_name, class_name, test_name, description) in enumerate(selected_tests, 1):
        full_test_name = f"{class_name}::{test_name}"
        
        # Update progress with test number
        progress_msg = f"[{idx}/{total_tests}] Running {full_test_name}..."
        if gui_callback:
            gui_callback(progress_msg)
        
        # Log to file
        with open(log_file, 'a') as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"Test {idx}/{total_tests}: {full_test_name}\n")
            f.write(f"Description: {description}\n")
            f.write(f"{'='*80}\n")
        
        start_time = time.time()
        
        try:
            # Build pytest path relative to project root
            test_path = f"tests/{module_name}.py::{class_name}::{test_name}"
            
            # Run pytest programmatically
            exit_code = pytest.main([
                test_path,
                "-v",
                "-s",
                "--tb=short",
                "-p", "no:warnings"
            ])
            
            duration = time.time() - start_time
            
            if exit_code == 0:
                results.append((full_test_name, True, duration, None, None))
                with open(log_file, 'a') as f:
                    f.write(f"✓ PASSED ({duration:.2f}s)\n")
                if gui_callback:
                    gui_callback(f"✓ Test {idx}/{total_tests} PASSED: {full_test_name}")
            elif exit_code == 5:  # No tests collected / skipped
                results.append((full_test_name, True, duration, "Skipped", None))
                with open(log_file, 'a') as f:
                    f.write(f"⊘ SKIPPED ({duration:.2f}s)\n")
                if gui_callback:
                    gui_callback(f"⊘ Test {idx}/{total_tests} SKIPPED: {full_test_name}")
            else:
                error_msg = f"Test failed with exit code {exit_code}"
                results.append((full_test_name, False, duration, error_msg, None))
                with open(log_file, 'a') as f:
                    f.write(f"✗ FAILED ({duration:.2f}s) - Exit code {exit_code}\n")
                if gui_callback:
                    gui_callback(f"✗ Test {idx}/{total_tests} FAILED: {full_test_name}")
            
            # Delay between tests so user can see what happened
            time.sleep(0.5)
        
        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            traceback = tb.format_exc()
            results.append((full_test_name, False, duration, error_msg, traceback))
            with open(log_file, 'a') as f:
                f.write(f"✗ EXCEPTION ({duration:.2f}s)\n")
                f.write(f"Error: {error_msg}\n")
                f.write(f"Traceback:\n{traceback}\n")
    
    # Write summary to log file
    passed = sum(1 for _, p, _, _, _ in results if p)
    failed = total_tests - passed
    
    with open(log_file, 'a') as f:
        f.write(f"\n{'='*80}\n")
        f.write(f"SUMMARY: {passed} passed, {failed} failed out of {total_tests} tests\n")
        f.write(f"Log file: {log_file}\n")
        f.write(f"{'='*80}\n")
    
    # Restore original directory
    os.chdir(original_cwd)
    
    print(f"\n✓ Test run complete. Log saved to: {log_file}")
    
    return results
