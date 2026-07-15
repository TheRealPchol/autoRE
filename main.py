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
    subprocess.run([sys.executable, '-O', script])

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
    print('Select action:\n0. exit\n1. Enter pcholshell 26.7.1\n2. Enter system shell\n3. Enter to ranger(file manager)\n4. Enter to Pchol autoRE file manager\n5. Enter to bpytop\033[0m')

def main(): 
        show_menu()
        while True:
            try:
                key = get_key()
                if key == '0':
                    print("\nExiting...")
                    sys.exit()
                if key == '1':
                    runph()
                    show_menu()
                if key == '2':
                    shell()
                    show_menu()
                if key == '3':
                    ranger()
                    show_menu()
                if key == '4':
                    autorefm()
                    show_menu()
                if key == '5':
                    start_bpytop()
                    show_menu() # Возвращаем меню после выхода из bpytop
            except KeyboardInterrupt:
                pass

if __name__ == '__main__':
    main()
