import os
import shutil
import glob
import time
import hashlib
import secrets
import platform
import sys
import asyncio

# Ленивые импорты - загружаем только когда нужны
end = True
pygame = None
cpuinfo = None
psutil = None
py7zr = None
tarfile = None
rarfile = None
RAR_SUPPORT = False

try:
    from pyterappeng import core
except ImportError:
    core = None

version = 'autoRE pcholhelper build from 26.7.1'
maindir = os.getcwd()

# Глобальные флаги
onefile = True
autostart_mode = False
nosounds = True


def resource_path(relative_path):
    """ 
    Получает абсолютный путь к ресурсу. 
    Работает как для обычной разработки, так и для PyInstaller (--onefile).
    """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def _get_pygame():
    """Ленивая загрузка pygame."""
    global pygame
    if pygame is None:
        import pygame as _pg
        pygame = _pg
    return pygame

def _get_cpuinfo():
    """Ленивая загрузка cpuinfo."""
    global cpuinfo
    if cpuinfo is None:
        import cpuinfo as _ci
        cpuinfo = _ci
    return cpuinfo

def _get_psutil():
    """Ленивая загрузка psutil."""
    global psutil
    if psutil is None:
        import psutil as _ps
        psutil = _ps
    return psutil

def _get_py7zr():
    """Ленивая загрузка py7zr."""
    global py7zr
    if py7zr is None:
        import py7zr as _p7
        py7zr = _p7
    return py7zr

def _get_tarfile():
    """Ленивая загрузка tarfile."""
    global tarfile
    if tarfile is None:
        import tarfile as _tf
        tarfile = _tf
    return tarfile

def _get_rarfile():
    """Ленивая загрузка rarfile."""
    global rarfile, RAR_SUPPORT
    if rarfile is None:
        try:
            import rarfile as _rf
            rarfile = _rf
            RAR_SUPPORT = True
        except ImportError:
            RAR_SUPPORT = False
            print('\033[1;31mOps! Rar support offed(\nFor fix it try this:\n\033[0mpip install rarfile')
    return rarfile


class shell():
    debug = False
    commands = [
        'pass', 'echo', 'cd', 'ls', 'perup', 'perdown', 'clear',
        'rd', 'wr', 'rm', 'mkd', 'rmd', '!', 'exec', 'time',
        'clock', 'phs', 'api', 'tsl', 'tsk', 'cp', 'user',
        'alias', 'chlen', 'mod', 'whoami', 'pwd', 'playsound',
        'phinstall', 'zip', 'mv', 'sysinfo', 'phpm', 'help', 'exit'
    ]
    @staticmethod
    async def ph_install():
        try:
            print(f'Welcome to the Pcholhelper {version} installer!')
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, input, 'Press any key to continue...\n')
            if core is None:
                print("pyterappeng not installed")
                return
            core.create_lines(3)
            core.line1 = "Select language/Выберите Язык"
            core.line2 = "1. English/English"
            core.line3 = "2. Russian/Русский"
            core.update()

            key = core.get_key()
            while key != '1' and key != '2':
                key = core.get_key()

            if key == '1':
                path_for_install = await loop.run_in_executor(None, input, f'Enter path to install PcholHelper {version}: ')
            elif key == '2':
                path_for_install = await loop.run_in_executor(None, input, f'Введите путь для установки PcholHelper {version}: ')
        except KeyboardInterrupt:
            pass

    @staticmethod
    @staticmethod
    @staticmethod
    async def phpm():
        """Менеджер пакетов PcholHelper (поддержка .phpmf как 7z)"""
        print('Welcome to the PcholHelper package manager')
        loop = asyncio.get_running_loop()
        
        while True:
            try:
                how = await loop.run_in_executor(None, input, 'phpm> ')
                how = how.strip()
                
                if not how:
                    continue
                    
                d = how.split(' ')
                cd = d[0]
                
                if cd == 'exit':
                    break
                elif cd == 'install':
                    if len(d) < 2:
                        print("Usage: install [package_name]")
                        continue
                        
                    pkg_name = d[1]
                    archive_file = f'{pkg_name}.phpmf'
                    
                    # 1. Проверяем наличие архива
                    if not os.path.exists(archive_file):
                        print(f"\033[1;31mError: File {archive_file} not found\033[0m")
                        continue

                    print(f"Installing {pkg_name} from {archive_file}...")
                    
                    # 2. Распаковка 7z архива
                    p7z = _get_py7zr() # Используем вашу ленивую загрузку
                    try:
                        with p7z.SevenZipFile(archive_file, mode='r') as archive:
                            archive.extractall('.') 
                    except Exception as e:
                        print(f"\033[1;31mFailed to extract 7z archive: {e}\033[0m")
                        continue

                    # 3. Подготовка папки apps/
                    if not os.path.exists('apps'):
                        os.makedirs('apps')
                    
                    source_dir = pkg_name
                    dest_dir = os.path.join('apps', pkg_name)

                    # Если папка уже существует, удаляем её во избежание ошибок перемещения
                    if os.path.exists(dest_dir):
                        import shutil
                        try:
                            shutil.rmtree(dest_dir)
                        except Exception as e:
                            print(f"\033[1;31mCould not remove old installation: {e}\033[0m")
                            continue

                    # 4. Перемещение распакованной папки в apps/
                    try:
                        os.rename(source_dir, dest_dir)
                    except OSError:
                        import shutil
                        shutil.move(source_dir, dest_dir)

                    # 5. Чтение и парсинг project.cfg
                    cfg_path = os.path.join(dest_dir, 'project.cfg')
                    if os.path.exists(cfg_path):
                        config_data = {}
                        with open(cfg_path, 'r', encoding='utf-8') as f:
                            for line in f:
                                line = line.strip()
                                # Пропускаем пустые строки и секции [PROJECT]
                                if not line or line.startswith('['):
                                    continue
                                
                                if '=' in line:
                                    key, value = line.split('=', 1)
                                    config_data[key.strip()] = value.strip()

                        # Извлекаем данные согласно вашему формату
                        proj_name = config_data.get('name', 'Unknown Project')
                        proj_com = config_data.get('comand', '') # Обратите внимание: у вас "comand", а не "command"
                        proj_main = config_data.get('mainfile', 'main.py')
                        
                        # Формируем путь к главному файлу
                        proj_mafi = f'apps/{pkg_name}/{proj_main}'

                        s = await loop.run_in_executor(None, input, f'Do you want to install "{proj_name}"? (y/n): ')
                        
                        if s.lower().startswith('y'):
                            # Запись в общий конфиг установленных приложений
                            with open('apps/appconfig.cfg', 'a', encoding='utf-8') as pdf:
                                # Формат: Имя=Команда=ПутьКФайлу
                                pdf.write(f'{proj_name}={proj_com}={proj_mafi}\n')
                            print(f"\033[1;32mSuccessfully installed {proj_name}!\033[0m")
                        else:
                            print("Installation cancelled.")
                            # Можно добавить удаление папки, если пользователь отказался
                            
                    else:
                        print(f"\033[1;31mError: project.cfg not found in {dest_dir}\033[0m")

                else:
                    print(f"Unknown command: {cd}")
                    
            except KeyboardInterrupt:
                print("\nExiting phpm...")
                break
            except Exception as e:
                print(f"\033[1;31mUnexpected error in phpm: {e}\033[0m")
    @staticmethod
    def playsound(path_or_name_sound: str, volume: float = 1.0):
        """Play a sound file using pygame. Ленивая инициализация."""
        if autostart_mode or nosounds:
            return

        pg = _get_pygame()
        if not pg.mixer.get_init():
            try:
                pg.mixer.init()
            except Exception as e:
                shell.write_log(f"Failed to init pygame mixer: {e}")
                return

        shell.write_log(f'Try to play sound file: {path_or_name_sound} with volume {volume}')
        try:
            if not os.path.isfile(path_or_name_sound):
                path_or_name_sound = resource_path(path_or_name_sound)
            if not os.path.isfile(path_or_name_sound):
                raise FileNotFoundError(f"Sound file not found: {path_or_name_sound}")

            shell.write_log(f'File {path_or_name_sound} found. Loading...')
            pg.mixer.music.load(path_or_name_sound)
            pg.mixer.music.play()
            pg.mixer.music.set_volume(volume)
            shell.write_log('Successfully playing sound file!')
        except Exception as e:
            print(f'\033[1;31mError playing sound: {e}\033[0m')
            shell.write_log(f'Error to play sound: {e}')

    @staticmethod
    def archive_file(source: str, archive_name: str, format_type: str):
        """Универсальный метод архивации для всех форматов"""
        shell.write_log(f"Starting archive: {source} -> {archive_name} (format: {format_type})")

        if not os.path.exists(source):
            error_msg = f"Error: Source '{source}' not found."
            print(f"\033[1;31m{error_msg}\033[0m")
            shell.write_log(error_msg)
            return False

        try:
            format_type = format_type.lower()
            extensions = {
                '7z': '.7z', 'zip': '.zip', 'targz': '.tar.gz',
                'tarxz': '.tar.xz', 'tarbz2': '.tar.bz2', 'tar': '.tar', 'rar': '.rar'
            }

            if format_type not in extensions:
                error_msg = f"Unsupported format: {format_type}"
                print(f"\033[1;31m{error_msg}\033[0m")
                shell.write_log(error_msg)
                return False

            expected_ext = extensions[format_type]
            if not archive_name.endswith(expected_ext):
                archive_name += expected_ext
                shell.write_log(f"Added extension to archive name: {archive_name}")

            shell.write_log(f"Creating archive: {archive_name}")

            if format_type == '7z':
                p7z = _get_py7zr()
                with p7z.SevenZipFile(archive_name, mode='w') as archive:
                    archive.writeall(source, arcname=os.path.basename(source))
            elif format_type == 'zip':
                import zipfile
                with zipfile.ZipFile(archive_name, 'w', zipfile.ZIP_DEFLATED) as archive:
                    if os.path.isfile(source):
                        archive.write(source, arcname=os.path.basename(source))
                    else:
                        for root, dirs, files in os.walk(source):
                            for file in files:
                                file_path = os.path.join(root, file)
                                arcname = os.path.relpath(file_path, os.path.dirname(source))
                                archive.write(file_path, arcname=arcname)
            elif format_type in ['targz', 'tarxz', 'tarbz2', 'tar']:
                tf = _get_tarfile()
                mode_map = {'targz': 'w:gz', 'tarxz': 'w:xz', 'tarbz2': 'w:bz2', 'tar': 'w'}
                with tf.open(archive_name, mode_map[format_type]) as archive:
                    archive.add(source, arcname=os.path.basename(source))
            elif format_type == 'rar':
                _get_rarfile()
                if not RAR_SUPPORT:
                    error_msg = "RAR support not available. Install rarfile: pip install rarfile"
                    print(f"\033[1;31m{error_msg}\033[0m")
                    shell.write_log(error_msg)
                    return False
                error_msg = "RAR creation not supported. Use 7z or zip instead."
                print(f"\033[1;31m{error_msg}\033[0m")
                shell.write_log(error_msg)
                return False

            success_msg = f"Success: Created {archive_name}"
            print(f"\033[1;32m{success_msg}\033[0m")
            shell.write_log(success_msg)
            return True
        except Exception as e:
            error_msg = f"Error creating archive: {e}"
            print(f"\033[1;31m{error_msg}\033[0m")
            shell.write_log(error_msg)
            return False

    @staticmethod
    def extract_archive(archive_name: str, output_dir: str = '.'):
        """Универсальный метод распаковки (определяет формат по расширению)"""
        shell.write_log(f"Starting extraction: {archive_name} -> {output_dir}")

        if not os.path.exists(archive_name):
            error_msg = f"Error: Archive '{archive_name}' not found."
            print(f"\033[1;31m{error_msg}\033[0m")
            shell.write_log(error_msg)
            return False

        try:
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
                shell.write_log(f"Created output directory: {output_dir}")

            archive_lower = archive_name.lower()

            if archive_lower.endswith('.7z'):
                p7z = _get_py7zr()
                with p7z.SevenZipFile(archive_name, mode='r') as archive:
                    archive.extractall(path=output_dir)
            elif archive_lower.endswith('.zip'):
                import zipfile
                with zipfile.ZipFile(archive_name, 'r') as archive:
                    archive.extractall(path=output_dir)
            elif archive_lower.endswith(('.tar.gz', '.tgz')):
                tf = _get_tarfile()
                with tf.open(archive_name, 'r:gz') as archive:
                    archive.extractall(path=output_dir)
            elif archive_lower.endswith(('.tar.xz', '.txz')):
                tf = _get_tarfile()
                with tf.open(archive_name, 'r:xz') as archive:
                    archive.extractall(path=output_dir)
            elif archive_lower.endswith(('.tar.bz2', '.tbz2')):
                tf = _get_tarfile()
                with tf.open(archive_name, 'r:bz2') as archive:
                    archive.extractall(path=output_dir)
            elif archive_lower.endswith('.tar'):
                tf = _get_tarfile()
                with tf.open(archive_name, 'r') as archive:
                    archive.extractall(path=output_dir)
            elif archive_lower.endswith('.rar'):
                rf = _get_rarfile()
                if not RAR_SUPPORT:
                    error_msg = "RAR support not available. Install rarfile: pip install rarfile"
                    print(f"\033[1;31m{error_msg}\033[0m")
                    shell.write_log(error_msg)
                    return False
                with rf.RarFile(archive_name, 'r') as archive:
                    archive.extractall(path=output_dir)
            else:
                error_msg = f"Unsupported archive format: {archive_name}"
                print(f"\033[1;31m{error_msg}\033[0m")
                shell.write_log(error_msg)
                return False

            success_msg = f"Success: Extracted to {output_dir}"
            print(f"\033[1;32m{success_msg}\033[0m")
            shell.write_log(success_msg)
            return True
        except Exception as e:
            error_msg = f"Error extracting archive: {e}"
            print(f"\033[1;31m{error_msg}\033[0m")
            shell.write_log(error_msg)
            return False

    @staticmethod
    def get_time_and_date(): return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    @staticmethod
    def write_log(log_text: str = 'writed in the logs without text'):
        """Write log entry to log file. Пропускает запись в режиме автостарта для скорости."""
        # Вывод логов в консоль, если включен режим отладки
        if shell.debug:
            print(f"\033[1;36m[DEBUG {shell.get_time_and_date()}] {log_text}\033[0m")
            
        if onefile or autostart_mode:
            return
        try:
            with open('lastles.log', 'a') as log_file:
                log_file.write(f'[{shell.get_time_and_date()}]: {log_text}\n')
        except Exception as e:
            print(f"Error writing to log: {e}")

    @staticmethod
    async def informer():
        print('===== Pchollehper system informer =====')
        print(f'\033[1mPcholhelper version: \033[0m{version}')
        await sysi.update_sysi()
        print(f"CPU: {sysi.cpu_model}")
        print(f"Cores: {sysi.cores_physical} physical / {sysi.cores_logical} logical")
        print(f"CPU Load: {sysi.cpu_load}%")
        print(f"Platform: {sysi.plat} {sysi.plat_realese}")
        print(f"Platform version: {sysi.plat_ver}")
        print(f"Architecture: {sysi.arch}")
        print(f"Python: {sysi.pyver}")
        print(f"Current file: {sysi.current_file_filename}")

    @staticmethod
    async def start_phs(mod_name):
        """Interpreter for .phs scripts."""
        shell.write_log(f"Starting .phs script: {mod_name}")
        try:
            if not os.path.exists(mod_name):
                error_msg = f'Error: File "{mod_name}" not found.'
                print(f'\033[1;31m{error_msg}\033[0m')
                shell.write_log(error_msg)
                return

            with open(mod_name, 'r', encoding='utf-8') as h:
                lines = h.readlines()

            shell.write_log(f"Loaded {len(lines)} lines from {mod_name}")

            lc = 0
            while lc < len(lines):
                line = lines[lc].strip()
                if not line:
                    lc += 1
                    continue

                shell.write_log(f"Processing line {lc}: {line}")

                if line.startswith('jmp'):
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            target_line = int(parts[1])
                            if 0 <= target_line < len(lines):
                                shell.write_log(f"Jumping to line {target_line}")
                                lc = target_line
                                continue
                            else:
                                error_msg = f"Error: jmp target {target_line} out of range"
                                print(f'\033[1;31m{error_msg}\033[0m')
                                shell.write_log(error_msg)
                        except ValueError:
                            error_msg = f'Error: invalid jmp target "{parts[1]}"'
                            print(f'\033[1;31m{error_msg}\033[0m')
                            shell.write_log(error_msg)
                    else:
                        error_msg = "Error: jmp requires line number"
                        print(f'\033[1;31m{error_msg}\033[0m')
                        shell.write_log(error_msg)
                    lc += 1
                    continue

                await shell.command(line)
                lc += 1

        except Exception as e:
            error_msg = f"Error in start_phs: {e}"
            print(f"\033[1;31m{error_msg}\033[0m")
            shell.write_log(error_msg)

    @staticmethod
    def hash_(layers, data, salt=""):
        """Hashes string with salt addition specified number of times."""
        shell.write_log(f"Hashing data with {layers} layers and salt")
        salted_data = data + salt
        if layers <= 0:
            result = hashlib.sha256(salted_data.encode('utf-8')).hexdigest()
            shell.write_log(f"Hash result (no layers): {result[:16]}...")
            return result

        byte_data = salted_data.encode('utf-8')
        for i in range(layers):
            hash_object = hashlib.sha256(byte_data)
            byte_data = hash_object.hexdigest().encode('utf-8')
            if i % 100000 == 0 and layers > 100000:
                shell.write_log(f"Hashing progress: {i}/{layers} iterations")

        result = byte_data.decode('utf-8')
        shell.write_log(f"Hash completed with {layers} layers")
        return result

    @staticmethod
    def clear_screen():
        """Cross-platform screen clearing."""
        shell.write_log("Clearing screen")
        command = 'cls' if platform.system().lower() == 'windows' else 'clear'
        os.system(command)

    @staticmethod
    async def reg():
        """Register new user."""
        if onefile:
            print("\033[1;31mUser registration is disabled in onefile mode.\033[0m")
            return

        shell.write_log("Starting user registration")
        loop = asyncio.get_running_loop()
        
        name = await loop.run_in_executor(None, input, 'Username: ')
        name = name.strip()
        shell.write_log(f"Registration attempt for username: {name}")

        password = await loop.run_in_executor(None, input, 'Password: ')
        shell.write_log("Password entered")

        shell.clear_screen()
        password_correct = await loop.run_in_executor(None, input, 'Confirm password: ')
        shell.write_log("Password confirmation entered")

        if password != password_correct:
            error_msg = "Error: Passwords do not match."
            print(error_msg)
            shell.write_log(error_msg)
            return

        birthday = await loop.run_in_executor(None, input, 'Birthday: ')
        shell.write_log(f"Birthday entered: {birthday}")

        user_salt = secrets.token_hex(16)
        shell.write_log("Generated user salt")

        hashed_password = shell.hash_(1000000, password, salt=user_salt)
        shell.write_log("Password hashed successfully")

        name_hash = shell.hash_(100, name)
        shell.write_log("Name hashed successfully")

        user_filename = f"{name_hash}.phu"
        shell.write_log(f"User filename: {user_filename}")

        try:
            with open(user_filename, 'x', encoding='utf-8') as ht:
                ht.write(f'name:{name_hash}\n')
                ht.write(f'salt={user_salt}\n')
                ht.write(f'pwd={hashed_password}\n')
                ht.write(f'birthday={birthday}\n')
            success_msg = "\nRegistration successful!"
            print(success_msg)
            shell.write_log(f"User registered successfully: {name}")
        except FileExistsError:
            error_msg = "\nError: User with his name already exists."
            print(error_msg)
            shell.write_log(f"Registration failed - user exists: {name}")

    @staticmethod
    async def command(com_line):
        """Execute shell command."""
        shell.write_log(f"Executing command: {com_line}")
        try:
            line = com_line.strip()
            if not line:
                shell.write_log("Empty command received")
                return
            com = line.split(' ')
            cmd = com[0].lower()
            shell.write_log(f"Parsed command: {cmd}")

            if cmd == 'phinstall':
                await shell.ph_install()
            elif cmd == 'pass':
                pass
            elif cmd == 'help':
                print("""\033[1;36m=== PcholHelper Commands ===\033[0m
  \033[1mGeneral:\033[0m
    help        - Show this help
    echo [text] - Print text
    clear       - Clear screen
    pass        - Do nothing
    exec [code] - Execute Python code
    ! [cmd]     - Run system command
    time/clock  - Show current time

  \033[1mFilesystem:\033[0m
    ls [dir]    - List directory
    cd [dir]    - Change directory
    pwd         - Print working directory
    rd [file]   - Read file
    wr [file]   - Write to file
    cp [src] [dst] - Copy file
    mv [src] [dst] - Move/rename
    rm [pattern] - Remove files
    mkd [dir]   - Create directory
    rmd [dir]   - Remove directory

  \033[1mArchives:\033[0m
    zip [fmt] zip [src] [out]   - Create archive (7z/zip/tar)
    zip [fmt] unzip [arc] [out] - Extract archive

  \033[1mSystem:\033[0m
    sysinfo     - Show system information
    whoami      - Show current user
    user create - Register new user
    tsl         - List processes
    tsk [name]  - Kill process
    perup       - Grant root privileges
    perdown     - Revoke root privileges

  \033[1mPcholHelper:\033[0m
    phs [file]  - Run .phs script
    mod [file]  - Run .phs script
    phpm        - Package manager
    phinstall   - Install PcholHelper
    alias list  - Show aliases
    alias new [n] [cmd] - Create alias
    playsound [file] - Play sound file""")
            elif cmd == 'echo':
                if len(com) > 1:
                    output = ' '.join(com[1:])
                    print(output)
                else:
                    print()
            elif cmd == 'exit':
                global end
                end = False
            elif cmd == 'phpm':
                await shell.phpm()
            elif cmd == 'cd':
                if len(com) > 1:
                    target_dir = com[1]
                    try:
                        os.chdir(target_dir)
                    except PermissionError:
                        print('\033[1;31mPermission denied\033[0m')
                    except FileNotFoundError:
                        print('\033[1;31mDirectory not found\033[0m')
            elif cmd == 'ls':
                target = com[1] if len(com) > 1 else './'
                try:
                    files = os.listdir(target)
                    print('\n'.join(files))
                except FileNotFoundError:
                    print('\033[1;31mDirectory not found\033[0m')
            elif cmd == 'perup':
                main.root = True
                print("Root privileges granted.")
            elif cmd == 'perdown':
                main.root = False
                print("Root privileges revoked.")
            elif cmd == '!':
                if len(com) > 1:
                    os.system(' '.join(com[1:]))
            elif cmd == 'clear':
                shell.clear_screen()
            elif cmd == 'rd':
                if len(com) > 1 and os.path.exists(com[1]):
                    filename = com[1]
                    with open(filename, 'r', encoding='utf-8') as read_:
                        content = read_.read()
                        if shell.debug:
                            print(repr(content))
                        print(content)
            elif cmd == 'cp':
                if len(com) > 2:
                    shutil.copy(com[1], com[2])
            elif cmd == "tsl":
                ps = _get_psutil()
                print("-" * 80)
                current_user = ps.Process().username()
                for p in ps.process_iter(['pid', 'name', 'username']):
                    try:
                        if p.info['username'] == current_user and p.info['pid'] >= 1000:
                            print(f"{p.info['pid']}\t{p.info['name']}")
                    except (ps.NoSuchProcess, ps.AccessDenied):
                        pass
            elif cmd == "tsk":
                ps = _get_psutil()
                if len(com) > 1:
                    target_proc = com[1]
                    killed = False
                    for proc in ps.process_iter(['name']):
                        if proc.info['name'] == target_proc:
                            proc.terminate()
                            killed = True
                    if not killed:
                        print(f"Process '{target_proc}' not found.")
            elif cmd == 'user':
                if onefile:
                    print("\033[1;31mUser management is disabled in onefile mode.\033[0m")
                    return
                if len(com) > 1 and com[1] == 'create':
                    await shell.reg()
                else:
                    await shell.reg()
            elif cmd == 'wr':
                if len(com) > 1 and os.path.exists(com[1]):
                    filename = com[1]
                    text_to_write = line.split(f'wr {filename} ', 1)
                    if len(text_to_write) > 1:
                        with open(filename, 'w', encoding='utf-8') as wr_:
                            wr_.write(text_to_write[1])
            elif cmd == 'mv':
                if len(com) > 2 and os.path.exists(com[1]):
                    os.rename(com[1], com[2])
            elif cmd == 'rmd':
                if len(com) > 1 and os.path.exists(com[1]):
                    shutil.rmtree(com[1])
            elif cmd == 'exec':
                exec(com_line.split('exec ')[1])
            elif cmd == 'mkd':
                if len(com) > 1:
                    dirname = com[1]
                    if not os.path.exists(dirname):
                        os.mkdir(dirname)
                    else:
                        print('\033[1;31mDirectory already exists\033[0m')
            elif cmd == 'rm':
                if len(com) > 1:
                    pattern = com[1]
                    matches = glob.glob(pattern)
                    if matches:
                        for file in matches:
                            try:
                                if os.path.isfile(file):
                                    os.remove(file)
                                else:
                                    print(f'\033[1;31m{file} is a directory.\nUse: rmd [directory_name]\033[0m')
                            except Exception as e:
                                print(f"Error removing {file}: {e}")
            elif cmd == 'zip':
                if len(com) < 4:
                    print("Usage: zip [7z|zip|targz|tarxz|tarbz2|tar|rar] [zip|unzip] [source/archive] [output_name]")
                    return

                format_type = com[1].lower()
                action = com[2].lower()
                source_or_archive = com[3]
                output = com[4] if len(com) > 4 else None

                if action == 'zip':
                    if output:
                        archive_name = output
                    else:
                        base_name = os.path.basename(source_or_archive)
                        if '.' in base_name:
                            base_name = base_name.rsplit('.', 1)[0]
                        archive_name = f"{base_name}.{format_type}"
                    shell.archive_file(source_or_archive, archive_name, format_type)
                elif action == 'unzip':
                    output_dir = output if output else '.'
                    shell.extract_archive(source_or_archive, output_dir)
                else:
                    print(f"\033[1;31mUnknown action: {action}. Use 'zip' or 'unzip'\033[0m")
            elif cmd == 'api':
                if len(com) > 1:
                    api_file = com[1]
                    if os.path.exists(api_file):
                        os.system(f'python3 {api_file}')
                    else:
                        print('File not found')
            elif cmd == 'phs':
                if len(com) > 1:
                    await shell.start_phs(com[1])
            elif cmd == 'alias':
                if onefile:
                    print("\033[1;31mAliases are disabled in onefile mode.\033[0m")
                    return
                alias_file = 'aliases.7z'
                if len(com) > 1:
                    if com[1] == "list":
                        if os.path.exists(alias_file):
                            with open(alias_file, 'r', encoding='utf-8') as aliases:
                                print('\n'.join(aliases.readlines()))
                        else:
                            print("No aliases found.")
                    elif com[1] == 'new' and len(com) > 3:
                        alias_name = com[2]
                        alias_target = ' '.join(com[3:])
                        with open(alias_file, 'a', encoding='utf-8') as aliases:
                            aliases.write(f'{alias_name} > {alias_target}\n')
                        print(f"Alias '{alias_name}' created.")
                    else:
                        print("Usage: alias new [name] [command]  OR  alias list")
            elif cmd == 'mod':
                if len(com) > 1:
                    await shell.start_phs(com[1])
                else:
                    print("Usage: mod [filename.phs]")
            elif cmd == 'whoami':
                print(main.username)
            elif cmd == 'pwd':
                print(os.getcwd())
            elif cmd == 'sysinfo':
                await shell.informer()
            elif cmd == 'playsound':
                if len(com) > 1:
                    shell.playsound(com[1])
            elif cmd == 'phpm':
                shell.phpm
            else:
                if cmd not in shell.commands:
                    alias_executed = False
                    if not onefile:
                        alias_file = 'aliases.7z'
                        if os.path.exists(alias_file):
                            with open(alias_file, 'r', encoding='utf-8') as aliases:
                                for alias_line in aliases:
                                    alias_line = alias_line.strip()
                                    if not alias_line or ' > ' not in alias_line:
                                        continue
                                    parts = alias_line.split(' > ', 1)
                                    if len(parts) == 2 and parts[0] == cmd:
                                        target_cmd = parts[1]
                                        if len(com) > 1:
                                            target_cmd += ' ' + ' '.join(com[1:])
                                        await shell.command(target_cmd)
                                        alias_executed = True
                                        break

                    if not alias_executed:
                        print(f"\033[1;31mCommand not found: {cmd}\033[0m")

        except Exception as error_log_:
            print(f'\033[1;31mError: {error_log_}\033[0m')
            shell.write_log(f"Command execution error: {error_log_}")


class main:
    username = 'root'
    pcname = 'pc'
    root = False

    @staticmethod
    def init_files():
        """Инициализация необходимых файлов (только если не onefile)."""
        if onefile:
            return
        if not os.path.exists('autostart.phs'):
            shell.write_log("Creating autostart.phs file")
            with open('autostart.phs', 'x'):
                pass

        if not os.path.exists('aliases.7z'):
            shell.write_log("Creating aliases.7z file")
            with open('aliases.7z', 'x'):
                pass

    @staticmethod
    async def shell_loop():
        """Main shell loop."""
        global end
        shell.write_log("Starting shell loop")
        
        if not onefile:
            await shell.start_phs('autostart.phs')

        loop = asyncio.get_running_loop()

        while end:
            if not onefile and os.path.exists('config.7z'):
                try:
                    with open('config.7z', 'r', encoding='utf-8') as s:
                        for line in s:
                            if line.startswith('pcname='):
                                old_pcname = main.pcname
                                main.pcname = line.strip().split('=', 1)[1]
                                if old_pcname != main.pcname:
                                    shell.write_log(f"PC name updated: {old_pcname} -> {main.pcname}")
                except Exception as e:
                    shell.write_log(f"Error reading config: {e}")

            sts = '#' if main.root else "$"
            current_dir = os.getcwd()

            try:
                prompt = f'\033[1;32m{main.username}@{main.pcname}\033[0m:\033[1;34m{current_dir}\033[0m{sts} '
                
                # Неблокирующий ввод через executor
                coman = await loop.run_in_executor(None, input, prompt)
                coman = coman.strip()
                
                shell.write_log(f"User input: {coman if coman else '(empty)'}")
                
                # УБРАЛИ await sysi.update_sysi() отсюда, чтобы не было задержек перед каждой командой
                
                if onefile:
                    await shell.command('rm lastles.log')
            except (EOFError, KeyboardInterrupt):
                print("\nExiting shell...")
                shell.write_log("Exiting shell...")
                break

            if coman == 'exit':
                print("Exiting shell...")
                shell.write_log("Exiting shell")
                end = False
            elif coman == 'mod menu':
                sa = await loop.run_in_executor(None, input, 'mod name\n>>> ')
                sa = sa.strip()
                if sa:
                    await shell.start_phs(sa)
            elif coman:
                await shell.command(coman)

    @staticmethod
    async def login():
        """Authenticate existing user."""
        shell.write_log("Starting login process")
        loop = asyncio.get_running_loop()
        
        name = await loop.run_in_executor(None, input, 'Username: ')
        name = name.strip()
        password = await loop.run_in_executor(None, input, 'Password: ')

        name_hash = shell.hash_(100, name)
        user_filename = f"{name_hash}.phu"

        if not os.path.exists(user_filename):
            print("\nError: Invalid username or password.")
            return

        user_data = {}
        with open(user_filename, 'r', encoding='utf-8') as ht:
            for line in ht:
                if '=' in line:
                    key, val = line.strip().split('=', 1)
                    user_data[key] = val

        user_salt = user_data.get('salt')
        saved_password_hash = user_data.get('pwd')

        if not user_salt or not saved_password_hash:
            print("\nError: Corrupted user file.")
            return

        input_password_hash = shell.hash_(1000000, password, salt=user_salt)

        if input_password_hash == saved_password_hash:
            shell.clear_screen()
            print(f"Welcome, {name}!")
            main.username = name
            await main.shell_loop()
        else:
            print("\nError: Invalid username or password.")

    @staticmethod
    async def auth():
        """Authentication and initial setup."""
        shell.write_log("Starting authentication process")

        main.init_files()

        if onefile or main.root:
            main.username = 'root'
            main.root = True
            await main.shell_loop()
            return

        loop = asyncio.get_running_loop()

        while True:
            if not os.path.exists('config.7z'):
                print('Welcome to initial setup.\nSystem did not find configuration file "config.7z"')
                pcnam = await loop.run_in_executor(None, input, 'Computer name: ')
                pcnam = pcnam.strip()
                sunn = await loop.run_in_executor(None, input, 'Administrator username: ')
                sunn = sunn.strip()

                with open('config.7z', 'w+', encoding='utf-8') as fik:
                    fik.write(f'config!\npcname={pcnam}\nsun={sunn}\nfis=True\n')
                main.pcname = pcnam
                main.username = sunn

            phu_files = glob.glob('users/*.phu') + glob.glob('*.phu')
            if not phu_files:
                print("No users found. Registration required.")
                await shell.reg()
            else:
                await main.login()
                break


class sysi():
    """
    Класс для хранения системной информации.
    Атрибуты инициализируются лениво.
    """
    pyver = ''
    plat_ver = ''
    plat = ''
    plat_realese = ''
    arch = ''
    cpu_model = ''
    cores_physical = 0
    cores_logical = 0
    cpu_load = 0.0
    current_file = ''
    current_file_filename = ''
    _initialized = False

    @staticmethod
    async def update_sysi():
        """Обновление системной информации."""
        try:
            ps = _get_psutil()
            ci = _get_cpuinfo()
            
            sysi.pyver = platform.python_version()
            sysi.plat_ver = platform.version()
            sysi.plat = platform.platform()
            sysi.plat_realese = platform.release()
            sysi.arch = platform.processor()
            
            # Кэшируем модель CPU, так как py-cpuinfo работает медленно
            if not sysi.cpu_model:
                sysi.cpu_model = ci.get_cpu_info().get('brand_raw', 'Unknown')
                
            sysi.cores_physical = ps.cpu_count(logical=False) or 0
            sysi.cores_logical = ps.cpu_count(logical=True) or 0
            sysi.cpu_load = ps.cpu_percent(interval=None)
            sysi.current_file = __file__
            
            try:
                sysi.current_file_filename = __file__.split(f'{maindir}/')[1]
            except (IndexError, AttributeError):
                sysi.current_file_filename = os.path.basename(__file__)
            
            sysi._initialized = True
        except Exception as e:
            shell.write_log(f"Error in update_sysi: {e}")


# ===================== MAIN =====================
if __name__ == "__main__":
    # 1. Парсим аргументы командной строки
    autostart_command = None
    autostart_exit = False

    try:
        if '--onefile' in sys.argv:
            onefile = True
        if '--root' in sys.argv:
            main.root = True
        if '--nosounds' in sys.argv:
            nosounds = True

        if '--autostartex' in sys.argv:
            idx = sys.argv.index('--autostartex')
            remaining_args = sys.argv[idx + 1:]
            if remaining_args:
                autostart_command = ' '.join(remaining_args)
                autostart_exit = True
                autostart_mode = True

        elif '--autostart' in sys.argv:
            idx = sys.argv.index('--autostart')
            remaining_args = sys.argv[idx + 1:]
            if remaining_args:
                autostart_command = ' '.join(remaining_args)
                autostart_exit = False
                autostart_mode = False

    except Exception as e:
        shell.write_log(f"Error parsing arguments: {e}")

    # 2. Если есть команда автостарта - выполняем её
    if autostart_command:
        try:
            # Запуск асинхронной команды через asyncio.run
            asyncio.run(shell.command(autostart_command))
        except Exception as e:
            print(f'\033[1;31mError executing autostart command: {e}\033[0m')
            if autostart_exit:
                os._exit(1)

        if autostart_exit:
            os._exit(0)

    # 3. Полноценный запуск программы
    shell.write_log('=== Program started ===')
    shell.write_log(f"Working directory: {maindir}")
    
    # Инициализация системной информации
    asyncio.run(sysi.update_sysi())
    
    shell.write_log(f"Platform: {sysi.plat} {sysi.plat_realese}")
    shell.write_log(f'Platform version: {sysi.plat_ver}')
    shell.write_log(f"Python version: {sysi.pyver}")

    try:
        shell.playsound(resource_path('pcholhelper/sounds/start_sound.mp3'))
        # Запуск основного асинхронного цикла
        asyncio.run(main.auth())

    except Exception as e:
        error_msg = f"Fatal error: {e}"
        print(error_msg)
        shell.write_log(error_msg)
    finally:
        if not onefile:
            if not os.path.isdir('logs/'):
                os.mkdir('logs/')
            log_filename = 'lastles.log'
            timestamp = shell.get_time_and_date().replace(':', '-').replace(' ', '_')
            archive_name = f"logs/log_backup_{timestamp}.tar.gz"

            shell.write_log(f"Attempting to backup log to {archive_name}")

            try:
                if os.path.exists(log_filename) and os.path.getsize(log_filename) > 0:
                    tf = _get_tarfile()
                    with tf.open(archive_name, "w:gz") as tar:
                        tar.add(log_filename, arcname=os.path.basename(log_filename))
                    shell.write_log(f"Log archived to {archive_name}")
            except Exception as arch_err:
                shell.write_log(f"Failed to archive log: {arch_err}")

            try:
                with open(log_filename, 'w') as f:
                    pass
                shell.write_log('Log file cleared')
            except Exception as clear_err:
                print(f'\033[1;31mFailed to clear log: {clear_err}\033[0m')

        shell.write_log('=== Program ended ===')