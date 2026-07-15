#!/usr/bin/env python3
"""
exeTracker — трекер поведения .exe файлов
Запускает EXE через Wine под strace и анализирует его действия.
"""

import subprocess
import sys
import os
import re
import signal
import threading
import time
from datetime import datetime, timedelta
from collections import defaultdict

C = {
    'reset': '\033[0m',
    'red': '\033[91m',
    'green': '\033[92m',
    'yellow': '\033[93m',
    'blue': '\033[94m',
    'magenta': '\033[95m',
    'cyan': '\033[96m',
    'white': '\033[97m',
    'bold': '\033[1m',
    'dim': '\033[2m',
    'header': '\033[44;97m',
    'warn': '\033[43;30m',
    'good': '\033[42;30m',
    'bad': '\033[41;97m',
}

EVENT_COLORS = {
    'file_create': 'green',
    'file_delete': 'red',
    'file_write': 'yellow',
    'file_read': 'blue',
    'file_other': 'cyan',
    'registry_write': 'yellow',
    'registry_read': 'blue',
    'registry_delete': 'red',
    'process_create': 'green',
    'process_exit': 'red',
    'network_connect': 'magenta',
    'network_bind': 'magenta',
    'other': 'white',
}

class EXETracker:
    def __init__(self, exe_path, wine_prefix=None, timeout=None):
        self.exe_path = os.path.abspath(exe_path)
        self.timeout = timeout
        self.env = os.environ.copy()
        if wine_prefix:
            self.env['WINEPREFIX'] = os.path.abspath(wine_prefix)

        self.start_time = None
        self.events = []
        self.event_counts = defaultdict(int)
        self.event_types = defaultdict(int)
        self.created_files = set()
        self.deleted_files = set()
        self.modified_files = set()
        self.registry_ops = []
        self.process_tree = []
        self.network_connections = set()
        self.running = False
        self.process = None
        self.lock = threading.Lock()
        self.syscall_patterns = self._compile_patterns()

    def _compile_patterns(self):
        return {
            'file_create': re.compile(r'creat\("([^"]+)"'),
            'file_open': re.compile(r'open(at)?\("([^"]+)"'),
            'file_mkdir': re.compile(r'mkdir\("([^"]+)"'),
            'file_unlink': re.compile(r'unlink\("([^"]+)"'),
            'file_rmdir': re.compile(r'rmdir\("([^"]+)"'),
            'file_rename': re.compile(r'rename\("([^"]+)",\s*"([^"]+)"'),
            'file_link': re.compile(r'(symlink|link)\("([^"]+)",\s*"([^"]+)"'),
            'file_write': re.compile(r'(write|pwrite64?)\((\d+),'),
            'file_read': re.compile(r'(read|pread64?)\((\d+),'),
            'process_fork': re.compile(r'(fork|clone)\(\)\s*=\s*(\d+)'),
            'process_exec': re.compile(r'execve\("([^"]+)"'),
            'network_connect': re.compile(r'connect\((\d+),\s*\{sa_family=AF_INET,\s*sin_port=htons\((\d+)\),\s*sin_addr=inet_addr\("([\d.]+)"'),
            'network_bind': re.compile(r'bind\((\d+),\s*\{sa_family=AF_INET,\s*sin_port=htons\((\d+)\)'),
        }

    def classify_syscall(self, line):
        line_lower = line.lower()
        path = None
        etype = 'other'
        details = line.strip()

        if 'wine' in line_lower and 'reg' in line_lower:
            if 'regcreatekey' in line_lower:
                m = re.search(r'L"([^"]+)"', line)
                if m:
                    path = m.group(1).replace('\\\\', '\\')
                etype = 'registry_write'
            elif 'regopenkey' in line_lower:
                m = re.search(r'L"([^"]+)"', line)
                if m:
                    path = m.group(1).replace('\\\\', '\\')
                etype = 'registry_read'
            elif 'regdelete' in line_lower:
                m = re.search(r'L"([^"]+)"', line)
                if m:
                    path = m.group(1).replace('\\\\', '\\')
                etype = 'registry_delete'
            elif 'regsetvalue' in line_lower:
                m = re.search(r'L"([^"]+)"', line)
                if m:
                    path = m.group(1).replace('\\\\', '\\')
                etype = 'registry_write'

        for key, pat in self.syscall_patterns.items():
            m = pat.search(line)
            if m:
                if key == 'file_create':
                    path = m.group(1)
                    etype = 'file_create'
                elif key == 'file_open':
                    path = m.group(2)
                    flags = line[m.end():]
                    if 'O_WRONLY' in flags or 'O_RDWR' in flags or 'O_CREAT' in flags:
                        etype = 'file_write'
                    elif 'O_TRUNC' in flags:
                        etype = 'file_write'
                    else:
                        etype = 'file_read'
                elif key == 'file_mkdir':
                    path = m.group(1)
                    etype = 'file_create'
                elif key in ('file_unlink', 'file_rmdir'):
                    path = m.group(1)
                    etype = 'file_delete'
                elif key == 'file_rename':
                    etype = 'file_create'
                    path = f"{m.group(1)} -> {m.group(2)}"
                    self.modified_files.add(m.group(2))
                elif key in ('file_link', 'file_write'):
                    etype = 'file_create' if 'write' in key else 'file_other'
                elif key == 'file_read':
                    etype = 'file_read'
                elif key == 'process_fork':
                    etype = 'process_create'
                elif key == 'process_exec':
                    path = m.group(1)
                    etype = 'process_create'
                elif key in ('network_connect', 'network_bind'):
                    if key == 'network_connect':
                        path = f"{m.group(3)}:{m.group(2)}"
                    else:
                        path = f"port {m.group(2)}"
                    etype = key
                break

        if etype == 'file_create' and path:
            self.created_files.add(path)
        elif etype == 'file_delete' and path:
            self.deleted_files.add(path)

        if etype.startswith('registry') and path:
            self.registry_ops.append((etype, path))

        if etype.startswith('network_') and path:
            self.network_connections.add(path)

        return etype, path or '', details[:120]

    def _read_strace(self, pipe):
        try:
            for line in iter(pipe.readline, ''):
                if not self.running:
                    break
                line = line.rstrip('\n')
                if not line:
                    continue
                with self.lock:
                    etype, path, details = self.classify_syscall(line)
                    event = {
                        'time': datetime.now(),
                        'type': etype,
                        'path': path,
                        'details': details,
                        'raw': line,
                    }
                    self.events.append(event)
                    self.event_counts[etype] += 1
                    self.event_types[etype.split('_')[0]] += 1
                    self._display_event(event)
        except (IOError, ValueError):
            pass

    def _display_event(self, event):
        color_key = event['type'] if event['type'] in EVENT_COLORS else 'other'
        color = EVENT_COLORS[color_key]
        ts = event['time'].strftime('%H:%M:%S.%f')[:12]
        icon = {
            'file_create': '+', 'file_delete': '-', 'file_write': '~',
            'file_read': '[R]', 'registry_write': '[RW]', 'registry_read': '[RR]',
            'registry_delete': '[RD]', 'process_create': '[P+]', 'process_exit': '[P-]',
            'network_connect': '[NET]', 'network_bind': '[BND]', 'other': '[?]',
        }.get(event['type'], '[?]')

        label = event['type'].ljust(18)
        print(f" {C[color]}{icon}{C['reset']} {C['dim']}{ts}{C['reset']} {C[color]}{label}{C['reset']} {event['path'] or event['details'][:80]}")

    def _summary(self):
        print(f"\n{C['header']}{'='*60}{C['reset']}")
        print(f"{C['bold']}  📊 ОТЧЁТ ПО ПОВЕДЕНИЮ{C['reset']}")
        print(f"{C['header']}{'='*60}{C['reset']}\n")

        elapsed = datetime.now() - self.start_time if self.start_time else timedelta(0)
        print(f"  Файл:        {C['cyan']}{self.exe_path}{C['reset']}")
        print(f"  Время работы: {elapsed.total_seconds():.1f} сек")
        print(f"  Всего событий:{C['bold']} {len(self.events)}{C['reset']}\n")

        categories = [
            ('📁 Файловые операции', {
                'file_create': 'Создано файлов',
                'file_delete': 'Удалено файлов',
                'file_write': 'Запись в файлы',
                'file_read': 'Чтение файлов',
            }),
            ('📝 Реестр', {
                'registry_write': 'Запись в реестр',
                'registry_read': 'Чтение реестра',
                'registry_delete': 'Удаление из реестра',
            }),
            ('⚙ Процессы', {
                'process_create': 'Создано процессов',
                'process_exit': 'Завершено процессов',
            }),
            ('🌐 Сеть', {
                'network_connect': 'Соединений',
                'network_bind': 'Открыто портов',
            }),
        ]

        for title, items in categories:
            total = sum(self.event_counts.get(k, 0) for k in items)
            if total == 0:
                continue
            print(f"  {C['bold']}{title}{C['reset']}")
            for key, label in items.items:
                count = self.event_counts.get(key, 0)
                if count:
                    bar = '█' * min(count, 40)
                    print(f"    {label:20} {C['green']}{count:>5}{C['reset']}  {bar}")
            print()

        if self.created_files:
            print(f"  {C['bold']}📄 Созданные файлы:{C['reset']}")
            for f in list(self.created_files)[:15]:
                for p in ['/home/', '/tmp/', '/root/', '/mnt/', '/media/']:
                    if p in f:
                        f_short = f[f.index(p):]
                        break
                else:
                    f_short = f[-60:]
                print(f"    {C['green']}+{C['reset']} {f_short}")
            if len(self.created_files) > 15:
                print(f"    ... и ещё {len(self.created_files) - 15}")
            print()

        if self.deleted_files:
            print(f"  {C['bold']}🗑 Удалённые файлы:{C['reset']}")
            for f in list(self.deleted_files)[:10]:
                print(f"    {C['red']}-{C['reset']} {f[-60:]}")
            if len(self.deleted_files) > 10:
                print(f"    ... и ещё {len(self.deleted_files) - 10}")
            print()

        if self.registry_ops:
            print(f"  {C['bold']}📝 Операции с реестром:{C['reset']}")
            for op_type, path in self.registry_ops[:10]:
                c = 'green' if 'write' in op_type else ('red' if 'delete' in op_type else 'blue')
                print(f"    {C[c]}{op_type.split('_')[1].upper():6}{C['reset']} {path}")
            if len(self.registry_ops) > 10:
                print(f"    ... и ещё {len(self.registry_ops) - 10}")
            print()

        if self.network_connections:
            print(f"  {C['bold']}🌐 Сетевые соединения:{C['reset']}")
            for conn in self.network_connections:
                print(f"    {C['magenta']}🔗{C['reset']} {conn}")
            print()

        risk_score = 0
        risk_items = []
        if self.event_counts.get('registry_write', 0) > 5:
            risk_score += 25
            risk_items.append("множественные записи в реестр")
        if self.deleted_files:
            risk_score += 20
            risk_items.append("удаление файлов")
        if self.network_connections:
            risk_score += 20
            risk_items.append("сетевые соединения")
        if self.event_counts.get('process_create', 0) > 3:
            risk_score += 15
            risk_items.append("создание дочерних процессов")
        if self.event_counts.get('file_create', 0) > 20:
            risk_score += 10
            risk_items.append("большое количество созданных файлов")
        risk_score = min(risk_score, 100)

        bar_color = 'green' if risk_score < 30 else ('yellow' if risk_score < 60 else 'red')
        bar_len = risk_score // 2
        print(f"  {C['bold']}⚠️  УРОВЕНЬ РИСКА: {C[bar_color]}{risk_score}%{C['reset']}")
        print(f"  {C[bar_color]}{'█' * bar_len}{'░' * (50 - bar_len)}{C['reset']}")
        if risk_items:
            print(f"  Факторы: {', '.join(risk_items)}")
        print()

    def run(self):
        if not os.path.exists(self.exe_path):
            print(f"{C['bad']} Файл не найден: {self.exe_path}{C['reset']}")
            return

        print(f"{C['header']}{'='*60}{C['reset']}")
        print(f"{C['bold']}  🕵️ exeTracker — анализ поведения{C['reset']}")
        print(f"{C['header']}{'='*60}{C['reset']}\n")
        print(f"  Файл:    {C['cyan']}{self.exe_path}{C['reset']}")
        print(f"  Размер:  {os.path.getsize(self.exe_path)} байт")
        print(f"  Префикс: {self.env.get('WINEPREFIX', 'WINE (default)')}")
        print(f"\n  {C['dim']}Нажми Ctrl+C для завершения и показа отчёта{C['reset']}\n")

        cmd = [
            'strace', '-f', '-q',
            '-e', 'trace=file,process,network,desc,signal',
            '-s', '256',
            '-o', '/dev/stderr',
            'wine', self.exe_path,
        ]

        self.running = True
        self.start_time = datetime.now()

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self.env,
                bufsize=1,
                universal_newlines=True,
            )

            reader = threading.Thread(
                target=self._read_strace,
                args=(self.process.stderr,),
                daemon=True,
            )
            reader.start()

            if self.timeout:
                self.process.wait(timeout=self.timeout)
            else:
                self.process.wait()

        except subprocess.TimeoutExpired:
            print(f"\n{C['yellow']}⏰ Тайм-аут ({self.timeout}с){C['reset']}")
            self.process.kill()
        except KeyboardInterrupt:
            print(f"\n{C['yellow']}⏹ Остановлено пользователем{C['reset']}")
            self.process.kill() if self.process else None
        except FileNotFoundError:
            print(f"{C['bad']} strace или wine не найдены. Установите: sudo apt install strace wine{C['reset']}")
            return
        finally:
            self.running = False
            time.sleep(0.2)

        self._summary()

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='exeTracker — трекер поведения .exe файлов\n'
        'Запускает EXE через Wine под strace и показывает все его действия',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('exe', help='Путь к .exe файлу')
    parser.add_argument('-p', '--prefix', help='WINEPREFIX (путь к папке wine)')
    parser.add_argument('-t', '--timeout', type=int, help='Максимальное время работы (сек)')
    parser.add_argument('-w', '--wait', action='store_true', help='Ожидать завершения EXE')

    args = parser.parse_args()

    tracker = EXETracker(args.exe, args.prefix, args.timeout)
    tracker.run()

if __name__ == '__main__':
    main()
