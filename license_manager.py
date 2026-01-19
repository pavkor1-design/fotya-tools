#!/usr/bin/env python3
"""
Система лицензирования и управления пользователями FotyaTools
Использует GitHub Gist как бесплатную "базу данных"
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
APP_VERSION = "1.0.12"

# GitHub Gist настройки (будут заполнены при настройке)
GITHUB_TOKEN = ""  # Будет установлен из config
GIST_ID = ""  # ID гиста с базой пользователей
GITHUB_REPO = "pavkor1-design/fotya-tools"  # Репозиторий для обновлений

# Файл локального кэша авторизации
LOCAL_AUTH_CACHE = os.path.expanduser("~/.fotya_tools_auth.json")


class LicenseManager:
    """Менеджер лицензий и авторизации"""
    
    def __init__(self):
        self.current_user: Optional[Dict] = None
        self.is_admin = False
        self.permissions: Dict[str, bool] = {}
        self.github_token = ""
        self.gist_id = ""
        self.users_db: Dict = {}
        self.heartbeat_thread: Optional[threading.Thread] = None
        self.heartbeat_running = False
        
        # Загружаем конфигурацию
        self._load_config()
    
    def _load_config(self):
        """Загружает конфигурацию из файла"""
        config_path = os.path.join(os.path.dirname(__file__), "license_config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    self.github_token = config.get("github_token", "")
                    self.gist_id = config.get("gist_id", "")
            except:
                pass
    
    def _save_config(self, github_token: str, gist_id: str):
        """Сохраняет конфигурацию"""
        config_path = os.path.join(os.path.dirname(__file__), "license_config.json")
        config = {
            "github_token": github_token,
            "gist_id": gist_id
        }
        with open(config_path, 'w') as f:
            json.dump(config, f)
        self.github_token = github_token
        self.gist_id = gist_id
    
    # ==================== ПРОВЕРКА ИНТЕРНЕТА ====================
    
    @staticmethod
    def check_internet_connection(timeout: float = 5.0) -> bool:
        """Проверяет наличие интернет-соединения"""
        test_hosts = [
            ("8.8.8.8", 53),      # Google DNS
            ("1.1.1.1", 53),      # Cloudflare DNS
            ("github.com", 443),  # GitHub
        ]
        
        for host, port in test_hosts:
            try:
                socket.setdefaulttimeout(timeout)
                socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
                return True
            except socket.error:
                continue
        
        return False
    
    # ==================== РАБОТА С GITHUB GIST ====================
    
    def _get_gist_content(self) -> Optional[Dict]:
        """Получает содержимое гиста с базой пользователей"""
        if not self.github_token or not self.gist_id:
            return None
        
        try:
            headers = {
                "Authorization": f"token {self.github_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            response = requests.get(
                f"https://api.github.com/gists/{self.gist_id}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                gist = response.json()
                if "users_db.json" in gist["files"]:
                    content = gist["files"]["users_db.json"]["content"]
                    return json.loads(content)
            
            return None
        except Exception as e:
            print(f"Ошибка получения гиста: {e}")
            return None
    
    def _update_gist_content(self, data: Dict) -> bool:
        """Обновляет содержимое гиста"""
        if not self.github_token or not self.gist_id:
            return False
        
        try:
            headers = {
                "Authorization": f"token {self.github_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            payload = {
                "files": {
                    "users_db.json": {
                        "content": json.dumps(data, indent=2, ensure_ascii=False)
                    }
                }
            }
            response = requests.patch(
                f"https://api.github.com/gists/{self.gist_id}",
                headers=headers,
                json=payload,
                timeout=10
            )
            
            return response.status_code == 200
        except Exception as e:
            print(f"Ошибка обновления гиста: {e}")
            return False
    
    def _create_initial_gist(self) -> Optional[str]:
        """Создаёт начальный гист с базой пользователей"""
        if not self.github_token:
            return None
        
        initial_db = {
            "version": "1.0",
            "app_version": APP_VERSION,
            "users": {},
            "active_sessions": {},
            "settings": {
                "require_auth": True,
                "allow_registration": False
            }
        }
        
        try:
            headers = {
                "Authorization": f"token {self.github_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            payload = {
                "description": "FotyaTools Users Database",
                "public": False,
                "files": {
                    "users_db.json": {
                        "content": json.dumps(initial_db, indent=2, ensure_ascii=False)
                    }
                }
            }
            response = requests.post(
                "https://api.github.com/gists",
                headers=headers,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 201:
                gist = response.json()
                return gist["id"]
            
            return None
        except Exception as e:
            print(f"Ошибка создания гиста: {e}")
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
        
        # Получаем базу пользователей
        db = self._get_gist_content()
        if not db:
            return False, "Не удалось подключиться к серверу"
        
        self.users_db = db
        users = db.get("users", {})
        
        # Проверяем пользователя
        if username not in users:
            return False, "Неверный логин или пароль"
        
        user = users[username]
        password_hash = self.hash_password(password)
        
        if user["password_hash"] != password_hash:
            return False, "Неверный логин или пароль"
        
        # Проверяем блокировку
        if not user.get("enabled", True):
            return False, "Ваш аккаунт заблокирован"
        
        # Успешная авторизация
        self.current_user = user
        self.current_user["username"] = username
        self.is_admin = user.get("is_admin", False)
        self.permissions = user.get("permissions", {
            "ai_enabled": True,
            "app_enabled": True
        })
        
        # Обновляем сессию
        self._update_session(username)
        
        # Сохраняем локальный кэш
        self._save_local_auth(username)
        
        # Запускаем heartbeat
        self._start_heartbeat()
        
        return True, "Авторизация успешна"
    
    def _update_session(self, username: str):
        """Обновляет информацию о сессии пользователя"""
        try:
            db = self._get_gist_content()
            if db:
                if "active_sessions" not in db:
                    db["active_sessions"] = {}
                
                db["active_sessions"][username] = {
                    "machine_id": self.get_machine_id(),
                    "last_seen": datetime.now().isoformat(),
                    "login_time": datetime.now().isoformat(),
                    "app_version": APP_VERSION,
                    "platform": platform.system(),
                    "status": "online"
                }
                
                # Записываем событие входа
                self._log_event(db, username, "login", "Вход в приложение")
                
                self._update_gist_content(db)
        except:
            pass
    
    def _log_event(self, db: dict, username: str, event_type: str, description: str, extra: dict = None):
        """Записывает событие в лог аналитики"""
        if "analytics" not in db:
            db["analytics"] = {}
        if username not in db["analytics"]:
            db["analytics"][username] = []
        
        event = {
            "type": event_type,
            "description": description,
            "timestamp": datetime.now().isoformat(),
            "platform": platform.system(),
            "app_version": APP_VERSION
        }
        if extra:
            event.update(extra)
        
        # Храним последние 100 событий на пользователя
        db["analytics"][username].append(event)
        if len(db["analytics"][username]) > 100:
            db["analytics"][username] = db["analytics"][username][-100:]
    
    def log_action(self, action: str, details: str = ""):
        """Логирует действие пользователя (асинхронно через очередь)"""
        if not self.current_user:
            return
        
        username = self.current_user.get("username", "")
        if not username:
            return
        
        # Добавляем в очередь (не блокируем UI)
        event = {
            "username": username,
            "type": "action",
            "description": action,
            "timestamp": datetime.now().isoformat(),
            "platform": platform.system(),
            "app_version": APP_VERSION
        }
        if details:
            event["details"] = details
        
        if not hasattr(self, '_event_queue'):
            self._event_queue = []
            self._start_event_flush_thread()
        
        self._event_queue.append(event)
    
    def _start_event_flush_thread(self):
        """Запускает фоновый поток для отправки событий"""
        def flush_events():
            while True:
                time.sleep(60)  # Отправляем каждые 60 секунд
                self._flush_event_queue()
        
        flush_thread = threading.Thread(target=flush_events, daemon=True)
        flush_thread.start()
    
    def _flush_event_queue(self):
        """Отправляет накопленные события на сервер"""
        if not hasattr(self, '_event_queue') or not self._event_queue:
            return
        
        try:
            events_to_send = self._event_queue.copy()
            self._event_queue.clear()
            
            db = self._get_gist_content()
            if db:
                if "analytics" not in db:
                    db["analytics"] = {}
                
                for event in events_to_send:
                    username = event.pop("username", "unknown")
                    if username not in db["analytics"]:
                        db["analytics"][username] = []
                    db["analytics"][username].append(event)
                    
                    # Ограничиваем 100 событий на пользователя
                    if len(db["analytics"][username]) > 100:
                        db["analytics"][username] = db["analytics"][username][-100:]
                
                self._update_gist_content(db)
        except:
            pass
    
    def get_user_analytics(self, username: str = None) -> list:
        """Получает аналитику пользователя (только для админа)"""
        if not self.is_admin:
            return []
        
        db = self._get_gist_content()
        if not db:
            return []
        
        analytics = db.get("analytics", {})
        
        if username:
            return analytics.get(username, [])
        
        # Все события всех пользователей
        all_events = []
        for user, events in analytics.items():
            for event in events:
                event["username"] = user
                all_events.append(event)
        
        # Сортируем по времени (новые первые)
        all_events.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return all_events[:200]  # Последние 200 событий
    
    def _save_local_auth(self, username: str):
        """Сохраняет локальный кэш авторизации"""
        try:
            auth_data = {
                "username": username,
                "machine_id": self.get_machine_id(),
                "timestamp": datetime.now().isoformat()
            }
            with open(LOCAL_AUTH_CACHE, 'w') as f:
                json.dump(auth_data, f)
        except:
            pass
    
    def _load_local_auth(self) -> Optional[str]:
        """Загружает локальный кэш авторизации"""
        try:
            if os.path.exists(LOCAL_AUTH_CACHE):
                with open(LOCAL_AUTH_CACHE, 'r') as f:
                    auth_data = json.load(f)
                    if auth_data.get("machine_id") == self.get_machine_id():
                        return auth_data.get("username")
        except:
            pass
        return None
    
    def try_auto_login(self) -> tuple[bool, str]:
        """Пытается автоматически войти используя сохранённый кэш"""
        # Проверяем интернет
        if not self.check_internet_connection():
            return False, "Нет подключения к интернету"
        
        # Проверяем сохранённый кэш
        cached_username = self._load_local_auth()
        if not cached_username:
            return False, "Нет сохранённой сессии"
        
        # Получаем базу пользователей
        db = self._get_gist_content()
        if not db:
            return False, "Не удалось подключиться к серверу"
        
        users = db.get("users", {})
        
        # Проверяем пользователя
        if cached_username not in users:
            self._clear_local_auth()
            return False, "Пользователь не найден"
        
        user = users[cached_username]
        
        # Проверяем блокировку
        if not user.get("enabled", True):
            self._clear_local_auth()
            return False, "Ваш аккаунт заблокирован"
        
        # Успешная автоматическая авторизация
        self.current_user = user
        self.current_user["username"] = cached_username
        self.is_admin = user.get("is_admin", False)
        self.permissions = user.get("permissions", {
            "ai_enabled": True,
            "app_enabled": True
        })
        
        # Обновляем сессию
        self._update_session(cached_username)
        
        # Запускаем heartbeat
        self._start_heartbeat()
        
        return True, f"Автовход: {cached_username}"
    
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
            
            # Удаляем сессию и логируем выход
            try:
                db = self._get_gist_content()
                if db:
                    # Логируем выход
                    self._log_event(db, username, "logout", "Выход из приложения")
                    
                    # Обновляем статус сессии
                    if "active_sessions" in db and username in db["active_sessions"]:
                        db["active_sessions"][username]["status"] = "offline"
                        db["active_sessions"][username]["logout_time"] = datetime.now().isoformat()
                    
                    self._update_gist_content(db)
            except:
                pass
        
        self.current_user = None
        self.is_admin = False
        self.permissions = {}
        self._stop_heartbeat()
        
        # Удаляем локальный кэш
        try:
            if os.path.exists(LOCAL_AUTH_CACHE):
                os.remove(LOCAL_AUTH_CACHE)
        except:
            pass
    
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
                self._update_session(self.current_user.get("username", ""))
                
                # Проверяем не заблокирован ли пользователь
                db = self._get_gist_content()
                if db:
                    username = self.current_user.get("username")
                    if username in db.get("users", {}):
                        user = db["users"][username]
                        if not user.get("enabled", True):
                            self.heartbeat_running = False
                            # Пользователь заблокирован
                        self.permissions = user.get("permissions", self.permissions)
    
    # ==================== ПРОВЕРКА РАЗРЕШЕНИЙ ====================
    
    def check_permission(self, permission: str) -> bool:
        """Проверяет разрешение"""
        if self.is_admin:
            return True
        return self.permissions.get(permission, False)
    
    def is_ai_enabled(self) -> bool:
        """Проверяет доступ к нейросетям"""
        return self.check_permission("ai_enabled")
    
    def is_app_enabled(self) -> bool:
        """Проверяет доступ к приложению"""
        return self.check_permission("app_enabled")
    
    # ==================== АДМИН-ФУНКЦИИ ====================
    
    def create_user(self, username: str, password: str, is_admin: bool = False,
                   permissions: Optional[Dict] = None) -> tuple[bool, str]:
        """Создаёт нового пользователя (только для админа)"""
        if not self.is_admin:
            return False, "Недостаточно прав"
        
        db = self._get_gist_content()
        if not db:
            return False, "Не удалось подключиться к серверу"
        
        if username in db.get("users", {}):
            return False, "Пользователь уже существует"
        
        if "users" not in db:
            db["users"] = {}
        
        default_permissions = {
            "ai_enabled": True,
            "app_enabled": True
        }
        
        db["users"][username] = {
            "password_hash": self.hash_password(password),
            "is_admin": is_admin,
            "enabled": True,
            "permissions": permissions or default_permissions,
            "created_at": datetime.now().isoformat(),
            "created_by": self.current_user.get("username", "system")
        }
        
        if self._update_gist_content(db):
            return True, f"Пользователь {username} создан"
        return False, "Ошибка сохранения"
    
    def update_user(self, username: str, **kwargs) -> tuple[bool, str]:
        """Обновляет пользователя (только для админа)"""
        if not self.is_admin:
            return False, "Недостаточно прав"
        
        db = self._get_gist_content()
        if not db:
            return False, "Не удалось подключиться к серверу"
        
        if username not in db.get("users", {}):
            return False, "Пользователь не найден"
        
        user = db["users"][username]
        
        if "password" in kwargs:
            user["password_hash"] = self.hash_password(kwargs["password"])
        if "enabled" in kwargs:
            user["enabled"] = kwargs["enabled"]
        if "is_admin" in kwargs:
            user["is_admin"] = kwargs["is_admin"]
        if "permissions" in kwargs:
            user["permissions"] = kwargs["permissions"]
        if "ai_enabled" in kwargs:
            user["permissions"]["ai_enabled"] = kwargs["ai_enabled"]
        if "app_enabled" in kwargs:
            user["permissions"]["app_enabled"] = kwargs["app_enabled"]
        
        db["users"][username] = user
        
        if self._update_gist_content(db):
            return True, f"Пользователь {username} обновлён"
        return False, "Ошибка сохранения"
    
    def delete_user(self, username: str) -> tuple[bool, str]:
        """Удаляет пользователя (только для админа)"""
        if not self.is_admin:
            return False, "Недостаточно прав"
        
        db = self._get_gist_content()
        if not db:
            return False, "Не удалось подключиться к серверу"
        
        if username not in db.get("users", {}):
            return False, "Пользователь не найден"
        
        del db["users"][username]
        
        # Удаляем сессию если есть
        if username in db.get("active_sessions", {}):
            del db["active_sessions"][username]
        
        if self._update_gist_content(db):
            return True, f"Пользователь {username} удалён"
        return False, "Ошибка сохранения"
    
    def get_all_users(self) -> List[Dict]:
        """Получает список всех пользователей (только для админа)"""
        if not self.is_admin:
            return []
        
        db = self._get_gist_content()
        if not db:
            return []
        
        users = []
        for username, data in db.get("users", {}).items():
            user_info = {
                "username": username,
                "is_admin": data.get("is_admin", False),
                "enabled": data.get("enabled", True),
                "permissions": data.get("permissions", {}),
                "created_at": data.get("created_at", ""),
                "is_online": username in db.get("active_sessions", {})
            }
            
            # Добавляем информацию о сессии
            if username in db.get("active_sessions", {}):
                session = db["active_sessions"][username]
                user_info["last_seen"] = session.get("last_seen", "")
                user_info["platform"] = session.get("platform", "")
                user_info["app_version"] = session.get("app_version", "")
            
            users.append(user_info)
        
        return users
    
    def get_active_sessions(self) -> List[Dict]:
        """Получает список активных сессий (только для админа)"""
        if not self.is_admin:
            return []
        
        db = self._get_gist_content()
        if not db:
            return []
        
        sessions = []
        for username, session in db.get("active_sessions", {}).items():
            sessions.append({
                "username": username,
                **session
            })
        
        return sessions
    
    # ==================== АВТООБНОВЛЕНИЯ ====================
    
    def check_for_updates_gist(self) -> Optional[Dict]:
        """Проверяет наличие обновлений через Gist (основной метод)"""
        try:
            db = self._get_gist_content()
            if not db:
                return None
            
            latest_version = db.get("app_version", APP_VERSION)
            update_info = db.get("update_info", {})
            
            if latest_version and self._compare_versions(latest_version, APP_VERSION) > 0:
                return {
                    "version": latest_version,
                    "current_version": APP_VERSION,
                    "name": update_info.get("name", f"Версия {latest_version}"),
                    "body": update_info.get("description", ""),
                    "download_url": update_info.get("download_url", ""),
                    "published_at": update_info.get("published_at", "")
                }
            
            return None
        except:
            return None
    
    def _compare_versions(self, v1: str, v2: str) -> int:
        """Сравнивает версии. 1 если v1 > v2, -1 если v1 < v2, 0 если равны"""
        try:
            parts1 = [int(x) for x in v1.split(".")]
            parts2 = [int(x) for x in v2.split(".")]
            
            for i in range(max(len(parts1), len(parts2))):
                p1 = parts1[i] if i < len(parts1) else 0
                p2 = parts2[i] if i < len(parts2) else 0
                
                if p1 > p2:
                    return 1
                elif p1 < p2:
                    return -1
            return 0
        except:
            return 0
    
    def publish_update(self, new_version: str, description: str = "", download_url: str = "") -> tuple[bool, str]:
        """Публикует новую версию (только для админа)"""
        if not self.is_admin:
            return False, "Недостаточно прав"
        
        db = self._get_gist_content()
        if not db:
            return False, "Не удалось подключиться к серверу"
        
        db["app_version"] = new_version
        db["update_info"] = {
            "name": f"Версия {new_version}",
            "description": description,
            "download_url": download_url,
            "published_at": datetime.now().isoformat(),
            "published_by": self.current_user.get("username", "admin")
        }
        
        if self._update_gist_content(db):
            return True, f"Версия {new_version} опубликована"
        return False, "Ошибка сохранения"
    
    def get_current_server_version(self) -> str:
        """Получает текущую версию с сервера"""
        try:
            db = self._get_gist_content()
            if db:
                return db.get("app_version", APP_VERSION)
        except:
            pass
        return APP_VERSION
    
    def check_for_updates(self) -> Optional[Dict]:
        """Проверяет наличие обновлений (сначала Gist, потом GitHub)"""
        # Сначала проверяем через Gist
        update = self.check_for_updates_gist()
        if update:
            return update
        
        # Fallback на GitHub releases
        try:
            response = requests.get(
                f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                timeout=10
            )
            
            if response.status_code == 200:
                release = response.json()
                latest_version = release.get("tag_name", "").lstrip("v")
                
                if latest_version and self._compare_versions(latest_version, APP_VERSION) > 0:
                    return {
                        "version": latest_version,
                        "current_version": APP_VERSION,
                        "name": release.get("name", ""),
                        "body": release.get("body", ""),
                        "download_url": release.get("zipball_url", ""),
                        "published_at": release.get("published_at", "")
                    }
        except:
            pass
        
        return None
    
    def download_update(self, download_url: str, target_path: str) -> bool:
        """Скачивает обновление"""
        try:
            response = requests.get(download_url, stream=True, timeout=60)
            if response.status_code == 200:
                with open(target_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                return True
        except:
            pass
        return False


# Глобальный экземпляр менеджера лицензий
license_manager = LicenseManager()


def require_internet(func):
    """Декоратор для проверки интернета"""
    def wrapper(*args, **kwargs):
        if not LicenseManager.check_internet_connection():
            raise ConnectionError("Требуется подключение к интернету")
        return func(*args, **kwargs)
    return wrapper


def require_permission(permission: str):
    """Декоратор для проверки разрешения"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            if not license_manager.check_permission(permission):
                raise PermissionError(f"Нет доступа к функции: {permission}")
            return func(*args, **kwargs)
        return wrapper
    return decorator


if __name__ == "__main__":
    # Тест
    print("=== Тест LicenseManager ===")
    print(f"Интернет: {LicenseManager.check_internet_connection()}")
    print(f"Machine ID: {license_manager.get_machine_id()}")
