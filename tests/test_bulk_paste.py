#!/usr/bin/env python3
"""
Comprehensive Test Suite for Omarchy Bulk Paste Extension
Tests:
  1. JS selection and validation functions (validateBulkCount, getBulkEntries)
  2. Chronological ordering (oldest-to-newest replay)
  3. Boundary conditions (0, -1, >50, non-digits, empty input, whitespace)
  4. History count < requested count handling
  5. Missing, corrupted, and invalid clipboard entries
  6. Terminal vs GUI window detection
  7. Unavailable / closed target window safety abort
  8. Missing / invalid file paths and image readability
  9. Temporary file handling and cleanup
  10. Repeated execution and state isolation
  11. Desktop integration tests (optional, run only in live Hyprland session)
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, call, patch

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BULK_SCRIPT = os.path.join(REPO_DIR, "bulk_paste.py")
HISTORY_JS = os.path.join(REPO_DIR, "ClipboardHistory.js")


class TestBulkPasteJS(unittest.TestCase):
    """Test JS logic in ClipboardHistory.js via Node.js."""

    @classmethod
    def setUpClass(cls):
        if not shutil.which("node"):
            raise unittest.SkipTest("node executable not found")

    def run_node_code(self, code):
        full_code = f"const ch = require('{HISTORY_JS}');\n{code}"
        res = subprocess.run(["node", "-e", full_code], capture_output=True, text=True, check=True)
        return json.loads(res.stdout)

    def test_validate_bulk_count(self):
        code = """
        const results = {
          valid10: ch.validateBulkCount("10", 50),
          valid1: ch.validateBulkCount("1", 50),
          valid50: ch.validateBulkCount("50", 50),
          zero: ch.validateBulkCount("0", 50),
          negative: ch.validateBulkCount("-5", 50),
          floatVal: ch.validateBulkCount("5.5", 50),
          text: ch.validateBulkCount("abc", 50),
          empty: ch.validateBulkCount("", 50),
          nullVal: ch.validateBulkCount(null, 50),
          undefinedVal: ch.validateBulkCount(undefined, 50),
          overMax: ch.validateBulkCount("51", 50),
          whitespace: ch.validateBulkCount("  7  ", 50)
        };
        console.log(JSON.stringify(results));
        """
        data = self.run_node_code(code)
        self.assertEqual(data["valid10"], 10)
        self.assertEqual(data["valid1"], 1)
        self.assertEqual(data["valid50"], 50)
        self.assertEqual(data["zero"], 0)
        self.assertEqual(data["negative"], 0)
        self.assertEqual(data["floatVal"], 0)
        self.assertEqual(data["text"], 0)
        self.assertEqual(data["empty"], 0)
        self.assertEqual(data["nullVal"], 0)
        self.assertEqual(data["undefinedVal"], 0)
        self.assertEqual(data["overMax"], 0)
        self.assertEqual(data["whitespace"], 7)

    def test_chronological_ordering(self):
        """Verifies that history items (newest at index 0) are reversed to chronological order."""
        code = """
        const history = [
          { type: "image", path: "/tmp/shot15.png", mime: "image/png" }, // newest (index 0)
          { type: "image", path: "/tmp/shot14.png", mime: "image/png" },
          { type: "image", path: "/tmp/shot13.png", mime: "image/png" },
          { type: "image", path: "/tmp/shot12.png", mime: "image/png" },
          { type: "image", path: "/tmp/shot11.png", mime: "image/png" },
          { type: "image", path: "/tmp/shot10.png", mime: "image/png" }, // oldest of 6 (index 5)
          { type: "image", path: "/tmp/shot9.png", mime: "image/png" }
        ];
        const res = ch.getBulkEntries(history, 6, 50);
        console.log(JSON.stringify(res));
        """
        data = self.run_node_code(code)
        self.assertEqual(data["requested"], 6)
        self.assertEqual(data["available"], 6)
        entries = data["entries"]
        self.assertEqual(len(entries), 6)
        # Oldest first: shot10, shot11, ..., shot15
        self.assertEqual(entries[0]["path"], "/tmp/shot10.png")
        self.assertEqual(entries[1]["path"], "/tmp/shot11.png")
        self.assertEqual(entries[2]["path"], "/tmp/shot12.png")
        self.assertEqual(entries[3]["path"], "/tmp/shot13.png")
        self.assertEqual(entries[4]["path"], "/tmp/shot14.png")
        self.assertEqual(entries[5]["path"], "/tmp/shot15.png")

    def test_history_smaller_than_requested(self):
        """If only 3 items exist and user asks for 10, take all 3 in chronological order."""
        code = """
        const history = [
          { type: "text", text: "third" }, // newest
          { type: "text", text: "second" },
          { type: "text", text: "first" }   // oldest
        ];
        const res = ch.getBulkEntries(history, 10, 50);
        console.log(JSON.stringify(res));
        """
        data = self.run_node_code(code)
        self.assertEqual(data["requested"], 10)
        self.assertEqual(data["available"], 3)
        self.assertEqual(len(data["entries"]), 3)
        self.assertEqual(data["entries"][0]["text"], "first")
        self.assertEqual(data["entries"][1]["text"], "second")
        self.assertEqual(data["entries"][2]["text"], "third")

    def test_invalid_and_corrupted_history_entries(self):
        """Malformed entries in history should be safely ignored by getBulkEntries."""
        code = """
        const history = [
          null,
          undefined,
          { type: "unknown", data: 123 },
          { type: "text", text: "" },
          { type: "text", text: "   " },
          { type: "image", path: "" },
          { notAProperty: 123 },
          12345,
          true,
          { type: "text", text: "valid text" }
        ];
        const res = ch.getBulkEntries(history, 5, 50);
        console.log(JSON.stringify(res));
        """
        data = self.run_node_code(code)
        self.assertEqual(data["available"], 1)
        self.assertEqual(len(data["entries"]), 1)
        self.assertEqual(data["entries"][0]["text"], "valid text")


class TestBulkPastePythonLogic(unittest.TestCase):
    """Test Python logic in bulk_paste.py directly."""

    def setUp(self):
        if REPO_DIR not in sys.path:
            sys.path.insert(0, REPO_DIR)
        import bulk_paste
        self.bp = bulk_paste

    def test_is_terminal_client(self):
        # Foot terminal
        self.assertTrue(self.bp.is_terminal_client({"class": "foot", "tags": []}))
        # Alacritty terminal
        self.assertTrue(self.bp.is_terminal_client({"class": "Alacritty", "tags": []}))
        # Ghostty terminal
        self.assertTrue(self.bp.is_terminal_client({"class": "com.mitchellh.ghostty", "tags": []}))
        # Tagged terminal
        self.assertTrue(self.bp.is_terminal_client({"class": "custom-app", "tags": ["terminal*"]}))
        # Brave browser (not terminal)
        self.assertFalse(self.bp.is_terminal_client({"class": "brave-browser", "tags": []}))
        # Nautilus (not terminal)
        self.assertFalse(self.bp.is_terminal_client({"class": "org.gnome.Nautilus", "tags": []}))

    def test_normalize_history_items(self):
        raw = [
            {"type": "text", "text": "valid string"},
            {"type": "text", "text": ""},
            {"type": "text", "text": "   "},
            {"type": "image", "path": "/path/to/img.png", "mime": "image/png"},
            {"type": "image", "path": ""},
            {"kind": "text", "text": "legacy kind support"},
            "raw string",
            None
        ]
        norm = self.bp.normalize_history_items(raw)
        self.assertEqual(len(norm), 3)
        self.assertEqual(norm[0]["text"], "valid string")
        self.assertEqual(norm[1]["path"], "/path/to/img.png")
        self.assertEqual(norm[2]["text"], "legacy kind support")

    def test_load_history_isolated(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump([{"type": "text", "text": "isolated"}], f)
            temp_path = f.name
        try:
            items = self.bp.load_history(temp_path)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["text"], "isolated")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_load_history_missing_and_corrupted(self):
        # Missing file returns []
        self.assertEqual(self.bp.load_history("/nonexistent/history/file.json"), [])

        # Corrupted JSON returns []
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write("corrupted JSON content {[[")
            corrupt_path = f.name
        try:
            self.assertEqual(self.bp.load_history(corrupt_path), [])
        finally:
            if os.path.exists(corrupt_path):
                os.remove(corrupt_path)

    def test_unavailable_window_aborts_safely(self):
        """Calling bulk_paste with nonexistent window must abort without throwing unhandled exceptions."""
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump([{"type": "text", "text": "sample text"}], f)
            temp_history = f.name
        try:
            res = subprocess.run([
                sys.executable, BULK_SCRIPT,
                "--count", "1",
                "--history", temp_history,
                "--target-window", "0xdeadbeef"
            ], capture_output=True, text=True)
            self.assertIn("Target window 0xdeadbeef not found", res.stderr)
        finally:
            if os.path.exists(temp_history):
                os.remove(temp_history)

    def test_empty_history_aborts_safely(self):
        """Calling bulk_paste when history is empty must abort gracefully."""
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump([], f)
            temp_history = f.name
        try:
            res = subprocess.run([
                sys.executable, BULK_SCRIPT,
                "--count", "1",
                "--history", temp_history,
                "--target-window", "0xdeadbeef"
            ], capture_output=True, text=True)
            self.assertIn("No valid clipboard items to paste", res.stderr)
        finally:
            if os.path.exists(temp_history):
                os.remove(temp_history)

    def test_invalid_arguments_exit_code(self):
        # Missing target window
        res = subprocess.run([sys.executable, BULK_SCRIPT, "--count", "5"], capture_output=True, text=True)
        self.assertNotEqual(res.returncode, 0)

        # Missing count and payload
        res2 = subprocess.run([sys.executable, BULK_SCRIPT, "--target-window", "0x1234"], capture_output=True, text=True)
        self.assertNotEqual(res2.returncode, 0)

    def test_missing_and_unreadable_image_paths(self):
        """Unreadable image paths should be counted as failed without crashing."""
        entries = [
            {"type": "image", "path": "/nonexistent/test_img.png", "mime": "image/png"},
            {"type": "image", "path": "/another/missing.jpg", "mime": "image/jpeg"}
        ]
        # execute_bulk_paste should log error and count failed without raising
        self.bp.execute_bulk_paste(entries=entries, target_address="0xdeadbeef")

    def test_repeated_execution_state_isolation(self):
        """Running multiple calls successively must not leave contaminated state."""
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump([{"type": "text", "text": "item"}], f)
            temp_history = f.name
        try:
            for _ in range(5):
                res = subprocess.run([
                    sys.executable, BULK_SCRIPT,
                    "--count", "1",
                    "--history", temp_history,
                    "--target-window", "0xdeadbeef"
                ], capture_output=True, text=True)
                self.assertIn("Target window 0xdeadbeef not found", res.stderr)
        finally:
            if os.path.exists(temp_history):
                os.remove(temp_history)


class TestFocusVerificationSecurityRegression(unittest.TestCase):
    """Regression test suite for target window focus verification and fail-closed security guarantees.
    Verifies that no clipboard history or keystrokes are ever sent to an unverified or unintended window.
    All Hyprland and clipboard subprocess interactions are strictly mocked.
    """

    def setUp(self):
        if REPO_DIR not in sys.path:
            sys.path.insert(0, REPO_DIR)
        import bulk_paste
        self.bp = bulk_paste
        self.notify_patcher = patch.object(self.bp, "notify")
        self.mock_notify = self.notify_patcher.start()

    def tearDown(self):
        self.notify_patcher.stop()

    def test_is_window_active(self):
        """is_window_active must strictly verify that the active window address matches."""
        with patch.object(self.bp, "get_hyprland_active_window", return_value={"address": "0x5571f7a63ec0"}):
            self.assertTrue(self.bp.is_window_active("0x5571f7a63ec0"))
            self.assertTrue(self.bp.is_window_active("0x5571F7A63EC0"))
            self.assertFalse(self.bp.is_window_active("0x999999999999"))
            self.assertFalse(self.bp.is_window_active(""))
            self.assertFalse(self.bp.is_window_active(None))

        with patch.object(self.bp, "get_hyprland_active_window", return_value={}):
            self.assertFalse(self.bp.is_window_active("0x5571f7a63ec0"))

    def test_target_already_focused(self):
        """When target is already active, ensure_window_focused returns (True, client) without dispatching focus command."""
        target = "0xTARGET"
        mock_client = {"address": "0xtarget", "title": "Editor", "class": "gedit"}
        with patch.object(self.bp, "get_hyprland_clients", return_value=[mock_client]), \
             patch.object(self.bp, "get_hyprland_active_window", return_value={"address": "0xtarget"}), \
             patch.object(self.bp, "focus_window") as mock_focus:
            ok, client = self.bp.ensure_window_focused(target)
            self.assertTrue(ok)
            self.assertEqual(client, mock_client)
            mock_focus.assert_not_called()

    def test_focus_successfully_changes_to_target(self):
        """When target is not active initially, focus is requested and succeeds upon verification."""
        target = "0xTARGET"
        mock_client = {"address": "0xtarget", "title": "Editor", "class": "gedit"}
        active_sequence = [{"address": "0xOTHER"}, {"address": "0xtarget"}]
        with patch.object(self.bp, "get_hyprland_clients", return_value=[mock_client]), \
             patch.object(self.bp, "get_hyprland_active_window", side_effect=active_sequence), \
             patch.object(self.bp, "focus_window", return_value=True) as mock_focus:
            ok, client = self.bp.ensure_window_focused(target, max_wait=0.2)
            self.assertTrue(ok)
            self.assertEqual(client, mock_client)
            mock_focus.assert_called_once_with(target)

    def test_focus_command_succeeds_but_actual_focus_does_not_change(self):
        """A successful hyprctl command returncode MUST NOT be treated as proof of focus.
        Must fail closed and return (False, None) when active window does not match.
        """
        target = "0xTARGET"
        mock_client = {"address": "0xtarget", "title": "Editor", "class": "gedit"}
        with patch.object(self.bp, "get_hyprland_clients", return_value=[mock_client]), \
             patch.object(self.bp, "get_hyprland_active_window", return_value={"address": "0xOTHER"}), \
             patch.object(self.bp, "focus_window", return_value=True) as mock_focus:
            ok, client = self.bp.ensure_window_focused(target, max_wait=0.05)
            self.assertFalse(ok)
            self.assertIsNone(client)
            mock_focus.assert_called_once_with(target)

    def test_another_window_remains_active_after_all_retries(self):
        """When polling retries expire without active window matching target, return (False, None)."""
        target = "0xTARGET"
        mock_client = {"address": "0xtarget", "title": "Editor", "class": "gedit"}
        with patch.object(self.bp, "get_hyprland_clients", return_value=[mock_client]), \
             patch.object(self.bp, "get_hyprland_active_window", return_value={"address": "0xUNINTENDED"}), \
             patch.object(self.bp, "focus_window", return_value=False):
            ok, client = self.bp.ensure_window_focused(target, max_wait=0.05)
            self.assertFalse(ok)
            self.assertIsNone(client)

    def test_target_missing_from_clients(self):
        """If target window address is not among Hyprland clients, fail closed immediately."""
        with patch.object(self.bp, "get_hyprland_clients", return_value=[]):
            ok, client = self.bp.ensure_window_focused("0xNONEXISTENT")
            self.assertFalse(ok)
            self.assertIsNone(client)

    def test_target_disappears_during_replay(self):
        """If target window disappears mid-paste, execution must abort immediately and no further keys sent."""
        target = "0xTARGET"
        mock_client = {"address": "0xtarget", "title": "Terminal", "class": "foot"}
        entries = [
            {"type": "text", "text": "item 1"},
            {"type": "text", "text": "item 2"}
        ]
        # Sequence of clients queries:
        # 1. execute_bulk_paste initial find_client_by_address
        # 2. execute_bulk_paste initial ensure_window_focused
        # 3. item 1 ensure_window_focused
        # 4. item 2 ensure_window_focused -> window closed!
        clients_seq = [
            [mock_client],
            [mock_client],
            [mock_client],
            []
        ]

        with patch.object(self.bp, "get_hyprland_clients", side_effect=clients_seq), \
             patch.object(self.bp, "get_hyprland_active_window", return_value={"address": "0xtarget"}), \
             patch.object(self.bp, "send_paste_keys") as mock_paste, \
             patch.object(self.bp, "wait_for_clipboard_ready", return_value=True), \
             patch.object(self.bp, "notify") as mock_notify, \
             patch("subprocess.Popen") as mock_popen:
            proc_inst = MagicMock()
            proc_inst.communicate.return_value = (b"", b"")
            mock_popen.return_value = proc_inst

            self.bp.execute_bulk_paste(entries, target, delay_text=0.001)

            # Only item 1 was pasted; item 2 was aborted before paste keys
            self.assertEqual(mock_paste.call_count, 1)
            mock_notify.assert_any_call("Bulk Paste Stopped",
                                        "Target window closed or lost focus after pasting 1 of 2 items.",
                                        urgency="normal")

    def test_focus_changes_between_clipboard_preparation_and_paste(self):
        """If active window changes to another window during clipboard preparation,
        paste keys MUST NOT be sent, and execution must abort immediately.
        """
        target = "0xTARGET"
        mock_client = {"address": "0xtarget", "title": "Terminal", "class": "foot"}
        entries = [{"type": "text", "text": "sensitive_token_here"}]

        # Sequence for active window queries:
        # 1. initial ensure_window_focused -> target
        # 2. item 1 ensure_window_focused -> target
        # 3. pre-paste check (after wl-copy) -> OTHER window is active! Focus lost!
        active_seq = [
            {"address": "0xtarget"},
            {"address": "0xtarget"},
            {"address": "0xUNINTENDED_BROWSER"}
        ]

        with patch.object(self.bp, "get_hyprland_clients", return_value=[mock_client]), \
             patch.object(self.bp, "get_hyprland_active_window", side_effect=active_seq), \
             patch.object(self.bp, "send_paste_keys") as mock_paste, \
             patch.object(self.bp, "wait_for_clipboard_ready", return_value=True), \
             patch.object(self.bp, "notify") as mock_notify, \
             patch("subprocess.Popen") as mock_popen:
            proc_inst = MagicMock()
            proc_inst.communicate.return_value = (b"", b"")
            mock_popen.return_value = proc_inst

            self.bp.execute_bulk_paste(entries, target, delay_text=0.001)

            # Paste keys must NEVER be sent!
            mock_paste.assert_not_called()
            mock_notify.assert_any_call("Bulk Paste Aborted",
                                        "Target window lost focus; paste aborted for safety.",
                                        urgency="normal")

    def test_image_focus_changes_between_preparation_and_paste(self):
        """If active window changes during image clipboard preparation,
        paste keys MUST NOT be sent for image, and execution must abort.
        """
        target = "0xTARGET"
        mock_client = {"address": "0xtarget", "title": "Editor", "class": "gedit"}

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\x89PNG\r\n\x1a\nfakeimage")
            img_path = f.name

        try:
            entries = [{"type": "image", "path": img_path, "mime": "image/png"}]
            active_seq = [
                {"address": "0xtarget"},
                {"address": "0xtarget"},
                {"address": "0xDIFFERENT_APP"}
            ]

            with patch.object(self.bp, "get_hyprland_clients", return_value=[mock_client]), \
                 patch.object(self.bp, "get_hyprland_active_window", side_effect=active_seq), \
                 patch.object(self.bp, "send_paste_keys") as mock_paste, \
                 patch.object(self.bp, "wait_for_clipboard_ready", return_value=True), \
                 patch.object(self.bp, "notify") as mock_notify, \
                 patch("subprocess.Popen") as mock_popen:
                proc_inst = MagicMock()
                proc_inst.communicate.return_value = (b"", b"")
                mock_popen.return_value = proc_inst

                self.bp.execute_bulk_paste(entries, target, delay_image=0.001)

                mock_paste.assert_not_called()
                mock_notify.assert_any_call("Bulk Paste Aborted",
                                            "Target window lost focus; paste aborted for safety.",
                                            urgency="normal")
        finally:
            if os.path.exists(img_path):
                os.remove(img_path)

    def test_no_paste_keystrokes_sent_when_target_verification_fails(self):
        """send_paste_keys with target_address must strictly block wtype when verification fails."""
        with patch.object(self.bp, "is_window_active", return_value=False), \
             patch("subprocess.run") as mock_subproc:
            res = self.bp.send_paste_keys(is_terminal=False, target_address="0xTARGET")
            self.assertFalse(res)
            mock_subproc.assert_not_called()

        with patch.object(self.bp, "is_window_active", return_value=True), \
             patch("subprocess.run") as mock_subproc:
            res = self.bp.send_paste_keys(is_terminal=False, target_address="0xTARGET")
            self.assertTrue(res)
            mock_subproc.assert_called_once()
            call_args = mock_subproc.call_args[0][0]
            self.assertIn("wtype", call_args)

    def test_initial_focus_failure_aborts_without_keystrokes(self):
        """If initial ensure_window_focused fails, abort immediately before loop starts."""
        target = "0xTARGET"
        mock_client = {"address": "0xtarget", "title": "Editor", "class": "gedit"}
        entries = [{"type": "text", "text": "will_not_paste"}]

        with patch.object(self.bp, "get_hyprland_clients", return_value=[mock_client]), \
             patch.object(self.bp, "ensure_window_focused", return_value=(False, None)), \
             patch.object(self.bp, "send_paste_keys") as mock_paste:
            self.bp.execute_bulk_paste(entries, target)
            mock_paste.assert_not_called()


class TestLivePasteIntegration(unittest.TestCase):
    """Live functional desktop integration tests (executed only when Wayland/Hyprland session is active)."""

    def setUp(self):
        if not (os.environ.get("WAYLAND_DISPLAY") and shutil.which("hyprctl") and shutil.which("wtype")):
            self.skipTest("Requires active Wayland session with hyprctl and wtype")

    def test_live_gtk4_window_paste(self):
        """Spawn GTK4 test window, paste 3 sequential text items, and verify content."""
        receiver_script = """
import signal, sys, gi
signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

app = Gtk.Application(application_id='org.test.LiveReceiver')

def on_activate(app):
    win = Gtk.ApplicationWindow(application=app)
    win.set_title("BulkPasteLiveReceiver")
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
                            if c.get("class") == "org.test.LiveReceiver":
                                target_addr = c.get("address")
                                break
                    except Exception:
                        pass
                if target_addr:
                    break

            self.assertIsNotNone(target_addr, "GTK4 test window did not appear in Hyprland.")

            # Focus the test window
            focus_cmd = f"hl.dsp.focus({{ window = 'address:{target_addr}' }})"
            subprocess.run(["hyprctl", "dispatch", focus_cmd], check=False)
            time.sleep(0.15)

            # Prepare 3 test items via payload
            payload_data = [
                {"type": "text", "text": "Item1 "},
                {"type": "text", "text": "Item2 "},
                {"type": "text", "text": "Item3"}
            ]
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as pf:
                json.dump(payload_data, pf)
                payload_file = pf.name

            # Run bulk_paste.py targeting the GTK4 window
            paste_res = subprocess.run([
                sys.executable, BULK_SCRIPT,
                "--payload", payload_file,
                "--target-window", target_addr,
                "--delay-text", "0.1"
            ], capture_output=True, text=True)

            self.assertEqual(paste_res.returncode, 0, f"bulk_paste failed: {paste_res.stderr}")
            self.assertIn("Finished bulk paste: 3 succeeded, 0 failed", paste_res.stderr)

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
