# Hardware checklist

The automatic tests cover everything up to the USB cable. This checklist
covers the rest: run it with a real board **before tagging a version for the
course**. It takes about 15 minutes, plus a 10-minute run with the board
sending data.

Linux is required. Windows and macOS are optional; ask a student who uses
them to go through the same list.

## What the board must do

Any firmware works if it:

1. **Sends a numbered line every ~250 ms** at 115200 baud, 8N1, ending in
   `\r\n`, for example `Hola Mundo!! 1234`.
2. Optionally **answers or echoes** a received command, so sending can be
   checked too.

## Checklist

Version: `______`  Date: `______`  OS: `______`  Board: `______`

### Install
- [ ] Fresh clone and install following [INSTALL.md](../INSTALL.md) (the
      checklist at its top), in a new folder and a new environment.
- [ ] The app opens and **About** shows the version being released.

### Connect and receive
- [ ] The board appears in **PORT** (click ↺ if it was plugged in later).
- [ ] **Connect** → the button turns red and reads **Disconnect**; the status bar
      says `CONNECTED`.
- [ ] Lines arrive; the counter has **no gaps** (check a few consecutive lines).
- [ ] The **hex dump** and **ASCII strip** show the same bytes (`0D 0A` at each
      line end).
- [ ] The **CHART** tab plots the counter.

### Send
- [ ] Type a command with **CR+LF** selected, press Enter: it appears in amber
      and the board reacts.
- [ ] Uncheck **ECHO** and send again: the command is no longer shown twice.
- [ ] Check **ECHO** again. **HEX** mode: type `0xAA 0x55`; the field shows
      `AA 55` and the hex dump shows `AA 55` in the sent (TX) color.
- [ ] A **saved command** sends with its ↵ button; a **keypad** arrow sends
      `DIR:N` (or the matching direction).

### Connection edge cases
- [ ] Click **Connect** and **Disconnect** quickly, then **Connect** again:
      it reconnects normally (no "busy" / "Access denied").
- [ ] **Unplug** the board while connected: an error message appears and the
      app shows disconnected, without closing.
- [ ] Plug it back in, click ↺, **Connect**: data arrives again.

### Files, looks, stability
- [ ] **Save** writes the file in the folder the app was started from, and
      it contains the received lines.
- [ ] With **auto** checked, closing the app creates a timestamped capture file.
- [ ] Switch through all three **themes** while connected.
- [ ] Leave it receiving for **10 minutes**: no slowdown, no freeze.
- [ ] The log (`~/.config/serial_terminal/logs/serial_terminal.log`, see
      README) has no `ERROR` lines except the expected unplug error.

## Release steps

When the checklist passes:

1. Set the version in `serial_terminal/__init__.py` (`__version__ = 'X.Y.Z'`).
2. In `CHANGELOG.md`, add or finish the `## [X.Y.Z] - YYYY-MM-DD` section.
3. Commit, push, and wait for the three checks to be green.
4. Tag and publish:
   ```bash
   git tag -a vX.Y.Z -m "Version X.Y.Z"
   git push origin vX.Y.Z
   gh release create vX.Y.Z --title "vX.Y.Z" --notes "<the CHANGELOG section>"
   ```
   CI checks that the tag matches `__version__`.
5. Tell students to install that version:
   `git clone --branch vX.Y.Z https://github.com/namontoy/Taller5-Terminal.git`,
   or download it from the Releases page.
