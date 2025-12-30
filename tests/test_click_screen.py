import time

import ubuntu_desktop_control.server as server


class DummyPyAutoGUI:
    def __init__(self):
        self.click_calls = []

    def size(self):
        return (1000, 800)

    def click(self, x, y, clicks=1, button="left"):
        self.click_calls.append({"x": x, "y": y, "clicks": clicks, "button": button})


class DummyPyAutoGUIForScreenshot:
    def size(self):
        return (1000, 800)

    def screenshot(self):
        raise RuntimeError("screenshot not supported in test")


def setup_function(_):
    server._ELEMENT_CACHE = None
    server._pyautogui = None
    server._pyautogui_error = None


def test_click_screen_percent_coordinates(monkeypatch):
    dummy = DummyPyAutoGUI()
    monkeypatch.setattr(server, "_get_pyautogui", lambda: dummy)
    result = server.click_screen(x_percent=0.5, y_percent=0.25)
    assert result.success is True
    assert dummy.click_calls == [{"x": 500, "y": 200, "clicks": 1, "button": "left"}]


def test_click_screen_element_id_uses_cache(monkeypatch):
    dummy = DummyPyAutoGUI()
    monkeypatch.setattr(server, "_get_pyautogui", lambda: dummy)
    monkeypatch.setattr(server, "_get_active_app_name", lambda: None)
    monkeypatch.setattr(server, "_attempt_atspi_action", lambda *_args, **_kwargs: (False, None))
    server._ELEMENT_CACHE = {
        "meta": {
            "logical_width": 1000,
            "logical_height": 800,
            "scaling_factor": 1.0,
            "active_app_name": None,
            "monitor_index": None,
            "monitor_origin": None,
        },
        "elements": {
            1: {"x_percent": 0.2, "y_percent": 0.4},
        },
        "captured_at": time.monotonic(),
    }
    result = server.click_screen(element_id=1)
    assert result.success is True
    assert dummy.click_calls == [{"x": 200, "y": 320, "clicks": 1, "button": "left"}]


def test_click_screen_invalid_button(monkeypatch):
    dummy = DummyPyAutoGUI()
    monkeypatch.setattr(server, "_get_pyautogui", lambda: dummy)
    result = server.click_screen(x_percent=0.1, y_percent=0.1, button="invalid")
    assert result.success is False
    assert "Invalid button" in (result.error or "")


def test_click_screen_missing_coords(monkeypatch):
    dummy = DummyPyAutoGUI()
    monkeypatch.setattr(server, "_get_pyautogui", lambda: dummy)
    result = server.click_screen()
    assert result.success is False
    assert "Must provide" in (result.error or "")
