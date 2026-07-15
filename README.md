# autoRE — Multi-Tool Console System

**autoRE** is a collection of console tools for Linux, bundled with a unified launcher. It includes custom components (PcholHelper shell, autoReFM file manager) and embedded third-party utilities (ranger, kaa, bpytop, patool).

## Features

- **Unified launcher menu** for all tools (`main.py`)
- **PcholHelper** (`ph.py`) — interactive shell with:
  - user system (register, login, SHA-256 hashed passwords)
  - file management (ls, cd, cp, mv, rm, wr, rd, mkd, rmd)
  - archiving (7z, zip, tar.gz, tar.xz, tar.bz2, tar, rar)
  - `.phs` scripting language (commands, jumps)
  - `.phpmf` package manager
  - system info (CPU, memory, processes)
  - sound playback via pygame
- **autoReFM** (`autoReFM.py`) — file manager with built-in text editor (auto-detects UTF-8/16/32, cp1251, koi8-r, latin-1) and image viewer (ANSI true-color half-block rendering)
- **ranger** — console file manager with vi keybindings (GPLv3)
- **kaa** — console text editor with syntax highlighting, Python debugger, macros (MIT)
- **bpytop** — terminal resource monitor (Apache 2.0)
- **patool** — portable archive manager (60+ formats) (GPLv3)

## Installation

```bash
git clone <repo>
cd autoRe
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
# Main menu
python3 main.py

# Individual components
python3 src/ph.py              # PcholHelper
python3 src/ph.py --autostart  # PcholHelper with auto-start script
sudo python3 src/autoReFM.py   # File manager
python3 src/shell.py           # System shell
python3 src/kaa/runkaa.py      # kaa editor
python3 src/ranger/ranger.py   # ranger file manager
python3 src/bpytop/bpytop.py   # Resource monitor
```

## Menu

Running `main.py` shows:

```
|__Pchol__|autoRE|__v0.1__|
Select item:
    1: PcholShell
    2: System Shell
    3: Ranger
    4: autoRE File Manager
    5: Bpytop
    0: Exit
```

## Project Structure

```
autoRe/
├── main.py             # Launcher
├── requirements.txt    # Python dependencies
├── env/                # Python virtual environment
├── src/
│   ├── ph.py           # PcholHelper — custom shell
│   ├── autoReFM.py     # File manager + editor + image viewer
│   ├── shell.py        # Minimal system shell
│   ├── kaa/            # kaa editor (MIT)
│   │   └── runkaa.py   # kaa entry point
│   ├── ranger/         # ranger file manager (GPLv3)
│   ├── bpytop/         # bpytop resource monitor (Apache 2.0)
│   └── patool/         # patool archive manager (GPLv3)
```

## Dependencies

### Core
- pygame
- py-cpuinfo
- psutil
- py7zr
- rarfile
- pyterappeng
- keyboard
- urwid
- Pillow

### kaa editor
- curses_ex
- pyjf3
- setproctitle
- GitPython
- kaadbg
- pyenchant (optional, spell checker)

## License

GNU GPL v3 — custom components and original code. Embedded third-party tools are distributed under their respective licenses (MIT, Apache 2.0, GPLv3).
