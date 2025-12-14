"""Tests for workflow batching functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from PIL import Image

from ubuntu_desktop_control.server import (
    execute_workflow,
    WorkflowResult,
)


class TestExecuteWorkflow:
    """Test the workflow batching tool."""
    
    def test_workflow_screenshot_action(self, mock_pyautogui, mock_x11_env, tmp_path):
        """Test workflow with screenshot action."""
        test_img = Image.new('RGB', (1920, 1080), color='blue')
        mock_pyautogui.screenshot.return_value = test_img
        
        with patch('ubuntu_desktop_control.server._get_screenshot_with_backend') as mock_backend:
            mock_backend.return_value = (test_img, 1920, 1080, None)
            
            actions = [
                {"action": "screenshot", "detect_elements": False, "output_dir": str(tmp_path)}
            ]
            
            result = execute_workflow(actions=actions, take_final_screenshot=False)
        
        assert result.success is True
        assert result.actions_completed == 1
        assert result.total_actions == 1
        assert result.results[0]["action"] == "screenshot"
        assert result.results[0]["success"] is True
    
    def test_workflow_click_action(self, mock_pyautogui, mock_x11_env):
        """Test workflow with click action."""
        mock_pyautogui.size.return_value = (1920, 1080)
        
        actions = [
            {"action": "click", "x_percent": 0.5, "y_percent": 0.5}
        ]
        
        result = execute_workflow(actions=actions, take_final_screenshot=False)
        
        assert result.success is True
        assert result.actions_completed == 1
        assert result.results[0]["action"] == "click"
        assert result.results[0]["success"] is True
        assert result.results[0]["x"] == 960
        assert result.results[0]["y"] == 540
    
    def test_workflow_type_action(self, mock_pyautogui, mock_x11_env):
        """Test workflow with type action."""
        actions = [
            {"action": "type", "text": "Hello World", "interval": 0.0}
        ]
        
        result = execute_workflow(actions=actions, take_final_screenshot=False)
        
        assert result.success is True
        assert result.actions_completed == 1
        assert result.results[0]["action"] == "type"
        assert result.results[0]["success"] is True
        mock_pyautogui.write.assert_called_once_with("Hello World", interval=0.0)
    
    def test_workflow_wait_action(self, mock_pyautogui, mock_x11_env):
        """Test workflow with wait action."""
        actions = [
            {"action": "wait", "duration": 0.1}
        ]
        
        with patch('time.sleep') as mock_sleep:
            result = execute_workflow(actions=actions, take_final_screenshot=False)
        
        assert result.success is True
        assert result.actions_completed == 1
        assert result.results[0]["action"] == "wait"
        assert result.results[0]["success"] is True
        mock_sleep.assert_called_once_with(0.1)
    
    def test_workflow_move_action(self, mock_pyautogui, mock_x11_env):
        """Test workflow with move mouse action."""
        mock_pyautogui.size.return_value = (1920, 1080)
        
        actions = [
            {"action": "move", "x_percent": 0.25, "y_percent": 0.75, "duration": 0.5}
        ]
        
        result = execute_workflow(actions=actions, take_final_screenshot=False)
        
        assert result.success is True
        assert result.actions_completed == 1
        assert result.results[0]["action"] == "move"
        assert result.results[0]["success"] is True
        mock_pyautogui.moveTo.assert_called_once_with(480, 810, duration=0.5)
    
    def test_workflow_multiple_actions(self, mock_pyautogui, mock_x11_env):
        """Test workflow with multiple sequential actions."""
        mock_pyautogui.size.return_value = (1920, 1080)
        
        actions = [
            {"action": "move", "x_percent": 0.5, "y_percent": 0.5},
            {"action": "wait", "duration": 0.1},
            {"action": "click", "x_percent": 0.5, "y_percent": 0.5},
            {"action": "type", "text": "test"}
        ]
        
        with patch('time.sleep'):
            result = execute_workflow(actions=actions, take_final_screenshot=False)
        
        assert result.success is True
        assert result.actions_completed == 4
        assert result.total_actions == 4
        assert len(result.results) == 4
    
    def test_workflow_stops_on_error(self, mock_pyautogui, mock_x11_env):
        """Test that workflow stops when an action fails."""
        mock_pyautogui.size.return_value = (1920, 1080)
        
        actions = [
            {"action": "click", "x_percent": 0.5, "y_percent": 0.5},
            {"action": "click", "x_percent": 5.0, "y_percent": 0.5},  # Invalid - will fail
            {"action": "type", "text": "should not execute"}
        ]
        
        result = execute_workflow(actions=actions, take_final_screenshot=False)
        
        assert result.success is False
        assert result.actions_completed == 1  # Only first action completed
        assert result.total_actions == 3
        assert len(result.results) == 2  # Two actions attempted
    
    def test_workflow_unknown_action(self, mock_pyautogui, mock_x11_env):
        """Test workflow with unknown action type."""
        actions = [
            {"action": "invalid_action"}
        ]
        
        result = execute_workflow(actions=actions, take_final_screenshot=False)
        
        assert result.success is False
        assert result.actions_completed == 0
        assert result.results[0]["success"] is False
        assert "Unknown action type" in result.results[0]["error"]
    
    def test_workflow_with_final_screenshot(self, mock_pyautogui, mock_x11_env, tmp_path):
        """Test workflow with final screenshot enabled."""
        test_img = Image.new('RGB', (1920, 1080), color='green')
        mock_pyautogui.screenshot.return_value = test_img
        mock_pyautogui.size.return_value = (1920, 1080)
        
        with patch('ubuntu_desktop_control.server._get_screenshot_with_backend') as mock_backend:
            mock_backend.return_value = (test_img, 1920, 1080, None)
            
            actions = [
                {"action": "click", "x_percent": 0.5, "y_percent": 0.5}
            ]
            
            result = execute_workflow(actions=actions, take_final_screenshot=True)
        
        assert result.success is True
        assert result.final_screenshot is not None
        assert result.final_screenshot.endswith('.png')
    
    def test_workflow_empty_actions(self, mock_pyautogui, mock_x11_env):
        """Test workflow with empty action list."""
        result = execute_workflow(actions=[], take_final_screenshot=False)
        
        assert result.success is True
        assert result.actions_completed == 0
        assert result.total_actions == 0
        assert len(result.results) == 0


# ============================================================================
# INTEGRATION TESTS (Real Dependencies)
# ============================================================================

class TestRealWorkflow:
    """Integration tests using REAL operations in workflows."""
    
    @pytest.mark.integration
    def test_real_workflow_screenshot_only(self, tmp_path):
        """Test workflow with real screenshot."""
        import os
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        actions = [
            {"action": "screenshot", "detect_elements": False, "output_dir": str(tmp_path)}
        ]
        
        result = execute_workflow(actions=actions, take_final_screenshot=False)
        
        assert result.success is True
        assert result.actions_completed == 1
        assert result.results[0]['success'] is True


# ============================================================================
# GUI INTEGRATION TESTS (Test GUI Application)
# ============================================================================

class TestGUIWorkflow:
    """Test complete workflows with the test GUI."""
    
    @pytest.mark.integration
    def test_complete_interaction_workflow(self, gui_ready, tmp_path):
        """Test a complete workflow."""
        import os
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        from ubuntu_desktop_control.server import execute_workflow
        
        actions = [
            {"action": "screenshot", "detect_elements": True, "output_dir": str(tmp_path)},
            {"action": "wait", "seconds": 0.2},
        ]
        
        result = execute_workflow(actions=actions, take_final_screenshot=True)
        
        assert result.success is True
        assert result.actions_completed >= 1
        print(f"✓ Workflow completed: {result.actions_completed} actions")


class TestGUIWorkflowAdvanced:
    """Advanced workflow tests."""
    
    @pytest.mark.integration
    def test_multi_action_workflow(self, gui_ready, tmp_path):
        """Test workflow with multiple actions."""
        import os
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        from ubuntu_desktop_control.server import execute_workflow
        
        actions = [
            {"action": "screenshot", "detect_elements": False, "output_dir": str(tmp_path)},
            {"action": "wait", "duration": 0.1},
            {"action": "move", "x_percent": 0.5, "y_percent": 0.5, "duration": 0.1},
            {"action": "wait", "duration": 0.1},
            {"action": "screenshot", "detect_elements": True, "output_dir": str(tmp_path)},
        ]
        
        result = execute_workflow(actions=actions, take_final_screenshot=True)
        
        assert result.success
        assert result.actions_completed == len(actions)
        print(f"✓ Workflow completed: {result.actions_completed} actions")
    
    @pytest.mark.integration
    def test_workflow_with_errors(self, gui_ready, tmp_path):
        """Test workflow error handling."""
        import os
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        from ubuntu_desktop_control.server import execute_workflow
        
        actions = [
            {"action": "screenshot", "detect_elements": False, "output_dir": str(tmp_path)},
            {"action": "invalid_action"},
            {"action": "wait", "seconds": 0.1},
        ]
        
        result = execute_workflow(actions=actions, take_final_screenshot=False)
        
        assert result.actions_completed < len(actions)
        print(f"✓ Workflow error handling: stopped at action {result.actions_completed}")


class TestGUIStressTest:
    """Stress test with rapid actions."""
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_rapid_screenshots(self, gui_ready, tmp_path):
        """Test taking multiple screenshots rapidly."""
        import os, time
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        from ubuntu_desktop_control.server import take_screenshot
        
        start_time = time.time()
        for i in range(10):
            result = take_screenshot(detect_elements=False, output_dir=str(tmp_path))
            assert result.success
        elapsed = time.time() - start_time
        
        print(f"✓ Rapid screenshot test: 10 screenshots in {elapsed:.2f}s")
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_rapid_mouse_movements(self, gui_ready):
        """Test rapid mouse movements."""
        import os, time, random
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        from ubuntu_desktop_control.server import move_mouse
        
        start_time = time.time()
        for i in range(20):
            x_pct = random.uniform(0.2, 0.8)
            y_pct = random.uniform(0.2, 0.8)
            result = move_mouse(x_percent=x_pct, y_percent=y_pct, duration=0.05)
            assert result.success
        elapsed = time.time() - start_time
        
        print(f"✓ Rapid movement test: 20 movements in {elapsed:.2f}s")
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_rapid_clicks(self, gui_ready):
        """Test rapid clicking."""
        import os, time
        if not os.environ.get('DISPLAY'):
            pytest.skip("No DISPLAY available")
        
        from ubuntu_desktop_control.server import click_screen
        from PyQt5.QtWidgets import QApplication
        
        start_time = time.time()
        for i in range(10):
            result = click_screen(x_percent=0.15, y_percent=0.08)
            assert result.success
            QApplication.instance().processEvents()
            time.sleep(0.05)
        elapsed = time.time() - start_time
        
        state = gui_ready.get_state()
        print(f"✓ Rapid click test: 10 clicks in {elapsed:.2f}s, "
              f"last registered: {state['last_button_clicked']}")
