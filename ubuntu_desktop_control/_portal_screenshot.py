"""Wayland screenshot via xdg-desktop-portal. Run with the SYSTEM python3 (needs PyGObject).

Prints the saved file path on stdout; exits non-zero on failure.
"""
import sys
import uuid

from gi.repository import Gio, GLib


def main() -> int:
    bus = Gio.bus_get_sync(Gio.BusType.SESSION)
    sender = bus.get_unique_name()[1:].replace(".", "_")
    token = "udc" + uuid.uuid4().hex[:12]
    handle = f"/org/freedesktop/portal/desktop/request/{sender}/{token}"
    loop = GLib.MainLoop()
    out = {}

    def on_response(_conn, _snd, _path, _iface, _sig, params):
        out["r"] = params.unpack()
        loop.quit()

    bus.signal_subscribe(
        "org.freedesktop.portal.Desktop", "org.freedesktop.portal.Request", "Response",
        handle, None, Gio.DBusSignalFlags.NONE, on_response,
    )
    opts = {"handle_token": GLib.Variant("s", token), "interactive": GLib.Variant("b", False)}
    bus.call_sync(
        "org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop",
        "org.freedesktop.portal.Screenshot", "Screenshot",
        GLib.Variant("(sa{sv})", ("", opts)), None, Gio.DBusCallFlags.NONE, -1, None,
    )
    GLib.timeout_add_seconds(40, loop.quit)
    loop.run()
    resp = out.get("r")
    if not resp or resp[0] != 0 or "uri" not in resp[1]:
        print(f"portal screenshot failed: {resp}", file=sys.stderr)
        return 1
    print(GLib.filename_from_uri(resp[1]["uri"])[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())
