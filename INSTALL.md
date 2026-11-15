# Installing CometTrain

CometTrain is a single Python file with no third-party dependencies. "Installing"
it means putting `comettrain.py` somewhere and having a Python 3.9+ interpreter.

## 1. Prerequisite: Python 3.9 or newer

Check what you have:

```bash
python3 --version
```

CometTrain is tested on CPython 3.11 on Linux; it uses only `argparse`, `datetime`,
`sys` and `textwrap`, so 3.9 and newer all work. macOS ships `python3` with the
command line developer tools; on Linux use your distribution's `python3` package.

There is nothing else to install: no pip packages, no compiler, no service, no
database. `requirements.txt` exists for convention and resolves to an empty set.

## 2. Run the setup check

From the project directory:

```bash
bash install.sh
```

The script

- verifies that `python3` exists and is at least 3.9 (`PYTHON=python3.11 bash install.sh`
  to force a specific interpreter),
- byte-compiles `comettrain.py`,
- imports the module and prints the catalogue size.

It installs nothing, needs no privileges, writes nothing outside the project, and
exits. It never starts a long-running process.

## 3. Try it

```bash
python3 comettrain.py list
python3 comettrain.py show encke
python3 comettrain.py perihelion --date 2023-10-20 --window 30
python3 comettrain.py calendar --days 3650
```

## 4. Run the demo (optional)

```bash
bash demo.sh
```

Runs every surface unattended, prints each command's exit code, and exits non-zero
if any surface misbehaved. `demo/transcript.txt` holds a captured run.

## 5. Run the tests (optional)

```bash
python3 -m unittest discover -s tests
```

The suite uses the standard library `unittest` runner; `python3 -m pytest tests`
runs exactly the same tests if pytest happens to be installed.

## Uninstalling

Delete the directory. CometTrain creates no files outside it, so nothing else is
left behind. (`install.sh` / the import check may leave a `__pycache__/` directory
next to `comettrain.py`; it is safe to delete.)

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `install: python3 was not found on PATH` | Python 3 is not installed or not on `PATH`; install it, or run `PYTHON=/path/to/python3 bash install.sh` |
| `install: Python 3.9 or newer is required` | The interpreter is too old; use `PYTHON=python3.11 bash install.sh` |
| `SyntaxError` when running the tool | You are on Python 2 or a pre-3.9 interpreter; run it as `python3 comettrain.py` |
| `error: argument --date: invalid date '2023-02-30'` | CometTrain rejects impossible calendar dates rather than rolling them over — use a real date |
| `no comet matched '…'` | The `show` query is a case-insensitive substring of a name or alias; run `python3 comettrain.py list` to see every name |
