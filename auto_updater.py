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
import requests
from datetime import datetime

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


def publish_update(new_version: str, description: str = "", base_dir: str = None) -> tuple:
    """
    Полный цикл публикации обновления:
    1. Создаёт ZIP-архив
    2. Загружает на сервер TimeWeb
    3. Обновляет версию в базе
    """
    print("\n" + "=" * 50)
    print(f"🚀 ПУБЛИКАЦИЯ ВЕРСИИ {new_version}")
    print("=" * 50)
    
    # 1. Создаём ZIP
    zip_path = create_release_zip(new_version, base_dir=base_dir)
    
    # 2. Загружаем на сервер
    result = upload_update(zip_path, new_version, description)
    
    if not result.get("success"):
        print(f"\n❌ Ошибка публикации: {result.get('message')}")
        return False, result.get("message", "Ошибка загрузки")
    
    # 3. Удаляем временный файл
    try:
        os.remove(zip_path)
    except:
        pass
    
    print("\n" + "=" * 50)
    print(f"🎉 ВЕРСИЯ {new_version} ОПУБЛИКОВАНА!")
    print("=" * 50)
    print(f"\n📥 URL для скачивания:")
    print(f"   {result.get('download_url', 'N/A')}")
    print(f"\n👥 Пользователи получат уведомление при следующем запуске")
    
    return True, f"Версия {new_version} опубликована"


def download_and_install_update(download_url: str, version: str) -> tuple:
    """
    Скачивает и устанавливает обновление
    """
    try:
        print(f"\n📥 Скачивание обновления v{version}...")
        
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
        
        # Распаковываем
        app_dir = os.path.dirname(os.path.abspath(__file__))
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
