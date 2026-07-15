#!/usr/bin/env python3
"""
autoRe File Maneger — консольный файловый менеджер
С защитой от повторных срабатываний клавиш
"""

import os
import sys
import shutil
import time
import queue
import threading

import urwid
import keyboard
from PIL import Image


# =============================================================================
# ANSI цвета
# =============================================================================
C = {
    'reset':    '\033[0m',
    'header':   '\033[44;37m',
    'status':   '\033[47;30m',
    'footer':   '\033[42;37m',
    'error':    '\033[41;37m',
    'dir':      '\033[33m',
    'file':     '\033[37m',
    'image':    '\033[35m',
    'text':     '\033[36m',
    'selected': '\033[43;30m',
    'line_num': '\033[36m',
    'modified': '\033[41;37m',
    'cursor':   '\033[7m',
}


def safe_cols_rows(screen):
    try:
        cols, rows = screen.get_cols_rows()
        if cols < 10: cols = 80
        if rows < 5:  rows = 24
        return cols, rows
    except:
        return 80, 24


def write_screen(screen, lines):
    try:
        screen.clear()
        screen.write("\n".join(lines) + "\n")
        screen.flush()
    except:
        pass


# =============================================================================
# ТЕКСТОВЫЙ РЕДАКТОР
# =============================================================================
class TextEditor:
    def __init__(self, filepath):
        self.filepath = filepath
        self.lines = [""]
        self.cx = 0
        self.cy = 0
        self.scroll_y = 0
        self.modified = False
        self.encoding = 'utf-8'
        self.running = True

        self.cmd_queue = queue.Queue()
        self.screen = urwid.raw_display.Screen()
        
        # Защита от повторных срабатываний
        self.last_key_time = 0
        self.key_debounce = 0.05  # 50мс задержка
        
        self._load_file()

    def _load_file(self):
        try:
            with open(self.filepath, 'rb') as f:
                raw = f.read(4)
            if raw[:3] == b'\xef\xbb\xbf':
                self.encoding = 'utf-8-sig'
            elif raw[:4] in (b'\xff\xfe\x00\x00', b'\x00\x00\xfe\xff'):
                self.encoding = 'utf-32'
            elif raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
                self.encoding = 'utf-16'
            else:
                for enc in ['utf-8', 'cp1251', 'koi8-r', 'latin-1']:
                    try:
                        with open(self.filepath, 'r', encoding=enc) as f:
                            f.read()
                        self.encoding = enc
                        break
                    except:
                        continue
        except:
            self.encoding = 'utf-8'

        try:
            with open(self.filepath, 'r', encoding=self.encoding) as f:
                content = f.read()
                self.lines = content.split('\n')
                if not self.lines:
                    self.lines = [""]
        except Exception as e:
            self.lines = [f"Ошибка чтения: {e}", "", "Файл может быть бинарным."]
            self.encoding = 'utf-8'

    def _save_file(self):
        try:
            with open(self.filepath, 'w', encoding=self.encoding) as f:
                f.write('\n'.join(self.lines))
            self.modified = False
            return True
        except:
            return False

    def _on_key(self, event):
        """Обработчик клавиш с защитой от повторных срабатываний"""
        # Реагируем только на KEY_DOWN (нажатие), игнорируем KEY_UP (отпускание)
        if hasattr(event, 'event_type') and event.event_type != 'down':
            return
            
        # Защита от дребезга
        current_time = time.time()
        if current_time - self.last_key_time < self.key_debounce:
            return
        self.last_key_time = current_time
        
        if not hasattr(event, 'name'):
            return
        name = event.name

        if name == 'up':
            self._move(0, -1)
        elif name == 'down':
            self._move(0, 1)
        elif name == 'left':
            self._move(-1, 0)
        elif name == 'right':
            self._move(1, 0)
        elif name == 'home':
            self.cx = 0
            self._redraw()
        elif name == 'end':
            self.cx = len(self.lines[self.cy])
            self._redraw()
        elif name == 'page up':
            self._page_scroll(-1)
        elif name == 'page down':
            self._page_scroll(1)
        elif name == 'enter':
            self._insert_newline()
        elif name == 'backspace':
            self._backspace()
        elif name == 'delete':
            self._delete_forward()
        elif name == 'tab':
            self._insert_text("    ")
        elif name == 'f10':
            self.cmd_queue.put('exit')
        elif name == 'esc':
            self.cmd_queue.put('exit')
        else:
            if hasattr(event, 'char') and event.char:
                code = ord(event.char) if len(event.char) == 1 else 0
                if code == 19:  # Ctrl+S
                    self._save_file()
                    self._redraw()
                elif code == 17:  # Ctrl+Q
                    self.cmd_queue.put('exit')
                elif len(event.char) == 1 and code >= 32:
                    self._insert_text(event.char)

    def _move(self, dx, dy):
        self.cx += dx
        self.cy += dy

        if self.cy < 0:
            self.cy = 0
        if self.cy >= len(self.lines):
            self.cy = len(self.lines) - 1

        line_len = len(self.lines[self.cy])
        if self.cx < 0:
            self.cx = 0
        if self.cx > line_len:
            self.cx = line_len

        self._adjust_scroll()
        self._redraw()

    def _page_scroll(self, direction):
        _, rows = safe_cols_rows(self.screen)
        page_size = max(1, rows - 4)
        self.cy += direction * page_size

        if self.cy < 0:
            self.cy = 0
        if self.cy >= len(self.lines):
            self.cy = len(self.lines) - 1

        self.cx = min(self.cx, len(self.lines[self.cy]))
        self._adjust_scroll()
        self._redraw()

    def _adjust_scroll(self):
        _, rows = safe_cols_rows(self.screen)
        visible_height = rows - 4
        if visible_height < 1:
            visible_height = 1

        if self.cy < self.scroll_y:
            self.scroll_y = self.cy

        if self.cy >= self.scroll_y + visible_height:
            self.scroll_y = self.cy - visible_height + 1

        if self.scroll_y < 0:
            self.scroll_y = 0

        max_scroll = max(0, len(self.lines) - visible_height)
        if self.scroll_y > max_scroll:
            self.scroll_y = max_scroll

    def _insert_text(self, text):
        line = self.lines[self.cy]
        self.lines[self.cy] = line[:self.cx] + text + line[self.cx:]
        self.cx += len(text)
        self.modified = True
        self._adjust_scroll()
        self._redraw()

    def _insert_newline(self):
        line = self.lines[self.cy]
        left = line[:self.cx]
        right = line[self.cx:]
        self.lines[self.cy] = left
        self.lines.insert(self.cy + 1, right)
        self.cy += 1
        self.cx = 0
        self.modified = True
        self._adjust_scroll()
        self._redraw()

    def _backspace(self):
        if self.cx > 0:
            line = self.lines[self.cy]
            self.lines[self.cy] = line[:self.cx - 1] + line[self.cx:]
            self.cx -= 1
            self.modified = True
        elif self.cy > 0:
            prev_len = len(self.lines[self.cy - 1])
            self.lines[self.cy - 1] += self.lines[self.cy]
            del self.lines[self.cy]
            self.cy -= 1
            self.cx = prev_len
            self.modified = True
        self._adjust_scroll()
        self._redraw()

    def _delete_forward(self):
        line = self.lines[self.cy]
        if self.cx < len(line):
            self.lines[self.cy] = line[:self.cx] + line[self.cx + 1:]
            self.modified = True
        elif self.cy < len(self.lines) - 1:
            self.lines[self.cy] += self.lines[self.cy + 1]
            del self.lines[self.cy + 1]
            self.modified = True
        self._redraw()

    def _redraw(self):
        cols, rows = safe_cols_rows(self.screen)
        out = []

        mod_mark = " *MODIFIED*" if self.modified else ""
        title = f" autoRe Editor: {os.path.basename(self.filepath)}{mod_mark} "
        out.append(f"{C['header']}{title[:cols].ljust(cols)}{C['reset']}")

        visible_height = rows - 4
        if visible_height < 1:
            visible_height = 1

        for i in range(visible_height):
            line_idx = self.scroll_y + i
            if line_idx < len(self.lines):
                line_text = self.lines[line_idx]

                h_scroll = 0
                text_area_width = cols - 6
                if text_area_width < 10:
                    text_area_width = 10
                if self.cx > h_scroll + text_area_width - 1:
                    h_scroll = self.cx - text_area_width + 1

                visible_text = line_text[h_scroll:h_scroll + text_area_width]

                num_str = f"{line_idx + 1:4d}|"

                if line_idx == self.cy:
                    cursor_col = self.cx - h_scroll
                    if cursor_col < len(visible_text):
                        display = (visible_text[:cursor_col]
                                   + '█'
                                   + visible_text[cursor_col + 1:])
                    else:
                        display = visible_text + '█'

                    out.append(f"{C['line_num']}{num_str}{C['reset']}{display}")
                else:
                    out.append(f"{C['line_num']}{num_str}{C['reset']}{visible_text}")
            else:
                out.append(f"{C['line_num']}    |{C['reset']}~")

        while len(out) < rows - 2:
            out.append(f"{C['line_num']}    |{C['reset']}~")

        status_parts = [
            f"Ln:{self.cy + 1}/{len(self.lines)}",
            f"Col:{self.cx + 1}",
            f"Enc:{self.encoding}",
        ]
        if self.modified:
            status_parts.insert(0, "[MODIFIED]")
        status = " ".join(status_parts)
        out.append(f"{C['status']}{status[:cols].ljust(cols)}{C['reset']}")

        footer = " Ctrl+S:Save  Ctrl+Q/F10:Quit  PgUp/PgDn:Scroll "
        out.append(f"{C['footer']}{footer.center(cols)[:cols]}{C['reset']}")

        write_screen(self.screen, out)

    def run(self):
        try:
            self.screen.start()
            self.screen.set_terminal_properties(colors=256)
            self._adjust_scroll()
            self._redraw()

            hook_ref = keyboard.hook(self._on_key)

            while self.running:
                try:
                    cmd = self.cmd_queue.get(timeout=0.05)
                    if cmd == 'exit':
                        self.running = False
                except queue.Empty:
                    pass

        except KeyboardInterrupt:
            pass
        finally:
            try:
                keyboard.unhook(hook_ref)
            except:
                pass
            try:
                self.screen.stop()
            except:
                pass


# =============================================================================
# ПРОСМОТРЩИК ИЗОБРАЖЕНИЙ
# =============================================================================
class ImageViewer:
    def __init__(self, filepath):
        self.filepath = filepath
        self.image = None
        self.error_msg = None
        self.running = True
        self.cmd_queue = queue.Queue()
        self.screen = urwid.raw_display.Screen()
        
        # Защита от повторных срабатываний
        self.last_key_time = 0
        self.key_debounce = 0.05

        try:
            self.image = Image.open(filepath).convert('RGB')
        except Exception as e:
            self.error_msg = str(e)

    def _on_key(self, event):
        if hasattr(event, 'event_type') and event.event_type != 'down':
            return
            
        current_time = time.time()
        if current_time - self.last_key_time < self.key_debounce:
            return
        self.last_key_time = current_time
        
        if hasattr(event, 'name') and event.name in ['f10', 'q', 'esc']:
            self.cmd_queue.put('exit')

    def _redraw(self):
        cols, rows = safe_cols_rows(self.screen)
        out = []

        title = f" autoRe Viewer: {os.path.basename(self.filepath)} "
        out.append(f"{C['header']}{title[:cols].ljust(cols)}{C['reset']}")

        if self.image:
            img_w = max(1, cols)
            img_h = max(1, (rows - 3) * 2)

            try:
                resized = self.image.resize((img_w, img_h), Image.LANCZOS)
                pixels = resized.load()

                for y in range(0, img_h - 1, 2):
                    line = ""
                    for x in range(img_w):
                        r1, g1, b1 = pixels[x, y]
                        r2, g2, b2 = pixels[x, y + 1]

                        if r1 == r2 and g1 == g2 and b1 == b2:
                            line += f"\033[48;2;{r1};{g1};{b1}m \033[0m"
                        else:
                            line += (f"\033[38;2;{r1};{g1};{b1}m"
                                     f"\033[48;2;{r2};{g2};{b2}m▄\033[0m")
                    out.append(line)
            except Exception as e:
                out.append(f"Ошибка рендеринга: {e}")
        else:
            out.append(f"{C['error']} Не удалось загрузить изображение {C['reset']}")
            if self.error_msg:
                out.append(f"  {self.error_msg}")

        while len(out) < rows - 1:
            out.append("")

        if self.image:
            info = f" {self.image.size[0]}x{self.image.size[1]} {self.image.format or ''} "
        else:
            info = ""
        footer_text = f"{info} | F10/Q: Exit "
        out.append(f"{C['footer']}{footer_text.center(cols)[:cols]}{C['reset']}")

        write_screen(self.screen, out)

    def run(self):
        try:
            self.screen.start()
            self.screen.set_terminal_properties(colors=256)
            self._redraw()

            hook_ref = keyboard.hook(self._on_key)

            while self.running:
                try:
                    cmd = self.cmd_queue.get(timeout=0.05)
                    if cmd == 'exit':
                        self.running = False
                except queue.Empty:
                    pass

        except KeyboardInterrupt:
            pass
        finally:
            try:
                keyboard.unhook(hook_ref)
            except:
                pass
            try:
                self.screen.stop()
            except:
                pass


# =============================================================================
# ФАЙЛОВЫЙ МЕНЕДЖЕР
# =============================================================================
class AutoReFileManager:
    IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.ico'}
    TEXT_EXTS = {
        '.txt', '.py', '.pyw', '.js', '.ts', '.jsx', '.tsx',
        '.html', '.htm', '.css', '.scss', '.less',
        '.md', '.rst', '.json', '.yaml', '.yml', '.xml', '.toml', '.ini', '.cfg', '.conf',
        '.csv', '.tsv', '.log',
        '.sh', '.bash', '.zsh', '.fish',
        '.c', '.cpp', '.h', '.hpp', '.cc', '.cxx',
        '.java', '.kt', '.scala',
        '.go', '.rs', '.rb', '.php', '.pl', '.lua', '.r',
        '.sql', '.makefile', '.dockerfile',
    }

    def __init__(self):
        self.current_dir = os.getcwd()
        self.file_list = []
        self.selected_index = 0
        self.running = True
        self.scroll_offset = 0

        self.cmd_queue = queue.Queue()
        self.screen = urwid.raw_display.Screen()
        
        # Защита от повторных срабатываний
        self.last_key_time = 0
        self.key_debounce = 0.1  # 100мс для файлового менеджера (больше, т.к. операции тяжелее)
        
        self._update_file_list()

    def _get_file_type(self, filepath):
        _, ext = os.path.splitext(filepath.lower())
        if ext in self.IMAGE_EXTS:
            return 'image'
        if ext in self.TEXT_EXTS:
            return 'text'
        try:
            with open(filepath, 'rb') as f:
                chunk = f.read(512)
                if b'\x00' not in chunk:
                    return 'text'
        except:
            pass
        return 'binary'

    def _update_file_list(self):
        try:
            items = os.listdir(self.current_dir)
        except:
            items = []

        dirs = []
        files = []

        for item in items:
            if item == '.':
                continue

            full_path = os.path.join(self.current_dir, item)
            try:
                if os.path.isdir(full_path):
                    dirs.append((item, True, 'dir'))
                else:
                    ftype = self._get_file_type(full_path)
                    files.append((item, False, ftype))
            except:
                files.append((item, False, 'binary'))

        dirs.sort(key=lambda x: x[0].lower())
        files.sort(key=lambda x: x[0].lower())

        if self.current_dir != os.path.dirname(self.current_dir):
            self.file_list = [("..", True, 'dir')] + dirs + files
        else:
            self.file_list = dirs + files

        if not self.file_list:
            self.selected_index = 0
        elif self.selected_index >= len(self.file_list):
            self.selected_index = len(self.file_list) - 1

    def _on_key(self, event):
        """Обработчик клавиш с защитой от повторных срабатываний"""
        # Реагируем только на KEY_DOWN
        if hasattr(event, 'event_type') and event.event_type != 'down':
            return
            
        # Защита от дребезга
        current_time = time.time()
        if current_time - self.last_key_time < self.key_debounce:
            return
        self.last_key_time = current_time
        
        if not hasattr(event, 'name'):
            return
        name = event.name

        if name == 'up':
            self._move(-1)
        elif name == 'down':
            self._move(1)
        elif name == 'home':
            self.selected_index = 0
            self._redraw()
        elif name == 'end':
            self.selected_index = len(self.file_list) - 1
            self._redraw()
        elif name == 'page up':
            self._move(-10)
        elif name == 'page down':
            self._move(10)
        elif name == 'enter':
            self._open_selected()
        elif name == 'f5':
            self._copy_selected()
        elif name == 'f6':
            self._rename_selected()
        elif name == 'f8':
            self._delete_selected()
        elif name in ('f10', 'q'):
            self.cmd_queue.put('exit')

    def _move(self, delta):
        new_idx = self.selected_index + delta
        if new_idx < 0:
            new_idx = 0
        if new_idx >= len(self.file_list):
            new_idx = len(self.file_list) - 1
        if new_idx != self.selected_index:
            self.selected_index = new_idx
            self._redraw()

    def _get_selected(self):
        if self.file_list and 0 <= self.selected_index < len(self.file_list):
            return self.file_list[self.selected_index]
        return None

    def _open_selected(self):
        item = self._get_selected()
        if not item:
            return

        name, is_dir, ftype = item
        full_path = os.path.join(self.current_dir, name)

        if is_dir:
            if name == "..":
                parent = os.path.dirname(self.current_dir)
                if parent != self.current_dir:
                    self.current_dir = parent
            else:
                self.current_dir = full_path

            self.current_dir = os.path.normpath(self.current_dir)
            self.selected_index = 0
            self.scroll_offset = 0
            self._update_file_list()
            self._redraw()
        else:
            self.cmd_queue.put(('open_file', full_path, ftype))

    def _copy_selected(self):
        item = self._get_selected()
        if not item or item[0] == "..":
            return

        name, is_dir, ftype = item
        src = os.path.join(self.current_dir, name)
        base, ext = os.path.splitext(name)
        dst_name = f"{base}_copy{ext}"
        dst = os.path.join(self.current_dir, dst_name)

        try:
            if is_dir:
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
            self._update_file_list()
            self._redraw()
        except:
            pass

    def _rename_selected(self):
        item = self._get_selected()
        if not item or item[0] == "..":
            return

        name, is_dir, ftype = item
        src = os.path.join(self.current_dir, name)
        base, ext = os.path.splitext(name)
        dst_name = f"{base}_renamed{ext}"
        dst = os.path.join(self.current_dir, dst_name)

        try:
            shutil.move(src, dst)
            self._update_file_list()
            self._redraw()
        except:
            pass

    def _delete_selected(self):
        item = self._get_selected()
        if not item or item[0] == "..":
            return

        name, is_dir, ftype = item
        full_path = os.path.join(self.current_dir, name)

        try:
            if is_dir:
                shutil.rmtree(full_path)
            else:
                os.remove(full_path)
            self._update_file_list()
            self._redraw()
        except:
            pass

    def _redraw(self):
        cols, rows = safe_cols_rows(self.screen)
        out = []

        header = " autoRe File Maneger "
        out.append(f"{C['header']}{header.center(cols)[:cols]}{C['reset']}")

        list_height = rows - 3
        if list_height < 1:
            list_height = 1

        if self.selected_index < self.scroll_offset:
            self.scroll_offset = self.selected_index
        if self.selected_index >= self.scroll_offset + list_height:
            self.scroll_offset = self.selected_index - list_height + 1

        visible = self.file_list[self.scroll_offset:self.scroll_offset + list_height]

        for i, (name, is_dir, ftype) in enumerate(visible):
            real_idx = self.scroll_offset + i

            if name == "..":
                display = "[..]"
                color = C['dir']
            elif is_dir:
                display = f"[{name}]"
                color = C['dir']
            else:
                display = name
                if ftype == 'image':
                    color = C['image']
                elif ftype == 'text':
                    color = C['text']
                else:
                    color = C['file']

            safe = display[:cols]

            if real_idx == self.selected_index:
                pad = " " * max(0, cols - len(safe))
                line = f"{C['selected']}{safe}{pad}{C['reset']}"
            else:
                pad = " " * max(0, cols - len(safe))
                line = f"{color}{safe}{C['reset']}{pad}"

            out.append(line)

        while len(out) < rows - 2:
            out.append(" " * cols)

        item = self._get_selected()
        if item:
            name, is_dir, ftype = item
            detail = f"[{ftype}]" if not is_dir else "[dir]"
            status = f" Path: {self.current_dir} | {name} {detail} "
        else:
            status = f" Path: {self.current_dir} "
        out.append(f"{C['status']}{status[:cols].ljust(cols)}{C['reset']}")

        footer = " ↑↓:Nav  Enter:Open  F5:Copy  F6:Rename  F8:Del  F10:Quit "
        out.append(f"{C['footer']}{footer.center(cols)[:cols]}{C['reset']}")

        write_screen(self.screen, out)

    def _process_command(self, cmd):
        if cmd == 'exit':
            self.running = False
            return

        if isinstance(cmd, tuple) and cmd[0] == 'open_file':
            _, filepath, ftype = cmd

            try:
                self.screen.stop()
            except:
                pass

            if ftype == 'image':
                app = ImageViewer(filepath)
                app.run()
            else:
                app = TextEditor(filepath)
                app.run()

            try:
                self.screen.start()
                self.screen.set_terminal_properties(colors=256)
            except:
                pass

            self._update_file_list()
            self._redraw()

    def run(self):
        try:
            self.screen.start()
            self.screen.set_terminal_properties(colors=256)
            self._redraw()

            hook_ref = keyboard.hook(self._on_key)

            while self.running:
                try:
                    cmd = self.cmd_queue.get(timeout=0.05)
                    self._process_command(cmd)
                except queue.Empty:
                    pass

        except KeyboardInterrupt:
            pass
        finally:
            try:
                keyboard.unhook(hook_ref)
            except:
                pass
            try:
                self.screen.stop()
            except:
                pass
            print(C['reset'], end='')
def start():
    if os.name != 'nt' and os.geteuid() != 0:
        print("=" * 60)
        print(" autoRe File Maneger")
        print("=" * 60)
        print()
        print(" ОШИБКА: Требуется запуск от имени root (sudo).")
        print()
        print(f" Используйте: sudo python3 {sys.argv[0]}")
        print()
        sys.exit(1)

    try:
        fm = AutoReFileManager()
        fm.run()
    except Exception as e:
        print(f"\nКритическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if os.name != 'nt' and os.geteuid() != 0:
        print("=" * 60)
        print(" autoRe File Maneger")
        print("=" * 60)
        print()
        print(" ОШИБКА: Требуется запуск от имени root (sudo).")
        print()
        print(f" Используйте: sudo python3 {sys.argv[0]}")
        print()
        sys.exit(1)

    try:
        fm = AutoReFileManager()
        fm.run()
    except Exception as e:
        print(f"\nКритическая ошибка: {e}")
        sys.exit(1)