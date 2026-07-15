#!/usr/bin/env python3
"""
RegEdit — полноценный консольный редактор реестра Windows
Работает в WinRE, не требует внешних зависимостей (только winreg + ctypes)

Возможности:
  - Навигация по кустам реестра (HKLM, HKCU, HKCR, HKU, HKCC)
  - Создание/удаление/переименование ключей
  - Создание/изменение/удаление значений (REG_SZ, REG_DWORD, REG_BINARY,
    REG_MULTI_SZ, REG_EXPAND_SZ, REG_QWORD, REG_NONE)
  - Загрузка/выгрузка кустов (RegLoadKey/RegUnLoadKey)
  - Импорт/экспорт .reg файлов
  - Поиск по именам ключей и значений
  - Копирование пути ключа
"""

import os
import sys
import re
import struct
from datetime import datetime
from collections import deque

HIVES = {
    1: ('HKEY_LOCAL_MACHINE', 'HKLM'),
    2: ('HKEY_CURRENT_USER', 'HKCU'),
    3: ('HKEY_CLASSES_ROOT', 'HKCR'),
    4: ('HKEY_USERS', 'HKU'),
    5: ('HKEY_CURRENT_CONFIG', 'HKCC'),
}

HIVE_MAP = {
    'HKEY_LOCAL_MACHINE':   0x80000002,
    'HKLM':                 0x80000002,
    'HKEY_CURRENT_USER':    0x80000001,
    'HKCU':                 0x80000001,
    'HKEY_CLASSES_ROOT':    0x80000000,
    'HKCR':                 0x80000000,
    'HKEY_USERS':           0x80000003,
    'HKU':                  0x80000003,
    'HKEY_CURRENT_CONFIG':  0x80000005,
    'HKCC':                 0x80000005,
}

REGTYPE_NAMES = {
    0: 'REG_NONE',
    1: 'REG_SZ',
    2: 'REG_EXPAND_SZ',
    3: 'REG_BINARY',
    4: 'REG_DWORD',
    5: 'REG_DWORD_BIG_ENDIAN',
    6: 'REG_LINK',
    7: 'REG_MULTI_SZ',
    8: 'REG_RESOURCE_LIST',
    9: 'REG_FULL_RESOURCE_DESCRIPTOR',
    10: 'REG_RESOURCE_REQUIREMENTS_LIST',
    11: 'REG_QWORD',
}

REGTYPE_SIMPLE = {v: k for k, v in REGTYPE_NAMES.items()}

C = {
    'reset': '\033[0m',
    'bold': '\033[1m',
    'dim': '\033[2m',
    'red': '\033[91m',
    'green': '\033[92m',
    'yellow': '\033[93m',
    'blue': '\033[94m',
    'magenta': '\033[95m',
    'cyan': '\033[96m',
    'white': '\033[97m',
    'header': '\033[44;97m',
    'sel': '\033[7m',
    'warn': '\033[43;30m',
    'bad': '\033[41;97m',
    'good': '\033[42;30m',
}

IS_WINDOWS = sys.platform == 'win32'

if IS_WINDOWS:
    import winreg
    import msvcrt
    from ctypes import windll, byref, create_unicode_buffer, addressof, c_wchar_p, c_void_p
    from ctypes import wintypes
    from ctypes.wintypes import LPCWSTR, LPWSTR, HANDLE, DWORD, LPVOID, BOOL, LPDWORD

    advapi32 = windll.advapi32

    KEY_READ = 0x20019
    KEY_WRITE = 0x20006
    KEY_ALL_ACCESS = 0xF003F

    REG_OPTION_BACKUP_RESTORE = 4
    REG_OPTION_NON_VOLATILE = 0
    REG_OPTION_VOLATILE = 1
    REG_OPTION_CREATE_LINK = 2

    advapi32.RegLoadKeyW.argtypes = [HANDLE, LPCWSTR, LPCWSTR]
    advapi32.RegLoadKeyW.restype = LONG

    advapi32.RegUnLoadKeyW.argtypes = [HANDLE, LPCWSTR]
    advapi32.RegUnLoadKeyW.restype = LONG

    advapi32.RegSaveKeyW.argtypes = [HANDLE, LPCWSTR, LPVOID]
    advapi32.RegSaveKeyW.restype = LONG

    advapi32.RegRestoreKeyW.argtypes = [HANDLE, LPCWSTR, DWORD]
    advapi32.RegRestoreKeyW.restype = LONG

    advapi32.RegReplaceKeyW.argtypes = [HANDLE, LPCWSTR, LPCWSTR, LPCWSTR, LPVOID]
    advapi32.RegReplaceKeyW.restype = LONG
else:
    winreg = None


def _winreg(func):
    def wrapper(*args, **kwargs):
        if not IS_WINDOWS:
            print(f"{C['bad']} Редактор реестра работает только на Windows{C['reset']}")
            return None
        try:
            return func(*args, **kwargs)
        except PermissionError:
            print(f"{C['bad']} Ошибка доступа. Запустите от имени администратора.{C['reset']}")
            return None
        except Exception as e:
            print(f"{C['red']} Ошибка: {e}{C['reset']}")
            return None
    return wrapper


class RegistryEditor:
    def __init__(self):
        self.current_hive = None
        self.current_key = None
        self.current_path = ''
        self.history = deque(maxlen=50)
        self.history_index = -1
        self.search_results = []
        self.search_index = 0
        self.running = True

    def _get_hkey(self, hive_name):
        if not IS_WINDOWS:
            return None
        handle = HIVE_MAP.get(hive_name)
        if handle == 0x80000000:
            return winreg.HKEY_CLASSES_ROOT
        elif handle == 0x80000001:
            return winreg.HKEY_CURRENT_USER
        elif handle == 0x80000002:
            return winreg.HKEY_LOCAL_MACHINE
        elif handle == 0x80000003:
            return winreg.HKEY_USERS
        elif handle == 0x80000005:
            return winreg.HKEY_CURRENT_CONFIG
        return None

    def _get_hive_handle(self, hive_name):
        if not IS_WINDOWS:
            return None
        handle_map = {
            'HKEY_LOCAL_MACHINE': 0x80000002,
            'HKLM': 0x80000002,
            'HKEY_CURRENT_USER': 0x80000001,
            'HKCU': 0x80000001,
            'HKEY_CLASSES_ROOT': 0x80000000,
            'HKCR': 0x80000000,
            'HKEY_USERS': 0x80000003,
            'HKU': 0x80000003,
            'HKEY_CURRENT_CONFIG': 0x80000005,
            'HKCC': 0x80000005,
        }
        h = handle_map.get(hive_name)
        if h is None:
            return None
        return ctypes.c_void_p(h)

    def _get_user_key_count(self, key):
        if not IS_WINDOWS:
            return 0, 0
        try:
            info = winreg.QueryInfoKey(key)
            return info[0], info[1]
        except:
            return 0, 0

    @_winreg
    def open_key(self, hive_name, subkey=''):
        hkey = self._get_hkey(hive_name)
        if hkey is None:
            return False
        try:
            if subkey:
                key = winreg.OpenKey(hkey, subkey, 0, winreg.KEY_READ | winreg.KEY_WRITE)
            else:
                key = winreg.OpenKey(hkey, '', 0, winreg.KEY_READ | winreg.KEY_WRITE)
            self._close_current_key()
            self.current_hive = hive_name
            self.current_key = key
            self.current_path = subkey if subkey else ''
            self.history.append(f"{hive_name}\\{self.current_path}")
            return True
        except PermissionError:
            try:
                if subkey:
                    key = winreg.OpenKey(hkey, subkey, 0, winreg.KEY_READ)
                else:
                    key = winreg.OpenKey(hkey, '', 0, winreg.KEY_READ)
                self._close_current_key()
                self.current_hive = hive_name
                self.current_key = key
                self.current_path = subkey if subkey else ''
                self.history.append(f"{hive_name}\\{self.current_path}")
                return True
            except Exception as e:
                return False
        except Exception as e:
            return False

    def _close_current_key(self):
        if self.current_key is not None and IS_WINDOWS:
            try:
                winreg.CloseKey(self.current_key)
            except:
                pass
        self.current_key = None

    def _get_full_path(self):
        if not self.current_hive:
            return ''
        if self.current_path:
            return f"{self.current_hive}\\{self.current_path}"
        return self.current_hive

    def _format_value_data(self, type_id, data):
        if data is None:
            return ''
        if type_id == winreg.REG_SZ or type_id == winreg.REG_EXPAND_SZ:
            return str(data)
        elif type_id == winreg.REG_DWORD:
            return f"0x{data:08X} ({data})"
        elif type_id == winreg.REG_QWORD:
            return f"0x{data:016X} ({data})"
        elif type_id == winreg.REG_BINARY:
            if isinstance(data, bytes):
                hex_str = data.hex().upper()
                if len(hex_str) > 48:
                    return f"{hex_str[:48]}..."
                return hex_str
            return str(data)
        elif type_id == winreg.REG_MULTI_SZ:
            parts = list(data) if isinstance(data, (list, tuple)) else []
            return ' | '.join(parts) if parts else '(empty)'
        elif type_id == winreg.REG_NONE:
            return '(empty)' if data == b'' else data.hex().upper()[:48]
        return str(data)[:60]

    def enumerate_key(self):
        if not IS_WINDOWS or self.current_key is None:
            return [], []
        key = self.current_key
        subkeys = []
        values = []
        try:
            n_subkeys, n_values = winreg.QueryInfoKey(key)
            for i in range(n_subkeys):
                try:
                    name = winreg.EnumKey(key, i)
                    sk = winreg.OpenKey(key, name)
                    sk_count, sv_count = winreg.QueryInfoKey(sk)
                    winreg.CloseKey(sk)
                    subkeys.append((name, sk_count, sv_count))
                except:
                    subkeys.append((f'<error:{i}>', 0, 0))
            for i in range(n_values):
                try:
                    name, data, type_id = winreg.EnumValue(key, i)
                    display = self._format_value_data(type_id, data)
                    values.append((name, REGTYPE_NAMES.get(type_id, f'REG_UNKNOWN({type_id})'), display, type_id, data))
                except:
                    values.append((f'<error:{i}>', 'REG_UNKNOWN', '', 0, b''))
        except:
            pass
        return subkeys, values

    @_winreg
    def create_key(self, name):
        if self.current_key is None:
            return False
        try:
            winreg.CreateKey(self.current_key, name)
            return True
        except:
            return False

    @_winreg
    def delete_key(self, name):
        if self.current_key is None:
            return False
        try:
            winreg.DeleteKey(self.current_key, name)
            return True
        except:
            self._delete_key_recursive(self.current_key, name)
            return True

    def _delete_key_recursive(self, parent, name):
        if not IS_WINDOWS:
            return
        try:
            sub = winreg.OpenKey(parent, name, 0, winreg.KEY_READ | winreg.KEY_WRITE)
            sub_subkeys = []
            try:
                n_sub, _ = winreg.QueryInfoKey(sub)
                for i in range(n_sub - 1, -1, -1):
                    sub_name = winreg.EnumKey(sub, i)
                    self._delete_key_recursive(sub, sub_name)
            except:
                pass
            winreg.CloseKey(sub)
            winreg.DeleteKey(parent, name)
        except:
            pass

    @_winreg
    def rename_key(self, old_name, new_name):
        if self.current_key is None:
            return False
        try:
            if not IS_WINDOWS:
                return False
            sub = winreg.OpenKey(self.current_key, old_name, 0, winreg.KEY_READ)
            values = []
            try:
                n_vals = winreg.QueryInfoKey(sub)[1]
                for i in range(n_vals):
                    values.append(winreg.EnumValue(sub, i))
            except:
                pass
            sub_key_names = []
            try:
                n_subs = winreg.QueryInfoKey(sub)[0]
                for i in range(n_subs):
                    sub_key_names.append(winreg.EnumKey(sub, i))
            except:
                pass
            winreg.CloseKey(sub)

            new_sub = winreg.CreateKey(self.current_key, new_name)
            for vname, vdata, vtype in values:
                winreg.SetValueEx(new_sub, vname, 0, vtype, vdata)
            winreg.CloseKey(new_sub)

            for sk in sub_key_names:
                self._rename_move_subkey(self.current_key, old_name, new_name, sk)

            self._delete_key_recursive(self.current_key, old_name)
            return True
        except:
            return False

    def _rename_move_subkey(self, parent, old_parent, new_parent, name):
        if not IS_WINDOWS:
            return
        try:
            old_path = f"{old_parent}\\{name}"
            new_path = f"{new_parent}\\{name}"
            old_sub = winreg.OpenKey(parent, old_path, 0, winreg.KEY_READ)
            values = []
            try:
                n_vals = winreg.QueryInfoKey(old_sub)[1]
                for i in range(n_vals):
                    values.append(winreg.EnumValue(old_sub, i))
            except:
                pass
            sub_names = []
            try:
                n_subs = winreg.QueryInfoKey(old_sub)[0]
                for i in range(n_subs):
                    sub_names.append(winreg.EnumKey(old_sub, i))
            except:
                pass
            winreg.CloseKey(old_sub)

            new_full = f"{new_parent}\\{name}"
            new_sub = winreg.CreateKey(parent, new_full)
            for vname, vdata, vtype in values:
                winreg.SetValueEx(new_sub, vname, 0, vtype, vdata)
            winreg.CloseKey(new_sub)

            for sk in sub_names:
                self._rename_move_subkey(parent, old_path, new_path, sk)

            self._delete_key_recursive(parent, old_path)
        except:
            pass

    @_winreg
    def set_value(self, name, value, type_id=1):
        if self.current_key is None:
            return False
        try:
            winreg.SetValueEx(self.current_key, name, 0, type_id, value)
            return True
        except:
            return False

    @_winreg
    def delete_value(self, name):
        if self.current_key is None:
            return False
        try:
            winreg.DeleteValue(self.current_key, name)
            return True
        except:
            return False

    @_winreg
    def load_hive(self, key_path, file_path):
        if not IS_WINDOWS:
            return False
        hive_handle = self._get_hive_handle(self.current_hive)
        if hive_handle is None:
            return False
        result = advapi32.RegLoadKeyW(hive_handle, key_path, file_path)
        if result != 0:
            error_msg = {
                2: "Файл не найден",
                5: "Отказано в доступе (нужен админ)",
                13: "Некорректные данные (не файл куста?)",
                87: "Некорректный параметр",
            }.get(result, f"Ошибка 0x{result:08X}")
            print(f"{C['bad']} {error_msg}{C['reset']}")
            return False
        return True

    @_winreg
    def unload_hive(self, key_name):
        if not IS_WINDOWS:
            return False
        if self.current_path and self.current_path.lower().startswith(key_name.lower()):
            print(f"{C['warn']} Нельзя выгрузить куст, находясь внутри него{C['reset']}")
            return False
        hive_handle = self._get_hive_handle(self.current_hive)
        if hive_handle is None:
            return False
        result = advapi32.RegUnLoadKeyW(hive_handle, key_name)
        if result != 0:
            error_msg = {
                5: "Отказано в доступе",
                161: "Куст занят (есть открытые ключи)",
            }.get(result, f"Ошибка 0x{result:08X}")
            print(f"{C['bad']} {error_msg}{C['reset']}")
            return False
        return True

    @_winreg
    def export_reg(self, file_path, hive=None, key_path=None):
        if not IS_WINDOWS:
            return False
        if hive is None:
            hive = self.current_hive
        if key_path is None:
            key_path = self.current_path
        try:
            hkey = self._get_hkey(hive)
            if hkey is None:
                return False
            if key_path:
                key = winreg.OpenKey(hkey, key_path, 0, winreg.KEY_READ)
            else:
                key = winreg.OpenKey(hkey, '', 0, winreg.KEY_READ)
            lines = []
            lines.append('Windows Registry Editor Version 5.00')
            lines.append('')
            self._export_recursive(key, f"[{hive}\\{key_path}]" if key_path else f"[{hive}]", lines)
            winreg.CloseKey(key)
            with open(file_path, 'w', encoding='utf-16-le') as f:
                f.write('\xef\xbb\xbf')
                f.write('\r\n'.join(lines))
            return True
        except:
            return False

    def _export_recursive(self, key, current_path, lines):
        if not IS_WINDOWS:
            return
        subkeys = []
        values = []
        try:
            n_sub, n_val = winreg.QueryInfoKey(key)
            for i in range(n_val):
                try:
                    values.append(winreg.EnumValue(key, i))
                except:
                    pass
            for i in range(n_sub):
                try:
                    subkeys.append(winreg.EnumKey(key, i))
                except:
                    pass
        except:
            pass

        lines.append('')
        lines.append(current_path)
        for vname, vdata, vtype in values:
            lines.append(self._format_reg_value(vname, vdata, vtype))

        for sk in subkeys:
            try:
                sk_key = winreg.OpenKey(key, sk, 0, winreg.KEY_READ)
                self._export_recursive(sk_key, f"{current_path}\\{sk}", lines)
                winreg.CloseKey(sk_key)
            except:
                pass

    def _format_reg_value(self, name, data, type_id):
        if type_id == winreg.REG_SZ:
            escaped = str(data).replace('\\', '\\\\').replace('"', '\\"')
            return f'"{name}"="{escaped}"' if name else f'@="{escaped}"'
        elif type_id == winreg.REG_DWORD:
            return f'"{name}"=dword:{data:08X}' if name else f'@=dword:{data:08X}'
        elif type_id == winreg.REG_QWORD:
            if isinstance(data, int):
                return f'"{name}"=hex(b):{struct.pack("<Q", data).hex().upper()}' if name else f'@=hex(b):{struct.pack("<Q", data).hex().upper()}'
            return f'"{name}"=hex(b):{data}' if name else f'@=hex(b):{data}'
        elif type_id == winreg.REG_BINARY or type_id == winreg.REG_NONE:
            if isinstance(data, bytes):
                hex_str = ','.join(f'{b:02X}' for b in data)
                return f'"{name}"=hex:{hex_str}' if name else f'@=hex:{hex_str}'
        elif type_id == winreg.REG_MULTI_SZ:
            parts = list(data) if isinstance(data, (list, tuple)) else []
            hex_data = b'\x00'.join(p.encode('utf-16-le') for p in parts) + b'\x00\x00'
            hex_str = ','.join(f'{b:02X}' for b in hex_data)
            return f'"{name}"=hex(7):{hex_str}' if name else f'@=hex(7):{hex_str}'
        elif type_id == winreg.REG_EXPAND_SZ:
            escaped = str(data).replace('\\', '\\\\').replace('"', '\\"')
            return f'"{name}"=hex(2):{escaped.encode("utf-16-le").hex(",").upper()}' if name else f'@=hex(2):{escaped.encode("utf-16-le").hex(",").upper()}'
        return f'"{name}"="<unsupported type>"' if name else '@="<unsupported type>"'

    @_winreg
    def import_reg(self, file_path):
        if not IS_WINDOWS:
            return False
        if not os.path.exists(file_path):
            print(f"{C['bad']} Файл не найден: {file_path}{C['reset']}")
            return False
        try:
            with open(file_path, 'rb') as f:
                raw = f.read()
            if raw[:3] == b'\xef\xbb\xbf':
                content = raw[3:].decode('utf-16-le', errors='replace')
            else:
                try:
                    content = raw.decode('utf-16-le', errors='replace')
                except:
                    content = raw.decode('utf-8', errors='replace')
            content = content.replace('\r\n', '\n').replace('\r', '\n')
            lines = content.split('\n')

            if not lines or 'REGEDIT4' not in lines[0].upper():
                if 'Windows Registry Editor' not in lines[0].upper():
                    print(f"{C['bad']} Невалидный .reg файл (нет заголовка){C['reset']}")
                    return False

            current_path = None
            imports = 0
            errors = 0

            for line in lines[1:]:
                line = line.strip()
                if not line or line.startswith(';'):
                    continue
                if line.startswith('[') and line.endswith(']'):
                    current_path = line[1:-1]
                    parts = current_path.split('\\', 1)
                    hive_short = parts[0]
                    subpath = parts[1] if len(parts) > 1 else ''
                    hkey = self._get_hkey(hive_short)
                    if hkey is None:
                        errors += 1
                        current_path = None
                        continue
                    try:
                        if subpath:
                            winreg.CreateKey(hkey, subpath)
                        self.open_key(hive_short, subpath)
                        imports += 1
                    except:
                        errors += 1
                        current_path = None
                        continue
                elif current_path is not None and self.current_key is not None:
                    try:
                        self._parse_and_set_value(line)
                        imports += 1
                    except:
                        errors += 1

            print(f"{C['green']} Импортировано: {imports} операций, ошибок: {errors}{C['reset']}")
            return errors == 0
        except Exception as e:
            print(f"{C['bad']} Ошибка импорта: {e}{C['reset']}")
            return False

    def _parse_and_set_value(self, line):
        if not IS_WINDOWS:
            return
        m = re.match(r'"([^"]*)"\s*=\s*"((?:[^"\\]|\\.)*)"', line)
        if m:
            name = m.group(1)
            data = m.group(2).replace('\\\\', '\\').replace('\\"', '"').replace('\\n', '\n').replace('\\r', '\r')
            winreg.SetValueEx(self.current_key, name, 0, winreg.REG_SZ, data)
            return

        m = re.match(r'"([^"]*)"\s*=\s*dword:([0-9a-fA-F]{8})', line)
        if m:
            name = m.group(1)
            data = int(m.group(2), 16)
            winreg.SetValueEx(self.current_key, name, 0, winreg.REG_DWORD, data)
            return

        m = re.match(r'"([^"]*)"\s*=\s*qword:([0-9a-fA-F]{16})', line)
        if m:
            name = m.group(1)
            data = int(m.group(2), 16)
            winreg.SetValueEx(self.current_key, name, 0, winreg.REG_QWORD, data)
            return

        m = re.match(r'"([^"]*)"\s*=\s*hex(?:\((\d+)\))?:(.*)', line)
        if m:
            name = m.group(1)
            hex_type = m.group(2)
            hex_str = m.group(3).replace(',', '').replace(' ', '')
            try:
                data = bytes.fromhex(hex_str)
            except:
                return
            if hex_type is None or hex_type == '':
                winreg.SetValueEx(self.current_key, name, 0, winreg.REG_BINARY, data)
            elif hex_type == '0':
                winreg.SetValueEx(self.current_key, name, 0, winreg.REG_NONE, data)
            elif hex_type == '2':
                try:
                    text = data.decode('utf-16-le').rstrip('\x00')
                except:
                    text = str(data)
                winreg.SetValueEx(self.current_key, name, 0, winreg.REG_EXPAND_SZ, text)
            elif hex_type == '7':
                try:
                    parts = data.split(b'\x00\x00')[0].split(b'\x00')
                    text_parts = [p.decode('utf-16-le', errors='replace') for p in parts if p]
                except:
                    text_parts = [str(data)]
                winreg.SetValueEx(self.current_key, name, 0, winreg.REG_MULTI_SZ, text_parts)
            elif hex_type == 'b':
                try:
                    val = struct.unpack('<Q', data[:8])[0]
                except:
                    val = int.from_bytes(data[:8], 'little')
                winreg.SetValueEx(self.current_key, name, 0, winreg.REG_QWORD, val)
            return

    @_winreg
    def search(self, query, hive=None, key_path=None, max_results=200):
        if not IS_WINDOWS:
            return []
        if hive is None:
            hive = self.current_hive
        if key_path is None:
            key_path = self.current_path
        results = []
        try:
            hkey = self._get_hkey(hive)
            if hkey is None:
                return []
            key = winreg.OpenKey(hkey, key_path, 0, winreg.KEY_READ)
            self._search_recursive(key, hive, key_path, query.lower(), results, max_results)
            winreg.CloseKey(key)
        except:
            pass
        return results

    def _search_recursive(self, key, hive, path, query, results, max_results):
        if not IS_WINDOWS:
            return
        if len(results) >= max_results:
            return
        try:
            n_sub, n_val = winreg.QueryInfoKey(key)

            if query in path.lower():
                results.append(('key', f"{hive}\\{path}"))

            for i in range(n_val):
                if len(results) >= max_results:
                    break
                try:
                    name, data, type_id = winreg.EnumValue(key, i)
                    if query in name.lower():
                        results.append(('value_name', f"{hive}\\{path}", name, REGTYPE_NAMES.get(type_id, f'REG_{type_id}')))
                    str_data = str(data).lower()
                    if isinstance(data, bytes):
                        try:
                            str_data += data.decode('utf-16-le', errors='ignore').lower()
                        except:
                            pass
                    if query in str_data:
                        results.append(('value_data', f"{hive}\\{path}", name))
                except:
                    pass

            for i in range(n_sub):
                if len(results) >= max_results:
                    break
                try:
                    name = winreg.EnumKey(key, i)
                    sub_path = f"{path}\\{name}" if path else name
                    try:
                        sub_key = winreg.OpenKey(key, name, 0, winreg.KEY_READ)
                        self._search_recursive(sub_key, hive, sub_path, query, results, max_results)
                        winreg.CloseKey(sub_key)
                    except:
                        pass
                except:
                    pass
        except:
            pass

    @_winreg
    def get_value_preview(self):
        if self.current_key is None:
            return ''
        result = []
        try:
            n_sub, n_val = winreg.QueryInfoKey(self.current_key)
            result.append(f"Subkeys: {n_sub}, Values: {n_val}")
            for i in range(min(n_val, 5)):
                try:
                    name, data, type_id = winreg.EnumValue(self.current_key, i)
                    display = self._format_value_data(type_id, data)
                    result.append(f"  {name} = {display[:60]}")
                except:
                    pass
        except:
            pass
        return '\n'.join(result)

    def close(self):
        self._close_current_key()

    def __del__(self):
        self.close()


def format_size(n):
    for unit in ['', 'K', 'M', 'G']:
        if n < 1024:
            return f"{n:.{1 if unit else 0}f}{unit}B"
        n /= 1024
    return f"{n:.1f}TB"


class RegEditUI:
    def __init__(self, editor):
        self.editor = editor
        self.selected_index = 0
        self.page_offset = 0
        self.mode = 'browse'
        self.status_text = ''
        self.status_color = 'green'
        self.page_size = 20

    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def print_header(self):
        print(f"{C['header']}{'='*70}{C['reset']}")
        print(f"{C['header']}  Registry Editor v1.0 | autoRE{C['reset']}")
        print(f"{C['header']}{'='*70}{C['reset']}")

    def print_path(self):
        path = self.editor._get_full_path()
        max_w = 66
        if len(path) > max_w:
            path = '...' + path[-(max_w-3):]
        print(f"  {C['bold']}Path:{C['reset']} {C['cyan']}{path}{C['reset']}")

    def print_key_list(self, subkeys, values, selected):
        self.clear_screen()
        self.print_header()
        self.print_path()
        print()

        n_sub, n_val = 0, 0
        if self.editor.current_key is not None and IS_WINDOWS:
            try:
                n_sub, n_val = winreg.QueryInfoKey(self.editor.current_key)
            except:
                pass

        if not subkeys and not values:
            print(f"  {C['dim']}(пустой ключ){C['reset']}\n")
        else:
            all_items = []
            for i, (name, skc, svc) in enumerate(subkeys):
                label = f"{name}\\  [{skc}K, {svc}V]"
                all_items.append(('key', label, name))
            for i, (name, rtype, data, tid, _) in enumerate(values):
                display = data[:50] if len(data) > 50 else data
                label = f"{name}  {C['dim']}{rtype}{C['reset']}  {display}"
                all_items.append(('value', label, name, rtype, tid, data))

            max_items = self.page_size
            if selected >= self.page_offset + max_items:
                self.page_offset = selected - max_items + 5
            if selected < self.page_offset:
                self.page_offset = selected

            visible = all_items[self.page_offset:self.page_offset + max_items]
            for i, item in enumerate(visible):
                idx = self.page_offset + i
                prefix = '>' if idx == selected else ' '
                if item[0] == 'key':
                    kname = item[2]
                    skc, svc = subkeys[[s[0] for s in subkeys].index(kname)][1:3] if kname in [s[0] for s in subkeys] else (0, 0)
                    if idx == selected:
                        print(f"  {C['sel']}> [{kname}]  [{skc}K, {svc}V]{C['reset']}")
                    else:
                        print(f"   [{kname}]  {C['dim']}[{skc}K, {svc}V]{C['reset']}")
                else:
                    vname = item[2]
                    rtype = item[3]
                    vdata = str(item[5])[:55] if item[5] is not None else ''
                    c = 'yellow' if rtype in ('REG_DWORD', 'REG_QWORD') else ('green' if rtype == 'REG_SZ' else ('magenta' if rtype == 'REG_BINARY' else 'white'))
                    if idx == selected:
                        print(f"  {C['sel']}> {vname}{C['reset']}")
                        print(f"    {C['dim']}{rtype:12}{C['reset']} {C[c]}{vdata}{C['reset']}")
                    else:
                        print(f"   {C[c]}{vname}{C['reset']}")
                        print(f"    {C['dim']}{rtype:12}{C['reset']} {C['dim']}{vdata[:60]}{C['reset']}")

        if len(subkeys) + len(values) > self.page_offset + self.page_size:
            print(f"  {C['dim']}... and more ({len(subkeys) + len(values) - self.page_offset - self.page_size} more){C['reset']}")
        print()

        items_count = len(subkeys) + len(values)
        print(f"  {C['dim']}Items: {items_count}  |  Sel: {selected+1}/{items_count}{C['reset']}")
        print()

        cmds = (
            f"  {C['bold']}[↑↓]{C['reset']} Navigate  "
            f"{C['bold']}[Enter]{C['reset']} Open  "
            f"{C['bold']}[Ins]{C['reset']} New Key  "
            f"{C['bold']}[Del]{C['reset']} Delete  "
            f"{C['bold']}[F2]{C['reset']} Rename\n"
            f"  {C['bold']}[V]{C['reset']} New Value  "
            f"{C['bold']}[M]{C['reset']} Modify  "
            f"{C['bold']}[X]{C['reset']} Del Value  "
            f"{C['bold']}[L]{C['reset']} Load Hive  "
            f"{C['bold']}[U]{C['reset']} Unload Hive\n"
            f"  {C['bold']}[I]{C['reset']} Import .reg  "
            f"{C['bold']}[E]{C['reset']} Export .reg  "
            f"{C['bold']}[S]{C['reset']} Search  "
            f"{C['bold']}[C]{C['reset']} Copy Path  "
            f"{C['bold']}[F5]{C['reset']} Refresh  "
            f"{C['bold']}[0]{C['reset']} Back  "
            f"{C['bold']}[Q]{C['reset']} Quit"
        )
        print(cmds)

        if self.status_text:
            print(f"\n  {C[self.status_color]}▸ {self.status_text}{C['reset']}")
            self.status_text = ''

    def prompt_input(self, prompt, default=''):
        val = input(f"  {C['bold']}▸{C['reset']} {prompt}: ").strip()
        if not val and default:
            return default
        return val

    def prompt_choice(self, prompt, options):
        print(f"\n  {C['bold']}{prompt}{C['reset']}")
        for k, v in options.items():
            print(f"    {C['cyan']}[{k}]{C['reset']} {v}")
        return input(f"  {C['bold']}▸{C['reset']} ").strip().upper()

    def edit_binary(self, prompt, current=b''):
        print(f"\n  {C['bold']}{prompt}{C['reset']}")
        print(f"  {C['dim']}Current ({len(current)} bytes): {current.hex().upper()[:80]}{C['reset']}")
        val = input(f"  {C['bold']}▸ Enter hex bytes (e.g. 00 FF AA):{C['reset']} ").strip()
        if not val:
            return current
        try:
            return bytes.fromhex(val.replace(' ', ''))
        except:
            print(f"{C['bad']} Невалидный hex{C['reset']}")
            return current

    def edit_multi_sz(self, prompt, current=None):
        if current is None:
            current = []
        print(f"\n  {C['bold']}{prompt}{C['reset']}")
        print(f"  {C['dim']}Current: {', '.join(current)}{C['reset']}")
        print(f"  {C['dim']}Enter strings, empty line to finish{C['reset']}")
        items = []
        while True:
            line = input(f"  {C['bold']}▸{C['reset']} ").strip()
            if not line:
                break
            items.append(line)
        return items if items else current

    def run(self):
        if not IS_WINDOWS:
            print(f"{C['bad']} Редактор реестра работает только на Windows{C['reset']}")
            input("  Нажми Enter...")
            return

        self.clear_screen()
        self.print_header()
        print(f"\n  {C['bold']}Выберите корневой куст:{C['reset']}\n")
        hives = [
            ('1', 'HKEY_LOCAL_MACHINE (HKLM)'),
            ('2', 'HKEY_CURRENT_USER (HKCU)'),
            ('3', 'HKEY_CLASSES_ROOT (HKCR)'),
            ('4', 'HKEY_USERS (HKU)'),
            ('5', 'HKEY_CURRENT_CONFIG (HKCC)'),
        ]
        for k, v in hives:
            print(f"    {C['cyan']}[{k}]{C['reset']} {v}")
        print(f"    {C['cyan']}[0]{C['reset']} Exit\n")

        choice = input(f"  {C['bold']}▸{C['reset']} ").strip()
        hive_map = {'1': 'HKEY_LOCAL_MACHINE', '2': 'HKEY_CURRENT_USER', '3': 'HKEY_CLASSES_ROOT', '4': 'HKEY_USERS', '5': 'HKEY_CURRENT_CONFIG'}

        if choice not in hive_map:
            return

        hive = hive_map[choice]
        if not self.editor.open_key(hive):
            self.status_text = f"Не удалось открыть {hive}"
            self.status_color = 'red'
            input(f"  {C['bad']} {self.status_text}{C['reset']}\n  Нажми Enter...")
            return

        while self.editor.running:
            try:
                subkeys, values = self.editor.enumerate_key()
                total_items = len(subkeys) + len(values)

                if self.selected_index >= total_items:
                    self.selected_index = max(0, total_items - 1)

                self.print_key_list(subkeys, values, self.selected_index)

                key = self._get_key()
                if key is None:
                    continue

                if key == 'KEY_UP':
                    self.selected_index = max(0, self.selected_index - 1)
                elif key == 'KEY_DOWN':
                    self.selected_index = min(total_items - 1, self.selected_index + 1)
                elif key == 'KEY_ENTER':
                    if self.selected_index < len(subkeys):
                        name = subkeys[self.selected_index][0]
                        new_path = f"{self.editor.current_path}\\{name}" if self.editor.current_path else name
                        if self.editor.open_key(self.editor.current_hive, new_path):
                            self.selected_index = 0
                            self.page_offset = 0
                        else:
                            self.status_text = f"Не удалось открыть {name}"
                            self.status_color = 'red'
                    elif self.selected_index < total_items:
                        self._modify_value_dialog(values[self.selected_index - len(subkeys)])
                elif key == 'KEY_BACK':
                    self._navigate_up()
                elif key == 'KEY_INS':
                    self._create_key_dialog()
                elif key == 'KEY_DEL':
                    if self.selected_index < len(subkeys):
                        self._delete_key_dialog(subkeys[self.selected_index][0])
                    elif self.selected_index < total_items:
                        self._delete_value_dialog(values[self.selected_index - len(subkeys)])
                elif key == 'KEY_F2':
                    if self.selected_index < len(subkeys):
                        self._rename_key_dialog(subkeys[self.selected_index][0])
                elif key == 'KEY_F5':
                    pass
                elif key == 'V':
                    self._create_value_dialog()
                elif key == 'M':
                    if self.selected_index >= len(subkeys) and self.selected_index < total_items:
                        self._modify_value_dialog(values[self.selected_index - len(subkeys)])
                elif key == 'X':
                    if self.selected_index >= len(subkeys) and self.selected_index < total_items:
                        self._delete_value_dialog(values[self.selected_index - len(subkeys)])
                elif key == 'L':
                    self._load_hive_dialog()
                elif key == 'U':
                    self._unload_hive_dialog()
                elif key == 'I':
                    self._import_dialog()
                elif key == 'E':
                    self._export_dialog()
                elif key == 'S':
                    self._search_dialog()
                elif key == 'C':
                    self._copy_path()
                elif key == '0':
                    self._navigate_up()
                elif key == 'Q':
                    self.editor.running = False

            except KeyboardInterrupt:
                break
            except Exception as e:
                self.status_text = f"Error: {e}"
                self.status_color = 'red'

    def _get_key(self):
        if os.name == 'nt':
            import msvcrt
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                if ch == b'\xe0':
                    ch2 = msvcrt.getch()
                    arrow_map = {
                        b'H': 'KEY_UP', b'P': 'KEY_DOWN',
                        b'M': 'KEY_RIGHT', b'K': 'KEY_LEFT',
                        b'G': 'KEY_HOME', b'O': 'KEY_END',
                        b'I': 'KEY_PGUP', b'Q': 'KEY_PGDN',
                        b'R': 'KEY_INS', b'S': 'KEY_DEL',
                    }
                    fn_map = {
                        b'\x3b': 'KEY_F1', b'\x3c': 'KEY_F2', b'\x3d': 'KEY_F3',
                        b'\x3e': 'KEY_F4', b'\x3f': 'KEY_F5', b'\x40': 'KEY_F6',
                        b'\x41': 'KEY_F7', b'\x42': 'KEY_F8', b'\x43': 'KEY_F9',
                        b'\x44': 'KEY_F10',
                    }
                    if ch2 in arrow_map:
                        return arrow_map[ch2]
                    if ch2 in fn_map:
                        return fn_map[ch2]
                    return None
                elif ch == b'\r':
                    return 'KEY_ENTER'
                elif ch == b'\x08' or ch == b'\x7f':
                    return 'KEY_BACK'
                elif ch == b'\x1b':
                    return 'KEY_ESC'
                elif ch == b'\t':
                    return 'KEY_TAB'
                else:
                    try:
                        c = ch.decode('utf-8', errors='replace').upper()
                        return c
                    except:
                        return None
            return None
        else:
            import select
            if select.select([sys.stdin], [], [], 0.1)[0]:
                ch = sys.stdin.read(1)
                if ch == '\x1b':
                    seq = sys.stdin.read(2)
                    if seq == '[A': return 'KEY_UP'
                    elif seq == '[B': return 'KEY_DOWN'
                    elif seq == '[C': return 'KEY_RIGHT'
                    elif seq == '[D': return 'KEY_LEFT'
                    return None
                elif ch == '\r' or ch == '\n': return 'KEY_ENTER'
                elif ch == '\x08' or ch == '\x7f': return 'KEY_BACK'
                elif ch == '\x1b': return 'KEY_ESC'
                else: return ch.upper() if ch.isalpha() else ch
            return None

    def _navigate_up(self):
        if not self.editor.current_path:
            self.editor.running = False
            return
        parts = self.editor.current_path.split('\\')
        parent = '\\'.join(parts[:-1])
        if self.editor.open_key(self.editor.current_hive, parent):
            self.selected_index = 0
            self.page_offset = 0

    def _create_key_dialog(self):
        name = self.prompt_input('Enter key name')
        if not name:
            return
        if self.editor.create_key(name):
            self.status_text = f'Key created: {name}'
            self.status_color = 'green'
        else:
            self.status_text = f'Failed to create key: {name}'
            self.status_color = 'red'

    def _delete_key_dialog(self, name):
        print(f"\n  {C['warn']} Delete key '{name}' and all subkeys?{C['reset']}")
        confirm = input(f"  {C['bold']}▸ Type 'YES' to confirm: {C['reset']}").strip()
        if confirm == 'YES':
            if self.editor.delete_key(name):
                self.status_text = f'Key deleted: {name}'
                self.status_color = 'green'
            else:
                self.status_text = f'Failed to delete key: {name}'
                self.status_color = 'red'
        else:
            self.status_text = 'Cancelled'
            self.status_color = 'yellow'

    def _rename_key_dialog(self, old_name):
        new_name = self.prompt_input(f'Rename "{old_name}" to')
        if not new_name or new_name == old_name:
            return
        if self.editor.rename_key(old_name, new_name):
            self.status_text = f'Renamed to: {new_name}'
            self.status_color = 'green'
        else:
            self.status_text = 'Rename failed'
            self.status_color = 'red'

    def _create_value_dialog(self):
        name = self.prompt_input('Value name (leave empty for default)')
        print(f"\n  {C['bold']}Select type:{C['reset']}")
        types = [
            ('1', 'REG_SZ (string)'),
            ('2', 'REG_DWORD (32-bit)'),
            ('3', 'REG_QWORD (64-bit)'),
            ('4', 'REG_BINARY'),
            ('5', 'REG_MULTI_SZ (multi-string)'),
            ('6', 'REG_EXPAND_SZ (expandable string)'),
        ]
        for k, v in types:
            print(f"    {C['cyan']}[{k}]{C['reset']} {v}")
        t_choice = input(f"  {C['bold']}▸{C['reset']} ").strip()

        type_map = {'1': winreg.REG_SZ, '2': winreg.REG_DWORD, '3': winreg.REG_QWORD,
                    '4': winreg.REG_BINARY, '5': winreg.REG_MULTI_SZ, '6': winreg.REG_EXPAND_SZ}
        type_id = type_map.get(t_choice, winreg.REG_SZ)

        if type_id == winreg.REG_SZ or type_id == winreg.REG_EXPAND_SZ:
            data = self.prompt_input('Value data')
        elif type_id == winreg.REG_DWORD:
            val = self.prompt_input('Value (decimal or 0xhex)')
            try:
                data = int(val, 16) if val.startswith('0x') else int(val) if val else 0
            except:
                data = 0
        elif type_id == winreg.REG_QWORD:
            val = self.prompt_input('Value (decimal or 0xhex)')
            try:
                data = int(val, 16) if val.startswith('0x') else int(val) if val else 0
            except:
                data = 0
        elif type_id == winreg.REG_BINARY:
            data = self.edit_binary('Enter hex bytes')
            if not data:
                data = b'\x00'
        elif type_id == winreg.REG_MULTI_SZ:
            data = self.edit_multi_sz('Enter strings (empty line to finish)')
        else:
            data = ''

        if self.editor.set_value(name, data, type_id):
            self.status_text = f'Value created: {name}'
            self.status_color = 'green'
        else:
            self.status_text = f'Failed to create value: {name}'
            self.status_color = 'red'

    def _modify_value_dialog(self, value_info):
        name, rtype, display, type_id, data = value_info
        print(f"\n  {C['bold']}Modify Value{C['reset']}")
        print(f"  Name: {C['cyan']}{name}{C['reset']}")
        print(f"  Type: {C['yellow']}{rtype}{C['reset']}")
        print(f"  Current: {C['dim']}{display[:60]}{C['reset']}\n")

        if type_id in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
            new_data = self.prompt_input(f'New value', str(data) if data else '')
        elif type_id == winreg.REG_DWORD:
            new_val = self.prompt_input(f'New value', f'{data}')
            try:
                new_data = int(new_val, 16) if new_val.startswith('0x') else int(new_val) if new_val else data
            except:
                new_data = data
        elif type_id == winreg.REG_QWORD:
            new_val = self.prompt_input(f'New value', f'{data}')
            try:
                new_data = int(new_val, 16) if new_val.startswith('0x') else int(new_val) if new_val else data
            except:
                new_data = data
        elif type_id == winreg.REG_BINARY:
            new_data = self.edit_binary('Edit hex bytes', data if isinstance(data, bytes) else b'')
        elif type_id == winreg.REG_MULTI_SZ:
            current = list(data) if isinstance(data, (list, tuple)) else []
            new_data = self.edit_multi_sz('Edit strings', current)
        else:
            self.status_text = f'Unsupported type: {rtype}'
            self.status_color = 'red'
            return

        if self.editor.set_value(name, new_data, type_id):
            self.status_text = 'Value updated'
            self.status_color = 'green'
        else:
            self.status_text = 'Failed to update value'
            self.status_color = 'red'

    def _delete_value_dialog(self, value_info):
        name = value_info[0]
        confirm = input(f"  {C['bold']}▸ Delete value '{name}'? (y/N): {C['reset']}").strip().upper()
        if confirm == 'Y':
            if self.editor.delete_value(name):
                self.status_text = f'Value deleted: {name}'
                self.status_color = 'green'
            else:
                self.status_text = 'Failed to delete value'
                self.status_color = 'red'

    def _load_hive_dialog(self):
        print(f"\n  {C['bold']}Load Hive{C['reset']}")
        print(f"  {C['dim']}Mount a hive file (e.g., C:\\Windows\\System32\\config\\SOFTWARE){C['reset']}\n")
        hive_path = self.prompt_input('Path to hive file').strip('"')
        if not hive_path or not os.path.exists(hive_path):
            self.status_text = f'File not found: {hive_path}'
            self.status_color = 'red'
            return
        key_name = self.prompt_input('Key name (under current hive)')
        if not key_name:
            self.status_text = 'Key name required'
            self.status_color = 'red'
            return
        if self.editor.load_hive(key_name, hive_path):
            self.status_text = f'Hive loaded: {key_name}'
            self.status_color = 'green'
        else:
            self.status_text = 'Failed to load hive'
            self.status_color = 'red'

    def _unload_hive_dialog(self):
        key_name = self.prompt_input('Key name to unload')
        if not key_name:
            return
        if self.editor.unload_hive(key_name):
            self.status_text = f'Hive unloaded: {key_name}'
            self.status_color = 'green'
        else:
            self.status_text = 'Failed to unload hive'
            self.status_color = 'red'

    def _import_dialog(self):
        file_path = self.prompt_input('Path to .reg file').strip('"')
        if not file_path:
            return
        self.clear_screen()
        print(f"\n  {C['bold']}Importing: {file_path}{C['reset']}\n")
        if self.editor.import_reg(file_path):
            self.status_text = 'Import complete'
            self.status_color = 'green'
        else:
            self.status_text = 'Import completed with errors'
            self.status_color = 'yellow'
        input(f"\n  Нажми Enter...")

    def _export_dialog(self):
        file_path = self.prompt_input('Path for .reg file', 'export.reg').strip('"')
        if not file_path:
            return
        if not file_path.endswith('.reg'):
            file_path += '.reg'
        if self.editor.export_reg(file_path):
            self.status_text = f'Exported to: {os.path.basename(file_path)}'
            self.status_color = 'green'
        else:
            self.status_text = 'Export failed'
            self.status_color = 'red'

    def _search_dialog(self):
        query = self.prompt_input('Search for')
        if not query:
            return
        self.clear_screen()
        print(f"\n  {C['bold']}Searching for '{query}'...{C['reset']}\n")
        results = self.editor.search(query, max_results=200)
        if not results:
            print(f"  {C['yellow']}No results found{C['reset']}")
        else:
            print(f"  {C['green']}Found {len(results)} results:{C['reset']}\n")
            for r in results[:50]:
                if r[0] == 'key':
                    print(f"  {C['cyan']}[KEY]{C['reset']} {r[1]}")
                elif r[0] == 'value_name':
                    print(f"  {C['magenta']}[VAL]{C['reset']} {r[1]}  →  {r[2]} ({r[3]})")
                elif r[0] == 'value_data':
                    print(f"  {C['yellow']}[DAT]{C['reset']} {r[1]}  →  {r[2]}")
            if len(results) > 50:
                print(f"  {C['dim']}... and {len(results) - 50} more{C['reset']}")
        input(f"\n  Нажми Enter...")

    def _copy_path(self):
        path = self.editor._get_full_path()
        if IS_WINDOWS:
            try:
                import ctypes
                ctypes.windll.user32.OpenClipboard(None)
                ctypes.windll.user32.EmptyClipboard()
                ctypes.windll.user32.SetClipboardData(1, ctypes.create_unicode_buffer(path))
                ctypes.windll.user32.CloseClipboard()
                self.status_text = f'Path copied: {path}'
            except:
                self.status_text = f'Path: {path}'
        else:
            self.status_text = f'Path: {path}'
        self.status_color = 'green'


def start():
    if not IS_WINDOWS:
        print(f"{C['bad']} Редактор реестра работает только на Windows{C['reset']}")
        input("  Нажми Enter для возврата...")
        return
    editor = RegistryEditor()
    ui = RegEditUI(editor)
    try:
        ui.run()
    finally:
        editor.close()


if __name__ == '__main__':
    start()
