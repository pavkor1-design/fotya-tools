#!/usr/bin/env python3
"""
Система лицензирования и управления пользователями FotyaTools
Использует собственный API сервер на TimeWeb (вместо GitHub Gist)
"""

import os
import sys
import json
import hashlib
import requests
import socket
import platform
import uuid
from datetime import datetime
from typing import Optional, Dict, List
import threading
import time

# Версия приложения
APP_VERSION = "1.0.16"

# API сервер на TimeWeb
AUTH_API_URL = "http://5.129.203.43:8085/api"

# Файл локального кэша авторизации
LOCAL_AUTH_CACHE = os.path.expanduser("~/.fotya_tools_auth.json")


class LicenseManager:
    """Менеджер лицензий и авторизации"""
    
    def __init__(self):
        self.current_user: Optional[Dict] = None
        self.is_admin = False
        self.permissions: Dict[str, bool] = {}
        self.heartbeat_thread: Optional[threading.Thread] = None
        self.heartbeat_running = False
        self._event_queue = []
    
    # ==================== ПРОВЕРКА ИНТЕРНЕТА ====================
    
    @staticmethod
    def check_internet_connection(timeout: float = 5.0) -> bool:
        """Проверяет наличие интернет-соединения"""
        test_hosts = [
            ("8.8.8.8", 53),      # Google DNS
            ("1.1.1.1", 53),      # Cloudflare DNS
            ("5.129.203.43", 8085),  # Наш API сервер
        ]
        
        for host, port in test_hosts:
            try:
                socket.setdefaulttimeout(timeout)
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((host, port))
                sock.close()
                return True
            except socket.error:
                continue
        
        return False
    
    # ==================== РАБОТА С API ====================
    
    def _api_request(self, method: str, endpoint: str, data: dict = None) -> Optional[dict]:
        """Выполняет запрос к API"""
        url = f"{AUTH_API_URL}{endpoint}"
        
        try:
            if method == "GET":
                response = requests.get(url, params=data, timeout=10)
            elif method == "POST":
                response = requests.post(url, json=data, timeout=10)
            elif method == "PUT":
                response = requests.put(url, json=data, timeout=10)
            elif method == "DELETE":
                response = requests.delete(url, timeout=10)
            else:
                return None
            
            if response.status_code in [200, 201]:
                return response.json()
            else:
                print(f"API Error {response.status_code}: {response.text[:200]}")
                return None
                
        except Exception as e:
            print(f"API Request Error: {e}")
            return None
    
    # ==================== АВТОРИЗАЦИЯ ====================
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Хеширует пароль"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def get_machine_id(self) -> str:
        """Получает уникальный ID машины"""
        machine_info = f"{platform.node()}-{platform.machine()}-{uuid.getnode()}"
        return hashlib.md5(machine_info.encode()).hexdigest()[:16]
    
    def login(self, username: str, password: str) -> tuple[bool, str]:
        """Авторизация пользователя"""
        # Проверяем интернет
        if not self.check_internet_connection():
            return False, "Нет подключения к интернету"
        
        # Отправляем запрос на авторизацию
        result = self._api_request("POST", "/login", {
            "username": username,
            "password": password,
            "machine_id": self.get_machine_id(),
            "platform": platform.system(),
            "app_version": APP_VERSION
        })
        
        if not result:
            return False, "Не удалось подключиться к серверу"
        
        if not result.get("success"):
            return False, result.get("message", "Ошибка авторизации")
        
        # Успешная авторизация
        user = result.get("user", {})
        self.current_user = user
        self.current_user["username"] = username
        self.is_admin = user.get("is_admin", False)
        self.permissions = user.get("permissions", {
            "ai_enabled": True,
            "app_enabled": True
        })
        
        # Сохраняем локальный кэш
        self._save_local_auth(username, password)
        
        # Запускаем heartbeat
        self._start_heartbeat()
        
        return True, "Авторизация успешна"
    
    def _save_local_auth(self, username: str, password: str):
        """Сохраняет локальный кэш авторизации"""
        try:
            auth_data = {
                "username": username,
                "password": password,  # Для автологина
                "machine_id": self.get_machine_id(),
                "timestamp": datetime.now().isoformat()
            }
            with open(LOCAL_AUTH_CACHE, 'w') as f:
                json.dump(auth_data, f)
        except:
            pass
    
    def _load_local_auth(self) -> Optional[tuple]:
        """Загружает локальный кэш авторизации"""
        try:
            if os.path.exists(LOCAL_AUTH_CACHE):
                with open(LOCAL_AUTH_CACHE, 'r') as f:
                    auth_data = json.load(f)
                    if auth_data.get("machine_id") == self.get_machine_id():
                        return auth_data.get("username"), auth_data.get("password")
        except:
            pass
        return None, None
    
    def try_auto_login(self) -> tuple[bool, str]:
        """Пытается автоматически войти используя сохранённый кэш"""
        # Проверяем интернет
        if not self.check_internet_connection():
            return False, "Нет подключения к интернету"
        
        # Проверяем сохранённый кэш
        username, password = self._load_local_auth()
        if not username or not password:
            return False, "Нет сохранённой сессии"
        
        # Пробуем войти
        return self.login(username, password)
    
    def _clear_local_auth(self):
        """Очищает локальный кэш авторизации"""
        try:
            if os.path.exists(LOCAL_AUTH_CACHE):
                os.remove(LOCAL_AUTH_CACHE)
        except:
            pass
    
    def logout(self):
        """Выход из аккаунта"""
        if self.current_user:
            username = self.current_user.get("username")
            self._api_request("POST", "/logout", {"username": username})
        
        self.current_user = None
        self.is_admin = False
        self.permissions = {}
        self._stop_heartbeat()
        self._clear_local_auth()
    
    # ==================== HEARTBEAT ====================
    
    def _start_heartbeat(self):
        """Запускает периодическую проверку сессии"""
        self.heartbeat_running = True
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()
    
    def _stop_heartbeat(self):
        """Останавливает heartbeat"""
        self.heartbeat_running = False
    
    def _heartbeat_loop(self):
        """Цикл проверки сессии каждые 60 секунд"""
        while self.heartbeat_running:
            time.sleep(60)
            if self.current_user:
                username = self.current_user.get("username", "")
                result = self._api_request("POST", "/heartbeat", {"username": username})
                
                if result and result.get("success"):
                    # Обновляем права если изменились
                    if not result.get("enabled", True):
                        # Пользователь заблокирован
                        self.logout()
                    else:
                        self.permissions = result.get("permissions", self.permissions)
    
    # ==================== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ====================
    
    def get_all_users(self) -> List[Dict]:
        """Получает список всех пользователей (для админа)"""
        if not self.is_admin:
            return []
        
        result = self._api_request("GET", "/users")
        if result and result.get("success"):
            return result.get("users", [])
        return []
    
    def create_user(self, username: str, password: str, is_admin: bool = False, 
                    permissions: dict = None) -> tuple[bool, str]:
        """Создаёт нового пользователя"""
        if not self.is_admin:
            return False, "Только администратор может создавать пользователей"
        
        perms = permissions or {"ai_enabled": True, "app_enabled": True}
        
        result = self._api_request("POST", "/users", {
            "username": username,
            "password": password,
            "is_admin": is_admin,
            "ai_enabled": perms.get("ai_enabled", True),
            "app_enabled": perms.get("app_enabled", True),
            "created_by": self.current_user.get("username", "admin")
        })
        
        if result and result.get("success"):
            return True, result.get("message", "Пользователь создан")
        return False, result.get("message", "Ошибка создания пользователя") if result else "Нет связи с сервером"
    
    def update_user(self, username: str, **kwargs) -> tuple[bool, str]:
        """Обновляет пользователя"""
        if not self.is_admin:
            return False, "Только администратор может редактировать пользователей"
        
        data = {}
        if "password" in kwargs and kwargs["password"]:
            data["password"] = kwargs["password"]
        if "enabled" in kwargs:
            data["enabled"] = kwargs["enabled"]
        if "is_admin" in kwargs:
            data["is_admin"] = kwargs["is_admin"]
        if "ai_enabled" in kwargs:
            data["ai_enabled"] = kwargs["ai_enabled"]
        if "app_enabled" in kwargs:
            data["app_enabled"] = kwargs["app_enabled"]
        
        result = self._api_request("PUT", f"/users/{username}", data)
        
        if result and result.get("success"):
            return True, result.get("message", "Пользователь обновлён")
        return False, result.get("message", "Ошибка обновления") if result else "Нет связи с сервером"
    
    def delete_user(self, username: str) -> tuple[bool, str]:
        """Удаляет пользователя"""
        if not self.is_admin:
            return False, "Только администратор может удалять пользователей"
        
        result = self._api_request("DELETE", f"/users/{username}")
        
        if result and result.get("success"):
            return True, result.get("message", "Пользователь удалён")
        return False, result.get("message", "Ошибка удаления") if result else "Нет связи с сервером"
    
    # ==================== СЕССИИ И АНАЛИТИКА ====================
    
    def get_active_sessions(self) -> List[Dict]:
        """Получает активные сессии"""
        result = self._api_request("GET", "/sessions")
        if result and result.get("success"):
            return result.get("sessions", [])
        return []
    
    def get_user_analytics(self, username: str = None) -> List[Dict]:
        """Получает аналитику"""
        params = {"limit": 200}
        if username:
            params["username"] = username
        
        result = self._api_request("GET", "/analytics", params)
        if result and result.get("success"):
            return result.get("events", [])
        return []
    
    def log_action(self, action: str, details: str = ""):
        """Логирует действие пользователя"""
        if not self.current_user:
            return
        
        # Добавляем в очередь для асинхронной отправки
        self._event_queue.append({
            "username": self.current_user.get("username", ""),
            "type": "action",
            "description": action,
            "platform": platform.system(),
            "app_version": APP_VERSION
        })
        
        # Отправляем если накопилось много или периодически
        if len(self._event_queue) >= 5:
            self._flush_event_queue()
    
    def _flush_event_queue(self):
        """Отправляет накопленные события"""
        if not self._event_queue:
            return
        
        for event in self._event_queue:
            self._api_request("POST", "/analytics", event)
        
        self._event_queue.clear()
    
    # ==================== НАСТРОЙКИ ====================
    
    def get_settings(self) -> Dict:
        """Получает настройки приложения"""
        result = self._api_request("GET", "/settings")
        if result and result.get("success"):
            return result.get("settings", {})
        return {}
    
    def get_current_server_version(self) -> str:
        """Получает текущую версию с сервера обновлений"""
        try:
            # Используем API обновлений, а не settings
            result = self._api_request("GET", "/updates/latest")
            if result and result.get("success"):
                return result.get("version", APP_VERSION)
        except:
            pass
        return APP_VERSION
    
    def publish_update(self, version: str, description: str, download_url: str = "") -> tuple[bool, str]:
        """Публикует обновление"""
        if not self.is_admin:
            return False, "Только администратор может публиковать обновления"
        
        result = self._api_request("POST", "/settings", {
            "app_version": version,
            "update_description": description,
            "download_url": download_url,
            "update_time": datetime.now().isoformat()
        })
        
        if result and result.get("success"):
            return True, f"Версия {version} опубликована"
        return False, "Ошибка публикации"
    
    def check_for_updates(self) -> tuple[bool, str, str]:
        """Проверяет наличие обновлений через API"""
        try:
            # Используем правильный API для проверки обновлений
            result = self._api_request("GET", f"/updates/check/{APP_VERSION}")
            if result and result.get("success") and result.get("has_update"):
                return True, result.get("latest_version", ""), result.get("download_url", "")
        except Exception as e:
            logger.warning(f"Update check failed: {e}")
        
        return False, APP_VERSION, ""
    
    @staticmethod
    def _compare_versions(v1: str, v2: str) -> int:
        """Сравнивает версии. Возвращает 1 если v1 > v2, -1 если v1 < v2, 0 если равны"""
        try:
            parts1 = [int(x) for x in v1.split(".")]
            parts2 = [int(x) for x in v2.split(".")]
            
            for i in range(max(len(parts1), len(parts2))):
                p1 = parts1[i] if i < len(parts1) else 0
                p2 = parts2[i] if i < len(parts2) else 0
                if p1 > p2:
                    return 1
                if p1 < p2:
                    return -1
            return 0
        except:
            return 0


# Глобальный экземпляр
license_manager = LicenseManager()
