# Changelog

All notable changes to this project are listed here. Versions follow
[semantic versioning](https://semver.org/): `1.0.1` fixes bugs, `1.1.0` adds
features, `2.0.0` changes something in a way that may break existing use.

## [1.0.1] - 2026-09-24

Documentation release: the app itself is unchanged from 1.0.0.

### Documentation
- The installation guide now starts by installing Miniconda (`wget` on Linux,
  `curl` on macOS, the installer on Windows) instead of assuming conda is
  already there, including the one-time Terms of Service acceptance that
  recent conda versions require before creating an environment.

### Changed
- Automatic checks run on pushes to `main`, on version tags and on pull
  requests (no longer twice for a branch with an open pull request).

## [1.0.0] - 2026-09-24

First version for the course.

### Features
- Serial terminal with configurable port, baud rate (300–921 600), data bits,
  parity, stop bits and flow control; settings are remembered.
- Terminal view with visible line endings and named control characters;
  collapsible hex dump; ASCII strip (character / decimal / hex).
- Live chart of up to 8 signals from `key:value`, `key=value` or CSV lines.
- ASCII and HEX command sending (C-style `0xAA` accepted), selectable and
  custom line endings, 12 ASCII + 12 HEX saved commands, 8-direction keypad
  with START/STOP.
- **ECHO** switch to show or hide your own commands.
- Save the buffer to a file, or auto-save a timestamped capture on close.
- Demo mode with simulated sensor data, for use without hardware.
- Three themes: The Matrix, Light, Matte.
- Linux, Windows and macOS: the port list follows each system's naming
  (`/dev/ttyUSB0`, `COM3`, `/dev/cu.usbserial-…`).

### Quality
- 70+ automated tests, run on Linux, Windows and macOS after every push:
  byte encoding, chart formats, settings files, port detection, the serial
  thread through a virtual loopback port, and a start-up test that fails if
  any stylesheet is ignored.

### Fixed during development
- The app slowed down and could close after several minutes of steady data
  (hex dump and ASCII strip redrew everything on every byte).
- The Connect button never turned red while connected (invalid stylesheet).
- Typing `0xAA` in HEX mode sent `0A 0A`.
- Disconnecting while the port was still opening left the port open until
  the app was restarted.
- Connect with no port detected tried a stale port instead of explaining the
  likely cause (missing USB driver).
