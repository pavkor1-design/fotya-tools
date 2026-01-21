#!/usr/bin/env python3
"""
PhotoTools - Полный тест установки
Этот тест проверяет работоспособность программы при установке на новом компьютере.
Запустите этот файл для диагностики проблем.
"""

import sys
import os
import traceback
import ssl
import certifi
from datetime import datetime

# Исправление SSL для macOS
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except:
    pass

# Альтернативный способ - использование certifi
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

# Результаты тестов
TEST_RESULTS = {
    "passed": [],
    "failed": [],
    "warnings": []
}

def log_result(test_name, passed, message="", warning=False):
    """Логирует результат теста"""
    if warning:
        TEST_RESULTS["warnings"].append((test_name, message))
        print(f"  ⚠️  {test_name}: {message}")
    elif passed:
        TEST_RESULTS["passed"].append(test_name)
        print(f"  ✅ {test_name}")
    else:
        TEST_RESULTS["failed"].append((test_name, message))
        print(f"  ❌ {test_name}: {message}")

def print_section(title):
    """Печатает заголовок секции"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

# ============================================================
# 1. ПРОВЕРКА ЗАВИСИМОСТЕЙ
# ============================================================
def test_dependencies():
    print_section("1. ПРОВЕРКА ЗАВИСИМОСТЕЙ")
    
    required_packages = {
        "customtkinter": "GUI библиотека",
        "PIL": "Обработка изображений (Pillow)",
        "fal_client": "FAL.ai API для нейросетей",
        "cv2": "OpenCV для обработки изображений",
        "numpy": "Математические операции",
        "requests": "HTTP запросы",
    }
    
    optional_packages = {
        "webview": "Встроенный браузер (pywebview)",
        "scipy": "Расширенная коррекция перспективы",
    }
    
    print("\nОбязательные пакеты:")
    all_required_ok = True
    for package, desc in required_packages.items():
        try:
            if package == "PIL":
                from PIL import Image
            elif package == "cv2":
                import cv2
            elif package == "fal_client":
                import fal_client
            else:
                __import__(package)
            log_result(f"{package} ({desc})", True)
        except ImportError as e:
            log_result(f"{package} ({desc})", False, f"Не установлен: {e}")
            all_required_ok = False
    
    print("\nОпциональные пакеты:")
    for package, desc in optional_packages.items():
        try:
            __import__(package)
            log_result(f"{package} ({desc})", True)
        except ImportError:
            log_result(f"{package} ({desc})", True, "Не установлен (опционально)", warning=True)
    
    return all_required_ok

# ============================================================
# 2. ПРОВЕРКА ИНТЕРНЕТ-СОЕДИНЕНИЯ
# ============================================================
def test_internet():
    print_section("2. ПРОВЕРКА ИНТЕРНЕТ-СОЕДИНЕНИЯ")
    
    import urllib.request
    import urllib.error
    import socket
    import ssl
    
    # Создаём контекст без проверки сертификатов (для обхода проблем macOS)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    # Тест 1: Общее подключение к интернету
    try:
        socket.setdefaulttimeout(10)
        urllib.request.urlopen("https://www.google.com", timeout=10, context=ctx)
        log_result("Подключение к интернету", True)
    except Exception as e:
        # Пробуем без SSL проверки
        try:
            urllib.request.urlopen("http://www.google.com", timeout=10)
            log_result("Подключение к интернету", True)
            log_result("SSL сертификаты", True, "Проблема с SSL, но HTTP работает", warning=True)
        except Exception as e2:
            log_result("Подключение к интернету", False, str(e))
            return False
    
    # Тест 2: Доступность FAL.ai API (проверяем что хост доступен, 404 - это ОК)
    try:
        req = urllib.request.Request("https://fal.run", method='HEAD')
        urllib.request.urlopen(req, timeout=10, context=ctx)
        log_result("Доступность FAL.ai (fal.run)", True)
    except urllib.error.HTTPError as e:
        # 404, 405 и т.д. - сервер отвечает, значит доступен
        if e.code in [404, 405, 403, 400]:
            log_result("Доступность FAL.ai (fal.run)", True)
        else:
            log_result("Доступность FAL.ai (fal.run)", False, f"HTTP ошибка: {e.code}")
            return False
    except Exception as e:
        log_result("Доступность FAL.ai (fal.run)", False, f"Возможно заблокирован: {e}")
        return False
    
    # Тест 3: Доступность FAL upload
    try:
        urllib.request.urlopen("https://fal.media", timeout=10, context=ctx)
        log_result("Доступность FAL Media (fal.media)", True)
    except Exception as e:
        log_result("Доступность FAL Media", True, f"Не критично: {e}", warning=True)
    
    # Тест 4: Доступность GitHub (для обновлений)
    try:
        urllib.request.urlopen("https://api.github.com", timeout=10, context=ctx)
        log_result("Доступность GitHub API", True)
    except Exception as e:
        log_result("Доступность GitHub API", True, f"Не критично: {e}", warning=True)
    
    return True

# ============================================================
# 3. ПРОВЕРКА FAL API КЛЮЧА
# ============================================================
def test_fal_api():
    print_section("3. ПРОВЕРКА FAL API")
    
    try:
        import fal_client
    except ImportError:
        log_result("Импорт fal_client", False, "Пакет не установлен: pip install fal-client")
        return False
    
    # Проверяем наличие API ключа
    fal_key = os.environ.get('FAL_KEY', '')
    
    if not fal_key:
        # Устанавливаем ключ из photo_tools.py
        os.environ['FAL_KEY'] = "8b41b065-51b8-4877-8880-a809f89216dd:8353eacc4adddec908c50eea36dfe501"
        fal_key = os.environ.get('FAL_KEY')
        log_result("FAL_KEY из переменной окружения", True, "Установлен из кода", warning=True)
    else:
        log_result("FAL_KEY из переменной окружения", True)
    
    # Проверяем формат ключа
    if ':' in fal_key and len(fal_key) > 50:
        log_result("Формат FAL_KEY", True)
    else:
        log_result("Формат FAL_KEY", False, "Неверный формат ключа")
        return False
    
    # Тест реального API вызова (минимальный)
    print("\n  Тестирование реального API вызова...")
    try:
        # Создаём минимальное тестовое изображение
        from PIL import Image
        from io import BytesIO
        
        # Маленькое красное изображение 64x64
        test_img = Image.new('RGB', (64, 64), color='red')
        buffer = BytesIO()
        test_img.save(buffer, format='JPEG', quality=85)
        buffer.seek(0)
        
        # Пробуем загрузить в FAL
        print("  📤 Загрузка тестового изображения в FAL...")
        url = fal_client.upload(buffer.read(), "image/jpeg")
        
        if url and url.startswith("http"):
            log_result("Загрузка в FAL (upload)", True)
        else:
            log_result("Загрузка в FAL (upload)", False, "Пустой URL")
            return False
        
        # Пробуем простой API вызов - ESRGAN (самая быстрая модель)
        print("  🧠 Тестирование ESRGAN модели...")
        result = fal_client.run(
            "fal-ai/esrgan",
            arguments={
                "image_url": url,
                "scale": 2
            }
        )
        
        if result and "image" in result and result["image"].get("url"):
            log_result("ESRGAN API вызов", True)
            print(f"      Результат: {result['image']['url'][:50]}...")
        else:
            log_result("ESRGAN API вызов", False, f"Неожиданный ответ: {result}")
            return False
        
    except Exception as e:
        error_msg = str(e)
        log_result("FAL API вызов", False, error_msg)
        
        # Анализируем ошибку
        if "401" in error_msg or "Unauthorized" in error_msg:
            print("\n  💡 РЕШЕНИЕ: API ключ недействителен или истёк.")
            print("     Получите новый ключ на https://fal.ai")
        elif "timeout" in error_msg.lower():
            print("\n  💡 РЕШЕНИЕ: Превышено время ожидания. Проверьте интернет.")
        elif "connection" in error_msg.lower():
            print("\n  💡 РЕШЕНИЕ: Нет соединения с сервером FAL.")
            print("     Возможно, сервис заблокирован или недоступен.")
        
        return False
    
    return True

# ============================================================
# 4. ПРОВЕРКА ФАЙЛОВОЙ СИСТЕМЫ
# ============================================================
def test_filesystem():
    print_section("4. ПРОВЕРКА ФАЙЛОВОЙ СИСТЕМЫ")
    
    # Текущая директория
    current_dir = os.path.dirname(os.path.abspath(__file__))
    log_result(f"Рабочая директория: {current_dir}", True)
    
    # Проверка необходимых файлов
    required_files = [
        "photo_tools.py",
        "requirements.txt",
    ]
    
    for f in required_files:
        path = os.path.join(current_dir, f)
        if os.path.exists(path):
            log_result(f"Файл {f}", True)
        else:
            log_result(f"Файл {f}", False, "Не найден")
    
    # Проверка возможности создания папок
    test_folder = os.path.join(current_dir, "_test_folder_")
    try:
        os.makedirs(test_folder, exist_ok=True)
        log_result("Создание папок", True)
        os.rmdir(test_folder)
    except Exception as e:
        log_result("Создание папок", False, str(e))
    
    # Проверка папки вывода
    home = os.path.expanduser("~")
    output_folder = os.path.join(home, "PhotoTools_Output")
    try:
        os.makedirs(output_folder, exist_ok=True)
        log_result(f"Папка вывода: {output_folder}", True)
    except Exception as e:
        log_result("Папка вывода", False, str(e))
    
    return True

# ============================================================
# 5. ПРОВЕРКА СОРТИРОВКИ ФОТОГРАФИЙ
# ============================================================
def test_sort_functionality():
    print_section("5. ПРОВЕРКА ФУНКЦИИ СОРТИРОВКИ")
    
    from PIL import Image
    import shutil
    import tempfile
    
    # Создаём временную директорию с тестовыми изображениями
    test_dir = tempfile.mkdtemp(prefix="phototools_test_")
    
    try:
        # Создаём горизонтальное изображение (800x600)
        horizontal_img = Image.new('RGB', (800, 600), color='blue')
        horizontal_path = os.path.join(test_dir, "horizontal_test.jpg")
        horizontal_img.save(horizontal_path)
        log_result("Создание горизонтального тестового фото", True)
        
        # Создаём вертикальное изображение (600x800)
        vertical_img = Image.new('RGB', (600, 800), color='green')
        vertical_path = os.path.join(test_dir, "vertical_test.jpg")
        vertical_img.save(vertical_path)
        log_result("Создание вертикального тестового фото", True)
        
        # Создаём квадратное изображение (500x500) - должно пойти в horizontal
        square_img = Image.new('RGB', (500, 500), color='red')
        square_path = os.path.join(test_dir, "square_test.jpg")
        square_img.save(square_path)
        log_result("Создание квадратного тестового фото", True)
        
        # Создаём папки для сортировки
        output_dir = tempfile.mkdtemp(prefix="phototools_output_")
        horizontal_folder = os.path.join(output_dir, "horizontal")
        vertical_folder = os.path.join(output_dir, "vertical")
        os.makedirs(horizontal_folder, exist_ok=True)
        os.makedirs(vertical_folder, exist_ok=True)
        
        # Выполняем сортировку (логика из photo_tools.py)
        image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.tiff', '.bmp', '.gif'}
        files = [(f, os.path.join(test_dir, f)) for f in os.listdir(test_dir)
                 if os.path.isfile(os.path.join(test_dir, f)) and 
                 os.path.splitext(f)[1].lower() in image_extensions]
        
        stats = {"horizontal": 0, "vertical": 0}
        
        for filename, filepath in files:
            try:
                with Image.open(filepath) as img:
                    width, height = img.size
                    if width >= height:
                        shutil.copy(filepath, os.path.join(horizontal_folder, filename))
                        stats["horizontal"] += 1
                    else:
                        shutil.copy(filepath, os.path.join(vertical_folder, filename))
                        stats["vertical"] += 1
            except Exception as e:
                log_result(f"Обработка {filename}", False, str(e))
        
        # Проверяем результаты
        h_files = os.listdir(horizontal_folder)
        v_files = os.listdir(vertical_folder)
        
        if stats["horizontal"] == 2 and stats["vertical"] == 1:
            log_result("Сортировка по ориентации", True)
            print(f"      Горизонтальных: {stats['horizontal']} ({', '.join(h_files)})")
            print(f"      Вертикальных: {stats['vertical']} ({', '.join(v_files)})")
        else:
            log_result("Сортировка по ориентации", False, 
                      f"Ожидалось h=2, v=1, получено h={stats['horizontal']}, v={stats['vertical']}")
        
        return True
        
    except Exception as e:
        log_result("Тест сортировки", False, str(e))
        traceback.print_exc()
        return False
        
    finally:
        # Очистка
        try:
            shutil.rmtree(test_dir)
            shutil.rmtree(output_dir)
        except:
            pass

# ============================================================
# 6. ПОЛНЫЙ ТЕСТ AI ГЕНЕРАЦИИ
# ============================================================
def test_ai_generation():
    print_section("6. ТЕСТ AI ГЕНЕРАЦИИ (опционально)")
    
    try:
        import fal_client
        from PIL import Image
        from io import BytesIO
        import requests
    except ImportError as e:
        log_result("Импорт модулей", False, str(e))
        return False
    
    # Убеждаемся что API ключ установлен
    if not os.environ.get('FAL_KEY'):
        os.environ['FAL_KEY'] = "8b41b065-51b8-4877-8880-a809f89216dd:8353eacc4adddec908c50eea36dfe501"
    
    # Создаём тестовое изображение
    test_img = Image.new('RGB', (256, 256), color='gray')
    buffer = BytesIO()
    test_img.save(buffer, format='JPEG', quality=85)
    buffer.seek(0)
    
    print("\n  Тестирование различных AI моделей:")
    
    # Загружаем изображение
    try:
        url = fal_client.upload(buffer.read(), "image/jpeg")
        log_result("Загрузка тестового изображения", True)
    except Exception as e:
        log_result("Загрузка тестового изображения", False, str(e))
        return False
    
    # Тестируем модели
    models_to_test = {
        "ESRGAN": ("fal-ai/esrgan", {"image_url": url, "scale": 2}),
    }
    
    for model_name, (model_id, params) in models_to_test.items():
        try:
            print(f"\n  🧪 Тестирование {model_name}...")
            result = fal_client.run(model_id, arguments=params)
            
            if result and ("image" in result or "images" in result):
                # Проверяем что результат можно скачать
                if "image" in result:
                    result_url = result["image"].get("url")
                else:
                    result_url = result["images"][0].get("url")
                
                if result_url:
                    response = requests.get(result_url, timeout=30)
                    if response.status_code == 200 and len(response.content) > 1000:
                        log_result(f"{model_name}", True)
                    else:
                        log_result(f"{model_name}", False, "Не удалось скачать результат")
                else:
                    log_result(f"{model_name}", False, "Пустой URL результата")
            else:
                log_result(f"{model_name}", False, f"Неожиданный формат ответа")
                
        except Exception as e:
            log_result(f"{model_name}", False, str(e))
    
    return True

# ============================================================
# 7. ПРОВЕРКА GUI (без запуска окна)
# ============================================================
def test_gui_imports():
    print_section("7. ПРОВЕРКА GUI КОМПОНЕНТОВ")
    
    try:
        import customtkinter as ctk
        log_result("Импорт customtkinter", True)
    except ImportError as e:
        log_result("Импорт customtkinter", False, str(e))
        return False
    
    try:
        from PIL import Image, ImageTk
        log_result("Импорт PIL/ImageTk", True)
    except ImportError as e:
        log_result("Импорт PIL/ImageTk", False, str(e))
    
    try:
        from tkinter import filedialog, messagebox
        log_result("Импорт tkinter dialogs", True)
    except ImportError as e:
        log_result("Импорт tkinter dialogs", False, str(e))
    
    return True

# ============================================================
# ИТОГОВЫЙ ОТЧЁТ
# ============================================================
def print_summary():
    print("\n")
    print("=" * 60)
    print("  ИТОГОВЫЙ ОТЧЁТ")
    print("=" * 60)
    
    passed = len(TEST_RESULTS["passed"])
    failed = len(TEST_RESULTS["failed"])
    warnings = len(TEST_RESULTS["warnings"])
    
    print(f"\n  ✅ Пройдено: {passed}")
    print(f"  ❌ Провалено: {failed}")
    print(f"  ⚠️  Предупреждений: {warnings}")
    
    if TEST_RESULTS["failed"]:
        print("\n  ОШИБКИ:")
        for test_name, message in TEST_RESULTS["failed"]:
            print(f"    • {test_name}: {message}")
    
    if TEST_RESULTS["warnings"]:
        print("\n  ПРЕДУПРЕЖДЕНИЯ:")
        for test_name, message in TEST_RESULTS["warnings"]:
            print(f"    • {test_name}: {message}")
    
    print("\n" + "=" * 60)
    
    if failed == 0:
        print("  🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Программа готова к работе.")
    else:
        print("  ⚠️  Есть проблемы. Исправьте их перед использованием.")
        print("\n  РЕШЕНИЯ ЧАСТЫХ ПРОБЛЕМ:")
        print("  1. 'fal_client не установлен' → pip install fal-client")
        print("  2. 'Нет интернета' → Проверьте подключение")
        print("  3. 'API ключ недействителен' → Обновите ключ на fal.ai")
        print("  4. 'Модуль не найден' → pip install -r requirements.txt")
    
    print("=" * 60)
    
    return failed == 0

# ============================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================
def main():
    print("\n")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║         📸 PhotoTools - Тест установки v2.0                ║")
    print("║         Проверка работоспособности на новом ПК             ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print(f"\n  Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Python: {sys.version.split()[0]}")
    print(f"  ОС: {sys.platform}")
    
    # Запускаем тесты
    deps_ok = test_dependencies()
    
    if not deps_ok:
        print("\n❌ КРИТИЧЕСКАЯ ОШИБКА: Не все зависимости установлены!")
        print("   Выполните: pip install -r requirements.txt")
        print_summary()
        return False
    
    internet_ok = test_internet()
    
    if not internet_ok:
        print("\n❌ КРИТИЧЕСКАЯ ОШИБКА: Нет подключения к интернету или FAL заблокирован!")
        print_summary()
        return False
    
    test_fal_api()
    test_filesystem()
    test_sort_functionality()
    test_gui_imports()
    
    # Опционально: полный тест AI (занимает время)
    if "--full" in sys.argv:
        test_ai_generation()
    else:
        print("\n  ℹ️  Для полного теста AI генерации запустите с флагом --full")
    
    success = print_summary()
    return success

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nТест прерван пользователем.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}")
        traceback.print_exc()
        sys.exit(1)
