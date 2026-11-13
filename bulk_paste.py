#!/usr/bin/env python3
"""
Omarchy Bulk Paste Runner
Executes sequential clipboard paste of the N newest history items in chronological order.
Handles:
  - Window focus preservation and verification
  - Sensitive clipboard replay (zero duplicate history records via capture.sh)
  - Content type / MIME preservation (text, images, screenshots)
  - Synchronized Wayland clipboard operations with wtype
  - Single summary notification via omarchy-notification-send / notify-send
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

TERMINAL_PATTERN = re.compile(
    r"^(Alacritty|kitty|com\.mitchellh\.ghostty|foot|org\.codeberg\.dnkl\.foot|wezterm|org\.omarchy\..*|TUI\..*)$",
    re.IGNORECASE
)

DEFAULT_HISTORY_PATH = os.path.expanduser(
    os.environ.get("OMARCHY_CLIPBOARD_HISTORY", "~/.local/state/omarchy/clipboard-history.json")
)


def log(msg):
    # Internal logging to stderr, avoiding any clipboard payload contents
    sys.stderr.write(f"[bulk-paste] {msg}\n")
    sys.stderr.flush()


def notify(title, message, urgency="low", glyph="󰅌"):
    cmd = shutil.which("omarchy-notification-send")
    if cmd:
        subprocess.run([cmd, "-g", glyph, "-u", urgency, title, message],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    else:
        fallback = shutil.which("notify-send")
        if fallback:
            subprocess.run([fallback, "-u", urgency, title, message],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def get_hyprland_clients():
    try:
        res = subprocess.run(["hyprctl", "-j", "clients"], capture_output=True, text=True, check=True)
        return json.loads(res.stdout)
    except Exception as e:
        log(f"Error querying hyprctl clients: {e}")
        return []


def get_hyprland_active_window():
    try:
        res = subprocess.run(["hyprctl", "-j", "activewindow"], capture_output=True, text=True, check=True)
        return json.loads(res.stdout)
    except Exception as e:
        log(f"Error querying activewindow: {e}")
        return {}


def find_client_by_address(clients, address):
    if not address:
        return None
    addr_clean = address.lower()
    for c in clients:
        if str(c.get("address", "")).lower() == addr_clean:
            return c
    return None


def is_terminal_client(client):
    if not client:
        return False
    # Check tags
    tags = client.get("tags") or []
    for tag in tags:
        clean_tag = tag.rstrip("*")
        if clean_tag == "terminal":
            return True

    # Check window class
    win_class = client.get("class") or ""
    if TERMINAL_PATTERN.match(win_class):
        return True

    initial_class = client.get("initialClass") or ""
    if TERMINAL_PATTERN.match(initial_class):
        return True

    return False


def focus_window(address):
    if not address:
        return False
    # Try Omarchy Quattro Hyprland Lua dispatch first
    cmd = f"hl.dsp.focus({{ window = 'address:{address}' }})"
    res = subprocess.run(["hyprctl", "dispatch", cmd], capture_output=True, text=True)
    if res.returncode == 0:
        return True

    # Fallback to standard Hyprland focuswindow dispatcher
    res2 = subprocess.run(["hyprctl", "dispatch", "focuswindow", f"address:{address}"],
                          capture_output=True, text=True)
    return res2.returncode == 0


def ensure_window_focused(target_address, client_title="", max_wait=0.25):
    """Verifies target window exists and is focused. Refocuses if needed."""
    clients = get_hyprland_clients()
    client = find_client_by_address(clients, target_address)
    if not client:
        return False, None

    active = get_hyprland_active_window()
    if str(active.get("address", "")).lower() == str(target_address).lower():
        return True, client

    # Refocus
    focus_window(target_address)
    start = time.time()
    while time.time() - start < max_wait:
        time.sleep(0.02)
        active = get_hyprland_active_window()
        if str(active.get("address", "")).lower() == str(target_address).lower():
            return True, client

    # Even if activewindow report lagged, client still exists
    return True, client


def wait_for_clipboard_ready(expected_mime=None, timeout=0.5):
    start = time.time()
    while time.time() - start < timeout:
        res = subprocess.run(["wl-paste", "--list-types"], capture_output=True, text=True)
        if res.returncode == 0:
            types = res.stdout.splitlines()
            if not expected_mime:
                return True
            if expected_mime in types:
                return True
            if expected_mime == "text/plain" and any(t.startswith("text/") for t in types):
                return True
        time.sleep(0.015)
    return False


def send_paste_keys(is_terminal):
    if is_terminal:
        # Terminal standard paste: Shift + Insert
        subprocess.run(["wtype", "-M", "shift", "-k", "Insert", "-m", "shift"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    else:
        # GUI standard paste: Ctrl + V
        subprocess.run(["wtype", "-M", "ctrl", "-k", "v", "-m", "ctrl"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def load_history(history_path=None):
    path = history_path or DEFAULT_HISTORY_PATH
    if not os.path.isfile(path) or not os.access(path, os.R_OK):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        log(f"Failed to read history from {path}: {e}")
        return []


def normalize_history_items(raw_items):
    valid = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        itype = item.get("type") or item.get("kind")
        if itype == "text":
            text = item.get("text")
            if isinstance(text, str) and len(text.strip()) > 0:
                valid.append({
                    "type": "text",
                    "text": text
                })
        elif itype == "image":
            path = item.get("path")
            if isinstance(path, str) and len(path) > 0:
                valid.append({
                    "type": "image",
                    "path": path,
                    "mime": item.get("mime", "image/png"),
                    "capturedAt": item.get("capturedAt", "")
                })
    return valid


def execute_bulk_paste(entries, target_address, delay_text=0.15, delay_image=0.35, requested_count=None):
    if not entries:
        log("No valid clipboard items to paste.")
        notify("Bulk Paste", "No valid clipboard items to paste.", urgency="normal")
        return

    if not target_address:
        log("No target window address provided.")
        notify("Bulk Paste Aborted", "No target window was specified.", urgency="normal")
        return

    # Verify target window
    clients = get_hyprland_clients()
    client = find_client_by_address(clients, target_address)
    if not client:
        log(f"Target window {target_address} not found among Hyprland clients.")
        notify("Bulk Paste Aborted", "The target window is no longer open.", urgency="normal")
        return

    app_name = client.get("title") or client.get("class") or "Application"
    if len(app_name) > 30:
        app_name = app_name[:27] + "…"

    is_terminal = is_terminal_client(client)
    log(f"Target application: '{app_name}' (class={client.get('class')}, is_terminal={is_terminal})")

    # Initial focus settlement
    focus_ok, client = ensure_window_focused(target_address, app_name, max_wait=0.3)
    if not focus_ok:
        notify("Bulk Paste Aborted", "Failed to focus target window.", urgency="normal")
        return
    time.sleep(0.06)

    succeeded = 0
    failed = 0
    total = len(entries)

    for idx, item in enumerate(entries):
        # 1. Safety focus check before each paste
        focus_ok, client = ensure_window_focused(target_address, app_name, max_wait=0.2)
        if not focus_ok:
            log(f"Target window disappeared mid-paste at item {idx + 1}")
            notify("Bulk Paste Stopped",
                   f"Target window closed after pasting {succeeded} of {total} items.",
                   urgency="normal")
            return

        itype = item.get("type")

        # 2. Replay content
        if itype == "text":
            text = item.get("text", "")
            try:
                proc = subprocess.Popen(
                    ["wl-copy", "--sensitive"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                proc.communicate(input=text.encode("utf-8"), timeout=2.0)
                wait_for_clipboard_ready("text/plain", timeout=0.3)
                time.sleep(0.03)

                send_paste_keys(is_terminal)
                time.sleep(delay_text)
                succeeded += 1
            except Exception as e:
                log(f"Failed to paste text entry {idx}: {e}")
                failed += 1

        elif itype == "image":
            img_path = item.get("path", "")
            mime = item.get("mime", "image/png")

            if not os.path.isfile(img_path) or not os.access(img_path, os.R_OK):
                log(f"Image file not readable: {img_path}")
                failed += 1
                continue

            try:
                with open(img_path, "rb") as f:
                    img_data = f.read()

                proc = subprocess.Popen(
                    ["wl-copy", "--sensitive", "--type", mime],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                proc.communicate(input=img_data, timeout=3.0)
                wait_for_clipboard_ready(mime, timeout=0.4)
                time.sleep(0.04)

                send_paste_keys(is_terminal)
                time.sleep(delay_image)
                succeeded += 1
            except Exception as e:
                log(f"Failed to paste image entry {idx}: {e}")
                failed += 1

        else:
            log(f"Skipping unsupported entry type: {itype}")
            failed += 1

    # 3. Final summary notification
    req = requested_count if requested_count is not None else total
    if failed == 0:
        if succeeded < req:
            summary = f"Pasted {succeeded} items (only {succeeded} available in history) into {app_name}."
        else:
            item_label = "item" if succeeded == 1 else "items"
            summary = f"Pasted {succeeded} {item_label} into {app_name}."
        notify("Bulk Paste Complete", summary, urgency="low")
    else:
        summary = f"Pasted {succeeded} items ({failed} failed) into {app_name}."
        notify("Bulk Paste Finished", summary, urgency="normal")

    log(f"Finished bulk paste: {succeeded} succeeded, {failed} failed out of {total} items.")


def main():
    parser = argparse.ArgumentParser(description="Omarchy Bulk Paste Runner")
    parser.add_argument("--count", "-n", type=int, default=None,
                        help="Number of items to paste from history (positive integer, 1-50)")
    parser.add_argument("--payload", type=str, default=None,
                        help="Path to JSON file containing snapshot items to paste")
    parser.add_argument("--history", type=str, default=None,
                        help="Path to clipboard history JSON file (defaults to ~/.local/state/omarchy/clipboard-history.json)")
    parser.add_argument("--target-window", type=str, required=True,
                        help="Hyprland client window address (e.g. 0x5571f7a63ec0)")
    parser.add_argument("--delay-text", type=float, default=0.15,
                        help="Delay in seconds after text paste (default: 0.15)")
    parser.add_argument("--delay-image", type=float, default=0.35,
                        help="Delay in seconds after image paste (default: 0.35)")

    args = parser.parse_args()

    payload_file = args.payload
    entries = []
    requested = args.count

    if payload_file:
        try:
            if os.path.isfile(payload_file):
                with open(payload_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        entries = data.get("items", [])
                        if not requested and "requestedCount" in data:
                            requested = data.get("requestedCount")
                    elif isinstance(data, list):
                        entries = data
        except Exception as e:
            log(f"Error loading payload {payload_file}: {e}")

    if not entries:
        if not args.count or args.count < 1:
            log("Error: Must specify valid --count (1-50) or --payload")
            sys.exit(1)

        count = min(50, args.count)
        raw_history = load_history(args.history)
        normalized = normalize_history_items(raw_history)

        take = min(count, len(normalized))
        # Newest items are at the beginning of history: slice(0, take)
        selected = normalized[:take]
        # Reverse to process in chronological order (oldest to newest)
        selected.reverse()
        entries = selected
        requested = count

    execute_bulk_paste(
        entries=entries,
        target_address=args.target_window,
        delay_text=args.delay_text,
        delay_image=args.delay_image,
        requested_count=requested
    )


if __name__ == "__main__":
    main()
