"""Wayland input injection via xdg-desktop-portal RemoteDesktop. Run with the SYSTEM python3 (needs PyGObject).

Long-lived: reads one JSON command per line on stdin, writes one JSON reply per line on stdout.
The portal session lives as long as this process. The portal only offers RELATIVE pointer motion
here, so absolute positioning homes the pointer to the desktop's top-left corner in small steps
(large single jumps get stuck on the current monitor's edge) and then walks to the target.

Commands: goto, click, drag, type, key, hotkey, state
"""
import json
import os
import sys
import time
import uuid

from gi.repository import Gdk, Gio, GLib

NAME = "org.freedesktop.portal.Desktop"
PATH = "/org/freedesktop/portal/desktop"
RD = "org.freedesktop.portal.RemoteDesktop"
V = GLib.Variant
TOKEN_FILE = os.environ.get(
    "UDC_RD_TOKEN_FILE", os.path.expanduser("~/.config/ubuntu-desktop-control/rd_restore_token")
)
STEP = float(os.environ.get("UDC_POINTER_STEP", "600"))
STEP_DELAY = float(os.environ.get("UDC_STEP_DELAY", "0"))
SETTLE = float(os.environ.get("UDC_SETTLE", "0.02"))
BUTTONS = {"left": 272, "right": 273, "middle": 274}

# pyautogui key names -> X keysym names
KEY_ALIASES = {
    "enter": "Return", "return": "Return", "esc": "Escape", "escape": "Escape", "tab": "Tab",
    "space": "space", "backspace": "BackSpace", "delete": "Delete", "del": "Delete",
    "ctrl": "Control_L", "ctrlleft": "Control_L", "ctrlright": "Control_R",
    "alt": "Alt_L", "altleft": "Alt_L", "altright": "Alt_R",
    "shift": "Shift_L", "shiftleft": "Shift_L", "shiftright": "Shift_R",
    "win": "Super_L", "winleft": "Super_L", "winright": "Super_R", "super": "Super_L", "command": "Super_L",
    "up": "Up", "down": "Down", "left": "Left", "right": "Right",
    "home": "Home", "end": "End", "pageup": "Page_Up", "pagedown": "Page_Down",
    "insert": "Insert", "capslock": "Caps_Lock", "printscreen": "Print", "prtsc": "Print",
}
for _i in range(1, 25):
    KEY_ALIASES[f"f{_i}"] = f"F{_i}"

bus = Gio.bus_get_sync(Gio.BusType.SESSION)
_sender = bus.get_unique_name()[1:].replace(".", "_")
_session = None
_pos = None  # tracked absolute pointer position, None = unknown


def _request(method, build, timeout=120):
    token = "t" + uuid.uuid4().hex[:10]
    handle = f"/org/freedesktop/portal/desktop/request/{_sender}/{token}"
    loop = GLib.MainLoop()
    out = {}
    sid = bus.signal_subscribe(
        NAME, "org.freedesktop.portal.Request", "Response", handle, None, Gio.DBusSignalFlags.NONE,
        lambda *a: (out.update(r=a[5].unpack()), loop.quit()),
    )
    bus.call_sync(NAME, PATH, RD, method, build(token), None, Gio.DBusCallFlags.NONE, -1, None)
    GLib.timeout_add_seconds(timeout, loop.quit)
    loop.run()
    bus.signal_unsubscribe(sid)
    return out.get("r")


def _start_session():
    global _session
    r = _request("CreateSession", lambda t: V("(a{sv})", ({
        "handle_token": V("s", t), "session_handle_token": V("s", "s" + uuid.uuid4().hex[:8])},)))
    if not r or r[0] != 0:
        raise RuntimeError(f"CreateSession failed: {r}")
    session = r[1]["session_handle"]
    opts_extra = {}
    try:
        opts_extra["restore_token"] = V("s", open(TOKEN_FILE).read().strip())
    except OSError:
        pass
    r = _request("SelectDevices", lambda t: V("(oa{sv})", (session, {
        "handle_token": V("s", t), "types": V("u", 3), "persist_mode": V("u", 2), **opts_extra})))
    if not r or r[0] != 0:
        raise RuntimeError(f"SelectDevices failed: {r}")
    r = _request("Start", lambda t: V("(osa{sv})", (session, "", {"handle_token": V("s", t)})))
    if not r or r[0] != 0:
        raise RuntimeError(f"Start failed or was denied: {r}")
    new_token = r[1].get("restore_token")
    if new_token:
        os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
        fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(new_token)
    _session = session


def _notify(method, fmt, *args):
    bus.call_sync(NAME, PATH, RD, method, V(fmt, (_session, {}) + args), None,
                  Gio.DBusCallFlags.NONE, -1, None)


def _rel(dx, dy):
    _notify("NotifyPointerMotion", "(oa{sv}dd)", float(dx), float(dy))


def _desktop_extent():
    """(right, bottom) edge of the logical desktop from Mutter's DisplayConfig; generous fallback if unavailable."""
    try:
        _serial, monitors, logical, _props = bus.call_sync(
            "org.gnome.Mutter.DisplayConfig", "/org/gnome/Mutter/DisplayConfig",
            "org.gnome.Mutter.DisplayConfig", "GetCurrentState", None, None,
            Gio.DBusCallFlags.NONE, -1, None).unpack()
        size = {}
        for m in monitors:
            for mode in m[1]:
                if mode[6].get("is-current"):
                    size[m[0][0]] = (mode[1], mode[2])
        right = bottom = 0.0
        for x, y, scale, transform, _primary, mons, _p in logical:
            w, h = size[mons[0][0]]
            if transform in (1, 3, 5, 7):
                w, h = h, w
            right = max(right, x + w / scale)
            bottom = max(bottom, y + h / scale)
        if right and bottom:
            return right, bottom
    except Exception:  # noqa: BLE001
        pass
    return 20000.0, 20000.0


def _walk(dx, dy, duration=0.0):
    """Relative move in small steps (optionally spread over `duration` seconds)."""
    n = max(1, int(max(abs(dx), abs(dy)) // STEP) + 1)
    delay = duration / n if duration else STEP_DELAY
    for _ in range(n):
        _rel(dx / n, dy / n)
        time.sleep(delay)


def _home():
    global _pos
    right, bottom = _desktop_extent()   # no need to travel further than the desktop is big
    _walk(0, -(bottom + 50))   # up first, then left: a diagonal jump gets stuck at the current monitor's corner
    _walk(-(right + 50), 0)
    time.sleep(SETTLE)
    _pos = (0.0, 0.0)


def goto(x, y, duration=0.0, rehome=True):
    global _pos
    if _pos is None or rehome:
        _home()
        _walk(x, 0)
        _walk(0, y)
        if duration:
            time.sleep(duration)
    else:
        _walk(x - _pos[0], y - _pos[1], duration)
    _pos = (float(x), float(y))
    time.sleep(SETTLE)


def _button(name, state):
    _notify("NotifyPointerButton", "(oa{sv}iu)", BUTTONS[name], state)


def click(x, y, clicks, button):
    if x is not None:
        goto(x, y)
    elif _pos is None:
        raise RuntimeError("pointer position unknown; move the mouse to a coordinate first")
    for _ in range(max(1, clicks)):
        _button(button, 1)
        time.sleep(0.03)
        _button(button, 0)
        time.sleep(0.06)


def drag(x, y, duration, button):
    if _pos is None:
        raise RuntimeError("pointer position unknown; move the mouse to a coordinate first")
    _button(button, 1)
    time.sleep(0.08)
    try:
        goto(x, y, duration, rehome=False)
    finally:
        time.sleep(0.05)
        _button(button, 0)


def _keysym(name):
    if len(name) == 1:
        kv = Gdk.unicode_to_keyval(ord(name))
    else:
        kv = Gdk.keyval_from_name(KEY_ALIASES.get(name.lower(), name))
        if kv == 0:
            kv = Gdk.keyval_from_name(name)
    if not kv:
        raise ValueError(f"unknown key: {name!r}")
    return kv


def _tap(kv):
    _notify("NotifyKeyboardKeysym", "(oa{sv}iu)", kv, 1)
    _notify("NotifyKeyboardKeysym", "(oa{sv}iu)", kv, 0)


def type_text(text, interval):
    for ch in text:
        _tap(Gdk.unicode_to_keyval(ord("\n" if ch == "\r" else ch)) if ch not in "\n\t" else
             Gdk.keyval_from_name("Return" if ch == "\n" else "Tab"))
        time.sleep(interval or 0.005)


def hotkey(keys):
    kvs = [_keysym(k) for k in keys]
    for kv in kvs:
        _notify("NotifyKeyboardKeysym", "(oa{sv}iu)", kv, 1)
        time.sleep(0.02)
    for kv in reversed(kvs):
        _notify("NotifyKeyboardKeysym", "(oa{sv}iu)", kv, 0)
        time.sleep(0.02)


def handle(cmd):
    op = cmd["op"]
    if op == "goto":
        goto(cmd["x"], cmd["y"], cmd.get("duration", 0.0))
    elif op == "click":
        click(cmd.get("x"), cmd.get("y"), cmd.get("clicks", 1), cmd.get("button", "left"))
    elif op == "drag":
        drag(cmd["x"], cmd["y"], cmd.get("duration", 0.5), cmd.get("button", "left"))
    elif op == "type":
        type_text(cmd["text"], cmd.get("interval", 0.0))
    elif op == "key":
        _tap(_keysym(cmd["key"]))
    elif op == "hotkey":
        hotkey(cmd["keys"])
    elif op != "state":
        raise ValueError(f"unknown op {op!r}")
    return {"ok": True, "pos": _pos}


def main():
    try:
        _start_session()
        print(json.dumps({"ready": True}), flush=True)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ready": False, "error": str(exc)}), flush=True)
        return 1
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            reply = handle(json.loads(line))
        except Exception as exc:  # noqa: BLE001
            reply = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        print(json.dumps(reply), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
