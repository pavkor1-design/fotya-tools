#!/usr/bin/env python3
"""
Окно входа и админ-панель FotyaTools
"""

import customtkinter as ctk
from tkinter import messagebox
import threading
from license_manager import license_manager, APP_VERSION

COLORS = {
    "bg_primary": "#0f0f1a",
    "bg_secondary": "#1a1a2e", 
    "primary": "#6366f1",
    "success": "#22c55e",
    "danger": "#ef4444",
    "text_primary": "#ffffff",
    "text_secondary": "#94a3b8"
}

class LoginWindow(ctk.CTk):
    """Окно входа в приложение"""
    
    def __init__(self, on_success_callback=None, skip_auto_login=False):
        super().__init__()
        self.on_success = on_success_callback
        self.skip_auto_login = skip_auto_login
        self.title("FotyaTools - Вход")
        self.geometry("400x600")
        self.configure(fg_color=COLORS["bg_primary"])
        self.resizable(False, False)
        
        # Центрируем окно
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 400) // 2
        y = (self.winfo_screenheight() - 600) // 2
        self.geometry(f"400x600+{x}+{y}")
        
        self._create_ui()
        self._check_internet_and_auto_login()
    
    def _create_ui(self):
        # Логотип
        ctk.CTkLabel(self, text="🤖", font=ctk.CTkFont(size=60)).pack(pady=(40, 10))
        ctk.CTkLabel(self, text="FotyaTools", font=ctk.CTkFont(size=28, weight="bold"),
                    text_color=COLORS["text_primary"]).pack()
        ctk.CTkLabel(self, text=f"v{APP_VERSION}", font=ctk.CTkFont(size=12),
                    text_color=COLORS["text_secondary"]).pack(pady=(0, 30))
        
        # Статус интернета
        self.internet_label = ctk.CTkLabel(self, text="⏳ Проверка подключения...",
                                           font=ctk.CTkFont(size=12),
                                           text_color=COLORS["text_secondary"])
        self.internet_label.pack(pady=5)
        
        # Форма входа
        form = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], corner_radius=12)
        form.pack(padx=40, pady=20, fill="x")
        
        ctk.CTkLabel(form, text="Логин", font=ctk.CTkFont(size=14)).pack(anchor="w", padx=20, pady=(20, 5))
        self.username_entry = ctk.CTkEntry(form, height=40, font=ctk.CTkFont(size=14))
        self.username_entry.pack(fill="x", padx=20)
        
        ctk.CTkLabel(form, text="Пароль", font=ctk.CTkFont(size=14)).pack(anchor="w", padx=20, pady=(15, 5))
        self.password_entry = ctk.CTkEntry(form, height=40, font=ctk.CTkFont(size=14), show="•")
        self.password_entry.pack(fill="x", padx=20)
        
        self.login_btn = ctk.CTkButton(form, text="Войти", height=45, font=ctk.CTkFont(size=16, weight="bold"),
                                       fg_color=COLORS["primary"], command=self._login)
        self.login_btn.pack(fill="x", padx=20, pady=20)
        
        self.status_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=12),
                                         text_color=COLORS["danger"])
        self.status_label.pack(pady=10)
        
        # Enter для входа
        self.password_entry.bind("<Return>", lambda e: self._login())
        self.username_entry.bind("<Return>", lambda e: self.password_entry.focus())
    
    def _check_internet_and_auto_login(self):
        """Проверяет интернет и пытается автоматически войти"""
        def check():
            if not license_manager.check_internet_connection():
                self.after(0, lambda: self.internet_label.configure(
                    text="❌ Нет подключения к интернету", text_color=COLORS["danger"]))
                self.after(0, lambda: self.login_btn.configure(state="disabled"))
                return
            
            self.after(0, lambda: self.internet_label.configure(
                text="✅ Подключение установлено", text_color=COLORS["success"]))
            
            # Пытаемся автоматически войти (если не пропущено)
            if not self.skip_auto_login:
                self.after(0, lambda: self.status_label.configure(
                    text="🔄 Проверка сохранённой сессии...", text_color=COLORS["text_secondary"]))
                
                success, message = license_manager.try_auto_login()
                
                if success:
                    self.after(0, lambda: self.status_label.configure(
                        text=f"✅ {message}", text_color=COLORS["success"]))
                    self.after(500, self._on_login_success)
                    return
                else:
                    self.after(0, lambda: self.status_label.configure(text=""))
            
            self.after(0, lambda: self.login_btn.configure(state="normal"))
        
        self.login_btn.configure(state="disabled")
        threading.Thread(target=check, daemon=True).start()
    
    def _login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        
        if not username or not password:
            self.status_label.configure(text="Введите логин и пароль")
            return
        
        self.login_btn.configure(state="disabled", text="Вход...")
        self.status_label.configure(text="")
        
        def do_login():
            success, message = license_manager.login(username, password)
            self.after(0, lambda: self._login_result(success, message))
        
        threading.Thread(target=do_login, daemon=True).start()
    
    def _login_result(self, success, message):
        self.login_btn.configure(state="normal", text="Войти")
        
        if success:
            self.status_label.configure(text="✅ " + message, text_color=COLORS["success"])
            self.after(500, self._on_login_success)
        else:
            self.status_label.configure(text="❌ " + message, text_color=COLORS["danger"])
    
    def _on_login_success(self):
        self.destroy()
        if self.on_success:
            self.on_success()


class AdminPanel(ctk.CTkToplevel):
    """Админ-панель для управления пользователями"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Админ-панель")
        self.geometry("900x700")
        self.configure(fg_color=COLORS["bg_primary"])
        self.auto_refresh = True
        
        self._create_ui()
        self._load_users()
        self._start_auto_refresh()
    
    def _create_ui(self):
        # Заголовок
        header = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], height=60)
        header.pack(fill="x", padx=10, pady=10)
        header.pack_propagate(False)
        
        ctk.CTkLabel(header, text="👑 Админ-панель", font=ctk.CTkFont(size=20, weight="bold")).pack(side="left", padx=20, pady=15)
        ctk.CTkButton(header, text="🔄", width=40, command=self._refresh_all).pack(side="right", padx=5)
        ctk.CTkButton(header, text="➕ Добавить", width=100, fg_color=COLORS["success"],
                     command=self._add_user_dialog).pack(side="right", padx=5)
        ctk.CTkButton(header, text="📦 Версия", width=90, fg_color=COLORS["primary"],
                     command=self._publish_update_dialog).pack(side="right", padx=5)
        
        # Вкладки
        self.tabview = ctk.CTkTabview(self, fg_color=COLORS["bg_secondary"])
        self.tabview.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        self.tabview.add("👥 Пользователи")
        self.tabview.add("🟢 Онлайн")
        self.tabview.add("📈 Статистика")
        
        # Вкладка пользователей
        self.users_frame = ctk.CTkScrollableFrame(self.tabview.tab("👥 Пользователи"), fg_color="transparent")
        self.users_frame.pack(fill="both", expand=True)
        
        # Вкладка онлайн
        self._create_online_tab()
        
        # Вкладка статистики
        self._create_stats_tab()
    
    def _create_online_tab(self):
        """Создаёт вкладку онлайн пользователей"""
        tab = self.tabview.tab("🟢 Онлайн")
        
        # Статус
        self.online_status = ctk.CTkLabel(tab, text="Активных пользователей: 0",
                                          font=ctk.CTkFont(size=14, weight="bold"))
        self.online_status.pack(pady=10)
        
        # Список онлайн
        self.online_frame = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.online_frame.pack(fill="both", expand=True)
    
    def _create_stats_tab(self):
        """Создаёт вкладку статистики с визуализацией"""
        tab = self.tabview.tab("📈 Статистика")
        
        # Заголовок
        header = ctk.CTkFrame(tab, fg_color=COLORS["bg_primary"], height=50)
        header.pack(fill="x", pady=5)
        header.pack_propagate(False)
        
        ctk.CTkLabel(header, text="📈 Статистика активности",
                    font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=15, pady=10)
        
        ctk.CTkButton(header, text="🔄 Обновить", width=100,
                     command=self._load_stats).pack(side="right", padx=10, pady=10)
        
        # Контейнер для статистики
        self.stats_frame = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.stats_frame.pack(fill="both", expand=True, pady=5)
    
    def _load_stats(self):
        """Загружает и отображает статистику по пользователям"""
        for widget in self.stats_frame.winfo_children():
            widget.destroy()
        
        from datetime import datetime, timedelta
        
        # Получаем все события и пользователей
        events = license_manager.get_user_analytics()
        users = license_manager.get_all_users()
        sessions = license_manager.get_active_sessions()
        
        # Создаём словарь сессий по имени
        sessions_dict = {s.get("username"): s for s in sessions}
        
        # Считаем события по пользователям
        user_events = {}
        for event in events:
            username = event.get("username", "unknown")
            if username not in user_events:
                user_events[username] = {"total": 0, "logins": 0, "actions": 0, "events": []}
            user_events[username]["total"] += 1
            user_events[username]["events"].append(event)
            if event.get("type") == "login":
                user_events[username]["logins"] += 1
            elif event.get("type") == "action":
                user_events[username]["actions"] += 1
        
        # === Карточки пользователей ===
        for user in users:
            username = user.get("username", "")
            stats = user_events.get(username, {"total": 0, "logins": 0, "actions": 0, "events": []})
            session = sessions_dict.get(username, {})
            
            self._create_user_stats_card(username, user, stats, session)
    
    def _create_stat_card(self, parent, icon, title, value, col):
        """Создаёт карточку статистики"""
        card = ctk.CTkFrame(parent, fg_color=COLORS["bg_secondary"], corner_radius=8, width=120, height=80)
        card.grid(row=0, column=col, padx=5, pady=5, sticky="nsew")
        card.grid_propagate(False)
        
        parent.grid_columnconfigure(col, weight=1)
        
        ctk.CTkLabel(card, text=icon, font=ctk.CTkFont(size=24)).pack(pady=(10, 0))
        ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=20, weight="bold")).pack()
        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=10),
                    text_color=COLORS["text_secondary"]).pack()
    
    def _create_user_stats_card(self, username, user, stats, session):
        """Создаёт карточку статистики пользователя"""
        from datetime import datetime
        
        card = ctk.CTkFrame(self.stats_frame, fg_color=COLORS["bg_primary"], corner_radius=10)
        card.pack(fill="x", padx=5, pady=5)
        
        # Заголовок с именем и статусом
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(10, 5))
        
        # Статус онлайн
        is_online = session.get("status") == "online"
        status_icon = "🟢" if is_online else "⚫"
        
        # Роль
        role_icon = "👑" if user.get("is_admin") else "👤"
        
        ctk.CTkLabel(header, text=f"{status_icon} {role_icon} {username}",
                    font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        
        # Время последней активности
        last_seen = session.get("last_seen", "")
        if last_seen:
            try:
                dt = datetime.fromisoformat(last_seen)
                last_str = dt.strftime("%d.%m %H:%M")
            except:
                last_str = "-"
        else:
            last_str = "Никогда"
        
        ctk.CTkLabel(header, text=f"Последняя активность: {last_str}",
                    font=ctk.CTkFont(size=11), text_color=COLORS["text_secondary"]).pack(side="right")
        
        # Статистика в цифрах
        stats_row = ctk.CTkFrame(card, fg_color="transparent")
        stats_row.pack(fill="x", padx=15, pady=5)
        
        # Мини-карточки статистики
        mini_stats = [
            ("🔑", f"{stats['logins']}", "Входов"),
            ("⚡", f"{stats['actions']}", "Действий"),
            ("📊", f"{stats['total']}", "Всего"),
        ]
        
        for i, (icon, value, label) in enumerate(mini_stats):
            mini = ctk.CTkFrame(stats_row, fg_color=COLORS["bg_secondary"], corner_radius=6, width=100, height=50)
            mini.pack(side="left", padx=5, pady=5)
            mini.pack_propagate(False)
            
            ctk.CTkLabel(mini, text=f"{icon} {value}", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(8, 0))
            ctk.CTkLabel(mini, text=label, font=ctk.CTkFont(size=9), text_color=COLORS["text_secondary"]).pack()
        
        # Последние 5 действий пользователя
        if stats.get("events"):
            events_frame = ctk.CTkFrame(card, fg_color=COLORS["bg_secondary"], corner_radius=6)
            events_frame.pack(fill="x", padx=15, pady=(5, 10))
            
            ctk.CTkLabel(events_frame, text="Последние действия:",
                        font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=10, pady=(8, 3))
            
            for event in stats["events"][:5]:
                event_type = event.get("type", "action")
                icons = {"login": "🟢", "logout": "🔴", "action": "⚡"}
                icon = icons.get(event_type, "📌")
                
                timestamp = event.get("timestamp", "")[:16].replace("T", " ")
                description = event.get("description", "")[:40]
                
                ctk.CTkLabel(events_frame, text=f"  {icon} {timestamp} — {description}",
                            font=ctk.CTkFont(size=10), text_color=COLORS["text_secondary"]).pack(anchor="w", padx=10)
            
            # Отступ снизу
            ctk.CTkLabel(events_frame, text="").pack(pady=3)
    
    def _create_mini_event(self, parent, event):
        """Создаёт мини-строку события"""
        row = ctk.CTkFrame(parent, fg_color="transparent", height=25)
        row.pack(fill="x", padx=15, pady=1)
        row.pack_propagate(False)
        
        event_type = event.get("type", "action")
        icons = {"login": "🟢", "logout": "🔴", "action": "⚡"}
        icon = icons.get(event_type, "📌")
        
        timestamp = event.get("timestamp", "")[:16].replace("T", " ")
        username = event.get("username", "")
        description = event.get("description", "")[:30]
        
        ctk.CTkLabel(row, text=f"{icon} {timestamp} | {username}: {description}",
                    font=ctk.CTkFont(size=10), text_color=COLORS["text_secondary"]).pack(side="left")
    
    def _start_auto_refresh(self):
        """Запускает автообновление каждые 10 секунд"""
        def refresh():
            if self.auto_refresh and self.winfo_exists():
                if hasattr(self, 'online_frame'):
                    self._load_online()
                self.after(10000, refresh)
        
        self.after(10000, refresh)
    
    def _refresh_all(self):
        """Обновляет все вкладки"""
        self._load_users()
        if hasattr(self, 'analytics_frame'):
            self._load_analytics()
        if hasattr(self, 'online_frame'):
            self._load_online()
    
    def destroy(self):
        self.auto_refresh = False
        super().destroy()
    
    def _load_users(self):
        for widget in self.users_frame.winfo_children():
            widget.destroy()
        
        users = license_manager.get_all_users()
        
        if not users:
            ctk.CTkLabel(self.users_frame, text="Нет пользователей", 
                        font=ctk.CTkFont(size=14)).pack(pady=20)
            return
        
        for user in users:
            self._create_user_row(user)
    
    def _create_user_row(self, user):
        row = ctk.CTkFrame(self.users_frame, fg_color=COLORS["bg_primary"], corner_radius=8, height=60)
        row.pack(fill="x", pady=5, padx=5)
        row.pack_propagate(False)
        
        # Статус онлайн
        status = "��" if user.get("is_online") else "⚫"
        ctk.CTkLabel(row, text=status, font=ctk.CTkFont(size=16)).pack(side="left", padx=10)
        
        # Имя и роль
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="y", padx=10)
        
        name_text = user["username"]
        if user.get("is_admin"):
            name_text += " 👑"
        ctk.CTkLabel(info, text=name_text, font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w")
        
        perms = []
        if user.get("permissions", {}).get("ai_enabled"):
            perms.append("AI")
        if user.get("permissions", {}).get("app_enabled"):
            perms.append("App")
        ctk.CTkLabel(info, text=f"Доступ: {', '.join(perms) if perms else 'Нет'}",
                    font=ctk.CTkFont(size=11), text_color=COLORS["text_secondary"]).pack(anchor="w")
        
        # Кнопки
        btns = ctk.CTkFrame(row, fg_color="transparent")
        btns.pack(side="right", padx=10)
        
        if user.get("enabled", True):
            ctk.CTkButton(btns, text="🔒", width=35, fg_color=COLORS["danger"],
                         command=lambda u=user["username"]: self._toggle_user(u, False)).pack(side="left", padx=2)
        else:
            ctk.CTkButton(btns, text="🔓", width=35, fg_color=COLORS["success"],
                         command=lambda u=user["username"]: self._toggle_user(u, True)).pack(side="left", padx=2)
        
        ctk.CTkButton(btns, text="✏️", width=35, command=lambda u=user: self._edit_user_dialog(u)).pack(side="left", padx=2)
        ctk.CTkButton(btns, text="🗑️", width=35, fg_color=COLORS["danger"],
                     command=lambda u=user["username"]: self._delete_user(u)).pack(side="left", padx=2)
    
    def _toggle_user(self, username, enabled):
        success, msg = license_manager.update_user(username, enabled=enabled)
        if success:
            self._load_users()
        else:
            messagebox.showerror("Ошибка", msg)
    
    def _delete_user(self, username):
        if messagebox.askyesno("Удаление", f"Удалить пользователя {username}?"):
            success, msg = license_manager.delete_user(username)
            if success:
                self._load_users()
            else:
                messagebox.showerror("Ошибка", msg)
    
    def _add_user_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Новый пользователь")
        dialog.geometry("350x400")
        dialog.configure(fg_color=COLORS["bg_primary"])
        dialog.grab_set()
        
        ctk.CTkLabel(dialog, text="Логин:").pack(anchor="w", padx=20, pady=(20, 5))
        username_entry = ctk.CTkEntry(dialog, height=35)
        username_entry.pack(fill="x", padx=20)
        
        ctk.CTkLabel(dialog, text="Пароль:").pack(anchor="w", padx=20, pady=(15, 5))
        password_entry = ctk.CTkEntry(dialog, height=35)
        password_entry.pack(fill="x", padx=20)
        
        is_admin_var = ctk.BooleanVar()
        ai_var = ctk.BooleanVar(value=True)
        app_var = ctk.BooleanVar(value=True)
        
        ctk.CTkCheckBox(dialog, text="Администратор", variable=is_admin_var).pack(anchor="w", padx=20, pady=(15, 5))
        ctk.CTkCheckBox(dialog, text="Доступ к AI", variable=ai_var).pack(anchor="w", padx=20, pady=5)
        ctk.CTkCheckBox(dialog, text="Доступ к приложению", variable=app_var).pack(anchor="w", padx=20, pady=5)
        
        def create():
            username = username_entry.get().strip()
            password = password_entry.get()
            if not username or not password:
                messagebox.showwarning("Внимание", "Заполните все поля")
                return
            
            perms = {"ai_enabled": ai_var.get(), "app_enabled": app_var.get()}
            success, msg = license_manager.create_user(username, password, is_admin_var.get(), perms)
            
            if success:
                dialog.destroy()
                self._load_users()
            else:
                messagebox.showerror("Ошибка", msg)
        
        ctk.CTkButton(dialog, text="Создать", height=40, fg_color=COLORS["success"],
                     command=create).pack(fill="x", padx=20, pady=20)
    
    def _edit_user_dialog(self, user):
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Редактирование: {user['username']}")
        dialog.geometry("350x350")
        dialog.configure(fg_color=COLORS["bg_primary"])
        dialog.grab_set()
        
        ctk.CTkLabel(dialog, text=f"Пользователь: {user['username']}",
                    font=ctk.CTkFont(size=16, weight="bold")).pack(pady=20)
        
        ctk.CTkLabel(dialog, text="Новый пароль (оставьте пустым):").pack(anchor="w", padx=20, pady=(10, 5))
        password_entry = ctk.CTkEntry(dialog, height=35)
        password_entry.pack(fill="x", padx=20)
        
        ai_var = ctk.BooleanVar(value=user.get("permissions", {}).get("ai_enabled", True))
        app_var = ctk.BooleanVar(value=user.get("permissions", {}).get("app_enabled", True))
        
        ctk.CTkCheckBox(dialog, text="Доступ к AI", variable=ai_var).pack(anchor="w", padx=20, pady=(15, 5))
        ctk.CTkCheckBox(dialog, text="Доступ к приложению", variable=app_var).pack(anchor="w", padx=20, pady=5)
        
        def save():
            kwargs = {"ai_enabled": ai_var.get(), "app_enabled": app_var.get()}
            if password_entry.get():
                kwargs["password"] = password_entry.get()
            
            success, msg = license_manager.update_user(user["username"], **kwargs)
            if success:
                dialog.destroy()
                self._load_users()
            else:
                messagebox.showerror("Ошибка", msg)
        
        ctk.CTkButton(dialog, text="Сохранить", height=40, fg_color=COLORS["primary"],
                     command=save).pack(fill="x", padx=20, pady=20)
    
    def _load_online(self):
        """Загружает онлайн пользователей"""
        for widget in self.online_frame.winfo_children():
            widget.destroy()
        
        sessions = license_manager.get_active_sessions()
        
        # Фильтруем по статусу и времени
        from datetime import datetime, timedelta
        now = datetime.now()
        online_users = []
        
        for session in sessions:
            try:
                # Проверяем статус или время последней активности
                status = session.get("status", "")
                last_seen_str = session.get("last_seen", "")
                
                if last_seen_str:
                    last_seen = datetime.fromisoformat(last_seen_str)
                    time_diff = now - last_seen
                    
                    # Онлайн если status=online ИЛИ активность < 5 минут
                    if status == "online" or time_diff < timedelta(minutes=5):
                        session["is_online"] = True
                    else:
                        session["is_online"] = False
                else:
                    session["is_online"] = (status == "online")
                
                online_users.append(session)
            except Exception as e:
                session["is_online"] = False
                online_users.append(session)
        
        # Сортируем: онлайн первые, потом по времени
        online_users.sort(key=lambda x: (not x.get("is_online", False), x.get("last_seen", "") or ""), reverse=True)
        
        online_count = sum(1 for u in online_users if u.get("is_online"))
        self.online_status.configure(text=f"🟢 Активных пользователей: {online_count} из {len(online_users)}")
        
        if not online_users:
            ctk.CTkLabel(self.online_frame, text="Нет данных о сессиях",
                        font=ctk.CTkFont(size=14)).pack(pady=20)
            return
        
        for session in online_users:
            self._create_online_row(session)
    
    def _create_online_row(self, session):
        """Создаёт строку онлайн пользователя"""
        row = ctk.CTkFrame(self.online_frame, fg_color=COLORS["bg_primary"], corner_radius=8, height=70)
        row.pack(fill="x", pady=3, padx=5)
        row.pack_propagate(False)
        
        # Статус
        is_online = session.get("is_online", False)
        status_color = COLORS["success"] if is_online else COLORS["text_secondary"]
        status_text = "🟢" if is_online else "⚫"
        
        ctk.CTkLabel(row, text=status_text, font=ctk.CTkFont(size=20)).pack(side="left", padx=15)
        
        # Информация
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="y", padx=10)
        
        username = session.get("username", "Unknown")
        ctk.CTkLabel(info, text=username,
                    font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", pady=(10, 0))
        
        # Детали
        platform_name = session.get("platform", "")
        app_version = session.get("app_version", "")
        
        # Время входа/выхода
        login_time = session.get("login_time", "")
        last_seen = session.get("last_seen", "")
        
        try:
            from datetime import datetime
            if login_time:
                login_dt = datetime.fromisoformat(login_time)
                login_str = login_dt.strftime("%H:%M:%S")
            else:
                login_str = "-"
            
            if last_seen:
                last_dt = datetime.fromisoformat(last_seen)
                last_str = last_dt.strftime("%H:%M:%S")
            else:
                last_str = "-"
        except:
            login_str = "-"
            last_str = "-"
        
        details = f"{platform_name} | v{app_version} | Вход: {login_str} | Активность: {last_str}"
        ctk.CTkLabel(info, text=details,
                    font=ctk.CTkFont(size=10),
                    text_color=COLORS["text_secondary"]).pack(anchor="w")
    
    def _publish_update_dialog(self):
        """Диалог публикации новой версии с полной загрузкой на GitHub"""
        from license_manager import APP_VERSION
        
        dialog = ctk.CTkToplevel(self)
        dialog.title("Опубликовать версию")
        dialog.geometry("450x600")
        dialog.configure(fg_color=COLORS["bg_primary"])
        dialog.grab_set()
        
        ctk.CTkLabel(dialog, text="� Публикация обновления",
                    font=ctk.CTkFont(size=18, weight="bold")).pack(pady=20)
        
        # Текущая версия
        ctk.CTkLabel(dialog, text=f"Текущая версия в коде: {APP_VERSION}",
                    font=ctk.CTkFont(size=12),
                    text_color=COLORS["text_secondary"]).pack(pady=5)
        
        # Серверная версия
        server_version = license_manager.get_current_server_version()
        ctk.CTkLabel(dialog, text=f"Версия на сервере: {server_version}",
                    font=ctk.CTkFont(size=12),
                    text_color=COLORS["text_secondary"]).pack(pady=5)
        
        ctk.CTkLabel(dialog, text="Новая версия:").pack(anchor="w", padx=20, pady=(15, 5))
        version_entry = ctk.CTkEntry(dialog, height=35)
        version_entry.pack(fill="x", padx=20)
        version_entry.insert(0, self._increment_version(server_version))
        
        ctk.CTkLabel(dialog, text="Описание изменений:").pack(anchor="w", padx=20, pady=(15, 5))
        desc_entry = ctk.CTkTextbox(dialog, height=80)
        desc_entry.pack(fill="x", padx=20)
        
        # Чекбокс для полной публикации
        full_publish_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(dialog, text="📦 Упаковать и загрузить на GitHub", 
                       variable=full_publish_var,
                       font=ctk.CTkFont(size=12)).pack(anchor="w", padx=20, pady=10)
        
        ctk.CTkLabel(dialog, text="⚠️ При полной публикации файлы приложения\nбудут загружены на GitHub Releases",
                    font=ctk.CTkFont(size=10),
                    text_color=COLORS["text_secondary"]).pack(pady=5)
        
        status_label = ctk.CTkLabel(dialog, text="", font=ctk.CTkFont(size=11))
        status_label.pack(pady=10)
        
        publish_btn = ctk.CTkButton(dialog, text="🚀 Опубликовать", height=40, fg_color=COLORS["success"])
        
        def update_status(text, color=None):
            """Helper для обновления статуса из любого потока"""
            try:
                if dialog.winfo_exists():
                    status_label.configure(text=text, text_color=color or COLORS["text_secondary"])
                    dialog.update_idletasks()
            except:
                pass
        
        def publish():
            new_version = version_entry.get().strip()
            description = desc_entry.get("1.0", "end").strip()
            
            if not new_version:
                status_label.configure(text="❌ Введите версию", text_color=COLORS["danger"])
                return
            
            publish_btn.configure(state="disabled", text="⏳ Публикация...")
            status_label.configure(text="📦 Подготовка...", text_color=COLORS["text_secondary"])
            dialog.update()
            
            if full_publish_var.get():
                # Полная публикация с загрузкой файлов
                def do_full_publish():
                    try:
                        # Callback для обновления статуса из потока публикации
                        def on_status(text):
                            dialog.after(0, lambda t=text: update_status(t))
                        
                        from auto_updater import publish_update
                        success, msg = publish_update(new_version, description, status_callback=on_status)
                        
                        # Вызываем finish_publish в главном потоке
                        dialog.after(0, lambda s=success, m=msg: finish_publish(s, m))
                    except Exception as e:
                        import traceback
                        error_msg = f"{str(e)}\n{traceback.format_exc()[:200]}"
                        dialog.after(0, lambda: finish_publish(False, error_msg))
                
                import threading
                t = threading.Thread(target=do_full_publish, daemon=True)
                t.start()
            else:
                # Только обновление версии в Gist
                success, msg = license_manager.publish_update(new_version, description, "")
                finish_publish(success, msg)
        
        def finish_publish(success, msg):
            try:
                if not dialog.winfo_exists():
                    return
                publish_btn.configure(state="normal", text="🚀 Опубликовать")
                if success:
                    status_label.configure(text="✅ " + str(msg), text_color=COLORS["success"])
                    dialog.after(2000, dialog.destroy)
                else:
                    status_label.configure(text="❌ " + str(msg)[:100], text_color=COLORS["danger"])
            except Exception as e:
                print(f"finish_publish error: {e}")
        
        publish_btn.configure(command=publish)
        publish_btn.pack(fill="x", padx=20, pady=10)
    
    def _increment_version(self, version: str) -> str:
        """Увеличивает patch версию"""
        try:
            parts = version.split(".")
            parts[-1] = str(int(parts[-1]) + 1)
            return ".".join(parts)
        except:
            return version


if __name__ == "__main__":
    app = LoginWindow()
    app.mainloop()
