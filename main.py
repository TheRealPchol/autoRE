from src.autoReFM import start as autorefm
from src.shell import shell
from src.exeTracker import EXETracker
import sys
import subprocess
import platform
import os
import time
from pyterappeng.core import get_key
from runph import runph as runph
import asyncio

def ranger():
    script = os.path.join(os.path.dirname(__file__), 'src', 'ranger', 'ranger.py')
    try:
        subprocess.run([sys.executable, '-O', script])
    except Exception:
        pass

def start_bpytop():
    script = os.path.join(os.path.dirname(__file__), 'src', 'bpytop', 'bpytop.py')
    subprocess.run([sys.executable, script])

def start_exe_tracker():
    print(f'\033[44;97m{"="*60}\033[0m')
    print(f'\033[1m  🕵️ exeTracker — введите путь к .exe файлу\033[0m')
    print(f'\033[44;97m{"="*60}\033[0m\n')
    path = input('  Путь к EXE: ').strip().strip('"\'')
    if not path:
        return
    timeout_str = input('  Тайм-аут в секундах (Enter = без лимита): ').strip()
    timeout = int(timeout_str) if timeout_str.isdigit() else None
    print()
    tracker = EXETracker(path, timeout=timeout)
    tracker.run()
    input('\n  Нажми Enter для возврата в меню...')

def start_regedit():
    from src.regedit import start as regedit_start
    regedit_start()

def clear_screen():
    command = 'cls' if platform.system().lower() == 'windows' else 'clear'
    os.system(command)

def show_menu():
    clear_screen()
    print('\033[1mWelcome to Pchol autoRE version')
    print('Select action:\n0. exit\n1. PcholShell\n2. System shell\n3. Ranger\n4. autoRE File Manager\n5. Bpytop\n6. exeTracker — трекер .exe\n7. Registry Editor — редактор реестра\033[0m')

def main(): 
        show_menu()
        while True:
            try:
                key = get_key()
            except KeyboardInterrupt:
                show_menu()
                continue
            except Exception:
                os.system('stty sane 2>/dev/null')
                show_menu()
                continue

            try:
                if key == '0':
                    print("\nExiting...")
                    clear_screen()
                    sys.exit()
                if key == '1':
                    runph()
                elif key == '2':
                    shell()
                elif key == '3':
                    ranger()
                elif key == '4':
                    autorefm()
                elif key == '5':
                    start_bpytop()
                elif key == '6':
                    start_exe_tracker()
                elif key == '7':
                    start_regedit()
            except Exception as e:
                os.system('stty sane 2>/dev/null')

            show_menu()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='autoRE — Multi-Tool Console System')
    parser.add_argument('--regedit', action='store_true', help='Launch Registry Editor directly')
    parser.add_argument('--tracker', metavar='EXE_PATH', help='Launch exeTracker with given file')
    parser.add_argument('--rangeredit', action='store_true', help='Launch autoRE File Manager directly')
    parser.add_argument('--shell', action='store_true', help='Launch System Shell directly')
    args, _ = parser.parse_known_args()

    if args.regedit:
        start_regedit()
    elif args.tracker:
        tracker = EXETracker(args.tracker)
        tracker.run()
    elif args.rangeredit:
        autorefm()
    elif args.shell:
        shell()
    else:
        main()
