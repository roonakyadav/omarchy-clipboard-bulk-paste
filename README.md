# Clipboard Bulk Paste for Omarchy

[![Omarchy Plugin](https://img.shields.io/badge/omarchy-plugin-10b981?style=flat-square)](https://plugins.omarchy.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)
[![Quickshell Native](https://img.shields.io/badge/quickshell-native-purple?style=flat-square)](https://quickshell.org/)
[![CI](https://github.com/roonakyadav/omarchy-clipboard-bulk-paste/actions/workflows/ci.yml/badge.svg)](https://github.com/roonakyadav/omarchy-clipboard-bulk-paste/actions/workflows/ci.yml)

**Clipboard Bulk Paste** is an open-source Quickshell overlay plugin for Omarchy Linux that supercharges clipboard history management with **chronological bulk pasting**, multi-image replaying, and Wayland window focus preservation.

---

## 1. What the Plugin Does

Clipboard Bulk Paste enhances Omarchy's native clipboard overlay by letting you paste multiple clipboard history items sequentially in one action. Instead of repeatedly switching windows, pressing `Super + Ctrl + V`, selecting an item, pasting it, and repeating that process for every single snippet or screenshot, you can copy several items across different sources and paste them all in chronological order into your destination application.

---

## 2. The Problem It Solves

When taking multiple consecutive screenshots (e.g., documenting a bug, compiling a tutorial, or annotating UI mockups) or copying multiple text snippets (e.g., code blocks, URLs, diff lines, or config parameters):
- Standard clipboard managers require **N separate round-trips**: switch window, summon clipboard, search, select, paste, refocus, repeat.
- The clipboard history stores the most recently copied item at the top (newest-first). If you copied Item 1, then Item 2, then Item 3, standard clipboard order displays `[3, 2, 1]`. Replaying them manually in original chronological sequence requires mental sorting and reverse selection.
- In Wayland environments, pasting programmatically into target windows often fails if window focus is lost or if terminal emulators require `Shift + Insert` instead of `Ctrl + V`.
- Repeated pastes can pollute clipboard history by re-registering each replayed item as a brand new copy event.

Clipboard Bulk Paste solves all of these challenges seamlessly in a single lightweight Quickshell overlay.

---

## 3. Features & Supported Content

- **Chronological Bulk Replay:** Specify how many items to paste (1 to 50); the plugin automatically reverses the newest-first history slice to paste in the exact order you originally copied them.
- **Multi-Image Support:** Seamlessly handles multiple screenshots and images (`image/png`, `image/jpeg`, `image/webp`, `image/gif`, `image/bmp`, `image/tiff`).
- **Mixed Content Pipelines:** Sequences text snippets, file paths, and images in the same bulk operation.
- **Terminal vs. GUI Auto-Detection:** Automatically inspects Hyprland client classes and tags to send `Shift + Insert` to terminal emulators (`foot`, `kitty`, `Alacritty`, `ghostty`, `wezterm`, `org.omarchy.*`) and `Ctrl + V` to GUI applications.
- **Zero History Pollution (`--sensitive`):** Replays items through `wl-copy --sensitive`, which Omarchy's `capture.sh` watcher detects and excludes from creating duplicate entries.
- **Window Focus Safety Barrier:** Queries Hyprland client state before each item, refocuses the target window if necessary, and immediately halts with a notification if the target application window is closed mid-operation.
- **Desktop Summary Alerts:** Issues a single clean notification via `omarchy-notification-send` (with fallback to `notify-send`) summarizing total succeeded and failed items.
- **Standard Clipboard Retained:** Full single-item search, preview, image thumbnail rendering, single paste, and copy-only functionality are 100% preserved.

---

## 4. How Bulk & Recursive Pasting Works

1. **Copy Your Items:** Copy several text snippets or take screenshots across your apps. Each item is captured into `~/.local/state/omarchy/clipboard-history.json` as usual.
2. **Summon Clipboard:** Press `Super + Ctrl + V` inside your target application (e.g., text editor, web form, terminal, or chat client).
3. **Set Count & Paste:** The top bulk bar displays:
   ```
   Paste last [ 10 ] items [ Paste ]
   ```
   Type the number of items you wish to paste (e.g., `5`), or press `Enter` directly to paste the default.
4. **Execution Flow:**
   - The overlay dismisses immediately so Hyprland focus returns to your active target application.
   - The standalone runner `bulk_paste.py` executes in the background.
   - It takes the newest *N* items from history and reverses them into chronological order.
   - For each item, it sets the Wayland clipboard via `wl-copy --sensitive`, waits until Wayland advertises readiness, sends the appropriate keystroke (`Ctrl + V` or `Shift + Insert`), and pauses for the configured settle delay.
   - Once all items are pasted, a single summary notification is displayed.

---

## 5. Multi-Image Behavior

- Screenshots and image files stored in `~/.local/state/omarchy/clipboard-images/` are read in binary format and copied with their exact MIME type (`--type image/png`, etc.).
- Applications that accept image pastes (such as rich text editors, chat applications, document editors, and social web apps) receive the images sequentially.
- If an image file was deleted or moved from disk prior to bulk paste, the runner marks that item as failed, skips it safely without crashing, and continues pasting remaining items.
- Image settle delays (default `0.35s`) ensure target applications have enough time to process the image buffer before the next paste event arrives.

---

## 6. Visual Previews & Screenshots

The plugin integrates directly into the standard Omarchy Quattro clipboard surface, adding a dedicated bulk paste bar above the search box:

```
+-------------------------------------------------------------------+
|  Paste last [ 10 ] items   [ 󰅌 Paste ]                             |
+-------------------------------------------------------------------+
|  Search clipboard...                                              |
+---------------------------------+---------------------------------+
| [IMG] Screenshot from Monday    | Preview Image / Full Text       |
| Code snippet from terminal      |                                 |
| URL from browser                |                                 |
+---------------------------------+---------------------------------+
```

*(Note: Live desktop screenshots depend on your active Omarchy theme. The marketplace automatically provides fallback card previews.)*

---

## 7. Installation

Install directly using the official Omarchy plugin CLI:

```bash
omarchy plugin add https://github.com/roonakyadav/omarchy-clipboard-bulk-paste.git --enable --yes
```

No sudo or pkexec is required. The plugin runs entirely with normal user permissions inside the user's desktop session.

---

## 8. Updating

To update to the latest release:

```bash
omarchy plugin update roonakyadav.clipboard-bulk-paste --yes
```

Or update all installed Git-managed plugins simultaneously:

```bash
omarchy plugin update --yes
```

---

## 9. Enabling and Disabling

To disable without removing the files:

```bash
omarchy plugin disable roonakyadav.clipboard-bulk-paste
```
*(When disabled, Omarchy automatically falls back to its built-in `omarchy.clipboard` manager.)*

To re-enable:

```bash
omarchy plugin enable roonakyadav.clipboard-bulk-paste
```

---

## 10. Uninstallation

To completely remove the plugin:

```bash
omarchy plugin remove roonakyadav.clipboard-bulk-paste --yes
```

Removing the plugin automatically restores the default Omarchy clipboard manager.

---

## 11. Keyboard Shortcuts & Navigation

| Key / Shortcut | Action |
| :--- | :--- |
| `Super + Ctrl + V` | Summon / dismiss the clipboard overlay (Omarchy system default) |
| `Enter` (inside number box) | Trigger bulk paste with the specified count |
| `Tab` | Move focus between the count box, the **Paste** button, and the search list |
| `Shift + Tab` (`Backtab`) | Move focus backward between controls |
| `Down Arrow` (from count box) | Move focus straight into the clipboard history search list |
| `Up Arrow` (from top item) | Move focus back up to the bulk count input box |
| `Escape` | Clear active search filter, or dismiss the overlay if search is empty |
| `Enter` (on list item) | Paste the selected individual item immediately |
| `Shift + Enter` (on list item) | Copy the selected item to clipboard without pasting |
| `Alt + Enter` (on list item) | Open file path in default file manager / viewer |
| `Delete` (on list item) | Delete the selected item from clipboard history |
| `Shift + Delete` | Open dialog to clear entire clipboard history |

---

## 12. Dependencies and Compatibility

### System Requirements
- **OS:** Omarchy Linux (v4.0.0+ / Quattro)
- **Compositor:** Hyprland
- **Shell:** `omarchy-shell` / [Quickshell](https://quickshell.org/)
- **Architecture:** x86_64, aarch64

### Runtime Dependencies
The following standard Wayland and desktop tools are used (all pre-installed on standard Omarchy):
- `python3` (v3.10+) — Executes the bulk paste runner
- `wl-clipboard` (`wl-copy`, `wl-paste`) — Wayland clipboard engine
- `wtype` — Wayland keystroke synthesizer
- `hyprctl` — Window manager IPC for client verification and focusing
- `jq` — JSON parsing helper
- `perl` — High-efficiency UTF-8/UTF-16 encoding parser in `capture.sh`

---

## 13. Troubleshooting

### Pasting doesn't occur into the target window
- Ensure the destination window is focused before opening the clipboard manager with `Super + Ctrl + V`.
- Some heavy web or Electron applications require slightly longer settle delays. You can adjust the delay flags when invoking `bulk_paste.py`:
  ```bash
  python3 ~/.config/omarchy/plugins/roonakyadav.clipboard-bulk-paste/bulk_paste.py --count 5 --target-window <address> --delay-text 0.25 --delay-image 0.5
  ```

### Terminal emulator receives garbled text
- The plugin detects terminal emulators and issues `Shift + Insert`. If your terminal emulator uses a non-standard window class, add a tag named `terminal` to your Hyprland window rule:
  ```lua
  hl.window_rule({ match = { class = "my-custom-term" }, tag = "terminal" })
  ```

### Check Plugin Validation
You can verify the plugin folder integrity at any time using:
```bash
omarchy plugin validate ~/.config/omarchy/plugins/roonakyadav.clipboard-bulk-paste
```

---

## 14. Testing

The repository includes comprehensive automated test suites covering JS history slicing, Python logic, boundary conditions, and desktop integration:

```bash
# Run all unit tests (isolated and headless-friendly)
python3 -m unittest discover -s tests -v

# Run the bulk paste test suite
python3 tests/test_bulk_paste.py -v

# Run the multi-image pipeline test suite
python3 tests/test_multi_image_paste.py -v

# Validate manifest against the Omarchy Quattro specification
omarchy plugin validate .
```

All unit tests execute in complete isolation from the live desktop session and never mutate your real clipboard history. When run within an active Hyprland desktop session, live integration tests automatically launch temporary GTK4 sandbox receivers to verify simulated keystroke delivery.

---

## 15. Known Limitations

- **Non-Hyprland Compositors:** The bulk paste runner relies on `hyprctl` for window address validation and focus restoration. It is designed specifically for Omarchy's Hyprland environment.
- **Maximum Bulk Count:** Bulk operations are capped at 50 items per batch to prevent accidental keyboard event flooding.
- **Closed Windows:** If the target application window is closed while a bulk paste is actively running, the runner immediately halts to prevent sending keystrokes to an unintended window.

---

## 16. License and Attribution

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) for full details.

Portions of this software are derived from the upstream Omarchy clipboard plugin:
- Copyright (c) 2024-2026 David Heinemeier Hansson and Omarchy contributors (https://github.com/basecamp/omarchy)
- Copyright (c) 2026 Ronak Yadav (Bulk paste implementation, multi-image pipeline, tests, and documentation)
