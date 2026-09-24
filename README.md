# Serial Terminal

A Python serial terminal with real-time hex dump, live chart, and three themes.
Built with PyQt6, pyserial, and matplotlib.

---

## Quick start

```bash
# Create environment and install dependencies (first time only)
conda create -n taller5 python=3.12 -y
conda run -n taller5 pip install -r requirements.txt

# Run
conda activate taller5
python main.py
```

On Linux, two extra one-time steps are required before the app can open a port:
install the Qt XCB system libraries, and add your user to the `dialout` group
(`sudo usermod -aG dialout $USER`, then log out and back in). Without the second
one the port still appears in the dropdown but **Connect** fails with
`Permission denied`.

See [INSTALL.md](INSTALL.md) for full installation details, the Ubuntu 24.04
setup, fonts, and troubleshooting.

---

## Interface overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│  TOOLBAR   PORT ▾  BAUD ▾  DATA ▾  PARITY ▾  STOP ▾  FLOW ▾  [Connect] │
├─────────────────────────────────────────────────────────────────────────┤
│  STATUS    OFFLINE │ rx 0 B │ tx 0 B │ /dev/ttyUSB0 │ 9,600 baud │ 8N1 │
├──────────────────────────────────────────────────┬──────────┬───────────┤
│  TERMINAL / CHART  (tab)                         │  HEX     │  SIDEBAR  │
│                                                  │  DUMP    │           │
│                                                  │          │           │
├──────────────────────────────────────────────────┤  (<</>>) │           │
│  ASCII STRIP                                     │          │           │
├──────────────────────────────────────────────────┤          │           │
│  BOTTOM BAR   ✕  ⬇  buf 10k  file capture.txt  [Save] □auto│           │
└──────────────────────────────────────────────────┴──────────┴───────────┘
```

### Toolbar

| Control | Description |
|---------|-------------|
| **PORT ▾** | Dropdown of detected serial ports. Only `ttyUSB*`, `ttyACM*`, `ttyAMA*`, and `rfcomm*` devices appear — virtual terminals and legacy `ttyS*` ports are excluded. Click **↺** to rescan without restarting the app. |
| **BAUD ▾** | Standard baud rates from 300 to 921 600. |
| **DATA ▾** | Data bits: 5, 6, 7, or 8. |
| **PARITY ▾** | None, Even, Odd, Mark, Space. |
| **STOP ▾** | Stop bits: 1, 1.5, or 2. |
| **FLOW ▾** | None, RTS/CTS, XON/XOFF. |
| **Demo** | Starts a simulated data stream (sensor readings) without requiring hardware. Useful for testing the UI and chart. |
| **Connect / Disconnect** | Opens or closes the serial port. All port settings are locked while connected. |

All settings are saved automatically and restored on the next launch.

---

### Status bar

```
CONNECTED │ rx 1,024 B │ tx 48 B │ /dev/ttyUSB0 │ 9,600 baud │ 8N1 │ term CR+LF │
```

| Field | Meaning |
|-------|---------|
| OFFLINE / CONNECTED | Current connection state. |
| rx N B | Total bytes received since last clear. |
| tx N B | Total bytes transmitted since last clear. |
| Port | Active serial port path. |
| Baud | Active baud rate. |
| 8N1 | Frame format: data bits + parity initial + stop bits. |
| term … | Active end-of-command terminators. |
| [DEMO] | Shown in amber when demo mode is running. |

---

### Terminal view

The main area shows the incoming byte stream as text.

| Color | Meaning |
|-------|---------|
| Main foreground | Normal received bytes. |
| Amber | Bytes you sent (echoed back). |
| Amber, smaller | Control characters displayed as `[NAME]` — e.g. `[BEL]`, `[ESC]`. |
| Dim ↵ | Line-feed marker at the end of each line. |

The buffer holds the last **N** lines (configurable: 1 k / 5 k / 10 k / 50 k via the bottom bar).
When the limit is reached the oldest lines are discarded automatically.

**Auto-scroll** follows new data as it arrives.
Click **⬇** in the bottom bar to freeze the view in place — new data keeps arriving but the viewport stays still.
Dragging the scrollbar all the way to the bottom re-enables auto-scroll automatically.

---

### Chart panel

Click the **CHART** tab to switch from the terminal view to the live plot.
Data continues to accumulate in the background even when the terminal tab is active —
switching to the terminal tab and back will not lose any points.

The chart parser reads each complete line (terminated by LF) and tries to extract numeric values.
Lines that contain no numbers are silently ignored, so it is safe to mix data lines with
plain-text status messages in the same stream.

#### Signal limits

| Parameter | Value | Notes |
|-----------|-------|-------|
| Maximum signals (series) | **8** | Signals beyond the 8th are silently ignored |
| Points per signal | **200** | Rolling window — oldest point drops when a new one arrives |
| Supported number formats | integer, float, scientific | `42`, `3.14`, `1.5e-3`, `-0.7` |

Each signal gets a unique color from a fixed palette (green, orange, blue, red, purple, cyan, orange-red, yellow-green).
The legend is updated automatically every time a new signal name appears.

#### Supported line formats

The parser tries key:value / key=value first. If no named pairs are found it falls back to
positional parsing (comma, semicolon, or whitespace as delimiter).

| Format | Example line | Resulting signal names |
|--------|-------------|------------------------|
| Key `:` value | `temp:23.5 hum:65 press:1013` | `temp`, `hum`, `press` |
| Key `=` value | `val1=1.2 val2=3.4` | `val1`, `val2` |
| Comma-separated | `1.23, 4.56, 7.89` | `0`, `1`, `2` |
| Semicolon-separated | `1.23; 4.56` | `0`, `1` |
| Space / tab separated | `23.5  65.2  1013.0` | `0`, `1`, `2` |
| Mixed (named + text) | `T:23.5 status=OK count:42` | `T`, `count` (`status` skipped — not numeric) |

#### Signal naming rules

- Names come from the key in `key:value` or `key=value` pairs.
- Names must start with a letter or underscore and can contain letters, digits, and underscores — e.g. `rpm`, `axis_x`, `ch1`.
- When using positional format (CSV / semicolons / spaces), signals are named `0`, `1`, `2`, … in column order.
- The signal name is fixed the first time it appears. If later lines send a different number of columns the extra columns are added as new signals (up to the 8-signal limit).
- Signal names are **case-sensitive**: `Temp` and `temp` are two different signals.

#### Mixing named and positional signals

You can freely mix formats across different lines. Each line is parsed independently.
However, mixing named and positional formats in the **same stream** is not recommended
because positional signals named `0`, `1`, … may collide with key names.

#### Arduino / microcontroller examples

**Named pairs (recommended — self-documenting in the terminal view too):**

```cpp
// Arduino — one line per sample
Serial.print("T:");    Serial.print(temperature, 1);
Serial.print(" V:");   Serial.print(voltage, 2);
Serial.print(" H:");   Serial.println(humidity, 1);
// → T:23.5 V:3.28 H:61.4
```

**CSV (compact, good for high data rates):**

```cpp
// Arduino — comma-separated, no labels
Serial.print(temperature, 1);  Serial.print(',');
Serial.print(voltage, 2);      Serial.print(',');
Serial.println(humidity, 1);
// → 23.5,3.28,61.4   (series named 0, 1, 2)
```

**MicroPython:**

```python
import sys
print(f"T:{temperature:.1f} V:{voltage:.2f} H:{humidity:.1f}")
```

#### Demo mode signals

When **Demo** mode is active the app generates three synthetic signals
so the chart can be tested without hardware:

| Signal | Centre | Amplitude | Period | Noise | Description |
|--------|--------|-----------|--------|-------|-------------|
| `T` | 40 | ±8 | ~2 min | ±0.4 | Slow temperature-like drift |
| `V` | 60 | ±12 | ~8 s | ±2.0 | Fast voltage-like oscillation |
| `H` | 50 | ±15 | ~30 s | ±1.2 | Medium humidity-like wave |

All three are sine waves with different periods and a small amount of random noise,
centred approximately 10–20 units apart so all lines are visible on the same Y axis.

---

### ASCII strip

A compact horizontal strip below the terminal showing the most recent characters.
Each column displays the character, its decimal value, and its hex value.
The strip is updated continuously as data arrives.

---

### Hex dump panel

The collapsible panel on the right side of the terminal.
Click **>>** / **<<** to expand or collapse it with a smooth animation.

Each row shows:
- **Offset** (in hex) of the first byte in that row
- **8 hex bytes** — color-coded: green = normal, amber = sent, dim = control/NUL
- **ASCII representation** — printable characters shown, non-printable shown as `·`

The legend in the panel header explains the three colors:
- **● RX** — bytes received from the device
- **● TX** — bytes you sent (echoed)
- **● OFF** — row offset values

---

### Sidebar

#### Command

Type a command and press **Enter** or click **Send**.
Toggle **HEX** mode to send raw hex bytes:
- ASCII mode: `hello` → sends `68 65 6C 6C 6F`
- HEX mode: `68 65 6C 6C 6F` → sends those exact bytes

The **Send** button is disabled when not connected and when the input field is empty.

#### End of command (terminator)

Select which byte(s) are appended to every outgoing command.

| Button | Bytes sent |
|--------|-----------|
| LF `0x0A` | Line feed only |
| CR `0x0D` | Carriage return only |
| CR+LF `0x0D 0x0A` | Carriage return + line feed (most common) |
| NUL `0x00` | Null byte |

You can also define a **custom terminator** by clicking **+ add** and entering a single character or a hex code like `0x03`.
Click the chip again (it turns into a remove button) to delete a custom terminator.
Active terminators appear in the status bar under **term**.

Multiple terminators can be active at the same time.

#### Saved commands (presets)

Six numbered slots for frequently-used commands.
Type into a slot's text field to save a command, then click its number button to send it instantly.
Presets are saved to disk and restored on the next launch.

#### Keypad

A 3×3 directional pad for sending movement or navigation commands.
The center button toggles **START** / **STOP** (sends the configured command string for each).

#### Theme

Switch between three visual themes:

| Theme | Description |
|-------|-------------|
| **The Matrix** | Very dark background with phosphor-green text. High-contrast, easy on the eyes in the dark. |
| **Light** | Off-white background with dark text. Good for bright environments. |
| **Matte** | Dark warm-brown background with parchment-tinted text. |

The selected theme is persisted and applied at startup.

---

### Bottom bar

| Control | Description |
|---------|-------------|
| **✕** | Clears the terminal buffer, the chart data, the hex dump, and resets the rx/tx counters. |
| **⬇ / ⏸** | Toggle auto-scroll. ⬇ = following new data. ⏸ = viewport frozen. |
| **buf N k** | Buffer size selector: 1 k / 5 k / 10 k / 50 k characters. |
| **filename** | Base name used for manual and auto saves. |
| **Save** | Saves the current buffer to the file named in the field. |
| **auto** | When checked, saves the buffer automatically to a **timestamped file** when the application is closed. The filename uses the pattern `<base>_DDMMYY_HHMMSS.txt` — for example, `capture_300526_143022.txt`. Each close creates a new file; nothing is ever overwritten. |

---

## Configuration

Settings are saved automatically to:

```
~/.config/serial_terminal/config.json
```

The file is updated every time a setting changes (port, baud, theme, presets, etc.).
Deleting the file resets everything to defaults.

| Config key | Default | Description |
|-----------|---------|-------------|
| `port` | `/dev/ttyUSB0` | Last selected serial port |
| `baud` | `9600` | Baud rate |
| `data_bits` | `8` | Data bits |
| `parity` | `none` | Parity |
| `stop_bits` | `1` | Stop bits |
| `flow` | `none` | Flow control |
| `theme` | `matrix` | Active theme |
| `font_size` | `13` | Terminal font size (pt) |
| `buf_size` | `10000` | Terminal buffer size (characters) |
| `save_filename` | `capture.txt` | Base filename for saves |
| `active_terms` | `['0x0D 0x0A']` | Active end-of-command terminators |
| `presets` | `['', …]` | Six saved command presets |
| `custom_terms` | `[]` | User-defined custom terminators |

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| Python | 3.12 | Runtime |
| PyQt6 | ≥ 6.6 | GUI framework |
| pyserial | ≥ 3.5 | Serial port I/O |
| matplotlib | ≥ 3.8 | Real-time chart |

All dependencies are installed inside the `taller5` conda environment and do not affect the system Python.

---

## Project structure

```
Taller5-Terminal/
├── main.py                        Entry point
├── requirements.txt               Python dependencies
├── README.md                      This file
├── INSTALL.md                     Step-by-step installation guide
└── serial_terminal/
    ├── __init__.py                Char dataclass (code, ts, sent)
    ├── themes.py                  OKLCH color palettes + QSS generator
    ├── config.py                  JSON config load / save
    ├── serial_worker.py           QThread-based serial I/O (pyserial)
    ├── main_window.py             Main window, signal wiring, demo mode
    └── widgets/
        ├── toolbar.py             Port selector, baud, frame settings
        ├── status_bar.py          Live stats row
        ├── terminal_view.py       Scrolling char stream (QTextEdit)
        ├── ascii_strip.py         Last-chars strip (custom QPainter)
        ├── hex_panel.py           Collapsible hex dump (custom QPainter)
        ├── chart_panel.py         Real-time matplotlib chart
        ├── bottom_bar.py          Clear / scroll / buffer / save controls
        └── sidebar.py             Command input, presets, keypad, theme
```
