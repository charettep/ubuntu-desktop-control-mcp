import numpy as np

import ubuntu_desktop_control.server as server


class DummyPyAutoGUI:
    def size(self):
        return (100, 100)


def test_map_gui_elements_coordinate_space(monkeypatch, tmp_path):
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    path = tmp_path / "test.png"

    import cv2

    cv2.rectangle(image, (10, 10), (40, 40), (255, 255, 255), 2)
    cv2.imwrite(str(path), image)

    monkeypatch.setattr(server, "_get_pyautogui", lambda: DummyPyAutoGUI())
    monkeypatch.setattr(server, "_detect_scaling_factor", lambda *args, **kwargs: (1.0, None))

    server._pyautogui = None
    server._pyautogui_error = None
    result = server.map_GUI_elements_location(screenshot_path=str(path))
    assert result.success is True
    assert result.coordinates == "logical"
    assert result.count >= 1
