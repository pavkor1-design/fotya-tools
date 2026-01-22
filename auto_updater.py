#!/usr/bin/env python3
"""
🚀 Система автообновления FotyaTools v2
Использует собственный API сервер на TimeWeb (без GitHub токенов)

Функции:
- Упаковка приложения в ZIP
- Загрузка на сервер TimeWeb
- Проверка обновлений
- Скачивание и установка обновлений
"""

import os
import sys
import json
import zipfile
import shutil
import tempfile
import subprocess
import requests
from datetime import datetime


def is_app_translocated() -> bool:
    """
    Проверяет, запущено ли приложение из AppTranslocation (read-only)
    Это происходит когда приложение скачано из интернета и не перемещено в Applications
    """
    app_path = os.path.dirname(os.path.abspath(__file__))
    # AppTranslocation директории содержат '/AppTranslocation/' в пути
    return '/AppTranslocation/' in app_path or app_path.startswith('/private/var/folders')


def get_real_app_path() -> str:
    """
    Возвращает реальный путь к приложению (не translocated)
    Если приложение в Applications - возвращает путь там
    """
    # Стандартные пути установки
    standard_paths = [
        '/Applications/PhotoTools.app/Contents/Frameworks',
        os.path.expanduser('~/Applications/PhotoTools.app/Contents/Frameworks'),
    ]
    
    for path in standard_paths:
        if os.path.exists(path):
            return path
    
    # Если не нашли - возвращаем текущий путь
    return os.path.dirname(os.path.abspath(__file__))


# URL API сервера
API_URL = "http://5.129.203.43:8085/api"

# Файлы для включения в сборку
INCLUDE_FILES = [
    "photo_tools.py",
    "license_manager.py",
    "login_window.py",
    "updater.py",
    "auto_updater.py",
    "requirements.txt",
    "start.command",
    "README.md",
]

# Папки для включения
INCLUDE_FOLDERS = []

# Исключения
EXCLUDE_PATTERNS = [
    "__pycache__",
    ".pyc",
    ".git",
    "test_",
    ".DS_Store",
    "license_config.json",
]


def get_app_version() -> str:
    """Получает текущую версию приложения"""
    try:
        from license_manager import APP_VERSION
        return APP_VERSION
    except:
        return "1.0.0"


def get_server_version() -> dict:
    """Получает информацию о последней версии с сервера"""
    try:
        resp = requests.get(f"{API_URL}/updates/latest", timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return {"success": False, "version": "1.0.0"}
    except Exception as e:
        print(f"❌ Ошибка получения версии: {e}")
        return {"success": False, "version": "1.0.0", "error": str(e)}


def check_for_updates(current_version: str = None) -> dict:
    """Проверяет наличие обновлений"""
    if current_version is None:
        current_version = get_app_version()
    
    try:
        resp = requests.get(f"{API_URL}/updates/check/{current_version}", timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return {"success": False, "has_update": False}
    except Exception as e:
        print(f"❌ Ошибка проверки обновлений: {e}")
        return {"success": False, "has_update": False, "error": str(e)}


def create_release_zip(version: str, output_path: str = None, base_dir: str = None) -> str:
    """
    Создаёт ZIP-архив с текущей версией приложения
    """
    if output_path is None:
        output_path = os.path.join(tempfile.gettempdir(), f"fotya_tools_v{version}.zip")
    
    if base_dir is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Создаём временную директорию для модифицированных файлов
    temp_dir = os.path.join(tempfile.gettempdir(), f"fotya_build_{version}")
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir, exist_ok=True)
    
    print(f"📦 Создание архива версии {version}...")
    print(f"   Базовая директория: {base_dir}")
    
    # Копируем license_manager.py с обновлённой версией
    license_manager_path = os.path.join(base_dir, "license_manager.py")
    if os.path.exists(license_manager_path):
        with open(license_manager_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        import re
        new_content = re.sub(
            r'APP_VERSION\s*=\s*"[^"]*"',
            f'APP_VERSION = "{version}"',
            content
        )
        
        temp_license_path = os.path.join(temp_dir, "license_manager.py")
        with open(temp_license_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print(f"   📝 APP_VERSION = \"{version}\" (в архиве)")
    
    files_added = 0
    
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Добавляем файлы
        for filename in INCLUDE_FILES:
            # Для license_manager.py используем модифицированную версию
            if filename == "license_manager.py" and os.path.exists(os.path.join(temp_dir, filename)):
                zipf.write(os.path.join(temp_dir, filename), filename)
                print(f"   ✅ {filename} (с версией {version})")
                files_added += 1
            else:
                filepath = os.path.join(base_dir, filename)
                if os.path.exists(filepath):
                    zipf.write(filepath, filename)
                    print(f"   ✅ {filename}")
                    files_added += 1
                else:
                    print(f"   ⚠️ {filename} не найден")
        
        # Добавляем папки
        for folder in INCLUDE_FOLDERS:
            folder_path = os.path.join(base_dir, folder)
            if os.path.isdir(folder_path):
                for root, dirs, files in os.walk(folder_path):
                    dirs[:] = [d for d in dirs if not any(p in d for p in EXCLUDE_PATTERNS)]
                    
                    for file in files:
                        if any(p in file for p in EXCLUDE_PATTERNS):
                            continue
                        
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, base_dir)
                        zipf.write(file_path, arcname)
                        print(f"   ✅ {arcname}")
                        files_added += 1
    
    # Очищаем временную директорию
    shutil.rmtree(temp_dir, ignore_errors=True)
    
    file_size = os.path.getsize(output_path)
    print(f"\n✅ Архив создан: {output_path}")
    print(f"   Файлов: {files_added}")
    print(f"   Размер: {file_size / 1024:.1f} KB")
    
    return output_path


def upload_update(zip_path: str, version: str, description: str = "", published_by: str = "admin") -> dict:
    """
    Загружает обновление на сервер
    """
    print(f"\n☁️ Загрузка на сервер...")
    
    if not os.path.exists(zip_path):
        return {"success": False, "message": f"Файл не найден: {zip_path}"}
    
    try:
        with open(zip_path, 'rb') as f:
            files = {'file': (os.path.basename(zip_path), f, 'application/zip')}
            data = {
                'version': version,
                'description': description,
                'published_by': published_by
            }
            
            resp = requests.post(
                f"{API_URL}/updates/publish",
                files=files,
                data=data,
                timeout=120
            )
        
        if resp.status_code == 200:
            result = resp.json()
            if result.get("success"):
                print(f"✅ Загружено успешно!")
                print(f"   URL: {result.get('download_url', 'N/A')}")
                return result
            else:
                return {"success": False, "message": result.get("message", "Неизвестная ошибка")}
        else:
            return {"success": False, "message": f"HTTP {resp.status_code}: {resp.text[:200]}"}
            
    except Exception as e:
        return {"success": False, "message": f"Ошибка: {str(e)}"}


def build_dmg(version: str, base_dir: str = None) -> str:
    """
    Собирает приложение и создаёт DMG файл
    Возвращает путь к DMG или None при ошибке
    """
    if base_dir is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    spec_file = os.path.join(base_dir, "PhotoTools.spec")
    if not os.path.exists(spec_file):
        print("⚠️ PhotoTools.spec не найден, пропускаем сборку DMG")
        return None
    
    print(f"\n🔨 Сборка приложения v{version}...")
    
    # Собираем через PyInstaller
    try:
        result = subprocess.run(
            [sys.executable, "-m", "PyInstaller", "PhotoTools.spec", "--clean", "--noconfirm"],
            cwd=base_dir, capture_output=True, text=True, timeout=300
        )
        if result.returncode != 0:
            print(f"❌ Ошибка сборки PyInstaller: {result.stderr[-500:] if result.stderr else 'unknown'}")
            return None
        print("✅ PyInstaller сборка завершена")
    except subprocess.TimeoutExpired:
        print("❌ Таймаут сборки PyInstaller")
        return None
    except Exception as e:
        print(f"❌ Ошибка PyInstaller: {e}")
        return None
    
    # Проверяем что app создан
    app_path = os.path.join(base_dir, "dist", "PhotoTools.app")
    if not os.path.exists(app_path):
        print("❌ PhotoTools.app не создан")
        return None
    
    # Создаём DMG
    dmg_name = f"PhotoTools-{version}.dmg"
    dmg_path = os.path.join(base_dir, dmg_name)
    
    # Удаляем старый DMG если есть
    if os.path.exists(dmg_path):
        os.remove(dmg_path)
    
    print(f"📦 Создание {dmg_name}...")
    try:
        result = subprocess.run(
            ["hdiutil", "create", "-volname", "PhotoTools", "-srcfolder", app_path, 
             "-ov", "-format", "UDZO", dmg_path],
            cwd=base_dir, capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            print(f"❌ Ошибка hdiutil: {result.stderr}")
            return None
        print(f"✅ DMG создан: {dmg_name}")
        return dmg_path
    except Exception as e:
        print(f"❌ Ошибка создания DMG: {e}")
        return None


def _get_repo_dir() -> str:
    """Возвращает путь к git репозиторию PhotoTools"""
    # Известные пути к репозиторию
    known_paths = [
        "/Users/andreykorushov/ai_bot/PhotoTools-Release",
        os.path.expanduser("~/ai_bot/PhotoTools-Release"),
        os.path.expanduser("~/PhotoTools-Release"),
    ]
    
    for path in known_paths:
        if os.path.exists(os.path.join(path, ".git")):
            return path
    
    # Пробуем текущую директорию
    current = os.path.dirname(os.path.abspath(__file__))
    if os.path.exists(os.path.join(current, ".git")):
        return current
    
    return None


def _log_to_file(msg: str):
    """Логирование в файл для отладки"""
    log_path = os.path.expanduser("~/phototools_publish.log")
    try:
        with open(log_path, "a") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    except:
        pass


def create_github_release(version: str, description: str = "", base_dir: str = None, build_if_missing: bool = True) -> dict:
    """
    Создаёт GitHub Release с DMG файлом (если доступен gh CLI)
    """
    try:
        _log_to_file(f"=== create_github_release v{version} ===")
        
        # Проверяем наличие gh CLI (с полными путями для macOS)
        gh_paths = ["/opt/homebrew/bin/gh", "/usr/local/bin/gh", "gh"]
        gh_cmd = None
        
        for path in gh_paths:
            try:
                result = subprocess.run([path, "--version"], capture_output=True, text=True)
                if result.returncode == 0:
                    gh_cmd = path
                    break
            except:
                continue
        
        if not gh_cmd:
            _log_to_file("ERROR: gh CLI не найден")
            print("⚠️ gh CLI не найден, GitHub Release не создан")
            return {"success": False, "message": "gh CLI не установлен"}
        
        _log_to_file(f"gh CLI: {gh_cmd}")
        
        # Определяем директорию git репозитория (важно для gh CLI!)
        repo_dir = _get_repo_dir()
        if not repo_dir:
            _log_to_file("ERROR: Git репозиторий не найден")
            print("⚠️ Git репозиторий не найден")
            return {"success": False, "message": "Git репозиторий не найден"}
        
        _log_to_file(f"Repo dir: {repo_dir}")
        
        # Для поиска DMG используем repo_dir
        if base_dir is None:
            base_dir = repo_dir
        
        # Ищем DMG файл
        dmg_file = None
        _log_to_file(f"Searching DMG in: {base_dir}")
        
        try:
            files = os.listdir(base_dir)
            _log_to_file(f"Files: {[f for f in files if f.endswith('.dmg')]}")
        except Exception as e:
            _log_to_file(f"ERROR listdir: {e}")
        
        for f in os.listdir(base_dir):
            if f.endswith('.dmg') and version in f:
                dmg_file = os.path.join(base_dir, f)
                break
        
        # Если DMG с этой версией нет, пробуем собрать
        if not dmg_file and build_if_missing:
            _log_to_file("DMG не найден, собираем...")
            print("📦 DMG не найден, пробуем собрать...")
            dmg_file = build_dmg(version, repo_dir)
            _log_to_file(f"build_dmg result: {dmg_file}")
        
        # Если всё равно нет - ищем любой DMG
        if not dmg_file:
            for f in os.listdir(base_dir):
                if f.endswith('.dmg'):
                    dmg_file = os.path.join(base_dir, f)
                    break
        
        if not dmg_file:
            _log_to_file("WARNING: DMG не найден")
            print("⚠️ DMG файл не найден, GitHub Release создаётся без файла")
        
        # Формируем заметки релиза
        notes = f"""## 📸 PhotoTools v{version}

{description if description else "Обновление PhotoTools"}

### Установка:
1. Скачайте DMG файл
2. Откройте и перетащите в Applications
3. При первом запуске: ПКМ → Открыть

### Если ошибка "повреждено":
```bash
xattr -cr /Applications/PhotoTools.app
```
"""
        
        _log_to_file(f"DMG file: {dmg_file}")
        
        # Проверяем существует ли релиз (используем repo_dir для gh CLI!)
        check_result = subprocess.run(
            [gh_cmd, "release", "view", f"v{version}"],
            capture_output=True, text=True, cwd=repo_dir
        )
        
        if check_result.returncode == 0:
            # Релиз существует - удаляем его
            _log_to_file(f"Удаляем старый релиз v{version}")
            print(f"🗑️ Удаляем старый релиз v{version}...")
            subprocess.run(
                [gh_cmd, "release", "delete", f"v{version}", "-y"],
                capture_output=True, text=True, cwd=repo_dir
            )
            # Удаляем тег
            subprocess.run(
                ["git", "tag", "-d", f"v{version}"],
                capture_output=True, text=True, cwd=repo_dir
            )
            subprocess.run(
                ["git", "push", "origin", f":refs/tags/v{version}"],
                capture_output=True, text=True, cwd=repo_dir
            )
        
        # Создаём новый релиз
        _log_to_file(f"Создаём GitHub Release v{version}...")
        print(f"🐙 Создаём GitHub Release v{version}...")
        
        cmd = [
            gh_cmd, "release", "create", f"v{version}",
            "--title", f"PhotoTools v{version}",
            "--notes", notes
        ]
        
        if dmg_file and os.path.exists(dmg_file):
            cmd.append(dmg_file)
            _log_to_file(f"С файлом: {dmg_file}")
            print(f"   📦 С файлом: {os.path.basename(dmg_file)}")
        else:
            _log_to_file("Без DMG файла")
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_dir)
        
        _log_to_file(f"gh result: code={result.returncode}, stdout={result.stdout[:200] if result.stdout else ''}, stderr={result.stderr[:200] if result.stderr else ''}")
        
        if result.returncode == 0:
            url = result.stdout.strip()
            _log_to_file(f"SUCCESS: {url}")
            print(f"✅ GitHub Release создан: {url}")
            return {"success": True, "url": url}
        else:
            _log_to_file(f"ERROR: {result.stderr}")
            print(f"❌ Ошибка создания релиза: {result.stderr}")
            return {"success": False, "message": result.stderr}
            
    except Exception as e:
        _log_to_file(f"EXCEPTION: {e}")
        import traceback
        _log_to_file(traceback.format_exc())
        print(f"⚠️ Ошибка GitHub Release: {e}")
        return {"success": False, "message": str(e)}


def publish_update(new_version: str, description: str = "", base_dir: str = None, status_callback=None) -> tuple:
    """
    Полный цикл публикации обновления:
    1. Создаёт ZIP-архив
    2. Загружает на сервер TimeWeb
    3. Обновляет версию в базе
    
    status_callback(text) - функция для обновления статуса в UI
    """
    def update_status(text):
        print(text)
        if status_callback:
            try:
                status_callback(text)
            except:
                pass
    
    update_status("📦 Создание архива...")
    
    # 1. Создаём ZIP
    try:
        zip_path = create_release_zip(new_version, base_dir=base_dir)
        update_status("✅ Архив создан")
    except Exception as e:
        return False, f"Ошибка создания архива: {e}"
    
    # 2. Загружаем на сервер
    update_status("☁️ Загрузка на сервер...")
    try:
        result = upload_update(zip_path, new_version, description)
    except Exception as e:
        return False, f"Ошибка загрузки: {e}"
    
    if not result.get("success"):
        return False, result.get("message", "Ошибка загрузки")
    
    update_status("✅ Загружено на сервер")
    
    # 3. Удаляем временный файл
    try:
        os.remove(zip_path)
    except:
        pass
    
    # 4. Создаём GitHub Release (DMG ~290MB, может занять 3-5 минут)
    update_status("🐙 GitHub Release (загрузка DMG ~3-5 мин)...")
    try:
        github_result = create_github_release(new_version, description, base_dir)
    except Exception as e:
        # GitHub Release опционален
        github_result = {"success": False, "message": str(e)}
    
    if github_result.get("success"):
        update_status("✅ GitHub Release создан")
    else:
        update_status("⚠️ GitHub Release: " + github_result.get("message", "ошибка")[:50])
    
    return True, f"Версия {new_version} опубликована"


def download_and_install_update(download_url: str, version: str) -> tuple:
    """
    Скачивает и устанавливает обновление
    Обрабатывает случай AppTranslocation (read-only filesystem)
    """
    try:
        print(f"\n📥 Скачивание обновления v{version}...")
        
        # Проверяем AppTranslocation
        if is_app_translocated():
            print("⚠️ Приложение запущено из защищённой директории (AppTranslocation)")
            # Скачиваем DMG в Downloads для ручной установки
            return _download_dmg_for_manual_install(version)
        
        resp = requests.get(download_url, stream=True, timeout=120)
        if resp.status_code != 200:
            return False, f"Ошибка скачивания: {resp.status_code}"
        
        # Получаем размер
        total_size = int(resp.headers.get('content-length', 0))
        
        # Сохраняем во временный файл
        temp_zip = os.path.join(tempfile.gettempdir(), f"fotya_update_{version}.zip")
        downloaded = 0
        
        with open(temp_zip, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    percent = (downloaded / total_size) * 100
                    print(f"\r   Загружено: {downloaded / 1024:.1f} KB ({percent:.0f}%)", end="")
        
        print()
        print(f"✅ Скачано: {os.path.getsize(temp_zip) / 1024:.1f} KB")
        
        # Определяем директорию для установки
        app_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Проверяем можем ли записать в директорию
        test_file = os.path.join(app_dir, ".write_test")
        try:
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
        except (IOError, OSError) as e:
            print(f"⚠️ Нет прав на запись в {app_dir}")
            os.remove(temp_zip)
            return _download_dmg_for_manual_install(version)
        
        backup_dir = os.path.join(tempfile.gettempdir(), f"fotya_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        
        print(f"📦 Распаковка...")
        
        with zipfile.ZipFile(temp_zip, 'r') as zipf:
            # Создаём бэкап
            os.makedirs(backup_dir, exist_ok=True)
            
            for name in zipf.namelist():
                target_path = os.path.join(app_dir, name)
                if os.path.exists(target_path):
                    backup_path = os.path.join(backup_dir, name)
                    os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                    shutil.copy2(target_path, backup_path)
            
            # Распаковываем
            zipf.extractall(app_dir)
        
        # Удаляем временный файл
        os.remove(temp_zip)
        
        print(f"✅ Обновление установлено!")
        print(f"   Бэкап: {backup_dir}")
        
        return True, "Обновление установлено. Перезапустите приложение."
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"Ошибка установки: {str(e)}"


def _download_dmg_for_manual_install(version: str) -> tuple:
    """
    Скачивает DMG из GitHub Releases для ручной установки
    """
    try:
        # Получаем URL DMG из GitHub
        dmg_url = f"https://github.com/pavkor1-design/fotya-tools/releases/download/v{version}/PhotoTools-{version}.dmg"
        
        downloads_dir = os.path.expanduser("~/Downloads")
        dmg_path = os.path.join(downloads_dir, f"PhotoTools-{version}.dmg")
        
        print(f"📥 Скачивание DMG из GitHub...")
        print(f"   URL: {dmg_url}")
        
        resp = requests.get(dmg_url, stream=True, timeout=120)
        if resp.status_code != 200:
            return False, f"DMG не найден на GitHub (HTTP {resp.status_code}).\n\nСкачайте вручную: https://github.com/pavkor1-design/fotya-tools/releases"
        
        total_size = int(resp.headers.get('content-length', 0))
        downloaded = 0
        
        with open(dmg_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    percent = (downloaded / total_size) * 100
                    print(f"\r   Загружено: {downloaded / 1024:.1f} KB ({percent:.0f}%)", end="")
        
        print(f"\n✅ DMG скачан: {dmg_path}")
        
        # Открываем папку Downloads
        subprocess.run(["open", downloads_dir], capture_output=True)
        
        return True, f"DMG скачан в Downloads.\n\n1. Откройте {os.path.basename(dmg_path)}\n2. Перетащите PhotoTools в Applications\n3. Запустите новую версию"
        
    except Exception as e:
        return False, f"Ошибка скачивания DMG: {str(e)}\n\nСкачайте вручную: https://github.com/pavkor1-design/fotya-tools/releases"


def download_and_install_update_with_progress(download_url: str, version: str, progress_callback=None) -> tuple:
    """
    Скачивает и устанавливает обновление с отображением прогресса
    progress_callback(progress: float 0-1, status: str)
    Обрабатывает случай AppTranslocation (read-only filesystem)
    """
    try:
        if progress_callback:
            progress_callback(0, "Проверка системы...")
        
        # Проверяем AppTranslocation
        if is_app_translocated():
            if progress_callback:
                progress_callback(0.1, "Приложение в защищённой директории...")
            return _download_dmg_with_progress(version, progress_callback)
        
        if progress_callback:
            progress_callback(0.05, "Подключение к серверу...")
        
        resp = requests.get(download_url, stream=True, timeout=120)
        if resp.status_code != 200:
            return False, f"Ошибка скачивания: {resp.status_code}"
        
        total_size = int(resp.headers.get('content-length', 0))
        temp_zip = os.path.join(tempfile.gettempdir(), f"fotya_update_{version}.zip")
        downloaded = 0
        
        with open(temp_zip, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0 and progress_callback:
                    progress = downloaded / total_size * 0.7  # 70% на скачивание
                    size_kb = downloaded / 1024
                    total_kb = total_size / 1024
                    progress_callback(progress, f"Скачивание: {size_kb:.0f} / {total_kb:.0f} KB")
        
        if progress_callback:
            progress_callback(0.72, "Проверка прав записи...")
        
        # Определяем директорию для установки
        app_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Проверяем можем ли записать в директорию
        test_file = os.path.join(app_dir, ".write_test")
        try:
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
        except (IOError, OSError):
            os.remove(temp_zip)
            if progress_callback:
                progress_callback(0.1, "Нет прав записи, скачиваю DMG...")
            return _download_dmg_with_progress(version, progress_callback)
        
        if progress_callback:
            progress_callback(0.75, "Создание резервной копии...")
        
        backup_dir = os.path.join(tempfile.gettempdir(), f"fotya_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        
        with zipfile.ZipFile(temp_zip, 'r') as zipf:
            os.makedirs(backup_dir, exist_ok=True)
            
            files = zipf.namelist()
            for i, name in enumerate(files):
                target_path = os.path.join(app_dir, name)
                if os.path.exists(target_path):
                    backup_path = os.path.join(backup_dir, name)
                    os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                    shutil.copy2(target_path, backup_path)
            
            if progress_callback:
                progress_callback(0.85, "Установка файлов...")
            
            zipf.extractall(app_dir)
        
        os.remove(temp_zip)
        
        if progress_callback:
            progress_callback(1.0, "✅ Обновление установлено!")
        
        return True, "Обновление установлено"
        
    except Exception as e:
        return False, f"Ошибка: {str(e)}"


def _download_dmg_with_progress(version: str, progress_callback=None) -> tuple:
    """
    Скачивает DMG с прогрессом для ручной установки
    """
    try:
        dmg_url = f"https://github.com/pavkor1-design/fotya-tools/releases/download/v{version}/PhotoTools-{version}.dmg"
        
        downloads_dir = os.path.expanduser("~/Downloads")
        dmg_path = os.path.join(downloads_dir, f"PhotoTools-{version}.dmg")
        
        if progress_callback:
            progress_callback(0.15, "Скачивание DMG из GitHub...")
        
        resp = requests.get(dmg_url, stream=True, timeout=120)
        if resp.status_code != 200:
            return False, f"DMG не найден (HTTP {resp.status_code}).\n\nСкачайте вручную:\nhttps://github.com/pavkor1-design/fotya-tools/releases"
        
        total_size = int(resp.headers.get('content-length', 0))
        downloaded = 0
        
        with open(dmg_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0 and progress_callback:
                    progress = 0.15 + (downloaded / total_size * 0.8)
                    size_mb = downloaded / 1024 / 1024
                    total_mb = total_size / 1024 / 1024
                    progress_callback(progress, f"Скачивание DMG: {size_mb:.1f} / {total_mb:.1f} MB")
        
        if progress_callback:
            progress_callback(0.98, "Открытие папки Downloads...")
        
        # Открываем DMG автоматически
        subprocess.run(["open", dmg_path], capture_output=True)
        
        if progress_callback:
            progress_callback(1.0, "✅ DMG скачан и открыт!")
        
        return True, f"DMG скачан и открыт.\n\n1. Перетащите PhotoTools в Applications\n2. Закройте это приложение\n3. Запустите новую версию из Applications"
        
    except Exception as e:
        return False, f"Ошибка: {str(e)}\n\nСкачайте вручную:\nhttps://github.com/pavkor1-design/fotya-tools/releases"


def list_updates() -> list:
    """Получает список всех опубликованных обновлений"""
    try:
        resp = requests.get(f"{API_URL}/updates/list", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("updates", [])
        return []
    except:
        return []


def delete_update(version: str) -> dict:
    """Удаляет обновление с сервера"""
    try:
        resp = requests.delete(f"{API_URL}/updates/delete/{version}", timeout=10)
        return resp.json()
    except Exception as e:
        return {"success": False, "message": str(e)}


# ==================== CLI ====================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="FotyaTools Auto Updater v2 (TimeWeb)")
    parser.add_argument("--publish", type=str, help="Опубликовать версию (например: --publish 1.0.13)")
    parser.add_argument("--description", "-d", type=str, default="", help="Описание обновления")
    parser.add_argument("--pack", type=str, help="Только создать ZIP")
    parser.add_argument("--check", action="store_true", help="Проверить обновления")
    parser.add_argument("--list", action="store_true", help="Список обновлений")
    parser.add_argument("--delete", type=str, help="Удалить версию")
    parser.add_argument("--install", type=str, help="Установить версию")
    parser.add_argument("--dir", type=str, help="Базовая директория для сборки")
    
    args = parser.parse_args()
    
    if args.publish:
        success, msg = publish_update(args.publish, args.description, args.dir)
        print(f"\nРезультат: {msg}")
        sys.exit(0 if success else 1)
    
    elif args.pack:
        zip_path = create_release_zip(args.pack, base_dir=args.dir)
        print(f"\nАрхив: {zip_path}")
    
    elif args.check:
        result = check_for_updates()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif args.list:
        updates = list_updates()
        if updates:
            print("\n📦 Опубликованные версии:")
            for u in updates:
                print(f"   v{u['version']} - {u['description'][:50] if u.get('description') else 'Без описания'}")
                print(f"      Размер: {u.get('filesize', 0) / 1024:.1f} KB, Скачиваний: {u.get('download_count', 0)}")
        else:
            print("Нет опубликованных версий")
    
    elif args.delete:
        result = delete_update(args.delete)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif args.install:
        info = check_for_updates("0.0.0")  # Получаем URL последней версии
        if info.get("download_url"):
            success, msg = download_and_install_update(info["download_url"], args.install)
            print(f"\n{msg}")
        else:
            print("Не удалось получить URL для скачивания")
    
    else:
        print("FotyaTools Auto Updater v2")
        print("=" * 40)
        print(f"Текущая версия: {get_app_version()}")
        
        server_info = get_server_version()
        print(f"Версия на сервере: {server_info.get('version', 'N/A')}")
        
        print("\nИспользование:")
        print("  python auto_updater_new.py --publish 1.0.13 -d 'Описание'")
        print("  python auto_updater_new.py --check")
        print("  python auto_updater_new.py --list")
        print("  python auto_updater_new.py --pack 1.0.13")
