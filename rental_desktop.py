#!/usr/bin/env python3
"""
Rental OS — Native Desktop App (GTK + WebKit)
Wraps the Rental OS web app in a native window with no browser chrome.
"""

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gtk, Gdk, WebKit2, GLib  # noqa: F401
import sys
import os
import signal
import urllib.request

APP_NAME = "Rental OS"
APP_VERSION = "0.1.0"
WEB_APP_URL = "http://localhost:5173"

# Handle Ctrl+C gracefully
signal.signal(signal.SIGINT, signal.SIG_DFL)


class RentalDesktop(Gtk.Window):
    def __init__(self):
        super().__init__(title=f"{APP_NAME} v{APP_VERSION}")

        # ── Window properties ──
        self.set_default_size(1200, 800)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_icon_name("applications-internet")

        # Use dark theme to match the app
        screen = self.get_screen()
        css = Gtk.CssProvider()
        css.load_from_data(b"""
            window { background-color: #020617; }
            .titlebar { background-color: #0f172a; color: #94a3b8; }
        """)
        Gtk.StyleContext.add_provider_for_screen(screen, css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        # ── Title bar (custom to match app theme) ──
        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.props.title = f"{APP_NAME}"
        header.props.subtitle = f"v{APP_VERSION}"
        header.get_style_context().add_class("titlebar")
        self.set_titlebar(header)

        # Refresh button
        refresh_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.MENU)
        refresh_btn.set_tooltip_text("Reload")
        refresh_btn.connect("clicked", self._on_refresh)
        header.pack_end(refresh_btn)

        # DevTools toggle (hidden by default — Ctrl+Shift+I to open)
        self._inspector = None

        # ── WebView ──
        self.webview = WebKit2.WebView()
        settings = self.webview.get_settings()
        settings.set_enable_javascript(True)
        settings.set_enable_developer_extras(True)
        settings.set_allow_file_access_from_file_urls(True)
        settings.set_allow_universal_access_from_file_urls(True)

        # Load the app
        self.webview.load_uri(WEB_APP_URL)

        # Handle connection errors — show a user-friendly page
        self.webview.connect("load-failed", self._on_load_failed)

        # Scrollable container
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)
        scroll.add(self.webview)

        self.add(scroll)

        # ── Keyboard shortcuts ──
        self.connect("key-press-event", self._on_key_press)

        # ── Show time ──
        self.show_all()

    def _on_refresh(self, _btn=None):
        self.webview.reload()

    def _on_key_press(self, _widget, event):
        # Ctrl+Shift+I — toggle inspector
        if event.state & Gtk.accelerator_get_default_mod_mask() == \
                Gtk.ModifierType.CONTROL_MASK | Gtk.ModifierType.SHIFT_MASK and \
                event.keyval == Gdk.KEY_I:
            self._toggle_inspector()
            return True
        # F5 / Ctrl+R — refresh
        if event.keyval in (Gdk.KEY_F5, Gdk.KEY_r) and \
                event.state & Gtk.accelerator_get_default_mod_mask() in (0, Gtk.ModifierType.CONTROL_MASK):
            self._on_refresh()
            return True
        return False

    def _toggle_inspector(self):
        if self._inspector and self._inspector.is_visible():
            self._inspector.hide()
        else:
            self._inspector = self.webview.get_inspector()
            self._inspector.show()

    def _on_load_failed(self, webview, load_event, failing_uri, error):
        print(f"[Rental Desktop] Load failed for {failing_uri}: {error.message}")
        # Only intercept the main frame
        if load_event == WebKit2.LoadEvent.FINISHED:
            return False

        html = f"""<html><body style="background:#020617;color:#94a3b8;
        font-family:sans-serif;display:flex;align-items:center;justify-content:center;
        height:100vh;text-align:center;">
        <div>
        <h1 style="color:#10b981;">Rental OS</h1>
        <p>Could not connect to the app server.</p>
        <p style="font-size:small;color:#64748b;">Make sure the backend is running on port 5173</p>
        <button onclick="location.reload()"
        style="background:#10b981;color:#020617;border:none;padding:8px 20px;
        border-radius:6px;margin-top:12px;cursor:pointer;">Retry</button>
        </div></body></html>"""
        webview.load_html(html, "http://localhost/")
        return True

def detect_working_url():
    global WEB_APP_URL
    ports = [5173, 8080, 8011]
    for p in ports:
        url = f"http://localhost:{p}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "RentalDesktop/1.0"})
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status in (200, 302, 304):
                    WEB_APP_URL = url
                    print(f"[Rental Desktop] ✓ Connected to {WEB_APP_URL}")
                    return url
        except Exception:
            continue
    print(f"[Rental Desktop] ⚠ Defaulting to {WEB_APP_URL}")
    return WEB_APP_URL


def main():
    detect_working_url()
    win = RentalDesktop()
    Gtk.main()


if __name__ == "__main__":
    main()
