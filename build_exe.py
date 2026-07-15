#!/usr/bin/env python3
"""
autoRE — Build script for standalone Windows .exe
Creates a single-file executable that works without Python
and in Windows Recovery Environment (WinRE).

Usage:
    python build_exe.py              # build with defaults
    python build_exe.py --name autoRE  # custom name

Requirements:
    pip install pyinstaller
"""

import os
import sys
import shutil
import subprocess
import argparse


def build():
    parser = argparse.ArgumentParser(description='Build autoRE standalone .exe')
    parser.add_argument('--name', default='autoRE', help='Output executable name')
    parser.add_argument('--console', action='store_true', default=True, help='Console mode (default)')
    parser.add_argument('--no-console', dest='console', action='store_false', help='No console window')
    parser.add_argument('--uac-admin', action='store_true', default=True, help='Require admin (default)')
    parser.add_argument('--no-uac', dest='uac_admin', action='store_false', help='Don\'t require admin')
    parser.add_argument('--add-data', action='append', default=[], help='Extra data files')
    parser.add_argument('--clean', action='store_true', default=True, help='Clean build')
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    main_script = os.path.join(base_dir, 'main.py')

    if not os.path.exists(main_script):
        print(f"[ERROR] main.py not found in {base_dir}")
        sys.exit(1)

    pyinstaller = shutil.which('pyinstaller')
    if not pyinstaller:
        print("[ERROR] PyInstaller not found. Install: pip install pyinstaller")
        sys.exit(1)

    print("=" * 55)
    print(f"  Building {args.name}.exe — standalone Windows executable")
    print(f"  Works in WinRE, no Python required")
    print("=" * 55)

    for d in ['dist', 'build']:
        p = os.path.join(base_dir, d)
        if os.path.exists(p):
            print(f"  Cleaning {d}...")
            shutil.rmtree(p)

    cmd = [
        sys.executable, pyinstaller,
        '--onefile',
        '--console',
        '--clean',
        '--noconfirm',
        '--name', args.name,
        '--add-data', f'src{os.pathsep}src',
        '--hidden-import', 'src.ph',
        '--hidden-import', 'src.shell',
        '--hidden-import', 'src.exeTracker',
        '--hidden-import', 'src.regedit',
        '--hidden-import', 'src.autoReFM',
    ]

    if args.uac_admin:
        cmd.append('--uac-admin')
        print("  ✓ Admin rights requested (--uac-admin)")

    excludes = ['tkinter', 'matplotlib', 'numpy', 'PIL', 'pygame',
                'urwid', 'pyterappeng', 'psutil', 'cpuinfo',
                'py7zr', 'rarfile', 'keyboard', 'Pillow',
                'curses_ex', 'pyjf3', 'setproctitle', 'GitPython',
                'kaadbg', 'pyenchant']
    for ex in excludes:
        cmd.extend(['--exclude-module', ex])

    for data in args.add_data:
        cmd.extend(['--add-data', data])

    cmd.append(main_script)

    print(f"\n  Running: {' '.join(cmd[:6])} ...")
    print(f"  {' '.join(cmd[6:])}\n")

    result = subprocess.run(cmd, cwd=base_dir)

    if result.returncode == 0:
        output = os.path.join(base_dir, 'dist', f'{args.name}.exe')
        size = os.path.getsize(output) if os.path.exists(output) else 0
        print(f"\n{'=' * 55}")
        print(f"  ✓ BUILD COMPLETE!")
        print(f"  Output: {output}")
        print(f"  Size:   {size / 1024 / 1024:.1f} MB")
        print(f"{'=' * 55}")
        print()
        print(f"  Run:         {output}")
        print(f"  WinRE:       Copy to USB, boot WinRE, run from X:\\")
        print(f"  Admin:       {args.name}.exe --regedit")
        print(f"  Tracker:     {args.name}.exe --tracker virus.exe")
    else:
        print(f"\n[ERROR] Build failed (code {result.returncode})")
        sys.exit(1)


if __name__ == '__main__':
    build()
