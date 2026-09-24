# Serial Terminal — Installation Guide

Tested target: **Ubuntu 24.04 LTS** (also works on Linux Mint 21.x / Ubuntu 22.04,
macOS and Windows). Everything not listed here is contained in the project folder.

---

## Requirements

| Requirement | Notes |
|---|---|
| **Python 3.12** | Ubuntu 24.04 ships this by default; conda can also provide it |
| **PyQt6 >= 6.6** | GUI framework — installed with pip inside the environment |
| **pyserial >= 3.5** | Serial port communication — installed with pip |
| **matplotlib >= 3.8** | Real-time chart panel — installed with pip |
| **Qt XCB system libraries** | Linux only — see [step 1](#1-system-packages-linux-only) |
| **`dialout` group membership** | Linux only, **required to open serial ports** — see [step 2](#2-serial-port-permissions-linux-required) |

---

## Checklist (Ubuntu 24.04)

Work down the list. Each row has a command that **verifies** the step actually
worked — do not move on until the "Expected" column matches, since several of
these fail silently and only show up much later as a confusing symptom.

| ☐ | Step | Verify with | Expected |
|---|---|---|---|
| ☐ | 1 — Qt XCB system libraries installed | `dpkg -s libxcb-cursor0 \| grep Status` | `Status: install ok installed` |
| ☐ | 2 — User added to `dialout` | `sudo usermod -aG dialout $USER` | *(no output)* |
| ☐ | 2 — **Logged out and back in** after that | `groups` | output contains `dialout` |
| ☐ | 3 — `brltty` not stealing the adapter | `dmesg \| tail -20` after plugging in | no `brltty` lines |
| ☐ | 3 — Adapter present and stable | `ls -l /dev/ttyUSB* /dev/ttyACM*` | a device, still there 10 s later |
| ☐ | 3 — Device is readable by you | `test -r /dev/ttyUSB0 && echo OK` | `OK` |
| ☐ | 4 — Environment created | `.venv/bin/python -V` (or `conda run -n taller5 python -V`) | `Python 3.12.x` |
| ☐ | 4 — Dependencies installed | `.venv/bin/python -c "import PyQt6, serial, matplotlib; print('OK')"` | `OK` |
| ☐ | 5 — GUI opens | `.venv/bin/python main.py` | window appears, no `xcb` error |
| ☐ | 6 — GUI works without hardware | click **Demo** in the toolbar | text scrolls, chart moves |
| ☐ | 6 — Serial works | select the port, click **Connect** | status bar shows `CONNECTED` |

If any row fails, jump to the matching section below, or to
[Troubleshooting](#troubleshooting).

> Substitute your real device path for `/dev/ttyUSB0`, and use the conda
> equivalents from [step 4](#4-python-environment) if you chose Option B.

---

## Linux (Ubuntu 24.04) — full setup

### 1. System packages (Linux only)

The PyQt6 wheel bundles Qt itself, but **not** the X/XCB libraries Qt's platform
plugin links against. On a fresh or minimal Ubuntu install these are missing and
the app exits immediately with a message about `xcb` or "could not load the Qt
platform plugin".

```bash
sudo apt update
sudo apt install -y \
    libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
    libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-sync1 \
    libxcb-util1 libxcb-xfixes0 libxcb-xkb1 \
    libxkbcommon-x11-0 libegl1 libgl1
```

> **Fedora / RHEL equivalent:** `sudo dnf install xcb-util-cursor xcb-util-wm
> xcb-util-image xcb-util-keysyms xcb-util-renderutil libxkbcommon-x11
> mesa-libEGL mesa-libGL`

### 2. Serial port permissions (Linux, required)

On Ubuntu, `/dev/ttyUSB*` and `/dev/ttyACM*` are owned by the `dialout` group and
a new user is **not** a member. This is the single most common installation
failure, and it is misleading: **the port still shows up in the PORT dropdown**
(the scan reads `/sys`, which needs no permission) — only pressing **Connect**
fails, with:

```
PermissionError: [Errno 13] Permission denied: '/dev/ttyUSB0'
```

Fix it once:

```bash
sudo usermod -aG dialout $USER
```

Then **log out and log back in** (a reboot also works). Group membership is only
applied to new login sessions — reopening the terminal is not enough. Verify:

```bash
groups | grep dialout        # must print a line containing "dialout"
```

For the current terminal only, without logging out: `newgrp dialout`.

### 3. Free the USB adapter from `brltty` (Linux)

Ubuntu 22.04 and later ship `brltty` (braille display support), which claims
CH340 and CP210x USB-serial adapters. Symptom: `/dev/ttyUSB0` appears when you
plug the device in, then **disappears a few seconds later**, or never appears at
all.

Check whether it applies to you:

```bash
sudo dmesg | tail -20            # look for "brltty" right after you plug in
```

If it does, remove it (it is not needed unless you actually use a braille display):

```bash
sudo apt remove -y brltty
```

Then unplug and replug the adapter.

### 4. Python environment

Pick **one** of the two options below.

#### Option A — venv (recommended on Ubuntu 24.04, no conda needed)

Ubuntu 24.04 already has Python 3.12. Note that a plain `pip install` into the
system Python is blocked by PEP 668 ("externally-managed-environment"), so a
virtual environment is mandatory:

```bash
sudo apt install -y python3-venv          # not installed by default
cd /path/to/Taller5-Terminal
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

#### Option B — conda

```bash
conda create -n taller5 python=3.12 -y
conda run -n taller5 pip install -r requirements.txt
```

### 5. Run

**venv:**
```bash
cd /path/to/Taller5-Terminal
.venv/bin/python main.py
```

**conda:**
```bash
cd /path/to/Taller5-Terminal
conda activate taller5
python main.py
```

or, without activating:

```bash
conda run --no-capture-output -n taller5 python main.py
```

> **Do not use a bare `conda run` for this app.** Without
> `--no-capture-output`, conda buffers stdout/stderr and a startup crash can
> produce no visible error at all.
>
> **Do not set `DISPLAY=:0` manually.** When you run from a desktop terminal the
> display is already configured correctly — Ubuntu 24.04 defaults to a Wayland
> session, where forcing `DISPLAY=:0` can point at nothing. Set `DISPLAY`
> yourself only when running over SSH or from a headless context.

The PyQt6 wheel bundles both the `xcb` and `wayland` platform plugins, so X11 and
Wayland sessions both work. To force one:
`QT_QPA_PLATFORM=xcb ...` or `QT_QPA_PLATFORM=wayland ...`.

### 6. Verify without hardware

The toolbar has a **Demo** button that generates a simulated data stream. If Demo
mode draws text and the chart moves, the GUI half of the install is correct and
any remaining problem is serial-port related (steps 2 and 3).

---

## macOS / Windows

```bash
conda create -n taller5 python=3.12 -y
conda run -n taller5 pip install -r requirements.txt
conda activate taller5
python main.py
```

No extra system packages are needed. On Windows the USB-serial adapter usually
needs a vendor driver (CH340 / CP210x / FTDI) before the port appears.

---

## Optional — Fonts

The app is designed around **JetBrains Mono** and **IBM Plex Mono**. If neither is
installed, Qt falls back to the system monospace font — the app works, it just
does not look exactly as designed.

**Ubuntu / Debian:**
```bash
sudo apt install -y fonts-jetbrains-mono fonts-ibm-plex
```

**Manual download:**
- JetBrains Mono — https://github.com/JetBrains/JetBrainsMono/releases
- IBM Plex — https://github.com/IBM/plex/releases

---

## Troubleshooting

**Always start here:** the app writes a rotating log to

```
~/.config/serial_terminal/logs/serial_terminal.log
```

Unhandled exceptions, Qt warnings and serial errors all land there, including
cases where the window closes without printing anything to the terminal.

| Symptom | Cause | Fix |
|---|---|---|
| `Could not load the Qt platform plugin "xcb"` | Missing system libraries | [Step 1](#1-system-packages-linux-only). Re-run with `QT_DEBUG_PLUGINS=1` to see exactly which `.so` is missing. |
| Port is listed, but **Connect** fails with `Permission denied` | Not in `dialout` group | [Step 2](#2-serial-port-permissions-linux-required) — and remember to log out/in |
| `/dev/ttyUSB0` appears then vanishes | `brltty` claimed the adapter | [Step 3](#3-free-the-usb-adapter-from-brltty-linux) |
| PORT dropdown is empty | Adapter not enumerated, or non-matching name | `ls -l /dev/tty{USB,ACM}*` and `sudo dmesg \| tail`. The app only lists `ttyUSB*`, `ttyACM*`, `ttyAMA*`, `ttyXRUSB*` and `rfcomm*` (`serial_terminal/widgets/toolbar.py`). |
| Port listed but `Device or resource busy` | Another program holds it (ModemManager, a second terminal, Arduino IDE) | `sudo fuser -v /dev/ttyUSB0` to find it. Persistent ModemManager grabs: `sudo systemctl disable --now ModemManager`. |
| App exits with no message at all | `conda run` swallowed the traceback | Re-run with `conda run --no-capture-output`, or read the log file above |
| Chart tab shows "matplotlib is not installed" | Deps installed into a different environment | Re-run the install step, confirm with `python -c "import matplotlib"` inside the same env |
| `error: externally-managed-environment` from pip | Installing into system Python on Ubuntu 24.04 | Use a venv or conda — [step 4](#4-python-environment). Do **not** use `--break-system-packages`. |

---

## Updating the environment

If a new version of the app requires additional libraries, re-run the install
step inside the existing environment:

```bash
.venv/bin/pip install -r requirements.txt          # venv
conda run -n taller5 pip install -r requirements.txt   # conda
```

`requirements.txt` in the project root always reflects the current dependencies.
