# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-11-13

### Added
- **Bulk Paste Engine:** Sequential, chronological replay of the *N* newest clipboard history items into any focused Wayland application.
- **Chronological Ordering:** Reverses history stack (newest-first) to natural paste order (oldest-copied first).
- **Multi-Image & Mixed Pipeline:** Full support for sequential pasting of multiple screenshots, images (`image/png`, `image/jpeg`, etc.), and text items.
- **Dynamic Terminal Detection:** Automatically switches between GUI paste (`Ctrl+V`) and terminal paste (`Shift+Insert`) based on active Hyprland window classes and tags (`kitty`, `foot`, `Alacritty`, `ghostty`, `wezterm`, etc.).
- **Sensitive Replay:** Replays clipboard content using `wl-copy --sensitive` to prevent polluting history with duplicates or reordering.
- **Focus Safety Checks:** Automatically queries and restores window focus before each sequential item to avoid accidental pasting into unintended windows.
- **UI Integration:** Integrated bulk paste bar in the Quickshell overlay with number selector (1–50 items), status messaging, and keyboard navigation.
- **Desktop Notifications:** Emits consolidated summary alerts via `omarchy-notification-send` (with fallback to `notify-send`) upon completion.
- **Automated Test Suite:** Comprehensive unit and desktop integration tests for JS validation, ordering, window detection, and multi-image pipelines.
- **GitHub Actions CI:** Continuous integration testing on Python 3.12 with syntax and manifest validation.
