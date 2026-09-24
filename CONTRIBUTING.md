# Contributing

Thanks for helping improve the Taller5 Serial Terminal! Bug reports, fixes and
ideas from students are welcome. This page explains how to propose a change so
that everything that works today keeps working.

## Reporting a bug

Open an [issue](https://github.com/namontoy/Taller5-Terminal/issues/new/choose)
and pick **Bug report**. The form asks for the app version (**About** button),
your operating system, the board or USB adapter, and the **log file**:

| System | Log file |
|---|---|
| Linux / macOS | `~/.config/serial_terminal/logs/serial_terminal.log` |
| Windows | `%USERPROFILE%\.config\serial_terminal\logs\serial_terminal.log` |

The log is the most useful part: it records errors even when the window closes
without a message.

## Proposing a change

1. **Fork** the repository and create a branch for one topic
   (`fix-hex-input`, `add-baud-autodetect`…).
2. Set up the environment as in [INSTALL.md](INSTALL.md).
3. Make your change.
4. **Run the tests** from the project folder:
   ```bash
   python -m unittest discover tests
   python tests/smoke_test.py
   ```
   Both must pass. They need no hardware and no screen.
5. Open a **pull request**. The template asks a few short questions.

GitHub then runs the same tests on Linux, Windows and macOS. A pull request can
be merged when all three are green and the maintainer has reviewed it.

## The rules that keep things working

**A bug fix comes with a test that fails without the fix.** Write the test
first, check that it fails, then fix the code and check that it passes. That
way the bug can never come back unnoticed. Two examples in this project:

- `tests/test_protocol.py`, `test_c_style_0x_prefixes_are_accepted`: typing
  `0xAA` in HEX mode used to send the wrong bytes.
- `tests/test_serial_worker.py`, `StopWhileOpeningTest`: Disconnect during the
  port opening left the serial thread running.

**Keep the README true.** Several tests check what the README promises (the
chart line formats, what HEX mode sends, the 12 saved commands). If you change
that behavior on purpose, update the README and the tests together.

**Logic goes where it can be tested.** Byte and text conversions live in
`serial_terminal/protocol.py`, which has no GUI code; widgets only call it.
Prefer that pattern over putting logic inside widget classes.

**One topic per pull request.** Small pull requests are reviewed faster.

**Try it with a real board if you can**, and say so in the pull request
(which board, which operating system). The automatic tests can't plug in a USB
cable.

## For the maintainer

- A first-time contributor's pull request shows **Approve and run** before the
  checks start (GitHub's default protection for forks). Look at the changes
  first, then approve.
- Before tagging a version for the course, go through
  [docs/HARDWARE_CHECKLIST.md](docs/HARDWARE_CHECKLIST.md). The release steps are at the
  end of that file.
