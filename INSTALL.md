# Serial Terminal — Installation Guide

Tested target: **Ubuntu 24.04 LTS** (also works on Linux Mint 21.x / Ubuntu 22.04).
**Windows** and **macOS** are supported and community-tested; see
[Windows](#windows) and [macOS](#macos). Everything not listed here is contained in the project folder.

---

## Requirements

| Requirement | Notes |
|---|---|
| **Conda (Miniconda)** | Creates the isolated Python environment — see [step 1](#1-install-miniconda-conda) |
| **Python 3.12** | Installed by conda inside the environment (Ubuntu 24.04 also ships it, for the venv alternative) |
| **PyQt6 >= 6.6** | GUI framework — installed with pip inside the environment |
| **pyserial >= 3.5** | Serial port communication — installed with pip |
| **matplotlib >= 3.8** | Real-time chart panel — installed with pip |
| **Qt XCB system libraries** | Linux only — see [step 2](#2-system-packages-linux-only) |
| **`dialout` group membership** | Linux only, **required to open serial ports** — see [step 3](#3-serial-port-permissions-linux-required) |

---

## Checklist (Ubuntu 24.04)

Work down the list. Each row has a command that **verifies** the step actually
worked — do not move on until the "Expected" column matches, since several of
these fail silently and only show up much later as a confusing symptom.

| ☐ | Step | Verify with | Expected |
|---|---|---|---|
| ☐ | 1 — Miniconda installed (**new terminal** opened afterwards) | `conda --version` | `conda 26.x` (any version) |
| ☐ | 1 — Terms of Service accepted | `conda tos` | a date in the **Accepted** column for both channels |
| ☐ | 2 — Qt XCB system libraries installed | `dpkg -s libxcb-cursor0 \| grep Status` | `Status: install ok installed` |
| ☐ | 3 — User added to `dialout` | `sudo usermod -aG dialout $USER` | *(no output)* |
| ☐ | 3 — **Logged out and back in** after that | `groups` | output contains `dialout` |
| ☐ | 4 — `brltty` not stealing the adapter | `dmesg \| tail -20` after plugging in | no `brltty` lines |
| ☐ | 4 — Adapter present and stable | `ls -l /dev/ttyUSB* /dev/ttyACM*` | a device, still there 10 s later |
| ☐ | 4 — Device is readable by you | `test -r /dev/ttyUSB0 && echo OK` | `OK` |
| ☐ | 5 — Environment created | `conda run -n taller5 python -V` | `Python 3.12.x` |
| ☐ | 5 — Dependencies installed | `conda run -n taller5 python -c "import PyQt6, serial, matplotlib; print('OK')"` | `OK` |
| ☐ | 6 — GUI opens | `conda run --no-capture-output -n taller5 python main.py` | window appears, no `xcb` error |
| ☐ | 7 — GUI works without hardware | click **Demo** in the toolbar | text scrolls, chart moves |
| ☐ | 7 — Serial works | select the port, click **Connect** | status bar shows `CONNECTED` |

If any row fails, jump to the matching section below, or to
[Troubleshooting](#troubleshooting).

> Substitute your real device path for `/dev/ttyUSB0`. If you chose the venv
> alternative in [step 5](#5-python-environment), skip the step 1 rows and use
> `.venv/bin/python` instead of `conda run -n taller5 python`.

---

## Linux (Ubuntu 24.04) — full setup

### 1. Install Miniconda (conda)

Conda creates an isolated Python environment for the app, so nothing is
installed into the system Python. Check first whether you already have it:

```bash
conda --version
```

If that prints a version, skip to [step 2](#2-system-packages-linux-only).
Otherwise, download and install Miniconda into your home folder:

```bash
mkdir -p ~/miniconda3
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda3/miniconda.sh
bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3
rm ~/miniconda3/miniconda.sh
```

Then make the `conda` command available in every new terminal:

```bash
source ~/miniconda3/bin/activate
conda init --all
```

**Close the terminal and open a new one.** The prompt now starts with
`(base)`, and `conda --version` prints a version.

Finally, accept Anaconda's Terms of Service for its package channels. Recent
conda versions require this once; without it, creating the environment in
step 5 stops with *"Terms of Service have not been accepted"*:

```bash
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
```

> **Notes**
> - `wget: command not found` on a minimal install: `sudo apt install -y wget`.
> - **ARM computers** (e.g. Raspberry Pi 64-bit; check with `uname -m`, which
>   prints `aarch64`): use `Miniconda3-latest-Linux-aarch64.sh` in the `wget` line.
> - The `-b` option installs without questions, which means accepting the
>   Miniconda license.
> - Don't want `(base)` active in every terminal?
>   `conda config --set auto_activate false` (use `conda activate` when needed).

### 2. System packages (Linux only)

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

### 3. Serial port permissions (Linux, required)

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

### 4. Free the USB adapter from `brltty` (Linux)

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

### 5. Python environment

#### Option A — conda (recommended)

With conda from [step 1](#1-install-miniconda-conda), inside the project folder:

```bash
cd /path/to/Taller5-Terminal
conda create -n taller5 python=3.12 -y
conda run -n taller5 pip install -r requirements.txt
```

#### Option B — venv (without conda)

Ubuntu 24.04 already has Python 3.12, so a plain virtual environment also
works. A `pip install` into the system Python is blocked by PEP 668
("externally-managed-environment"), so the virtual environment is mandatory:

```bash
sudo apt install -y python3-venv          # not installed by default
cd /path/to/Taller5-Terminal
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 6. Run

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
> **venv:** `cd /path/to/Taller5-Terminal`, then `.venv/bin/python main.py`.
>
> **Do not set `DISPLAY=:0` manually.** When you run from a desktop terminal the
> display is already configured correctly — Ubuntu 24.04 defaults to a Wayland
> session, where forcing `DISPLAY=:0` can point at nothing. Set `DISPLAY`
> yourself only when running over SSH or from a headless context.

The PyQt6 wheel bundles both the `xcb` and `wayland` platform plugins, so X11 and
Wayland sessions both work. To force one:
`QT_QPA_PLATFORM=xcb ...` or `QT_QPA_PLATFORM=wayland ...`.

### 7. Verify without hardware

The toolbar has a **Demo** button that generates a simulated data stream. If Demo
mode draws text and the chart moves, the GUI half of the install is correct and
any remaining problem is serial-port related (steps 3 and 4).

---

## Windows

Supported and community-tested: the app is started automatically on Windows
after every change (see the *smoke test* badge in the README), but it is
developed on Linux.

1. **Install Miniconda.** Download
   [Miniconda3-latest-Windows-x86_64.exe](https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe),
   run it and keep the default options ("Just Me", default folder).
2. Open **Anaconda Prompt (miniconda3)** from the Start menu and accept the
   Terms of Service once (without this, `conda create` stops with
   *"Terms of Service have not been accepted"*):
   ```bat
   conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
   conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
   ```
3. Install and run, in the same Anaconda Prompt:
   ```bat
   cd path\to\Taller5-Terminal
   conda create -n taller5 python=3.12 -y
   conda activate taller5
   pip install -r requirements.txt
   python main.py
   ```
4. Ports appear in **PORT** as `COM3`, `COM4`, … No permission setup is needed.

**USB driver.** If the board doesn't appear, open **Device Manager**. A device
under *Other devices* with a yellow warning sign means the driver is missing:

| Adapter / board | Driver |
|---|---|
| CH340 / CH341 (cheap Arduino clones) | WCH CH341SER driver |
| CP210x (many ESP32 boards) | Silicon Labs CP210x VCP driver |
| FTDI | FTDI VCP driver (usually installed automatically by Windows Update) |
| STM32 Nucleo (ST-LINK) | ST-LINK driver, installed together with STM32CubeIDE |

**"Access is denied" when connecting.** On Windows only one program at a time
can open a COM port. Close the other one: Arduino IDE (Serial Monitor),
STM32CubeIDE's terminal, PuTTY, a second copy of this app…

## macOS

Supported and community-tested, like Windows.

**Install Miniconda** (skip if `conda --version` already works). macOS has
`curl` instead of `wget`. Use `MacOSX-arm64` on Apple Silicon (M1 and later)
and `MacOSX-x86_64` on Intel Macs; `uname -m` prints `arm64` or `x86_64`:

```bash
mkdir -p ~/miniconda3
curl https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-arm64.sh -o ~/miniconda3/miniconda.sh
bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3
rm ~/miniconda3/miniconda.sh
source ~/miniconda3/bin/activate
conda init --all
```

Close the terminal, open a new one, and accept the Terms of Service once:

```bash
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
```

Then install and run:

```bash
cd /path/to/Taller5-Terminal
conda create -n taller5 python=3.12 -y
conda activate taller5
pip install -r requirements.txt
python main.py
```

- Ports appear as `/dev/cu.usbserial-…` or `/dev/cu.usbmodem…`. Long names are
  cut off in the box; hover over it, or open the list, to see the whole name.
- Built-in entries such as `Bluetooth-Incoming-Port` are hidden on purpose.
- Recent macOS versions include drivers for most adapters. If a board doesn't
  appear, install the vendor driver (CH340, CP210x) and allow it in
  *System Settings → Privacy & Security*.
- `Resource busy` when connecting means another program has the port open.

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
| `conda: command not found` | Miniconda not installed, or the terminal was opened before `conda init` | [Step 1](#1-install-miniconda-conda); then **open a new terminal** |
| `Terms of Service have not been accepted` when creating the environment | Recent conda versions require accepting Anaconda's terms once | Run the two `conda tos accept` commands from [step 1](#1-install-miniconda-conda) |
| `Could not load the Qt platform plugin "xcb"` | Missing system libraries | [Step 2](#2-system-packages-linux-only). Re-run with `QT_DEBUG_PLUGINS=1` to see exactly which `.so` is missing. |
| Port is listed, but **Connect** fails with `Permission denied` | Not in `dialout` group | [Step 3](#3-serial-port-permissions-linux-required) — and remember to log out/in |
| `/dev/ttyUSB0` appears then vanishes | `brltty` claimed the adapter | [Step 4](#4-free-the-usb-adapter-from-brltty-linux) |
| PORT dropdown is empty (Linux) | Adapter not enumerated, or non-matching name | `ls -l /dev/tty{USB,ACM}*` and `sudo dmesg \| tail`. The app only lists `ttyUSB*`, `ttyACM*`, `ttyAMA*`, `ttyXRUSB*` and `rfcomm*` (`serial_terminal/widgets/toolbar.py`). |
| PORT shows *(none detected)* (Windows / macOS) | USB driver missing | [Windows](#windows): check Device Manager. [macOS](#macos): install and allow the vendor driver. Then click **↺**. |
| **Connect** says *No serial port detected* | Nothing is plugged in, or the driver is missing | Plug in the board, click **↺**; see the rows above. |
| `Access is denied` (Windows) or `Resource busy` (macOS) | Another program has the port open | Close Arduino IDE, STM32CubeIDE's terminal, PuTTY, etc. |
| Port listed but `Device or resource busy` | Another program holds it (ModemManager, a second terminal, Arduino IDE) | `sudo fuser -v /dev/ttyUSB0` to find it. Persistent ModemManager grabs: `sudo systemctl disable --now ModemManager`. |
| App exits with no message at all | `conda run` swallowed the traceback | Re-run with `conda run --no-capture-output`, or read the log file above |
| Chart tab shows "matplotlib is not installed" | Deps installed into a different environment | Re-run the install step, confirm with `python -c "import matplotlib"` inside the same env |
| `error: externally-managed-environment` from pip | Installing into system Python on Ubuntu 24.04 | Use conda or a venv — [step 5](#5-python-environment). Do **not** use `--break-system-packages`. |

---

## Updating the environment

If a new version of the app requires additional libraries, re-run the install
step inside the existing environment:

```bash
.venv/bin/pip install -r requirements.txt          # venv
conda run -n taller5 pip install -r requirements.txt   # conda
```

`requirements.txt` in the project root always reflects the current dependencies.
