from src.autoReFM import start as autorefm
from src.shell import shell
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
    # Формируем правильный путь к файлу bpytop.py
    script = os.path.join(os.path.dirname(__file__), 'src', 'bpytop', 'bpytop.py')
    # Запускаем в отдельном изолированном процессе со своим потоком stdin
    subprocess.run([sys.executable, script])

def clear_screen():
    command = 'cls' if platform.system().lower() == 'windows' else 'clear'
    os.system(command)

def show_menu():
    clear_screen()
    print('\033[1mWelcome to Pchol autoRE version')
    # Добавлено визуальное отображение пункта 5 в меню
    print('Select action:\n0. exit\n1. Enter pcholhelper (pcholshell) 26.7.2\n2. Enter system shell\n3. Enter to ranger(file manager)\n4. Enter to Pchol autoRE file manager\n5. Enter to bpytop\033[0m')

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
            except Exception:
                os.system('stty sane 2>/dev/null')

            show_menu()

if __name__ == '__main__':
    main()
