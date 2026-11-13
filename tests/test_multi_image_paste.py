#!/usr/bin/env python3
"""
Test multi-image paste and mixed content bulk paste.
Includes both unit tests and desktop integration tests (when active Hyprland session exists).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BULK_SCRIPT = os.path.join(REPO_DIR, "bulk_paste.py")


class TestMultiImagePayloadUnit(unittest.TestCase):
    """Unit tests for multi-image payloads, filtering, and normalization."""

    def setUp(self):
        if REPO_DIR not in sys.path:
            sys.path.insert(0, REPO_DIR)
        import bulk_paste
        self.bp = bulk_paste
        self.temp_dir = tempfile.mkdtemp()
        self.image_files = []
        png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        for i in range(10):
            img_path = os.path.join(self.temp_dir, f"test_shot_{i+1}.png")
            with open(img_path, "wb") as f:
                f.write(png_bytes)
            self.image_files.append(img_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_normalize_ten_images(self):
        raw_items = [
            {"type": "image", "path": p, "mime": "image/png", "capturedAt": f"Nov 1 23:{i:02d}"}
            for i, p in enumerate(self.image_files)
        ]
        norm = self.bp.normalize_history_items(raw_items)
        self.assertEqual(len(norm), 10)
        for i, item in enumerate(norm):
            self.assertEqual(item["type"], "image")
            self.assertEqual(item["path"], self.image_files[i])
            self.assertEqual(item["mime"], "image/png")

    def test_mixed_text_and_images_normalization(self):
        raw_items = [
            {"type": "image", "path": self.image_files[0], "mime": "image/png"},
            {"type": "text", "text": "Snippet 1"},
            {"type": "image", "path": self.image_files[1], "mime": "image/png"},
            {"type": "text", "text": "Snippet 2"},
            {"type": "image", "path": "", "mime": "image/png"},  # missing path -> skipped
            {"type": "text", "text": ""}                          # empty text -> skipped
        ]
        norm = self.bp.normalize_history_items(raw_items)
        self.assertEqual(len(norm), 4)
        self.assertEqual(norm[0]["type"], "image")
        self.assertEqual(norm[1]["type"], "text")
        self.assertEqual(norm[2]["type"], "image")
        self.assertEqual(norm[3]["type"], "text")


class TestMultiImagePasteIntegration(unittest.TestCase):
    """Live desktop integration tests for multi-image pasting."""

    def setUp(self):
        if not (os.environ.get("WAYLAND_DISPLAY") and shutil.which("hyprctl") and shutil.which("wtype")):
            self.skipTest("Requires active Wayland session with hyprctl and wtype")

        self.temp_dir = tempfile.mkdtemp()
        self.image_files = []
        png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        for i in range(10):
            img_path = os.path.join(self.temp_dir, f"test_screenshot_{i+1}.png")
            with open(img_path, "wb") as f:
                f.write(png_bytes)
            self.image_files.append(img_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_ten_images_payload(self):
        """Verify bulk paste processes 10 screenshots in sequence without failure."""
        payload_items = [
            {"type": "image", "path": p, "mime": "image/png", "capturedAt": f"Nov 1 23:{i:02d}"}
            for i, p in enumerate(self.image_files)
        ]

        receiver_script = """
import signal, sys, gi
signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

app = Gtk.Application(application_id='org.test.ImageReceiver')

def on_activate(app):
    win = Gtk.ApplicationWindow(application=app)
    win.set_title("ImageReceiverWindow")
    win.set_default_size(300, 200)
    tv = Gtk.TextView()
    win.set_child(tv)
    win.present()

app.connect('activate', on_activate)
app.run(sys.argv)
"""
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(receiver_script)
            script_path = f.name

        proc = subprocess.Popen([sys.executable, script_path])
        payload_file = None
        try:
            target_addr = None
            for _ in range(30):
                time.sleep(0.1)
                res = subprocess.run(["hyprctl", "-j", "clients"], capture_output=True, text=True)
                if res.returncode == 0:
                    try:
                        clients = json.loads(res.stdout)
                        for c in clients:
                            if c.get("class") == "org.test.ImageReceiver":
                                target_addr = c.get("address")
                                break
                    except Exception:
                        pass
                if target_addr:
                    break

            self.assertIsNotNone(target_addr, "Image receiver window did not appear.")

            focus_cmd = f"hl.dsp.focus({{ window = 'address:{target_addr}' }})"
            subprocess.run(["hyprctl", "dispatch", focus_cmd], check=False)
            time.sleep(0.15)

            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as pf:
                json.dump(payload_items, pf)
                payload_file = pf.name

            res = subprocess.run([
                sys.executable, BULK_SCRIPT,
                "--payload", payload_file,
                "--target-window", target_addr,
                "--delay-image", "0.08"
            ], capture_output=True, text=True)

            self.assertEqual(res.returncode, 0, f"Error: {res.stderr}")
            self.assertIn("Finished bulk paste: 10 succeeded, 0 failed out of 10 items", res.stderr)

        finally:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            if os.path.exists(script_path):
                os.remove(script_path)
            if payload_file and os.path.exists(payload_file):
                os.remove(payload_file)

    def test_mixed_text_and_images_payload(self):
        """Verify mixture of 3 text items and 3 images in chronological order."""
        mixed_items = [
            {"type": "image", "path": self.image_files[0], "mime": "image/png"},
            {"type": "text", "text": "Note A "},
            {"type": "image", "path": self.image_files[1], "mime": "image/png"},
            {"type": "text", "text": "Note B "},
            {"type": "image", "path": self.image_files[2], "mime": "image/png"},
            {"type": "text", "text": "Note C"}
        ]

        receiver_script = """
import signal, sys, gi
signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

app = Gtk.Application(application_id='org.test.MixedReceiver')

def on_activate(app):
    win = Gtk.ApplicationWindow(application=app)
    win.set_title("MixedReceiverWindow")
    win.set_default_size(300, 200)
    tv = Gtk.TextView()
    win.set_child(tv)
    win.present()

app.connect('activate', on_activate)
app.run(sys.argv)
"""
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(receiver_script)
            script_path = f.name

        proc = subprocess.Popen([sys.executable, script_path])
        payload_file = None
        try:
            target_addr = None
            for _ in range(30):
                time.sleep(0.1)
                res = subprocess.run(["hyprctl", "-j", "clients"], capture_output=True, text=True)
                if res.returncode == 0:
                    try:
                        clients = json.loads(res.stdout)
                        for c in clients:
                            if c.get("class") == "org.test.MixedReceiver":
                                target_addr = c.get("address")
                                break
                    except Exception:
                        pass
                if target_addr:
                    break

            self.assertIsNotNone(target_addr, "Mixed receiver window did not appear.")

            focus_cmd = f"hl.dsp.focus({{ window = 'address:{target_addr}' }})"
            subprocess.run(["hyprctl", "dispatch", focus_cmd], check=False)
            time.sleep(0.15)

            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as pf:
                json.dump(mixed_items, pf)
                payload_file = pf.name

            res = subprocess.run([
                sys.executable, BULK_SCRIPT,
                "--payload", payload_file,
                "--target-window", target_addr,
                "--delay-text", "0.08",
                "--delay-image", "0.08"
            ], capture_output=True, text=True)

            self.assertEqual(res.returncode, 0, f"Error: {res.stderr}")
            self.assertIn("Finished bulk paste: 6 succeeded, 0 failed out of 6 items", res.stderr)

        finally:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            if os.path.exists(script_path):
                os.remove(script_path)
            if payload_file and os.path.exists(payload_file):
                os.remove(payload_file)


if __name__ == "__main__":
    unittest.main()
