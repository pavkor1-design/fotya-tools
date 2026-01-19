#!/usr/bin/env python3
"""Тест подключения к серверу лицензий"""

import sys
sys.path.insert(0, '.')

from license_manager import LicenseManager, GIST_ID

def test_connection():
    print("=" * 50)
    print("ТЕСТ ПОДКЛЮЧЕНИЯ К СЕРВЕРУ ЛИЦЕНЗИЙ")
    print("=" * 50)
    
    lm = LicenseManager()
    
    # 1. Проверка интернета
    print("\n1. Проверка интернета...")
    if lm.check_internet_connection():
        print("   ✅ Интернет доступен")
    else:
        print("   ❌ Нет интернета")
        return False
    
    # 2. Проверка Gist ID
    print(f"\n2. Gist ID: {GIST_ID}")
    if GIST_ID:
        print("   ✅ Gist ID установлен")
    else:
        print("   ❌ Gist ID не установлен")
        return False
    
    # 3. Получение данных из Gist
    print("\n3. Получение данных из Gist...")
    db = lm._get_gist_content()
    if db:
        print("   ✅ Данные получены")
        users = db.get("users", {})
        print(f"   📋 Найдено пользователей: {len(users)}")
        for username in users:
            user = users[username]
            admin = "👑 ADMIN" if user.get("is_admin") else ""
            enabled = "✅" if user.get("enabled", True) else "❌"
            print(f"      - {username} {admin} {enabled}")
    else:
        print("   ❌ Не удалось получить данные")
        return False
    
    # 4. Тест авторизации
    print("\n4. Тест авторизации (admin / admin123)...")
    success, message = lm.login("admin", "admin123")
    if success:
        print(f"   ✅ {message}")
    else:
        print(f"   ❌ {message}")
        return False
    
    print("\n" + "=" * 50)
    print("ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
    print("=" * 50)
    return True

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
