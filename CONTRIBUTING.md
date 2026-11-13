# Contributing to Clipboard Bulk Paste for Omarchy

Thank you for your interest in contributing to **Clipboard Bulk Paste**!

## Development Guidelines

1. **Philosophy:** Keep changes focused, correct, performant, and safe. Avoid adding heavy external runtime dependencies.
2. **Upstream Attribution:** When modifying files derived from upstream Omarchy, preserve licensing notices and attribution comments.
3. **Safety & Security:** Plugins run within the Omarchy shell process. Avoid shell injections, insecure temporary file creation, unvalidated paths, or destructive operations.
4. **Testing:** All new features and bug fixes must include corresponding tests.

## Running Tests Locally

Run the complete test suite:

```bash
# Run all unit tests (works headless and in CI)
python3 -m unittest discover -s tests -v

# Run specific test suites
python3 tests/test_bulk_paste.py -v
python3 tests/test_multi_image_paste.py -v
```

If you are running in an active Omarchy Hyprland desktop session, the desktop integration tests will automatically execute live against temporary GTK4 windows. In headless or CI environments without `WAYLAND_DISPLAY`, integration tests are cleanly skipped while all unit tests are verified.

## Manifest Validation

Always validate the plugin manifest against the official Omarchy specification before opening a pull request:

```bash
omarchy plugin validate .
```

## Pull Request Process

1. Fork the repository and create your feature branch: `git checkout -b feature/my-new-feature`
2. Commit your changes with clear, descriptive commit messages.
3. Ensure all tests pass and manifest validation succeeds.
4. Push to your branch and open a Pull Request.
