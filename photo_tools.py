#!/usr/bin/env python3
"""
Photo Tools - Современный интерфейс с CustomTkinter
Apple-style дизайн с Material Design палитрой
Helvetica шрифт, плавные анимации
"""

import os
import sys
import ssl
import shutil

# === ИСПРАВЛЕНИЕ SSL ДЛЯ macOS ===
# На некоторых Mac с Python 3.6+ SSL сертификаты не установлены
# Это вызывает ошибку CERTIFICATE_VERIFY_FAILED при работе с API
try:
    import certifi
    os.environ['SSL_CERT_FILE'] = certifi.where()
    os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
except ImportError:
    pass

# Альтернативный метод - отключение проверки SSL (менее безопасно, но работает)
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

import requests
import queue
import traceback
from threading import Thread
from PIL import Image, ImageDraw, ImageFont, ImageTk, ImageEnhance
import customtkinter as ctk
import numpy as np
from tkinter import filedialog, messagebox
try:
    from scipy.optimize import minimize
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
import fal_client
import webview
import threading
import cv2
import webbrowser
import subprocess

# Kling Workspace - VDS сервер
KLING_VDS_HOST = "5.129.203.43"
KLING_VDS_NOVNC_PORT = 6080
KLING_VDS_FILES_PORT = 8080
KLING_SESSION_PORT = 8081
# Главная точка входа - Session Manager с авторизацией и очередью
KLING_WORKSPACE_URL = f"http://{KLING_VDS_HOST}:{KLING_SESSION_PORT}"
# noVNC напрямую (для внутреннего использования)
KLING_NOVNC_URL = f"http://{KLING_VDS_HOST}:{KLING_VDS_NOVNC_PORT}/vnc.html?autoconnect=true&resize=scale&quality=9&compression=6"
KLING_FILES_URL = f"http://{KLING_VDS_HOST}:{KLING_VDS_FILES_PORT}"

# Локальный Kling Workspace (fallback)
KLING_WORKSPACE_AVAILABLE = False
KLING_DOWNLOADS_DIR = None
try:
    from kling_workspace.config import DOWNLOADS_DIR as KLING_DOWNLOADS_DIR
    KLING_WORKSPACE_AVAILABLE = True
except ImportError:
    pass

# Lensfun для коррекции объективов (как в Darktable)
LENSFUN_AVAILABLE = False
try:
    import lensfunpy
    LENSFUN_AVAILABLE = True
except ImportError:
    pass

# Модуль коррекции перспективы (GIMP/Darktable алгоритмы)
try:
    from perspective_engine import (
        GIMPPerspective, DarktablePerspective, 
        AutoPerspective, GuidedUpright,
        apply_perspective_correction, auto_perspective_correction
    )
    PERSPECTIVE_ENGINE_AVAILABLE = True
except ImportError:
    PERSPECTIVE_ENGINE_AVAILABLE = False

# Точная реализация Darktable ashift
try:
    from darktable_perspective import DarktableAshift
    DARKTABLE_ASHIFT_AVAILABLE = True
except ImportError:
    DARKTABLE_ASHIFT_AVAILABLE = False

# Логирование
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('PhotoTools')
# Отключаем DEBUG для PIL
logging.getLogger('PIL').setLevel(logging.WARNING)

# Drag & Drop - будем использовать простой метод через clipboard/paste
DND_AVAILABLE = False
DND_FILES = None

# Pinch-to-zoom и Liquid Glass через PyObjC (macOS)
PINCH_ZOOM_AVAILABLE = False
LIQUID_GLASS_AVAILABLE = False
# ВРЕМЕННО ОТКЛЮЧЕНО ДЛЯ ОТЛАДКИ КРАША В БАНДЛЕ
# try:
#     import objc
#     from Cocoa import NSEvent, NSApplication, NSEventMaskMagnify
#     PINCH_ZOOM_AVAILABLE = True
#     logger.info("PyObjC available for pinch-to-zoom")
#     
#     # Liquid Glass blur effect (NSVisualEffectView)
#     try:
#         from AppKit import (
#             NSVisualEffectView, NSVisualEffectBlendingModeBehindWindow,
#             NSVisualEffectMaterialDark, NSVisualEffectStateActive,
#             NSWindow, NSColor, NSView
#         )
#         LIQUID_GLASS_AVAILABLE = True
#         logger.info("Liquid Glass blur available via NSVisualEffectView")
#     except ImportError:
#         logger.warning("NSVisualEffectView not available - Liquid Glass blur disabled")
# except ImportError:
#     logger.warning("PyObjC not available - pinch-to-zoom and Liquid Glass disabled")

# === macOS LIQUID GLASS ТЕМА ===
ctk.set_appearance_mode("dark")

# Liquid Glass цветовая схема - macOS Tahoe стиль
# Полупрозрачные материалы, адаптивные цвета, мягкие градиенты
COLORS = {
    # Акцентные цвета macOS
    "primary": "#007AFF",        # macOS Blue - системный акцент
    "primary_hover": "#0056CC",
    "secondary": "#5856D6",      # macOS Purple
    "secondary_hover": "#4240A8",
    "success": "#30D158",        # macOS Green
    "success_hover": "#28B84C",
    "warning": "#FF9F0A",        # macOS Orange
    "warning_hover": "#E68A00",
    "danger": "#FF453A",         # macOS Red
    "danger_hover": "#E03E35",
    "pink": "#FF375F",           # macOS Pink
    "pink_hover": "#E0304F",
    "teal": "#5AC8FA",           # macOS Teal/Cyan
    "cyan": "#64D2FF",           # macOS Light Blue
    
    # Фоны - непрозрачные серые
    "bg_dark": "#1C1C1E",        # Тёмный фон
    "bg_secondary": "#2C2C2E",   # Вторичный фон
    "bg_tertiary": "#3A3A3C",    # Карточки
    "bg_card": "#2C2C2E",        # Карточки
    "bg_glass": "#48484A",       # Серый
    "bg_glass_light": "#636366", # Светло-серый
    
    # Текст
    "text_primary": "#FFFFFF",   # Белый текст
    "text_secondary": "#98989D", # Чуть светлее для контраста
    "text_tertiary": "#636366",  # macOS Tertiary Label
    
    # Границы - тонкие светящиеся линии как в Liquid Glass
    "border": "#3D3D40",         # Граница с лёгким свечением
    "border_light": "#4A4A4D",   # Светлая граница
    
    # Эффекты Liquid Glass
    "glass_highlight": "#FFFFFF15",  # Блик сверху
    "glass_shadow": "#00000020",     # Мягкая тень
    "glass_glow": "#007AFF20",       # Свечение акцентного цвета
}

# San Francisco шрифт (системный на macOS) с fallback на Helvetica
FONT_FAMILY = "SF Pro Display"
FONT_FAMILY_ROUNDED = "SF Pro Rounded"
# Fallback если SF Pro не доступен
try:
    import tkinter.font as tkfont
    available_fonts = tkfont.families()
    if "SF Pro Display" not in available_fonts:
        FONT_FAMILY = "Helvetica Neue"
        FONT_FAMILY_ROUNDED = "Helvetica Neue"
except:
    FONT_FAMILY = "Helvetica Neue"
    FONT_FAMILY_ROUNDED = "Helvetica Neue"

FONTS = {
    "title": (FONT_FAMILY, 28, "bold"),
    "heading": (FONT_FAMILY, 20, "bold"),
    "subheading": (FONT_FAMILY, 16, "bold"),
    "body": (FONT_FAMILY, 14),
    "caption": (FONT_FAMILY, 12),
    "small": (FONT_FAMILY, 11),
    "button": (FONT_FAMILY, 14, "bold"),
    "button_large": (FONT_FAMILY, 16, "bold"),
}

# Liquid Glass параметры
GLASS_CORNER_RADIUS = 16        # Увеличенные скругления macOS
GLASS_CORNER_RADIUS_SMALL = 10
GLASS_CORNER_RADIUS_LARGE = 20
GLASS_BORDER_WIDTH = 1          # Тонкая граница

# API ключ
os.environ['FAL_KEY'] = "8b41b065-51b8-4877-8880-a809f89216dd:8353eacc4adddec908c50eea36dfe501"

MODELS = {
    "ESRGAN (универсальный)": "fal-ai/esrgan",
    "Clarity Upscaler": "fal-ai/clarity-upscaler",
    "Creative Upscaler": "fal-ai/creative-upscaler",
    "Recraft Crisp": "fal-ai/recraft/upscale/crisp",
    "Topaz Upscale": "fal-ai/topaz/upscale/image"
}


# === АНИМИРОВАННЫЕ КОМПОНЕНТЫ ===
def hex_to_rgb(hex_color):
    """Конвертирует HEX в RGB"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(rgb):
    """Конвертирует RGB в HEX"""
    return '#{:02x}{:02x}{:02x}'.format(int(rgb[0]), int(rgb[1]), int(rgb[2]))

def interpolate_color(color1, color2, factor):
    """Интерполяция между двумя цветами"""
    rgb1 = hex_to_rgb(color1)
    rgb2 = hex_to_rgb(color2)
    rgb = tuple(rgb1[i] + (rgb2[i] - rgb1[i]) * factor for i in range(3))
    return rgb_to_hex(rgb)


class AnimatedCard(ctk.CTkFrame):
    """Анимированная карточка с плавным переходом цветов и эффектами"""
    
    def __init__(self, master, text, icon, value, variable, 
                 inactive_color=None, active_color=None, **kwargs):
        self.inactive_color = inactive_color or COLORS["bg_tertiary"]
        self.active_color = active_color or COLORS["success"]
        self.base_width = 140
        self.base_height = 120
        
        super().__init__(master, fg_color=self.inactive_color, corner_radius=GLASS_CORNER_RADIUS, 
                        width=self.base_width, height=self.base_height, cursor="hand2", 
                        border_width=0, **kwargs)
        self.pack_propagate(False)
        
        self.value = value
        self.variable = variable
        self.animation_id = None
        self.scale_animation_id = None
        self.current_color = self.inactive_color
        self.current_scale = 1.0
        
        # Иконка
        self.icon_label = ctk.CTkLabel(self, text=icon, 
                                       font=ctk.CTkFont(family=FONT_FAMILY, size=28))
        self.icon_label.pack(pady=(18, 5))
        
        # Текст
        self.text_label = ctk.CTkLabel(self, text=text,
                                       font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
                                       text_color=COLORS["text_primary"])
        self.text_label.pack()
        
        # Подпись
        self.sub_label = ctk.CTkLabel(self, text=value,
                                      font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                                      text_color=COLORS["text_secondary"])
        self.sub_label.pack()
        
        # Привязываем клик и hover ко всем элементам
        for widget in [self, self.icon_label, self.text_label, self.sub_label]:
            widget.bind("<Button-1>", self.on_click)
            widget.bind("<Enter>", self.on_enter)
            widget.bind("<Leave>", self.on_leave)
        
        # Обновляем состояние при изменении переменной
        self.variable.trace_add("write", self.update_state)
        self.update_state()
    
    def on_enter(self, event=None):
        """Hover эффект - увеличение и свечение"""
        self.animate_scale(1.05)
        self.configure(border_width=2, border_color=self.active_color)
    
    def on_leave(self, event=None):
        """Убираем hover эффект"""
        self.animate_scale(1.0)
        is_selected = self.variable.get() == self.value
        if not is_selected:
            self.configure(border_width=0)
    
    def on_click(self, event=None):
        """Клик с подсветкой фона"""
        self.flash_animation()
        self.variable.set(self.value)
    
    def flash_animation(self):
        """Плавная вспышка фона при клике"""
        current = self.current_color
        bright_color = interpolate_color(current, "#ffffff", 0.5)
        steps = 6
        
        def flash_up(step):
            if step <= steps:
                factor = step / steps
                color = interpolate_color(current, bright_color, factor)
                self.configure(fg_color=color)
                self.after(20, lambda: flash_up(step + 1))
            else:
                flash_down(steps)
        
        def flash_down(step):
            if step >= 0:
                factor = step / steps
                color = interpolate_color(current, bright_color, factor)
                self.configure(fg_color=color)
                self.after(25, lambda: flash_down(step - 1))
            else:
                self.configure(fg_color=current)
        
        flash_up(1)
    
    def animate_scale(self, target_scale, duration=100, steps=6):
        """Плавная анимация масштаба"""
        if self.scale_animation_id:
            self.after_cancel(self.scale_animation_id)
        
        start_scale = self.current_scale
        step_duration = duration // steps
        
        def scale_step(step):
            if step <= steps:
                factor = step / steps
                factor = factor * factor * (3 - 2 * factor)
                new_scale = start_scale + (target_scale - start_scale) * factor
                self.set_scale(new_scale)
                self.scale_animation_id = self.after(step_duration, lambda: scale_step(step + 1))
            else:
                self.current_scale = target_scale
                self.scale_animation_id = None
        
        scale_step(1)
    
    def set_scale(self, scale):
        """Устанавливает масштаб карточки"""
        self.current_scale = scale
        new_width = int(self.base_width * scale)
        new_height = int(self.base_height * scale)
        self.configure(width=new_width, height=new_height)
    
    def update_state(self, *args):
        is_selected = self.variable.get() == self.value
        target_color = self.active_color if is_selected else self.inactive_color
        self.animate_to_color(target_color)
        if is_selected:
            self.configure(border_width=2, border_color=self.active_color)
        else:
            self.configure(border_width=0)
    
    def animate_to_color(self, target_color, duration=150, steps=10):
        """Плавная анимация перехода цвета"""
        if self.animation_id:
            self.after_cancel(self.animation_id)
        
        start_color = self.current_color
        step_duration = duration // steps
        
        def animate_step(step):
            if step <= steps:
                factor = step / steps
                factor = factor * factor * (3 - 2 * factor)
                new_color = interpolate_color(start_color, target_color, factor)
                self.configure(fg_color=new_color)
                self.current_color = new_color
                self.animation_id = self.after(step_duration, lambda: animate_step(step + 1))
            else:
                self.current_color = target_color
                self.animation_id = None
        
        animate_step(1)


class AnimatedNavButton(ctk.CTkFrame):
    """Анимированная кнопка навигации - macOS Liquid Glass стиль"""
    
    def __init__(self, master, icon, text, color, command=None, **kwargs):
        self.base_color = COLORS["bg_tertiary"]
        self.active_color = color
        self.is_active = False
        self.command = command
        
        super().__init__(master, fg_color="transparent", width=58, height=68, **kwargs)
        self.pack_propagate(False)
        
        # Кнопка - Liquid Glass стиль с увеличенными скруглениями
        self.btn = ctk.CTkButton(
            self,
            text=icon,
            width=48,
            height=48,
            corner_radius=GLASS_CORNER_RADIUS,  # macOS скругления
            fg_color=self.base_color,
            hover_color=color,
            border_width=0,
            font=ctk.CTkFont(size=20),
            command=self._on_click
        )
        self.btn.pack(pady=(0, 2))
        
        # Подпись - SF Pro шрифт
        self.label = ctk.CTkLabel(
            self,
            text=text,
            font=ctk.CTkFont(family=FONT_FAMILY, size=9),
            text_color=COLORS["text_secondary"]
        )
        self.label.pack(pady=(2, 0))
        
        # Hover эффекты
        self.btn.bind("<Enter>", self.on_enter)
        self.btn.bind("<Leave>", self.on_leave)
        
        self.animation_id = None
        self.current_color = self.base_color
        self.glow_animation_id = None
    
    def _on_click(self):
        """Обработка клика"""
        if self.command:
            self.command()
    
    def on_enter(self, event=None):
        """Hover - подсветка границы"""
        if not self.is_active:
            self.btn.configure(border_width=2, border_color=self.active_color)
    
    def on_leave(self, event=None):
        """Убираем hover"""
        if not self.is_active:
            self.btn.configure(border_width=0)
    
    def flash_animation(self):
        """Плавная вспышка фона при клике"""
        current = self.current_color
        # Яркая вспышка - осветляем на 50%
        bright_color = interpolate_color(current, "#ffffff", 0.5)
        
        # Плавное осветление и затухание
        steps = 6
        
        def flash_up(step):
            if step <= steps:
                factor = step / steps
                color = interpolate_color(current, bright_color, factor)
                self.btn.configure(fg_color=color)
                self.after(20, lambda: flash_up(step + 1))
            else:
                # Затухание
                flash_down(steps)
        
        def flash_down(step):
            if step >= 0:
                factor = step / steps
                color = interpolate_color(current, bright_color, factor)
                self.btn.configure(fg_color=color)
                self.after(25, lambda: flash_down(step - 1))
            else:
                self.btn.configure(fg_color=current)
        
        flash_up(1)
    
    def set_active(self, active, animate=True):
        """Установить активное состояние с анимацией"""
        self.is_active = active
        target_color = self.active_color if active else self.base_color
        
        if animate:
            self.animate_color(target_color)
        else:
            self.btn.configure(fg_color=target_color)
            self.current_color = target_color
        
        self.label.configure(text_color=self.active_color if active else COLORS["text_secondary"])
        
        if active:
            self.btn.configure(border_width=2, border_color=self.active_color)
        else:
            self.btn.configure(border_width=0)
    
    def animate_color(self, target_color, duration=150, steps=10):
        """Плавная анимация цвета"""
        if self.animation_id:
            self.after_cancel(self.animation_id)
        
        start_color = self.current_color
        step_duration = duration // steps
        
        def animate_step(step):
            if step <= steps:
                factor = step / steps
                factor = factor * factor * (3 - 2 * factor)
                new_color = interpolate_color(start_color, target_color, factor)
                self.btn.configure(fg_color=new_color)
                self.current_color = new_color
                self.animation_id = self.after(step_duration, lambda: animate_step(step + 1))
            else:
                self.current_color = target_color
                self.animation_id = None
        
        animate_step(1)
    
    def start_pulse(self):
        """Пульсация активной кнопки"""
        self.pulse_step = 0
        self._pulse()
    
    def _pulse(self):
        """Один шаг пульсации"""
        if not self.is_active:
            return
        
        # Мягкая пульсация яркости границы
        import math
        self.pulse_step += 1
        factor = (math.sin(self.pulse_step * 0.15) + 1) / 2
        pulse_color = interpolate_color(self.active_color, "#ffffff", factor * 0.3)
        self.btn.configure(border_color=pulse_color)
        
        self.glow_animation_id = self.after(50, self._pulse)
    
    def stop_pulse(self):
        """Остановить пульсацию"""
        if self.glow_animation_id:
            self.after_cancel(self.glow_animation_id)
            self.glow_animation_id = None


def apply_liquid_glass_style(window):
    """
    Применяет macOS стиль к окну (без прозрачности).
    """
    try:
        # Убираем прозрачность - полностью непрозрачное окно
        window.attributes("-alpha", 1.0)
        
        logger.info("✨ macOS стиль применён")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка применения стиля: {e}")
        return False


class PhotoToolsApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Настройка окна - macOS Liquid Glass стиль
        self.title("Fotya Tools")
        self.geometry("1100x800")
        self.minsize(950, 700)
        self.base_bg_color = COLORS["bg_dark"]
        self.configure(fg_color=self.base_bg_color)
        
        # Применяем Liquid Glass стиль
        # self.after(100, lambda: apply_liquid_glass_style(self))
        logger.info("Skipping apply_liquid_glass_style for stability test")
        
        self.files = []
        self.watermark_logo = None
        self.output_folder = os.path.expanduser("~/Desktop/upscaled_output")
        
        # Папка для автосохранения
        self.autosave_folder = os.path.expanduser("~/Documents/FotyaTools")
        os.makedirs(self.autosave_folder, exist_ok=True)
        self.autosave_file = os.path.join(self.autosave_folder, "autosave.json")
        
        logger.info("Creating UI...")
        self.create_ui()
        
        # Загружаем сохранённое состояние
        logger.info("Loading autosave...")
        try:
            self.load_autosave()
            logger.info("Autosave loaded successfully.")
        except Exception as e:
            logger.error(f"Critical error during load_autosave: {e}")
            logger.error(traceback.format_exc())
        
        # Автосохранение при закрытии
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        logger.info("App initialized. Starting mainloop...")
        sys.stdout.flush()
        sys.stderr.flush()
    
    def create_ui(self):
        # Главный контейнер - только контент растягивается (row 2)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)  # header - фикс
        self.grid_rowconfigure(1, weight=0)  # nav + workspace - фикс
        self.grid_rowconfigure(2, weight=1)  # content - растягивается
        self.grid_rowconfigure(3, weight=0)  # status - фикс
        
        # === ЗАГОЛОВОК - Liquid Glass стиль ===
        header = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], corner_radius=GLASS_CORNER_RADIUS)
        header.grid(row=0, column=0, padx=12, pady=(8, 4), sticky="ew")
        
        # Заголовок с SF Pro шрифтом
        ctk.CTkLabel(header, text="📸 Fotya Tools", 
                    font=ctk.CTkFont(family=FONT_FAMILY, size=24, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(side="left", padx=20, pady=12)
        
        # Кнопка Админ - Liquid Glass стиль
        self.admin_mode = False
        self.hidden_tabs = []
        
        # Кнопка управления пользователями и профиль (зависит от прав)
        try:
            from license_manager import license_manager
            
            if license_manager.is_admin:
                # Админ видит кнопку настроек вкладок
                self.admin_btn = ctk.CTkButton(header, text="⚙️ Админ", width=85, height=30,
                                               command=self.toggle_admin_panel,
                                               fg_color=COLORS["bg_tertiary"],
                                               hover_color=COLORS["primary"],
                                               corner_radius=GLASS_CORNER_RADIUS_SMALL,
                                               font=ctk.CTkFont(family=FONT_FAMILY, size=12))
                self.admin_btn.pack(side="left", padx=8, pady=12)
                
                # Кнопка управления пользователями
                self.users_btn = ctk.CTkButton(header, text="👥 Пользователи", width=120, height=30,
                                               command=self._open_users_panel,
                                               fg_color=COLORS["danger"],
                                               hover_color=COLORS["primary"],
                                               corner_radius=GLASS_CORNER_RADIUS_SMALL,
                                               font=ctk.CTkFont(family=FONT_FAMILY, size=12))
                self.users_btn.pack(side="left", padx=4, pady=12)
                
                # Кнопка выхода
                self.logout_btn = ctk.CTkButton(header, text="🚪 Выйти", width=80, height=30,
                                                command=self._logout,
                                                fg_color=COLORS["bg_tertiary"],
                                                hover_color=COLORS["danger"],
                                                corner_radius=GLASS_CORNER_RADIUS_SMALL,
                                                font=ctk.CTkFont(family=FONT_FAMILY, size=12))
                self.logout_btn.pack(side="right", padx=8, pady=12)
                
                # Показываем текущего пользователя
                user_name = license_manager.current_user.get("username", "")
                ctk.CTkLabel(header, text=f"👑 {user_name}",
                            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                            text_color=COLORS["success"]).pack(side="right", padx=5, pady=12)
                
                # Проверяем обновления в фоне
                self._check_updates_indicator(header, license_manager)
            else:
                # Обычный пользователь - НЕ видит кнопку Админ
                user_name = license_manager.current_user.get("username", "") if license_manager.current_user else ""
                
                # Кнопка выхода
                self.logout_btn = ctk.CTkButton(header, text="🚪 Выйти", width=80, height=30,
                                                command=self._logout,
                                                fg_color=COLORS["bg_tertiary"],
                                                hover_color=COLORS["danger"],
                                                corner_radius=GLASS_CORNER_RADIUS_SMALL,
                                                font=ctk.CTkFont(family=FONT_FAMILY, size=12))
                self.logout_btn.pack(side="right", padx=8, pady=12)
                
                if user_name:
                    ctk.CTkLabel(header, text=f"👤 {user_name}",
                                font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                                text_color=COLORS["text_secondary"]).pack(side="right", padx=5, pady=12)
                
                # Проверяем обновления в фоне
                self._check_updates_indicator(header, license_manager)
        except:
            # Если система лицензирования не работает - показываем кнопку Админ
            self.admin_btn = ctk.CTkButton(header, text="⚙️ Админ", width=85, height=30,
                                           command=self.toggle_admin_panel,
                                           fg_color=COLORS["bg_tertiary"],
                                           hover_color=COLORS["primary"],
                                           corner_radius=GLASS_CORNER_RADIUS_SMALL,
                                           font=ctk.CTkFont(family=FONT_FAMILY, size=12))
            self.admin_btn.pack(side="left", padx=8, pady=12)
        
        # === ПАНЕЛЬ НАВИГАЦИИ - Liquid Glass ===
        nav_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], corner_radius=GLASS_CORNER_RADIUS_SMALL)
        nav_frame.grid(row=1, column=0, padx=12, pady=(0, 4), sticky="ew")
        
        # Внутренний контейнер
        nav_inner = ctk.CTkFrame(nav_frame, fg_color="transparent")
        nav_inner.pack(side="left", fill="x", expand=False)
        
        # Рабочая папка - Liquid Glass карточка
        workspace_frame = ctk.CTkFrame(nav_inner, fg_color=COLORS["bg_tertiary"], corner_radius=GLASS_CORNER_RADIUS_SMALL)
        workspace_frame.pack(side="left", padx=8, pady=8)
        
        ctk.CTkLabel(workspace_frame, text="📁", 
                    font=ctk.CTkFont(size=14)).pack(side="left", padx=(8, 4), pady=6)
        
        self.workspace_label = ctk.CTkLabel(workspace_frame, text=self.output_folder,
                                            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                                            text_color=COLORS["text_primary"])
        self.workspace_label.pack(side="left", padx=(0, 5), pady=6)
        
        ctk.CTkButton(workspace_frame, text="...", width=30, height=24,
                     command=self.change_workspace,
                     fg_color=COLORS["bg_secondary"],
                     hover_color=COLORS["primary"],
                     corner_radius=6).pack(side="left", padx=(0, 6), pady=6)
        
        # Кнопки навигации - сразу после рабочей папки
        nav_buttons = ctk.CTkFrame(nav_inner, fg_color="transparent")
        nav_buttons.pack(side="left", pady=8, padx=(8, 15))
        
        # Данные для кнопок навигации
        self.nav_tabs = [
            ("🚀", "Upscale", COLORS["primary"]),
            ("🗜️", "Сжатие", COLORS["secondary"]),
            ("💧", "Ватермарка", COLORS["cyan"]),
            ("📂", "Сортировка", COLORS["warning"]),
            ("📐", "Aspect", COLORS["pink"]),
            ("🎬", "Раскадровка", COLORS["teal"]),
            ("🎨", "Редактор", COLORS["success"]),
            ("🤖", "AI", COLORS["danger"]),
        ]
        
        self.nav_buttons = {}
        self.current_tab = "Upscale"
        
        for i, (icon, name, color) in enumerate(self.nav_tabs):
            # Анимированная кнопка навигации
            nav_btn = AnimatedNavButton(
                nav_buttons,
                icon=icon,
                text=name,
                color=color,
                command=lambda n=name: self.switch_tab(n)
            )
            nav_btn.pack(side="left", padx=4)
            self.nav_buttons[name] = nav_btn
        
        # Активируем первую кнопку
        self.nav_buttons["Upscale"].set_active(True, animate=False)
        
        # === КОНТЕЙНЕР ДЛЯ КОНТЕНТА ВКЛАДОК - Liquid Glass ===
        self.content_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], corner_radius=GLASS_CORNER_RADIUS)
        self.content_frame.grid(row=2, column=0, padx=12, pady=(0, 4), sticky="nsew")
        
        # Создаём фреймы для каждой вкладки
        self.tab_frames = {}
        tab_names = ["Upscale", "Сжатие", "Ватермарка", "Сортировка", "Aspect", "Раскадровка", "Редактор", "AI"]
        
        for name in tab_names:
            frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
            self.tab_frames[name] = frame
        
        # Присваиваем ссылки на вкладки
        self.tab_upscale = self.tab_frames["Upscale"]
        self.tab_compress = self.tab_frames["Сжатие"]
        self.tab_watermark = self.tab_frames["Ватермарка"]
        self.tab_sort = self.tab_frames["Сортировка"]
        self.tab_aspect = self.tab_frames["Aspect"]
        self.tab_storyboard = self.tab_frames["Раскадровка"]
        self.tab_editor = self.tab_frames["Редактор"]
        self.tab_ai = self.tab_frames["AI"]
        
        # Заполняем вкладки
        self.create_upscale_tab()
        self.create_compress_tab()
        self.create_watermark_tab()
        self.create_sort_tab()
        self.create_aspect_tab()
        self.create_storyboard_tab()
        self.create_editor_tab()
        self.create_ai_tab()
        
        # Показываем первую вкладку
        self.show_tab("Upscale")
        
        # === СТАТУС БАР - Liquid Glass ===
        status_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], corner_radius=GLASS_CORNER_RADIUS_SMALL, height=28)
        status_frame.grid(row=3, column=0, padx=12, pady=(0, 8), sticky="ew")
        
        # Индикатор интернета
        self.internet_indicator = ctk.CTkLabel(status_frame, text="🟢 Онлайн", 
                                               font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                                               text_color=COLORS["success"])
        self.internet_indicator.pack(side="left", padx=10, pady=5)
        
        # Версия приложения
        try:
            from license_manager import APP_VERSION
            version_text = f"v{APP_VERSION}"
        except:
            version_text = "v1.0.0"
        
        self.version_label = ctk.CTkLabel(status_frame, text=version_text, 
                                          font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                                          text_color=COLORS["text_secondary"])
        self.version_label.pack(side="right", padx=10, pady=5)
        
        self.status_bar = ctk.CTkLabel(status_frame, text="© Фотя. Все права защищены", 
                                       font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                                       text_color=COLORS["text_secondary"])
        self.status_bar.pack(pady=5)
        
        # Запускаем проверку интернета каждые 30 секунд
        self._start_internet_check()
    
    def switch_tab(self, tab_name):
        """Переключение вкладки с плавной анимацией"""
        if tab_name == self.current_tab:
            return
        
        # Логируем переключение вкладки
        try:
            from license_manager import license_manager
            license_manager.log_action(f"Открыл вкладку: {tab_name}")
        except:
            pass
        
        # Деактивируем предыдущую кнопку
        if self.current_tab in self.nav_buttons:
            self.nav_buttons[self.current_tab].set_active(False)
        
        # Активируем новую кнопку
        self.nav_buttons[tab_name].set_active(True)
        
        # Переключаем вкладку
        self.current_tab = tab_name
        self.show_tab(tab_name)
    
    def flash_screen(self):
        """Вспышка фона всего приложения"""
        base = self.base_bg_color
        bright = interpolate_color(base, "#ffffff", 0.15)
        steps = 5
        
        def flash_up(step):
            if step <= steps:
                factor = step / steps
                color = interpolate_color(base, bright, factor)
                self.configure(fg_color=color)
                self.after(15, lambda: flash_up(step + 1))
            else:
                flash_down(steps)
        
        def flash_down(step):
            if step >= 0:
                factor = step / steps
                color = interpolate_color(base, bright, factor)
                self.configure(fg_color=color)
                self.after(20, lambda: flash_down(step - 1))
            else:
                self.configure(fg_color=base)
        
        flash_up(1)
    
    def show_tab(self, tab_name):
        """Показать выбранную вкладку"""
        # Скрываем все вкладки
        for name, frame in self.tab_frames.items():
            frame.grid_forget()
        
        # Показываем выбранную
        if tab_name in self.tab_frames:
            self.tab_frames[tab_name].grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
            self.content_frame.grid_columnconfigure(0, weight=1)
            self.content_frame.grid_rowconfigure(0, weight=1)
    
    def change_workspace(self):
        folder = filedialog.askdirectory(title="Выберите рабочую папку")
        if folder:
            self.output_folder = folder
            self.workspace_label.configure(text=folder)
    
    def toggle_admin_panel(self):
        """Открыть панель управления вкладками"""
        admin_window = ctk.CTkToplevel(self)
        admin_window.title("⚙️ Админ панель")
        admin_window.geometry("400x600")
        admin_window.configure(fg_color=COLORS["bg_dark"])
        admin_window.transient(self)
        admin_window.grab_set()
        
        # Создаём tabview для разделов
        admin_tabs = ctk.CTkTabview(admin_window, fg_color=COLORS["bg_secondary"])
        admin_tabs.pack(fill="both", expand=True, padx=10, pady=10)
        
        # === Вкладка "Вкладки" ===
        tabs_tab = admin_tabs.add("📑 Вкладки")
        
        ctk.CTkLabel(tabs_tab, text="Показать/скрыть вкладки",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(pady=(10, 10))
        
        tab_names = ["Upscale", "Сжатие", "Ватермарка", "Сортировка", "Aspect", "Раскадровка", "Редактор", "AI"]
        
        self.tab_vars = {}
        
        for name in tab_names:
            var = ctk.BooleanVar(value=name not in self.hidden_tabs)
            self.tab_vars[name] = var
            
            cb = ctk.CTkCheckBox(tabs_tab, text=name, variable=var,
                                font=ctk.CTkFont(family=FONT_FAMILY, size=13),
                                fg_color=COLORS["primary"],
                                hover_color=COLORS["primary_hover"],
                                text_color=COLORS["text_primary"])
            cb.pack(pady=3, padx=20, anchor="w")
        
        ctk.CTkButton(tabs_tab, text="✅ Применить", 
                     command=lambda: self.apply_tab_visibility(admin_window),
                     width=180, height=36,
                     fg_color=COLORS["success"], hover_color=COLORS["success_hover"],
                     font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold")).pack(pady=15)
        
        # === Вкладка "Kling Workspace" ===
        kling_tab = admin_tabs.add("🎬 Kling")
        
        ctk.CTkLabel(kling_tab, text="Управление пользователями",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(pady=(10, 10))
        
        # Кнопка открыть веб-админку
        ctk.CTkButton(kling_tab, text="🌐 Открыть админ панель в браузере", 
                     command=lambda: webbrowser.open(f"{KLING_WORKSPACE_URL}/admin"),
                     width=280, height=40,
                     fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
                     font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold")).pack(pady=10)
        
        # Разделитель
        ctk.CTkLabel(kling_tab, text="─" * 40, text_color=COLORS["text_secondary"]).pack(pady=5)
        
        # Быстрое добавление пользователя
        ctk.CTkLabel(kling_tab, text="Быстрое добавление пользователя",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                    text_color=COLORS["text_secondary"]).pack(pady=(10, 5))
        
        user_frame = ctk.CTkFrame(kling_tab, fg_color="transparent")
        user_frame.pack(fill="x", padx=20, pady=5)
        
        self.kling_username = ctk.CTkEntry(user_frame, placeholder_text="Логин", width=120)
        self.kling_username.pack(side="left", padx=(0, 5))
        
        self.kling_password = ctk.CTkEntry(user_frame, placeholder_text="Пароль", width=120, show="*")
        self.kling_password.pack(side="left", padx=5)
        
        ctk.CTkButton(user_frame, text="➕", width=40,
                     command=self._add_kling_user,
                     fg_color=COLORS["success"], hover_color=COLORS["success_hover"]).pack(side="left", padx=5)
        
        # Статус
        self.kling_admin_status = ctk.CTkLabel(kling_tab, text="",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                    text_color=COLORS["text_secondary"])
        self.kling_admin_status.pack(pady=5)
        
        # Информация
        info_frame = ctk.CTkFrame(kling_tab, fg_color=COLORS["bg_tertiary"], corner_radius=8)
        info_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(info_frame, text="ℹ️ Информация",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(anchor="w", padx=10, pady=(8, 5))
        
        ctk.CTkLabel(info_frame, text=f"Сервер: {KLING_VDS_HOST}",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                    text_color=COLORS["text_secondary"]).pack(anchor="w", padx=10)
        
        ctk.CTkLabel(info_frame, text=f"Админ панель: {KLING_WORKSPACE_URL}/admin",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                    text_color=COLORS["text_secondary"]).pack(anchor="w", padx=10)
        
        ctk.CTkLabel(info_frame, text="Логин по умолчанию: admin / admin123",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                    text_color=COLORS["text_secondary"]).pack(anchor="w", padx=10, pady=(0, 8))
    
    def _open_users_panel(self):
        """Открывает панель управления пользователями (лицензирование)"""
        try:
            from login_window import AdminPanel
            AdminPanel(self)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось открыть панель: {e}")
    
    def _start_internet_check(self):
        """Запускает периодическую проверку интернета"""
        def check():
            try:
                from license_manager import license_manager
                if license_manager.check_internet_connection():
                    self.internet_indicator.configure(text="🟢 Онлайн", text_color=COLORS["success"])
                else:
                    self.internet_indicator.configure(text="🔴 Нет сети", text_color=COLORS["danger"])
                    # Показываем предупреждение
                    self._show_no_internet_warning()
            except:
                pass
        
        def schedule_check():
            if self.winfo_exists():
                threading.Thread(target=check, daemon=True).start()
                self.after(30000, schedule_check)  # Каждые 30 секунд
        
        # Первая проверка через 5 секунд
        self.after(5000, schedule_check)
    
    def _show_no_internet_warning(self):
        """Показывает предупреждение об отсутствии интернета"""
        try:
            # Показываем только если ещё не показано
            if not hasattr(self, '_internet_warning_shown') or not self._internet_warning_shown:
                self._internet_warning_shown = True
                
                warning = ctk.CTkToplevel(self)
                warning.title("⚠️ Нет подключения")
                warning.geometry("350x150")
                warning.configure(fg_color=COLORS["bg_dark"])
                warning.transient(self)
                
                ctk.CTkLabel(warning, text="⚠️ Нет подключения к интернету",
                            font=ctk.CTkFont(size=16, weight="bold"),
                            text_color=COLORS["danger"]).pack(pady=20)
                
                ctk.CTkLabel(warning, text="Приложение требует интернет для работы.\nНекоторые функции могут быть недоступны.",
                            font=ctk.CTkFont(size=12),
                            text_color=COLORS["text_secondary"]).pack(pady=10)
                
                def close():
                    self._internet_warning_shown = False
                    warning.destroy()
                
                ctk.CTkButton(warning, text="OK", width=100, command=close).pack(pady=10)
                
                # Автозакрытие через 5 секунд
                warning.after(5000, close)
        except:
            pass
    
    def _logout(self):
        """Выход из аккаунта и показ окна входа"""
        try:
            from license_manager import license_manager
            license_manager.logout()
        except:
            pass
        
        # Закрываем текущее окно
        self.destroy()
        
        # Показываем окно входа (skip_auto_login=True чтобы не входить автоматически)
        from login_window import LoginWindow
        login = LoginWindow(on_success_callback=start_main_app, skip_auto_login=True)
        login.mainloop()
    
    def _check_updates_indicator(self, header, license_manager):
        """Проверяет обновления в фоне и показывает индикатор"""
        def check():
            try:
                has_update, version, download_url = license_manager.check_for_updates()
                if has_update and version:
                    update_info = {
                        'version': version,
                        'download_url': download_url
                    }
                    self.after(0, lambda: self._show_update_indicator(header, update_info))
            except Exception as e:
                logger.warning(f"Update check error: {e}")
        
        # Запускаем в фоне
        threading.Thread(target=check, daemon=True).start()
    
    def _show_update_indicator(self, header, update_info):
        """Показывает индикатор обновления в header"""
        update_btn = ctk.CTkButton(
            header, 
            text=f"🔔 Обновление v{update_info['version']}", 
            width=160, height=30,
            command=lambda: self._show_update_dialog(update_info),
            fg_color=COLORS["warning"],
            hover_color=COLORS["danger"],
            corner_radius=GLASS_CORNER_RADIUS_SMALL,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold")
        )
        update_btn.pack(side="right", padx=5, pady=12)
    
    def _show_update_dialog(self, update_info):
        """Показывает диалог с информацией об обновлении"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Доступно обновление")
        dialog.geometry("400x350")
        dialog.configure(fg_color=COLORS["bg_dark"])
        dialog.transient(self)
        dialog.grab_set()
        
        ctk.CTkLabel(dialog, text="🚀 Доступно обновление!",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=20, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(pady=(30, 10))
        
        # Версии
        version_frame = ctk.CTkFrame(dialog, fg_color=COLORS["bg_secondary"], corner_radius=10)
        version_frame.pack(fill="x", padx=30, pady=15)
        
        ctk.CTkLabel(version_frame, text=f"Текущая версия: {update_info['current_version']}",
                    font=ctk.CTkFont(size=12),
                    text_color=COLORS["text_secondary"]).pack(anchor="w", padx=15, pady=(10, 5))
        
        ctk.CTkLabel(version_frame, text=f"Новая версия: {update_info['version']}",
                    font=ctk.CTkFont(size=14, weight="bold"),
                    text_color=COLORS["success"]).pack(anchor="w", padx=15, pady=(0, 10))
        
        # Описание
        if update_info.get('body'):
            desc_frame = ctk.CTkFrame(dialog, fg_color=COLORS["bg_secondary"], corner_radius=10)
            desc_frame.pack(fill="x", padx=30, pady=10)
            
            ctk.CTkLabel(desc_frame, text="Что нового:",
                        font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=15, pady=(10, 5))
            
            ctk.CTkLabel(desc_frame, text=update_info['body'][:300],
                        font=ctk.CTkFont(size=11),
                        text_color=COLORS["text_secondary"],
                        wraplength=340, justify="left").pack(anchor="w", padx=15, pady=(0, 10))
        
        # Статус
        status_label = ctk.CTkLabel(dialog, text="", font=ctk.CTkFont(size=11))
        status_label.pack(pady=5)
        
        # Кнопки
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=30, pady=10)
        
        update_btn = ctk.CTkButton(btn_frame, text="🚀 Обновить", height=40,
                                   fg_color=COLORS["success"])
        
        def do_update():
            download_url = update_info.get('download_url', '')
            if not download_url:
                status_label.configure(text="❌ Ссылка на обновление не найдена", text_color=COLORS["danger"])
                return
            
            update_btn.configure(state="disabled", text="⏳ Загрузка...")
            status_label.configure(text="📥 Скачивание обновления...", text_color=COLORS["text_secondary"])
            dialog.update()
            
            def install():
                try:
                    from auto_updater import download_and_install_update
                    success, msg = download_and_install_update(download_url, update_info['version'])
                    dialog.after(0, lambda: finish_update(success, msg))
                except Exception as e:
                    dialog.after(0, lambda: finish_update(False, str(e)))
            
            threading.Thread(target=install, daemon=True).start()
        
        def finish_update(success, msg):
            update_btn.configure(state="normal", text="🚀 Обновить")
            if success:
                status_label.configure(text="✅ Перезапуск...", text_color=COLORS["success"])
                dialog.update()
                
                # Автоматический перезапуск через 1 секунду
                def restart_app():
                    try:
                        dialog.destroy()
                        # Перезапускаем приложение
                        python = sys.executable
                        script = os.path.abspath(sys.argv[0])
                        self.destroy()
                        os.execl(python, python, script)
                    except Exception as e:
                        messagebox.showerror("Ошибка", f"Не удалось перезапустить: {e}\n\nПерезапустите вручную.")
                
                self.after(1000, restart_app)
            else:
                status_label.configure(text="❌ " + msg, text_color=COLORS["danger"])
        
        update_btn.configure(command=do_update)
        update_btn.pack(side="left", expand=True, fill="x", padx=(0, 5))
        
        ctk.CTkButton(btn_frame, text="Позже", height=40,
                     fg_color=COLORS["bg_tertiary"],
                     command=dialog.destroy).pack(side="right", width=100)
    
    def apply_tab_visibility(self, window):
        """Применить настройки видимости вкладок"""
        self.hidden_tabs = [name for name, var in self.tab_vars.items() if not var.get()]
        
        # Скрываем/показываем кнопки навигации
        for name, nav_btn in self.nav_buttons.items():
            if name in self.hidden_tabs:
                nav_btn.pack_forget()
            else:
                nav_btn.pack(side="left", padx=4)
        
        # Если текущая вкладка скрыта, переключаемся на первую видимую
        if self.current_tab in self.hidden_tabs:
            for name in self.nav_buttons:
                if name not in self.hidden_tabs:
                    self.switch_tab(name)
                    break
        
        window.destroy()
    
    def _add_kling_user(self):
        """Добавить пользователя в Kling Workspace через API"""
        username = self.kling_username.get().strip()
        password = self.kling_password.get().strip()
        
        if not username or not password:
            self.kling_admin_status.configure(text="❌ Введите логин и пароль", text_color="#ff6b6b")
            return
        
        try:
            import urllib.request
            import urllib.parse
            
            # Отправляем POST запрос на добавление пользователя
            url = f"{KLING_WORKSPACE_URL}/api/add-user"
            data = urllib.parse.urlencode({
                'username': username,
                'password': password,
                'role': 'user'
            }).encode()
            
            req = urllib.request.Request(url, data=data, method='POST')
            req.add_header('Content-Type', 'application/x-www-form-urlencoded')
            
            with urllib.request.urlopen(req, timeout=5) as response:
                result = response.read().decode()
                if 'success' in result.lower() or response.status == 200:
                    self.kling_admin_status.configure(text=f"✅ Пользователь {username} добавлен", text_color="#4CAF50")
                    self.kling_username.delete(0, 'end')
                    self.kling_password.delete(0, 'end')
                else:
                    self.kling_admin_status.configure(text=f"⚠️ {result}", text_color="#ff9800")
        except Exception as e:
            # Если API не работает, открываем веб-админку
            self.kling_admin_status.configure(text="ℹ️ Откройте админ панель в браузере", text_color="#007AFF")
            webbrowser.open(f"{KLING_WORKSPACE_URL}/admin")
    
    # ==================== UPSCALE TAB ====================
    def create_upscale_tab(self):
        tab = self.tab_upscale
        tab.grid_columnconfigure(0, weight=1)
        
        # Загрузка файлов - Liquid Glass Card
        load_frame = ctk.CTkFrame(tab, fg_color=COLORS["bg_tertiary"], corner_radius=GLASS_CORNER_RADIUS)
        load_frame.grid(row=0, column=0, padx=16, pady=12, sticky="ew")
        load_frame.grid_columnconfigure((0, 1), weight=1)
        
        ctk.CTkButton(load_frame, text="📁 Загрузить фото", command=self.load_files,
                     height=42, font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
                     fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
                     corner_radius=GLASS_CORNER_RADIUS_SMALL).grid(row=0, column=0, padx=10, pady=12, sticky="ew")
        ctk.CTkButton(load_frame, text="📂 Загрузить папку", command=self.load_folder,
                     height=42, font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
                     fg_color=COLORS["secondary"], hover_color=COLORS["secondary_hover"],
                     corner_radius=GLASS_CORNER_RADIUS_SMALL).grid(row=0, column=1, padx=10, pady=12, sticky="ew")
        
        # Список файлов - Liquid Glass
        self.file_listbox = ctk.CTkTextbox(tab, height=100, corner_radius=GLASS_CORNER_RADIUS_SMALL,
                                           fg_color=COLORS["bg_tertiary"],
                                           font=ctk.CTkFont(family=FONT_FAMILY, size=13))
        self.file_listbox.grid(row=1, column=0, padx=16, pady=6, sticky="ew")
        
        # Настройки - Liquid Glass Card
        settings_frame = ctk.CTkFrame(tab, fg_color=COLORS["bg_tertiary"], corner_radius=GLASS_CORNER_RADIUS)
        settings_frame.grid(row=2, column=0, padx=16, pady=12, sticky="ew")
        settings_frame.grid_columnconfigure((0, 1), weight=1)
        
        # Модель
        ctk.CTkLabel(settings_frame, text="Модель:", 
                    font=ctk.CTkFont(family=FONT_FAMILY, size=14),
                    text_color=COLORS["text_secondary"]).grid(row=0, column=0, padx=16, pady=10, sticky="w")
        self.model_var = ctk.StringVar(value="ESRGAN (универсальный)")
        self.model_menu = ctk.CTkOptionMenu(settings_frame, variable=self.model_var, 
                                            values=list(MODELS.keys()), width=280,
                                            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
                                            fg_color=COLORS["bg_secondary"],
                                            button_color=COLORS["primary"],
                                            button_hover_color=COLORS["primary_hover"],
                                            corner_radius=GLASS_CORNER_RADIUS_SMALL)
        self.model_menu.grid(row=0, column=1, padx=16, pady=10, sticky="w")
        
        # Масштаб
        ctk.CTkLabel(settings_frame, text="Масштаб:", 
                    font=ctk.CTkFont(family=FONT_FAMILY, size=14),
                    text_color=COLORS["text_secondary"]).grid(row=1, column=0, padx=16, pady=10, sticky="w")
        self.scale_var = ctk.IntVar(value=4)
        self.scale_slider = ctk.CTkSlider(settings_frame, from_=2, to=4, number_of_steps=2, 
                                          variable=self.scale_var, width=220,
                                          progress_color=COLORS["primary"],
                                          button_color=COLORS["text_primary"],
                                          button_hover_color=COLORS["cyan"])
        self.scale_slider.grid(row=1, column=1, padx=16, pady=10, sticky="w")
        self.scale_label = ctk.CTkLabel(settings_frame, text="4x", 
                                        font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
                                        text_color=COLORS["primary"])
        self.scale_label.grid(row=1, column=2, padx=6)
        self.scale_slider.configure(command=lambda v: self.scale_label.configure(text=f"{int(v)}x"))
        
        # Прогресс - тонкий macOS стиль
        self.upscale_progress = ctk.CTkProgressBar(tab, height=4, corner_radius=2,
                                                   progress_color=COLORS["success"],
                                                   fg_color=COLORS["bg_tertiary"])
        self.upscale_progress.grid(row=3, column=0, padx=16, pady=16, sticky="ew")
        self.upscale_progress.set(0)
        
        # Кнопка запуска - macOS Liquid Glass стиль
        ctk.CTkButton(tab, text="🚀 Запустить Upscale", command=self.start_upscale,
                     height=50, font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
                     fg_color=COLORS["success"], hover_color=COLORS["success_hover"],
                     corner_radius=GLASS_CORNER_RADIUS).grid(row=4, column=0, padx=16, pady=12, sticky="ew")
    
    # ==================== COMPRESS TAB ====================
    def create_compress_tab(self):
        tab = self.tab_compress
        tab.grid_columnconfigure(0, weight=1)
        
        # Загрузка - Liquid Glass
        load_frame = ctk.CTkFrame(tab, fg_color=COLORS["bg_tertiary"], corner_radius=GLASS_CORNER_RADIUS)
        load_frame.grid(row=0, column=0, padx=16, pady=12, sticky="ew")
        load_frame.grid_columnconfigure((0, 1), weight=1)
        
        ctk.CTkButton(load_frame, text="📁 Загрузить фото", command=self.load_compress_files,
                     height=42, font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
                     fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
                     corner_radius=GLASS_CORNER_RADIUS_SMALL).grid(row=0, column=0, padx=10, pady=12, sticky="ew")
        ctk.CTkButton(load_frame, text="📂 Загрузить папку", command=self.load_compress_folder,
                     height=42, font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
                     fg_color=COLORS["secondary"], hover_color=COLORS["secondary_hover"],
                     corner_radius=GLASS_CORNER_RADIUS_SMALL).grid(row=0, column=1, padx=10, pady=12, sticky="ew")
        
        self.compress_files = []
        self.compress_listbox = ctk.CTkTextbox(tab, height=100, corner_radius=GLASS_CORNER_RADIUS_SMALL,
                                               fg_color=COLORS["bg_tertiary"],
                                               font=ctk.CTkFont(family=FONT_FAMILY, size=13))
        self.compress_listbox.grid(row=1, column=0, padx=16, pady=6, sticky="ew")
        
        # Настройки - Liquid Glass
        settings = ctk.CTkFrame(tab, fg_color=COLORS["bg_tertiary"], corner_radius=GLASS_CORNER_RADIUS)
        settings.grid(row=2, column=0, padx=16, pady=12, sticky="ew")
        
        ctk.CTkLabel(settings, text="Целевой размер (МБ):", 
                    font=ctk.CTkFont(family=FONT_FAMILY, size=14),
                    text_color=COLORS["text_secondary"]).pack(side="left", padx=16, pady=12)
        self.target_size_var = ctk.DoubleVar(value=1.5)
        ctk.CTkEntry(settings, textvariable=self.target_size_var, width=80,
                    font=ctk.CTkFont(family=FONT_FAMILY, size=13),
                    fg_color=COLORS["bg_secondary"], corner_radius=GLASS_CORNER_RADIUS_SMALL).pack(side="left", padx=6, pady=12)
        
        # === HEIC2JPG конвертер - Liquid Glass ===
        heic_frame = ctk.CTkFrame(tab, fg_color=COLORS["bg_tertiary"], corner_radius=GLASS_CORNER_RADIUS)
        heic_frame.grid(row=3, column=0, padx=16, pady=12, sticky="ew")
        heic_frame.grid_columnconfigure((0, 1), weight=1)
        
        ctk.CTkLabel(heic_frame, text="🖼️ HEIC → JPG", 
                    font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
                    text_color=COLORS["text_primary"]).grid(row=0, column=0, padx=12, pady=10, sticky="w")
        
        # Две кнопки: Выбрать папку и Конвертировать
        btn_container = ctk.CTkFrame(heic_frame, fg_color="transparent")
        btn_container.grid(row=0, column=1, padx=12, pady=10, sticky="e")
        
        ctk.CTkButton(btn_container, text="📂 Выбрать папку", command=self.select_heic_folder,
                     height=34, width=140, font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                     fg_color=COLORS["secondary"], hover_color=COLORS["secondary_hover"],
                     corner_radius=GLASS_CORNER_RADIUS_SMALL).pack(side="left", padx=5)
        
        ctk.CTkButton(btn_container, text="▶️ Конвертировать", command=self.start_heic_convert,
                     height=34, width=150, font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
                     fg_color=COLORS["teal"], hover_color="#0D9488",
                     corner_radius=GLASS_CORNER_RADIUS_SMALL).pack(side="left", padx=5)
        
        # Путь к папке HEIC
        self.heic_folder_path = None
        
        # Прогресс - тонкий macOS стиль
        self.compress_progress = ctk.CTkProgressBar(tab, height=4, corner_radius=2,
                                                    progress_color=COLORS["danger"],
                                                    fg_color=COLORS["bg_tertiary"])
        self.compress_progress.grid(row=4, column=0, padx=16, pady=16, sticky="ew")
        self.compress_progress.set(0)
        
        # Статус HEIC
        self.heic_status = ctk.CTkLabel(tab, text="", 
                                        font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                                        text_color=COLORS["text_secondary"])
        self.heic_status.grid(row=5, column=0, padx=16, pady=2)
        
        # Кнопка - Liquid Glass
        ctk.CTkButton(tab, text="🗜️ Сжать изображения", command=self.start_compress,
                     height=50, font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
                     fg_color=COLORS["danger"], hover_color=COLORS["danger_hover"],
                     corner_radius=GLASS_CORNER_RADIUS).grid(row=6, column=0, padx=16, pady=12, sticky="ew")
    
    # ==================== WATERMARK TAB ====================
    def create_watermark_tab(self):
        import tkinter as tk
        tab = self.tab_watermark
        tab.grid_columnconfigure(0, weight=0)  # Левая панель
        tab.grid_columnconfigure(1, weight=1)  # Превью
        tab.grid_rowconfigure(0, weight=1)
        
        # Инициализация переменных
        self.wm_files = []
        self.wm_video_path = None
        self.wm_logo_path = None
        self.wm_preview_image = None
        self.wm_preview_source = None
        self.wm_presets = {}  # {"Имя пресета": {"text": ..., "font": ..., ...}}
        self.wm_presets_file = os.path.join(self.autosave_folder, "watermark_presets.json")
        self.load_wm_presets()
        
        # === ЛЕВАЯ ПАНЕЛЬ - Настройки ===
        left_panel = ctk.CTkScrollableFrame(tab, width=320, fg_color=COLORS["bg_secondary"])
        left_panel.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="nsew")
        
        # --- Загрузка медиа ---
        ctk.CTkLabel(left_panel, text="📎 Загрузка медиа", 
                    font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(pady=(10, 5), anchor="w", padx=10)
        
        load_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        load_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkButton(load_frame, text="📷 Фото", command=self.load_wm_files,
                     height=36, width=90, font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                     fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
                     corner_radius=8).pack(side="left", padx=2)
        ctk.CTkButton(load_frame, text="🎬 Видео", command=self.load_wm_video,
                     height=36, width=90, font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                     fg_color=COLORS["warning"], hover_color=COLORS["warning_hover"],
                     corner_radius=8).pack(side="left", padx=2)
        ctk.CTkButton(load_frame, text="📂 Папка", command=self.load_wm_folder,
                     height=36, width=90, font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                     fg_color=COLORS["secondary"], hover_color=COLORS["secondary_hover"],
                     corner_radius=8).pack(side="left", padx=2)
        
        self.wm_media_label = ctk.CTkLabel(left_panel, text="Нет загруженных файлов",
                                           font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                                           text_color=COLORS["text_secondary"])
        self.wm_media_label.pack(pady=5, anchor="w", padx=10)
        
        # === СВОРАЧИВАЕМОЕ МЕНЮ НАСТРОЕК ===
        self.wm_settings_expanded = ctk.BooleanVar(value=False)
        
        # Кнопка разворачивания
        self.wm_settings_btn = ctk.CTkButton(left_panel, text="⚙️ Настройки ▼", 
                                             command=self.toggle_wm_settings,
                                             height=36, font=ctk.CTkFont(family=FONT_FAMILY, size=13),
                                             fg_color=COLORS["bg_tertiary"], hover_color=COLORS["primary"],
                                             corner_radius=8)
        self.wm_settings_btn.pack(fill="x", padx=10, pady=(15, 5))
        
        # Скрываемый фрейм с настройками
        self.wm_settings_frame = ctk.CTkFrame(left_panel, fg_color=COLORS["bg_tertiary"], corner_radius=8)
        # Изначально скрыт
        
        # --- Тип водяного знака ---
        ctk.CTkLabel(self.wm_settings_frame, text="🎨 Тип водяного знака", 
                    font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(pady=(10, 3), anchor="w", padx=10)
        
        self.wm_type = ctk.StringVar(value="text")
        type_frame = ctk.CTkFrame(self.wm_settings_frame, fg_color="transparent")
        type_frame.pack(fill="x", padx=10, pady=3)
        ctk.CTkRadioButton(type_frame, text="Текст", variable=self.wm_type, value="text",
                          command=self.update_wm_preview,
                          font=ctk.CTkFont(family=FONT_FAMILY, size=11)).pack(side="left", padx=5)
        ctk.CTkRadioButton(type_frame, text="PNG", variable=self.wm_type, value="logo",
                          command=self.update_wm_preview,
                          font=ctk.CTkFont(family=FONT_FAMILY, size=11)).pack(side="left", padx=5)
        ctk.CTkRadioButton(type_frame, text="Текст+PNG", variable=self.wm_type, value="both",
                          command=self.update_wm_preview,
                          font=ctk.CTkFont(family=FONT_FAMILY, size=11)).pack(side="left", padx=5)
        
        # --- Текст (многострочный) ---
        ctk.CTkLabel(self.wm_settings_frame, text="⌨️ Текст", 
                    font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(pady=(10, 3), anchor="w", padx=10)
        
        self.wm_text = ctk.CTkTextbox(self.wm_settings_frame, height=60,
                                      font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                                      fg_color=COLORS["bg_secondary"], corner_radius=6)
        self.wm_text.pack(fill="x", padx=10, pady=3)
        self.wm_text.insert("1.0", "© Your Brand 2025\nВсе права защищены")
        self.wm_text.bind("<KeyRelease>", lambda e: self.update_wm_preview())
        
        # --- Шрифт ---
        font_frame = ctk.CTkFrame(self.wm_settings_frame, fg_color="transparent")
        font_frame.pack(fill="x", padx=10, pady=3)
        
        ctk.CTkLabel(font_frame, text="Шрифт:", 
                    font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                    text_color=COLORS["text_secondary"]).pack(side="left")
        
        available_fonts = ["Arial", "Helvetica", "Times New Roman", "Georgia", "Verdana", 
                          "Courier New", "Impact", "Comic Sans MS", "Trebuchet MS"]
        self.wm_font = ctk.StringVar(value="Arial")
        self.wm_font_menu = ctk.CTkOptionMenu(font_frame, variable=self.wm_font, values=available_fonts,
                                              command=lambda x: self.update_wm_preview(),
                                              font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                                              fg_color=COLORS["bg_secondary"], width=150, height=28)
        self.wm_font_menu.pack(side="left", padx=10)
        
        # Базовый размер шрифта
        self.wm_font_size = ctk.IntVar(value=48)
        
        # --- PNG логотип ---
        logo_frame = ctk.CTkFrame(self.wm_settings_frame, fg_color="transparent")
        logo_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(logo_frame, text="🖼️ PNG логотип", command=self.select_logo, width=120,
                     fg_color=COLORS["bg_secondary"], hover_color=COLORS["primary"],
                     font=ctk.CTkFont(family=FONT_FAMILY, size=11), corner_radius=6, height=28).pack(side="left")
        self.logo_label = ctk.CTkLabel(logo_frame, text="Не выбран", 
                                       text_color=COLORS["text_secondary"],
                                       font=ctk.CTkFont(family=FONT_FAMILY, size=10))
        self.logo_label.pack(side="left", padx=10)
        
        # --- Масштаб текста ---
        ctk.CTkLabel(self.wm_settings_frame, text="📝 Масштаб текста", 
                    font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                    text_color=COLORS["text_secondary"]).pack(pady=(8, 2), anchor="w", padx=10)
        
        self.wm_text_scale = ctk.DoubleVar(value=1.0)
        text_scale_frame = ctk.CTkFrame(self.wm_settings_frame, fg_color="transparent")
        text_scale_frame.pack(fill="x", padx=10, pady=2)
        
        self.wm_text_scale_slider = ctk.CTkSlider(text_scale_frame, from_=0.2, to=5.0, variable=self.wm_text_scale,
                                                  command=lambda x: self.update_wm_preview(),
                                                  width=180, height=14, progress_color=COLORS["warning"])
        self.wm_text_scale_slider.pack(side="left")
        self.wm_text_scale_label = ctk.CTkLabel(text_scale_frame, text="100%",
                                                font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                                                text_color=COLORS["text_secondary"])
        self.wm_text_scale_label.pack(side="left", padx=8)
        
        # --- Масштаб PNG ---
        ctk.CTkLabel(self.wm_settings_frame, text="🖼️ Масштаб PNG", 
                    font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                    text_color=COLORS["text_secondary"]).pack(pady=(8, 2), anchor="w", padx=10)
        
        self.wm_scale = ctk.DoubleVar(value=1.0)
        scale_frame = ctk.CTkFrame(self.wm_settings_frame, fg_color="transparent")
        scale_frame.pack(fill="x", padx=10, pady=2)
        
        self.wm_scale_slider = ctk.CTkSlider(scale_frame, from_=0.1, to=3.0, variable=self.wm_scale,
                                             command=lambda x: self.update_wm_preview(),
                                             width=180, height=14, progress_color=COLORS["primary"])
        self.wm_scale_slider.pack(side="left")
        self.wm_scale_label = ctk.CTkLabel(scale_frame, text="100%",
                                           font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                                           text_color=COLORS["text_secondary"])
        self.wm_scale_label.pack(side="left", padx=8)
        
        # --- Прозрачность ---
        ctk.CTkLabel(self.wm_settings_frame, text="👁️ Прозрачность", 
                    font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                    text_color=COLORS["text_secondary"]).pack(pady=(8, 2), anchor="w", padx=10)
        
        self.wm_opacity = ctk.DoubleVar(value=0.7)
        opacity_frame = ctk.CTkFrame(self.wm_settings_frame, fg_color="transparent")
        opacity_frame.pack(fill="x", padx=10, pady=2)
        
        self.wm_opacity_slider = ctk.CTkSlider(opacity_frame, from_=0.1, to=1.0, variable=self.wm_opacity,
                                               command=lambda x: self.update_wm_preview(),
                                               width=180, height=14, progress_color=COLORS["pink"])
        self.wm_opacity_slider.pack(side="left")
        self.wm_opacity_label = ctk.CTkLabel(opacity_frame, text="70%",
                                             font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                                             text_color=COLORS["text_secondary"])
        self.wm_opacity_label.pack(side="left", padx=8)
        
        # --- Позиция ---
        ctk.CTkLabel(self.wm_settings_frame, text="📍 Позиция", 
                    font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                    text_color=COLORS["text_secondary"]).pack(pady=(8, 2), anchor="w", padx=10)
        
        self.wm_position = ctk.StringVar(value="center")
        pos_frame = ctk.CTkFrame(self.wm_settings_frame, fg_color="transparent")
        pos_frame.pack(fill="x", padx=10, pady=(2, 10))
        
        positions = [("↖", "top-left"), ("↑", "top-center"), ("↗", "top-right"),
                    ("←", "center-left"), ("◎", "center"), ("→", "center-right"),
                    ("↙", "bottom-left"), ("↓", "bottom-center"), ("↘", "bottom-right")]
        
        pos_grid = ctk.CTkFrame(pos_frame, fg_color="transparent")
        pos_grid.pack()
        for i, (icon, val) in enumerate(positions):
            row, col = i // 3, i % 3
            ctk.CTkRadioButton(pos_grid, text=icon, variable=self.wm_position, value=val,
                              command=self.update_wm_preview, width=35,
                              font=ctk.CTkFont(size=14)).grid(row=row, column=col, padx=3, pady=1)
        
        # --- Пресеты ---
        ctk.CTkLabel(left_panel, text="💾 Пресеты", 
                    font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(pady=(15, 5), anchor="w", padx=10)
        
        preset_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        preset_frame.pack(fill="x", padx=10, pady=5)
        
        self.wm_preset_var = ctk.StringVar(value="")
        preset_names = list(self.wm_presets.keys()) if self.wm_presets else ["Нет пресетов"]
        self.wm_preset_menu = ctk.CTkOptionMenu(preset_frame, variable=self.wm_preset_var, 
                                                values=preset_names,
                                                command=self.load_wm_preset,
                                                font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                                                fg_color=COLORS["bg_tertiary"], width=150)
        self.wm_preset_menu.pack(side="left", padx=2)
        
        ctk.CTkButton(preset_frame, text="💾", command=self.save_wm_preset, width=36,
                     fg_color=COLORS["success"], hover_color=COLORS["success_hover"],
                     font=ctk.CTkFont(size=14), corner_radius=8).pack(side="left", padx=2)
        ctk.CTkButton(preset_frame, text="🗑️", command=self.delete_wm_preset, width=36,
                     fg_color=COLORS["danger"], hover_color=COLORS["danger_hover"],
                     font=ctk.CTkFont(size=14), corner_radius=8).pack(side="left", padx=2)
        
        # --- Прогресс и кнопка ---
        self.wm_progress = ctk.CTkProgressBar(left_panel, height=6, corner_radius=3,
                                              progress_color=COLORS["pink"],
                                              fg_color=COLORS["bg_tertiary"])
        self.wm_progress.pack(fill="x", padx=10, pady=(20, 10))
        self.wm_progress.set(0)
        
        ctk.CTkButton(left_panel, text="💧 Применить водяной знак", command=self.start_watermark,
                     height=50, font=ctk.CTkFont(family=FONT_FAMILY, size=15, weight="bold"),
                     fg_color=COLORS["pink"], hover_color=COLORS["pink_hover"],
                     corner_radius=GLASS_CORNER_RADIUS_SMALL).pack(fill="x", padx=10, pady=10)
        
        self.wm_status = ctk.CTkLabel(left_panel, text="",
                                      font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                                      text_color=COLORS["text_secondary"])
        self.wm_status.pack(pady=5)
        
        # === ПРАВАЯ ПАНЕЛЬ - Превью ===
        preview_frame = ctk.CTkFrame(tab, fg_color=COLORS["bg_tertiary"], corner_radius=GLASS_CORNER_RADIUS)
        preview_frame.grid(row=0, column=1, padx=(5, 10), pady=10, sticky="nsew")
        preview_frame.grid_rowconfigure(0, weight=1)
        preview_frame.grid_columnconfigure(0, weight=1)
        
        self.wm_preview_canvas = tk.Canvas(preview_frame, bg="#1a1a2e", highlightthickness=0)
        self.wm_preview_canvas.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Подсказка
        ctk.CTkLabel(preview_frame, text="Загрузите фото или видео для превью",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                    text_color=COLORS["text_secondary"]).pack(pady=5)
    
    # ==================== SORT TAB ====================
    def create_sort_tab(self):
        tab = self.tab_sort
        tab.grid_columnconfigure(0, weight=1)
        
        # Описание
        ctk.CTkLabel(tab, text="📸 Сортировка фото по ориентации", 
                    font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, pady=20)
        ctk.CTkLabel(tab, text="Разделяет фотографии на горизонтальные и вертикальные\nСоздаёт папки horizontal/ и vertical/",
                    font=ctk.CTkFont(size=14), text_color="gray").grid(row=1, column=0, pady=10)
        
        # Кнопка выбора папки
        ctk.CTkButton(tab, text="📁 Выбрать папку с фото", command=self.start_sort,
                     height=60, width=300, font=ctk.CTkFont(size=18, weight="bold"),
                     fg_color="#e91e63", hover_color="#c2185b").grid(row=2, column=0, pady=30)
        
        self.sort_folder_label = ctk.CTkLabel(tab, text="", font=ctk.CTkFont(size=13))
        self.sort_folder_label.grid(row=3, column=0, pady=5)
        
        # Прогресс
        self.sort_progress = ctk.CTkProgressBar(tab, width=400)
        self.sort_progress.grid(row=4, column=0, pady=20)
        self.sort_progress.set(0)
        
        self.sort_status = ctk.CTkLabel(tab, text="", font=ctk.CTkFont(size=14))
        self.sort_status.grid(row=5, column=0, pady=10)
    
    # ==================== ASPECT RATIO TAB ====================
    def create_aspect_tab(self):
        tab = self.tab_aspect
        tab.grid_columnconfigure(0, weight=1)
        
        # Метод по умолчанию - обрезка (без UI выбора)
        self.aspect_method = ctk.StringVar(value="crop")
        
        # Храним выбранные файлы для кропа
        self.crop_preset_files = []
        self.crop_preset_folder = None
        
        # === АВТО-СООТНОШЕНИЕ ===
        auto_frame = ctk.CTkFrame(tab, fg_color=COLORS["bg_secondary"], corner_radius=GLASS_CORNER_RADIUS)
        auto_frame.grid(row=0, column=0, padx=30, pady=(20, 15), sticky="ew")
        
        ctk.CTkLabel(auto_frame, text="🔄 Авто-соотношение", 
                    font=ctk.CTkFont(family=FONT_FAMILY, size=18, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(pady=(15, 5), anchor="center")
        
        ctk.CTkLabel(auto_frame, text="Анализирует папку и приводит все фото к единому размеру", 
                    font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                    text_color=COLORS["text_secondary"]).pack(pady=(0, 12), anchor="center")
        
        ctk.CTkButton(auto_frame, text="📁 Выбрать папку", command=self.start_aspect_fix,
                     height=45, width=220, 
                     font=ctk.CTkFont(family=FONT_FAMILY, size=15, weight="bold"),
                     fg_color=COLORS["warning"], hover_color=COLORS["warning_hover"],
                     corner_radius=GLASS_CORNER_RADIUS_SMALL).pack(pady=(0, 15), anchor="center")
        
        # === ПРЕСЕТЫ КРОПА ===
        preset_frame = ctk.CTkFrame(tab, fg_color=COLORS["bg_secondary"], corner_radius=GLASS_CORNER_RADIUS)
        preset_frame.grid(row=1, column=0, padx=30, pady=10, sticky="ew")
        
        ctk.CTkLabel(preset_frame, text="✂️ Пресеты кропа", 
                    font=ctk.CTkFont(family=FONT_FAMILY, size=18, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(pady=(15, 12), anchor="center")
        
        # Горизонтальные пресеты
        ctk.CTkLabel(preset_frame, text="▬ Горизонтальные", 
                    font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
                    text_color=COLORS["text_secondary"]).pack(pady=(0, 8), anchor="center")
        
        h_presets_row = ctk.CTkFrame(preset_frame, fg_color="transparent")
        h_presets_row.pack(pady=(0, 12), anchor="center")
        
        h_presets = [("3:2", COLORS["primary"]), ("4:3", COLORS["secondary"]), 
                     ("16:9", COLORS["success"]), ("21:9", COLORS["pink"])]
        for ratio, color in h_presets:
            ctk.CTkButton(h_presets_row, text=ratio, command=lambda r=ratio: self.apply_crop_preset(r),
                         width=75, height=38, font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
                         fg_color=color, hover_color=color,
                         corner_radius=GLASS_CORNER_RADIUS_SMALL).pack(side="left", padx=5)
        
        # Вертикальные пресеты
        ctk.CTkLabel(preset_frame, text="▮ Вертикальные", 
                    font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
                    text_color=COLORS["text_secondary"]).pack(pady=(5, 8), anchor="center")
        
        v_presets_row = ctk.CTkFrame(preset_frame, fg_color="transparent")
        v_presets_row.pack(pady=(0, 12), anchor="center")
        
        v_presets = [("2:3", COLORS["primary"]), ("3:4", COLORS["secondary"]), 
                     ("9:16", COLORS["success"]), ("4:5", COLORS["teal"])]
        for ratio, color in v_presets:
            ctk.CTkButton(v_presets_row, text=ratio, command=lambda r=ratio: self.apply_crop_preset(r),
                         width=75, height=38, font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
                         fg_color=color, hover_color=color,
                         corner_radius=GLASS_CORNER_RADIUS_SMALL).pack(side="left", padx=5)
        
        # Квадрат
        ctk.CTkButton(preset_frame, text="1:1 ▢", command=lambda: self.apply_crop_preset("1:1"),
                     width=90, height=38, font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
                     fg_color=COLORS["cyan"], hover_color=COLORS["cyan"],
                     corner_radius=GLASS_CORNER_RADIUS_SMALL).pack(pady=(0, 15), anchor="center")
        
        # Разделитель
        ctk.CTkFrame(preset_frame, fg_color=COLORS["border"], height=2).pack(fill="x", padx=30, pady=10)
        
        # Выбор источника
        ctk.CTkLabel(preset_frame, text="Выберите источник:", 
                    font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                    text_color=COLORS["text_secondary"]).pack(pady=(5, 8), anchor="center")
        
        source_row = ctk.CTkFrame(preset_frame, fg_color="transparent")
        source_row.pack(pady=(0, 8), anchor="center")
        
        ctk.CTkButton(source_row, text="📁 Папка", command=self.select_crop_folder,
                     width=110, height=36, font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
                     fg_color=COLORS["bg_tertiary"], hover_color=COLORS["primary"],
                     corner_radius=GLASS_CORNER_RADIUS_SMALL).pack(side="left", padx=5)
        
        ctk.CTkButton(source_row, text="🖼️ Фото", command=self.select_crop_files,
                     width=110, height=36, font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
                     fg_color=COLORS["bg_tertiary"], hover_color=COLORS["primary"],
                     corner_radius=GLASS_CORNER_RADIUS_SMALL).pack(side="left", padx=5)
        
        ctk.CTkButton(source_row, text="🗑️", command=self.clear_crop_selection,
                     width=45, height=36, font=ctk.CTkFont(family=FONT_FAMILY, size=14),
                     fg_color=COLORS["danger"], hover_color=COLORS["danger_hover"],
                     corner_radius=GLASS_CORNER_RADIUS_SMALL).pack(side="left", padx=5)
        
        self.crop_source_label = ctk.CTkLabel(preset_frame, text="Не выбрано", 
                                              font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
                                              text_color=COLORS["warning"])
        self.crop_source_label.pack(pady=(8, 18), anchor="center")
        
        # Прогресс и статус
        self.aspect_folder_label = ctk.CTkLabel(tab, text="", 
                                                font=ctk.CTkFont(family=FONT_FAMILY, size=13),
                                                text_color=COLORS["text_secondary"])
        self.aspect_folder_label.grid(row=2, column=0, pady=5)
        
        self.aspect_progress = ctk.CTkProgressBar(tab, width=400, height=10,
                                                  progress_color=COLORS["primary"])
        self.aspect_progress.grid(row=3, column=0, pady=12)
        self.aspect_progress.set(0)
        
        self.aspect_status = ctk.CTkLabel(tab, text="", 
                                          font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
                                          text_color=COLORS["success"])
        self.aspect_status.grid(row=4, column=0, pady=8)
    
    # ==================== STORYBOARD TAB ====================
    def create_storyboard_tab(self):
        tab = self.tab_storyboard
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(3, weight=1)
        
        # Описание
        ctk.CTkLabel(tab, text="🎬 Раскадровка", 
                    font=ctk.CTkFont(family=FONT_FAMILY, size=22, weight="bold"),
                    text_color=COLORS["text_primary"]).grid(row=0, column=0, pady=(10, 3))
        ctk.CTkLabel(tab, text="Свободно перемещайте фото в любое место • При сохранении сортировка слева→направо, сверху→вниз",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=12), 
                    text_color=COLORS["text_secondary"]).grid(row=1, column=0, pady=(0, 8))
        
        # Кнопки управления - ровная сетка
        btn_frame = ctk.CTkFrame(tab, fg_color="transparent")
        btn_frame.grid(row=2, column=0, pady=5, padx=20, sticky="ew")
        btn_frame.grid_columnconfigure((0,1,2,3,4,5,6,7), weight=1)
        
        ctk.CTkButton(btn_frame, text="📁 Загрузить", command=self.load_storyboard_files,
                     height=36, font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                     fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
                     corner_radius=GLASS_CORNER_RADIUS_SMALL).grid(row=0, column=0, padx=2, sticky="ew")
        ctk.CTkButton(btn_frame, text="📂 Папка", command=self.load_storyboard_folder,
                     height=36, font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                     fg_color=COLORS["secondary"], hover_color=COLORS["secondary_hover"],
                     corner_radius=GLASS_CORNER_RADIUS_SMALL).grid(row=0, column=1, padx=2, sticky="ew")
        ctk.CTkButton(btn_frame, text="📋 Вставить", command=self.paste_files_from_finder,
                     height=36, font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                     fg_color=COLORS["teal"], hover_color="#0D9488",
                     corner_radius=GLASS_CORNER_RADIUS_SMALL).grid(row=0, column=2, padx=2, sticky="ew")
        ctk.CTkButton(btn_frame, text="↩️", command=self.undo_storyboard, width=50,
                     height=36, font=ctk.CTkFont(family=FONT_FAMILY, size=16),
                     fg_color=COLORS["warning"], hover_color=COLORS["warning_hover"],
                     corner_radius=GLASS_CORNER_RADIUS_SMALL).grid(row=0, column=3, padx=2, sticky="ew")
        ctk.CTkButton(btn_frame, text="➖", command=self.zoom_out_storyboard, width=50,
                     height=36, font=ctk.CTkFont(family=FONT_FAMILY, size=16),
                     fg_color=COLORS["bg_tertiary"], hover_color=COLORS["bg_secondary"],
                     corner_radius=GLASS_CORNER_RADIUS_SMALL).grid(row=0, column=4, padx=2, sticky="ew")
        ctk.CTkButton(btn_frame, text="➕", command=self.zoom_in_storyboard, width=50,
                     height=36, font=ctk.CTkFont(family=FONT_FAMILY, size=16),
                     fg_color=COLORS["bg_tertiary"], hover_color=COLORS["bg_secondary"],
                     corner_radius=GLASS_CORNER_RADIUS_SMALL).grid(row=0, column=5, padx=2, sticky="ew")
        ctk.CTkButton(btn_frame, text="🗑️", command=self.clear_storyboard, width=50,
                     height=36, font=ctk.CTkFont(family=FONT_FAMILY, size=14),
                     fg_color=COLORS["danger"], hover_color=COLORS["danger_hover"],
                     corner_radius=GLASS_CORNER_RADIUS_SMALL).grid(row=0, column=6, padx=2, sticky="ew")
        ctk.CTkButton(btn_frame, text="💾 Сохранить", command=self.save_storyboard,
                     height=36, font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                     fg_color=COLORS["success"], hover_color=COLORS["success_hover"],
                     corner_radius=GLASS_CORNER_RADIUS_SMALL).grid(row=0, column=7, padx=2, sticky="ew")
        
        # Sandbox Canvas - свободное поле для размещения
        import tkinter as tk
        try:
            from tkinterdnd2 import DND_FILES
        except ImportError:
            DND_FILES = None
        
        # Спокойный глубокий синий цвет для размышлений (Deep Space Blue)
        calm_bg_color = "#1a1a2e"
        
        canvas_frame = ctk.CTkFrame(tab, fg_color=calm_bg_color, corner_radius=GLASS_CORNER_RADIUS)
        canvas_frame.grid(row=3, column=0, padx=20, pady=8, sticky="nsew")
        
        self.storyboard_canvas = tk.Canvas(canvas_frame, bg=calm_bg_color, 
                                           highlightthickness=0)
        self.storyboard_canvas.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Список изображений для раскадровки
        self.storyboard_images = []  # [{"path": ..., "x": ..., "y": ..., "scale": 1.0}, ...]
        self.storyboard_items = []   # элементы на canvas
        self.drag_data = {"item": None, "x": 0, "y": 0, "multi": False}
        self.selected_items = set()  # множество выбранных элементов (Milanote-style)
        self.zoom_scale = 1.0        # общий масштаб canvas
        
        # Кэш превью изображений (оптимизация для 50+ фото)
        self.thumbnail_cache = {}    # {path: {scale: PhotoImage}}
        self.base_thumbnail_cache = {}  # {path: PIL.Image} - базовые превью
        
        # Undo система (история действий)
        self.undo_stack = []         # стек состояний для отмены
        self.undo_max_size = 50      # максимум 50 шагов назад
        
        # Масштабирование отдельных фото
        self.resize_mode = False     # режим изменения размера
        self.resize_item = None      # элемент для изменения размера
        self.resize_start = None     # начальная точка
        
        # Lasso selection (выделение рамкой как в Milanote)
        self.lasso_rect = None       # ID прямоугольника выделения
        self.lasso_start = None      # начальная точка
        
        # Привязка событий drag & drop (свободное перемещение)
        self.storyboard_canvas.bind("<Button-1>", self.on_storyboard_click)
        self.storyboard_canvas.bind("<B1-Motion>", self.on_storyboard_drag)
        self.storyboard_canvas.bind("<ButtonRelease-1>", self.on_storyboard_drop)
        
        # Shift+click для добавления к выделению
        self.storyboard_canvas.bind("<Shift-Button-1>", self.on_storyboard_shift_click)
        
        # Удаление по Backspace/Delete
        self.storyboard_canvas.bind("<BackSpace>", self.delete_selected_storyboard)
        self.storyboard_canvas.bind("<Delete>", self.delete_selected_storyboard)
        self.bind("<BackSpace>", self.delete_selected_storyboard)
        self.bind("<Delete>", self.delete_selected_storyboard)
        
        # Scroll для прокрутки (pan)
        self.storyboard_canvas.bind("<MouseWheel>", self.on_storyboard_scroll)
        self.storyboard_canvas.bind("<Button-4>", self.on_storyboard_scroll)
        self.storyboard_canvas.bind("<Button-5>", self.on_storyboard_scroll)
        
        # Shift+scroll для горизонтального pan
        self.storyboard_canvas.bind("<Shift-MouseWheel>", self.on_storyboard_hscroll)
        
        # Pinch-to-zoom двумя пальцами (Option/Alt + scroll на trackpad)
        self.storyboard_canvas.bind("<Option-MouseWheel>", self.on_pinch_zoom)
        self.storyboard_canvas.bind("<Alt-MouseWheel>", self.on_pinch_zoom)
        # Для плавного zoom
        self._pinch_zoom_accumulator = 0.0
        
        # Pan (перемещение) с зажатым Shift или средней кнопкой
        self.storyboard_canvas.bind("<Shift-B1-Motion>", self.on_storyboard_pan)
        self.storyboard_canvas.bind("<B2-Motion>", self.on_storyboard_pan)
        self.pan_data = {"x": 0, "y": 0}
        self.storyboard_canvas.bind("<Shift-Button-1>", self.on_pan_start)
        self.storyboard_canvas.bind("<Button-2>", self.on_pan_start)
        
        # Drag & Drop из Finder - tkinterdnd2 требует установленную tkdnd Tcl библиотеку
        # На Mac без tkdnd используем кнопку "Загрузить"
        if DND_AVAILABLE and DND_FILES:
            try:
                self.storyboard_canvas.drop_target_register(DND_FILES)
                self.storyboard_canvas.dnd_bind('<<Drop>>', self.on_drop_files)
                logger.info("Drag & drop enabled for storyboard canvas")
            except Exception as e:
                logger.warning(f"Drag & drop not available (tkdnd not installed): {e}")
        
        # Фокус для клавиатуры
        self.storyboard_canvas.focus_set()
        self.storyboard_canvas.bind("<Enter>", lambda e: self.storyboard_canvas.focus_set())
        
        # Cmd+C для копирования выбранных фото (только на canvas, чтобы не дублировать)
        self.storyboard_canvas.bind("<Command-c>", self.copy_selected_storyboard)
        
        # Cmd+V для вставки скопированных фото или файлов из Finder (только на canvas)
        self.storyboard_canvas.bind("<Command-v>", self.paste_storyboard)
        
        # Cmd+Z для Undo (отмена действий)
        self.storyboard_canvas.bind("<Command-z>", self.undo_storyboard)
        self.bind("<Command-z>", self.undo_storyboard)
        
        # Option+клик для клонирования фото
        self.storyboard_canvas.bind("<Option-Button-1>", self.on_storyboard_option_click)
        
        # Cmd+клик для множественного выбора (toggle selection)
        self.storyboard_canvas.bind("<Command-Button-1>", self.on_storyboard_cmd_click)
        
        # Правый клик для контекстного меню
        self.storyboard_canvas.bind("<Button-2>", self.on_storyboard_right_click)  # Mac trackpad
        self.storyboard_canvas.bind("<Control-Button-1>", self.on_storyboard_right_click)  # Control+click
        if self.winfo_toplevel().tk.call('tk', 'windowingsystem') == 'aqua':
            self.storyboard_canvas.bind("<Button-3>", self.on_storyboard_right_click)  # некоторые мыши
        
        # Буфер для копирования фото
        self.storyboard_clipboard = []
        
        # Cmd+Plus/Cmd+Minus для зума раскадровки
        self.storyboard_canvas.bind("<Command-equal>", self.zoom_in_storyboard)  # Cmd+= (plus)
        self.storyboard_canvas.bind("<Command-plus>", self.zoom_in_storyboard)
        self.storyboard_canvas.bind("<Command-minus>", self.zoom_out_storyboard)
        self.bind("<Command-equal>", self.zoom_in_storyboard)
        self.bind("<Command-plus>", self.zoom_in_storyboard)
        self.bind("<Command-minus>", self.zoom_out_storyboard)
        
        # Статус
        self.storyboard_status = ctk.CTkLabel(tab, text="🖱️ Рамка выделения • ⌘Z отмена • ➕➖ zoom • ⌫ удалить", 
                                              font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                                              text_color=COLORS["text_secondary"])
        self.storyboard_status.grid(row=4, column=0, pady=(5, 8))
    
    def save_undo_state(self):
        """Сохраняет текущее состояние для Undo"""
        import copy
        state = copy.deepcopy(self.storyboard_images)
        self.undo_stack.append(state)
        # Ограничиваем размер стека
        if len(self.undo_stack) > self.undo_max_size:
            self.undo_stack.pop(0)
    
    def undo_storyboard(self, event=None):
        """Отмена последнего действия (Cmd+Z)"""
        if not self.undo_stack:
            self.storyboard_status.configure(text="⚠️ Нет действий для отмены")
            return
        
        import copy
        # Полностью заменяем список изображений на сохранённое состояние
        restored_state = self.undo_stack.pop()
        self.storyboard_images = []
        for img in restored_state:
            self.storyboard_images.append(copy.deepcopy(img))
        
        self.selected_items.clear()
        self.thumbnail_cache.clear()  # Очищаем кэш для предотвращения проблем
        self.refresh_storyboard()
        self.storyboard_status.configure(text=f"↩️ Отмена • {len(self.storyboard_images)} фото • Осталось {len(self.undo_stack)} шагов")
    
    def get_cached_thumbnail(self, path, target_size):
        """Получает кэшированное превью или создаёт новое (оптимизировано)"""
        # Округляем размер до ближайших 20px для лучшего кэширования
        rounded_size = (target_size // 20) * 20
        rounded_size = max(40, min(600, rounded_size))  # Увеличен макс до 600px для большого зума
        
        cache_key = (path, rounded_size)
        
        if cache_key in self.thumbnail_cache:
            return self.thumbnail_cache[cache_key]
        
        # Загружаем базовое превью если ещё нет
        if path not in self.base_thumbnail_cache:
            try:
                img = Image.open(path)
                # Базовое превью 600px для большого зума
                img.thumbnail((600, 600), Image.Resampling.BILINEAR)
                self.base_thumbnail_cache[path] = img
            except Exception as e:
                logger.error(f"Ошибка загрузки {path}: {e}")
                return None, 0, 0
        
        # Масштабируем из базового превью
        base_img = self.base_thumbnail_cache[path].copy()
        orig_w, orig_h = base_img.size
        
        # Вычисляем размер с сохранением пропорций
        if orig_w >= orig_h:
            thumb_width = rounded_size
            thumb_height = int(rounded_size * orig_h / orig_w)
        else:
            thumb_height = rounded_size
            thumb_width = int(rounded_size * orig_w / orig_h)
        
        # Быстрый ресайз
        base_img = base_img.resize((thumb_width, thumb_height), Image.Resampling.BILINEAR)
        photo = ImageTk.PhotoImage(base_img)
        
        # Кэшируем (ограничиваем размер кэша)
        if len(self.thumbnail_cache) > 500:
            # Удаляем старые записи
            keys_to_remove = list(self.thumbnail_cache.keys())[:100]
            for k in keys_to_remove:
                del self.thumbnail_cache[k]
        
        self.thumbnail_cache[cache_key] = (photo, base_img.size[0], base_img.size[1])
        return self.thumbnail_cache[cache_key]
    
    def load_storyboard_files(self):
        files = filedialog.askopenfilenames(filetypes=[("Images", "*.jpg *.jpeg *.png *.webp")])
        if files:
            self.save_undo_state()  # Сохраняем состояние для Undo
            
            # Добавляем новые файлы сеткой (упорядоченно)
            canvas_w = self.storyboard_canvas.winfo_width() or 800
            
            # Параметры сетки
            thumb_size = 140  # Размер превью + отступ
            padding = 20      # Отступ от края
            cols = max(1, (canvas_w - padding * 2) // thumb_size)  # Количество столбцов
            
            # Начинаем с текущего количества изображений
            start_idx = len(self.storyboard_images)
            
            for i, path in enumerate(files):
                idx = start_idx + i
                col = idx % cols
                row = idx // cols
                x = padding + col * thumb_size
                y = padding + row * thumb_size
                self.storyboard_images.append({"path": path, "x": x, "y": y, "scale": 1.0})
            self.refresh_storyboard()
    
    def load_storyboard_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.save_undo_state()  # Сохраняем состояние для Undo
            
            canvas_w = self.storyboard_canvas.winfo_width() or 800
            
            # Параметры сетки
            thumb_size = 140  # Размер превью + отступ
            padding = 20      # Отступ от края
            cols = max(1, (canvas_w - padding * 2) // thumb_size)  # Количество столбцов
            
            # Начинаем с текущего количества изображений
            start_idx = len(self.storyboard_images)
            
            files = sorted([f for f in os.listdir(folder) 
                           if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))])
            
            # Показываем прогресс загрузки
            total = len(files)
            self.storyboard_status.configure(text=f"⏳ Загрузка 0/{total}...")
            self.update_idletasks()
            
            for i, f in enumerate(files):
                idx = start_idx + i
                col = idx % cols
                row = idx // cols
                x = padding + col * thumb_size
                y = padding + row * thumb_size
                self.storyboard_images.append({"path": os.path.join(folder, f), "x": x, "y": y, "scale": 1.0})
                
                # Обновляем прогресс каждые 10 файлов
                if (i + 1) % 10 == 0:
                    self.storyboard_status.configure(text=f"⏳ Загрузка {i+1}/{total}...")
                    self.update_idletasks()
            
            self.refresh_storyboard()
    
    def clear_storyboard(self):
        self.storyboard_images = []
        self.storyboard_items = []
        self.storyboard_canvas.delete("all")
        self.storyboard_status.configure(text="Загрузите фото и располагайте их свободно")
    
    def refresh_storyboard(self, visible_only=False):
        """Обновляет canvas с изображениями
        
        visible_only: отключено для стабильности - рисуем все элементы
        """
        # Очищаем canvas
        self.storyboard_canvas.delete("all")
        self.storyboard_items = []
        
        if not self.storyboard_images:
            self.storyboard_status.configure(text="Загрузите фото и располагайте их свободно")
            return
        
        # Получаем размеры видимой области
        canvas_w = self.storyboard_canvas.winfo_width() or 800
        canvas_h = self.storyboard_canvas.winfo_height() or 600
        
        # Базовый размер превью
        base_size = 100
        
        rendered_count = 0
        for idx, item_data in enumerate(self.storyboard_images):
            img_path = item_data["path"]
            x = int(item_data["x"] * self.zoom_scale)
            y = int(item_data["y"] * self.zoom_scale)
            item_scale = item_data.get("scale", 1.0)
            
            try:
                # Вычисляем целевой размер с учётом общего и индивидуального масштаба
                target_size = int(base_size * self.zoom_scale * item_scale)
                target_size = max(30, min(600, target_size))  # Увеличен макс до 600px для большого зума
                
                # Используем кэшированное превью
                cached = self.get_cached_thumbnail(img_path, target_size)
                if cached is None or cached[0] is None:
                    continue
                    
                photo, actual_w, actual_h = cached
                
                # Создаём фон карточки по размеру изображения
                card_id = self.storyboard_canvas.create_rectangle(
                    x - 3, y - 3, x + actual_w + 3, y + actual_h + 18,
                    fill=COLORS["bg_secondary"], outline=COLORS["border"], width=1,
                    tags=f"item_{idx}"
                )
                
                # Маркер resize (уголок для масштабирования)
                resize_id = self.storyboard_canvas.create_rectangle(
                    x + actual_w - 4, y + actual_h + 8,
                    x + actual_w + 3, y + actual_h + 18,
                    fill=COLORS["primary"], outline="", 
                    tags=(f"item_{idx}", f"resize_{idx}")
                )
                
                # Кнопка лупы для просмотра (в левом нижнем углу)
                preview_btn = self.storyboard_canvas.create_oval(
                    x - 1, y + actual_h + 4,
                    x + 14, y + actual_h + 19,
                    fill=COLORS["bg_tertiary"], outline=COLORS["text_secondary"], width=1,
                    tags=(f"item_{idx}", f"preview_{idx}")
                )
                # Иконка лупы
                preview_icon = self.storyboard_canvas.create_text(
                    x + 6, y + actual_h + 11,
                    text="🔍", font=(FONT_FAMILY, 8),
                    fill=COLORS["text_primary"],
                    tags=(f"item_{idx}", f"preview_{idx}")
                )
                
                # Изображение
                img_id = self.storyboard_canvas.create_image(
                    x + actual_w//2, y + actual_h//2,
                    image=photo, anchor="center", tags=f"item_{idx}"
                )
                
                # Имя файла (упрощённый шрифт)
                font_size = max(7, int(8 * self.zoom_scale))
                num_id = self.storyboard_canvas.create_text(
                    x + actual_w//2, y + actual_h + 8,
                    text=os.path.basename(img_path)[:12], fill=COLORS["text_secondary"],
                    font=(FONT_FAMILY, font_size), tags=f"item_{idx}"
                )
                
                self.storyboard_items.append({
                    "card_id": card_id,
                    "resize_id": resize_id,
                    "img_id": img_id,
                    "num_id": num_id,
                    "photo": photo,
                    "idx": idx,
                    "width": actual_w,
                    "height": actual_h
                })
                rendered_count += 1
                
            except Exception as e:
                logger.error(f"Ошибка загрузки {img_path}: {e}")
        
        zoom_pct = int(self.zoom_scale * 100)
        self.storyboard_status.configure(text=f"📷 {len(self.storyboard_images)} кадров ({rendered_count} видимых) • 🔍 {zoom_pct}% • ⌘Z отмена")
    
    def _update_single_item(self, idx):
        """Плавное обновление одного элемента без полной перерисовки canvas"""
        if idx >= len(self.storyboard_images):
            return
        
        item_data = self.storyboard_images[idx]
        img_path = item_data["path"]
        x = int(item_data["x"] * self.zoom_scale)
        y = int(item_data["y"] * self.zoom_scale)
        item_scale = item_data.get("scale", 1.0)
        
        # Удаляем старые элементы этого индекса
        self.storyboard_canvas.delete(f"item_{idx}")
        
        # Вычисляем целевой размер
        base_size = 100
        target_size = int(base_size * self.zoom_scale * item_scale)
        target_size = max(30, min(600, target_size))
        
        try:
            cached = self.get_cached_thumbnail(img_path, target_size)
            if cached is None or cached[0] is None:
                return
            
            photo, actual_w, actual_h = cached
            
            # Создаём фон карточки
            card_id = self.storyboard_canvas.create_rectangle(
                x - 3, y - 3, x + actual_w + 3, y + actual_h + 18,
                fill=COLORS["bg_secondary"], outline=COLORS["border"], width=1,
                tags=f"item_{idx}"
            )
            
            # Маркер resize
            resize_id = self.storyboard_canvas.create_rectangle(
                x + actual_w - 4, y + actual_h + 8,
                x + actual_w + 3, y + actual_h + 18,
                fill=COLORS["primary"], outline="", 
                tags=(f"item_{idx}", f"resize_{idx}")
            )
            
            # Кнопка лупы для просмотра
            self.storyboard_canvas.create_oval(
                x - 1, y + actual_h + 4,
                x + 14, y + actual_h + 19,
                fill=COLORS["bg_tertiary"], outline=COLORS["text_secondary"], width=1,
                tags=(f"item_{idx}", f"preview_{idx}")
            )
            self.storyboard_canvas.create_text(
                x + 6, y + actual_h + 11,
                text="🔍", font=(FONT_FAMILY, 8),
                fill=COLORS["text_primary"],
                tags=(f"item_{idx}", f"preview_{idx}")
            )
            
            # Изображение
            img_id = self.storyboard_canvas.create_image(
                x + actual_w//2, y + actual_h//2,
                image=photo, anchor="center", tags=f"item_{idx}"
            )
            
            # Имя файла
            font_size = max(7, int(8 * self.zoom_scale))
            num_id = self.storyboard_canvas.create_text(
                x + actual_w//2, y + actual_h + 8,
                text=os.path.basename(img_path)[:12], fill=COLORS["text_secondary"],
                font=(FONT_FAMILY, font_size), tags=f"item_{idx}"
            )
            
            # Обновляем ссылку на фото в списке элементов
            for i, item in enumerate(self.storyboard_items):
                if item["idx"] == idx:
                    self.storyboard_items[i] = {
                        "card_id": card_id,
                        "resize_id": resize_id,
                        "img_id": img_id,
                        "num_id": num_id,
                        "photo": photo,
                        "idx": idx,
                        "width": actual_w,
                        "height": actual_h
                    }
                    break
            
            # Подсвечиваем если выделен
            if idx in self.selected_items:
                self.storyboard_canvas.itemconfig(card_id, outline=COLORS["primary"], width=3)
                
        except Exception as e:
            logger.error(f"Ошибка обновления {img_path}: {e}")
    
    def clear_selection(self):
        """Снимает выделение со всех элементов (Milanote-style)"""
        for idx in self.selected_items:
            for item in self.storyboard_items:
                if item["idx"] == idx:
                    self.storyboard_canvas.itemconfig(item["card_id"], outline=COLORS["border"], width=2)
        self.selected_items.clear()
    
    def highlight_selected(self):
        """Подсвечивает выбранные элементы"""
        for idx in self.selected_items:
            for item in self.storyboard_items:
                if item["idx"] == idx:
                    self.storyboard_canvas.itemconfig(item["card_id"], outline=COLORS["primary"], width=3)
                    self.storyboard_canvas.tag_raise(f"item_{idx}")
    
    def on_storyboard_click(self, event):
        # Игнорируем если зажат Option (Alt) - это для клонирования
        # На Mac: Option = 0x0080
        if event.state & 0x0080:
            return  # Option+click обрабатывается в on_storyboard_option_click
        
        x, y = event.x, event.y
        
        # Проверяем модификаторы для множественного выбора
        # Shift = 0x1, Command/Meta = 0x8 (Mod1 на Mac)
        is_multi_select = bool(event.state & 0x1) or bool(event.state & 0x8)
        
        if is_multi_select:
            # Shift+click или Cmd+click: toggle выделения
            items = self.storyboard_canvas.find_overlapping(x-5, y-5, x+5, y+5)
            for canvas_item in items:
                tags = self.storyboard_canvas.gettags(canvas_item)
                for tag in tags:
                    if tag.startswith("item_"):
                        idx = int(tag.split("_")[1])
                        # Toggle: добавить или убрать из выделения
                        if idx in self.selected_items:
                            self.selected_items.discard(idx)
                        else:
                            self.selected_items.add(idx)
                        self.clear_selection()
                        self.highlight_selected()
                        count = len(self.selected_items)
                        if count > 0:
                            self.storyboard_status.configure(text=f"✅ Выбрано {count} • Shift/⌘+click добавить • ПКМ меню")
                        else:
                            self.storyboard_status.configure(text=f"📷 {len(self.storyboard_images)} кадров")
                        return
            return
        
        # Проверяем клик на кнопку превью (лупа)
        clicked_preview = None
        items = self.storyboard_canvas.find_overlapping(x-5, y-5, x+5, y+5)
        
        for canvas_item in items:
            tags = self.storyboard_canvas.gettags(canvas_item)
            for tag in tags:
                if tag.startswith("preview_"):
                    clicked_preview = int(tag.split("_")[1])
                    break
            if clicked_preview is not None:
                break
        
        if clicked_preview is not None:
            # Открываем большое превью
            self.show_photo_preview(clicked_preview)
            return
        
        # Проверяем клик на resize handle (масштабирование отдельного фото)
        clicked_resize = None
        for canvas_item in items:
            tags = self.storyboard_canvas.gettags(canvas_item)
            for tag in tags:
                if tag.startswith("resize_"):
                    clicked_resize = int(tag.split("_")[1])
                    break
            if clicked_resize is not None:
                break
        
        if clicked_resize is not None:
            # Начинаем масштабирование отдельного фото
            self.save_undo_state()  # Сохраняем для Undo
            self.resize_mode = True
            self.resize_item = clicked_resize
            self.resize_start = (x, y)
            self.drag_data["item"] = None
            self.storyboard_status.configure(text=f"📐 Масштабирование фото...")
            return
        
        # Ищем элемент под курсором
        clicked_idx = None
        for canvas_item in items:
            tags = self.storyboard_canvas.gettags(canvas_item)
            for tag in tags:
                if tag.startswith("item_"):
                    clicked_idx = int(tag.split("_")[1])
                    break
            if clicked_idx is not None:
                break
        
        if clicked_idx is not None:
            # Сохраняем состояние для Undo перед перетаскиванием
            self.save_undo_state()
            
            # Кликнули на элемент
            if clicked_idx in self.selected_items:
                # Уже выбран - начинаем перетаскивание группы
                self.drag_data["item"] = clicked_idx
                self.drag_data["multi"] = len(self.selected_items) > 1
            else:
                # Новый элемент - сбрасываем выделение и выбираем его
                self.clear_selection()
                self.selected_items.add(clicked_idx)
                self.highlight_selected()
                self.drag_data["item"] = clicked_idx
                self.drag_data["multi"] = False
            
            self.drag_data["x"] = x
            self.drag_data["y"] = y
            
            if len(self.selected_items) == 1:
                idx = list(self.selected_items)[0]
                scale_pct = int(self.storyboard_images[idx].get("scale", 1.0) * 100)
                self.storyboard_status.configure(text=f"✅ {os.path.basename(self.storyboard_images[idx]['path'])} • {scale_pct}% • ⌫ удалить")
            else:
                self.storyboard_status.configure(text=f"✅ Выбрано {len(self.selected_items)} элементов • ⌫ удалить")
        else:
            # Кликнули на пустое место - начинаем lasso selection
            self.clear_selection()
            self.lasso_start = (x, y)
            self.drag_data["item"] = None
            self.storyboard_status.configure(text=f"📷 {len(self.storyboard_images)} кадров")
    
    def on_storyboard_shift_click(self, event):
        """Shift+click для добавления к выделению (Milanote-style)"""
        x, y = event.x, event.y
        
        items = self.storyboard_canvas.find_overlapping(x-5, y-5, x+5, y+5)
        for canvas_item in items:
            tags = self.storyboard_canvas.gettags(canvas_item)
            for tag in tags:
                if tag.startswith("item_"):
                    idx = int(tag.split("_")[1])
                    if idx in self.selected_items:
                        self.selected_items.discard(idx)
                    else:
                        self.selected_items.add(idx)
                    self.clear_selection()
                    self.highlight_selected()
                    self.storyboard_status.configure(text=f"✅ Выбрано {len(self.selected_items)} элементов")
                    return
    
    def on_storyboard_drag(self, event):
        x, y = event.x, event.y
        dx = x - self.drag_data["x"]
        dy = y - self.drag_data["y"]
        
        # Режим масштабирования отдельного фото (плавное с throttling)
        if self.resize_mode and self.resize_item is not None:
            start_x, start_y = self.resize_start
            # Плавное изменение масштаба
            delta = ((x - start_x) + (y - start_y)) / 400
            
            idx = self.resize_item
            if 0 <= idx < len(self.storyboard_images):
                current_scale = self.storyboard_images[idx].get("scale", 1.0)
                new_scale = max(0.2, min(5.0, current_scale + delta))
                self.storyboard_images[idx]["scale"] = new_scale
                self.resize_start = (x, y)
                
                # Throttling: обновляем каждые 30мс для плавности
                import time
                now = time.time()
                if not hasattr(self, '_last_resize_update'):
                    self._last_resize_update = 0
                
                if now - self._last_resize_update > 0.03:  # 30мс
                    self._update_single_item(idx)
                    self._last_resize_update = now
                
                scale_pct = int(new_scale * 100)
                self.storyboard_status.configure(text=f"📐 Масштаб: {scale_pct}%")
            return
        
        if self.drag_data["item"] is not None:
            # Перетаскиваем выбранные элементы - только canvas.move, без пересчёта
            for idx in self.selected_items:
                self.storyboard_canvas.move(f"item_{idx}", dx, dy)
                self.storyboard_images[idx]["x"] += dx / self.zoom_scale
                self.storyboard_images[idx]["y"] += dy / self.zoom_scale
            
            self.drag_data["x"] = x
            self.drag_data["y"] = y
            
        elif self.lasso_start is not None:
            # Рисуем рамку выделения (lasso)
            if self.lasso_rect:
                self.storyboard_canvas.delete(self.lasso_rect)
            
            x1, y1 = self.lasso_start
            self.lasso_rect = self.storyboard_canvas.create_rectangle(
                x1, y1, x, y,
                outline=COLORS["primary"], width=2, dash=(4, 4),
                fill="", tags="lasso"
            )
            
            # Подсвечиваем элементы внутри рамки
            self.clear_selection()
            lx1, ly1 = min(x1, x), min(y1, y)
            lx2, ly2 = max(x1, x), max(y1, y)
            
            for item in self.storyboard_items:
                coords = self.storyboard_canvas.coords(item["card_id"])
                if coords:
                    cx = (coords[0] + coords[2]) / 2
                    cy = (coords[1] + coords[3]) / 2
                    if lx1 <= cx <= lx2 and ly1 <= cy <= ly2:
                        self.selected_items.add(item["idx"])
            
            self.highlight_selected()
            if self.selected_items:
                self.storyboard_status.configure(text=f"🔲 Выделено {len(self.selected_items)} элементов")
    
    def on_storyboard_drop(self, event):
        # Завершаем режим масштабирования
        if self.resize_mode:
            idx = self.resize_item
            self.resize_mode = False
            self.resize_item = None
            self.resize_start = None
            
            # Перерисовываем элемент с чёткой картинкой после завершения
            if idx is not None and 0 <= idx < len(self.storyboard_images):
                self._update_single_item(idx)
                scale_pct = int(self.storyboard_images[idx].get("scale", 1.0) * 100)
                self.storyboard_status.configure(text=f"✅ Масштаб: {scale_pct}%")
            return
        
        # Завершаем lasso selection
        if self.lasso_rect:
            self.storyboard_canvas.delete(self.lasso_rect)
            self.lasso_rect = None
        self.lasso_start = None
        self.drag_data["item"] = None
        
        if self.selected_items:
            self.storyboard_status.configure(text=f"✅ Выбрано {len(self.selected_items)} • ⌫ удалить • Shift+click добавить")
    
    def delete_selected_storyboard(self, event=None):
        """Удаляет выбранные элементы по Backspace/Delete (Milanote-style)"""
        if not self.selected_items:
            return
        
        self.save_undo_state()  # Сохраняем для Undo
        
        count = len(self.selected_items)
        # Удаляем в обратном порядке чтобы индексы не сбивались
        for idx in sorted(self.selected_items, reverse=True):
            if 0 <= idx < len(self.storyboard_images):
                del self.storyboard_images[idx]
        
        self.selected_items.clear()
        self.refresh_storyboard()
        self.storyboard_status.configure(text=f"🗑️ Удалено {count} элементов • ⌘Z отмена")
    
    def copy_selected_storyboard(self, event=None):
        """Копирует выбранные фото в буфер (Cmd+C)"""
        if not self.selected_items:
            self.storyboard_status.configure(text="⚠️ Выберите фото для копирования")
            return
        
        import copy
        self.storyboard_clipboard = []
        for idx in sorted(self.selected_items):
            if 0 <= idx < len(self.storyboard_images):
                self.storyboard_clipboard.append(copy.deepcopy(self.storyboard_images[idx]))
        
        count = len(self.storyboard_clipboard)
        self.storyboard_status.configure(text=f"📋 Скопировано {count} фото • ⌘V вставить")
    
    def paste_storyboard(self, event=None):
        """Вставляет фото из буфера или из Finder (Cmd+V)"""
        import copy
        
        # Если есть фото в буфере раскадровки
        if self.storyboard_clipboard:
            self.save_undo_state()
            
            # Смещение для вставленных фото
            offset = 30
            new_indices = []
            
            for i, img_data in enumerate(self.storyboard_clipboard):
                new_img = copy.deepcopy(img_data)
                new_img["x"] = img_data["x"] + offset * (i + 1)
                new_img["y"] = img_data["y"] + offset * (i + 1)
                self.storyboard_images.append(new_img)
                new_indices.append(len(self.storyboard_images) - 1)
            
            self.selected_items = set(new_indices)
            self.refresh_storyboard()
            self.storyboard_status.configure(text=f"📋 Вставлено {len(self.storyboard_clipboard)} фото")
        else:
            # Иначе пробуем вставить из Finder
            self.paste_files_from_finder(event)
    
    def on_storyboard_option_click(self, event):
        """Клонирует фото при Option+клике"""
        import copy
        
        # Находим элемент под курсором
        item = self.storyboard_canvas.find_closest(event.x, event.y)
        if not item:
            return
        
        # Находим индекс фото
        tags = self.storyboard_canvas.gettags(item[0])
        idx = None
        for tag in tags:
            if tag.startswith("img_"):
                try:
                    idx = int(tag.split("_")[1])
                except:
                    pass
                break
        
        if idx is None or idx >= len(self.storyboard_images):
            return
        
        self.save_undo_state()
        
        # Клонируем фото со смещением
        original = self.storyboard_images[idx]
        clone = copy.deepcopy(original)
        clone["x"] = original["x"] + 30
        clone["y"] = original["y"] + 30
        
        self.storyboard_images.append(clone)
        new_idx = len(self.storyboard_images) - 1
        
        # Выделяем клон
        self.selected_items = {new_idx}
        self.refresh_storyboard()
        self.storyboard_status.configure(text=f"👥 Клонировано • ⌘Z отмена")
    
    def on_storyboard_cmd_click(self, event):
        """Cmd+click для множественного выбора (toggle)"""
        x, y = event.x, event.y
        
        items = self.storyboard_canvas.find_overlapping(x-5, y-5, x+5, y+5)
        for canvas_item in items:
            tags = self.storyboard_canvas.gettags(canvas_item)
            for tag in tags:
                if tag.startswith("item_"):
                    idx = int(tag.split("_")[1])
                    # Toggle: добавить или убрать из выделения
                    if idx in self.selected_items:
                        self.selected_items.discard(idx)
                    else:
                        self.selected_items.add(idx)
                    self.clear_selection()
                    self.highlight_selected()
                    count = len(self.selected_items)
                    if count > 0:
                        self.storyboard_status.configure(text=f"✅ Выбрано {count} • ⌘+click добавить • ПКМ меню")
                    else:
                        self.storyboard_status.configure(text=f"📷 {len(self.storyboard_images)} кадров")
                    return
    
    def on_storyboard_right_click(self, event):
        """Правый клик - контекстное меню"""
        x, y = event.x, event.y
        
        # Находим элемент под курсором
        items = self.storyboard_canvas.find_overlapping(x-5, y-5, x+5, y+5)
        clicked_idx = None
        for canvas_item in items:
            tags = self.storyboard_canvas.gettags(canvas_item)
            for tag in tags:
                if tag.startswith("item_"):
                    clicked_idx = int(tag.split("_")[1])
                    break
            if clicked_idx is not None:
                break
        
        # Если кликнули на элемент, добавляем его к выделению если ещё не выбран
        if clicked_idx is not None and clicked_idx not in self.selected_items:
            self.selected_items = {clicked_idx}
            self.clear_selection()
            self.highlight_selected()
        
        # Создаём контекстное меню
        import tkinter as tk
        context_menu = tk.Menu(self.storyboard_canvas, tearoff=0, 
                              bg=COLORS["bg_secondary"], fg=COLORS["text_primary"],
                              activebackground=COLORS["primary"], activeforeground="white",
                              font=(FONT_FAMILY, 12))
        
        if self.selected_items:
            count = len(self.selected_items)
            
            # Расширить (AI Wide)
            if count == 1:
                context_menu.add_command(label="📐 Расширить", 
                                        command=lambda: self.extend_selected_photos())
            else:
                context_menu.add_command(label=f"📐 Расширить ({count} фото)", 
                                        command=lambda: self.extend_selected_photos())
            
            context_menu.add_separator()
            
            # Копировать
            context_menu.add_command(label="📋 Копировать", 
                                    command=lambda: self.copy_selected_storyboard())
            
            # Клонировать
            context_menu.add_command(label="👥 Клонировать", 
                                    command=lambda: self.clone_selected_photos())
            
            context_menu.add_separator()
            
            # Отправить в редактор
            if count == 1:
                context_menu.add_command(label="✏️ Открыть в редакторе", 
                                        command=lambda: self._storyboard_send_to_editor())
            else:
                context_menu.add_command(label=f"✏️ Открыть в редакторе ({count} фото)", 
                                        command=lambda: self._storyboard_send_to_editor())
            
            context_menu.add_separator()
            
            # Удалить
            context_menu.add_command(label="🗑️ Удалить", 
                                    command=lambda: self.delete_selected_storyboard())
        else:
            # Если ничего не выбрано
            context_menu.add_command(label="📁 Загрузить фото", 
                                    command=self.load_storyboard_files)
            context_menu.add_command(label="📂 Загрузить папку", 
                                    command=self.load_storyboard_folder)
        
        # Показываем меню
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()
    
    def _storyboard_send_to_editor(self):
        """Отправляет выбранные фото из раскадровки в редактор"""
        logger.info(f"_storyboard_send_to_editor called, selected_items: {self.selected_items}")
        
        if not self.selected_items:
            logger.warning("No selected items")
            return
        
        # Собираем пути к выбранным фото
        photo_paths = []
        for idx in sorted(self.selected_items):
            if 0 <= idx < len(self.storyboard_images):
                path = self.storyboard_images[idx]["path"]
                logger.info(f"Checking path: {path}, exists: {os.path.exists(path)}")
                if os.path.exists(path):
                    photo_paths.append(path)
        
        if not photo_paths:
            messagebox.showwarning("Внимание", "Не найдены файлы для редактирования")
            return
        
        logger.info(f"Sending {len(photo_paths)} photos to editor")
        
        # Очищаем библиотеку редактора и добавляем выбранные фото
        self.editor_library = []
        self.editor_current_index = 0  # Сбрасываем индекс
        for path in photo_paths:
            self.editor_library.append({
                'path': path,
                'settings': None,
                'selected': False
            })
        
        # Переключаемся на редактор
        self.switch_tab("Редактор")
        
        # Загружаем первое фото с задержкой чтобы canvas успел отрисоваться
        if photo_paths:
            first_path = photo_paths[0]
            logger.info(f"Will load first photo after delay: {first_path}")
            
            def load_delayed():
                logger.info(f"Loading photo now: {first_path}")
                self.editor_load_image(first_path)
                self._update_filmstrip()
                self.status_bar.configure(text=f"✏️ Загружено {len(photo_paths)} фото в редактор")
            
            # Задержка 200мс чтобы canvas успел появиться
            self.after(200, load_delayed)
    
    def clone_selected_photos(self):
        """Клонирует все выбранные фото"""
        import copy
        if not self.selected_items:
            return
        
        self.save_undo_state()
        new_indices = []
        offset = 30
        
        for i, idx in enumerate(sorted(self.selected_items)):
            if 0 <= idx < len(self.storyboard_images):
                original = self.storyboard_images[idx]
                clone = copy.deepcopy(original)
                clone["x"] = original["x"] + offset * (i + 1)
                clone["y"] = original["y"] + offset * (i + 1)
                self.storyboard_images.append(clone)
                new_indices.append(len(self.storyboard_images) - 1)
        
        self.selected_items = set(new_indices)
        self.refresh_storyboard()
        self.storyboard_status.configure(text=f"👥 Клонировано {len(new_indices)} фото • ⌘Z отмена")
    
    def extend_selected_photos(self):
        """Отправляет выбранные фото в AI расширение (Wide) - ДОБАВЛЯЕТ к существующим"""
        if not self.selected_items:
            self.storyboard_status.configure(text="⚠️ Выберите фото для расширения")
            return
        
        # Собираем пути к выбранным фото
        photo_paths = []
        for idx in sorted(self.selected_items):
            if 0 <= idx < len(self.storyboard_images):
                path = self.storyboard_images[idx]["path"]
                # Добавляем только если ещё нет в списке
                if path not in self.wide_images:
                    photo_paths.append(path)
        
        if not photo_paths:
            self.storyboard_status.configure(text="⚠️ Эти фото уже добавлены в Расширить")
            return
        
        # Переключаемся на вкладку AI
        self.switch_tab("AI")
        
        # Устанавливаем модель Wide
        self.ai_model_var.set("wide")
        self._on_model_change()
        
        # ДОБАВЛЯЕМ фото к существующим в Wide модуле (не заменяем!)
        self.wide_images.extend(photo_paths)
        
        # Обновляем превью
        self._update_wide_preview()
        
        total = len(self.wide_images)
        added = len(photo_paths)
        self.storyboard_status.configure(text=f"📐 +{added} фото → всего {total} в Расширить")
        self._ai_log(f"Добавлено {added} фото из раскадровки (всего {total})")
    
    def show_photo_preview(self, idx):
        """Показывает большое превью фото с затемнённым фоном"""
        if idx >= len(self.storyboard_images):
            return
        
        img_path = self.storyboard_images[idx]["path"]
        
        # Создаём окно превью
        preview_window = ctk.CTkToplevel(self)
        preview_window.title(f"🔍 {os.path.basename(img_path)}")
        preview_window.configure(fg_color="#000000")
        preview_window.attributes("-alpha", 0.95)  # Полупрозрачность
        
        # Размер экрана
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        
        # Окно на весь экран
        preview_window.geometry(f"{screen_w}x{screen_h}+0+0")
        preview_window.attributes("-topmost", True)
        
        # Загружаем изображение в большом размере
        try:
            img = Image.open(img_path)
            orig_w, orig_h = img.size
            
            # Масштабируем чтобы влезло в экран с отступами
            max_w = screen_w - 100
            max_h = screen_h - 150
            
            ratio = min(max_w / orig_w, max_h / orig_h)
            new_w = int(orig_w * ratio)
            new_h = int(orig_h * ratio)
            
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            
            # Фрейм для центрирования
            frame = ctk.CTkFrame(preview_window, fg_color="transparent")
            frame.pack(expand=True, fill="both")
            
            # Изображение
            import tkinter as tk
            img_label = tk.Label(frame, image=photo, bg="#000000", cursor="hand2")
            img_label.image = photo  # Сохраняем ссылку
            img_label.pack(expand=True)
            
            # Имя файла и размер
            info_text = f"{os.path.basename(img_path)} • {orig_w}×{orig_h}"
            info_label = ctk.CTkLabel(preview_window, text=info_text,
                                      font=ctk.CTkFont(family=FONT_FAMILY, size=14),
                                      text_color="#ffffff")
            info_label.pack(pady=10)
            
            # Подсказка
            hint_label = ctk.CTkLabel(preview_window, text="Нажмите в любом месте или Esc для закрытия",
                                      font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                                      text_color="#888888")
            hint_label.pack(pady=(0, 20))
            
            # Закрытие по клику или Esc
            def close_preview(event=None):
                preview_window.destroy()
            
            preview_window.bind("<Escape>", close_preview)
            preview_window.bind("<Button-1>", close_preview)
            img_label.bind("<Button-1>", close_preview)
            
            # Фокус на окно
            preview_window.focus_set()
            
        except Exception as e:
            logger.error(f"Ошибка открытия превью: {e}")
            preview_window.destroy()
    
    def setup_pinch_zoom(self):
        """Pinch-to-zoom отключён - используйте ⌘+scroll или +/- кнопки"""
        # PyObjC callback вызывает краши в Tkinter, поэтому отключаем
        logger.info("Pinch-to-zoom disabled - use ⌘+scroll or +/- buttons")
    
    def zoom_in_storyboard(self, event=None):
        """Увеличить масштаб на 25% (Cmd+Plus или кнопка +)"""
        new_scale = min(8.0, self.zoom_scale * 1.25)  # Макс 800% для детального просмотра
        self.zoom_scale = new_scale
        self.refresh_storyboard()
        self.storyboard_status.configure(text=f"🔍 Zoom: {int(new_scale * 100)}% • ⌘+/⌘- или кнопки")
    
    def zoom_out_storyboard(self, event=None):
        """Уменьшить масштаб на 25% (Cmd+Minus или кнопка -)"""
        new_scale = max(0.2, self.zoom_scale / 1.25)
        self.zoom_scale = new_scale
        self.refresh_storyboard()
        self.storyboard_status.configure(text=f"🔍 Zoom: {int(new_scale * 100)}% • ⌘+/⌘- или кнопки")
    
    def on_pan_start(self, event):
        """Начало панорамирования"""
        self.pan_data["x"] = event.x
        self.pan_data["y"] = event.y
    
    def on_storyboard_pan(self, event):
        """Pan (перемещение всего холста)"""
        dx = event.x - self.pan_data["x"]
        dy = event.y - self.pan_data["y"]
        
        # Перемещаем все элементы
        self.storyboard_canvas.move("all", dx, dy)
        
        # Обновляем позиции в данных (в базовых единицах)
        for img in self.storyboard_images:
            img["x"] += dx / self.zoom_scale
            img["y"] += dy / self.zoom_scale
        
        self.pan_data["x"] = event.x
        self.pan_data["y"] = event.y
    
    def on_storyboard_scroll(self, event):
        """Вертикальный scroll (pan) - двухпальцевый жест на trackpad"""
        dy = 0
        if hasattr(event, 'delta') and event.delta != 0:
            if abs(event.delta) >= 100:
                dy = event.delta // 3  # Windows
            else:
                dy = event.delta * 8  # Mac
        elif event.num == 4:
            dy = 30
        elif event.num == 5:
            dy = -30
        
        if dy != 0:
            # Быстрое перемещение без перерисовки
            self.storyboard_canvas.move("all", 0, dy)
            for img in self.storyboard_images:
                img["y"] += dy / self.zoom_scale
    
    def on_storyboard_hscroll(self, event):
        """Горизонтальный scroll (Shift+колёсико)"""
        if hasattr(event, 'delta') and event.delta != 0:
            if abs(event.delta) >= 100:
                dx = event.delta // 3
            else:
                dx = event.delta * 8
            self.storyboard_canvas.move("all", dx, 0)
            for img in self.storyboard_images:
                img["x"] += dx / self.zoom_scale
    
    def on_pinch_zoom(self, event):
        """Плавный pinch-to-zoom (Option+scroll на trackpad)
        
        Если курсор над фото - масштабирует это фото
        Если курсор на пустом месте - масштабирует весь canvas
        """
        if not hasattr(event, 'delta') or event.delta == 0:
            return
        
        x, y = event.x, event.y
        
        # Проверяем, есть ли фото под курсором
        item_under_cursor = None
        items = self.storyboard_canvas.find_overlapping(x-5, y-5, x+5, y+5)
        for canvas_item in items:
            tags = self.storyboard_canvas.gettags(canvas_item)
            for tag in tags:
                if tag.startswith("item_") and not tag.startswith("item_lasso"):
                    try:
                        item_under_cursor = int(tag.split("_")[1])
                        break
                    except:
                        pass
            if item_under_cursor is not None:
                break
        
        # Плавное масштабирование - маленький шаг
        if abs(event.delta) >= 100:
            step = event.delta / 2000
        else:
            step = event.delta / 50
        
        if item_under_cursor is not None:
            # Масштабируем конкретное фото под курсором
            idx = item_under_cursor
            if 0 <= idx < len(self.storyboard_images):
                current_scale = self.storyboard_images[idx].get("scale", 1.0)
                new_scale = max(0.2, min(5.0, current_scale + step))
                self.storyboard_images[idx]["scale"] = new_scale
                self._update_single_item(idx)
                scale_pct = int(new_scale * 100)
                self.storyboard_status.configure(text=f"📐 Фото: {scale_pct}% • Option+scroll или тяни уголок")
        else:
            # Масштабируем весь canvas
            self._pinch_zoom_accumulator += step
            
            if abs(self._pinch_zoom_accumulator) >= 0.02:
                scale_factor = 1 + self._pinch_zoom_accumulator
                new_scale = self.zoom_scale * scale_factor
                
                if 0.2 <= new_scale <= 8.0:
                    self.zoom_scale = new_scale
                    self.refresh_storyboard()
                    zoom_pct = int(new_scale * 100)
                    self.storyboard_status.configure(text=f"🔍 Canvas: {zoom_pct}% • Option+scroll")
                
                self._pinch_zoom_accumulator = 0.0
    
    def on_drop_files(self, event):
        """Обработка drop файлов из Finder
        
        tkinterdnd2 передаёт event.data как строку с путями файлов.
        На Mac пути могут содержать пробелы и быть в фигурных скобках.
        """
        logger.info(f"Drop event received: {event.data[:100]}...")
        
        try:
            # Парсим список файлов из event.data
            # tkinterdnd2 может передавать в разных форматах
            data = event.data
            
            # Если данные в фигурных скобках - это Tcl list
            if data.startswith('{'):
                files = self.tk.splitlist(data)
            else:
                # Иначе разделяем по пробелам, но учитываем что пути могут содержать пробелы
                files = data.split()
            
            logger.info(f"Parsed {len(files)} files from drop")
            
            canvas_w = self.storyboard_canvas.winfo_width() or 800
            
            # Параметры сетки
            thumb_size = 140
            padding = 20
            cols = max(1, (canvas_w - padding * 2) // thumb_size)
            start_idx = len(self.storyboard_images)
            
            added_count = 0
            for path in files:
                # Убираем фигурные скобки если есть
                path = path.strip('{}')
                
                if path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tiff')):
                    logger.debug(f"Adding file: {path}")
                    idx = start_idx + added_count
                    col = idx % cols
                    row = idx // cols
                    x = padding + col * thumb_size
                    y = padding + row * thumb_size
                    self.storyboard_images.append({"path": path, "x": x, "y": y})
                    added_count += 1
                else:
                    logger.debug(f"Skipping non-image file: {path}")
            
            if added_count > 0:
                self.refresh_storyboard()
                self.storyboard_status.configure(text=f"📥 Добавлено {added_count} файлов")
                logger.info(f"Successfully added {added_count} files to storyboard")
            else:
                self.storyboard_status.configure(text="⚠️ Нет подходящих изображений")
                logger.warning("No valid image files in drop")
                
        except Exception as e:
            logger.error(f"Error processing dropped files: {e}")
            logger.error(traceback.format_exc())
            self.storyboard_status.configure(text=f"❌ Ошибка: {e}")
    
    def paste_files_from_finder(self, event=None):
        """Вставка файлов из Finder/Explorer через Cmd+V / Ctrl+V"""
        import subprocess
        
        logger.info("Paste pressed - getting file selection")
        
        try:
            files = []
            
            if sys.platform == "darwin":
                # macOS: AppleScript для получения путей выделенных файлов в Finder
                script = '''
tell application "Finder"
    set theSelection to selection
    if (count of theSelection) > 0 then
        set thePaths to ""
        repeat with theItem in theSelection
            set thePaths to thePaths & (POSIX path of (theItem as alias)) & "
"
        end repeat
        return thePaths
    else
        return ""
    end if
end tell
'''
                result = subprocess.run(
                    ['osascript', '-e', script], 
                    capture_output=True, 
                    text=True,
                    timeout=5
                )
                
                logger.debug(f"osascript result: {result.returncode}")
                
                if result.returncode == 0 and result.stdout.strip():
                    files = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
            
            elif sys.platform == "win32":
                # Windows: получаем файлы из буфера обмена
                try:
                    import tkinter as tk
                    root = self.winfo_toplevel()
                    clipboard = root.clipboard_get()
                    # Проверяем, есть ли пути к файлам в буфере
                    potential_files = clipboard.strip().split('\n')
                    for f in potential_files:
                        f = f.strip()
                        if os.path.isfile(f):
                            files.append(f)
                except:
                    # Пробуем через win32clipboard если доступен
                    try:
                        import win32clipboard
                        import win32con
                        win32clipboard.OpenClipboard()
                        try:
                            data = win32clipboard.GetClipboardData(win32con.CF_HDROP)
                            files = list(data)
                        finally:
                            win32clipboard.CloseClipboard()
                    except:
                        pass
            
            logger.info(f"Found {len(files)} files in selection")
            
            if files:
                canvas_w = self.storyboard_canvas.winfo_width() or 800
                
                # Параметры сетки
                thumb_size = 140
                padding = 20
                cols = max(1, (canvas_w - padding * 2) // thumb_size)
                start_idx = len(self.storyboard_images)
                
                added_count = 0
                for path in files:
                    if path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tiff', '.heic')):
                        idx = start_idx + added_count
                        col = idx % cols
                        row = idx // cols
                        x = padding + col * thumb_size
                        y = padding + row * thumb_size
                        self.storyboard_images.append({"path": path, "x": x, "y": y})
                        added_count += 1
                        logger.info(f"Added: {os.path.basename(path)} at grid ({col}, {row})")
                    else:
                        logger.debug(f"Skipped non-image: {path}")
                
                if added_count > 0:
                    self.refresh_storyboard()
                    self.storyboard_status.configure(text=f"📋 Вставлено {added_count} фото")
                else:
                    self.storyboard_status.configure(text="⚠️ Выделите изображения")
            else:
                hint = "Finder → ⌘V" if sys.platform == "darwin" else "Explorer → Ctrl+V"
                self.storyboard_status.configure(text=f"📋 Выделите файлы в {hint}")
                
        except subprocess.TimeoutExpired:
            self.storyboard_status.configure(text="⏱️ Не отвечает")
        except Exception as e:
            logger.error(f"Paste error: {e}")
            self.storyboard_status.configure(text="❌ Ошибка вставки")
    
    def save_storyboard(self):
        """Cохраняет файлы в папку 'Раскадровка' в рабочей директории"""
        # Сначала сохраняем состояние программы (автосейв)
        self.save_autosave()
        
        if not self.storyboard_images:
            self.storyboard_status.configure(text="✅ Состояние сохранено")
            return
        
        # Создаём папку "Раскадровка" в рабочей директории
        storyboard_folder = os.path.join(self.output_folder, "Раскадровка")
        os.makedirs(storyboard_folder, exist_ok=True)
        
        # Сортируем по позиции: сверху вниз, слева направо (по строкам)
        row_height = 120  # Примерная высота строки
        sorted_images = sorted(self.storyboard_images, 
                              key=lambda item: (item["y"] // row_height, item["x"]))
        
        # Сохраняем файлы
        for idx, item_data in enumerate(sorted_images):
            img_path = item_data["path"]
            ext = os.path.splitext(img_path)[1]
            new_name = f"{idx+1:03d}{ext}"
            shutil.copy(img_path, os.path.join(storyboard_folder, new_name))
        
        self.storyboard_status.configure(text=f"✅ Сохранено {len(sorted_images)} файлов в 'Раскадровка'")
        messagebox.showinfo("Готово", f"Файлы сохранены в:\n{storyboard_folder}\n\nПорядок: слева→направо, сверху→вниз")
        os.system(f'open "{storyboard_folder}"')
    
    # ==================== POLARR (онлайн редактор с коррекцией перспективы) ====================
    def open_polarr(self):
        """Открыть Polarr в браузере и подготовить файл для быстрого вставления (Cmd+V)."""
        import webbrowser
        import tempfile
        import datetime
        
        if not self.editor_original_image and not getattr(self, 'editor_image_path', None):
            messagebox.showinfo("Polarr", "Сначала загрузите фотографию в редактор")
            return
        
        # Убеждаемся, что актуальные правки применены
        self.editor_apply_adjustments_fast()
        current_image = getattr(self, 'editor_current_image', None)
        
        image_path = None
        original_path = getattr(self, 'editor_image_path', None)
        if original_path and os.path.exists(original_path):
            image_path = original_path
        
        # Если есть текущее изображение (с правками), сохраняем временную копию
        temp_path = None
        if current_image is not None:
            try:
                temp_dir = os.path.join(tempfile.gettempdir(), "phototools_polarr")
                os.makedirs(temp_dir, exist_ok=True)
                base_name = os.path.splitext(os.path.basename(original_path or "phototools_image"))[0]
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                temp_path = os.path.join(temp_dir, f"{base_name}_{timestamp}.png")
                current_image.save(temp_path)
                image_path = temp_path
                logger.info(f"Temporary image for Polarr saved: {temp_path}")
            except Exception as err:
                logger.warning(f"Failed to save temp image for Polarr: {err}")
                temp_path = None
        
        # Открываем Polarr в браузере
        webbrowser.open("https://photoeditor.polarr.co/")
        
        if not image_path:
            messagebox.showinfo("Polarr", "Polarr открыт! Выберите файл вручную (нет доступного пути)")
            return
        
        # Копируем путь в буфер обмена, чтобы ⌘V сразу вставил файл
        try:
            import subprocess
            subprocess.run(['pbcopy'], input=image_path.encode(), check=True)
            messagebox.showinfo(
                "Polarr",
                "Polarr открыт!\n\n"
                "Путь к файлу скопирован в буфер обмена.\n"
                "В Polarr нажмите ⌘V или используйте 'Open' → 'Paste URL/File'.\n\n"
                f"Файл: {image_path}")
        except Exception as err:
            logger.warning(f"Failed to copy path to clipboard: {err}")
            messagebox.showinfo("Polarr", f"Polarr открыт!\n\nОткройте файл вручную:\n{image_path}")
    
    # ==================== EDITOR TAB (Lightroom-style) ====================
    def create_editor_tab(self):
        tab = self.tab_editor
        tab.grid_columnconfigure(0, weight=0)  # Панель слайдеров
        tab.grid_columnconfigure(1, weight=1)  # Canvas превью
        tab.grid_rowconfigure(1, weight=1)
        
        # ВАЖНО: Инициализируем переменные редактора ДО создания слайдеров
        self.editor_image_path = None
        self.editor_original_image = None  # Полное разрешение
        self.editor_preview_image = None   # Уменьшенная версия для preview (быстрее)
        self.editor_current_image = None
        self.editor_photo = None
        self.editor_guides = []
        self.editor_show_guides = False
        self.editor_show_grid = False
        self.editor_guide_start = None
        # Система масок (Lightroom-style)
        self.editor_masks = []  # [{name, array, exposure, temperature, saturation, feather}, ...]
        self.editor_current_mask_index = -1  # Индекс текущей маски
        self.editor_mask_mode = None  # 'drawing' или None
        self.editor_mask_drawing = False
        self.editor_show_mask_overlay = True  # Показывать красный оверлей
        self.editor_img_offset = (0, 0)
        self.editor_img_size = (0, 0)
        self.editor_preview_max = 800  # Уменьшено для скорости (было 1200)
        self.editor_checkerboard_image = None  # Кэш шахматного фона
        self.editor_debounce_id = None  # Для debounce слайдеров
        self.editor_original_array = None  # NumPy массив оригинала (для скорости)
        
        # Новые переменные
        self.editor_wb_picker_mode = False  # Режим выбора точки для баланса белого
        self.editor_zoom_level = 1.0  # Уровень зума
        self.editor_zoom_offset = (0, 0)  # Смещение при зуме
        self.editor_show_loupe = False  # Показывать лупу при гайдах
        
        # Undo/Redo история
        self.editor_history = []  # Стек состояний для undo
        self.editor_history_index = -1
        self.editor_max_history = 30
        
        # Библиотека фото (Lightroom-style)
        self.editor_library = []  # [{path, settings, thumbnail}, ...]
        self.editor_current_index = 0
        
        # Заголовок
        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, pady=(5, 5), sticky="ew")
        
        ctk.CTkLabel(header, text="🎨 Редактор фото", 
                    font=ctk.CTkFont(family=FONT_FAMILY, size=20, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(side="left", padx=20)
        
        # Кнопки управления
        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.pack(side="right", padx=20)
        
        ctk.CTkButton(btn_frame, text="📁 Открыть", command=self.editor_load_image,
                     width=80, height=32, font=ctk.CTkFont(size=11),
                     fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
                     corner_radius=8).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="📂 Папка", command=self.editor_load_folder,
                     width=70, height=32, font=ctk.CTkFont(size=11),
                     fg_color=COLORS["secondary"], hover_color=COLORS["secondary_hover"],
                     corner_radius=8).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="💾 Сохранить", command=self.editor_save_image,
                     width=80, height=32, font=ctk.CTkFont(size=11),
                     fg_color=COLORS["success"], hover_color=COLORS["success_hover"],
                     corner_radius=8).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="📤 Экспорт", command=self.editor_export_all,
                     width=70, height=32, font=ctk.CTkFont(size=11),
                     fg_color=COLORS["teal"], hover_color="#0D9488",
                     corner_radius=8).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="🔄 Сброс", command=self.editor_reset,
                     width=70, height=32, font=ctk.CTkFont(size=11),
                     fg_color=COLORS["warning"], hover_color=COLORS["warning_hover"],
                     corner_radius=8).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="🌐 Polarr", command=self.open_polarr,
                     width=80, height=32, font=ctk.CTkFont(size=11),
                     fg_color=COLORS["cyan"], hover_color="#0891B2",
                     corner_radius=8).pack(side="left", padx=2)
        
        # === ЛЕВАЯ ПАНЕЛЬ - СЛАЙДЕРЫ ===
        left_panel = ctk.CTkScrollableFrame(tab, width=280, fg_color=COLORS["bg_secondary"], corner_radius=GLASS_CORNER_RADIUS)
        left_panel.grid(row=1, column=0, padx=(10, 5), pady=5, sticky="ns")
        
        # --- Базовые настройки ---
        ctk.CTkLabel(left_panel, text="📊 Базовые", font=ctk.CTkFont(size=14, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(pady=(10, 5), anchor="w", padx=10)
        
        # Экспозиция
        self.editor_exposure = self._create_slider(left_panel, "Экспозиция", -2.0, 2.0, 0.0)
        # Контраст
        self.editor_contrast = self._create_slider(left_panel, "Контраст", 0.5, 2.0, 1.0)
        # Хайлайты (света)
        self.editor_highlights = self._create_slider(left_panel, "Хайлайты", -100, 100, 0)
        # Тени
        self.editor_shadows = self._create_slider(left_panel, "Тени", -100, 100, 0)
        # Яркость
        self.editor_brightness = self._create_slider(left_panel, "Яркость", 0.5, 2.0, 1.0)
        # Насыщенность
        self.editor_saturation = self._create_slider(left_panel, "Насыщенность", 0.0, 2.0, 1.0)
        
        # --- Цветовая температура ---
        ctk.CTkLabel(left_panel, text="🌡️ Температура", font=ctk.CTkFont(size=14, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(pady=(15, 5), anchor="w", padx=10)
        
        # Температура (холодный - тёплый)
        self.editor_temperature = self._create_slider(left_panel, "Температура", -100, 100, 0)
        # Тинт (зелёный - пурпурный)
        self.editor_tint = self._create_slider(left_panel, "Тинт", -100, 100, 0)
        
        # --- Геометрия и Перспектива (Lightroom-style) ---
        ctk.CTkLabel(left_panel, text="📐 Геометрия", font=ctk.CTkFont(size=14, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(pady=(15, 5), anchor="w", padx=10)
        
        # Вертикаль (keystone vertical - сходящиеся вертикали)
        self.editor_vertical = self._create_slider(left_panel, "Вертикаль", -300, 300, 0)
        # Горизонталь (keystone horizontal)
        self.editor_horizontal = self._create_slider(left_panel, "Горизонталь", -300, 300, 0)
        # Поворот
        self.editor_rotation = self._create_slider(left_panel, "Поворот", -90, 90, 0)
        # Сдвиг X (лево-право)
        self.editor_shift_x = self._create_slider(left_panel, "Сдвиг X", -500, 500, 0)
        # Сдвиг Y (верх-низ)
        self.editor_shift_y = self._create_slider(left_panel, "Сдвиг Y", -500, 500, 0)
        # Aspect (соотношение сторон)
        self.editor_aspect = self._create_slider(left_panel, "Aspect", -50, 50, 0)
        # Scale (масштаб для обрезки)
        self.editor_scale = self._create_slider(left_panel, "Масштаб", 0, 200, 0)
        
        # Кнопки автокоррекции
        auto_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        auto_frame.pack(pady=10, padx=10, fill="x")
        
        auto_row1 = ctk.CTkFrame(auto_frame, fg_color="transparent")
        auto_row1.pack(fill="x", pady=2)
        
        ctk.CTkButton(auto_row1, text="🔄 Авто-вертикаль", command=self.editor_auto_vertical,
                     height=32, font=ctk.CTkFont(size=11),
                     fg_color=COLORS["teal"], hover_color="#0D9488",
                     corner_radius=8).pack(side="left", fill="x", expand=True, padx=(0, 2))
        
        self.wb_btn = ctk.CTkButton(auto_row1, text="🎯 WB", command=self.editor_toggle_wb_picker,
                     width=60, height=32, font=ctk.CTkFont(size=11),
                     fg_color=COLORS["warning"], hover_color=COLORS["warning_hover"],
                     corner_radius=8)
        self.wb_btn.pack(side="left")
        
        # Гайды (макс 4, авто-применение при 2+)
        guide_row = ctk.CTkFrame(auto_frame, fg_color="transparent")
        guide_row.pack(fill="x", pady=2)
        
        self.guides_btn = ctk.CTkButton(guide_row, text="📏 Гайды (0/4)", command=self.editor_toggle_guides,
                     width=110, height=32, font=ctk.CTkFont(size=11),
                     fg_color=COLORS["secondary"], hover_color=COLORS["secondary_hover"],
                     corner_radius=8)
        self.guides_btn.pack(side="left", padx=(0, 2))
        
        ctk.CTkButton(guide_row, text="🗑️ Сброс", command=self.editor_clear_guides,
                     width=70, height=32, font=ctk.CTkFont(size=11),
                     fg_color=COLORS["danger"], hover_color=COLORS["danger_hover"],
                     corner_radius=8).pack(side="left", padx=2)
        
        # Сетка
        self.grid_btn = ctk.CTkButton(auto_frame, text="🔲 Показать сетку", command=self.editor_toggle_grid,
                     height=32, font=ctk.CTkFont(size=11),
                     fg_color=COLORS["bg_tertiary"], hover_color=COLORS["border"],
                     corner_radius=8)
        self.grid_btn.pack(fill="x", pady=2)
        
        # Выбор алгоритма перспективы (GIMP = Стандартный)
        algo_frame = ctk.CTkFrame(auto_frame, fg_color="transparent")
        algo_frame.pack(fill="x", pady=2)
        
        ctk.CTkLabel(algo_frame, text="Алгоритм:", font=ctk.CTkFont(size=10),
                    text_color=COLORS["text_secondary"]).pack(side="left", padx=(0, 5))
        
        algo_values = ["GIMP"]
        if DARKTABLE_ASHIFT_AVAILABLE:
            algo_values.append("Darktable (ashift)")
        
        self.perspective_algo = ctk.CTkOptionMenu(algo_frame, 
                                           values=algo_values,
                                           font=ctk.CTkFont(size=10),
                                           fg_color=COLORS["bg_secondary"],
                                           button_color=COLORS["primary"],
                                           width=120)
        self.perspective_algo.pack(side="left")
        self.perspective_algo.set("GIMP")
        
        # --- Локальные коррекции (Маски) ---
        ctk.CTkLabel(left_panel, text="🎭 Локальные коррекции", font=ctk.CTkFont(size=14, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(pady=(15, 5), anchor="w", padx=10)
        
        # Кнопка создания новой маски
        mask_btn_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        mask_btn_frame.pack(pady=5, padx=10, fill="x")
        
        self.mask_brush_btn = ctk.CTkButton(mask_btn_frame, text="➕ Новая маска", 
                     command=self.editor_new_mask,
                     height=32, font=ctk.CTkFont(size=12),
                     fg_color=COLORS["pink"], hover_color=COLORS["pink_hover"],
                     corner_radius=8)
        self.mask_brush_btn.pack(fill="x")
        
        # Список масок
        ctk.CTkLabel(left_panel, text="Маски:", font=ctk.CTkFont(size=11),
                    text_color=COLORS["text_secondary"]).pack(pady=(5, 2), anchor="w", padx=10)
        
        self.masks_listbox_frame = ctk.CTkFrame(left_panel, fg_color=COLORS["bg_tertiary"], height=80)
        self.masks_listbox_frame.pack(pady=2, padx=10, fill="x")
        self.masks_listbox_frame.pack_propagate(False)
        
        # Scrollable список масок
        self.masks_list = ctk.CTkScrollableFrame(self.masks_listbox_frame, fg_color="transparent", height=70)
        self.masks_list.pack(fill="both", expand=True)
        
        # Режим кисти/ластика
        brush_mode_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        brush_mode_frame.pack(pady=5, padx=10, fill="x")
        
        self.mask_brush_mode = "draw"  # "draw" или "erase"
        
        self.draw_btn = ctk.CTkButton(brush_mode_frame, text="🖌️ Кисть", 
                     command=lambda: self._set_brush_mode("draw"),
                     height=28, font=ctk.CTkFont(size=11),
                     fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
                     corner_radius=6)
        self.draw_btn.pack(side="left", fill="x", expand=True, padx=(0, 2))
        
        self.erase_btn = ctk.CTkButton(brush_mode_frame, text="🧹 Ластик", 
                     command=lambda: self._set_brush_mode("erase"),
                     height=28, font=ctk.CTkFont(size=11),
                     fg_color=COLORS["bg_tertiary"], hover_color=COLORS["border"],
                     corner_radius=6)
        self.erase_btn.pack(side="left", fill="x", expand=True, padx=(2, 0))
        
        # Настройки кисти
        self.mask_brush_size = self._create_slider(left_panel, "Размер кисти", 10, 200, 50)
        self.mask_feather = self._create_mask_slider(left_panel, "Feather", 0, 100, 30)
        
        # Локальные коррекции для маски (с реалтайм превью)
        ctk.CTkLabel(left_panel, text="Коррекция:", font=ctk.CTkFont(size=11),
                    text_color=COLORS["text_secondary"]).pack(pady=(5, 2), anchor="w", padx=10)
        self.mask_exposure = self._create_mask_slider(left_panel, "Экспозиция", -2.0, 2.0, 0.0)
        self.mask_highlights = self._create_mask_slider(left_panel, "Хайлайты", -100, 100, 0)
        self.mask_shadows = self._create_mask_slider(left_panel, "Тени", -100, 100, 0)
        self.mask_temperature = self._create_mask_slider(left_panel, "Температура", -100, 100, 0)
        self.mask_saturation = self._create_mask_slider(left_panel, "Насыщенность", 0.0, 2.0, 1.0)
        
        # Кнопки управления
        mask_ctrl = ctk.CTkFrame(left_panel, fg_color="transparent")
        mask_ctrl.pack(pady=5, padx=10, fill="x")
        
        self.mask_overlay_btn = ctk.CTkButton(mask_ctrl, text="👁️ Скрыть", command=self.editor_toggle_mask_view,
                     width=70, height=28, font=ctk.CTkFont(size=10),
                     fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
                     corner_radius=8)
        self.mask_overlay_btn.pack(side="left", padx=2)
        
        # --- Коррекция объектива (Darktable-style) ---
        ctk.CTkLabel(left_panel, text="📷 Коррекция объектива", font=ctk.CTkFont(size=14, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(pady=(15, 5), anchor="w", padx=10)
        
        # Дисторсия (бочка/подушка)
        self.editor_distortion = self._create_slider(left_panel, "Дисторсия", -100, 100, 0)
        # Виньетирование
        self.editor_vignette = self._create_slider(left_panel, "Виньетка", -100, 100, 0)
        # Хроматические аберрации
        self.editor_chromatic = self._create_slider(left_panel, "Хром. аберрации", -50, 50, 0)
        
        # Кнопка автокоррекции объектива
        if LENSFUN_AVAILABLE:
            ctk.CTkButton(left_panel, text="🔧 Авто-коррекция объектива", 
                         command=self.editor_auto_lens_correction,
                         height=32, font=ctk.CTkFont(size=11),
                         fg_color=COLORS["teal"], hover_color="#0D9488",
                         corner_radius=8).pack(fill="x", padx=10, pady=5)
        
        # --- Тоновая кривая (Darktable-style) ---
        ctk.CTkLabel(left_panel, text="📈 Тоновая кривая", font=ctk.CTkFont(size=14, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(pady=(15, 5), anchor="w", padx=10)
        
        # Точки кривой (тени, средние, света)
        self.editor_curve_blacks = self._create_slider(left_panel, "Чёрные", -50, 50, 0)
        self.editor_curve_shadows = self._create_slider(left_panel, "Тени (кривая)", -50, 50, 0)
        self.editor_curve_midtones = self._create_slider(left_panel, "Средние", -50, 50, 0)
        self.editor_curve_highlights = self._create_slider(left_panel, "Света (кривая)", -50, 50, 0)
        self.editor_curve_whites = self._create_slider(left_panel, "Белые", -50, 50, 0)
        
        # --- Резкость и шумоподавление ---
        ctk.CTkLabel(left_panel, text="🔍 Детализация", font=ctk.CTkFont(size=14, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(pady=(15, 5), anchor="w", padx=10)
        
        self.editor_sharpness = self._create_slider(left_panel, "Резкость", 0, 200, 0)
        self.editor_denoise = self._create_slider(left_panel, "Шумоподавление", 0, 100, 0)
        self.editor_clarity = self._create_slider(left_panel, "Clarity", -100, 100, 0)
        
        # === ПРАВАЯ ПАНЕЛЬ - CANVAS ===
        import tkinter as tk
        canvas_frame = ctk.CTkFrame(tab, fg_color=COLORS["bg_tertiary"], corner_radius=GLASS_CORNER_RADIUS)
        canvas_frame.grid(row=1, column=1, padx=(5, 10), pady=5, sticky="nsew")
        
        # Основной canvas для изображения
        self.editor_canvas = tk.Canvas(canvas_frame, bg="#1a1a2e", highlightthickness=0)
        self.editor_canvas.pack(fill="both", expand=True, padx=5, pady=(5, 0))
        
        # Filmstrip (превью фотографий внизу)
        self.filmstrip_frame = ctk.CTkFrame(canvas_frame, height=80, fg_color=COLORS["bg_secondary"])
        self.filmstrip_frame.pack(fill="x", padx=5, pady=5)
        self.filmstrip_frame.pack_propagate(False)
        
        # Scrollable filmstrip
        self.filmstrip_canvas = tk.Canvas(self.filmstrip_frame, bg=COLORS["bg_secondary"], 
                                          height=70, highlightthickness=0)
        self.filmstrip_canvas.pack(fill="both", expand=True)
        self.filmstrip_thumbnails = []  # Хранит PhotoImage объекты
        
        # Привязка событий для рисования гайдов
        self.editor_canvas.bind("<Button-1>", self.editor_canvas_click)
        self.editor_canvas.bind("<B1-Motion>", self.editor_canvas_drag)
        self.editor_canvas.bind("<ButtonRelease-1>", self.editor_canvas_release)
        
        # ПКМ для контекстного меню (Button-3 + Control+Click для Mac)
        self.editor_canvas.bind("<Button-3>", self._editor_right_click)
        self.editor_canvas.bind("<Control-Button-1>", self._editor_right_click)
        
        # Zoom колёсиком мыши / trackpad
        self.editor_canvas.bind("<MouseWheel>", self.editor_canvas_zoom)
        self.editor_canvas.bind("<Command-MouseWheel>", self.editor_canvas_zoom)
        self.editor_canvas.bind("<Control-MouseWheel>", self.editor_canvas_zoom)
        
        # Pan при зуме
        self.editor_canvas.bind("<Button-2>", self.editor_canvas_pan_start)
        self.editor_canvas.bind("<B2-Motion>", self.editor_canvas_pan)
        self.editor_canvas.bind("<Shift-Button-1>", self.editor_canvas_pan_start)
        self.editor_canvas.bind("<Shift-B1-Motion>", self.editor_canvas_pan)
        
        # Навигация стрелками
        self.bind("<Left>", lambda e: self._navigate_library(-1))
        self.bind("<Right>", lambda e: self._navigate_library(1))
        
        # Undo/Redo (привязываем к canvas и главному окну)
        self.bind("<Command-z>", lambda e: self.editor_undo())
        self.bind("<Control-z>", lambda e: self.editor_undo())
        self.bind("<Command-Shift-z>", lambda e: self.editor_redo())
        self.bind("<Control-Shift-z>", lambda e: self.editor_redo())
        self.editor_canvas.bind("<Command-z>", lambda e: self.editor_undo())
        self.editor_canvas.bind("<Control-z>", lambda e: self.editor_undo())
        self.bind_all("<Command-z>", lambda e: self.editor_undo())  # Глобальная привязка
        self.bind_all("<Control-z>", lambda e: self.editor_undo())
        # Русская раскладка (я = z на русской)
        self.bind_all("<Command-Cyrillic_ya>", lambda e: self.editor_undo())
        self.bind_all("<Control-Cyrillic_ya>", lambda e: self.editor_undo())
        # Альтернативный способ через keycode
        self.bind_all("<Key>", self._handle_undo_key)
        
        # Движение мыши для превью кисти и лупы в режиме гайдов
        self.editor_canvas.bind("<Motion>", self.editor_canvas_motion)
        self.editor_canvas.bind("<Leave>", self.editor_canvas_leave)
        
        # Применить настройки ко всем выбранным (Cmd+A)
        self.bind("<Command-a>", lambda e: self.editor_apply_to_selected())
        self.bind("<Control-a>", lambda e: self.editor_apply_to_selected())
        
        # Placeholder текст
        self.editor_canvas.create_text(
            400, 200, text="📁 Загрузите изображение для редактирования",
            font=(FONT_FAMILY, 16), fill=COLORS["text_secondary"], tags="placeholder"
        )
    
    def _create_slider(self, parent, label, from_, to, default):
        """Создаёт слайдер с меткой, полем ввода значения и высокой чувствительностью"""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(pady=3, padx=10, fill="x")
        
        # Метка и поле ввода значения
        label_frame = ctk.CTkFrame(frame, fg_color="transparent")
        label_frame.pack(fill="x")
        
        ctk.CTkLabel(label_frame, text=label, font=ctk.CTkFont(size=11),
                    text_color=COLORS["text_secondary"]).pack(side="left")
        
        # Поле ввода вместо простой метки
        is_float = isinstance(default, float)
        entry_var = ctk.StringVar(value=f"{default:.2f}" if is_float else str(int(default)))
        
        value_entry = ctk.CTkEntry(label_frame, textvariable=entry_var,
                                   width=55, height=22, font=ctk.CTkFont(size=10),
                                   fg_color=COLORS["bg_tertiary"], border_width=1,
                                   border_color=COLORS["border"], text_color=COLORS["text_primary"],
                                   justify="right")
        value_entry.pack(side="right")
        
        # Вычисляем количество шагов для шага = 1 (или 0.01 для float)
        range_size = to - from_
        if is_float:
            num_steps = int(range_size * 100)  # Шаг 0.01
        else:
            num_steps = int(range_size)  # Шаг 1
        num_steps = max(100, min(num_steps, 2000))  # Ограничиваем разумным диапазоном
        
        # Слайдер с высокой чувствительностью
        slider = ctk.CTkSlider(frame, from_=from_, to=to, number_of_steps=num_steps,
                              fg_color=COLORS["bg_tertiary"], progress_color=COLORS["primary"],
                              button_color=COLORS["primary"], button_hover_color=COLORS["primary_hover"],
                              height=16)
        slider.set(default)
        slider.pack(fill="x", pady=(2, 0))
        
        # Обновление поля ввода при изменении слайдера
        def update_from_slider(val):
            if is_float:
                entry_var.set(f"{val:.2f}")
            else:
                entry_var.set(str(int(round(val))))
            
            # Debounce
            if self.editor_debounce_id:
                self.after_cancel(self.editor_debounce_id)
            self.editor_debounce_id = self.after(30, self._apply_adjustments_debounced)
        
        slider.configure(command=update_from_slider)
        
        # Обновление слайдера при вводе значения в поле
        def update_from_entry(event=None):
            try:
                val = float(entry_var.get())
                val = max(from_, min(to, val))  # Ограничиваем диапазоном
                slider.set(val)
                if is_float:
                    entry_var.set(f"{val:.2f}")
                else:
                    entry_var.set(str(int(round(val))))
                self._apply_adjustments_debounced()
            except ValueError:
                pass  # Игнорируем некорректный ввод
        
        value_entry.bind("<Return>", update_from_entry)
        value_entry.bind("<FocusOut>", update_from_entry)
        
        return slider
    
    def _create_mask_slider(self, parent, label, from_, to, default):
        """Создаёт слайдер для маски с реалтайм превью"""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(pady=2, padx=10, fill="x")
        
        label_frame = ctk.CTkFrame(frame, fg_color="transparent")
        label_frame.pack(fill="x")
        
        ctk.CTkLabel(label_frame, text=label, font=ctk.CTkFont(size=10),
                    text_color=COLORS["text_secondary"]).pack(side="left")
        
        value_label = ctk.CTkLabel(label_frame, text=f"{default:.1f}" if isinstance(default, float) else str(default),
                                   font=ctk.CTkFont(size=10), text_color=COLORS["text_primary"])
        value_label.pack(side="right")
        
        slider = ctk.CTkSlider(frame, from_=from_, to=to, number_of_steps=100,
                              fg_color=COLORS["bg_tertiary"], progress_color=COLORS["pink"],
                              button_color=COLORS["pink"], button_hover_color=COLORS["pink_hover"],
                              height=14)
        slider.set(default)
        slider.pack(fill="x", pady=(1, 0))
        
        def update_mask_value(val):
            if isinstance(default, float):
                value_label.configure(text=f"{val:.1f}")
            else:
                value_label.configure(text=f"{int(val)}")
            # Обновляем текущую маску и применяем превью
            self._update_current_mask_settings()
            self._apply_masks_preview()
        
        slider.configure(command=update_mask_value)
        return slider
    
    def editor_new_mask(self):
        """Создаёт новую маску"""
        if self.editor_original_array is None:
            messagebox.showwarning("Внимание", "Сначала загрузите изображение")
            return
        
        h, w = self.editor_original_array.shape[:2]
        mask_name = f"Маска {len(self.editor_masks) + 1}"
        
        new_mask = {
            'name': mask_name,
            'array': np.zeros((h, w), dtype=np.float32),
            'exposure': 0.0,
            'highlights': 0,
            'shadows': 0,
            'temperature': 0,
            'saturation': 1.0,
            'feather': 30
        }
        
        self.editor_masks.append(new_mask)
        self.editor_current_mask_index = len(self.editor_masks) - 1
        self.editor_mask_mode = 'drawing'
        self.editor_canvas.configure(cursor="circle")
        
        self._update_masks_list()
        self._reset_mask_sliders()
        logger.info(f"New mask created: {mask_name}")
    
    def _update_masks_list(self):
        """Обновляет список масок в UI с кнопкой удаления"""
        # Очищаем список
        for widget in self.masks_list.winfo_children():
            widget.destroy()
        
        for i, mask in enumerate(self.editor_masks):
            is_current = (i == self.editor_current_mask_index)
            
            row = ctk.CTkFrame(self.masks_list, fg_color="transparent")
            row.pack(fill="x", pady=1)
            
            # Кнопка выбора маски
            btn = ctk.CTkButton(
                row, 
                text=f"{'▶ ' if is_current else ''}{mask['name']}",
                command=lambda idx=i: self._select_mask(idx),
                height=22, font=ctk.CTkFont(size=10),
                fg_color=COLORS["primary"] if is_current else COLORS["bg_tertiary"],
                hover_color=COLORS["primary_hover"] if is_current else COLORS["border"],
                corner_radius=4
            )
            btn.pack(side="left", fill="x", expand=True)
            
            # Кнопка вкл/выкл эффекта маски (⚡)
            is_enabled = mask.get('enabled', True)
            enable_btn = ctk.CTkButton(
                row, text="⚡" if is_enabled else "○",
                command=lambda idx=i: self._toggle_mask_enabled(idx),
                width=24, height=22, font=ctk.CTkFont(size=10),
                fg_color=COLORS["teal"] if is_enabled else COLORS["bg_tertiary"],
                hover_color="#0D9488",
                corner_radius=4
            )
            enable_btn.pack(side="right", padx=1)
            
            # Кнопка подсветки (👁️)
            is_visible = mask.get('visible', True)
            eye_btn = ctk.CTkButton(
                row, text="👁️" if is_visible else "○",
                command=lambda idx=i: self._toggle_mask_visibility(idx),
                width=24, height=22, font=ctk.CTkFont(size=10),
                fg_color=COLORS["primary"] if is_visible else COLORS["bg_tertiary"],
                hover_color=COLORS["primary_hover"],
                corner_radius=4
            )
            eye_btn.pack(side="right", padx=1)
            
            # Кнопка удаления (🗑️)
            del_btn = ctk.CTkButton(
                row, text="🗑️",
                command=lambda idx=i: self._delete_mask(idx),
                width=24, height=22, font=ctk.CTkFont(size=10),
                fg_color=COLORS["danger"], hover_color=COLORS["danger_hover"],
                corner_radius=4
            )
            del_btn.pack(side="right", padx=1)
    
    def _set_brush_mode(self, mode):
        """Переключает режим кисти: draw или erase"""
        self.mask_brush_mode = mode
        
        if mode == "draw":
            self.draw_btn.configure(fg_color=COLORS["primary"])
            self.erase_btn.configure(fg_color=COLORS["bg_tertiary"])
        else:
            self.draw_btn.configure(fg_color=COLORS["bg_tertiary"])
            self.erase_btn.configure(fg_color=COLORS["danger"])
        
        logger.info(f"Brush mode: {mode}")
    
    def _toggle_mask_enabled(self, index):
        """Переключает применение эффекта маски (вкл/выкл коррекцию)"""
        if 0 <= index < len(self.editor_masks):
            mask = self.editor_masks[index]
            mask['enabled'] = not mask.get('enabled', True)
            self._update_masks_list()
            self._apply_masks_preview()
            logger.info(f"Mask {index} enabled: {mask['enabled']}")
    
    def _toggle_mask_visibility(self, index):
        """Переключает видимость маски (подсветка красным)"""
        if 0 <= index < len(self.editor_masks):
            mask = self.editor_masks[index]
            mask['visible'] = not mask.get('visible', True)
            self._update_masks_list()
            self.editor_display_image()
    
    def _delete_mask(self, index):
        """Удаляет маску по индексу"""
        if 0 <= index < len(self.editor_masks):
            del self.editor_masks[index]
            if self.editor_current_mask_index >= len(self.editor_masks):
                self.editor_current_mask_index = len(self.editor_masks) - 1
            if self.editor_current_mask_index < 0:
                self.editor_mask_mode = None
                self.editor_canvas.configure(cursor="")
            self._update_masks_list()
            self._apply_masks_preview()
    
    def _select_mask(self, index):
        """Выбирает маску по индексу"""
        if 0 <= index < len(self.editor_masks):
            self.editor_current_mask_index = index
            self.editor_mask_mode = 'drawing'
            self.editor_canvas.configure(cursor="circle")
            
            # Загружаем настройки маски в слайдеры
            mask = self.editor_masks[index]
            self.mask_exposure.set(mask['exposure'])
            self.mask_highlights.set(mask.get('highlights', 0))
            self.mask_shadows.set(mask.get('shadows', 0))
            self.mask_temperature.set(mask['temperature'])
            self.mask_saturation.set(mask['saturation'])
            self.mask_feather.set(mask['feather'])
            
            self._update_masks_list()
            self._apply_masks_preview()
    
    def _reset_mask_sliders(self):
        """Сбрасывает слайдеры маски"""
        self.mask_exposure.set(0.0)
        self.mask_highlights.set(0)
        self.mask_shadows.set(0)
        self.mask_temperature.set(0)
        self.mask_saturation.set(1.0)
        self.mask_feather.set(30)
    
    def _update_current_mask_settings(self):
        """Обновляет настройки текущей маски из слайдеров"""
        if 0 <= self.editor_current_mask_index < len(self.editor_masks):
            mask = self.editor_masks[self.editor_current_mask_index]
            mask['exposure'] = float(self.mask_exposure.get())
            mask['highlights'] = float(self.mask_highlights.get())
            mask['shadows'] = float(self.mask_shadows.get())
            mask['temperature'] = float(self.mask_temperature.get())
            mask['saturation'] = float(self.mask_saturation.get())
            mask['feather'] = int(self.mask_feather.get())
    
    def _apply_masks_preview(self):
        """Применяет все маски для превью"""
        if self.editor_original_array is None:
            return
        
        # Начинаем с оригинала
        arr = self.editor_original_array.copy()
        
        # Применяем каждую маску
        for mask_data in self.editor_masks:
            # Пропускаем отключённые маски
            if not mask_data.get('enabled', True):
                continue
            
            mask = mask_data['array'].copy()  # Копируем чтобы не изменять оригинал
            if np.max(mask) < 0.01:
                continue  # Пустая маска
            
            # Применяем feather (размытие краёв)
            feather = mask_data.get('feather', 0)
            if feather > 0:
                try:
                    import cv2
                    # Размер ядра должен быть нечётным
                    kernel_size = feather * 2 + 1
                    if kernel_size % 2 == 0:
                        kernel_size += 1
                    # Sigma пропорционален feather для более заметного эффекта
                    sigma = feather * 0.5
                    mask = cv2.GaussianBlur(mask, (kernel_size, kernel_size), sigma)
                    logger.debug(f"Applied feather {feather} to mask, kernel={kernel_size}")
                except Exception as e:
                    logger.error(f"Feather error: {e}")
            
            mask_3d = mask[:,:,np.newaxis]
            
            # Экспозиция
            exp = mask_data['exposure']
            if abs(exp) > 0.01:
                factor = 2 ** exp
                corrected = arr * factor
                arr = arr * (1 - mask_3d) + corrected * mask_3d
            
            # Хайлайты (света)
            highlights = mask_data.get('highlights', 0)
            if abs(highlights) > 1:
                lum = 0.299 * arr[:,:,0] + 0.587 * arr[:,:,1] + 0.114 * arr[:,:,2]
                # Маска светов (яркость > 180)
                highlight_mask = np.clip((lum - 150) / 80, 0, 1)[:,:,np.newaxis]
                factor = 1 + highlights / 100
                corrected = arr * factor
                combined_mask = mask_3d * highlight_mask
                arr = arr * (1 - combined_mask) + corrected * combined_mask
            
            # Тени
            shadows = mask_data.get('shadows', 0)
            if abs(shadows) > 1:
                lum = 0.299 * arr[:,:,0] + 0.587 * arr[:,:,1] + 0.114 * arr[:,:,2]
                # Маска теней (яркость < 80)
                shadow_mask = np.clip((80 - lum) / 60, 0, 1)[:,:,np.newaxis]
                factor = 1 + shadows / 100
                corrected = arr * factor
                combined_mask = mask_3d * shadow_mask
                arr = arr * (1 - combined_mask) + corrected * combined_mask
            
            # Температура
            temp = mask_data['temperature']
            if abs(temp) > 1:
                corrected = arr.copy()
                corrected[:,:,0] = corrected[:,:,0] + temp * 0.6
                corrected[:,:,2] = corrected[:,:,2] - temp * 0.6
                arr = arr * (1 - mask_3d) + corrected * mask_3d
            
            # Насыщенность
            sat = mask_data['saturation']
            if abs(sat - 1.0) > 0.01:
                lum = 0.299 * arr[:,:,0] + 0.587 * arr[:,:,1] + 0.114 * arr[:,:,2]
                lum = lum[:,:,np.newaxis]
                corrected = lum + (arr - lum) * sat
                arr = arr * (1 - mask_3d) + corrected * mask_3d
        
        arr = np.clip(arr, 0, 255)
        self.editor_current_image = Image.fromarray(arr.astype(np.uint8))
        self.editor_display_image()
    
    def editor_delete_current_mask(self):
        """Удаляет текущую маску"""
        if 0 <= self.editor_current_mask_index < len(self.editor_masks):
            del self.editor_masks[self.editor_current_mask_index]
            self.editor_current_mask_index = min(self.editor_current_mask_index, len(self.editor_masks) - 1)
            self._update_masks_list()
            self._apply_masks_preview()
            self.editor_mask_mode = None
            self.editor_canvas.configure(cursor="")
    
    def editor_toggle_mask_view(self):
        """Переключает отображение маски"""
        self.editor_show_mask_overlay = not self.editor_show_mask_overlay
        if self.editor_show_mask_overlay:
            self.mask_overlay_btn.configure(text="👁️ Скрыть", fg_color=COLORS["primary"])
        else:
            self.mask_overlay_btn.configure(text="👁️ Показать", fg_color=COLORS["bg_tertiary"])
        self.editor_display_image()
    
    def editor_load_image(self, path=None):
        """Загрузка изображения для редактирования"""
        if path is None:
            path = filedialog.askopenfilename(filetypes=[("Images", "*.jpg *.jpeg *.png *.webp *.tiff")])
        
        if path and os.path.exists(path):
            logger.info(f"Editor: loading {path}")
            self.editor_image_path = path
            
            # Загружаем оригинал
            self.editor_original_image = Image.open(path).convert("RGB")
            orig_w, orig_h = self.editor_original_image.size
            
            # Создаём preview версию для быстрой работы
            if max(orig_w, orig_h) > self.editor_preview_max:
                scale = self.editor_preview_max / max(orig_w, orig_h)
                new_size = (int(orig_w * scale), int(orig_h * scale))
                self.editor_preview_image = self.editor_original_image.resize(new_size, Image.Resampling.LANCZOS)
                logger.info(f"Created preview: {new_size} from {orig_w}x{orig_h}")
            else:
                self.editor_preview_image = self.editor_original_image
            
            # Конвертируем в numpy для быстрой обработки
            self.editor_original_array = np.array(self.editor_preview_image, dtype=np.float32)
            
            self.editor_current_image = self.editor_preview_image.copy()
            self.editor_reset_sliders()
            self.editor_display_image()
    
    def editor_reset_sliders(self):
        """Сброс всех слайдеров к значениям по умолчанию"""
        self.editor_exposure.set(0.0)
        self.editor_contrast.set(1.0)
        self.editor_highlights.set(0)
        self.editor_shadows.set(0)
        self.editor_brightness.set(1.0)
        self.editor_saturation.set(1.0)
        self.editor_temperature.set(0)
        self.editor_tint.set(0)
        self.editor_vertical.set(0)
        self.editor_horizontal.set(0)
        self.editor_rotation.set(0)
        self.editor_shift_x.set(0)
        self.editor_shift_y.set(0)
        self.editor_aspect.set(0)
        self.editor_scale.set(0)
    
    def _calculate_auto_scale(self, H, w, h):
        """
        Вычисляет необходимый масштаб (zoom), чтобы после трансформации H
        не было видно черных полей (вписывает проекцию экрана в исходник).
        H: матрица Dst -> Src (un-projection).
        """
        try:
            # Проверка на вырожденную матрицу
            if np.linalg.det(H) < 1e-10:
                logger.warning("Degenerate homography matrix, returning default scale")
                return 1.0
            
            # Углы экрана (Dst)
            corners_dst = np.array([
                [0, 0, 1],
                [w, 0, 1],
                [w, h, 1],
                [0, h, 1]
            ], dtype=np.float32).T
            
            # Проекция углов экрана на исходник (Src)
            corners_src = H @ corners_dst
            
            # Защита от деления на ноль
            z_vals = corners_src[2, :]
            if np.any(np.abs(z_vals) < 1e-10):
                logger.warning("Near-zero z values in homography, returning default scale")
                return 1.0
            
            corners_src /= z_vals
            
            xs = corners_src[0, :]
            ys = corners_src[1, :]
            
            # Проверка на NaN/Inf
            if np.any(np.isnan(xs)) or np.any(np.isnan(ys)) or np.any(np.isinf(xs)) or np.any(np.isinf(ys)):
                logger.warning("NaN/Inf in projected corners, returning default scale")
                return 1.0
            
            cx, cy = w / 2.0, h / 2.0
            
            k_min = 1.0
            
            # Для каждой точки проверяем, насколько нужно сжать к центру
            for x, y in zip(xs, ys):
                dx = x - cx
                dy = y - cy
                
                # По X
                if x < 0 and abs(dx) > 1e-6:
                    k = -cx / dx
                    if k < k_min: k_min = k
                elif x > w and abs(dx) > 1e-6:
                    k = (w - cx) / dx
                    if k < k_min: k_min = k
                    
                # По Y
                if y < 0 and abs(dy) > 1e-6:
                    k = -cy / dy
                    if k < k_min: k_min = k
                elif y > h and abs(dy) > 1e-6:
                    k = (h - cy) / dy
                    if k < k_min: k_min = k
            
            # k_min - это коэффициент сжатия области src (<1).
            # Нам нужен Scale factor > 1 (zoom), который равен 1/k.
            if k_min < 0.001: 
                return 1.0
            
            result = 1.0 / k_min
            # Ограничиваем максимальный зум
            return min(result, 5.0)
            
        except Exception as e:
            logger.error(f"Error in _calculate_auto_scale: {e}")
            return 1.0

    def _handle_undo_key(self, event):
        """Обработка Cmd+Z для любой раскладки"""
        # Проверяем Cmd (Mac) или Ctrl (Windows/Linux)
        if (event.state & 0x8) or (event.state & 0x4):  # Command или Control
            # keycode 6 = z на Mac
            if event.keycode == 6 or event.keysym.lower() in ('z', 'я', 'cyrillic_ya'):
                if event.state & 0x1:  # Shift
                    self.editor_redo()
                else:
                    self.editor_undo()
                return "break"
    
    def editor_reset(self):
        """Полный сброс редактора"""
        if self.editor_original_image:
            self.editor_current_image = self.editor_original_image.copy()
            self.editor_reset_sliders()
            self.editor_guides = []
            self.editor_masks = []
            self.editor_history = []
            self.editor_history_index = -1
            self.editor_display_image()
    
    def _save_to_history(self):
        """Сохраняет текущее состояние в историю для undo"""
        state = {
            'exposure': self.editor_exposure.get(),
            'contrast': self.editor_contrast.get(),
            'highlights': self.editor_highlights.get(),
            'shadows': self.editor_shadows.get(),
            'brightness': self.editor_brightness.get(),
            'saturation': self.editor_saturation.get(),
            'temperature': self.editor_temperature.get(),
            'tint': self.editor_tint.get(),
            'vertical': self.editor_vertical.get(),
            'horizontal': self.editor_horizontal.get(),
            'rotation': self.editor_rotation.get(),
            'aspect': self.editor_aspect.get(),
            'scale': self.editor_scale.get(),
        }
        
        # Проверяем, отличается ли от последнего состояния
        if self.editor_history:
            last = self.editor_history[self.editor_history_index] if self.editor_history_index >= 0 else None
            if last and all(abs(state[k] - last[k]) < 0.001 for k in state):
                return  # Не сохраняем дубликаты
        
        # Удаляем будущие состояния если мы в середине истории
        if self.editor_history_index < len(self.editor_history) - 1:
            self.editor_history = self.editor_history[:self.editor_history_index + 1]
        
        self.editor_history.append(state)
        
        # Ограничиваем размер истории
        if len(self.editor_history) > self.editor_max_history:
            self.editor_history.pop(0)
        
        self.editor_history_index = len(self.editor_history) - 1
        logger.debug(f"History saved: {self.editor_history_index + 1}/{len(self.editor_history)}")
    
    def editor_undo(self):
        """Отмена последнего изменения (Cmd+Z)"""
        if self.editor_history_index > 0:
            self.editor_history_index -= 1
            state = self.editor_history[self.editor_history_index]
            self._apply_state(state)
            logger.debug(f"Undo: step {self.editor_history_index + 1}/{len(self.editor_history)}")
    
    def editor_redo(self):
        """Повтор отменённого изменения (Cmd+Shift+Z)"""
        if self.editor_history_index < len(self.editor_history) - 1:
            self.editor_history_index += 1
            state = self.editor_history[self.editor_history_index]
            self._apply_state(state)
            logger.debug(f"Redo: step {self.editor_history_index + 1}/{len(self.editor_history)}")
    
    def _apply_state(self, state):
        """Применяет состояние из истории без сохранения в историю"""
        self.editor_exposure.set(state['exposure'])
        self.editor_contrast.set(state['contrast'])
        self.editor_highlights.set(state.get('highlights', 0))
        self.editor_shadows.set(state.get('shadows', 0))
        self.editor_brightness.set(state['brightness'])
        self.editor_saturation.set(state['saturation'])
        self.editor_temperature.set(state['temperature'])
        self.editor_tint.set(state['tint'])
        self.editor_vertical.set(state['vertical'])
        self.editor_horizontal.set(state['horizontal'])
        self.editor_rotation.set(state['rotation'])
        self.editor_aspect.set(state['aspect'])
        self.editor_scale.set(state['scale'])
        # Применяем без сохранения в историю
        self._apply_adjustments_no_history()
    
    def _get_checkerboard_image(self, canvas_w, canvas_h):
        """Возвращает кэшированное изображение шахматного фона"""
        # Проверяем кэш
        if (self.editor_checkerboard_image and 
            hasattr(self, '_checkerboard_size') and 
            self._checkerboard_size == (canvas_w, canvas_h)):
            return self.editor_checkerboard_photo
        
        # Создаём новое изображение шахматного фона
        cell_size = 16
        colors = [(58, 58, 58), (42, 42, 42)]
        
        # Создаём через numpy (быстрее)
        arr = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
        for row in range(0, canvas_h, cell_size):
            for col in range(0, canvas_w, cell_size):
                color = colors[(row // cell_size + col // cell_size) % 2]
                arr[row:row+cell_size, col:col+cell_size] = color
        
        img = Image.fromarray(arr)
        self.editor_checkerboard_image = img
        self.editor_checkerboard_photo = ImageTk.PhotoImage(img)
        self._checkerboard_size = (canvas_w, canvas_h)
        
        return self.editor_checkerboard_photo
    
    def editor_display_image(self):
        """Отображение текущего изображения на canvas с поддержкой zoom"""
        if not self.editor_current_image:
            return
        
        self.editor_canvas.delete("all")
        
        canvas_w = self.editor_canvas.winfo_width() or 800
        canvas_h = self.editor_canvas.winfo_height() or 500
        
        # Рисуем шахматный фон (кэшированный)
        checkerboard = self._get_checkerboard_image(canvas_w, canvas_h)
        self.editor_canvas.create_image(0, 0, anchor="nw", image=checkerboard, tags="checkerboard")
        
        img = self.editor_current_image
        img_w, img_h = img.size
        
        # Базовый масштаб (fit to canvas)
        base_scale = min(canvas_w / img_w, canvas_h / img_h, 1.0)
        
        # Применяем zoom
        total_scale = base_scale * self.editor_zoom_level
        new_w = int(img_w * total_scale)
        new_h = int(img_h * total_scale)
        
        # Позиция с учётом zoom offset
        if self.editor_zoom_level == 1.0:
            x = (canvas_w - new_w) // 2
            y = (canvas_h - new_h) // 2
            self.editor_zoom_offset = (0, 0)
        else:
            base_x = (canvas_w - int(img_w * base_scale)) // 2
            base_y = (canvas_h - int(img_h * base_scale)) // 2
            x = int(base_x + self.editor_zoom_offset[0])
            y = int(base_y + self.editor_zoom_offset[1])
        
        # Создаём превью
        resample = Image.Resampling.BILINEAR if self.editor_zoom_level != 1.0 else Image.Resampling.LANCZOS
        preview = img.resize((new_w, new_h), resample)
        self.editor_photo = ImageTk.PhotoImage(preview)
        self.editor_canvas.create_image(x, y, anchor="nw", image=self.editor_photo, tags="image")
        
        # Рамка вокруг изображения (двойная для контраста)
        # Внешняя тёмная рамка
        self.editor_canvas.create_rectangle(x-3, y-3, x+new_w+3, y+new_h+3, 
                                           outline="#000000", width=2, tags="border_outer")
        # Внутренняя яркая рамка
        self.editor_canvas.create_rectangle(x-1, y-1, x+new_w+1, y+new_h+1, 
                                           outline="#00ff00", width=2, tags="border_inner")
        
        # Угловые маркеры (как в Lightroom)
        corner_len = min(30, new_w // 10, new_h // 10)
        corner_color = "#ffffff"
        # Верхний левый
        self.editor_canvas.create_line(x, y, x + corner_len, y, fill=corner_color, width=2, tags="corner")
        self.editor_canvas.create_line(x, y, x, y + corner_len, fill=corner_color, width=2, tags="corner")
        # Верхний правый
        self.editor_canvas.create_line(x + new_w, y, x + new_w - corner_len, y, fill=corner_color, width=2, tags="corner")
        self.editor_canvas.create_line(x + new_w, y, x + new_w, y + corner_len, fill=corner_color, width=2, tags="corner")
        # Нижний левый
        self.editor_canvas.create_line(x, y + new_h, x + corner_len, y + new_h, fill=corner_color, width=2, tags="corner")
        self.editor_canvas.create_line(x, y + new_h, x, y + new_h - corner_len, fill=corner_color, width=2, tags="corner")
        # Нижний правый
        self.editor_canvas.create_line(x + new_w, y + new_h, x + new_w - corner_len, y + new_h, fill=corner_color, width=2, tags="corner")
        self.editor_canvas.create_line(x + new_w, y + new_h, x + new_w, y + new_h - corner_len, fill=corner_color, width=2, tags="corner")
        
        # Сохраняем смещение изображения
        self.editor_img_offset = (x, y)
        self.editor_img_size = (new_w, new_h)
        
        # Показываем уровень zoom и номер фото
        info_parts = []
        if self.editor_zoom_level != 1.0:
            info_parts.append(f"{int(self.editor_zoom_level * 100)}%")
        if self.editor_library:
            info_parts.append(f"{self.editor_current_index + 1}/{len(self.editor_library)}")
        if info_parts:
            self.editor_canvas.create_text(canvas_w - 10, 10, text=" | ".join(info_parts), anchor="ne",
                                          font=(FONT_FAMILY, 11, "bold"), fill="#ffffff", tags="info_label")
            self.editor_canvas.create_text(canvas_w - 11, 11, text=" | ".join(info_parts), anchor="ne",
                                          font=(FONT_FAMILY, 11, "bold"), fill="#000000", tags="info_shadow")
        
        # Рисуем сетку (правило третей + центральные линии)
        if self.editor_show_grid:
            # Цвет сетки
            grid_color = "#ffffff"
            grid_color_light = "#666666"
            
            # Границы изображения
            left, top = x, y
            right, bottom = x + new_w, y + new_h
            
            # Вертикальные линии (правило третей)
            for i in range(1, 3):
                lx = left + (new_w * i // 3)
                self.editor_canvas.create_line(lx, top, lx, bottom, fill=grid_color_light, width=1, tags="grid")
            
            # Горизонтальные линии (правило третей)
            for i in range(1, 3):
                ly = top + (new_h * i // 3)
                self.editor_canvas.create_line(left, ly, right, ly, fill=grid_color_light, width=1, tags="grid")
            
            # Центральные линии
            cx = left + new_w // 2
            cy = top + new_h // 2
            self.editor_canvas.create_line(cx, top, cx, bottom, fill=grid_color, width=1, dash=(4, 4), tags="grid")
            self.editor_canvas.create_line(left, cy, right, cy, fill=grid_color, width=1, dash=(4, 4), tags="grid")
        
        # Рисуем гайды (конвертируем из нормализованных координат)
        if self.editor_show_guides:
            for guide in self.editor_guides:
                nx1, ny1, nx2, ny2 = guide
                # Конвертируем нормализованные координаты в canvas
                cx1, cy1, cx2, cy2 = self._image_to_canvas_coords(nx1, ny1, nx2, ny2)
                self.editor_canvas.create_line(cx1, cy1, cx2, cy2, fill="#00ff00", width=2, tags="guide")
        
        # Рисуем маску текущей (красный оверлей) если видимость включена
        if self.editor_current_mask_index >= 0 and self.editor_current_mask_index < len(self.editor_masks):
            mask = self.editor_masks[self.editor_current_mask_index]
            if mask.get('visible', True):
                self._draw_mask_overlay(x, y, new_w, new_h)
    
    def _draw_mask_overlay(self, img_x, img_y, img_w, img_h):
        """Рисует текущую маску как полупрозрачный красный оверлей"""
        if self.editor_current_mask_index < 0 or self.editor_current_mask_index >= len(self.editor_masks):
            return
        
        mask_data = self.editor_masks[self.editor_current_mask_index]
        mask_array = mask_data['array'].copy()
        
        # Применяем feather к оверлею тоже
        feather = mask_data.get('feather', 0)
        if feather > 0:
            try:
                import cv2
                kernel_size = feather * 2 + 1
                if kernel_size % 2 == 0:
                    kernel_size += 1
                mask_array = cv2.GaussianBlur(mask_array, (kernel_size, kernel_size), 0)
            except:
                pass
        
        try:
            import cv2
            mask_resized = cv2.resize(mask_array, (img_w, img_h), interpolation=cv2.INTER_LINEAR)
            
            # Создаём красный оверлей
            overlay = np.zeros((img_h, img_w, 4), dtype=np.uint8)
            overlay[:,:,0] = 255  # Red
            overlay[:,:,3] = (mask_resized * 80).astype(np.uint8)  # Alpha (менее яркий)
            
            overlay_img = Image.fromarray(overlay, mode='RGBA')
            self._mask_overlay_photo = ImageTk.PhotoImage(overlay_img)
            self.editor_canvas.create_image(img_x, img_y, anchor="nw", 
                                           image=self._mask_overlay_photo, tags="mask_overlay")
        except Exception as e:
            logger.error(f"Mask overlay error: {e}")
    
    def _apply_adjustments_no_history(self):
        """Применяет настройки без сохранения в историю (для undo/redo)"""
        self._do_apply_adjustments()
    
    def _apply_adjustments_debounced(self):
        """Применяет настройки при движении слайдера (без истории для скорости)"""
        self._do_apply_adjustments()
    
    def editor_apply_adjustments_fast(self):
        """Быстрое применение настроек через NumPy (для preview)"""
        if self.editor_original_array is None:
            return
        
        # Сохраняем в историю только при явном вызове (не при debounce)
        self._save_to_history()
        self._do_apply_adjustments()
    
    def _build_rotation_homography(self, yaw_deg, pitch_deg, roll_deg, w, h):
        """
        Строит гомографию в стиле GIMP EZ-Perspective.
        
        GIMP применяет вращения ПОСЛЕДОВАТЕЛЬНО с коррекцией после каждого:
        1. Pitch (up/down) + коррекция масштаба
        2. Yaw (left/right) + коррекция масштаба  
        3. Roll (rotation) - без коррекции
        """
        # Фокусное расстояние (как в GIMP)
        image_diagonal = np.sqrt(w*w + h*h)
        diagonal_35mm = np.sqrt(36*36 + 24*24)
        focal_length_mm = 50
        z_fix = image_diagonal * focal_length_mm / diagonal_35mm
        
        cx, cy = w / 2.0, h / 2.0
        
        def proj_point(ud, lr, rot, x_in, y_in):
            """Трансформация одной точки через 3D вращение"""
            x, y, z = x_in, y_in, z_fix
            
            # Вращение X (pitch)
            x, y, z = (x, 
                      np.cos(ud)*y - np.sin(ud)*z,
                      np.sin(ud)*y + np.cos(ud)*z)
            # Вращение Y (yaw)
            x, y, z = (np.cos(lr)*x - np.sin(lr)*z,
                      y,
                      np.sin(lr)*x + np.cos(lr)*z)
            # Вращение Z (roll)
            x, y, z = (np.cos(rot)*x - np.sin(rot)*y,
                      np.sin(rot)*x + np.cos(rot)*y,
                      z)
            
            if abs(z) < 1e-10:
                z = 1e-10
            scale = z_fix / z
            return x * scale, y * scale
        
        # Начальные углы (относительно центра)
        frame = [
            (-cx, -cy),      # UL
            (w - cx, -cy),   # UR
            (-cx, h - cy),   # LL
            (w - cx, h - cy) # LR
        ]
        
        ud = np.radians(pitch_deg)
        lr = np.radians(yaw_deg)
        rot = np.radians(roll_deg)
        
        # === ШАГ 1: Pitch (up/down) с коррекцией ===
        if abs(pitch_deg) > 0.01:
            # Трансформируем углы только по pitch
            frame_ud = []
            for x, y in frame:
                tx, ty = proj_point(ud, 0, 0, x, y)
                frame_ud.append((tx, ty))
            
            # Коррекция: вычисляем сдвиг и масштаб по центральной горизонтальной линии
            scx, shift_y = proj_point(ud, 0, 0, 100, 0)
            
            # Убираем вертикальный сдвиг
            frame_ud = [(x, y - shift_y) for x, y in frame_ud]
            
            # Масштабируем чтобы сохранить размер
            scale = 100 / scx if abs(scx) > 1e-6 else 1.0
            frame = [(x * scale, y * scale) for x, y in frame_ud]
        
        # === ШАГ 2: Yaw (left/right) с коррекцией ===
        if abs(yaw_deg) > 0.01:
            # Трансформируем углы только по yaw
            frame_lr = []
            for x, y in frame:
                tx, ty = proj_point(0, lr, 0, x, y)
                frame_lr.append((tx, ty))
            
            # Коррекция: вычисляем сдвиг и масштаб по центральной вертикальной линии
            shift_x, scy = proj_point(0, lr, 0, 0, 100)
            
            # Убираем горизонтальный сдвиг
            frame_lr = [(x - shift_x, y) for x, y in frame_lr]
            
            # Масштабируем
            scale = 100 / scy if abs(scy) > 1e-6 else 1.0
            frame = [(x * scale, y * scale) for x, y in frame_lr]
        
        # === ШАГ 3: Roll (rotation) - без коррекции ===
        if abs(roll_deg) > 0.01:
            frame_rot = []
            for x, y in frame:
                tx, ty = proj_point(0, 0, rot, x, y)
                frame_rot.append((tx, ty))
            frame = frame_rot
        
        # Переводим обратно в абсолютные координаты
        corners_dst = [(x + cx, y + cy) for x, y in frame]
        
        # Матрица гомографии
        src_pts = np.array([[0, 0], [w, 0], [0, h], [w, h]], dtype=np.float32)
        dst_pts = np.array(corners_dst, dtype=np.float32)
        
        H = cv2.getPerspectiveTransform(src_pts, dst_pts)
        return H.astype(np.float32)
    
    def _normalize_homography(self, H, w, h):
        """
        Нормализует гомографию, фиксируя центр изображения (Center Preservation).
        Это предотвращает 'улет' изображения при поворотах.
        """
        # Центр изображения
        cx, cy = w / 2.0, h / 2.0
        center_pt = np.array([cx, cy, 1.0])
        
        # Где оказывается центр после трансформации
        transformed_center = H @ center_pt
        transformed_center /= transformed_center[2]
        
        # Вычисляем сдвиг, чтобы вернуть центр на место
        tx = cx - transformed_center[0]
        ty = cy - transformed_center[1]
        
        # Матрица сдвига
        T = np.array([
            [1, 0, tx],
            [0, 1, ty],
            [0, 0, 1]
        ], dtype=np.float32)
        
        return T @ H

    def _solve_perspective_params(self, guides, w, h):
        """
        Использует SciPy для нахождения параметров yaw, pitch, roll, 
        которые делают линии в guides вертикальными/горизонтальными.
        """
        if not SCIPY_AVAILABLE:
            logger.warning("SciPy not available, skipping solver")
            return 0, 0, 0, 0
            
        def objective(params):
            yaw_deg, pitch_deg, roll_deg = params
            
            # Строим H для текущих параметров
            # Для скорости строим упрощенно, или вызываем тот же билдер
            # Но здесь нам нужна скорость, поэтому инлайним основные моменты или используем упрощенную модель
            # Для точности лучше использовать полный build_homography
            H = self._build_rotation_homography(yaw_deg, pitch_deg, roll_deg, w, h)
            
            total_error = 0.0
            
            for g in guides:
                # g: {nx1, ny1, nx2, ny2, type='v'/'h', weight}
                # Переводим в пиксели
                p1 = np.array([g['nx1'] * w, g['ny1'] * h, 1.0])
                p2 = np.array([g['nx2'] * w, g['ny2'] * h, 1.0])
                
                # Трансформируем точки
                q1 = H @ p1
                q1 /= q1[2]
                q2 = H @ p2
                q2 /= q2[2]
                
                # Считаем угол
                dx = q2[0] - q1[0]
                dy = q2[1] - q1[1]
                angle_deg = np.degrees(np.arctan2(dy, dx))
                
                if g['type'] == 'v':
                    # Цель: 90 или -90
                    # Ошибка: отклонение от вертикали
                    dev = abs(angle_deg) - 90.0
                    err = dev * dev
                else:
                    # Цель: 0 или 180
                    dev = abs(angle_deg)
                    if dev > 90:
                        dev = abs(180 - dev)
                    err = dev * dev
                
                total_error += err * g['weight']
            
            return total_error

        # Начальное приближение [yaw, pitch, roll]
        x0 = [0.0, 0.0, 0.0]
        
        # Ограничения (градусы) - UNLIMITED (физические пределы)
        bounds = [(-85, 85), (-85, 85), (-90, 90)]
        
        try:
            res = minimize(objective, x0, method='L-BFGS-B', bounds=bounds, tol=1e-5)
            return res.x[0], res.x[1], res.x[2], res.fun
        except Exception as e:
            logger.error(f"Solver failed: {e}")
            return 0, 0, 0, 0

    def _get_current_homography(self, w, h):
        """Возвращает текущую матрицу гомографии на основе слайдеров"""
        yaw_deg = float(self.editor_horizontal.get()) * 0.3
        pitch_deg = float(self.editor_vertical.get()) * 0.3
        roll_deg = float(self.editor_rotation.get())
        
        # Основная гомография
        H = self._build_rotation_homography(yaw_deg, pitch_deg, roll_deg, w, h)
        
        # Нормализация
        H = self._normalize_homography(H, w, h)
        
        # Aspect, Scale, Shift... (если нужно учитывать их влияние на координаты мыши)
        # Пока учитываем только перспективу/поворот, так как это основные искажения
        # Можно добавить Aspect/Scale если гайды рисуются поверх них
        # В _do_apply_adjustments порядок: H -> Aspect -> Scale -> Shift
        # Воспроизведем полный пайплайн для точности
        
        aspect = float(self.editor_aspect.get())
        if abs(aspect) > 0.5:
            cx, cy = w / 2, h / 2
            a = 1.0 + aspect / 100.0 * 0.3
            A = np.array([[a, 0, cx - cx*a], [0, 1/a, cy - cy/a], [0, 0, 1]], dtype=np.float32)
            H = A @ H
            
        scale = float(self.editor_scale.get())
        if abs(scale - 100) > 0.5:
            cx, cy = w / 2, h / 2
            s = scale / 100.0
            S = np.array([[s, 0, cx - cx*s], [0, s, cy - cy*s], [0, 0, 1]], dtype=np.float32)
            H = S @ H
            
        shift_x = float(self.editor_shift_x.get())
        shift_y = float(self.editor_shift_y.get())
        if abs(shift_x) > 0.5 or abs(shift_y) > 0.5:
            T = np.array([[1, 0, shift_x], [0, 1, shift_y], [0, 0, 1]], dtype=np.float32)
            H = T @ H
            
        return H

    def _apply_guides_realtime(self):
        """
        Guided Upright - коррекция перспективы по нарисованным гайдам.
        
        Алгоритм (как в Lightroom/Capture One):
        1. Пользователь рисует линии вдоль объектов, которые ДОЛЖНЫ быть вертикальными/горизонтальными
        2. Solver находит yaw/pitch/roll, которые делают эти линии строго вертикальными/горизонтальными
        3. Без искусственных лимитов - приоритет на геометрическую точность
        4. Auto Scale убирает черные края
        """
        if len(self.editor_guides) < 1:
            return

        w = self.editor_original_image.width if self.editor_original_image else 800
        h = self.editor_original_image.height if self.editor_original_image else 600
        
        # Подготовка данных для Solver'а
        # Гайды хранятся в нормализованных координатах (0-1) относительно preview
        solver_guides = []
        
        for nx1, ny1, nx2, ny2 in self.editor_guides:
            # Длина линии для веса
            length = np.sqrt((nx2-nx1)**2 + (ny2-ny1)**2) * max(w, h)
            
            # Угол линии для классификации
            angle = np.arctan2(ny2 - ny1, nx2 - nx1) * 180 / np.pi
            abs_angle = abs(angle)
            
            # Классификация: вертикальная или горизонтальная
            g_type = None
            if 45 < abs_angle < 135:
                g_type = 'v'  # Вертикальная (должна стать строго вертикальной)
            elif abs_angle <= 45 or abs_angle >= 135:
                g_type = 'h'  # Горизонтальная (должна стать строго горизонтальной)
            
            if g_type:
                solver_guides.append({
                    'nx1': nx1, 'ny1': ny1,
                    'nx2': nx2, 'ny2': ny2,
                    'type': g_type,
                    'weight': length
                })
                logger.debug(f"Guide: type={g_type}, angle={angle:.1f}°, length={length:.0f}")
        
        if not solver_guides:
            logger.info("No valid guides for correction")
            return

        logger.info(f"Guided Upright: {len(solver_guides)} guides")
        
        # Логируем каждый гайд для отладки
        for i, g in enumerate(solver_guides):
            angle = np.degrees(np.arctan2(g['ny2'] - g['ny1'], g['nx2'] - g['nx1']))
            logger.info(f"  Guide {i+1}: type={g['type']}, angle={angle:.1f}°, weight={g['weight']:.0f}")

        # Запускаем Solver
        if SCIPY_AVAILABLE:
            yaw, pitch, roll, loss = self._solve_perspective_params(solver_guides, w, h)
            logger.info(f"Solver RAW result: yaw={yaw:.2f}°, pitch={pitch:.2f}°, roll={roll:.2f}°, loss={loss:.4f}")
            
            # Применяем коррекцию напрямую (solver уже находит нужные углы для исправления)
            # НЕ инвертируем - solver минимизирует ошибку, находя углы которые делают линии прямыми
            
            # Защита от экстремальных значений
            MAX_ANGLE = 60
            yaw = np.clip(yaw, -MAX_ANGLE, MAX_ANGLE)
            pitch = np.clip(pitch, -MAX_ANGLE, MAX_ANGLE)
            roll = np.clip(roll, -90, 90)
            
            logger.info(f"Applying: yaw={yaw:.4f}°, pitch={pitch:.4f}°, roll={roll:.4f}°")
            
            # Применяем ВСЕГДА, даже маленькие значения (убрали порог)
            # pitch -> vertical slider (coeff 0.3)
            v_val = np.clip(pitch / 0.3, -300, 300)
            self.editor_vertical.set(v_val)
            logger.info(f"  Set vertical slider: {v_val:.2f}")
            
            # yaw -> horizontal slider (coeff 0.3)
            h_val = np.clip(yaw / 0.3, -300, 300)
            self.editor_horizontal.set(h_val)
            logger.info(f"  Set horizontal slider: {h_val:.2f}")
            
            # roll -> rotation slider
            r_val = np.clip(roll, -90, 90)
            self.editor_rotation.set(r_val)
            logger.info(f"  Set rotation slider: {r_val:.2f}")
            
            # --- AUTO SCALE (убираем черные края) ---
            H_scale = self._build_rotation_homography(yaw, pitch, roll, w, h)
            H_scale = self._normalize_homography(H_scale, w, h)
            
            zoom_needed = self._calculate_auto_scale(H_scale, w, h)
            
            if zoom_needed > 1.01:
                scale_slider = (zoom_needed - 1.0) * 50.0
                scale_slider = np.clip(scale_slider, 0, 200)
                self.editor_scale.set(scale_slider)
            else:
                self.editor_scale.set(0)
            
            self.editor_apply_adjustments_fast()
            logger.info(f"Applied: V={v_val:.1f}, H={h_val:.1f}, R={r_val:.1f}°, Scale={self.editor_scale.get():.0f}")
        else:
            logger.warning("SciPy not available - cannot optimize guides")
    
    def _do_apply_adjustments(self):
        """Внутренняя функция применения настроек (оптимизированная)"""
        if self.editor_original_array is None:
            return
        
        # Получаем все значения слайдеров
        exposure = float(self.editor_exposure.get())
        contrast = float(self.editor_contrast.get())
        highlights = float(self.editor_highlights.get())
        shadows = float(self.editor_shadows.get())
        brightness = float(self.editor_brightness.get())
        saturation = float(self.editor_saturation.get())
        temp = float(self.editor_temperature.get())
        tint = float(self.editor_tint.get())
        rotation = float(self.editor_rotation.get())
        vertical = float(self.editor_vertical.get())
        horizontal = float(self.editor_horizontal.get())
        aspect = float(self.editor_aspect.get())
        scale = float(self.editor_scale.get())
        
        # Новые параметры Darktable-style
        distortion = float(self.editor_distortion.get())
        vignette = float(self.editor_vignette.get())
        chromatic = float(self.editor_chromatic.get())
        sharpness = float(self.editor_sharpness.get())
        denoise = float(self.editor_denoise.get())
        clarity = float(self.editor_clarity.get())
        
        # Тоновая кривая
        curve_blacks = float(self.editor_curve_blacks.get())
        curve_shadows = float(self.editor_curve_shadows.get())
        curve_midtones = float(self.editor_curve_midtones.get())
        curve_highlights = float(self.editor_curve_highlights.get())
        curve_whites = float(self.editor_curve_whites.get())
        
        # Проверяем нужны ли цветовые коррекции
        need_color = (abs(exposure) > 0.01 or abs(brightness - 1.0) > 0.01 or 
                     abs(contrast - 1.0) > 0.01 or abs(saturation - 1.0) > 0.01 or
                     abs(temp) > 1 or abs(tint) > 1 or abs(highlights) > 1 or abs(shadows) > 1)
        
        # Проверяем нужны ли новые эффекты
        need_lens = abs(distortion) > 1 or abs(vignette) > 1 or abs(chromatic) > 1
        need_detail = sharpness > 1 or denoise > 1 or abs(clarity) > 1
        need_curve = (abs(curve_blacks) > 1 or abs(curve_shadows) > 1 or 
                     abs(curve_midtones) > 1 or abs(curve_highlights) > 1 or abs(curve_whites) > 1)
        
        # Проверяем нужны ли геометрические трансформации
        shift_x = float(self.editor_shift_x.get())
        shift_y = float(self.editor_shift_y.get())
        need_geom = (abs(rotation) > 0.1 or abs(vertical) > 0.5 or 
                    abs(horizontal) > 0.5 or abs(aspect) > 0.5 or scale > 0.5 or
                    abs(shift_x) > 0.5 or abs(shift_y) > 0.5 or abs(distortion) > 1)
        
        if not need_color and not need_geom:
            # Ничего не изменилось - показываем оригинал
            self.editor_current_image = Image.fromarray(self.editor_original_array.astype(np.uint8))
            self.editor_display_image()
            return
        
        # Работаем с numpy массивом
        arr = self.editor_original_array.copy()
        
        # === ЦВЕТОВЫЕ КОРРЕКЦИИ (объединённые для скорости) ===
        if need_color:
            # Объединяем экспозицию и яркость в один множитель
            color_mult = 1.0
            if abs(exposure) > 0.01:
                color_mult *= (2 ** exposure)
            if abs(brightness - 1.0) > 0.01:
                color_mult *= brightness
            
            if color_mult != 1.0:
                arr = arr * color_mult
            
            # Контраст
            if abs(contrast - 1.0) > 0.01:
                arr = (arr - 128) * contrast + 128
            
            # Насыщенность
            if abs(saturation - 1.0) > 0.01:
                lum = 0.299 * arr[:,:,0] + 0.587 * arr[:,:,1] + 0.114 * arr[:,:,2]
                arr = lum[:,:,np.newaxis] + (arr - lum[:,:,np.newaxis]) * saturation
            
            # Хайлайты (света)
            if abs(highlights) > 1:
                lum = 0.299 * arr[:,:,0] + 0.587 * arr[:,:,1] + 0.114 * arr[:,:,2]
                highlight_mask = np.clip((lum - 150) / 80, 0, 1)[:,:,np.newaxis]
                factor = 1 + highlights / 100
                arr = arr * (1 - highlight_mask) + arr * factor * highlight_mask
            
            # Тени
            if abs(shadows) > 1:
                lum = 0.299 * arr[:,:,0] + 0.587 * arr[:,:,1] + 0.114 * arr[:,:,2]
                shadow_mask = np.clip((80 - lum) / 60, 0, 1)[:,:,np.newaxis]
                factor = 1 + shadows / 100
                arr = arr * (1 - shadow_mask) + arr * factor * shadow_mask
            
            # Температура и тинт (объединённые)
            if abs(temp) > 1 or abs(tint) > 1:
                if abs(temp) > 1:
                    arr[:,:,0] += temp * 0.6
                    arr[:,:,2] -= temp * 0.6
                if abs(tint) > 1:
                    arr[:,:,1] -= tint * 0.5
                    arr[:,:,0] += tint * 0.2
                    arr[:,:,2] += tint * 0.2
            
            arr = np.clip(arr, 0, 255)
        
        # === ТОНОВАЯ КРИВАЯ (Darktable-style) ===
        if need_curve:
            # Создаём LUT для кривой
            lut = np.arange(256, dtype=np.float32)
            
            # Применяем точки кривой
            # Чёрные (0-50)
            if abs(curve_blacks) > 1:
                mask = lut < 50
                lut[mask] = lut[mask] + curve_blacks * 0.5
            
            # Тени (50-100)
            if abs(curve_shadows) > 1:
                mask = (lut >= 30) & (lut < 100)
                lut[mask] = lut[mask] + curve_shadows * 0.4
            
            # Средние тона (100-180)
            if abs(curve_midtones) > 1:
                mask = (lut >= 80) & (lut < 180)
                lut[mask] = lut[mask] + curve_midtones * 0.5
            
            # Света (180-220)
            if abs(curve_highlights) > 1:
                mask = (lut >= 150) & (lut < 230)
                lut[mask] = lut[mask] + curve_highlights * 0.4
            
            # Белые (220-255)
            if abs(curve_whites) > 1:
                mask = lut >= 200
                lut[mask] = lut[mask] + curve_whites * 0.5
            
            lut = np.clip(lut, 0, 255).astype(np.uint8)
            arr = lut[arr.astype(np.uint8)]
        
        # === ВИНЬЕТКА ===
        if abs(vignette) > 1:
            h, w = arr.shape[:2]
            Y, X = np.ogrid[:h, :w]
            cx, cy = w / 2, h / 2
            dist = np.sqrt((X - cx)**2 + (Y - cy)**2)
            max_dist = np.sqrt(cx**2 + cy**2)
            vignette_mask = dist / max_dist
            
            if vignette > 0:
                # Затемнение по краям
                factor = 1 - (vignette_mask ** 2) * (vignette / 100)
            else:
                # Осветление по краям
                factor = 1 + (vignette_mask ** 2) * (abs(vignette) / 100)
            
            arr = arr * factor[:, :, np.newaxis]
            arr = np.clip(arr, 0, 255)
        
        img = Image.fromarray(arr.astype(np.uint8))
        
        # === РЕЗКОСТЬ И ШУМОПОДАВЛЕНИЕ (через OpenCV) ===
        if need_detail:
            arr = np.array(img)
            
            # Шумоподавление (Bilateral Filter)
            if denoise > 1:
                d = int(denoise / 10) + 3
                sigma = denoise / 2
                arr = cv2.bilateralFilter(arr, d, sigma, sigma)
            
            # Резкость (Unsharp Mask)
            if sharpness > 1:
                blur = cv2.GaussianBlur(arr, (0, 0), 3)
                amount = sharpness / 100
                arr = cv2.addWeighted(arr, 1 + amount, blur, -amount, 0)
            
            # Clarity (локальный контраст)
            if abs(clarity) > 1:
                blur = cv2.GaussianBlur(arr, (0, 0), 50)
                amount = clarity / 200
                arr = cv2.addWeighted(arr, 1 + amount, blur, -amount, 0)
            
            arr = np.clip(arr, 0, 255)
            img = Image.fromarray(arr.astype(np.uint8))
        
        # === ГЕОМЕТРИЧЕСКИЕ ТРАНСФОРМАЦИИ (только если нужны) ===
        if not need_geom:
            self.editor_current_image = img
            self.editor_display_image()
            return
        
        try:
            arr = np.array(img)
            h, w = arr.shape[:2]
            
            # === ДИСТОРСИЯ ОБЪЕКТИВА (Darktable-style) ===
            if abs(distortion) > 1:
                # Barrel/Pincushion distortion через OpenCV
                cx, cy = w / 2, h / 2
                fx = fy = max(w, h)
                
                # Матрица камеры
                K = np.array([[fx, 0, cx],
                              [0, fy, cy],
                              [0, 0, 1]], dtype=np.float32)
                
                # Коэффициенты дисторсии (k1 - радиальная)
                k1 = distortion / 5000  # Масштабируем для плавности
                dist_coeffs = np.array([k1, 0, 0, 0, 0], dtype=np.float32)
                
                # Применяем undistort
                arr = cv2.undistort(arr, K, dist_coeffs)
            
            # === ПЕРСПЕКТИВА ===
            # Используем алгоритм Darktable ashift если доступен
            if DARKTABLE_ASHIFT_AVAILABLE and hasattr(self, 'perspective_algo') and self.perspective_algo.get() == "Darktable (ashift)":
                # Точный алгоритм Darktable
                dt = DarktableAshift(w, h)
                H = dt.get_homography(rotation=rotation, vertical=vertical, horizontal=horizontal,
                                     shear=0, orthocorr=0, aspect=1.0, forward=False)
            else:
                # Стандартный алгоритм через yaw/pitch/roll
                pitch_deg = vertical * 0.3   # верх/низ (keystone по вертикали)
                yaw_deg = horizontal * 0.3   # лево/право (keystone по горизонтали)
                roll_deg = rotation          # Z-ось (поворот)
                
                H = self._build_rotation_homography(yaw_deg, pitch_deg, roll_deg, w, h)
                
                # Нормализация (Center Preservation) - чтобы не улетало
                H = self._normalize_homography(H, w, h)
            
            # Aspect ratio (растяжение по горизонтали/вертикали)
            if abs(aspect) > 0.5:
                cx, cy = w / 2, h / 2
                a = 1.0 + aspect / 100.0 * 0.3
                A = np.array([
                    [a, 0, cx - cx*a],
                    [0, 1/a, cy - cy/a],
                    [0, 0, 1]
                ], dtype=np.float32)
                H = A @ H
            
            # Scale (масштаб / зум)
            # Слайдер 0..100 мапим в Zoom 1.0..3.0
            scale_val = float(self.editor_scale.get())
            if scale_val > 0.01:
                cx, cy = w / 2, h / 2
                zoom = 1.0 + (scale_val / 50.0)  # 0->1.0, 50->2.0, 100->3.0
                s = 1.0 / zoom  # H maps Dst->Src, so s<1 means Zoom In
                
                S = np.array([
                    [s, 0, cx - cx*s],
                    [0, s, cy - cy*s],
                    [0, 0, 1]
                ], dtype=np.float32)
                H = S @ H
            
            # Сдвиг X/Y (translate) — применяется после основной гомографии
            # Но так как мы используем WARP_INVERSE_MAP, матрица применяется как dst -> src?
            # Нет, WARP_INVERSE_MAP означает, что мы подаем matrix src -> dst (forward).
            # Значит, H - это трансформация, которую мы применяем к картинке.
            # Если мы хотим сдвинуть картинку ВПРАВО, то пиксель dst(x,y) берется из src(x-dx, y-dy).
            # Матрица сдвига T(dx, dy) делает x' = x + dx.
            # С WARP_INVERSE_MAP, это значит dst = T * src.
            
            shift_x = float(self.editor_shift_x.get())
            shift_y = float(self.editor_shift_y.get())
            if abs(shift_x) > 0.5 or abs(shift_y) > 0.5:
                T = np.array([
                    [1, 0, shift_x],
                    [0, 1, shift_y],
                    [0, 0, 1]
                ], dtype=np.float32)
                H = T @ H
            
            # Применяем трансформацию (пустые области = шахматный фон)
            if not np.allclose(H, np.eye(3)):
                checker = np.zeros((h, w, 3), dtype=np.uint8)
                cell = 16
                for row in range(0, h, cell):
                    for col in range(0, w, cell):
                        color = (80, 80, 90) if ((row // cell + col // cell) % 2 == 0) else (50, 50, 60)
                        checker[row:row+cell, col:col+cell] = color
                
                # ВАЖНО: WARP_INVERSE_MAP, так как H у нас - это матрица прямой трансформации (как исправить картинку)
                result = cv2.warpPerspective(arr, H, (w, h),
                                             flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                                             borderMode=cv2.BORDER_CONSTANT,
                                             borderValue=(0, 0, 0))
                
                mask = cv2.warpPerspective(np.ones((h, w), dtype=np.uint8) * 255, H, (w, h),
                                          flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                                          borderMode=cv2.BORDER_CONSTANT,
                                          borderValue=0)
                mask_3d = mask[:, :, np.newaxis] / 255.0
                arr = (result * mask_3d + checker * (1 - mask_3d)).astype(np.uint8)
            
            img = Image.fromarray(arr)
        
        except ImportError:
            # Fallback без OpenCV — только поворот
            if abs(rotation) > 0.1:
                img = img.rotate(-rotation, expand=False, resample=Image.Resampling.BILINEAR, fillcolor=(30, 30, 40))
        
        self.editor_current_image = img
        self.editor_display_image()
    
    def editor_apply_adjustments(self):
        """Полное применение настроек (для сохранения)"""
        self.editor_apply_adjustments_fast()
    
    def _apply_color_temperature(self, img, temp, tint):
        """Применяет цветовую температуру и тинт"""
        arr = np.array(img, dtype=np.float32)
        
        # Температура: сдвигает R и B каналы
        if temp > 0:  # Теплее
            arr[:, :, 0] = np.clip(arr[:, :, 0] + temp * 0.5, 0, 255)  # R+
            arr[:, :, 2] = np.clip(arr[:, :, 2] - temp * 0.3, 0, 255)  # B-
        else:  # Холоднее
            arr[:, :, 0] = np.clip(arr[:, :, 0] + temp * 0.3, 0, 255)  # R-
            arr[:, :, 2] = np.clip(arr[:, :, 2] - temp * 0.5, 0, 255)  # B+
        
        # Тинт: сдвигает G и M (пурпурный через R+B)
        if tint > 0:  # Пурпурный
            arr[:, :, 1] = np.clip(arr[:, :, 1] - tint * 0.3, 0, 255)  # G-
        else:  # Зелёный
            arr[:, :, 1] = np.clip(arr[:, :, 1] - tint * 0.3, 0, 255)  # G+
        
        return Image.fromarray(arr.astype(np.uint8))
    
    def _apply_perspective_fast(self, img, vertical, horizontal):
        """Быстрая коррекция перспективы через простой сдвиг"""
        w, h = img.size
        
        # Упрощённая коррекция через affine transform (быстрее чем perspective)
        # Вертикаль: сужаем верх или низ
        # Горизонталь: сужаем лево или право
        
        v = vertical / 45.0 * 0.15  # Нормализуем
        hz = horizontal / 45.0 * 0.15
        
        # Используем простой shear transform для скорости
        try:
            import cv2
            arr = np.array(img)
            
            # Матрица трансформации для вертикали
            if abs(vertical) > 0.5:
                pts1 = np.float32([[0, 0], [w, 0], [0, h], [w, h]])
                pts2 = np.float32([
                    [w * abs(v) if v > 0 else 0, 0],
                    [w - w * abs(v) if v > 0 else w, 0],
                    [0 if v > 0 else w * abs(v), h],
                    [w if v > 0 else w - w * abs(v), h]
                ])
                M = cv2.getPerspectiveTransform(pts1, pts2)
                arr = cv2.warpPerspective(arr, M, (w, h), borderValue=(30, 30, 40))
            
            # Матрица для горизонтали
            if abs(horizontal) > 0.5:
                pts1 = np.float32([[0, 0], [w, 0], [0, h], [w, h]])
                pts2 = np.float32([
                    [0, h * abs(hz) if hz > 0 else 0],
                    [w, 0 if hz > 0 else h * abs(hz)],
                    [0, h - h * abs(hz) if hz < 0 else h],
                    [w, h if hz < 0 else h - h * abs(hz)]
                ])
                M = cv2.getPerspectiveTransform(pts1, pts2)
                arr = cv2.warpPerspective(arr, M, (w, h), borderValue=(30, 30, 40))
            
            return Image.fromarray(arr)
        except ImportError:
            # Fallback без OpenCV
            return img
    
    def _apply_perspective(self, img, vertical, horizontal):
        """Применяет коррекцию перспективы"""
        return self._apply_perspective_fast(img, vertical, horizontal)
    
    def editor_auto_vertical(self):
        """Полная автоматическая коррекция по 3 осям (Lightroom Full Upright) с использованием Solver"""
        if not self.editor_original_image:
            messagebox.showwarning("Внимание", "Сначала загрузите изображение")
            return
        
        try:
            import cv2
            
            # Работаем с preview для скорости
            img_array = np.array(self.editor_preview_image or self.editor_original_image)
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            h, w = gray.shape
            
            # Улучшенная детекция краёв
            gray_filtered = cv2.bilateralFilter(gray, 9, 75, 75)
            edges = cv2.Canny(gray_filtered, 30, 100, apertureSize=3)
            
            # Морфологическое закрытие
            kernel = np.ones((3, 3), np.uint8)
            edges = cv2.dilate(edges, kernel, iterations=1)
            edges = cv2.erode(edges, kernel, iterations=1)
            
            # Детекция линий
            min_line_length = min(h, w) // 10
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=50, 
                                   minLineLength=min_line_length, maxLineGap=20)
            
            if lines is None or len(lines) < 3:
                messagebox.showinfo("Авто", "Недостаточно линий для анализа")
                return
            
            # Собираем данные для Solver'а
            solver_guides = []
            
            for line in lines:
                x1, y1, x2, y2 = line[0]
                length = np.sqrt((x2-x1)**2 + (y2-y1)**2)
                angle = np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi
                
                # Нормализуем координаты
                nx1, ny1 = x1 / w, y1 / h
                nx2, ny2 = x2 / w, y2 / h
                
                # Классификация
                g_type = None
                if 60 < abs(angle) < 120: # Вертикальные
                    g_type = 'v'
                elif abs(angle) < 30 or abs(angle) > 150: # Горизонтальные
                    g_type = 'h'
                    
                if g_type:
                    solver_guides.append({
                        'nx1': nx1, 'ny1': ny1,
                        'nx2': nx2, 'ny2': ny2,
                        'type': g_type,
                        'weight': length
                    })
            
            logger.info(f"Auto-vertical: found {len(solver_guides)} valid lines for optimization")
            
            if not solver_guides:
                 messagebox.showinfo("Авто", "Не найдено подходящих линий")
                 return

            # Запускаем Solver
            if SCIPY_AVAILABLE:
                yaw, pitch, roll, loss = self._solve_perspective_params(solver_guides, w, h)
                logger.info(f"Auto Solver result: yaw={yaw:.2f}, pitch={pitch:.2f}, roll={roll:.2f}, loss={loss:.4f}")
                
                # Ограничиваем экстремальные значения
                MAX_ANGLE = 60
                yaw = np.clip(yaw, -MAX_ANGLE, MAX_ANGLE)
                pitch = np.clip(pitch, -MAX_ANGLE, MAX_ANGLE)
                roll = np.clip(roll, -90, 90)
                
                changes = []
                
                # Применяем ВСЕ значения (убрали пороги для большей свободы)
                # Roll
                self.editor_rotation.set(roll)
                changes.append(f"Поворот: {roll:.2f}°")
                
                # Pitch (Vertical)
                v_val = pitch / 0.3
                self.editor_vertical.set(v_val)
                changes.append(f"Вертикаль: {v_val:.1f}")
                
                # Yaw (Horizontal)
                h_val = yaw / 0.3
                self.editor_horizontal.set(h_val)
                changes.append(f"Горизонталь: {h_val:.1f}")
                
                # --- AUTO SCALE (Убираем черные края) ---
                # Берем значения, которые фактически попали в слайдеры
                applied_roll = self.editor_rotation.get()
                applied_pitch_deg = self.editor_vertical.get() * 0.3
                applied_yaw_deg = self.editor_horizontal.get() * 0.3
                
                # Строим матрицу Dst->Src
                H_scale = self._build_rotation_homography(applied_yaw_deg, applied_pitch_deg, applied_roll, w, h)
                H_scale = self._normalize_homography(H_scale, w, h)
                
                zoom_needed = self._calculate_auto_scale(H_scale, w, h)
                
                if zoom_needed > 1.01:
                    # zoom = 1.0 + val/50.0 => val = (zoom - 1.0) * 50.0
                    scale_slider = (zoom_needed - 1.0) * 50.0
                    scale_slider = np.clip(scale_slider, 0, 200)  # Расширен до 200 для сильных коррекций
                    self.editor_scale.set(scale_slider)
                    changes.append(f"Масштаб: {int(scale_slider)}")
                else:
                    self.editor_scale.set(0)
                
                self.editor_apply_adjustments_fast()
                
                messagebox.showinfo("Авто-коррекция", 
                    f"Использовано линий: {len(solver_guides)}\n\n"
                    f"Применено:\n• " + "\n• ".join(changes))
            else:
                # Fallback (упрощенный, если scipy нет)
                messagebox.showwarning("Внимание", "Библиотека SciPy не найдена. Установите её для точной авто-коррекции.")
            
        except ImportError:
            messagebox.showwarning("OpenCV", "Установите: pip install opencv-python")
        except Exception as e:
            logger.error(f"Auto-vertical error: {e}")
            messagebox.showerror("Ошибка", str(e))

    def editor_auto_lens_correction(self):
        """Автоматическая коррекция объектива через Lensfun (как в Darktable)"""
        if not self.editor_original_image:
            messagebox.showwarning("Внимание", "Сначала загрузите изображение")
            return
        
        if not LENSFUN_AVAILABLE:
            messagebox.showwarning("Lensfun", "Библиотека lensfunpy не установлена.\nУстановите: pip install lensfunpy")
            return
        
        try:
            # Пытаемся получить EXIF данные
            from PIL.ExifTags import TAGS
            img = Image.open(self.editor_image_path)
            exif = img._getexif()
            
            camera_make = None
            camera_model = None
            lens_model = None
            focal_length = None
            aperture = None
            
            if exif:
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    if tag == 'Make':
                        camera_make = value
                    elif tag == 'Model':
                        camera_model = value
                    elif tag == 'LensModel':
                        lens_model = value
                    elif tag == 'FocalLength':
                        focal_length = float(value) if isinstance(value, (int, float)) else float(value[0]) / float(value[1])
                    elif tag == 'FNumber':
                        aperture = float(value) if isinstance(value, (int, float)) else float(value[0]) / float(value[1])
            
            if not camera_make or not camera_model:
                messagebox.showinfo("Lensfun", 
                    "Не удалось определить камеру из EXIF.\n\n"
                    "Используйте ручные слайдеры:\n"
                    "• Дисторсия - для бочки/подушки\n"
                    "• Виньетка - для затемнения краёв")
                return
            
            # Ищем камеру и объектив в базе Lensfun
            db = lensfunpy.Database()
            cam = db.find_cameras(camera_make, camera_model)
            
            if not cam:
                messagebox.showinfo("Lensfun", 
                    f"Камера {camera_make} {camera_model} не найдена в базе Lensfun.\n\n"
                    "Используйте ручные слайдеры.")
                return
            
            cam = cam[0]
            
            # Ищем объектив
            lenses = db.find_lenses(cam, lens_model) if lens_model else []
            
            if not lenses:
                messagebox.showinfo("Lensfun", 
                    f"Объектив не найден в базе Lensfun.\n"
                    f"Камера: {cam.maker} {cam.model}\n\n"
                    "Используйте ручные слайдеры.")
                return
            
            lens = lenses[0]
            
            # Применяем коррекцию
            arr = np.array(self.editor_preview_image or self.editor_original_image)
            h, w = arr.shape[:2]
            
            focal = focal_length or 50
            f_number = aperture or 5.6
            
            mod = lensfunpy.Modifier(lens, cam.crop_factor, w, h)
            mod.initialize(focal, f_number, 1.0)
            
            # Получаем карту коррекции дисторсии
            undist_coords = mod.apply_geometry_distortion()
            
            if undist_coords is not None:
                arr_corrected = cv2.remap(arr, undist_coords, None, cv2.INTER_LINEAR)
                
                # Обновляем изображение
                self.editor_original_array = arr_corrected.astype(np.float32)
                self.editor_apply_adjustments_fast()
                
                messagebox.showinfo("Lensfun", 
                    f"Коррекция применена!\n\n"
                    f"Камера: {cam.maker} {cam.model}\n"
                    f"Объектив: {lens.maker} {lens.model}\n"
                    f"Фокусное: {focal}mm, f/{f_number}")
            else:
                messagebox.showinfo("Lensfun", "Коррекция не требуется для этого объектива.")
                
        except Exception as e:
            logger.error(f"Lensfun error: {e}")
            messagebox.showerror("Ошибка Lensfun", 
                f"Ошибка: {str(e)}\n\n"
                "Используйте ручные слайдеры для коррекции.")
    
    def editor_toggle_guides(self):
        """Включает/выключает отображение гайдов"""
        self.editor_show_guides = not self.editor_show_guides
        if self.editor_show_guides:
            self.guides_btn.configure(fg_color=COLORS["success"])
        else:
            self.guides_btn.configure(fg_color=COLORS["secondary"])
        self.editor_display_image()
    
    def editor_clear_guides(self):
        """Очистка всех гайдов и сброс коррекций"""
        self.editor_guides = []
        self.guides_btn.configure(text="📏 Гайды (0/4)")
        # Сбрасываем коррекции перспективы
        self.editor_rotation.set(0)
        self.editor_vertical.set(0)
        self.editor_horizontal.set(0)
        self.editor_apply_adjustments_fast()
        logger.info("Guides cleared")
    
    def editor_apply_from_guides(self):
        """Применяет коррекцию (вызывает тот же метод, что и realtime)"""
        self._apply_guides_realtime()
        messagebox.showinfo("Гайды", "Коррекция обновлена")
    
    def editor_toggle_grid(self):
        """Включает/выключает отображение сетки"""
        self.editor_show_grid = not self.editor_show_grid
        if self.editor_show_grid:
            self.grid_btn.configure(text="🔲 Скрыть сетку", fg_color=COLORS["primary"])
        else:
            self.grid_btn.configure(text="🔲 Показать сетку", fg_color=COLORS["bg_tertiary"])
        self.editor_display_image()
    
    def editor_canvas_motion(self, event):
        """Движение мыши - показываем превью кисти или лупу в режиме гайдов"""
        # Режим рисования маски
        if self.editor_mask_mode == "drawing" and self.editor_current_mask_index >= 0:
            self._draw_brush_preview(event.x, event.y)
            return
        
        # Режим гайдов - показываем лупу при любом движении мыши
        if self.editor_show_guides and self.editor_current_image:
            self.editor_canvas.delete("loupe")
            self._draw_loupe(event.x, event.y)
    
    def editor_canvas_leave(self, event):
        """Курсор покинул canvas - скрываем лупу"""
        self.editor_canvas.delete("loupe")
        self.editor_canvas.delete("brush_preview")
    
    def _draw_brush_preview(self, x, y):
        """Рисует превью кисти (круг) на позиции курсора"""
        self.editor_canvas.delete("brush_preview")
        
        if self.editor_img_size[0] == 0:
            return
        
        brush_size = int(self.mask_brush_size.get())
        feather = int(self.mask_feather.get())
        
        # Внешний круг (размер кисти)
        self.editor_canvas.create_oval(
            x - brush_size, y - brush_size,
            x + brush_size, y + brush_size,
            outline="#ff0000", width=2, tags="brush_preview"
        )
        
        # Внутренний круг (область без feather)
        inner_size = max(5, brush_size - feather // 2)
        self.editor_canvas.create_oval(
            x - inner_size, y - inner_size,
            x + inner_size, y + inner_size,
            outline="#ff6666", width=1, dash=(3, 3), tags="brush_preview"
        )
        
        # Центральная точка
        self.editor_canvas.create_oval(
            x - 2, y - 2, x + 2, y + 2,
            fill="#ff0000", outline="", tags="brush_preview"
        )
    
    def editor_canvas_click(self, event):
        """Обработка клика на canvas"""
        # Режим выбора точки для баланса белого
        if self.editor_wb_picker_mode:
            self.editor_apply_wb_from_point(event.x, event.y)
            return
        
        # Режим рисования маски кистью
        if self.editor_mask_mode == "drawing" and self.editor_current_mask_index >= 0:
            self.editor_mask_drawing = True
            self._draw_mask_brush(event.x, event.y)
            self._apply_masks_preview()
            return
        
        # Режим рисования гайдов
        if self.editor_show_guides:
            # Проверяем клик по существующему гайду для выбора/удаления
            clicked_guide = self._find_guide_at(event.x, event.y)
            if clicked_guide is not None:
                # Удаляем гайд по клику
                self.editor_guides.pop(clicked_guide)
                self.guides_btn.configure(text=f"📏 Гайды ({len(self.editor_guides)}/4)")
                if len(self.editor_guides) >= 2:
                    self._apply_guides_realtime()
                else:
                    # Сбрасываем коррекции если меньше 2 гайдов
                    self.editor_rotation.set(0)
                    self.editor_vertical.set(0)
                    self.editor_horizontal.set(0)
                    self._apply_adjustments_debounced()
                self.editor_display_image()
                return
            
            self.editor_guide_start = (event.x, event.y)
    
    def _find_guide_at(self, x, y, threshold=10):
        """Находит гайд рядом с точкой (x, y)"""
        for i, (x1, y1, x2, y2) in enumerate(self.editor_guides):
            # Расстояние от точки до линии
            line_len = np.sqrt((x2-x1)**2 + (y2-y1)**2)
            if line_len < 1:
                continue
            
            # Проекция точки на линию
            t = max(0, min(1, ((x-x1)*(x2-x1) + (y-y1)*(y2-y1)) / (line_len**2)))
            proj_x = x1 + t * (x2 - x1)
            proj_y = y1 + t * (y2 - y1)
            
            dist = np.sqrt((x - proj_x)**2 + (y - proj_y)**2)
            if dist < threshold:
                return i
        return None
    
    def editor_canvas_drag(self, event):
        """Рисование гайда с лупой 4x или маски кистью"""
        # Режим рисования маски кистью
        if self.editor_mask_mode == "drawing" and self.editor_mask_drawing:
            self._draw_mask_brush(event.x, event.y)
            # Обновляем превью каждые N пикселей для плавности
            if not hasattr(self, '_last_mask_update') or abs(event.x - self._last_mask_update[0]) > 10 or abs(event.y - self._last_mask_update[1]) > 10:
                self._last_mask_update = (event.x, event.y)
                self._apply_masks_preview()
            return
        
        if self.editor_show_guides and self.editor_guide_start:
            self.editor_canvas.delete("temp_guide")
            self.editor_canvas.delete("loupe")
            
            x1, y1 = self.editor_guide_start
            self.editor_canvas.create_line(x1, y1, event.x, event.y, 
                                          fill="#00ff00", width=2, tags="temp_guide", dash=(4, 2))
            
            # Рисуем лупу 4x в углу
            self._draw_loupe(event.x, event.y)
    
    def _draw_loupe(self, cursor_x, cursor_y):
        """Рисует квадратик-лупу 4x с крестиком точно на позиции курсора"""
        if self.editor_current_image is None:
            return
        
        loupe_size = 120  # Размер лупы на экране
        zoom = 4  # Увеличение
        
        # Позиция лупы рядом с курсором
        canvas_w = self.editor_canvas.winfo_width() or 800
        canvas_h = self.editor_canvas.winfo_height() or 500
        
        offset = 25
        loupe_x = cursor_x + offset
        loupe_y = cursor_y + offset
        
        if loupe_x + loupe_size > canvas_w:
            loupe_x = cursor_x - loupe_size - offset
        if loupe_y + loupe_size > canvas_h:
            loupe_y = cursor_y - loupe_size - offset
        
        # Переводим координаты курсора в координаты изображения (с учётом масштаба preview)
        scale_x = self.editor_current_image.size[0] / self.editor_img_size[0] if self.editor_img_size[0] > 0 else 1
        scale_y = self.editor_current_image.size[1] / self.editor_img_size[1] if self.editor_img_size[1] > 0 else 1
        
        img_x = int((cursor_x - self.editor_img_offset[0]) * scale_x)
        img_y = int((cursor_y - self.editor_img_offset[1]) * scale_y)
        
        img = self.editor_current_image
        img_w, img_h = img.size
        
        # Размер области для вырезки (в пикселях изображения)
        source_half = loupe_size // (zoom * 2)
        
        # Границы области для лупы (центрированные на курсоре)
        x1 = img_x - source_half
        y1 = img_y - source_half
        x2 = img_x + source_half
        y2 = img_y + source_half
        
        # Смещение крестика если область выходит за границы
        cross_offset_x = 0
        cross_offset_y = 0
        
        if x1 < 0:
            cross_offset_x = x1 * zoom  # Отрицательное смещение
            x1 = 0
        if y1 < 0:
            cross_offset_y = y1 * zoom
            y1 = 0
        if x2 > img_w:
            x2 = img_w
        if y2 > img_h:
            y2 = img_h
        
        if x2 > x1 and y2 > y1:
            # Вырезаем область
            crop = img.crop((x1, y1, x2, y2))
            
            # Увеличиваем
            crop_w = int((x2 - x1) * zoom)
            crop_h = int((y2 - y1) * zoom)
            crop = crop.resize((crop_w, crop_h), Image.Resampling.NEAREST)
            
            # Создаём фон для лупы (если crop меньше loupe_size)
            loupe_img = Image.new('RGB', (loupe_size, loupe_size), (40, 40, 50))
            
            # Вставляем увеличенную область
            paste_x = max(0, -int(cross_offset_x))
            paste_y = max(0, -int(cross_offset_y))
            loupe_img.paste(crop, (paste_x, paste_y))
            
            self._loupe_photo = ImageTk.PhotoImage(loupe_img)
            self.editor_canvas.create_image(loupe_x, loupe_y, anchor="nw", 
                                           image=self._loupe_photo, tags="loupe")
            
            # Рамка лупы
            self.editor_canvas.create_rectangle(loupe_x-1, loupe_y-1, 
                                               loupe_x+loupe_size+1, loupe_y+loupe_size+1,
                                               outline="#00ff00", width=2, tags="loupe")
            
            # Крестик ТОЧНО в центре (соответствует позиции курсора)
            cx = loupe_x + loupe_size // 2
            cy = loupe_y + loupe_size // 2
            
            # Крестик с контуром для видимости
            self.editor_canvas.create_line(cx-12, cy, cx+12, cy, fill="#000000", width=3, tags="loupe")
            self.editor_canvas.create_line(cx, cy-12, cx, cy+12, fill="#000000", width=3, tags="loupe")
            self.editor_canvas.create_line(cx-12, cy, cx+12, cy, fill="#ff0000", width=1, tags="loupe")
            self.editor_canvas.create_line(cx, cy-12, cx, cy+12, fill="#ff0000", width=1, tags="loupe")
            
            # Точка в центре
            self.editor_canvas.create_oval(cx-2, cy-2, cx+2, cy+2, fill="#ff0000", outline="#000000", tags="loupe")
            
            # Метка "4x"
            self.editor_canvas.create_text(loupe_x + 5, loupe_y + loupe_size - 5, 
                                          text="4x", anchor="sw", fill="#00ff00",
                                          font=(FONT_FAMILY, 10, "bold"), tags="loupe")
    
    def editor_canvas_release(self, event):
        """Завершение рисования гайда или маски"""
        # Завершение рисования маски
        if self.editor_mask_mode == "brush" and self.editor_mask_drawing:
            self.editor_mask_drawing = False
            return
        
        if self.editor_show_guides and self.editor_guide_start:
            x1, y1 = self.editor_guide_start
            x2, y2 = event.x, event.y
            
            # Максимум 4 гайда
            if len(self.editor_guides) >= 4:
                self.editor_guide_start = None
                self.editor_canvas.delete("temp_guide")
                return
            
            # Сохраняем гайд если он достаточно длинный
            length = ((x2-x1)**2 + (y2-y1)**2) ** 0.5
            if length > 20:
                # Конвертируем координаты canvas в нормализованные координаты изображения (0-1)
                img_guide = self._canvas_to_image_coords(x1, y1, x2, y2)
                if img_guide:
                    self.editor_guides.append(img_guide)
                    
                    angle = np.arctan2(y2-y1, x2-x1) * 180 / np.pi
                    logger.info(f"Guide {len(self.editor_guides)}/4 added, angle: {angle:.1f}°, normalized: {img_guide}")
                    
                    # Обновляем текст кнопки
                    self.guides_btn.configure(text=f"📏 Гайды ({len(self.editor_guides)}/4)")
                    
                    # Авто-применение при 2+ гайдах
                    if len(self.editor_guides) >= 2:
                        self._apply_guides_realtime()
            
            self.editor_guide_start = None
            self.editor_canvas.delete("temp_guide")
            self.editor_canvas.delete("loupe")
            self.editor_display_image()
    
    def _canvas_to_image_coords(self, x1, y1, x2, y2):
        """Конвертирует координаты canvas в нормализованные координаты изображения (0-1)"""
        if self.editor_img_size[0] == 0 or self.editor_img_size[1] == 0:
            return None
        
        # Координаты изображения на canvas
        img_x, img_y = self.editor_img_offset
        img_w, img_h = self.editor_img_size
        
        # Нормализуем относительно изображения
        nx1 = (x1 - img_x) / img_w
        ny1 = (y1 - img_y) / img_h
        nx2 = (x2 - img_x) / img_w
        ny2 = (y2 - img_y) / img_h
        
        return (nx1, ny1, nx2, ny2)
    
    def _image_to_canvas_coords(self, nx1, ny1, nx2, ny2):
        """Конвертирует нормализованные координаты изображения в координаты canvas"""
        img_x, img_y = self.editor_img_offset
        img_w, img_h = self.editor_img_size
        
        x1 = img_x + nx1 * img_w
        y1 = img_y + ny1 * img_h
        x2 = img_x + nx2 * img_w
        y2 = img_y + ny2 * img_h
        
        return (x1, y1, x2, y2)
    
    def editor_start_mask(self, mask_type):
        """Начинает режим маски"""
        if not self.editor_original_image:
            messagebox.showwarning("Внимание", "Сначала загрузите изображение")
            return
        
        self.editor_mask_mode = mask_type
        
        if mask_type == "brush":
            # Инициализируем пустую маску
            h, w = self.editor_original_array.shape[:2]
            self.editor_mask_array = np.zeros((h, w), dtype=np.float32)
            self.mask_brush_btn.configure(fg_color=COLORS["success"])
            self.editor_canvas.configure(cursor="circle")
            logger.info("Brush mask mode started")
            
        elif mask_type == "highlights":
            # Автоматическая маска светов (яркость > 180)
            lum = 0.299 * self.editor_original_array[:,:,0] + 0.587 * self.editor_original_array[:,:,1] + 0.114 * self.editor_original_array[:,:,2]
            self.editor_mask_array = np.clip((lum - 150) / 80, 0, 1).astype(np.float32)
            self._show_mask_overlay()
            logger.info("Highlights mask created")
            
        elif mask_type == "shadows":
            # Автоматическая маска теней (яркость < 80)
            lum = 0.299 * self.editor_original_array[:,:,0] + 0.587 * self.editor_original_array[:,:,1] + 0.114 * self.editor_original_array[:,:,2]
            self.editor_mask_array = np.clip((80 - lum) / 60, 0, 1).astype(np.float32)
            self._show_mask_overlay()
            logger.info("Shadows mask created")
    
    def editor_apply_mask(self):
        """Применяет локальные коррекции по маске"""
        if self.editor_mask_array is None or self.editor_original_array is None:
            messagebox.showwarning("Внимание", "Сначала создайте маску")
            return
        
        # Получаем настройки коррекции
        exposure = float(self.mask_exposure.get())
        temperature = float(self.mask_temperature.get())
        saturation = float(self.mask_saturation.get())
        feather = int(self.mask_feather.get())
        
        # Применяем feather (размытие маски)
        mask = self.editor_mask_array.copy()
        if feather > 0:
            try:
                import cv2
                kernel_size = feather * 2 + 1
                mask = cv2.GaussianBlur(mask, (kernel_size, kernel_size), 0)
            except ImportError:
                pass
        
        # Расширяем маску до 3 каналов
        mask_3d = mask[:,:,np.newaxis]
        
        # Применяем коррекции только к замаскированным областям
        arr = self.editor_original_array.copy()
        
        # Экспозиция
        if abs(exposure) > 0.01:
            factor = 2 ** exposure
            corrected = arr * factor
            arr = arr * (1 - mask_3d) + corrected * mask_3d
        
        # Температура
        if abs(temperature) > 1:
            corrected = arr.copy()
            corrected[:,:,0] += temperature * 0.6
            corrected[:,:,2] -= temperature * 0.6
            arr = arr * (1 - mask_3d) + corrected * mask_3d
        
        # Насыщенность
        if abs(saturation - 1.0) > 0.01:
            lum = 0.299 * arr[:,:,0] + 0.587 * arr[:,:,1] + 0.114 * arr[:,:,2]
            lum = lum[:,:,np.newaxis]
            corrected = lum + (arr - lum) * saturation
            arr = arr * (1 - mask_3d) + corrected * mask_3d
        
        arr = np.clip(arr, 0, 255)
        
        # Сохраняем как новый оригинал
        self.editor_original_array = arr.astype(np.float32)
        self.editor_original_image = Image.fromarray(arr.astype(np.uint8))
        
        # Сбрасываем маску
        self.editor_clear_mask()
        self._do_apply_adjustments()
        
        logger.info(f"Mask applied: exp={exposure:.2f}, temp={temperature:.0f}, sat={saturation:.2f}")
    
    def editor_clear_mask(self):
        """Очищает текущую маску"""
        self.editor_mask_mode = None
        self.editor_mask_array = None
        self.editor_mask_drawing = False
        self.mask_brush_btn.configure(fg_color=COLORS["pink"])
        self.editor_canvas.configure(cursor="")
        self.editor_display_image()
    
    def _show_mask_overlay(self):
        """Показывает маску поверх изображения"""
        if self.editor_mask_array is None:
            return
        self.editor_display_image()
    
    def _draw_mask_brush(self, x, y):
        """Рисует кистью на текущей маске"""
        if self.editor_current_mask_index < 0 or self.editor_current_mask_index >= len(self.editor_masks):
            return
        
        mask_data = self.editor_masks[self.editor_current_mask_index]
        mask_array = mask_data['array']
        
        if self.editor_img_size[0] == 0 or self.editor_img_size[1] == 0:
            return
        
        # Переводим координаты canvas в координаты изображения
        h, w = mask_array.shape
        img_x = int((x - self.editor_img_offset[0]) * w / self.editor_img_size[0])
        img_y = int((y - self.editor_img_offset[1]) * h / self.editor_img_size[1])
        
        brush_size = int(self.mask_brush_size.get())
        
        # Масштабируем размер кисти
        scale = w / self.editor_img_size[0] if self.editor_img_size[0] > 0 else 1
        brush_size = max(5, int(brush_size * scale))
        
        # Рисуем круг на маске (оптимизированно - только в области кисти)
        x1 = max(0, img_x - brush_size - 10)
        x2 = min(w, img_x + brush_size + 10)
        y1 = max(0, img_y - brush_size - 10)
        y2 = min(h, img_y + brush_size + 10)
        
        if x2 <= x1 or y2 <= y1:
            return
        
        # Создаём локальную маску кисти
        local_y, local_x = np.ogrid[y1:y2, x1:x2]
        dist = np.sqrt((local_x - img_x)**2 + (local_y - img_y)**2)
        
        # Мягкие края
        feather = max(1, brush_size // 3)
        brush_mask = np.clip(1 - (dist - brush_size + feather) / feather, 0, 1)
        
        # Применяем к маске в зависимости от режима
        if self.mask_brush_mode == "erase":
            # Ластик: уменьшаем маску
            mask_array[y1:y2, x1:x2] = np.maximum(0, mask_array[y1:y2, x1:x2] - brush_mask.astype(np.float32))
        else:
            # Кисть: увеличиваем маску
            mask_array[y1:y2, x1:x2] = np.maximum(mask_array[y1:y2, x1:x2], brush_mask.astype(np.float32))
    
    def _editor_right_click(self, event):
        """ПКМ на редакторе - контекстное меню"""
        if not self.editor_current_image:
            return
        
        menu = tk.Menu(self, tearoff=0)
        
        menu.add_command(label="🎬 Отправить в раскадровку", 
                        command=self._editor_send_to_storyboard)
        menu.add_separator()
        menu.add_command(label="💾 Сохранить изображение", 
                        command=self.editor_save_image)
        menu.add_command(label="🔄 Сбросить настройки", 
                        command=self.editor_reset_sliders)
        
        menu.tk_popup(event.x_root, event.y_root)
    
    def _editor_send_to_storyboard(self):
        """Отправляет текущее изображение из редактора в раскадровку"""
        logger.info("_editor_send_to_storyboard called")
        
        if not self.editor_current_image:
            logger.warning("No editor_current_image")
            return
        
        try:
            # Сохраняем во временный файл
            import tempfile
            temp_dir = tempfile.gettempdir()
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_path = os.path.join(temp_dir, f"editor_export_{timestamp}.jpg")
            
            # Сохраняем текущее изображение (с примененными эффектами)
            img_to_save = self.editor_current_image
            if img_to_save.mode in ('RGBA', 'LA', 'P'):
                img_to_save = img_to_save.convert('RGB')
            
            img_to_save.save(temp_path, 'JPEG', quality=95)
            logger.info(f"Saved to temp: {temp_path}")
            
            # Добавляем в раскадровку
            img = Image.open(temp_path)
            self.storyboard_images.append({
                "path": temp_path,
                "x": 50,
                "y": 50,
                "width": img.width,
                "height": img.height
            })
            
            self.status_bar.configure(text="✅ Отправлено в раскадровку")
            self.switch_tab("Раскадровка")
            self.refresh_storyboard()
            logger.info("Successfully sent to storyboard")
            
        except Exception as e:
            logger.error(f"Error sending to storyboard: {e}")
            messagebox.showerror("Ошибка", f"Не удалось отправить в раскадровку: {e}")
    
    def editor_save_image(self):
        """Сохранение отредактированного изображения"""
        if not self.editor_current_image:
            messagebox.showwarning("Внимание", "Нет изображения для сохранения")
            return
        
        # Сохраняем настройки в библиотеку
        self._save_current_settings()
        
        # Диалог сохранения
        path = filedialog.asksaveasfilename(
            defaultextension=".jpg",
            filetypes=[("JPEG", "*.jpg"), ("PNG", "*.png"), ("TIFF", "*.tiff")],
            initialfile=f"edited_{os.path.basename(self.editor_image_path)}" if self.editor_image_path else "edited.jpg"
        )
        
        if path:
            self.editor_current_image.save(path, quality=95)
            logger.info(f"Saved edited image: {path}")
            messagebox.showinfo("Сохранено", f"Изображение сохранено:\n{path}")
    
    def _save_current_settings(self):
        """Сохраняет текущие настройки в библиотеку"""
        if not self.editor_image_path:
            return
        
        settings = {
            'exposure': self.editor_exposure.get(),
            'contrast': self.editor_contrast.get(),
            'brightness': self.editor_brightness.get(),
            'saturation': self.editor_saturation.get(),
            'temperature': self.editor_temperature.get(),
            'tint': self.editor_tint.get(),
            'vertical': self.editor_vertical.get(),
            'horizontal': self.editor_horizontal.get(),
            'rotation': self.editor_rotation.get(),
            'aspect': self.editor_aspect.get(),
            'scale': self.editor_scale.get(),
        }
        
        # Ищем в библиотеке
        for item in self.editor_library:
            if item['path'] == self.editor_image_path:
                item['settings'] = settings
                return
        
        # Добавляем новый
        self.editor_library.append({
            'path': self.editor_image_path,
            'settings': settings
        })
    
    def _load_settings(self, settings):
        """Загружает настройки из словаря"""
        self.editor_exposure.set(settings.get('exposure', 0.0))
        self.editor_contrast.set(settings.get('contrast', 1.0))
        self.editor_brightness.set(settings.get('brightness', 1.0))
        self.editor_saturation.set(settings.get('saturation', 1.0))
        self.editor_temperature.set(settings.get('temperature', 0))
        self.editor_tint.set(settings.get('tint', 0))
        self.editor_vertical.set(settings.get('vertical', 0))
        self.editor_horizontal.set(settings.get('horizontal', 0))
        self.editor_rotation.set(settings.get('rotation', 0))
        self.editor_aspect.set(settings.get('aspect', 0))
        self.editor_scale.set(settings.get('scale', 100))
    
    def editor_load_folder(self):
        """Загрузка папки с фотографиями"""
        folder = filedialog.askdirectory(title="Выберите папку с фотографиями")
        if not folder:
            return
        
        # Ищем изображения
        extensions = ('.jpg', '.jpeg', '.png', '.webp', '.tiff')
        files = sorted([f for f in os.listdir(folder) if f.lower().endswith(extensions)])
        
        if not files:
            messagebox.showwarning("Пусто", "В папке нет изображений")
            return
        
        # Создаём библиотеку
        self.editor_library = []
        self.editor_selected_indices = set()  # Для мульти-выбора
        for f in files:
            self.editor_library.append({
                'path': os.path.join(folder, f),
                'settings': None,
                'selected': False
            })
        
        self.editor_current_index = 0
        self._load_library_image(0)
        self._update_filmstrip()
        
        messagebox.showinfo("Загружено", f"Загружено {len(files)} фотографий\n\n← → навигация\nShift+клик - мульти-выбор\nCmd+A - применить ко всем выбранным")
    
    def _load_library_image(self, index):
        """Загружает изображение из библиотеки по индексу"""
        if not self.editor_library or index < 0 or index >= len(self.editor_library):
            return
        
        # Сохраняем текущие настройки
        self._save_current_settings()
        
        self.editor_current_index = index
        item = self.editor_library[index]
        
        # Загружаем изображение
        self.editor_image_path = item['path']
        self.editor_original_image = Image.open(item['path']).convert("RGB")
        orig_w, orig_h = self.editor_original_image.size
        
        # Preview
        if max(orig_w, orig_h) > self.editor_preview_max:
            scale = self.editor_preview_max / max(orig_w, orig_h)
            new_size = (int(orig_w * scale), int(orig_h * scale))
            self.editor_preview_image = self.editor_original_image.resize(new_size, Image.Resampling.LANCZOS)
        else:
            self.editor_preview_image = self.editor_original_image
        
        self.editor_original_array = np.array(self.editor_preview_image, dtype=np.float32)
        
        # Загружаем настройки если есть
        if item['settings']:
            self._load_settings(item['settings'])
        else:
            self.editor_reset_sliders()
        
        self.editor_current_image = self.editor_preview_image.copy()
        self.editor_zoom_level = 1.0
        self.editor_zoom_offset = (0, 0)
        self.editor_apply_adjustments_fast()
        
        logger.info(f"Loaded {index+1}/{len(self.editor_library)}: {os.path.basename(item['path'])}")
        self._highlight_filmstrip_selection()
    
    def _update_filmstrip(self):
        """Обновляет filmstrip с превью всех фотографий"""
        self.filmstrip_canvas.delete("all")
        self.filmstrip_thumbnails = []
        
        if not self.editor_library:
            return
        
        thumb_size = 60
        padding = 5
        x_offset = padding
        
        for i, item in enumerate(self.editor_library):
            try:
                # Создаём thumbnail
                img = Image.open(item['path'])
                img.thumbnail((thumb_size, thumb_size), Image.Resampling.LANCZOS)
                
                # Центрируем по вертикали
                y_offset = (70 - img.height) // 2
                
                photo = ImageTk.PhotoImage(img)
                self.filmstrip_thumbnails.append(photo)
                
                # Рисуем thumbnail
                self.filmstrip_canvas.create_image(x_offset, y_offset, anchor="nw", 
                                                   image=photo, tags=f"thumb_{i}")
                
                # Рамка (выделение для текущего и мульти-выбора)
                is_current = (i == self.editor_current_index)
                is_selected = hasattr(self, 'editor_selected_indices') and i in self.editor_selected_indices
                
                if is_current:
                    border_color = "#00ff00"  # Зелёный для текущего
                    border_width = 3
                elif is_selected:
                    border_color = "#ffaa00"  # Оранжевый для выбранных
                    border_width = 2
                else:
                    border_color = "#444444"
                    border_width = 1
                
                self.filmstrip_canvas.create_rectangle(
                    x_offset - 2, y_offset - 2,
                    x_offset + img.width + 2, y_offset + img.height + 2,
                    outline=border_color, width=border_width, tags=f"border_{i}"
                )
                
                # Клик для выбора (с поддержкой Shift внутри обработчика)
                self.filmstrip_canvas.tag_bind(f"thumb_{i}", "<Button-1>", 
                                               lambda e, idx=i: self._filmstrip_click(idx, e))
                self.filmstrip_canvas.tag_bind(f"border_{i}", "<Button-1>", 
                                               lambda e, idx=i: self._filmstrip_click(idx, e))
                
                # ПКМ для контекстного меню (Button-2 для Mac, Button-3 для Windows/Linux)
                self.filmstrip_canvas.tag_bind(f"thumb_{i}", "<Button-2>", 
                                               lambda e, idx=i: self._filmstrip_right_click(idx, e))
                self.filmstrip_canvas.tag_bind(f"border_{i}", "<Button-2>", 
                                               lambda e, idx=i: self._filmstrip_right_click(idx, e))
                self.filmstrip_canvas.tag_bind(f"thumb_{i}", "<Button-3>", 
                                               lambda e, idx=i: self._filmstrip_right_click(idx, e))
                self.filmstrip_canvas.tag_bind(f"border_{i}", "<Button-3>", 
                                               lambda e, idx=i: self._filmstrip_right_click(idx, e))
                self.filmstrip_canvas.tag_bind(f"thumb_{i}", "<Control-Button-1>", 
                                               lambda e, idx=i: self._filmstrip_right_click(idx, e))
                self.filmstrip_canvas.tag_bind(f"border_{i}", "<Control-Button-1>", 
                                               lambda e, idx=i: self._filmstrip_right_click(idx, e))
                
                x_offset += img.width + padding
                
            except Exception as e:
                logger.error(f"Filmstrip thumbnail error: {e}")
                x_offset += thumb_size + padding
        
        # Настраиваем scroll region
        self.filmstrip_canvas.configure(scrollregion=(0, 0, x_offset, 70))
        
        # Scroll колёсиком
        self.filmstrip_canvas.bind("<MouseWheel>", self._filmstrip_scroll)
    
    def _highlight_filmstrip_selection(self):
        """Подсвечивает текущее фото в filmstrip"""
        for i in range(len(self.editor_library)):
            border_color = "#00ff00" if i == self.editor_current_index else "#444444"
            border_width = 3 if i == self.editor_current_index else 1
            self.filmstrip_canvas.itemconfig(f"border_{i}", outline=border_color, width=border_width)
    
    def _filmstrip_click(self, index, event):
        """Обработка клика на filmstrip с проверкой Shift"""
        # Проверяем Shift (state & 0x1 на Mac/Linux)
        shift_pressed = bool(event.state & 0x1)
        
        if shift_pressed:
            # Shift+клик = добавить/убрать из выбора
            self._toggle_multi_select(index)
        else:
            # Обычный клик = переключиться на фото
            if index != self.editor_current_index:
                self._load_library_image(index)
    
    def _select_from_filmstrip(self, index, event=None):
        """Выбирает фото из filmstrip"""
        if index != self.editor_current_index:
            self._load_library_image(index)
    
    def _toggle_multi_select(self, index):
        """Переключает мульти-выбор для фото"""
        if not hasattr(self, 'editor_selected_indices'):
            self.editor_selected_indices = set()
        
        if index in self.editor_selected_indices:
            self.editor_selected_indices.remove(index)
        else:
            self.editor_selected_indices.add(index)
        
        # Обновляем только рамки, не перерисовываем всё
        self._update_filmstrip_borders()
        logger.info(f"Multi-select: {len(self.editor_selected_indices)} photos selected, indices: {self.editor_selected_indices}")
    
    def _update_filmstrip_borders(self):
        """Обновляет только рамки в filmstrip (быстрее чем полная перерисовка)"""
        for i in range(len(self.editor_library)):
            is_current = (i == self.editor_current_index)
            is_selected = hasattr(self, 'editor_selected_indices') and i in self.editor_selected_indices
            
            if is_current:
                border_color = "#00ff00"
                border_width = 3
            elif is_selected:
                border_color = "#ffaa00"
                border_width = 2
            else:
                border_color = "#444444"
                border_width = 1
            
            self.filmstrip_canvas.itemconfig(f"border_{i}", outline=border_color, width=border_width)
    
    def editor_apply_to_selected(self):
        """Применяет текущие настройки ко всем выбранным фото и обрабатывает их"""
        if not hasattr(self, 'editor_selected_indices') or not self.editor_selected_indices:
            messagebox.showwarning("Внимание", "Выберите фото с помощью Shift+клик\n\nШаги:\n1. Shift+клик на фото в filmstrip\n2. Повторите для всех нужных фото\n3. Нажмите Cmd+A")
            return
        
        # Получаем текущие настройки
        settings = {
            'exposure': self.editor_exposure.get(),
            'contrast': self.editor_contrast.get(),
            'highlights': self.editor_highlights.get(),
            'shadows': self.editor_shadows.get(),
            'brightness': self.editor_brightness.get(),
            'saturation': self.editor_saturation.get(),
            'temperature': self.editor_temperature.get(),
            'tint': self.editor_tint.get(),
            'vertical': self.editor_vertical.get(),
            'horizontal': self.editor_horizontal.get(),
            'rotation': self.editor_rotation.get(),
            'shift_x': self.editor_shift_x.get(),
            'shift_y': self.editor_shift_y.get(),
            'aspect': self.editor_aspect.get(),
            'scale': self.editor_scale.get(),
        }
        
        # Логируем для отладки
        logger.info(f"Applying settings to {len(self.editor_selected_indices)} photos: {list(self.editor_selected_indices)}")
        
        # Применяем ко всем выбранным
        count = 0
        applied_indices = []
        for idx in list(self.editor_selected_indices):  # Копируем set для безопасной итерации
            if 0 <= idx < len(self.editor_library):
                self.editor_library[idx]['settings'] = settings.copy()
                applied_indices.append(idx)
                count += 1
                logger.info(f"Applied to photo {idx}: {self.editor_library[idx]['path']}")
        
        # Сбрасываем выбор
        self.editor_selected_indices.clear()
        self._update_filmstrip_borders()
        
        messagebox.showinfo("Применено", f"Настройки применены к {count} фотографиям:\n{applied_indices}\n\nПри экспорте все фото будут обработаны с этими настройками")
    
    def _filmstrip_scroll(self, event):
        """Scroll filmstrip колёсиком"""
        self.filmstrip_canvas.xview_scroll(-1 if event.delta > 0 else 1, "units")
    
    def _filmstrip_right_click(self, index, event):
        """ПКМ на filmstrip - контекстное меню"""
        # Если кликнули на невыбранное фото - выбираем его
        if not hasattr(self, 'editor_selected_indices'):
            self.editor_selected_indices = set()
        
        if index not in self.editor_selected_indices:
            self.editor_selected_indices = {index}
            self._update_filmstrip_borders()
        
        # Создаём меню
        menu = tk.Menu(self, tearoff=0)
        
        count = len(self.editor_selected_indices)
        if count == 1:
            menu.add_command(label="🎬 Отправить в раскадровку", 
                            command=self._send_filmstrip_to_storyboard)
        else:
            menu.add_command(label=f"🎬 Отправить в раскадровку ({count} фото)", 
                            command=self._send_filmstrip_to_storyboard)
        
        menu.add_separator()
        menu.add_command(label="💾 Экспортировать выбранные", 
                        command=self.editor_apply_to_selected)
        menu.add_command(label="🗑️ Удалить из библиотеки", 
                        command=self._remove_from_library)
        
        menu.tk_popup(event.x_root, event.y_root)
    
    def _send_filmstrip_to_storyboard(self):
        """Отправляет выбранные фото из filmstrip в раскадровку"""
        if not hasattr(self, 'editor_selected_indices') or not self.editor_selected_indices:
            # Если ничего не выбрано, отправляем текущее
            if self.editor_current_image and self.editor_image_path:
                self._editor_send_to_storyboard()
            return
        
        import tempfile
        import datetime
        
        sent_count = 0
        
        for idx in sorted(self.editor_selected_indices):
            if 0 <= idx < len(self.editor_library):
                item = self.editor_library[idx]
                path = item.get('path')
                
                if path and os.path.exists(path):
                    try:
                        img = Image.open(path)
                        
                        # Если есть сохранённые настройки - применяем их
                        if item.get('settings'):
                            # Применяем настройки к изображению
                            settings = item['settings']
                            # Здесь можно добавить применение настроек
                            # Пока просто используем оригинал
                        
                        # Добавляем в раскадровку
                        self.storyboard_images.append({
                            "path": path,
                            "x": 50 + sent_count * 30,
                            "y": 50 + sent_count * 30,
                            "width": img.width,
                            "height": img.height
                        })
                        sent_count += 1
                        
                    except Exception as e:
                        logger.error(f"Error sending to storyboard: {e}")
        
        if sent_count > 0:
            self.status_bar.configure(text=f"✅ Отправлено {sent_count} фото в раскадровку")
            self.switch_tab("Раскадровка")
            self.refresh_storyboard()
            logger.info(f"Sent {sent_count} photos from filmstrip to storyboard")
    
    def _remove_from_library(self):
        """Удаляет выбранные фото из библиотеки редактора"""
        if not hasattr(self, 'editor_selected_indices') or not self.editor_selected_indices:
            return
        
        # Удаляем в обратном порядке чтобы индексы не сбивались
        for idx in sorted(self.editor_selected_indices, reverse=True):
            if 0 <= idx < len(self.editor_library):
                del self.editor_library[idx]
        
        self.editor_selected_indices.clear()
        
        # Корректируем текущий индекс
        if self.editor_current_index >= len(self.editor_library):
            self.editor_current_index = max(0, len(self.editor_library) - 1)
        
        # Обновляем UI
        self._update_filmstrip()
        if self.editor_library:
            self._load_library_image(self.editor_current_index)
        else:
            self.editor_canvas.delete("all")
            self.editor_current_image = None
        
        self.status_bar.configure(text=f"🗑️ Удалено из библиотеки")
    
    def _navigate_library(self, direction):
        """Навигация по библиотеке стрелками"""
        if not self.editor_library:
            return
        new_index = self.editor_current_index + direction
        if 0 <= new_index < len(self.editor_library):
            self._load_library_image(new_index)
    
    def editor_export_all(self):
        """Экспорт всех фотографий с применёнными настройками"""
        if not self.editor_library:
            messagebox.showwarning("Библиотека пуста", "Сначала загрузите папку с фотографиями")
            return
        
        # Сохраняем текущие настройки
        self._save_current_settings()
        
        # Выбираем папку для экспорта
        folder = filedialog.askdirectory(title="Выберите папку для экспорта")
        if not folder:
            return
        
        exported = 0
        for item in self.editor_library:
            if not item['settings']:
                continue
            
            try:
                # Загружаем оригинал
                img = Image.open(item['path']).convert("RGB")
                arr = np.array(img, dtype=np.float32)
                s = item['settings']
                
                # Применяем настройки
                if abs(s.get('exposure', 0)) > 0.01:
                    arr = arr * (2 ** s['exposure'])
                if abs(s.get('brightness', 1) - 1) > 0.01:
                    arr = arr * s['brightness']
                if abs(s.get('contrast', 1) - 1) > 0.01:
                    arr = (arr - 128) * s['contrast'] + 128
                if abs(s.get('saturation', 1) - 1) > 0.01:
                    lum = 0.299 * arr[:,:,0] + 0.587 * arr[:,:,1] + 0.114 * arr[:,:,2]
                    lum = lum[:,:,np.newaxis]
                    arr = lum + (arr - lum) * s['saturation']
                if abs(s.get('temperature', 0)) > 1:
                    arr[:,:,0] += s['temperature'] * 0.6
                    arr[:,:,2] -= s['temperature'] * 0.6
                if abs(s.get('tint', 0)) > 1:
                    arr[:,:,1] -= s['tint'] * 0.5
                
                arr = np.clip(arr, 0, 255)
                result = Image.fromarray(arr.astype(np.uint8))
                
                # Геометрия через OpenCV
                if any(abs(s.get(k, 0)) > 0.5 for k in ['rotation', 'vertical', 'horizontal']):
                    import cv2
                    arr = np.array(result)
                    h, w = arr.shape[:2]
                    cx, cy = w/2, h/2
                    M = np.eye(3, dtype=np.float32)
                    
                    if abs(s.get('rotation', 0)) > 0.1:
                        cos_r = np.cos(np.radians(-s['rotation']))
                        sin_r = np.sin(np.radians(-s['rotation']))
                        R = np.array([[cos_r, -sin_r, cx - cx*cos_r + cy*sin_r],
                                     [sin_r, cos_r, cy - cx*sin_r - cy*cos_r],
                                     [0, 0, 1]], dtype=np.float32)
                        M = R @ M
                    
                    if abs(s.get('vertical', 0)) > 0.5:
                        v = s['vertical'] / 100.0 * 0.0015
                        P = np.array([[1,0,0],[0,1,0],[0,v,1]], dtype=np.float32)
                        M = P @ M
                    
                    if abs(s.get('horizontal', 0)) > 0.5:
                        hz = s['horizontal'] / 100.0 * 0.0015
                        P = np.array([[1,0,0],[0,1,0],[hz,0,1]], dtype=np.float32)
                        M = P @ M
                    
                    arr = cv2.warpPerspective(arr, M, (w, h), borderValue=(30,30,40))
                    result = Image.fromarray(arr)
                
                # Сохраняем
                name = os.path.basename(item['path'])
                result.save(os.path.join(folder, f"edited_{name}"), quality=95)
                exported += 1
                
            except Exception as e:
                logger.error(f"Export error for {item['path']}: {e}")
        
        messagebox.showinfo("Экспорт завершён", f"Экспортировано {exported} из {len(self.editor_library)} фотографий")
    
    def editor_toggle_wb_picker(self):
        """Включает режим выбора точки для баланса белого"""
        self.editor_wb_picker_mode = not self.editor_wb_picker_mode
        if self.editor_wb_picker_mode:
            self.wb_btn.configure(fg_color=COLORS["success"])
            self.editor_canvas.configure(cursor="crosshair")
        else:
            self.wb_btn.configure(fg_color=COLORS["warning"])
            self.editor_canvas.configure(cursor="")
    
    def editor_apply_wb_from_point(self, x, y):
        """Применяет баланс белого по выбранной точке"""
        if self.editor_original_array is None:
            return
        
        # Переводим координаты canvas в координаты изображения
        img_x = int((x - self.editor_img_offset[0]) / self.editor_zoom_level)
        img_y = int((y - self.editor_img_offset[1]) / self.editor_zoom_level)
        
        h, w = self.editor_original_array.shape[:2]
        if 0 <= img_x < w and 0 <= img_y < h:
            # Берём среднее по области 5x5
            x1, x2 = max(0, img_x-2), min(w, img_x+3)
            y1, y2 = max(0, img_y-2), min(h, img_y+3)
            
            region = self.editor_original_array[y1:y2, x1:x2]
            avg_r = np.mean(region[:,:,0])
            avg_g = np.mean(region[:,:,1])
            avg_b = np.mean(region[:,:,2])
            
            # Вычисляем коррекцию (цель - сделать точку нейтральной)
            gray = (avg_r + avg_g + avg_b) / 3
            
            # Температура: разница R-B
            temp_correction = (avg_b - avg_r) * 0.5
            # Тинт: отклонение G от среднего
            tint_correction = (gray - avg_g) * 0.8
            
            # Применяем
            self.editor_temperature.set(np.clip(temp_correction, -100, 100))
            self.editor_tint.set(np.clip(tint_correction, -100, 100))
            
            self.editor_apply_adjustments_fast()
            logger.info(f"WB from point ({img_x}, {img_y}): temp={temp_correction:.0f}, tint={tint_correction:.0f}")
        
        # Выключаем режим
        self.editor_toggle_wb_picker()
    
    def editor_canvas_zoom(self, event):
        """Zoom колёсиком мыши"""
        if not self.editor_current_image:
            return
        
        # Определяем направление
        if event.delta > 0:
            factor = 1.1
        else:
            factor = 0.9
        
        new_zoom = self.editor_zoom_level * factor
        new_zoom = max(1.0, min(5.0, new_zoom))  # Ограничиваем 1x - 5x (не уменьшаем)
        
        if new_zoom != self.editor_zoom_level:
            # Zoom относительно позиции курсора
            mx, my = event.x, event.y
            ox, oy = self.editor_zoom_offset
            
            # Новое смещение
            self.editor_zoom_offset = (
                mx - (mx - ox) * (new_zoom / self.editor_zoom_level),
                my - (my - oy) * (new_zoom / self.editor_zoom_level)
            )
            self.editor_zoom_level = new_zoom
            self.editor_display_image()
    
    def editor_canvas_pan_start(self, event):
        """Начало pan"""
        self.editor_pan_start = (event.x, event.y)
        self.editor_pan_offset_start = self.editor_zoom_offset
    
    def editor_canvas_pan(self, event):
        """Pan при зуме"""
        if hasattr(self, 'editor_pan_start'):
            dx = event.x - self.editor_pan_start[0]
            dy = event.y - self.editor_pan_start[1]
            self.editor_zoom_offset = (
                self.editor_pan_offset_start[0] + dx,
                self.editor_pan_offset_start[1] + dy
            )
            self.editor_display_image()
    
    # ==================== AI / НЕЙРОСЕТИ TAB ====================
    def create_ai_tab(self):
        import tkinter as tk
        tab = self.tab_ai
        tab.grid_columnconfigure(0, weight=0)  # Левая панель - фикс
        tab.grid_columnconfigure(1, weight=1)  # Правая панель - растягивается
        tab.grid_rowconfigure(0, weight=1)
        
        # === ЛЕВАЯ ПАНЕЛЬ - ИНПУТЫ ===
        left_panel = ctk.CTkFrame(tab, fg_color=COLORS["bg_tertiary"], corner_radius=GLASS_CORNER_RADIUS, width=360)
        left_panel.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="ns")
        left_panel.grid_propagate(False)
        self.ai_left_panel = left_panel
        
        # Заголовок
        ctk.CTkLabel(left_panel, text="🤖 Нейросети", 
                    font=ctk.CTkFont(family=FONT_FAMILY, size=18, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(pady=(8, 5))
        
        # === ВЫБОР МОДЕЛИ (фиксированный вверху) ===
        model_frame = ctk.CTkFrame(left_panel, fg_color=COLORS["bg_secondary"], corner_radius=GLASS_CORNER_RADIUS_SMALL)
        model_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(model_frame, text="Модель",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(anchor="w", padx=8, pady=(8, 5))
        
        self.ai_model_var = ctk.StringVar(value="seedream")
        
        models_row = ctk.CTkFrame(model_frame, fg_color="transparent")
        models_row.pack(fill="x", padx=8, pady=2)
        
        ctk.CTkRadioButton(models_row, text="Seedream 4.5", variable=self.ai_model_var, value="seedream",
                          font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                          command=self._on_model_change).pack(side="left", padx=(0, 15))
        
        ctk.CTkRadioButton(models_row, text="NanoBanana Pro", variable=self.ai_model_var, value="nana",
                          font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                          command=self._on_model_change).pack(side="left", padx=(0, 15))
        
        models_row2 = ctk.CTkFrame(model_frame, fg_color="transparent")
        models_row2.pack(fill="x", padx=8, pady=(2, 8))
        
        ctk.CTkRadioButton(models_row2, text="QWEN Angles", variable=self.ai_model_var, value="qwen_angles",
                          font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                          command=self._on_model_change).pack(side="left", padx=(0, 15))
        
        ctk.CTkRadioButton(models_row2, text="Расширить", variable=self.ai_model_var, value="wide",
                          font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                          command=self._on_model_change).pack(side="left")
        
        # Scrollable frame для динамических настроек
        scroll_frame = ctk.CTkScrollableFrame(left_panel, fg_color="transparent")
        scroll_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self.ai_scroll_frame = scroll_frame
        
        # Промпт (в отдельном фрейме для скрытия)
        self.ai_prompt_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        self.ai_prompt_frame.pack(fill="x", padx=0, pady=0)
        
        ctk.CTkLabel(self.ai_prompt_frame, text="Промпт:", 
                    font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                    text_color=COLORS["text_secondary"]).pack(anchor="w", padx=5, pady=(5, 2))
        self.ai_prompt = ctk.CTkTextbox(self.ai_prompt_frame, height=50, 
                                        font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                                        fg_color=COLORS["bg_secondary"], corner_radius=8)
        self.ai_prompt.pack(fill="x", padx=5, pady=(0, 8))
        
        # === ГЛАВНОЕ ФОТО ===
        self.ai_main_frame = ctk.CTkFrame(scroll_frame, fg_color=COLORS["bg_secondary"], corner_radius=GLASS_CORNER_RADIUS_SMALL)
        self.ai_main_frame.pack(fill="x", padx=5, pady=5)
        main_frame = self.ai_main_frame
        
        main_header = ctk.CTkFrame(main_frame, fg_color="transparent")
        main_header.pack(fill="x", padx=8, pady=(8, 5))
        
        ctk.CTkLabel(main_header, text="Главное фото",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(side="left")
        
        ctk.CTkButton(main_header, text="Добавить фото", command=self.load_ai_main_image,
                     height=28, width=110, font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                     fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
                     corner_radius=8).pack(side="right")
        
        self.ai_main_image = None
        self.ai_main_label = ctk.CTkLabel(main_header, text="Не выбрано",
                                          font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                                          text_color=COLORS["text_secondary"])
        self.ai_main_label.pack(side="left", padx=8)
        
        # Превью главного фото - большое, со скруглёнными краями и обводкой
        self.ai_main_preview_frame = ctk.CTkFrame(main_frame, fg_color=COLORS["bg_tertiary"], 
                                                   corner_radius=GLASS_CORNER_RADIUS_SMALL, border_width=2, 
                                                   border_color=COLORS["text_secondary"],
                                                   width=300, height=180)
        self.ai_main_preview_frame.pack(padx=10, pady=(0, 10))
        self.ai_main_preview_frame.pack_propagate(False)
        
        # Контейнер для превью с крестиком
        preview_container = ctk.CTkFrame(self.ai_main_preview_frame, fg_color="transparent")
        preview_container.pack(expand=True, fill="both")
        
        self.ai_main_preview = ctk.CTkLabel(preview_container, text="📷 Превью", 
                                            font=ctk.CTkFont(size=12),
                                            text_color=COLORS["text_secondary"],
                                            cursor="hand2")
        self.ai_main_preview.pack(expand=True)
        self.ai_main_preview.bind("<Button-1>", lambda e: self._show_enlarged_image(self.ai_main_image))
        
        # Кнопка удаления (скрыта по умолчанию)
        self.ai_main_delete_btn = ctk.CTkButton(preview_container, text="✕", width=30, height=30,
                                                font=ctk.CTkFont(size=16, weight="bold"),
                                                fg_color="#ff4444", hover_color="#cc0000",
                                                command=self._delete_main_image)
        self.ai_main_photo = None
        
        # === РЕФЕРЕНСЫ ===
        self.ai_ref_frame = ctk.CTkFrame(scroll_frame, fg_color=COLORS["bg_secondary"], corner_radius=GLASS_CORNER_RADIUS_SMALL)
        self.ai_ref_frame.pack(fill="x", padx=5, pady=5)
        
        ref_header = ctk.CTkFrame(self.ai_ref_frame, fg_color="transparent")
        ref_header.pack(fill="x", padx=8, pady=(8, 5))
        
        ctk.CTkLabel(ref_header, text="Референсы",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(side="left")
        
        ctk.CTkButton(ref_header, text="Добавить фото", command=self.load_ai_references,
                     height=28, width=110, font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                     fg_color=COLORS["secondary"], hover_color=COLORS["secondary_hover"],
                     corner_radius=8).pack(side="right")
        
        self.ai_references = []
        self.ai_ref_label = ctk.CTkLabel(ref_header, text="",
                                         font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                                         text_color=COLORS["text_secondary"])
        self.ai_ref_label.pack(side="left", padx=8)
        
        # Контейнер для превью референсов
        self.ai_ref_preview_frame = ctk.CTkFrame(self.ai_ref_frame, fg_color="transparent", height=50)
        self.ai_ref_preview_frame.pack(fill="x", padx=8, pady=(0, 8))
        self.ai_ref_photos = []
        
        # === РАЗМЕР ===
        self.ai_size_frame = ctk.CTkFrame(scroll_frame, fg_color=COLORS["bg_secondary"], corner_radius=GLASS_CORNER_RADIUS_SMALL)
        self.ai_size_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(self.ai_size_frame, text="Размер",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(anchor="w", padx=8, pady=(8, 5))
        
        # Переменная для выбора режима размера
        self.ai_size_mode = ctk.StringVar(value="custom")
        
        # Режим кастомного размера
        custom_row = ctk.CTkFrame(self.ai_size_frame, fg_color="transparent")
        custom_row.pack(fill="x", padx=8, pady=2)
        
        ctk.CTkRadioButton(custom_row, text="Кастомный:", variable=self.ai_size_mode, value="custom",
                          font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                          command=self._update_ai_size_mode).pack(side="left")
        
        self.ai_width = ctk.CTkEntry(custom_row, width=55, placeholder_text="W",
                                     font=ctk.CTkFont(family=FONT_FAMILY, size=10))
        self.ai_width.pack(side="left", padx=(10, 2))
        self.ai_width.insert(0, "1536")
        
        ctk.CTkLabel(custom_row, text="×", font=ctk.CTkFont(size=10),
                    text_color=COLORS["text_secondary"]).pack(side="left")
        
        self.ai_height = ctk.CTkEntry(custom_row, width=55, placeholder_text="H",
                                      font=ctk.CTkFont(family=FONT_FAMILY, size=10))
        self.ai_height.pack(side="left", padx=2)
        self.ai_height.insert(0, "1024")
        
        # Режим соотношения сторон
        ratio_row = ctk.CTkFrame(self.ai_size_frame, fg_color="transparent")
        ratio_row.pack(fill="x", padx=8, pady=2)
        
        ctk.CTkRadioButton(ratio_row, text="Соотношение:", variable=self.ai_size_mode, value="ratio",
                          font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                          command=self._update_ai_size_mode).pack(side="left")
        
        self.ai_preset = ctk.CTkOptionMenu(ratio_row, 
                                           values=["как исходник", "3:2", "2:3", "16:9", "9:16", "4:3", "3:4", "1:1"],
                                           command=self.apply_ai_preset,
                                           font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                                           fg_color=COLORS["bg_tertiary"],
                                           button_color=COLORS["primary"],
                                           width=100)
        self.ai_preset.pack(side="left", padx=(10, 0))
        
        # === УЗНАТЬ СООТНОШЕНИЕ СТОРОН ===
        detect_frame = ctk.CTkFrame(self.ai_size_frame, fg_color="transparent")
        detect_frame.pack(fill="x", padx=8, pady=(8, 8))
        
        ctk.CTkLabel(detect_frame, text="Узнать соотношение сторон:",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                    text_color=COLORS["text_secondary"]).pack(side="left")
        
        ctk.CTkButton(detect_frame, text="📷 Фото", command=self._detect_aspect_ratio,
                     height=24, width=60, font=ctk.CTkFont(family=FONT_FAMILY, size=9),
                     fg_color=COLORS["bg_tertiary"], hover_color=COLORS["secondary"],
                     corner_radius=6).pack(side="left", padx=(8, 0))
        
        self.ai_detected_ratio = ctk.CTkLabel(detect_frame, text="",
                                              font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
                                              text_color=COLORS["success"])
        self.ai_detected_ratio.pack(side="left", padx=8)
        
        # === QWEN ANGLES НАСТРОЙКИ (скрыты по умолчанию) ===
        self.qwen_settings_frame = ctk.CTkFrame(scroll_frame, fg_color=COLORS["bg_secondary"], corner_radius=GLASS_CORNER_RADIUS_SMALL)
        # Не pack() - будет показан при выборе QWEN
        
        ctk.CTkLabel(self.qwen_settings_frame, text="🎥 Настройки камеры",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(anchor="w", padx=8, pady=(8, 5))
        
        # Rotate left/right (-180 to 180)
        rotate_row = ctk.CTkFrame(self.qwen_settings_frame, fg_color="transparent")
        rotate_row.pack(fill="x", padx=8, pady=3)
        ctk.CTkLabel(rotate_row, text="Поворот (лево/право):",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                    text_color=COLORS["text_secondary"]).pack(side="left")
        self.qwen_rotate_label = ctk.CTkLabel(rotate_row, text="0°",
                                              font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
                                              text_color=COLORS["primary"], width=40)
        self.qwen_rotate_label.pack(side="right")
        
        self.qwen_rotate = ctk.CTkSlider(self.qwen_settings_frame, from_=-90, to=90,
                                         number_of_steps=180, width=300,
                                         command=lambda v: self.qwen_rotate_label.configure(text=f"{int(v)}°"))
        self.qwen_rotate.pack(padx=8, pady=(0, 5))
        self.qwen_rotate.set(0)
        
        # Move forward (0 to 10)
        forward_row = ctk.CTkFrame(self.qwen_settings_frame, fg_color="transparent")
        forward_row.pack(fill="x", padx=8, pady=3)
        ctk.CTkLabel(forward_row, text="Приближение:",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                    text_color=COLORS["text_secondary"]).pack(side="left")
        self.qwen_forward_label = ctk.CTkLabel(forward_row, text="0",
                                               font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
                                               text_color=COLORS["primary"], width=40)
        self.qwen_forward_label.pack(side="right")
        
        self.qwen_forward = ctk.CTkSlider(self.qwen_settings_frame, from_=0, to=10,
                                          number_of_steps=20, width=300,
                                          command=lambda v: self.qwen_forward_label.configure(text=f"{v:.1f}"))
        self.qwen_forward.pack(padx=8, pady=(0, 5))
        self.qwen_forward.set(0)
        
        # Vertical angle (-1 to 1)
        vertical_row = ctk.CTkFrame(self.qwen_settings_frame, fg_color="transparent")
        vertical_row.pack(fill="x", padx=8, pady=3)
        ctk.CTkLabel(vertical_row, text="Вертикальный угол:",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                    text_color=COLORS["text_secondary"]).pack(side="left")
        self.qwen_vertical_label = ctk.CTkLabel(vertical_row, text="0",
                                                font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
                                                text_color=COLORS["primary"], width=40)
        self.qwen_vertical_label.pack(side="right")
        
        self.qwen_vertical = ctk.CTkSlider(self.qwen_settings_frame, from_=-1, to=1,
                                           number_of_steps=20, width=300,
                                           command=lambda v: self.qwen_vertical_label.configure(text=f"{v:.1f}"))
        self.qwen_vertical.pack(padx=8, pady=(0, 5))
        self.qwen_vertical.set(0)
        
        # 3D Куб визуализация
        cube_frame = ctk.CTkFrame(self.qwen_settings_frame, fg_color="transparent")
        cube_frame.pack(fill="x", padx=8, pady=(5, 8))
        
        ctk.CTkLabel(cube_frame, text="3D Превью:",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                    text_color=COLORS["text_secondary"]).pack(anchor="w")
        
        self.qwen_cube_canvas = tk.Canvas(cube_frame, width=150, height=150, 
                                          bg=COLORS["bg_tertiary"], highlightthickness=1,
                                          highlightbackground=COLORS["text_secondary"])
        self.qwen_cube_canvas.pack(pady=5)
        
        # Инициализация 3D куба
        self._init_3d_cube()
        self._draw_3d_cube()
        
        # Привязка мыши для вращения куба
        self.qwen_cube_canvas.bind("<Button-1>", self._cube_mouse_press)
        self.qwen_cube_canvas.bind("<B1-Motion>", self._cube_mouse_drag)
        
        # Обновление слайдеров при изменении куба
        self.qwen_rotate.configure(command=self._on_qwen_slider_change)
        self.qwen_forward.configure(command=self._on_qwen_slider_change)
        self.qwen_vertical.configure(command=self._on_qwen_slider_change)
        
        ctk.CTkLabel(cube_frame, text="🖱️ Перетаскивайте куб мышью",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=8),
                    text_color=COLORS["text_secondary"]).pack()
        
        # === НАСТРОЙКИ WIDE (скрыты по умолчанию) ===
        self.wide_settings_frame = ctk.CTkFrame(scroll_frame, fg_color=COLORS["bg_secondary"], corner_radius=GLASS_CORNER_RADIUS_SMALL)
        # Не pack() - будет показан при выборе Wide
        
        ctk.CTkLabel(self.wide_settings_frame, text="📐 Расширить изображение",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(anchor="w", padx=8, pady=(8, 5))
        
        # Две кнопки: Выбрать фото / Выбрать папку
        wide_btn_frame = ctk.CTkFrame(self.wide_settings_frame, fg_color="transparent")
        wide_btn_frame.pack(fill="x", padx=8, pady=5)
        
        ctk.CTkButton(wide_btn_frame, text="📷 Выбрать фото", 
                     command=self._load_wide_files,
                     height=32, width=130, font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                     fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
                     corner_radius=8).pack(side="left", padx=(0, 10))
        
        ctk.CTkButton(wide_btn_frame, text="📁 Выбрать папку", 
                     command=self._load_wide_folder,
                     height=32, width=130, font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                     fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
                     corner_radius=8).pack(side="left")
        
        # Счетчик и кнопка очистки
        self.wide_count_label = ctk.CTkLabel(wide_btn_frame, text="0 фото",
                                             font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                                             text_color=COLORS["text_secondary"])
        self.wide_count_label.pack(side="left", padx=10)
        
        ctk.CTkButton(wide_btn_frame, text="✕", width=28, height=28,
                     command=self._clear_wide_images,
                     fg_color="#ff4444", hover_color="#cc0000",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(side="right")
        
        # Список превью изображений с горизонтальным скроллом
        self.wide_preview_frame = ctk.CTkFrame(self.wide_settings_frame, fg_color=COLORS["bg_tertiary"],
                                               corner_radius=8, height=75)
        self.wide_preview_frame.pack(fill="x", padx=8, pady=5)
        self.wide_preview_frame.pack_propagate(False)
        
        # Canvas для горизонтального скролла
        self.wide_preview_canvas = tk.Canvas(self.wide_preview_frame, bg=COLORS["bg_tertiary"],
                                             highlightthickness=0, height=50)
        self.wide_preview_canvas.pack(side="top", fill="both", expand=True, padx=2, pady=(2, 0))
        
        self.wide_preview_scroll = ctk.CTkFrame(self.wide_preview_canvas, fg_color="transparent")
        self.wide_preview_canvas_window = self.wide_preview_canvas.create_window(
            (0, 0), window=self.wide_preview_scroll, anchor="nw")
        
        # Горизонтальный scrollbar внизу
        self.wide_scrollbar = tk.Scrollbar(self.wide_preview_frame, orient="horizontal",
                                           command=self.wide_preview_canvas.xview)
        self.wide_scrollbar.pack(side="bottom", fill="x", padx=2, pady=(0, 2))
        self.wide_preview_canvas.configure(xscrollcommand=self.wide_scrollbar.set)
        
        # Привязываем скролл колёсиком мыши и трекпадом
        def _on_wide_mousewheel(event):
            # На Mac трекпад отправляет delta, на Windows тоже
            self.wide_preview_canvas.xview_scroll(int(-1 * (event.delta / 30)), "units")
        self.wide_preview_canvas.bind("<MouseWheel>", _on_wide_mousewheel)
        self.wide_preview_scroll.bind("<MouseWheel>", _on_wide_mousewheel)
        
        # Обновляем scrollregion при изменении размера
        def _on_wide_frame_configure(event):
            self.wide_preview_canvas.configure(scrollregion=self.wide_preview_canvas.bbox("all"))
        self.wide_preview_scroll.bind("<Configure>", _on_wide_frame_configure)
        
        self.wide_images = []  # Список путей к изображениям
        self.wide_preview_photos = []  # Ссылки на фото для превью
        
        # Выбор модели для Wide
        ctk.CTkLabel(self.wide_settings_frame, text="Модель для расширения:",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                    text_color=COLORS["text_secondary"]).pack(anchor="w", padx=8, pady=(5, 3))
        
        self.wide_model_var = ctk.StringVar(value="seedream")
        wide_model_row = ctk.CTkFrame(self.wide_settings_frame, fg_color="transparent")
        wide_model_row.pack(fill="x", padx=8, pady=3)
        
        ctk.CTkRadioButton(wide_model_row, text="Seedream 4.5", variable=self.wide_model_var, value="seedream",
                          font=ctk.CTkFont(family=FONT_FAMILY, size=10)).pack(side="left", padx=(0, 15))
        ctk.CTkRadioButton(wide_model_row, text="NanoBanana Pro", variable=self.wide_model_var, value="nana",
                          font=ctk.CTkFont(family=FONT_FAMILY, size=10)).pack(side="left")
        
        # Соотношения сторон - используем CTkSegmentedButton для компактности
        ctk.CTkLabel(self.wide_settings_frame, text="Соотношение:",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                    text_color=COLORS["text_secondary"]).pack(anchor="w", padx=8, pady=(5, 2))
        
        self.wide_ratio_var = ctk.StringVar(value="16:9")
        self.wide_ratio_segment = ctk.CTkSegmentedButton(
            self.wide_settings_frame, 
            values=["3:2", "4:3", "16:9", "1:1"],
            variable=self.wide_ratio_var,
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            command=self._on_wide_ratio_change,
            height=28
        )
        self.wide_ratio_segment.pack(fill="x", padx=8, pady=2)
        
        # Кастомный размер (скрыт по умолчанию)
        self.wide_custom_frame = ctk.CTkFrame(self.wide_settings_frame, fg_color="transparent")
        
        custom_size_row = ctk.CTkFrame(self.wide_custom_frame, fg_color="transparent")
        custom_size_row.pack(fill="x", pady=3)
        
        ctk.CTkLabel(custom_size_row, text="Ширина:",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=10)).pack(side="left", padx=(0, 5))
        self.wide_custom_width = ctk.CTkEntry(custom_size_row, width=70, 
                                              font=ctk.CTkFont(family=FONT_FAMILY, size=11))
        self.wide_custom_width.insert(0, "3840")
        self.wide_custom_width.pack(side="left", padx=3)
        
        ctk.CTkLabel(custom_size_row, text="Высота:",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=10)).pack(side="left", padx=(8, 5))
        self.wide_custom_height = ctk.CTkEntry(custom_size_row, width=70,
                                               font=ctk.CTkFont(family=FONT_FAMILY, size=11))
        self.wide_custom_height.insert(0, "2160")
        self.wide_custom_height.pack(side="left", padx=3)
        
        ctk.CTkLabel(self.wide_settings_frame, 
                    text="Каждое фото обрабатывается отдельно • 4K разрешение",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=9),
                    text_color=COLORS["text_secondary"]).pack(anchor="w", padx=8, pady=(3, 8))
        
        # === КНОПКА ЗАПУСКА (сохраняем ссылку для перепаковки) ===
        self.ai_generate_btn = ctk.CTkButton(scroll_frame, text="🚀 Запустить генерацию", 
                     command=self._run_ai_generation,
                     height=45, font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
                     fg_color=COLORS["success"], hover_color=COLORS["success_hover"],
                     corner_radius=GLASS_CORNER_RADIUS_SMALL)
        self.ai_generate_btn.pack(fill="x", padx=5, pady=(10, 5))
        
        # Статус и прогресс
        self.ai_status = ctk.CTkLabel(left_panel, text="", 
                                      font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                                      text_color=COLORS["text_secondary"])
        self.ai_status.pack(pady=3)
        
        self.ai_progress = ctk.CTkProgressBar(left_panel, width=300, height=4,
                                              progress_color=COLORS["primary"],
                                              fg_color=COLORS["bg_secondary"])
        self.ai_progress.pack(pady=3)
        self.ai_progress.set(0)
        
        # === ПРАВАЯ ПАНЕЛЬ - OUTPUT ===
        right_panel = ctk.CTkFrame(tab, fg_color=COLORS["bg_tertiary"], corner_radius=GLASS_CORNER_RADIUS)
        right_panel.grid(row=0, column=1, padx=(5, 10), pady=10, sticky="nsew")
        right_panel.grid_rowconfigure(0, weight=1)
        right_panel.grid_rowconfigure(1, weight=0)
        right_panel.grid_columnconfigure(0, weight=1)
        
        # Большое превью результата
        preview_frame = ctk.CTkFrame(right_panel, fg_color=COLORS["bg_secondary"], corner_radius=GLASS_CORNER_RADIUS_SMALL)
        preview_frame.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="nsew")
        
        ctk.CTkLabel(preview_frame, text="📤 Output", 
                    font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(pady=(10, 5))
        
        # Главное превью
        self.ai_result_canvas = tk.Canvas(preview_frame, bg=COLORS["bg_secondary"], 
                                          highlightthickness=0)
        self.ai_result_canvas.pack(padx=10, pady=(0, 5), fill="both", expand=True)
        self.ai_result_photo = None
        self.ai_result_images = []  # Список путей к сгенерированным изображениям
        self.ai_result_current = 0  # Текущий индекс
        self.ai_result_selected = set()  # Выбранные миниатюры
        
        # ПКМ на главном превью
        self.ai_result_canvas.bind("<Button-2>", self._on_main_preview_right_click)
        self.ai_result_canvas.bind("<Button-3>", self._on_main_preview_right_click)
        
        # Центрированный текст-заглушка
        self._show_output_placeholder()
        
        # Галерея миниатюр
        self.ai_thumbs_frame = ctk.CTkFrame(preview_frame, fg_color=COLORS["bg_tertiary"], 
                                            corner_radius=8, height=60)
        self.ai_thumbs_frame.pack(fill="x", padx=10, pady=(0, 10))
        self.ai_thumbs_frame.pack_propagate(False)
        
        self.ai_thumbs_scroll = ctk.CTkFrame(self.ai_thumbs_frame, fg_color="transparent")
        self.ai_thumbs_scroll.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.ai_thumb_photos = []  # Ссылки на фото миниатюр
        
        # Логи внизу
        log_frame = ctk.CTkFrame(right_panel, fg_color=COLORS["bg_secondary"], corner_radius=GLASS_CORNER_RADIUS_SMALL, height=100)
        log_frame.grid(row=1, column=0, padx=10, pady=(5, 10), sticky="ew")
        log_frame.grid_propagate(False)
        
        ctk.CTkLabel(log_frame, text="📋 Логи", 
                    font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(anchor="w", padx=10, pady=(5, 2))
        
        self.ai_log_text = ctk.CTkTextbox(log_frame, height=60,
                                          font=ctk.CTkFont(family="Monaco", size=9),
                                          fg_color=COLORS["bg_tertiary"],
                                          text_color=COLORS["text_secondary"])
        self.ai_log_text.pack(fill="x", padx=10, pady=(0, 8))
        self.ai_log_text.insert("1.0", "Готов к генерации...\n")
        self.ai_log_text.configure(state="disabled")
    
    def _ai_log(self, msg):
        """Добавляет сообщение в лог AI вкладки"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.ai_log_text.configure(state="normal")
        self.ai_log_text.insert("end", f"[{timestamp}] {msg}\n")
        self.ai_log_text.see("end")
        self.ai_log_text.configure(state="disabled")
    
    def _show_output_placeholder(self):
        """Показывает центрированный текст-заглушку"""
        self.ai_result_canvas.delete("all")
        self.ai_result_canvas.update_idletasks()
        w = self.ai_result_canvas.winfo_width() or 350
        h = self.ai_result_canvas.winfo_height() or 280
        self.ai_result_canvas.create_text(w//2, h//2, 
            text="Здесь появится\nрезультат генерации",
            font=(FONT_FAMILY, 14), fill=COLORS["text_secondary"],
            justify="center", anchor="center")
    
    def _show_ai_result(self, img, path=None):
        """Показывает результат генерации в большом превью"""
        # Масштабируем под размер canvas
        canvas_w = self.ai_result_canvas.winfo_width() or 350
        canvas_h = self.ai_result_canvas.winfo_height() or 280
        
        img_copy = img.copy()
        img_copy.thumbnail((canvas_w - 20, canvas_h - 20), Image.Resampling.LANCZOS)
        
        self.ai_result_photo = ImageTk.PhotoImage(img_copy)
        self.ai_result_canvas.delete("all")
        
        # Центрируем изображение
        x = canvas_w // 2
        y = canvas_h // 2
        self.ai_result_canvas.create_image(x, y, image=self.ai_result_photo, anchor="center")
        
        # Добавляем путь в список если передан
        if path and path not in self.ai_result_images:
            self.ai_result_images.append(path)
            self._update_output_gallery()
    
    def _update_output_gallery(self):
        """Обновляет галерею миниатюр результатов"""
        # Очищаем
        for w in self.ai_thumbs_scroll.winfo_children():
            w.destroy()
        self.ai_thumb_photos = []
        
        if not self.ai_result_images:
            return
        
        # Создаём миниатюры
        for i, path in enumerate(self.ai_result_images):
            try:
                img = Image.open(path)
                img.thumbnail((45, 45), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.ai_thumb_photos.append(photo)
                
                # Контейнер для миниатюры
                thumb_frame = ctk.CTkFrame(self.ai_thumbs_scroll, fg_color="transparent", 
                                          width=50, height=50)
                thumb_frame.pack(side="left", padx=2)
                thumb_frame.pack_propagate(False)
                
                # Определяем цвет рамки
                border_color = COLORS["primary"] if i == self.ai_result_current else COLORS["border"]
                selected_color = COLORS["success"] if i in self.ai_result_selected else border_color
                
                lbl = ctk.CTkLabel(thumb_frame, image=photo, text="", cursor="hand2",
                                  fg_color=selected_color, corner_radius=4)
                lbl.pack(expand=True, fill="both", padx=2, pady=2)
                lbl.bind("<Button-1>", lambda e, idx=i: self._on_thumb_click(idx, e))
                lbl.bind("<Button-2>", lambda e, idx=i: self._on_thumb_right_click(idx, e))
                lbl.bind("<Button-3>", lambda e, idx=i: self._on_thumb_right_click(idx, e))
            except:
                pass
    
    def _on_thumb_click(self, idx, event=None):
        """При клике на миниатюру - показать в главном превью"""
        # Shift+click или Cmd+click для множественного выбора
        is_multi = event and (event.state & 0x1 or event.state & 0x8)
        
        if is_multi:
            # Toggle выбора
            if idx in self.ai_result_selected:
                self.ai_result_selected.discard(idx)
            else:
                self.ai_result_selected.add(idx)
        else:
            # Одиночный клик - показать и выбрать только это
            self.ai_result_selected = {idx}
            self.ai_result_current = idx
            
            # Показать изображение
            if 0 <= idx < len(self.ai_result_images):
                try:
                    img = Image.open(self.ai_result_images[idx])
                    self._show_ai_result(img)
                except:
                    pass
        
        self._update_output_gallery()
    
    def _on_thumb_right_click(self, idx, event):
        """ПКМ на миниатюре - контекстное меню"""
        # Если кликнули на невыбранную - выбрать её
        if idx not in self.ai_result_selected:
            self.ai_result_selected = {idx}
            self._update_output_gallery()
        
        menu = tk.Menu(self, tearoff=0)
        count = len(self.ai_result_selected)
        
        menu.add_command(label=f"🎬 Отправить в раскадровку ({count})", 
                        command=self._send_selected_to_storyboard)
        menu.add_separator()
        menu.add_command(label="✅ Выбрать все", command=self._select_all_thumbs)
        menu.add_command(label="❌ Снять выделение", command=self._deselect_all_thumbs)
        
        menu.tk_popup(event.x_root, event.y_root)
    
    def _select_all_thumbs(self):
        """Выбрать все миниатюры"""
        self.ai_result_selected = set(range(len(self.ai_result_images)))
        self._update_output_gallery()
    
    def _deselect_all_thumbs(self):
        """Снять выделение со всех миниатюр"""
        self.ai_result_selected.clear()
        self._update_output_gallery()
    
    def _send_selected_to_storyboard(self):
        """Отправляет выбранные фото в раскадровку"""
        if not self.ai_result_selected:
            return
        
        # Собираем пути
        paths = [self.ai_result_images[i] for i in sorted(self.ai_result_selected) 
                if 0 <= i < len(self.ai_result_images)]
        
        if not paths:
            return
        
        # Добавляем в раскадровку
        start_x, start_y = 50, 50
        offset = 30
        
        for i, path in enumerate(paths):
            try:
                img = Image.open(path)
                self.storyboard_images.append({
                    "path": path,
                    "x": start_x + (i % 5) * 150 + offset * (i // 5),
                    "y": start_y + (i // 5) * 120,
                    "width": img.width,
                    "height": img.height
                })
            except:
                pass
        
        self._ai_log(f"Отправлено {len(paths)} фото в раскадровку")
        self.ai_result_selected.clear()
        self._update_output_gallery()
        
        # Переключаемся на раскадровку
        self.switch_tab("Раскадровка")
        self.refresh_storyboard()
    
    def _on_main_preview_right_click(self, event):
        """ПКМ на главном превью - контекстное меню"""
        if not self.ai_result_images:
            return
        
        menu = tk.Menu(self, tearoff=0)
        
        # Текущее изображение
        if 0 <= self.ai_result_current < len(self.ai_result_images):
            menu.add_command(label="🎬 Отправить текущее в раскадровку", 
                            command=lambda: self._send_current_to_storyboard())
        
        # Все изображения
        if len(self.ai_result_images) > 1:
            menu.add_command(label=f"🎬 Отправить все ({len(self.ai_result_images)}) в раскадровку", 
                            command=self._send_all_to_storyboard)
        
        menu.add_separator()
        menu.add_command(label="🗑️ Очистить галерею", command=self._clear_output_gallery)
        
        menu.tk_popup(event.x_root, event.y_root)
    
    def _send_current_to_storyboard(self):
        """Отправляет текущее изображение в раскадровку"""
        if 0 <= self.ai_result_current < len(self.ai_result_images):
            path = self.ai_result_images[self.ai_result_current]
            try:
                img = Image.open(path)
                self.storyboard_images.append({
                    "path": path,
                    "x": 50,
                    "y": 50,
                    "width": img.width,
                    "height": img.height
                })
                self._ai_log(f"Отправлено 1 фото в раскадровку")
                self.switch_tab("Раскадровка")
                self.refresh_storyboard()
            except:
                pass
    
    def _send_all_to_storyboard(self):
        """Отправляет все изображения из галереи в раскадровку"""
        self.ai_result_selected = set(range(len(self.ai_result_images)))
        self._send_selected_to_storyboard()
    
    def _clear_output_gallery(self):
        """Очищает галерею результатов"""
        self.ai_result_images = []
        self.ai_result_selected.clear()
        self.ai_result_current = 0
        self._update_output_gallery()
        self._show_output_placeholder()
        self._ai_log("Галерея очищена")
    
    def _load_wide_files(self):
        """Загрузка файлов для Wide режима"""
        files = filedialog.askopenfilenames(filetypes=[("Images", "*.jpg *.jpeg *.png *.webp")])
        if files:
            self.wide_images = list(files)
            self._update_wide_preview()
            self._ai_log(f"Wide: загружено {len(files)} фото")
    
    def _load_wide_folder(self):
        """Загрузка папки с фото для Wide режима"""
        folder = filedialog.askdirectory(title="Выберите папку с фотографиями")
        if folder:
            import glob
            image_files = []
            for ext in ['*.jpg', '*.jpeg', '*.png', '*.webp', '*.JPG', '*.JPEG', '*.PNG', '*.WEBP']:
                image_files.extend(glob.glob(os.path.join(folder, ext)))
            
            if image_files:
                self.wide_images = image_files
                self._update_wide_preview()
                self._ai_log(f"Wide: загружено {len(image_files)} фото из папки {os.path.basename(folder)}")
            else:
                messagebox.showwarning("Папка пуста", "В выбранной папке нет изображений")
    
    def _clear_wide_images(self):
        """Очистка списка изображений Wide"""
        self.wide_images = []
        self._update_wide_preview()
        self._ai_log("Wide: список очищен")
    
    def _update_wide_preview(self):
        """Обновление превью списка изображений Wide с горизонтальным скроллом"""
        # Очищаем превью
        for widget in self.wide_preview_scroll.winfo_children():
            widget.destroy()
        self.wide_preview_photos = []
        
        # Обновляем счетчик
        self.wide_count_label.configure(text=f"{len(self.wide_images)} фото")
        
        if not self.wide_images:
            ctk.CTkLabel(self.wide_preview_scroll, text="Нет фото",
                        font=ctk.CTkFont(size=10), text_color=COLORS["text_secondary"]).pack(expand=True)
            return
        
        # Показываем ВСЕ превью с крестиком для удаления (скролл позволяет)
        for i, path in enumerate(self.wide_images):
            try:
                img = Image.open(path)
                img.thumbnail((45, 45), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.wide_preview_photos.append(photo)
                
                # Контейнер для фото + крестик
                item_frame = ctk.CTkFrame(self.wide_preview_scroll, fg_color="transparent", 
                                         width=50, height=50)
                item_frame.pack(side="left", padx=1)
                item_frame.pack_propagate(False)
                
                # Фото
                lbl = ctk.CTkLabel(item_frame, image=photo, text="", cursor="hand2")
                lbl.place(relx=0.5, rely=0.5, anchor="center")
                lbl.bind("<Button-1>", lambda e, p=path: self._show_enlarged_image(p))
                lbl.bind("<MouseWheel>", lambda e: self.wide_preview_canvas.xview_scroll(int(-1 * (e.delta / 120)), "units"))
                
                # Маленький крестик в правом верхнем углу
                close_btn = ctk.CTkLabel(item_frame, text="×", width=12, height=12,
                                        font=ctk.CTkFont(size=9, weight="bold"),
                                        fg_color=COLORS["danger"], text_color="white",
                                        corner_radius=6, cursor="hand2")
                close_btn.place(relx=1.0, rely=0, anchor="ne", x=0, y=0)
                close_btn.bind("<Button-1>", lambda e, p=path: self._remove_wide_image(p))
            except:
                pass
    
    def _remove_wide_image(self, path):
        """Удаляет одно фото из списка Wide"""
        if path in self.wide_images:
            self.wide_images.remove(path)
            self._update_wide_preview()
            self._ai_log(f"Wide: удалено фото, осталось {len(self.wide_images)}")
    
    def _on_wide_ratio_change(self, value=None):
        """Обработчик изменения соотношения для Wide"""
        ratio = value if value else self.wide_ratio_var.get()
        self.wide_custom_frame.pack_forget()
        self._ai_log(f"Wide: выбрано соотношение {ratio}")
    
    def load_ai_main_image(self):
        # Проверяем режим - для Wide можно выбрать несколько фото
        model = self.ai_model_var.get()
        
        if model == "wide":
            # Множественный выбор для Wide
            files = filedialog.askopenfilenames(filetypes=[("Images", "*.jpg *.jpeg *.png *.webp")])
            if files:
                self.ai_main_image = list(files)  # Список файлов
                self.ai_main_label.configure(text=f"📷 {len(files)} фото")
                self.wide_folder_label.configure(text=f"{len(files)} фото выбрано")
                # Показываем превью первого
                try:
                    img = Image.open(files[0])
                    img.thumbnail((280, 160), Image.Resampling.LANCZOS)
                    self.ai_main_photo = ImageTk.PhotoImage(img)
                    self.ai_main_preview.configure(image=self.ai_main_photo, text="")
                    # Показываем кнопку удаления
                    self.ai_main_delete_btn.place(relx=1.0, rely=0.0, x=-5, y=5, anchor="ne")
                except:
                    pass
                self._ai_log(f"Загружено {len(files)} фото для пакетной обработки")
        else:
            # Одиночный выбор для остальных моделей
            file = filedialog.askopenfilename(filetypes=[("Images", "*.jpg *.jpeg *.png *.webp")])
            if file:
                self.ai_main_image = file
                self.ai_main_label.configure(text=f"📷 {os.path.basename(file)[:15]}")
                # Показываем большое превью
                try:
                    img = Image.open(file)
                    img.thumbnail((280, 160), Image.Resampling.LANCZOS)
                    self.ai_main_photo = ImageTk.PhotoImage(img)
                    self.ai_main_preview.configure(image=self.ai_main_photo, text="")
                    # Показываем кнопку удаления
                    self.ai_main_delete_btn.place(relx=1.0, rely=0.0, x=-5, y=5, anchor="ne")
                except:
                    pass
    
    def load_ai_references(self):
        files = filedialog.askopenfilenames(filetypes=[("Images", "*.jpg *.jpeg *.png *.webp")])
        if files:
            self.ai_references = list(files)
            self.ai_ref_label.configure(text=f"📷 {len(self.ai_references)} шт")
            self._update_ref_preview()
    
    def _update_ref_preview(self):
        """Обновляет превью референсов"""
        # Очищаем старые превью
        for widget in self.ai_ref_preview_frame.winfo_children():
            widget.destroy()
        self.ai_ref_photos = []
        
        # Показываем превью (до 5 штук)
        for i, path in enumerate(self.ai_references[:5]):
            try:
                # Контейнер для превью с крестиком
                ref_container = ctk.CTkFrame(self.ai_ref_preview_frame, fg_color="transparent")
                ref_container.pack(side="left", padx=2)
                
                img = Image.open(path)
                img.thumbnail((60, 50), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.ai_ref_photos.append(photo)
                
                # Превью с возможностью клика
                lbl = ctk.CTkLabel(ref_container, image=photo, text="", cursor="hand2")
                lbl.pack()
                lbl.bind("<Button-1>", lambda e, p=path: self._show_enlarged_image(p))
                
                # Крестик для удаления
                del_btn = ctk.CTkButton(ref_container, text="✕", width=20, height=20,
                                       font=ctk.CTkFont(size=10, weight="bold"),
                                       fg_color="#ff4444", hover_color="#cc0000",
                                       command=lambda idx=i: self._delete_reference(idx))
                del_btn.place(relx=1.0, rely=0.0, x=-2, y=-2, anchor="ne")
            except:
                pass
        
        if len(self.ai_references) > 5:
            ctk.CTkLabel(self.ai_ref_preview_frame, text=f"+{len(self.ai_references)-5}",
                        font=ctk.CTkFont(size=10), text_color=COLORS["text_secondary"]).pack(side="left", padx=2)
    
    def _show_enlarged_image(self, image_path):
        """Показывает увеличенное изображение в отдельном окне"""
        if not image_path:
            return
        
        # Если это список (для Wide), показываем первое
        if isinstance(image_path, list):
            if not image_path:
                return
            image_path = image_path[0]
        
        try:
            # Создаем новое окно
            preview_window = ctk.CTkToplevel(self)
            preview_window.title("Просмотр изображения")
            preview_window.geometry("800x600")
            
            # Загружаем изображение
            img = Image.open(image_path)
            
            # Масштабируем под размер окна
            max_w, max_h = 780, 550
            img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
            
            photo = ImageTk.PhotoImage(img)
            
            # Показываем изображение
            label = ctk.CTkLabel(preview_window, image=photo, text="")
            label.image = photo  # Сохраняем ссылку
            label.pack(expand=True, padx=10, pady=10)
            
            # Информация о файле
            filename = os.path.basename(image_path)
            orig_img = Image.open(image_path)
            info_text = f"{filename} • {orig_img.size[0]}×{orig_img.size[1]}px"
            
            ctk.CTkLabel(preview_window, text=info_text,
                        font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                        text_color=COLORS["text_secondary"]).pack(pady=(0, 10))
            
            # Кнопка закрытия
            ctk.CTkButton(preview_window, text="Закрыть", 
                         command=preview_window.destroy,
                         width=100, height=32,
                         fg_color=COLORS["primary"],
                         hover_color=COLORS["primary_hover"]).pack(pady=(0, 10))
            
            # Центрируем окно
            preview_window.update_idletasks()
            x = (preview_window.winfo_screenwidth() // 2) - (800 // 2)
            y = (preview_window.winfo_screenheight() // 2) - (600 // 2)
            preview_window.geometry(f"800x600+{x}+{y}")
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось открыть изображение:\n{e}")
    
    def _delete_main_image(self):
        """Удаляет главное фото"""
        self.ai_main_image = None
        self.ai_main_photo = None
        self.ai_main_preview.configure(image="", text="📷 Превью")
        self.ai_main_label.configure(text="Не выбрано")
        self.ai_main_delete_btn.place_forget()
        self._ai_log("Главное фото удалено")
    
    def _delete_reference(self, index):
        """Удаляет референс по индексу"""
        if 0 <= index < len(self.ai_references):
            deleted = self.ai_references.pop(index)
            self._ai_log(f"Удален референс: {os.path.basename(deleted)}")
            self.ai_ref_label.configure(text=f"📷 {len(self.ai_references)} шт" if self.ai_references else "Не выбрано")
            self._update_ref_preview()
    
    def apply_ai_preset(self, preset):
        if preset == "как исходник":
            # Используем размер исходного изображения
            if self.ai_main_image:
                try:
                    img = Image.open(self.ai_main_image)
                    orig_w, orig_h = img.size
                    # Масштабируем до разумного размера (макс 2048 по большей стороне)
                    max_side = 2048
                    if orig_w > orig_h:
                        w = min(orig_w, max_side)
                        h = int(w * orig_h / orig_w)
                    else:
                        h = min(orig_h, max_side)
                        w = int(h * orig_w / orig_h)
                    self.ai_width.delete(0, "end")
                    self.ai_width.insert(0, str(w))
                    self.ai_height.delete(0, "end")
                    self.ai_height.insert(0, str(h))
                    self._ai_log(f"Размер как исходник: {w}x{h} (оригинал {orig_w}x{orig_h})")
                except Exception as e:
                    self._ai_log(f"Ошибка определения размера: {e}")
            else:
                self._ai_log("Сначала загрузите главное фото")
            return
        
        ratios = {
            "16:9": (1536, 864), "9:16": (864, 1536), 
            "4:3": (1536, 1152), "3:4": (1152, 1536),
            "1:1": (1024, 1024), "3:2": (1536, 1024), "2:3": (1024, 1536)
        }
        w, h = ratios.get(preset, (1536, 1024))
        self.ai_width.delete(0, "end")
        self.ai_width.insert(0, str(w))
        self.ai_height.delete(0, "end")
        self.ai_height.insert(0, str(h))
        # Переключаем на режим соотношения
        self.ai_size_mode.set("ratio")
    
    def _update_ai_size_mode(self):
        """Обновляет состояние полей при смене режима размера"""
        pass  # Поля всегда активны, режим определяет что использовать при генерации
    
    def _on_model_change(self):
        """Обработчик смены модели"""
        model = self.ai_model_var.get()
        
        # Скрываем ВСЕ динамические элементы и кнопку
        self.ai_prompt_frame.pack_forget()
        self.ai_main_frame.pack_forget()
        self.ai_ref_frame.pack_forget()
        self.ai_size_frame.pack_forget()
        self.qwen_settings_frame.pack_forget()
        self.wide_settings_frame.pack_forget()
        self.ai_generate_btn.pack_forget()
        
        # Показываем элементы в правильном порядке в зависимости от модели
        if model == "qwen_angles":
            # QWEN: только главное фото + настройки камеры
            self.ai_main_frame.pack(fill="x", padx=5, pady=5)
            self.qwen_settings_frame.pack(fill="x", padx=5, pady=5)
            self._ai_log("🎥 Модель QWEN Angles: управление углом камеры")
            
        elif model == "wide":
            # Wide: только настройки Wide (у него свой выбор фото)
            self.wide_settings_frame.pack(fill="x", padx=5, pady=5)
            self._ai_log("📐 Модель Расширить: горизонтальное расширение изображения")
            
        else:
            # Seedream, NanoBanana и другие: полный набор элементов
            self.ai_prompt_frame.pack(fill="x", padx=0, pady=0)
            self.ai_main_frame.pack(fill="x", padx=5, pady=5)
            self.ai_ref_frame.pack(fill="x", padx=5, pady=5)
            self.ai_size_frame.pack(fill="x", padx=5, pady=5)
            
            if model == "seedream":
                self._ai_log("🎨 Модель Seedream 4.5: редактирование с референсами")
            elif model == "nana":
                self._ai_log("✨ Модель NanoBanana Pro: быстрая генерация 2K")
        
        # Кнопка всегда в самом низу после всех блоков
        self.ai_generate_btn.pack(fill="x", padx=5, pady=(10, 5))
    
    def _detect_aspect_ratio(self):
        """Определяет соотношение сторон загруженного фото"""
        file = filedialog.askopenfilename(filetypes=[("Images", "*.jpg *.jpeg *.png *.webp")])
        if not file:
            return
        
        try:
            img = Image.open(file)
            w, h = img.size
            
            # Алгоритм определения соотношения с погрешностью
            ratio = w / h
            
            # Стандартные соотношения сторон
            standard_ratios = {
                (1, 1): 1.0,
                (4, 3): 4/3,
                (3, 4): 3/4,
                (3, 2): 3/2,
                (2, 3): 2/3,
                (16, 9): 16/9,
                (9, 16): 9/16,
                (5, 4): 5/4,
                (4, 5): 4/5,
                (21, 9): 21/9,
                (9, 21): 9/21,
                (16, 10): 16/10,
                (10, 16): 10/16,
            }
            
            # Находим ближайшее стандартное соотношение (погрешность 5%)
            best_match = None
            min_diff = float('inf')
            
            for (a, b), std_ratio in standard_ratios.items():
                diff = abs(ratio - std_ratio) / std_ratio
                if diff < min_diff:
                    min_diff = diff
                    best_match = (a, b)
            
            if min_diff <= 0.05:  # 5% погрешность
                result = f"{best_match[0]}:{best_match[1]}"
            else:
                # Упрощаем дробь для нестандартных соотношений
                from math import gcd
                g = gcd(w, h)
                simplified_w, simplified_h = w // g, h // g
                # Если слишком большие числа, округляем
                if simplified_w > 100 or simplified_h > 100:
                    result = f"~{ratio:.2f}:1"
                else:
                    result = f"{simplified_w}:{simplified_h}"
            
            self.ai_detected_ratio.configure(text=f"{result} ({w}×{h})")
            self._ai_log(f"Определено соотношение: {result} для {os.path.basename(file)}")
            
        except Exception as e:
            self.ai_detected_ratio.configure(text=f"Ошибка: {str(e)[:20]}")
    
    def _init_3d_cube(self):
        """Инициализация 3D куба для визуализации углов"""
        import math
        self.cube_vertices = [
            [-1, -1, -1],  # 0: задний нижний левый
            [ 1, -1, -1],  # 1: задний нижний правый
            [ 1,  1, -1],  # 2: задний верхний правый
            [-1,  1, -1],  # 3: задний верхний левый
            [-1, -1,  1],  # 4: передний нижний левый
            [ 1, -1,  1],  # 5: передний нижний правый
            [ 1,  1,  1],  # 6: передний верхний правый
            [-1,  1,  1],  # 7: передний верхний левый
        ]
        # Грани с правильным порядком вершин для backface culling
        self.cube_faces = [
            ([0, 1, 2, 3], "#4a4a6a"),  # задняя (z=-1)
            ([7, 6, 5, 4], "#6a6a8a"),  # передняя (z=+1)
            ([4, 5, 1, 0], "#5a5a7a"),  # нижняя (y=-1)
            ([3, 2, 6, 7], "#7a7a9a"),  # верхняя (y=+1)
            ([4, 0, 3, 7], "#5a6a7a"),  # левая (x=-1)
            ([1, 5, 6, 2], "#6a7a8a"),  # правая (x=+1)
        ]
        self.cube_mouse_x = 0
        self.cube_mouse_y = 0
        self.cube_angle_x = 0.3
        self.cube_angle_y = 0.5
        self.cube_angle_z = 0.0
    
    def _rotate_point(self, point, rx, ry, rz):
        """Поворот точки в 3D пространстве с правильными матрицами вращения"""
        import math
        x, y, z = point
        
        # Поворот вокруг X
        cos_x, sin_x = math.cos(rx), math.sin(rx)
        y1 = y * cos_x - z * sin_x
        z1 = y * sin_x + z * cos_x
        y, z = y1, z1
        
        # Поворот вокруг Y
        cos_y, sin_y = math.cos(ry), math.sin(ry)
        x1 = x * cos_y + z * sin_y
        z1 = -x * sin_y + z * cos_y
        x, z = x1, z1
        
        # Поворот вокруг Z
        cos_z, sin_z = math.cos(rz), math.sin(rz)
        x1 = x * cos_z - y * sin_z
        y1 = x * sin_z + y * cos_z
        x, y = x1, y1
        
        return [x, y, z]
    
    def _project_point(self, point, scale=40, offset_x=75, offset_y=75):
        """Ортографическая проекция 3D точки на 2D - без деформации"""
        x, y, z = point
        # Ортографическая проекция - идеально ровный куб
        px = x * scale + offset_x
        py = -y * scale + offset_y
        return (px, py, z)
    
    def _cross_product_z(self, p1, p2, p3):
        """Вычисляет Z-компоненту векторного произведения для backface culling"""
        v1x = p2[0] - p1[0]
        v1y = p2[1] - p1[1]
        v2x = p3[0] - p1[0]
        v2y = p3[1] - p1[1]
        return v1x * v2y - v1y * v2x
    
    def _draw_3d_cube(self):
        """Отрисовка 3D куба с backface culling"""
        import math
        if not hasattr(self, 'qwen_cube_canvas'):
            return
        canvas = self.qwen_cube_canvas
        canvas.delete("all")
        
        # Инициализируем углы куба если их нет
        if not hasattr(self, 'cube_angle_x'):
            self.cube_angle_x = 0.3
            self.cube_angle_y = 0.5
            self.cube_angle_z = 0
        
        # Получаем параметры из слайдеров
        rotate_deg = self.qwen_rotate.get()
        vertical = self.qwen_vertical.get()
        forward = self.qwen_forward.get()
        
        # Используем накопительные углы
        rx = self.cube_angle_x
        ry = self.cube_angle_y
        rz = self.cube_angle_z
        
        # Масштаб
        scale = 30 + forward * 3
        
        # Вращаем все вершины
        rotated = []
        for v in self.cube_vertices:
            rv = self._rotate_point(v, rx, ry, rz)
            rotated.append(rv)
        
        # Проецируем на 2D
        projected = [self._project_point(v, scale) for v in rotated]
        
        # Собираем видимые грани с backface culling
        visible_faces = []
        for indices, color in self.cube_faces:
            p1 = projected[indices[0]]
            p2 = projected[indices[1]]
            p3 = projected[indices[2]]
            
            # Проверяем видимость грани
            if self._cross_product_z(p1, p2, p3) >= 0:
                avg_z = sum(rotated[i][2] for i in indices) / len(indices)
                visible_faces.append((avg_z, indices, color))
        
        # Сортируем по глубине
        visible_faces.sort(key=lambda x: x[0])
        
        # Рисуем только видимые грани
        for avg_z, indices, color in visible_faces:
            points = [projected[i][:2] for i in indices]
            flat_points = [coord for p in points for coord in p]
            canvas.create_polygon(flat_points, fill=color, outline="#888888", width=2)
        
        # Рисуем оси
        origin = self._project_point([0, 0, 0], scale)
        axis_len = 1.5
        
        # X ось (красная) - право
        x_end = self._rotate_point([axis_len, 0, 0], rx, ry, 0)
        x_proj = self._project_point(x_end, scale)
        canvas.create_line(origin[0], origin[1], x_proj[0], x_proj[1], fill="#ff5555", width=2, arrow="last")
        
        # Y ось (зеленая) - верх
        y_end = self._rotate_point([0, axis_len, 0], rx, ry, 0)
        y_proj = self._project_point(y_end, scale)
        canvas.create_line(origin[0], origin[1], y_proj[0], y_proj[1], fill="#55ff55", width=2, arrow="last")
        
        # Z ось (синяя) - вперед
        z_end = self._rotate_point([0, 0, axis_len], rx, ry, 0)
        z_proj = self._project_point(z_end, scale)
        canvas.create_line(origin[0], origin[1], z_proj[0], z_proj[1], fill="#5555ff", width=2, arrow="last")
    
    def _cube_mouse_press(self, event):
        """Запоминаем позицию мыши при нажатии"""
        self.cube_mouse_x = event.x
        self.cube_mouse_y = event.y
    
    def _cube_mouse_drag(self, event):
        """Обработка перетаскивания куба мышью"""
        dx = event.x - self.cube_mouse_x
        dy = event.y - self.cube_mouse_y
        
        # Инициализируем углы куба если их нет
        if not hasattr(self, 'cube_angle_x'):
            self.cube_angle_x = 0.3  # начальный наклон
            self.cube_angle_y = 0.5
            self.cube_angle_z = 0
        
        # Вращаем куб по осям X и Y при перетаскивании
        self.cube_angle_y += dx * 0.01  # горизонтальное движение -> вращение вокруг Y
        self.cube_angle_x += dy * 0.01  # вертикальное движение -> вращение вокруг X
        
        # Обновляем слайдеры на основе углов куба
        # Горизонтальное вращение -> поворот камеры
        rotate_deg = (self.cube_angle_y * 180 / 3.14159) % 360
        if rotate_deg > 180:
            rotate_deg -= 360
        rotate_deg = max(-90, min(90, rotate_deg))
        self.qwen_rotate.set(rotate_deg)
        self.qwen_rotate_label.configure(text=f"{int(rotate_deg)}°")
        
        # Вертикальное вращение -> вертикальный угол
        vertical = self.cube_angle_x / (3.14159 / 4)  # нормализуем к -1..1
        vertical = max(-1, min(1, vertical))
        self.qwen_vertical.set(vertical)
        self.qwen_vertical_label.configure(text=f"{vertical:.1f}")
        
        self.cube_mouse_x = event.x
        self.cube_mouse_y = event.y
        
        self._draw_3d_cube()
    
    def _on_qwen_slider_change(self, value):
        """Обновление куба при изменении слайдеров"""
        import math
        # Обновляем лейблы
        self.qwen_rotate_label.configure(text=f"{int(self.qwen_rotate.get())}°")
        self.qwen_forward_label.configure(text=f"{self.qwen_forward.get():.1f}")
        self.qwen_vertical_label.configure(text=f"{self.qwen_vertical.get():.1f}")
        
        # Синхронизируем углы куба со слайдерами
        if not hasattr(self, 'cube_angle_x'):
            self.cube_angle_x = 0.3
            self.cube_angle_y = 0.5
            self.cube_angle_z = 0
        
        # Обновляем углы куба на основе слайдеров
        self.cube_angle_y = math.radians(self.qwen_rotate.get())
        self.cube_angle_x = self.qwen_vertical.get() * math.pi / 4
        
        # Перерисовываем куб
        self._draw_3d_cube()
    
    def _open_kling_workspace(self):
        """Открывает Kling Workspace на VDS сервере"""
        import socket
        import urllib.request
        
        def check_server_available(host, port, timeout=3):
            """Проверяет доступность сервера"""
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                result = sock.connect_ex((host, port))
                sock.close()
                return result == 0
            except:
                return False
        
        def check_http_available(url, timeout=5):
            """Проверяет доступность HTTP сервиса"""
            try:
                req = urllib.request.Request(url, method='HEAD')
                urllib.request.urlopen(req, timeout=timeout)
                return True
            except:
                return False
        
        logger.info("🎬 Запуск Kling Workspace...")
        self._ai_log("🎬 Проверка Kling Workspace сервера...")
        
        # Проверяем доступность VDS сервера
        self._ai_log(f"🔍 Проверка сервера {KLING_VDS_HOST}...")
        
        novnc_available = check_server_available(KLING_VDS_HOST, KLING_VDS_NOVNC_PORT)
        files_available = check_server_available(KLING_VDS_HOST, KLING_VDS_FILES_PORT)
        
        if novnc_available:
            logger.info(f"✅ VDS сервер доступен: {KLING_WORKSPACE_URL}")
            self._ai_log(f"✅ Сервер доступен!")
            self._ai_log(f"🖥️ Kling Workspace: {KLING_WORKSPACE_URL}")
            
            # Открываем Session Manager (с авторизацией и очередью)
            webbrowser.open(KLING_WORKSPACE_URL)
            
            self._ai_log("✅ Kling Workspace открыт!")
            self._ai_log("🔐 Войдите с логином/паролем")
            self._ai_log("⏳ Если занято - встанете в очередь")
            
            # Показываем информационное окно
            messagebox.showinfo(
                "🎬 Kling Workspace",
                f"Kling Workspace открыт в браузере!\n\n"
                f"🔐 Войдите с логином и паролем\n"
                f"⏳ Если сервер занят - встанете в очередь\n\n"
                f"📁 Файлы: {KLING_FILES_URL}\n\n"
                f"Админ: admin / admin123"
            )
        else:
            # VDS сервер недоступен - пробуем локальный вариант
            logger.warning(f"VDS сервер недоступен: {KLING_VDS_HOST}")
            self._ai_log(f"⚠️ VDS сервер недоступен")
            
            if KLING_WORKSPACE_AVAILABLE:
                # Запускаем локальный браузер
                self._ai_log("🔄 Запуск локального браузера...")
                try:
                    import sys
                    browser_script = os.path.join(os.path.dirname(__file__), 
                                                  "kling_workspace", "browser_launcher.py")
                    
                    if sys.platform == "darwin":
                        subprocess.Popen([
                            "osascript", "-e",
                            f'tell application "Terminal" to do script "python3 {browser_script}"'
                        ])
                    else:
                        subprocess.Popen([sys.executable, browser_script])
                    
                    self._ai_log("✅ Локальный браузер запущен!")
                    self._ai_log(f"📁 Файлы: {KLING_DOWNLOADS_DIR}")
                except Exception as e:
                    logger.error(f"Ошибка запуска локального браузера: {e}")
                    self._ai_log(f"❌ Ошибка: {e}")
                    webbrowser.open("https://klingai.com")
            else:
                # Fallback - открываем напрямую
                self._ai_log("🌐 Открываю Kling AI напрямую...")
                webbrowser.open("https://klingai.com")
                messagebox.showwarning(
                    "Kling Workspace",
                    f"VDS сервер недоступен ({KLING_VDS_HOST}).\n\n"
                    f"Kling AI открыт напрямую в браузере.\n"
                    f"Скачивания будут сохраняться в папку загрузок браузера."
                )
    
    def _open_kling_files(self):
        """Открывает страницу скачивания файлов Kling"""
        logger.info(f"📁 Открытие файлов Kling: {KLING_FILES_URL}")
        self._ai_log(f"📁 Открытие файлов: {KLING_FILES_URL}")
        webbrowser.open(KLING_FILES_URL)
    
    def _run_ai_generation(self):
        """Запускает генерацию с выбранной моделью"""
        # Проверка разрешения на использование AI
        try:
            from license_manager import license_manager
            if not license_manager.is_ai_enabled():
                messagebox.showwarning("Доступ запрещён", "У вас нет доступа к нейросетям.\nОбратитесь к администратору.")
                return
        except:
            pass
        
        model = self.ai_model_var.get()
        
        # Для Wide режима проверяем wide_images, для остальных - ai_main_image
        if model == "wide":
            if not hasattr(self, 'wide_images') or not self.wide_images:
                messagebox.showwarning("Ошибка", "Выберите фото для расширения!")
                return
        else:
            if not self.ai_main_image:
                messagebox.showwarning("Ошибка", "Загрузите главное фото!")
                return
        
        Thread(target=lambda: self._run_generation(model), daemon=True).start()
    
    def generate_seedream(self):
        if not self.ai_main_image:
            messagebox.showwarning("Ошибка", "Загрузите главное фото!")
            return
        Thread(target=lambda: self._run_generation("seedream"), daemon=True).start()
    
    def generate_nana(self):
        if not self.ai_main_image:
            messagebox.showwarning("Ошибка", "Загрузите главное фото!")
            return
        Thread(target=lambda: self._run_generation("nana"), daemon=True).start()
    
    def _run_generation(self, model_type):
        import datetime
        import time
        log_file = os.path.join(self.output_folder, "ai_generation.log")
        
        def log(msg):
            """Логирует в файл, консоль и UI"""
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(log_file, "a") as f:
                f.write(f"[{timestamp}] {msg}\n")
            print(f"[LOG] {msg}")
            # Обновляем UI из основного потока
            self.after(0, lambda: self._ai_log(msg))
        
        def update_status(text):
            self.after(0, lambda: self.ai_status.configure(text=text))
        
        def update_progress(val):
            self.after(0, lambda: self.ai_progress.set(val))
        
        def upload_with_retry(file_data, content_type="image/jpeg", max_retries=3):
            """Загружает файл в FAL с повторными попытками"""
            for attempt in range(max_retries):
                try:
                    log(f"Попытка загрузки {attempt + 1}/{max_retries}...")
                    url = fal_client.upload(file_data, content_type)
                    log(f"✅ Загружено успешно")
                    return url
                except Exception as e:
                    log(f"⚠️ Ошибка загрузки (попытка {attempt + 1}): {str(e)}")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt  # Экспоненциальная задержка: 1, 2, 4 сек
                        log(f"Повтор через {wait_time} сек...")
                        time.sleep(wait_time)
                    else:
                        raise Exception(f"Не удалось загрузить файл после {max_retries} попыток: {str(e)}")
        
        update_status(f"⏳ Генерация через {model_type}...")
        update_progress(0.1)
        log(f"=== Начало генерации: {model_type} ===")
        
        try:
            prompt = self.ai_prompt.get("1.0", "end").strip()
            w = int(self.ai_width.get())
            h = int(self.ai_height.get())
            
            if not prompt:
                prompt = "high quality photo"
                log("Промпт пустой, использую default")
            
            log(f"Промпт: {prompt[:100]}...")
            log(f"Размер: {w}x{h}")
            
            # Загружаем изображения
            main_images = []
            main_url = None
            
            if model_type == "wide":
                # Wide использует свой список изображений
                if not hasattr(self, 'wide_images') or not self.wide_images:
                    raise ValueError("Выберите фото для расширения!")
                update_status("📤 Загрузка фотографий...")
                log(f"Wide: загружаю {len(self.wide_images)} фотографий")
                for i, img_path in enumerate(self.wide_images):
                    # Загружаем через байты, чтобы избежать проблем с русскими именами файлов
                    with open(img_path, 'rb') as f:
                        url = upload_with_retry(f.read(), "image/jpeg")
                    main_images.append((img_path, url))
                    log(f"  ✅ {i+1}/{len(self.wide_images)}: {os.path.basename(img_path)}")
                main_url = main_images[0][1] if main_images else None
            elif isinstance(self.ai_main_image, list):
                # Множественные фото (для совместимости)
                update_status("📤 Загрузка фотографий...")
                log(f"Загружаю {len(self.ai_main_image)} фотографий")
                for i, img_path in enumerate(self.ai_main_image):
                    # Загружаем через байты, чтобы избежать проблем с русскими именами файлов
                    with open(img_path, 'rb') as f:
                        url = upload_with_retry(f.read(), "image/jpeg")
                    main_images.append((img_path, url))
                    log(f"  ✅ {i+1}/{len(self.ai_main_image)}: {os.path.basename(img_path)}")
                main_url = main_images[0][1]
            else:
                # Одно фото
                if not self.ai_main_image:
                    raise ValueError("Загрузите главное фото!")
                update_status("📤 Загрузка главного фото...")
                log(f"Загружаю: {os.path.basename(self.ai_main_image)}")
                # Загружаем через байты, чтобы избежать проблем с русскими именами файлов
                with open(self.ai_main_image, 'rb') as f:
                    main_url = upload_with_retry(f.read(), "image/jpeg")
                main_images = [(self.ai_main_image, main_url)]
                log(f"✅ Фото загружено в FAL")
            update_progress(0.3)
            
            # Загружаем референсы если есть
            ref_urls = []
            if self.ai_references:
                update_status("📤 Загрузка референсов...")
                log(f"Загружаю {len(self.ai_references)} референсов")
                for ref_path in self.ai_references:
                    # Загружаем через байты, чтобы избежать проблем с русскими именами файлов
                    with open(ref_path, 'rb') as f:
                        ref_url = upload_with_retry(f.read(), "image/jpeg")
                    ref_urls.append(ref_url)
                    log(f"  ✅ {os.path.basename(ref_path)}")
            update_progress(0.5)
            
            # Определяем подпапку для сохранения
            subfolder = "AI"  # по умолчанию
            
            if model_type == "seedream":
                # Seedream 4.5/Edit (ByteDance)
                model_id = "fal-ai/bytedance/seedream/v4.5/edit"
                update_status("🎨 Генерация Seedream 4.5...")
                log(f"Модель: {model_id}")
                subfolder = "AI"
                
                # Собираем все image_urls (главное + референсы)
                all_urls = [main_url] + ref_urls
                
                params = {
                    "prompt": prompt,
                    "image_urls": all_urls,
                    "image_size": {"width": w, "height": h},
                    "num_images": 1,
                    "enable_safety_checker": False
                }
                log(f"Отправляю {len(all_urls)} изображений...")
                
                # Используем subscribe для длительных генераций
                result = fal_client.subscribe(model_id, arguments=params, with_logs=True)
                log(f"✅ Ответ получен от FAL")
                
            elif model_type == "qwen_angles":
                # QWEN Angles - контроль камеры
                model_id = "fal-ai/qwen-image-edit-2509-lora-gallery/multiple-angles"
                update_status("🎥 Генерация QWEN Angles...")
                log(f"Модель: {model_id}")
                subfolder = "Angles"
                
                # Получаем параметры камеры из слайдеров
                rotate = self.qwen_rotate.get()
                forward = self.qwen_forward.get()
                vertical = self.qwen_vertical.get()
                
                log(f"=== QWEN ANGLES DEBUG ===")
                log(f"Параметры слайдеров:")
                log(f"  - rotate_right_left: {rotate}° (диапазон -90..+90)")
                log(f"  - move_forward: {forward} (диапазон -1..+1)")
                log(f"  - vertical_angle: {vertical} (диапазон -1..+1)")
                log(f"Углы куба (для визуализации):")
                log(f"  - cube_angle_x: {self.cube_angle_x:.3f} rad")
                log(f"  - cube_angle_y: {self.cube_angle_y:.3f} rad")
                log(f"  - cube_angle_z: {self.cube_angle_z:.3f} rad")
                
                params = {
                    "image_urls": [main_url],
                    "rotate_right_left": rotate,
                    "move_forward": forward,
                    "vertical_angle": vertical,
                    "num_images": 1,
                    "enable_safety_checker": False,
                    "output_format": "jpeg"
                }
                
                log(f"Отправляю запрос с параметрами: {params}")
                result = fal_client.subscribe(model_id, arguments=params, with_logs=True)
                log(f"✅ Ответ получен от FAL")
                log(f"=== END QWEN DEBUG ===")
            
            elif model_type == "wide":
                # Расширить - пакетная обработка нескольких фото
                # Выбор модели для Wide
                wide_model = self.wide_model_var.get()
                if wide_model == "nana":
                    model_id = "fal-ai/nano-banana-pro/edit"
                    log(f"Модель: NanoBanana Pro")
                else:
                    model_id = "fal-ai/bytedance/seedream/v4.5/edit"
                    log(f"Модель: Seedream 4.5")
                
                subfolder = "Wide"
                
                # Получаем выбранное соотношение
                wide_ratio = self.wide_ratio_var.get()
                
                if wide_ratio == "Кастом":
                    # Кастомный размер
                    try:
                        w = int(self.wide_custom_width.get())
                        h = int(self.wide_custom_height.get())
                        log(f"Кастомный размер: {w}x{h}")
                    except:
                        w, h = 3840, 2160 if wide_model != "nana" else 2560, 1440
                        log(f"Ошибка чтения кастомного размера, использую 16:9")
                else:
                    # Предустановленные соотношения - разные для Seedream (4K) и NanoBanana (2K)
                    if wide_model == "nana":
                        # NanoBanana Pro - 2K разрешение
                        wide_sizes = {
                            "3:2": (2560, 1707),
                            "4:3": (2560, 1920),
                            "16:9": (2560, 1440)
                        }
                    else:
                        # Seedream - 4K разрешение
                        wide_sizes = {
                            "3:2": (3840, 2560),
                            "4:3": (3840, 2880),
                            "16:9": (3840, 2160)
                        }
                    w, h = wide_sizes.get(wide_ratio, (2560, 1440) if wide_model == "nana" else (3840, 2160))
                
                log(f"Соотношение: {wide_ratio}, размер: {w}x{h} ({'2K' if wide_model == 'nana' else '4K'})")
                log(f"Пакетная обработка: {len(main_images)} фото")
                
                # Вычисляем aspect_ratio для NanoBanana
                ratio = w / h
                allowed_ratios = [
                    ("21:9", 21/9), ("16:9", 16/9), ("3:2", 3/2), ("4:3", 4/3),
                    ("5:4", 5/4), ("1:1", 1/1), ("4:5", 4/5), ("3:4", 3/4),
                    ("2:3", 2/3), ("9:16", 9/16)
                ]
                aspect_ratio = min(allowed_ratios, key=lambda x: abs(x[1] - ratio))[0]
                
                # Обрабатываем каждое фото ОТДЕЛЬНЫМ запросом
                all_results = []
                for idx, (img_path, img_url) in enumerate(main_images):
                    update_status(f"📐 Расширение {idx+1}/{len(main_images)}...")
                    log(f"--- Обработка {idx+1}/{len(main_images)}: {os.path.basename(img_path)} ---")
                    
                    if wide_model == "nana":
                        # NanoBanana Pro параметры
                        params = {
                            "prompt": "Make same image but wide",
                            "image_urls": [img_url],
                            "aspect_ratio": aspect_ratio,
                            "output_format": "jpeg"
                        }
                    else:
                        # Seedream параметры
                        params = {
                            "prompt": "Make same image but wide",
                            "image_urls": [img_url],
                            "image_size": {"width": w, "height": h},
                            "num_images": 1,
                            "enable_safety_checker": False
                        }
                    
                    try:
                        result = fal_client.subscribe(model_id, arguments=params, with_logs=True)
                        all_results.append((img_path, result))
                        log(f"✅ Готово {idx+1}/{len(main_images)}")
                        update_progress(0.5 + (0.3 * (idx + 1) / len(main_images)))
                    except Exception as e:
                        log(f"❌ Ошибка при обработке {os.path.basename(img_path)}: {e}")
                        all_results.append((img_path, None))
                
                # Используем последний результат для отображения
                result = all_results[-1][1] if all_results else None
                log(f"✅ Пакетная обработка завершена: {len(all_results)} фото")
                
            elif model_type == "nana":
                # Nano Banana Pro Edit - image-to-image редактирование
                model_id = "fal-ai/nano-banana-pro/edit"
                update_status("✨ Генерация Nano Banana Pro Edit...")
                log(f"Модель: {model_id}")
                subfolder = "AI"
                
                # Вычисляем ближайший допустимый aspect_ratio
                ratio = w / h
                allowed_ratios = [
                    ("21:9", 21/9), ("16:9", 16/9), ("3:2", 3/2), ("4:3", 4/3),
                    ("5:4", 5/4), ("1:1", 1/1), ("4:5", 4/5), ("3:4", 3/4),
                    ("2:3", 2/3), ("9:16", 9/16)
                ]
                aspect_ratio = min(allowed_ratios, key=lambda x: abs(x[1] - ratio))[0]
                
                log(f"Размер: {w}x{h}, aspect_ratio: {aspect_ratio}")
                
                # Собираем все изображения: главное фото + референсы
                all_image_urls = [main_url]
                if ref_urls:
                    all_image_urls.extend(ref_urls)
                    log(f"Добавлено {len(ref_urls)} референсов")
                
                # Nano Banana Pro Edit использует image_urls (массив)
                params = {
                    "prompt": prompt,
                    "image_urls": all_image_urls,
                    "aspect_ratio": aspect_ratio,
                    "output_format": "jpeg"
                }
                
                log(f"Отправляю: prompt={prompt}, images={len(all_image_urls)}, aspect_ratio={aspect_ratio}")
                result = fal_client.subscribe(model_id, arguments=params, with_logs=True)
                log(f"✅ Ответ получен от FAL")
            
            else:
                raise ValueError(f"Неизвестная модель: {model_type}")
            
            update_progress(0.8)
            
            # Обработка результатов
            save_folder = os.path.join(self.output_folder, subfolder)
            os.makedirs(save_folder, exist_ok=True)
            
            # Для Wide режима с пакетной обработкой
            if model_type == "wide" and 'all_results' in locals():
                log(f"Сохранение пакетных результатов...")
                saved_count = 0
                last_saved_img = None
                saved_paths = []  # Пути для галереи
                
                for idx, (img_path, res) in enumerate(all_results):
                    if res is None:
                        continue
                    
                    # Извлекаем URL
                    out_url = None
                    if "images" in res and res["images"]:
                        out_url = res["images"][0].get("url")
                    elif "image" in res:
                        out_url = res["image"].get("url")
                    
                    if out_url:
                        try:
                            img_data = requests.get(out_url).content
                            from io import BytesIO
                            
                            # Проверяем что данные не пустые
                            if len(img_data) < 1000:
                                log(f"  ⚠️ Слишком маленький ответ для {os.path.basename(img_path)}: {len(img_data)} байт")
                                continue
                            
                            img = Image.open(BytesIO(img_data))
                            img.load()  # Принудительно загружаем данные
                            
                            if img.mode in ('RGBA', 'LA', 'P', 'CMYK'):
                                img = img.convert('RGB')
                            
                            # Сохраняем с именем оригинала
                            orig_name = os.path.splitext(os.path.basename(img_path))[0]
                            timestamp = datetime.datetime.now().strftime("%H%M%S")
                            out_name = f"{orig_name}_wide_{w}x{h}_{timestamp}.jpg"
                            out_path = os.path.join(save_folder, out_name)
                            
                            img.save(out_path, 'JPEG', quality=95, optimize=True)
                            log(f"  ✅ Сохранено: {out_name}")
                            saved_count += 1
                            last_saved_img = img.copy()  # Сохраняем копию для отображения
                            saved_paths.append(out_path)  # Сохраняем путь для галереи
                            
                        except Exception as e:
                            log(f"  ❌ Ошибка сохранения {os.path.basename(img_path)}: {e}")
                
                # Добавляем все сохранённые файлы в галерею
                for sp in saved_paths:
                    if sp not in self.ai_result_images:
                        self.ai_result_images.append(sp)
                
                # Показываем последний результат и обновляем галерею
                if last_saved_img and saved_paths:
                    self._wide_result_img = last_saved_img
                    self.ai_result_current = len(self.ai_result_images) - 1
                    self.after(0, lambda: self._show_ai_result(self._wide_result_img))
                    self.after(0, self._update_output_gallery)
                
                update_progress(1.0)
                update_status(f"✅ Готово: {saved_count}/{len(all_results)} фото")
                log(f"✅ Сохранено {saved_count} из {len(all_results)} фото")
                
                self.after(0, lambda: messagebox.showinfo("Готово", f"Обработано: {saved_count}/{len(all_results)} фото\nПапка: {save_folder}"))
                os.system(f'open "{save_folder}"')
            
            else:
                # Одиночная обработка для остальных моделей
                out_url = None
                if result and "images" in result and result["images"]:
                    out_url = result["images"][0].get("url")
                    log(f"Найдено изображение в images[0]")
                elif result and "image" in result:
                    out_url = result["image"].get("url")
                    log(f"Найдено изображение в image")
                else:
                    log(f"Структура ответа: {list(result.keys()) if result else 'None'}")
                
                if out_url:
                    log(f"Скачиваю результат...")
                    img_data = requests.get(out_url).content
                    log(f"✅ Скачано {len(img_data) / 1024:.1f} KB")
                    
                    from io import BytesIO
                    img = Image.open(BytesIO(img_data))
                    
                    # Принудительно загружаем данные изображения
                    img.load()
                    
                    if img.mode in ('RGBA', 'LA', 'P', 'CMYK'):
                        img = img.convert('RGB')
                    
                    timestamp = datetime.datetime.now().strftime("%H%M%S")
                    out_name = f"{model_type}_{w}x{h}_{timestamp}.jpg"
                    out_path = os.path.join(save_folder, out_name)
                    
                    # Пересохраняем через буфер для исправления поврежденных данных
                    buffer = BytesIO()
                    img.save(buffer, 'JPEG', quality=95, optimize=True)
                    buffer.seek(0)
                    final_img = Image.open(buffer)
                    final_img.save(out_path, 'JPEG', quality=95, optimize=True, progressive=False, subsampling=0)
                    
                    # Показываем результат в UI с путём для галереи
                    saved_path = out_path
                    self.after(0, lambda p=saved_path: self._show_ai_result(img, p))
                    
                    log(f"✅ Сохранено: {subfolder}/{out_name}")
                    update_progress(1.0)
                    update_status(f"✅ Готово: {subfolder}/{out_name}")
                    
                    self.after(0, lambda: messagebox.showinfo("Готово", f"Сохранено:\n{out_path}"))
                    os.system(f'open "{save_folder}"')
                else:
                    log(f"❌ Нет URL в ответе!")
                    log(f"Ответ: {str(result)[:500] if result else 'None'}")
                    update_status("❌ Ошибка: нет результата")
                
        except Exception as e:
            import traceback
            error_msg = str(e)
            log(f"❌ ОШИБКА: {error_msg}")
            log(f"Traceback: {traceback.format_exc()}")
            update_status(f"❌ {error_msg[:50]}")
            self.after(0, lambda: messagebox.showerror("Ошибка", f"{error_msg}\n\nПодробности в логе:\n{log_file}"))
    
    # ==================== МЕТОДЫ ====================
    
    def load_files(self):
        files = filedialog.askopenfilenames(filetypes=[("Images", "*.jpg *.jpeg *.png")])
        if files:
            self.files = list(files)
            self.update_file_list()
    
    def load_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.files = [os.path.join(folder, f) for f in os.listdir(folder) 
                         if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            self.update_file_list()
    
    def update_file_list(self):
        self.file_listbox.delete("1.0", "end")
        for f in self.files:
            self.file_listbox.insert("end", os.path.basename(f) + "\n")
        self.status_bar.configure(text=f"Загружено {len(self.files)} файлов")
    
    def select_output(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, folder)
    
    def start_upscale(self):
        if not self.files:
            messagebox.showwarning("Ошибка", "Загрузите изображения!")
            return
        Thread(target=self.process_upscale, daemon=True).start()
    
    def process_upscale(self):
        model_id = MODELS[self.model_var.get()]
        scale = int(self.scale_var.get())
        output_folder = os.path.join(self.output_folder, "upscaled")
        os.makedirs(output_folder, exist_ok=True)
        total = len(self.files)
        
        for i, filepath in enumerate(self.files):
            filename = os.path.basename(filepath)
            self.status_bar.configure(text=f"Обработка {i+1}/{total}: {filename}")
            self.upscale_progress.set((i + 1) / total)
            
            try:
                # Загружаем через байты, чтобы избежать проблем с русскими именами файлов
                with open(filepath, 'rb') as f:
                    file_url = fal_client.upload(f.read(), "image/jpeg")
                result = fal_client.run(model_id, arguments={"image_url": file_url, "scale": scale})
                url = result['image']['url']
                img_data = requests.get(url).content
                
                # Переконвертируем через PIL для корректного JPEG
                # Это исправляет проблемы с цветовым профилем и метаданными
                from io import BytesIO
                img = Image.open(BytesIO(img_data))
                
                # Конвертируем в RGB если нужно (убираем альфа-канал и CMYK)
                if img.mode in ('RGBA', 'LA', 'P', 'CMYK'):
                    img = img.convert('RGB')
                
                # Определяем формат выходного файла
                name_base, ext = os.path.splitext(filename)
                ext = ext.lower()
                if ext not in ['.jpg', '.jpeg', '.png']:
                    ext = '.jpg'
                
                output_path = os.path.join(output_folder, f"upscaled_{name_base}{ext}")
                
                # Сохраняем с правильными параметрами
                if ext in ['.jpg', '.jpeg']:
                    # JPEG с baseline профилем (максимальная совместимость)
                    img.save(output_path, 'JPEG', quality=95, optimize=True, 
                            progressive=False, subsampling=0)
                else:
                    img.save(output_path, 'PNG', optimize=True)
                
                img.close()
                
            except Exception as e:
                print(f"Ошибка {filename}: {e}")
        
        self.status_bar.configure(text=f"✅ Готово! {total} файлов")
        messagebox.showinfo("Готово", f"Файлы сохранены в:\n{output_folder}")
        os.system(f'open "{output_folder}"')
    
    # --- Compress ---
    def load_compress_files(self):
        files = filedialog.askopenfilenames(filetypes=[("Images", "*.jpg *.jpeg *.png *.heic *.heif")])
        if files:
            self.compress_files = list(files)
            self.compress_listbox.delete("1.0", "end")
            heic_count = sum(1 for f in files if f.lower().endswith(('.heic', '.heif')))
            for f in self.compress_files:
                self.compress_listbox.insert("end", os.path.basename(f) + "\n")
            if heic_count > 0:
                self.heic_status.configure(text=f"🖼️ Найдено {heic_count} HEIC файлов")
    
    def load_compress_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.compress_files = [os.path.join(folder, f) for f in os.listdir(folder) 
                                   if f.lower().endswith(('.jpg', '.jpeg', '.png', '.heic', '.heif'))]
            self.compress_listbox.delete("1.0", "end")
            heic_count = sum(1 for f in self.compress_files if f.lower().endswith(('.heic', '.heif')))
            for f in self.compress_files:
                self.compress_listbox.insert("end", os.path.basename(f) + "\n")
            if heic_count > 0:
                self.heic_status.configure(text=f"🖼️ Найдено {heic_count} HEIC файлов")
    
    def select_compress_output(self):
        folder = filedialog.askdirectory()
        if folder:
            self.compress_output.delete(0, "end")
            self.compress_output.insert(0, folder)
    
    def start_compress(self):
        if not self.compress_files:
            messagebox.showwarning("Ошибка", "Загрузите изображения!")
            return
        Thread(target=self.process_compress, daemon=True).start()
    
    def select_heic_folder(self):
        """Выбирает папку для конвертации HEIC"""
        folder = filedialog.askdirectory(title="Выберите папку с HEIC файлами")
        if folder:
            self.heic_folder_path = folder
            # Считаем HEIC файлы рекурсивно
            heic_count = 0
            for root, dirs, files in os.walk(folder):
                for f in files:
                    if f.lower().endswith(('.heic', '.heif')):
                        heic_count += 1
            self.heic_status.configure(text=f"📂 {os.path.basename(folder)} • {heic_count} HEIC файлов")
    
    def start_heic_convert(self):
        """Запускает конвертацию HEIC"""
        if not self.heic_folder_path:
            messagebox.showwarning("Ошибка", "Сначала выберите папку с HEIC файлами")
            return
        Thread(target=lambda: self.process_heic_folder(self.heic_folder_path), daemon=True).start()
    
    def convert_heic_folder(self):
        """Конвертирует все HEIC файлы в папке в JPG (старый метод)"""
        folder = filedialog.askdirectory(title="Выберите папку с HEIC файлами")
        if folder:
            Thread(target=lambda: self.process_heic_folder(folder), daemon=True).start()
    
    def process_heic_folder(self, folder):
        """Обрабатывает папку с HEIC файлами (рекурсивно, включая подпапки)"""
        try:
            from pillow_heif import register_heif_opener
            register_heif_opener()
        except ImportError:
            self.heic_status.configure(text="⚠️ Установите: pip install pillow-heif")
            messagebox.showerror("Ошибка", "Для конвертации HEIC установите:\npip install pillow-heif")
            return
        
        # Находим все HEIC файлы РЕКУРСИВНО (включая подпапки)
        heic_files = []
        for root, dirs, files in os.walk(folder):
            for f in files:
                if f.lower().endswith(('.heic', '.heif')):
                    heic_files.append(os.path.join(root, f))
        
        if not heic_files:
            self.heic_status.configure(text="⚠️ HEIC файлы не найдены")
            return
        
        # Сохраняем в папку hack_to_jpeg
        output_folder = os.path.join(self.output_folder, "hack_to_jpeg")
        os.makedirs(output_folder, exist_ok=True)
        
        total = len(heic_files)
        converted = 0
        errors = 0
        
        for i, heic_path in enumerate(heic_files):
            filename = os.path.basename(heic_path)
            self.heic_status.configure(text=f"🔄 {i+1}/{total}: {filename}")
            self.compress_progress.set((i + 1) / total)
            
            try:
                img = Image.open(heic_path)
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Сохраняем в общую папку вывода
                base_name = os.path.splitext(filename)[0]
                output_path = os.path.join(output_folder, f"{base_name}.jpg")
                img.save(output_path, "JPEG", quality=95)
                converted += 1
            except Exception as e:
                logger.error(f"HEIC conversion error {filename}: {e}")
                errors += 1
        
        self.compress_progress.set(1.0)
        self.heic_status.configure(text=f"✅ Конвертировано: {converted}, ошибок: {errors}")
        messagebox.showinfo("Готово", f"HEIC → JPG\nКонвертировано: {converted}\nОшибок: {errors}\n\nСохранено в:\n{output_folder}")
        os.system(f'open "{output_folder}"')
    
    def convert_heic_to_jpg(self, heic_path):
        """Конвертирует один HEIC файл в JPG и возвращает путь"""
        try:
            from pillow_heif import register_heif_opener
            register_heif_opener()
        except ImportError:
            return None
        
        try:
            img = Image.open(heic_path)
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # Сохраняем во временный файл
            import tempfile
            fd, temp_path = tempfile.mkstemp(suffix='.jpg')
            os.close(fd)
            img.save(temp_path, "JPEG", quality=95)
            return temp_path
        except Exception as e:
            logger.error(f"HEIC conversion error: {e}")
            return None
    
    def process_compress(self):
        output_folder = os.path.join(self.output_folder, "compressed")
        os.makedirs(output_folder, exist_ok=True)
        target_mb = self.target_size_var.get()
        target_bytes = target_mb * 1024 * 1024
        total = len(self.compress_files)
        
        # Регистрируем HEIC если включен тумблер
        if self.heic_convert_var.get():
            try:
                from pillow_heif import register_heif_opener
                register_heif_opener()
            except ImportError:
                self.heic_status.configure(text="⚠️ Установите: pip install pillow-heif")
        
        heic_converted = 0
        for i, filepath in enumerate(self.compress_files):
            filename = os.path.basename(filepath)
            self.status_bar.configure(text=f"Сжатие {i+1}/{total}: {filename}")
            self.compress_progress.set((i + 1) / total)
            
            try:
                # Конвертируем HEIC если включено
                is_heic = filepath.lower().endswith(('.heic', '.heif'))
                if is_heic and self.heic_convert_var.get():
                    heic_converted += 1
                
                img = Image.open(filepath)
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Имя выходного файла (меняем расширение для HEIC)
                if is_heic:
                    base_name = os.path.splitext(filename)[0]
                    output_filename = f"compressed_{base_name}.jpg"
                else:
                    output_filename = f"compressed_{filename}"
                
                output_path = os.path.join(output_folder, output_filename)
                quality = 95
                while quality > 10:
                    img.save(output_path, "JPEG", quality=quality, optimize=True)
                    if os.path.getsize(output_path) <= target_bytes:
                        break
                    quality -= 5
            except Exception as e:
                logger.error(f"Ошибка {filename}: {e}")
        
        status_text = f"✅ Сжато {total} файлов"
        if heic_converted > 0:
            status_text += f" (из них HEIC: {heic_converted})"
        self.status_bar.configure(text=status_text)
        messagebox.showinfo("Готово", f"Файлы сохранены в:\n{output_folder}")
    
    # --- Watermark ---
    def load_wm_files(self):
        files = filedialog.askopenfilenames(filetypes=[("Images", "*.jpg *.jpeg *.png *.webp")])
        if files:
            self.wm_files = list(files)
            self.wm_video_path = None
            self.wm_media_label.configure(text=f"📷 {len(files)} фото загружено")
            # Показываем превью первого файла
            self.show_wm_preview(files[0])
    
    def load_wm_video(self):
        """Load video file for watermarking"""
        video_path = filedialog.askopenfilename(
            filetypes=[("Video", "*.mp4 *.mov *.avi *.mkv *.webm")]
        )
        if video_path:
            self.wm_video_path = video_path
            self.wm_files = []
            self.wm_media_label.configure(text=f"🎬 {os.path.basename(video_path)}")
            # Извлекаем первый кадр для превью
            self.extract_video_frame(video_path)
    
    def extract_video_frame(self, video_path):
        """Extract first frame from video for preview"""
        try:
            import cv2
            cap = cv2.VideoCapture(video_path)
            ret, frame = cap.read()
            if ret:
                # Конвертируем BGR в RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.wm_preview_source = Image.fromarray(frame_rgb)
                self.update_wm_preview()
            cap.release()
        except ImportError:
            self.wm_status.configure(text="⚠️ Установите opencv-python: pip install opencv-python")
        except Exception as e:
            self.wm_status.configure(text=f"❌ Ошибка видео: {e}")
    
    def load_wm_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.wm_files = [os.path.join(folder, f) for f in os.listdir(folder) 
                            if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
            self.wm_video_path = None
            self.wm_media_label.configure(text=f"📂 {len(self.wm_files)} фото из папки")
            if self.wm_files:
                self.show_wm_preview(self.wm_files[0])
    
    def show_wm_preview(self, image_path):
        """Show image preview on canvas"""
        try:
            self.wm_preview_source = Image.open(image_path)
            self.update_wm_preview()
        except Exception as e:
            self.wm_status.configure(text=f"❌ Ошибка: {e}")
    
    def update_wm_preview(self):
        """Update preview with current watermark settings"""
        if not hasattr(self, 'wm_preview_source') or self.wm_preview_source is None:
            return
        
        try:
            # Копируем исходное изображение
            img = self.wm_preview_source.copy().convert("RGBA")
            
            # Применяем водяной знак
            wm_type = self.wm_type.get()
            if wm_type == "text":
                img = self.add_text_watermark_preview(img)
            elif wm_type == "logo" and hasattr(self, 'wm_logo_path') and self.wm_logo_path:
                img = self.add_logo_watermark_preview(img)
            elif wm_type == "both":
                # Сначала лого, потом текст
                if hasattr(self, 'wm_logo_path') and self.wm_logo_path:
                    img = self.add_logo_watermark_preview(img)
                img = self.add_text_watermark_preview(img)
            
            # Масштабируем для превью
            canvas_w = self.wm_preview_canvas.winfo_width() or 600
            canvas_h = self.wm_preview_canvas.winfo_height() or 400
            
            ratio = min(canvas_w / img.width, canvas_h / img.height) * 0.9
            new_w = int(img.width * ratio)
            new_h = int(img.height * ratio)
            
            img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            self.wm_preview_photo = ImageTk.PhotoImage(img_resized)
            
            # Отображаем
            self.wm_preview_canvas.delete("all")
            self.wm_preview_canvas.create_image(
                canvas_w // 2, canvas_h // 2,
                image=self.wm_preview_photo, anchor="center"
            )
            
            # Обновляем лейблы
            self.wm_scale_label.configure(text=f"{int(self.wm_scale.get() * 100)}%")
            self.wm_opacity_label.configure(text=f"{int(self.wm_opacity.get() * 100)}%")
            if hasattr(self, 'wm_text_scale_label'):
                self.wm_text_scale_label.configure(text=f"{int(self.wm_text_scale.get() * 100)}%")
            
        except Exception as e:
            logger.error(f"Preview error: {e}")
    
    def add_text_watermark_preview(self, img):
        """Add multiline text watermark to image"""
        txt_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(txt_layer)
        
        # Размер шрифта с учётом масштаба
        try:
            base_size = self.wm_font_size.get()
        except:
            base_size = 48
        # Используем отдельный масштаб для текста
        text_scale = getattr(self, 'wm_text_scale', None)
        if text_scale:
            font_size = int(base_size * text_scale.get())
        else:
            font_size = base_size
        
        # Загружаем шрифт
        font_name = self.wm_font.get()
        try:
            font_paths = {
                "Arial": "/System/Library/Fonts/Supplemental/Arial.ttf",
                "Helvetica": "/System/Library/Fonts/Helvetica.ttc",
                "Times New Roman": "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
                "Georgia": "/System/Library/Fonts/Supplemental/Georgia.ttf",
                "Verdana": "/System/Library/Fonts/Supplemental/Verdana.ttf",
                "Courier New": "/System/Library/Fonts/Supplemental/Courier New.ttf",
                "Impact": "/System/Library/Fonts/Supplemental/Impact.ttf",
                "Comic Sans MS": "/System/Library/Fonts/Supplemental/Comic Sans MS.ttf",
                "Trebuchet MS": "/System/Library/Fonts/Supplemental/Trebuchet MS.ttf",
            }
            font_path = font_paths.get(font_name, "/System/Library/Fonts/Helvetica.ttc")
            font = ImageFont.truetype(font_path, font_size)
        except:
            font = ImageFont.load_default()
        
        # Получаем многострочный текст
        text = self.wm_text.get("1.0", "end-1c")  # Для CTkTextbox
        lines = text.split("\n")
        
        # Вычисляем общий размер текстового блока
        line_heights = []
        line_widths = []
        for line in lines:
            if line.strip():
                bbox = draw.textbbox((0, 0), line, font=font)
                line_widths.append(bbox[2] - bbox[0])
                line_heights.append(bbox[3] - bbox[1])
            else:
                line_widths.append(0)
                line_heights.append(font_size // 2)  # Пустая строка
        
        tw = max(line_widths) if line_widths else 100
        th = sum(line_heights) + (len(lines) - 1) * 5  # 5px между строками
        
        # Позиция блока
        x, y = self.calculate_wm_position(img.width, img.height, tw, th)
        
        # Прозрачность
        opacity = int(self.wm_opacity.get() * 255)
        
        # Рисуем каждую строку
        current_y = y
        for i, line in enumerate(lines):
            if line.strip():
                # Центрируем строку относительно блока
                line_x = x + (tw - line_widths[i]) // 2
                # Тень
                draw.text((line_x+2, current_y+2), line, font=font, fill=(0, 0, 0, opacity // 2))
                # Текст
                draw.text((line_x, current_y), line, font=font, fill=(255, 255, 255, opacity))
            current_y += line_heights[i] + 5
        
        return Image.alpha_composite(img, txt_layer)
    
    def add_logo_watermark_preview(self, img):
        """Add logo watermark to image"""
        try:
            logo = Image.open(self.wm_logo_path).convert("RGBA")
            
            # Масштабируем лого
            scale = self.wm_scale.get()
            new_w = int(logo.width * scale)
            new_h = int(logo.height * scale)
            logo = logo.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
            # Прозрачность
            opacity = self.wm_opacity.get()
            if opacity < 1.0:
                alpha = logo.split()[3]
                alpha = alpha.point(lambda p: int(p * opacity))
                logo.putalpha(alpha)
            
            # Позиция
            x, y = self.calculate_wm_position(img.width, img.height, new_w, new_h)
            
            # Накладываем
            img.paste(logo, (x, y), logo)
            return img
        except Exception as e:
            logger.error(f"Logo error: {e}")
            return img
    
    def calculate_wm_position(self, img_w, img_h, wm_w, wm_h):
        """Calculate watermark position based on selected position"""
        margin = 20
        pos = self.wm_position.get()
        
        positions = {
            "top-left": (margin, margin),
            "top-center": ((img_w - wm_w) // 2, margin),
            "top-right": (img_w - wm_w - margin, margin),
            "center-left": (margin, (img_h - wm_h) // 2),
            "center": ((img_w - wm_w) // 2, (img_h - wm_h) // 2),
            "center-right": (img_w - wm_w - margin, (img_h - wm_h) // 2),
            "bottom-left": (margin, img_h - wm_h - margin),
            "bottom-center": ((img_w - wm_w) // 2, img_h - wm_h - margin),
            "bottom-right": (img_w - wm_w - margin, img_h - wm_h - margin),
        }
        return positions.get(pos, positions["center"])
    
    def toggle_wm_settings(self):
        """Toggle watermark settings panel visibility"""
        if self.wm_settings_expanded.get():
            # Свернуть
            self.wm_settings_frame.pack_forget()
            self.wm_settings_btn.configure(text="⚙️ Настройки ▼")
            self.wm_settings_expanded.set(False)
        else:
            # Развернуть
            self.wm_settings_frame.pack(fill="x", padx=10, pady=5, after=self.wm_settings_btn)
            self.wm_settings_btn.configure(text="⚙️ Настройки ▲")
            self.wm_settings_expanded.set(True)
    
    def select_logo(self):
        path = filedialog.askopenfilename(filetypes=[("PNG", "*.png")])
        if path:
            self.wm_logo_path = path
            self.logo_label.configure(text=os.path.basename(path), text_color=COLORS["success"])
            self.update_wm_preview()
    
    # --- Watermark Presets ---
    def load_wm_presets(self):
        """Load watermark presets from file"""
        import json
        try:
            if os.path.exists(self.wm_presets_file):
                with open(self.wm_presets_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:  # Только если файл не пустой
                        self.wm_presets = json.loads(content)
                        logger.info(f"Loaded {len(self.wm_presets)} watermark presets")
                    else:
                        self.wm_presets = {}
            else:
                self.wm_presets = {}
        except Exception as e:
            logger.error(f"Error loading presets: {e}")
            self.wm_presets = {}
    
    def save_wm_presets_to_file(self):
        """Save presets to file"""
        import json
        try:
            logger.info(f"Saving presets to {self.wm_presets_file}: {len(self.wm_presets)} presets")
            with open(self.wm_presets_file, 'w', encoding='utf-8') as f:
                json.dump(self.wm_presets, f, ensure_ascii=False, indent=2)
            logger.info(f"Presets saved successfully")
        except Exception as e:
            logger.error(f"Error saving presets: {e}")
            messagebox.showerror("Ошибка", f"Не удалось сохранить пресеты: {e}")
    
    def save_wm_preset(self):
        """Save current settings as preset"""
        from tkinter import simpledialog
        try:
            name = simpledialog.askstring("Сохранить пресет", "Введите имя пресета:")
            if name:
                preset_data = {
                    "type": self.wm_type.get() if hasattr(self, 'wm_type') else "text",
                    "text": self.wm_text.get("1.0", "end-1c") if hasattr(self, 'wm_text') else "",
                    "font": self.wm_font.get() if hasattr(self, 'wm_font') else "Arial",
                    "font_size": self.wm_font_size.get() if hasattr(self, 'wm_font_size') else 48,
                    "text_scale": self.wm_text_scale.get() if hasattr(self, 'wm_text_scale') else 1.0,
                    "scale": self.wm_scale.get() if hasattr(self, 'wm_scale') else 1.0,
                    "opacity": self.wm_opacity.get() if hasattr(self, 'wm_opacity') else 0.7,
                    "position": self.wm_position.get() if hasattr(self, 'wm_position') else "center",
                    "logo_path": getattr(self, 'wm_logo_path', None)
                }
                self.wm_presets[name] = preset_data
                logger.info(f"Saving preset '{name}': {preset_data}")
                self.save_wm_presets_to_file()
                # Обновляем меню
                self.wm_preset_menu.configure(values=list(self.wm_presets.keys()))
                self.wm_preset_var.set(name)
                self.wm_status.configure(text=f"✅ Пресет '{name}' сохранён")
        except Exception as e:
            logger.error(f"Error saving preset: {e}")
            messagebox.showerror("Ошибка", f"Ошибка сохранения пресета: {e}")
    
    def load_wm_preset(self, name):
        """Load preset by name"""
        if name in self.wm_presets:
            preset = self.wm_presets[name]
            self.wm_type.set(preset.get("type", "text"))
            # Многострочный текст
            self.wm_text.delete("1.0", "end")
            self.wm_text.insert("1.0", preset.get("text", ""))
            self.wm_font.set(preset.get("font", "Arial"))
            self.wm_font_size.set(preset.get("font_size", 48))
            self.wm_text_scale.set(preset.get("text_scale", 1.0))  # Масштаб текста
            self.wm_scale.set(preset.get("scale", 1.0))  # Масштаб PNG
            self.wm_opacity.set(preset.get("opacity", 0.7))
            self.wm_position.set(preset.get("position", "center"))
            if preset.get("logo_path"):
                self.wm_logo_path = preset["logo_path"]
                self.logo_label.configure(text=os.path.basename(self.wm_logo_path))
            self.update_wm_preview()
            self.wm_status.configure(text=f"📥 Пресет '{name}' загружен")
    
    def delete_wm_preset(self):
        """Delete selected preset"""
        name = self.wm_preset_var.get()
        if name and name in self.wm_presets:
            del self.wm_presets[name]
            self.save_wm_presets_to_file()
            preset_names = list(self.wm_presets.keys()) if self.wm_presets else ["Нет пресетов"]
            self.wm_preset_menu.configure(values=preset_names)
            self.wm_preset_var.set("")
            self.wm_status.configure(text=f"🗑️ Пресет '{name}' удалён")
    
    def start_watermark(self):
        if not self.wm_files and not self.wm_video_path:
            messagebox.showwarning("Ошибка", "Загрузите фото или видео!")
            return
        
        try:
            if self.wm_video_path:
                Thread(target=self.process_video_watermark, daemon=True).start()
            else:
                Thread(target=self.process_watermark, daemon=True).start()
        except Exception as e:
            logger.error(f"Start watermark error: {e}")
            messagebox.showerror("Ошибка", f"Ошибка запуска: {e}")
    
    def process_video_watermark(self):
        """Add watermark to video using ffmpeg, preserving original quality"""
        try:
            import subprocess
            
            output_folder = os.path.join(self.output_folder, "watermarked")
            os.makedirs(output_folder, exist_ok=True)
            
            video_name = os.path.basename(self.wm_video_path)
            # Сохраняем в том же формате
            output_path = os.path.join(output_folder, f"wm_{video_name}")
            
            self.wm_status.configure(text="🎬 Обработка видео...")
            self.wm_progress.set(0.3)
            
            # Получаем информацию о видео для сохранения качества
            probe_cmd = [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=codec_name,bit_rate,width,height,r_frame_rate",
                "-of", "csv=p=0", self.wm_video_path
            ]
            probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
            logger.info(f"Video info: {probe_result.stdout}")
            
            wm_type = self.wm_type.get()
            
            # Позиция для ffmpeg
            pos = self.wm_position.get()
            
            # Базовые параметры ffmpeg для сохранения качества
            # -crf 18 = высокое качество, -preset slow = лучшее сжатие
            quality_params = ["-c:v", "libx264", "-crf", "18", "-preset", "medium", "-c:a", "copy"]
            
            if wm_type in ["text", "both"]:
                # Получаем многострочный текст
                text = self.wm_text.get("1.0", "end-1c").replace("\n", " | ").replace("'", "\\'")  # Заменяем переносы на |
                # Используем отдельный масштаб для текста
                font_size = int(self.wm_font_size.get() * self.wm_text_scale.get())
                opacity = self.wm_opacity.get()
                
                pos_map = {
                    "top-left": "x=20:y=20",
                    "top-center": "x=(w-text_w)/2:y=20",
                    "top-right": "x=w-text_w-20:y=20",
                    "center-left": "x=20:y=(h-text_h)/2",
                    "center": "x=(w-text_w)/2:y=(h-text_h)/2",
                    "center-right": "x=w-text_w-20:y=(h-text_h)/2",
                    "bottom-left": "x=20:y=h-text_h-20",
                    "bottom-center": "x=(w-text_w)/2:y=h-text_h-20",
                    "bottom-right": "x=w-text_w-20:y=h-text_h-20",
                }
                position = pos_map.get(pos, pos_map["center"])
                
                # Фильтр для текста
                text_filter = f"drawtext=text='{text}':fontsize={font_size}:fontcolor=white@{opacity}:borderw=2:bordercolor=black@0.5:{position}"
                
                if wm_type == "both" and hasattr(self, 'wm_logo_path') and self.wm_logo_path:
                    # Текст + лого
                    scale = self.wm_scale.get()
                    logo_opacity = self.wm_opacity.get()
                    logo_pos_map = {
                        "top-left": "20:20",
                        "top-center": "(W-w)/2:20",
                        "top-right": "W-w-20:20",
                        "center-left": "20:(H-h)/2",
                        "center": "(W-w)/2:(H-h)/2",
                        "center-right": "W-w-20:(H-h)/2",
                        "bottom-left": "20:H-h-20",
                        "bottom-center": "(W-w)/2:H-h-20",
                        "bottom-right": "W-w-20:H-h-20",
                    }
                    logo_position = logo_pos_map.get(pos, logo_pos_map["center"])
                    
                    cmd = [
                        "ffmpeg", "-y", "-i", self.wm_video_path, "-i", self.wm_logo_path,
                        "-filter_complex", 
                        f"[1:v]scale=iw*{scale}:ih*{scale},format=rgba,colorchannelmixer=aa={logo_opacity}[logo];[0:v][logo]overlay={logo_position},{text_filter}",
                    ] + quality_params + [output_path]
                else:
                    # Только текст
                    cmd = [
                        "ffmpeg", "-y", "-i", self.wm_video_path,
                        "-vf", text_filter,
                    ] + quality_params + [output_path]
                    
            elif wm_type == "logo" and hasattr(self, 'wm_logo_path') and self.wm_logo_path:
                # Только PNG логотип
                scale = self.wm_scale.get()
                opacity = self.wm_opacity.get()
                
                pos_map = {
                    "top-left": "20:20",
                    "top-center": "(W-w)/2:20",
                    "top-right": "W-w-20:20",
                    "center-left": "20:(H-h)/2",
                    "center": "(W-w)/2:(H-h)/2",
                    "center-right": "W-w-20:(H-h)/2",
                    "bottom-left": "20:H-h-20",
                    "bottom-center": "(W-w)/2:H-h-20",
                    "bottom-right": "W-w-20:H-h-20",
                }
                position = pos_map.get(pos, pos_map["center"])
                
                cmd = [
                    "ffmpeg", "-y", "-i", self.wm_video_path, "-i", self.wm_logo_path,
                    "-filter_complex", f"[1:v]scale=iw*{scale}:ih*{scale},format=rgba,colorchannelmixer=aa={opacity}[logo];[0:v][logo]overlay={position}",
                ] + quality_params + [output_path]
            else:
                self.wm_status.configure(text="❌ Выберите текст или логотип")
                return
            
            logger.info(f"FFmpeg command: {' '.join(cmd)}")
            self.wm_status.configure(text="🎬 Кодирование видео...")
            self.wm_progress.set(0.5)
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                self.wm_progress.set(1.0)
                self.wm_status.configure(text="✅ Видео сохранено")
                messagebox.showinfo("Готово", f"Видео сохранено:\n{output_path}")
                os.system(f'open "{output_folder}"')
            else:
                self.wm_status.configure(text="❌ Ошибка ffmpeg")
                logger.error(f"ffmpeg error: {result.stderr}")
                messagebox.showerror("Ошибка", f"FFmpeg ошибка:\n{result.stderr[:500]}")
                
        except FileNotFoundError:
            self.wm_status.configure(text="⚠️ Установите ffmpeg: brew install ffmpeg")
        except Exception as e:
            self.wm_status.configure(text=f"❌ Ошибка: {e}")
            logger.error(f"Video watermark error: {e}")
    
    def process_watermark(self):
        try:
            output_folder = os.path.join(self.output_folder, "watermarked")
            os.makedirs(output_folder, exist_ok=True)
            total = len(self.wm_files)
            
            if total == 0:
                self.wm_status.configure(text="⚠️ Нет файлов для обработки")
                return
            
            processed = 0
            for i, filepath in enumerate(self.wm_files):
                filename = os.path.basename(filepath)
                self.wm_status.configure(text=f"💧 {i+1}/{total}: {filename}")
                self.wm_progress.set((i + 1) / total)
                
                try:
                    img = Image.open(filepath).convert("RGBA")
                    
                    wm_type = self.wm_type.get()
                    if wm_type == "text":
                        img = self.add_text_watermark_preview(img)
                    elif wm_type == "logo" and hasattr(self, 'wm_logo_path') and self.wm_logo_path:
                        img = self.add_logo_watermark_preview(img)
                    elif wm_type == "both":
                        # Сначала лого, потом текст
                        if hasattr(self, 'wm_logo_path') and self.wm_logo_path:
                            img = self.add_logo_watermark_preview(img)
                        img = self.add_text_watermark_preview(img)
                    
                    output_path = os.path.join(output_folder, f"wm_{filename}")
                    img.convert("RGB").save(output_path, quality=95)
                    processed += 1
                except Exception as e:
                    logger.error(f"Ошибка {filename}: {e}")
            
            self.wm_status.configure(text=f"✅ Готово {processed}/{total} файлов")
            messagebox.showinfo("Готово", f"Файлы сохранены в:\n{output_folder}")
            os.system(f'open "{output_folder}"')
        except Exception as e:
            logger.error(f"Process watermark error: {e}")
            self.wm_status.configure(text=f"❌ Ошибка: {e}")
            messagebox.showerror("Ошибка", f"Ошибка обработки: {e}")
    
    def add_text_watermark(self, img, text, position):
        txt_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(txt_layer)
        font_size = max(20, img.width // 40)
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
        except:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        margin = 20
        if position == "bottom-right":
            x, y = img.width - tw - margin, img.height - th - margin
        elif position == "bottom-left":
            x, y = margin, img.height - th - margin
        else:
            x, y = (img.width - tw) // 2, (img.height - th) // 2
        draw.text((x, y), text, font=font, fill=(255, 255, 255, 180))
        return Image.alpha_composite(img, txt_layer)
    
    def add_logo_watermark(self, img, logo_path, position, size=15, opacity=50):
        logo = Image.open(logo_path).convert("RGBA")
        new_width = int(img.width * (size / 100))
        new_height = int(new_width * (logo.height / logo.width))
        logo = logo.resize((new_width, new_height), Image.Resampling.LANCZOS)
        alpha = logo.split()[3].point(lambda p: int(p * (opacity / 100)))
        logo.putalpha(alpha)
        margin = 20
        if position == "center":
            x, y = (img.width - logo.width) // 2, (img.height - logo.height) // 2
        elif position == "bottom-right":
            x, y = img.width - logo.width - margin, img.height - logo.height - margin
        else:
            x, y = margin, img.height - logo.height - margin
        img.paste(logo, (x, y), logo)
        return img
    
    # --- Sort ---
    def start_sort(self):
        folder = filedialog.askdirectory(title="Выберите папку с фотографиями")
        if folder:
            self.sort_folder_label.configure(text=f"📂 {os.path.basename(folder)}")
            Thread(target=lambda: self.process_sort(folder), daemon=True).start()
    
    def process_sort(self, source_folder):
        # Сохраняем в главную рабочую папку (output_folder)
        horizontal_folder = os.path.join(self.output_folder, "horizontal")
        vertical_folder = os.path.join(self.output_folder, "vertical")
        
        try:
            os.makedirs(horizontal_folder, exist_ok=True)
            os.makedirs(vertical_folder, exist_ok=True)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Ошибка", f"Не удалось создать папки: {e}"))
            return
        
        image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.tiff', '.bmp', '.gif'}
        
        try:
            files = [(f, os.path.join(source_folder, f)) for f in os.listdir(source_folder)
                     if os.path.isfile(os.path.join(source_folder, f)) and 
                     os.path.splitext(f)[1].lower() in image_extensions]
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Ошибка", f"Не удалось прочитать папку: {e}"))
            return
        
        total = len(files)
        if total == 0:
            self.after(0, lambda: messagebox.showwarning("Внимание", "В папке нет изображений"))
            return
        
        stats = {"horizontal": 0, "vertical": 0, "errors": 0}
        
        for i, (filename, filepath) in enumerate(files):
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
                stats["errors"] += 1
                logger.warning(f"Ошибка при обработке {filename}: {e}")
            
            # Обновляем прогресс через главный поток
            progress = (i + 1) / total
            self.after(0, lambda p=progress: self.sort_progress.set(p))
        
        result = f"✅ Горизонтальных: {stats['horizontal']}, Вертикальных: {stats['vertical']}"
        if stats["errors"] > 0:
            result += f", Ошибок: {stats['errors']}"
        
        # Обновляем UI через главный поток
        def finish():
            self.sort_status.configure(text=result)
            self.status_bar.configure(text=result)
            messagebox.showinfo("Готово", f"{result}\n\nСохранено в: {self.output_folder}")
            # Открываем папку (кроссплатформенно)
            if sys.platform == 'darwin':
                subprocess.run(['open', self.output_folder])
            elif sys.platform == 'win32':
                subprocess.run(['explorer', self.output_folder])
            else:
                subprocess.run(['xdg-open', self.output_folder])
        
        self.after(0, finish)
    
    # --- Aspect Ratio ---
    def select_crop_folder(self):
        """Выбор папки для пресетного кропа"""
        folder = filedialog.askdirectory(title="Выберите папку с фотографиями")
        if folder:
            self.crop_preset_folder = folder
            self.crop_preset_files = []
            # Собираем все фото из папки
            image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.tiff', '.bmp'}
            files = [os.path.join(folder, f) for f in os.listdir(folder)
                    if os.path.isfile(os.path.join(folder, f)) and 
                    os.path.splitext(f)[1].lower() in image_extensions]
            self.crop_preset_files = files
            self.crop_source_label.configure(text=f"📂 {os.path.basename(folder)} ({len(files)} фото)")
    
    def select_crop_files(self):
        """Выбор отдельных файлов для пресетного кропа"""
        files = filedialog.askopenfilenames(
            title="Выберите фотографии",
            filetypes=[("Изображения", "*.jpg *.jpeg *.png *.webp *.tiff *.bmp")]
        )
        if files:
            self.crop_preset_files = list(files)
            self.crop_preset_folder = None
            self.crop_source_label.configure(text=f"🖼️ Выбрано {len(files)} фото")
    
    def clear_crop_selection(self):
        """Очистка выбора для кропа"""
        self.crop_preset_files = []
        self.crop_preset_folder = None
        self.crop_source_label.configure(text="⬆️ Выберите источник, затем нажмите пресет")
    
    def apply_crop_preset(self, ratio_str):
        """Применяет кроп пресета к выбранным файлам"""
        if not self.crop_preset_files:
            messagebox.showwarning("Ошибка", "Сначала выберите папку или фото")
            return
        
        # Парсим соотношение
        ratio_parts = ratio_str.split(":")
        ratio_w, ratio_h = int(ratio_parts[0]), int(ratio_parts[1])
        target_aspect = ratio_w / ratio_h
        
        Thread(target=lambda: self.process_crop_preset(target_aspect, ratio_str), daemon=True).start()
    
    def process_crop_preset(self, target_aspect, ratio_str):
        """Обрабатывает кроп для всех выбранных файлов"""
        files = self.crop_preset_files
        if not files:
            return
        
        # Создаём папку для результатов
        output_folder = os.path.join(self.output_folder, f"crop_{ratio_str.replace(':', 'x')}")
        os.makedirs(output_folder, exist_ok=True)
        
        method = self.aspect_method.get()
        processed = 0
        total = len(files)
        
        self.aspect_status.configure(text=f"✂️ Кроп {ratio_str}: 0/{total}...")
        
        for i, filepath in enumerate(files):
            try:
                img = Image.open(filepath)
                filename = os.path.basename(filepath)
                
                # Конвертируем в RGB если нужно
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                w, h = img.size
                current_aspect = w / h
                
                # Приводим к целевому соотношению сторон
                if abs(current_aspect - target_aspect) > 0.01:
                    if method == "crop":
                        # Обрезка по центру
                        if current_aspect > target_aspect:
                            # Слишком широкое - обрезаем по ширине
                            new_w = int(h * target_aspect)
                            left = (w - new_w) // 2
                            img = img.crop((left, 0, left + new_w, h))
                        else:
                            # Слишком высокое - обрезаем по высоте
                            new_h = int(w / target_aspect)
                            top = (h - new_h) // 2
                            img = img.crop((0, top, w, top + new_h))
                    else:
                        # Добавление полей (pad)
                        if current_aspect > target_aspect:
                            # Добавляем поля сверху/снизу
                            new_h = int(w / target_aspect)
                            new_img = Image.new("RGB", (w, new_h), (0, 0, 0))
                            offset = (new_h - h) // 2
                            new_img.paste(img, (0, offset))
                            img = new_img
                        else:
                            # Добавляем поля слева/справа
                            new_w = int(h * target_aspect)
                            new_img = Image.new("RGB", (new_w, h), (0, 0, 0))
                            offset = (new_w - w) // 2
                            new_img.paste(img, (offset, 0))
                            img = new_img
                
                # Сохраняем с высоким качеством
                # Определяем формат по расширению
                ext = os.path.splitext(filename)[1].lower()
                if ext in ['.jpg', '.jpeg']:
                    img.save(os.path.join(output_folder, filename), 'JPEG', quality=95, optimize=True)
                elif ext == '.png':
                    img.save(os.path.join(output_folder, filename), 'PNG', optimize=True)
                else:
                    img.save(os.path.join(output_folder, filename), 'JPEG', quality=95, optimize=True)
                
                processed += 1
                img.close()
            except Exception as e:
                print(f"Ошибка {filepath}: {e}")
            
            self.aspect_progress.set((i + 1) / total)
            self.aspect_status.configure(text=f"✂️ Кроп {ratio_str}: {i+1}/{total}...")
        
        final_w, final_h = img.size if processed > 0 else (0, 0)
        result = f"✅ {processed} фото → {ratio_str}"
        self.aspect_status.configure(text=result)
        self.status_bar.configure(text=result)
        messagebox.showinfo("Готово", f"Кроп {ratio_str} применён к {processed} фото\n\nСохранено в: {output_folder}")
        os.system(f'open "{output_folder}"')
    
    def start_aspect_fix(self):
        folder = filedialog.askdirectory(title="Выберите папку с фотографиями")
        if folder:
            self.aspect_folder_label.configure(text=f"📂 {os.path.basename(folder)}")
            Thread(target=lambda: self.process_aspect_fix(folder), daemon=True).start()
    
    def get_aspect_ratio(self, width, height):
        """Возвращает упрощённое соотношение сторон как строку"""
        from math import gcd
        divisor = gcd(width, height)
        w_ratio = width // divisor
        h_ratio = height // divisor
        # Упрощаем до стандартных соотношений
        ratio = width / height
        if 0.55 <= ratio <= 0.58:
            return "9:16"
        elif 0.65 <= ratio <= 0.68:
            return "2:3"
        elif 0.74 <= ratio <= 0.76:
            return "3:4"
        elif 0.79 <= ratio <= 0.81:
            return "4:5"
        elif 0.99 <= ratio <= 1.01:
            return "1:1"
        elif 1.24 <= ratio <= 1.26:
            return "5:4"
        elif 1.32 <= ratio <= 1.35:
            return "4:3"
        elif 1.48 <= ratio <= 1.52:
            return "3:2"
        elif 1.76 <= ratio <= 1.79:
            return "16:9"
        else:
            return f"{w_ratio}:{h_ratio}"
    
    def process_aspect_fix(self, source_folder):
        image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.tiff', '.bmp'}
        files = [(f, os.path.join(source_folder, f)) for f in os.listdir(source_folder)
                 if os.path.isfile(os.path.join(source_folder, f)) and 
                 os.path.splitext(f)[1].lower() in image_extensions]
        
        if not files:
            messagebox.showwarning("Ошибка", "Нет изображений в папке")
            return
        
        # Анализируем соотношения сторон и размеры
        from collections import Counter
        ratios = []
        file_info = {}
        all_widths = []
        all_heights = []
        all_pixels = []  # Для вычисления среднего количества пикселей
        
        self.aspect_status.configure(text="🔍 Анализ фотографий...")
        
        for filename, filepath in files:
            try:
                with Image.open(filepath) as img:
                    w, h = img.size
                    ratio = self.get_aspect_ratio(w, h)
                    ratios.append(ratio)
                    file_info[filepath] = (ratio, w, h)
                    all_widths.append(w)
                    all_heights.append(h)
                    all_pixels.append(w * h)
            except:
                pass
        
        # Находим самое частое соотношение
        ratio_counts = Counter(ratios)
        target_ratio, count = ratio_counts.most_common(1)[0]
        
        # Парсим целевое соотношение
        ratio_w, ratio_h = map(int, target_ratio.split(":"))
        target_aspect = ratio_w / ratio_h
        
        # Вычисляем СРЕДНЕЕ разрешение
        # Формула: берем медиану количества пикселей и вычисляем размеры под целевое соотношение
        # Медиана лучше среднего - не искажается выбросами (очень большими или маленькими фото)
        all_pixels.sort()
        median_pixels = all_pixels[len(all_pixels) // 2]
        
        # Вычисляем размеры из медианы пикселей с учетом соотношения сторон
        # pixels = width * height, aspect = width / height
        # width = sqrt(pixels * aspect), height = sqrt(pixels / aspect)
        import math
        final_width = int(math.sqrt(median_pixels * target_aspect))
        final_height = int(math.sqrt(median_pixels / target_aspect))
        
        # Округляем до четных чисел (для совместимости с видеокодеками)
        final_width = (final_width // 2) * 2
        final_height = (final_height // 2) * 2
        
        self.aspect_status.configure(text=f"📐 {target_ratio} → {final_width}×{final_height} ({count}/{len(files)} фото)")
        
        # Создаём папку для результатов
        output_folder = os.path.join(self.output_folder, f"unified_{final_width}x{final_height}")
        os.makedirs(output_folder, exist_ok=True)
        
        method = self.aspect_method.get()
        processed = 0
        total = len(files)
        
        for i, (filename, filepath) in enumerate(files):
            if filepath not in file_info:
                continue
            
            current_ratio, w, h = file_info[filepath]
            
            try:
                img = Image.open(filepath)
                
                # Конвертируем в RGB если нужно
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                current_aspect = w / h
                
                # Шаг 1: Приводим к целевому соотношению сторон
                if abs(current_aspect - target_aspect) > 0.01:
                    if method == "crop":
                        # Обрезка по центру
                        if current_aspect > target_aspect:
                            # Слишком широкое - обрезаем по ширине
                            new_w = int(h * target_aspect)
                            left = (w - new_w) // 2
                            img = img.crop((left, 0, left + new_w, h))
                        else:
                            # Слишком высокое - обрезаем по высоте
                            new_h = int(w / target_aspect)
                            top = (h - new_h) // 2
                            img = img.crop((0, top, w, top + new_h))
                    else:
                        # Добавление полей (pad)
                        if current_aspect > target_aspect:
                            # Добавляем поля сверху/снизу
                            new_h = int(w / target_aspect)
                            new_img = Image.new("RGB", (w, new_h), (0, 0, 0))
                            offset = (new_h - h) // 2
                            new_img.paste(img, (0, offset))
                            img = new_img
                        else:
                            # Добавляем поля слева/справа
                            new_w = int(h * target_aspect)
                            new_img = Image.new("RGB", (new_w, h), (0, 0, 0))
                            offset = (new_w - w) // 2
                            new_img.paste(img, (offset, 0))
                            img = new_img
                
                # Шаг 2: Масштабируем до целевого разрешения
                if img.size != (final_width, final_height):
                    # Используем LANCZOS для качественного масштабирования
                    img = img.resize((final_width, final_height), Image.LANCZOS)
                
                # Сохраняем с высоким качеством
                img.save(os.path.join(output_folder, filename), 'JPEG', quality=95, optimize=True)
                
                processed += 1
                img.close()
            except Exception as e:
                print(f"Ошибка {filename}: {e}")
            
            self.aspect_progress.set((i + 1) / total)
            self.aspect_status.configure(text=f"⏳ Обработка {i+1}/{total}...")
        
        result = f"✅ {processed} фото → {final_width}×{final_height}"
        self.aspect_status.configure(text=result)
        self.status_bar.configure(text=result)
        messagebox.showinfo("Готово", f"Все фото приведены к:\n• Соотношение: {target_ratio}\n• Разрешение: {final_width}×{final_height}\n\nСохранено в: {output_folder}")
        os.system(f'open "{output_folder}"')
    


    # ==================== AUTOCLICKER TAB ====================
    def create_autoclicker_tab(self):
        from pynput import mouse
        from pynput.mouse import Button, Controller as MouseController
        from pynput.keyboard import Key, Listener as KeyboardListener
        import json
        from datetime import datetime
        
        tab = self.tab_autoclicker
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=2)
        tab.grid_rowconfigure(0, weight=1)
        
        # Mouse controller уже создан при инициализации, проверяем
        if not hasattr(self, 'ac_mouse_controller') or self.ac_mouse_controller is None:
            self.ac_mouse_controller = MouseController()
        
        # === ЛЕВАЯ ПАНЕЛЬ - ПРЕСЕТЫ ===
        presets_frame = ctk.CTkFrame(tab, fg_color=COLORS["bg_tertiary"], corner_radius=GLASS_CORNER_RADIUS)
        presets_frame.grid(row=0, column=0, padx=(15, 5), pady=10, sticky="nsew")
        
        ctk.CTkLabel(presets_frame, text="📁 Мои пресеты", 
                    font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(pady=(15, 10))
        
        # Кнопки управления пресетами
        preset_btns = ctk.CTkFrame(presets_frame, fg_color="transparent")
        preset_btns.pack(fill="x", padx=10, pady=(0, 10))
        
        ctk.CTkButton(preset_btns, text="🔄", width=40, height=30,
                     command=self.ac_refresh_presets,
                     fg_color=COLORS["bg_secondary"], hover_color=COLORS["primary"],
                     corner_radius=8).pack(side="left", padx=2)
        
        ctk.CTkButton(preset_btns, text="📂", width=40, height=30,
                     command=lambda: os.system(f'open "{self.ac_saves_folder}"'),
                     fg_color=COLORS["bg_secondary"], hover_color=COLORS["primary"],
                     corner_radius=8).pack(side="left", padx=2)
        
        # Список пресетов
        self.ac_presets_scroll = ctk.CTkScrollableFrame(presets_frame, 
                                                        fg_color=COLORS["bg_dark"],
                                                        corner_radius=GLASS_CORNER_RADIUS_SMALL,
                                                        height=300)
        self.ac_presets_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Быстрое сохранение
        save_frame = ctk.CTkFrame(presets_frame, fg_color="transparent")
        save_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        self.ac_preset_name = ctk.CTkEntry(save_frame, placeholder_text="Название...",
                                           width=140, height=35,
                                           fg_color=COLORS["bg_secondary"])
        self.ac_preset_name.pack(side="left", padx=(0, 5))
        
        ctk.CTkButton(save_frame, text="💾", width=40, height=35,
                     command=self.ac_quick_save,
                     fg_color=COLORS["success"], hover_color=COLORS["success_hover"],
                     corner_radius=8).pack(side="left")
        
        # === ПРАВАЯ ПАНЕЛЬ - УПРАВЛЕНИЕ ===
        control_frame = ctk.CTkFrame(tab, fg_color=COLORS["bg_tertiary"], corner_radius=GLASS_CORNER_RADIUS)
        control_frame.grid(row=0, column=1, padx=(5, 15), pady=10, sticky="nsew")
        
        # Заголовок
        ctk.CTkLabel(control_frame, text="🖱️ AutoClicker Pro", 
                    font=ctk.CTkFont(family=FONT_FAMILY, size=20, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(pady=(15, 5))
        
        # === ЗАПИСЬ ===
        record_section = ctk.CTkFrame(control_frame, fg_color=COLORS["bg_secondary"], corner_radius=GLASS_CORNER_RADIUS_SMALL)
        record_section.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkLabel(record_section, text="📹 Запись", 
                    font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(pady=(10, 5))
        
        rec_btns = ctk.CTkFrame(record_section, fg_color="transparent")
        rec_btns.pack(pady=5)
        
        # Кнопка НАЧАТЬ запись
        self.ac_start_btn = ctk.CTkButton(rec_btns, text="⏺️ Начать (F6)", 
                                          command=self.ac_start_recording,
                                          width=120, height=40,
                                          font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
                                          fg_color=COLORS["danger"], hover_color=COLORS["danger_hover"],
                                          corner_radius=GLASS_CORNER_RADIUS_SMALL)
        self.ac_start_btn.pack(side="left", padx=3)
        
        # Кнопка ОСТАНОВИТЬ запись
        self.ac_stop_btn = ctk.CTkButton(rec_btns, text="⏹️ Стоп (F6)", 
                                         command=self.ac_stop_recording,
                                         width=120, height=40,
                                         font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
                                         fg_color=COLORS["bg_tertiary"], hover_color=COLORS["border"],
                                         corner_radius=GLASS_CORNER_RADIUS_SMALL)
        self.ac_stop_btn.pack(side="left", padx=3)
        
        # Кнопка ОЧИСТИТЬ
        ctk.CTkButton(rec_btns, text="🗑️", command=self.ac_clear,
                     width=45, height=40,
                     fg_color=COLORS["bg_tertiary"], hover_color=COLORS["border"],
                     corner_radius=GLASS_CORNER_RADIUS_SMALL).pack(side="left", padx=3)
        
        self.ac_record_status = ctk.CTkLabel(record_section, text="Готов к записи",
                                             font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                                             text_color=COLORS["text_secondary"])
        self.ac_record_status.pack(pady=(5, 10))
        
        # === ВОСПРОИЗВЕДЕНИЕ ===
        play_section = ctk.CTkFrame(control_frame, fg_color=COLORS["bg_secondary"], corner_radius=GLASS_CORNER_RADIUS_SMALL)
        play_section.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkLabel(play_section, text="▶️ Воспроизведение", 
                    font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(pady=(10, 5))
        
        # Скорость
        speed_frame = ctk.CTkFrame(play_section, fg_color="transparent")
        speed_frame.pack(fill="x", padx=15, pady=5)
        
        ctk.CTkLabel(speed_frame, text="⚡ Скорость:", 
                    font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                    text_color=COLORS["text_secondary"]).pack(side="left")
        
        self.ac_speed_label = ctk.CTkLabel(speed_frame, text="1.0x", 
                                           font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
                                           text_color=COLORS["success"])
        self.ac_speed_label.pack(side="right")
        
        self.ac_speed_slider = ctk.CTkSlider(play_section, from_=0.5, to=10.0,
                                             number_of_steps=19,
                                             command=self.ac_update_speed,
                                             width=250,
                                             progress_color=COLORS["primary"],
                                             button_color=COLORS["text_primary"])
        self.ac_speed_slider.pack(pady=5)
        self.ac_speed_slider.set(1.0)
        
        # Быстрые кнопки скорости
        speed_btns = ctk.CTkFrame(play_section, fg_color="transparent")
        speed_btns.pack(pady=5)
        
        for speed in [1, 2, 3, 5, 10]:
            ctk.CTkButton(speed_btns, text=f"{speed}x", width=45, height=28,
                         command=lambda s=speed: self.ac_set_speed(s),
                         fg_color=COLORS["bg_tertiary"], hover_color=COLORS["primary"],
                         corner_radius=6).pack(side="left", padx=2)
        
        # Повторы
        repeat_frame = ctk.CTkFrame(play_section, fg_color="transparent")
        repeat_frame.pack(fill="x", padx=15, pady=5)
        
        ctk.CTkLabel(repeat_frame, text="🔁 Повторов:", 
                    font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                    text_color=COLORS["text_secondary"]).pack(side="left")
        
        self.ac_repeat_entry = ctk.CTkEntry(repeat_frame, width=60, height=28,
                                            fg_color=COLORS["bg_tertiary"], justify="center")
        self.ac_repeat_entry.pack(side="right")
        self.ac_repeat_entry.insert(0, "1")
        
        # Кнопка воспроизведения
        self.ac_play_btn = ctk.CTkButton(play_section, text="▶️ Воспроизвести", 
                                         command=self.ac_toggle_playback,
                                         width=200, height=45,
                                         font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
                                         fg_color=COLORS["success"], hover_color=COLORS["success_hover"],
                                         corner_radius=GLASS_CORNER_RADIUS_SMALL)
        self.ac_play_btn.pack(pady=(10, 15))
        
        # === ИНФОРМАЦИЯ ===
        info_section = ctk.CTkFrame(control_frame, fg_color=COLORS["bg_secondary"], corner_radius=GLASS_CORNER_RADIUS_SMALL)
        info_section.pack(fill="x", padx=15, pady=10)
        
        self.ac_info_label = ctk.CTkLabel(info_section, 
                                          text="📊 Записано: 0 действий\n⏱️ Длительность: 0.0 сек",
                                          font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                                          text_color=COLORS["text_secondary"],
                                          justify="left")
        self.ac_info_label.pack(pady=10, padx=15, anchor="w")
        
        hotkeys_text = "⌨️ Горячие клавиши: F6 — Запись | F7 — Воспроизвести | ESC — Стоп"
        ctk.CTkLabel(info_section, text=hotkeys_text,
                    font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                    text_color=COLORS["text_secondary"]).pack(pady=(0, 10), padx=15)
        
        # Загружаем список пресетов
        self.after(100, self.ac_refresh_presets)
    
    def ac_setup_global_hotkeys(self):
        """Настройка глобальных горячих клавиш для автокликера
        ОТКЛЮЧЕНО: pynput.keyboard.Listener вызывает trace trap на macOS.
        Используйте кнопки в интерфейсе вместо горячих клавиш.
        """
        logger.info("Global hotkeys DISABLED (causes trace trap on macOS)")
        logger.info("Use UI buttons instead: Record, Stop, Play")
        # Горячие клавиши отключены для стабильности на macOS
        return
    
    def ac_stop_all(self):
        """Остановить всё (ESC) - не сохраняем автоматически"""
        if self.ac_recording:
            self.ac_stop_recording(auto_save=False)
        if self.ac_playing:
            self.ac_stop_playback()
    
    def ac_toggle_recording(self):
        if self.ac_playing:
            messagebox.showwarning("Внимание", "Остановите воспроизведение!")
            return
        if self.ac_recording:
            self.ac_stop_recording()
        else:
            self.ac_start_recording()
    
    def ac_start_recording(self):
        from pynput import mouse, keyboard
        from pynput.mouse import Button
        from pynput.keyboard import Key
        import time
        
        if self.ac_playing:
            logger.warning("Cannot start recording while playing")
            return
        
        logger.info("Starting recording...")
        
        self.ac_recording = True
        self.ac_is_real_recording = True  # Это реальная запись
        self.ac_recorded_actions = []
        self.ac_start_time = time.time()
        
        # Обновляем кнопки
        self.ac_start_btn.configure(state="disabled")
        self.ac_stop_btn.configure(fg_color=COLORS["danger"], hover_color=COLORS["danger_hover"])
        self.ac_record_status.configure(text="🔴 Запись... (кнопка Стоп)", text_color=COLORS["danger"])
        
        def on_click(x, y, button, pressed):
            if not self.ac_recording:
                return False
            try:
                action = {
                    "type": "click",
                    "x": x, "y": y,
                    "button": "left" if button == Button.left else "right",
                    "pressed": pressed,
                    "time": time.time() - self.ac_start_time
                }
                self.ac_recorded_actions.append(action)
                # Обновляем статус с количеством записанных действий
                clicks = sum(1 for a in self.ac_recorded_actions if a["type"] == "click" and a.get("pressed"))
                keys = sum(1 for a in self.ac_recorded_actions if a["type"] == "key" and a.get("pressed"))
                self.after(0, lambda: self.ac_record_status.configure(
                    text=f"🔴 Запись: {clicks} кликов, {keys} клавиш",
                    text_color=COLORS["danger"]))
                self.after(0, self.ac_update_info)
                logger.info(f"Click recorded: {action['button']} at ({int(x)}, {int(y)})")
            except Exception as e:
                logger.error(f"Error recording click: {e}")
        
        def on_move(x, y):
            if not self.ac_recording:
                return False
            try:
                current_time = time.time() - self.ac_start_time
                if self.ac_recorded_actions:
                    last = self.ac_recorded_actions[-1]
                    if last["type"] == "move" and current_time - last["time"] < 0.02:
                        return
                self.ac_recorded_actions.append({"type": "move", "x": x, "y": y, "time": current_time})
            except Exception as e:
                logger.error(f"Error recording move: {e}")
        
        def on_scroll(x, y, dx, dy):
            if not self.ac_recording:
                return False
            try:
                action = {"type": "scroll", "x": x, "y": y, "dx": dx, "dy": dy,
                         "time": time.time() - self.ac_start_time}
                self.ac_recorded_actions.append(action)
                self.after(0, self.ac_update_info)
            except Exception as e:
                logger.error(f"Error recording scroll: {e}")
        
        def on_key_press(key):
            if not self.ac_recording:
                return False
            try:
                # Получаем строковое представление клавиши
                try:
                    key_char = key.char
                except AttributeError:
                    key_char = str(key)
                
                action = {
                    "type": "key",
                    "key": key_char,
                    "pressed": True,
                    "time": time.time() - self.ac_start_time
                }
                self.ac_recorded_actions.append(action)
                logger.info(f"Key recorded: {key_char} (press)")
                self.after(0, self.ac_update_info)
            except Exception as e:
                logger.error(f"Error recording key press: {e}")
        
        def on_key_release(key):
            if not self.ac_recording:
                return False
            try:
                try:
                    key_char = key.char
                except AttributeError:
                    key_char = str(key)
                
                action = {
                    "type": "key",
                    "key": key_char,
                    "pressed": False,
                    "time": time.time() - self.ac_start_time
                }
                self.ac_recorded_actions.append(action)
            except Exception as e:
                logger.error(f"Error recording key release: {e}")
        
        # Mouse listener
        try:
            self.ac_mouse_listener = mouse.Listener(on_click=on_click, on_move=on_move, on_scroll=on_scroll)
            self.ac_mouse_listener.start()
            logger.info("Mouse listener started successfully")
        except Exception as e:
            logger.error(f"Failed to start mouse listener: {e}")
            self.ac_recording = False
            self.ac_start_btn.configure(state="normal")
            self.ac_record_status.configure(text=f"❌ Ошибка мыши: {e}", text_color=COLORS["danger"])
            return
        
        # Keyboard listener через Quartz (macOS native API)
        try:
            import Quartz
            from Quartz import (
                CGEventTapCreate, kCGSessionEventTap, kCGHeadInsertEventTap,
                kCGEventTapOptionListenOnly, CGEventMaskBit, kCGEventKeyDown, kCGEventKeyUp,
                CFMachPortCreateRunLoopSource, CFRunLoopGetCurrent, CFRunLoopAddSource,
                kCFRunLoopCommonModes, CGEventTapEnable, CGEventGetIntegerValueField,
                kCGKeyboardEventKeycode
            )
            import threading
            
            def keyboard_callback(proxy, event_type, event, refcon):
                if not self.ac_recording:
                    return event
                try:
                    keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
                    pressed = (event_type == kCGEventKeyDown)
                    
                    # Конвертируем keycode в читаемое имя
                    keycode_map = {
                        0: 'a', 1: 's', 2: 'd', 3: 'f', 4: 'h', 5: 'g', 6: 'z', 7: 'x',
                        8: 'c', 9: 'v', 11: 'b', 12: 'q', 13: 'w', 14: 'e', 15: 'r',
                        16: 'y', 17: 't', 18: '1', 19: '2', 20: '3', 21: '4', 22: '6',
                        23: '5', 24: '=', 25: '9', 26: '7', 27: '-', 28: '8', 29: '0',
                        30: ']', 31: 'o', 32: 'u', 33: '[', 34: 'i', 35: 'p', 36: 'Key.enter',
                        37: 'l', 38: 'j', 39: "'", 40: 'k', 41: ';', 42: '\\', 43: ',',
                        44: '/', 45: 'n', 46: 'm', 47: '.', 48: 'Key.tab', 49: 'Key.space',
                        50: '`', 51: 'Key.backspace', 53: 'Key.esc', 55: 'Key.cmd',
                        56: 'Key.shift', 57: 'Key.caps_lock', 58: 'Key.alt', 59: 'Key.ctrl',
                        96: 'Key.f5', 97: 'Key.f6', 98: 'Key.f7', 99: 'Key.f3', 100: 'Key.f8',
                        101: 'Key.f9', 103: 'Key.f11', 105: 'Key.f13', 107: 'Key.f14',
                        109: 'Key.f10', 111: 'Key.f12', 113: 'Key.f15', 118: 'Key.f4',
                        120: 'Key.f2', 122: 'Key.f1', 123: 'Key.left', 124: 'Key.right',
                        125: 'Key.down', 126: 'Key.up'
                    }
                    key_char = keycode_map.get(keycode, f'keycode_{keycode}')
                    
                    action = {
                        "type": "key",
                        "key": key_char,
                        "pressed": pressed,
                        "time": time.time() - self.ac_start_time
                    }
                    self.ac_recorded_actions.append(action)
                    if pressed:
                        logger.info(f"Key recorded: {key_char}")
                        self.after(0, self.ac_update_info)
                except Exception as e:
                    logger.error(f"Keyboard callback error: {e}")
                return event
            
            # Создаём event tap для клавиатуры
            event_mask = CGEventMaskBit(kCGEventKeyDown) | CGEventMaskBit(kCGEventKeyUp)
            self.ac_event_tap = CGEventTapCreate(
                kCGSessionEventTap,
                kCGHeadInsertEventTap,
                kCGEventTapOptionListenOnly,
                event_mask,
                keyboard_callback,
                None
            )
            
            if self.ac_event_tap:
                run_loop_source = CFMachPortCreateRunLoopSource(None, self.ac_event_tap, 0)
                
                def run_tap():
                    CFRunLoopAddSource(CFRunLoopGetCurrent(), run_loop_source, kCFRunLoopCommonModes)
                    CGEventTapEnable(self.ac_event_tap, True)
                    from Quartz import CFRunLoopRun
                    CFRunLoopRun()
                
                self.ac_keyboard_thread = threading.Thread(target=run_tap, daemon=True)
                self.ac_keyboard_thread.start()
                logger.info("Keyboard recording started (Quartz CGEventTap)")
            else:
                logger.warning("Failed to create CGEventTap - check Accessibility permissions")
                
        except ImportError:
            logger.warning("Quartz not available - keyboard recording disabled")
        except Exception as e:
            logger.error(f"Failed to setup keyboard recording: {e}")
    
    def ac_stop_recording(self, auto_save=True):
        if not self.ac_recording:
            logger.info("ac_stop_recording called but not recording")
            return
        
        logger.info(f"Stopping recording, {len(self.ac_recorded_actions)} actions recorded")
        
        self.ac_recording = False
        
        # Останавливаем mouse listener
        if self.ac_mouse_listener:
            try:
                self.ac_mouse_listener.stop()
                logger.info("Mouse listener stopped")
            except Exception as e:
                logger.error(f"Error stopping mouse listener: {e}")
            self.ac_mouse_listener = None
        
        # Останавливаем keyboard listener (Quartz event tap)
        if hasattr(self, 'ac_event_tap') and self.ac_event_tap:
            try:
                from Quartz import CGEventTapEnable
                CGEventTapEnable(self.ac_event_tap, False)
                logger.info("Keyboard event tap disabled")
            except Exception as e:
                logger.error(f"Error stopping keyboard event tap: {e}")
            self.ac_event_tap = None
        
        # Считаем записанные клавиши
        key_count = sum(1 for a in self.ac_recorded_actions if a["type"] == "key" and a.get("pressed"))
        click_count = sum(1 for a in self.ac_recorded_actions if a["type"] == "click" and a.get("pressed"))
        logger.info(f"Recorded: {click_count} clicks, {key_count} keys")
        
        # Обновляем кнопки
        self.ac_start_btn.configure(state="normal")
        self.ac_stop_btn.configure(fg_color=COLORS["bg_tertiary"], hover_color=COLORS["border"])
        self.ac_record_status.configure(text=f"✅ Записано {len(self.ac_recorded_actions)} действий", 
                                        text_color=COLORS["success"])
        self.ac_update_info()
        
        # Автоматически сохраняем пресет только если это была реальная запись
        if auto_save and self.ac_recorded_actions and self.ac_is_real_recording:
            from datetime import datetime
            auto_name = f"Запись_{datetime.now().strftime('%H%M%S')}"
            self.ac_save_preset(auto_name)
        
        # Сбрасываем флаг реальной записи
        self.ac_is_real_recording = False
    
    def ac_clear(self):
        if self.ac_recording:
            self.ac_stop_recording(auto_save=False)
        self.ac_recorded_actions = []
        self.ac_record_status.configure(text="Готов к записи", text_color=COLORS["text_secondary"])
        self.ac_update_info()
    
    def ac_toggle_playback(self):
        if self.ac_recording:
            messagebox.showwarning("Внимание", "Остановите запись!")
            return
        if self.ac_playing:
            self.ac_stop_playback()
        else:
            self.ac_start_playback()
    
    def ac_start_playback(self):
        from pynput.mouse import Button, Controller as MouseController
        from pynput.keyboard import Controller as KeyboardController, Key
        import time
        import threading
        
        if not self.ac_recorded_actions:
            messagebox.showwarning("Внимание", "Сначала запишите действия!")
            return
        
        # Проверяем/создаём mouse controller
        if not hasattr(self, 'ac_mouse_controller') or self.ac_mouse_controller is None:
            logger.info("Creating mouse controller for playback...")
            self.ac_mouse_controller = MouseController()
        
        # Проверяем работоспособность контроллера
        try:
            test_pos = self.ac_mouse_controller.position
            logger.info(f"Mouse controller OK, position: {test_pos}")
        except Exception as e:
            logger.error(f"Mouse controller error: {e}")
            messagebox.showerror("Ошибка", f"Не удалось получить доступ к мыши:\n{e}\n\nПроверьте разрешения Accessibility в macOS!")
            return
        
        self.ac_playing = True
        self.ac_play_btn.configure(text="⏹️ Остановить", fg_color="#ff4444")
        keyboard_controller = KeyboardController()
        
        # Сохраняем ссылку на контроллер для потока
        mouse_ctrl = self.ac_mouse_controller
        actions_copy = list(self.ac_recorded_actions)  # Копия для безопасности
        speed = self.ac_speed_multiplier
        
        logger.info(f"Starting playback: {len(actions_copy)} actions at {speed}x speed")
        
        def play_thread():
            try:
                repeats = int(self.ac_repeat_entry.get())
            except:
                repeats = 1
            
            logger.info(f"Playback thread started, repeats: {repeats}")
            
            for rep in range(repeats):
                if not self.ac_playing:
                    logger.info("Playback stopped by user")
                    break
                    
                self.after(0, lambda r=rep+1, t=repeats: 
                          self.ac_record_status.configure(text=f"▶️ Воспроизведение {r}/{t}...",
                                                         text_color=COLORS["warning"]))
                last_time = 0
                action_count = 0
                
                for action in actions_copy:
                    if not self.ac_playing:
                        break
                    
                    try:
                        delay = (action["time"] - last_time) / speed
                        if delay > 0:
                            time.sleep(delay)
                        last_time = action["time"]
                        
                        if action["type"] == "move":
                            mouse_ctrl.position = (int(action["x"]), int(action["y"]))
                        elif action["type"] == "click":
                            mouse_ctrl.position = (int(action["x"]), int(action["y"]))
                            time.sleep(0.005)  # Небольшая пауза для стабильности
                            btn = Button.left if action["button"] == "left" else Button.right
                            if action["pressed"]:
                                mouse_ctrl.press(btn)
                            else:
                                mouse_ctrl.release(btn)
                        elif action["type"] == "scroll":
                            mouse_ctrl.position = (int(action["x"]), int(action["y"]))
                            time.sleep(0.005)
                            mouse_ctrl.scroll(int(action["dx"]), int(action["dy"]))
                        elif action["type"] == "key":
                            key_str = action["key"]
                            try:
                                if key_str.startswith("Key."):
                                    key_name = key_str.replace("Key.", "")
                                    key_obj = getattr(Key, key_name, None)
                                    if key_obj:
                                        if action["pressed"]:
                                            keyboard_controller.press(key_obj)
                                        else:
                                            keyboard_controller.release(key_obj)
                                else:
                                    if action["pressed"]:
                                        keyboard_controller.press(key_str)
                                    else:
                                        keyboard_controller.release(key_str)
                            except Exception as ke:
                                logger.warning(f"Key action error: {ke}")
                        
                        action_count += 1
                        
                    except Exception as e:
                        logger.error(f"Playback action error at {action_count}: {e}, action: {action}")
                        continue
                
                logger.info(f"Repeat {rep+1}/{repeats} completed, {action_count} actions played")
            
            logger.info("Playback thread finished")
            self.after(0, self.ac_stop_playback)
        
        threading.Thread(target=play_thread, daemon=True).start()
    
    def ac_stop_playback(self):
        self.ac_playing = False
        self.ac_play_btn.configure(text="▶️ Воспроизвести", fg_color=COLORS["success"])
        self.ac_record_status.configure(text="✅ Воспроизведение завершено", text_color=COLORS["success"])
    
    def ac_update_speed(self, value):
        self.ac_speed_multiplier = round(value, 1)
        self.ac_speed_label.configure(text=f"{self.ac_speed_multiplier}x")
    
    def ac_set_speed(self, speed):
        self.ac_speed_slider.set(speed)
        self.ac_update_speed(speed)
    
    def ac_update_info(self):
        count = len(self.ac_recorded_actions)
        duration = self.ac_recorded_actions[-1]["time"] if self.ac_recorded_actions else 0
        clicks = sum(1 for a in self.ac_recorded_actions if a["type"] == "click" and a.get("pressed"))
        self.ac_info_label.configure(
            text=f"📊 Записано: {count} действий ({clicks} кликов)\n"
                 f"⏱️ Длительность: {duration:.1f} сек | При {self.ac_speed_multiplier}x: {duration/self.ac_speed_multiplier:.1f} сек"
        )
    
    def ac_refresh_presets(self):
        for widget in self.ac_presets_scroll.winfo_children():
            widget.destroy()
        
        if not os.path.exists(self.ac_saves_folder):
            return
        
        files = sorted([f for f in os.listdir(self.ac_saves_folder) if f.endswith('.json')],
                      key=lambda x: os.path.getmtime(os.path.join(self.ac_saves_folder, x)), reverse=True)
        
        if not files:
            ctk.CTkLabel(self.ac_presets_scroll, text="Нет сохранённых\nпресетов",
                        font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                        text_color=COLORS["text_secondary"]).pack(pady=20)
            return
        
        for filename in files:
            self.ac_create_preset_item(filename)
    
    def ac_create_preset_item(self, filename):
        import json
        import tkinter as tk
        filepath = os.path.join(self.ac_saves_folder, filename)
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            actions_count = data.get("actions_count", len(data.get("actions", [])))
            duration = data.get("duration", 0)
            name = data.get("name", filename.replace(".json", ""))
        except:
            actions_count = 0
            duration = 0
            name = filename.replace(".json", "")
        
        item = ctk.CTkFrame(self.ac_presets_scroll, fg_color=COLORS["bg_tertiary"], corner_radius=8, height=55)
        item.pack(fill="x", pady=2, padx=2)
        item.pack_propagate(False)
        
        # Левая часть - название (кликабельное для переименования) и инфо
        info = ctk.CTkFrame(item, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=5, pady=3)
        
        # Название - по клику можно переименовать
        name_label = ctk.CTkLabel(info, text=name[:20] + "..." if len(name) > 20 else name,
                                  font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
                                  text_color=COLORS["text_primary"],
                                  anchor="w", cursor="hand2")
        name_label.pack(fill="x", anchor="w")
        name_label.bind("<Button-1>", lambda e, f=filename: self.ac_load_preset(f))
        name_label.bind("<Double-Button-1>", lambda e, f=filename, lbl=name_label, frm=item: self.ac_rename_preset(f, lbl, frm))
        
        # Инфо
        ctk.CTkLabel(info, text=f"📊 {actions_count}  ⏱️ {duration:.1f}с",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                    text_color=COLORS["text_secondary"], anchor="w").pack(fill="x", anchor="w")
        
        # Правая часть - кнопки ▶ и 🗑 в ряд
        btns = ctk.CTkFrame(item, fg_color="transparent")
        btns.pack(side="right", padx=3, pady=3)
        
        ctk.CTkButton(btns, text="▶", width=28, height=28,
                     command=lambda f=filename: self.ac_play_preset(f),
                     fg_color=COLORS["success"], hover_color=COLORS["success_hover"],
                     corner_radius=6, font=ctk.CTkFont(size=14)).pack(side="left", padx=1)
        ctk.CTkButton(btns, text="🗑", width=28, height=28,
                     command=lambda f=filename: self.ac_delete_preset(f),
                     fg_color=COLORS["danger"], hover_color=COLORS["danger_hover"],
                     corner_radius=6, font=ctk.CTkFont(size=12)).pack(side="left", padx=1)
    
    def ac_rename_preset(self, filename, label, frame):
        """Переименовать пресет по двойному клику"""
        import json
        from tkinter import simpledialog
        
        filepath = os.path.join(self.ac_saves_folder, filename)
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            old_name = data.get("name", filename.replace(".json", ""))
        except:
            old_name = filename.replace(".json", "")
        
        new_name = simpledialog.askstring("Переименовать", "Новое название:", 
                                          initialvalue=old_name, parent=self)
        if new_name and new_name.strip() and new_name != old_name:
            new_name = new_name.strip()
            # Обновляем данные в файле
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)
                data["name"] = new_name
                
                # Переименовываем файл
                safe_name = "".join(c for c in new_name if c.isalnum() or c in (' ', '-', '_')).strip()
                new_filepath = os.path.join(self.ac_saves_folder, f"{safe_name}.json")
                
                with open(new_filepath, "w") as f:
                    json.dump(data, f, indent=2)
                
                # Удаляем старый файл если имя изменилось
                if new_filepath != filepath:
                    os.remove(filepath)
                
                self.ac_refresh_presets()
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось переименовать:\n{e}")
    
    def ac_load_preset(self, filename):
        import json
        filepath = os.path.join(self.ac_saves_folder, filename)
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            self.ac_recorded_actions = data["actions"]
            self.ac_update_info()
            name = data.get("name", filename.replace(".json", ""))
            self.ac_record_status.configure(text=f"✅ Загружен: {name}", text_color=COLORS["success"])
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить:\n{e}")
    
    def ac_play_preset(self, filename):
        self.ac_load_preset(filename)
        if self.ac_recorded_actions:
            self.ac_start_playback()
    
    def ac_delete_preset(self, filename):
        if messagebox.askyesno("Удаление", f"Удалить пресет '{filename}'?"):
            try:
                os.remove(os.path.join(self.ac_saves_folder, filename))
                self.ac_refresh_presets()
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось удалить:\n{e}")
    
    def ac_save_preset(self, name):
        """Сохранить пресет с указанным именем"""
        import json
        from datetime import datetime
        
        if not self.ac_recorded_actions:
            return
        
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
        if not safe_name:
            safe_name = f"Запись_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        filepath = os.path.join(self.ac_saves_folder, f"{safe_name}.json")
        
        data = {
            "name": name,
            "created": datetime.now().isoformat(),
            "actions_count": len(self.ac_recorded_actions),
            "duration": self.ac_recorded_actions[-1]["time"] if self.ac_recorded_actions else 0,
            "actions": self.ac_recorded_actions
        }
        
        try:
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)
            self.ac_refresh_presets()
            self.ac_record_status.configure(text=f"✅ Сохранено: {name}", text_color=COLORS["success"])
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить:\n{e}")
    
    def ac_quick_save(self):
        import json
        from datetime import datetime
        
        if not self.ac_recorded_actions:
            messagebox.showwarning("Внимание", "Сначала запишите действия!")
            return
        
        name = self.ac_preset_name.get().strip()
        if not name:
            name = f"Запись_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.ac_save_preset(name)
        self.ac_preset_name.delete(0, "end")
    
    # === АВТОСОХРАНЕНИЕ ===
    
    def save_autosave(self):
        """Сохраняет состояние программы в файл"""
        import json
        from datetime import datetime
        
        try:
            data = {
                "version": 1,
                "saved_at": datetime.now().isoformat(),
                "storyboard": {
                    "images": self.storyboard_images if hasattr(self, 'storyboard_images') else [],
                    "zoom_scale": self.zoom_scale if hasattr(self, 'zoom_scale') else 1.0
                },
                "output_folder": self.output_folder
            }
            
            with open(self.autosave_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Автосохранение: {len(data['storyboard']['images'])} фото")
            return True
        except Exception as e:
            logger.error(f"Ошибка автосохранения: {e}")
            return False
    
    def load_autosave(self):
        """Загружает сохранённое состояние программы"""
        import json
        logger.info(f"Checking autosave file: {self.autosave_file}")
        
        if not os.path.exists(self.autosave_file):
            logger.info("Файл автосохранения не найден")
            return False
        
        try:
            logger.info("Opening autosave file...")
            with open(self.autosave_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info("Autosave JSON loaded.")
            
            # Загружаем раскадровку
            if "storyboard" in data:
                logger.info("Loading storyboard data...")
                storyboard = data["storyboard"]
                
                # Проверяем существование файлов и фильтруем
                valid_images = []
                for img in storyboard.get("images", []):
                    img_path = img.get("path", "")
                    try:
                        logger.info(f"Verifying image: {img_path}")
                        if os.path.exists(img_path):
                            # Пробуем открыть файл для проверки прав доступа
                            with open(img_path, 'rb') as f:
                                pass
                            valid_images.append(img)
                        else:
                            logger.warning(f"Файл не найден: {img_path}")
                    except PermissionError:
                        logger.error(f"Доступ запрещен (TCC): {img_path}")
                        # Пытаемся добавить, GUI может показать заглушку или ошибку позже
                        valid_images.append(img)
                    except Exception as e:
                        logger.error(f"Ошибка проверки файла {img_path}: {e}")
                
                self.storyboard_images = valid_images
                self.zoom_scale = storyboard.get("zoom_scale", 1.0)
                logger.info(f"Storyboard loaded with {len(valid_images)} images.")
                
                # Обновляем canvas
                if hasattr(self, 'storyboard_canvas'):
                    logger.info("Refreshing storyboard canvas...")
                    self.refresh_storyboard(visible_only=False)
                
                if valid_images:
                    self.storyboard_status.configure(
                        text=f"✅ Восстановлено {len(valid_images)} фото • ⌘Z отмена"
                    )
            
            # Загружаем папку вывода
            if "output_folder" in data:
                saved_folder = data["output_folder"]
                logger.info(f"Restoring output folder: {saved_folder}")
                # Проверяем что папка существует или можем её создать
                if os.path.exists(saved_folder) or os.path.exists(os.path.dirname(saved_folder)):
                    self.output_folder = saved_folder
                    os.makedirs(self.output_folder, exist_ok=True)
                    # Обновляем UI
                    if hasattr(self, 'workspace_label'):
                        self.workspace_label.configure(text=self.output_folder)
                    logger.info(f"Восстановлена рабочая папка: {self.output_folder}")
            
            logger.info(f"Загружено из автосохранения: {len(self.storyboard_images)} фото")
            return True
        except Exception as e:
            logger.error(f"Ошибка загрузки автосохранения: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def on_closing(self):
        """Обработчик закрытия окна - сохраняем состояние"""
        self.save_autosave()
        
        # Останавливаем автокликер если запущен
        if hasattr(self, 'ac_stop_all'):
            self.ac_stop_all()
        
        self.destroy()


def start_main_app():
    """Запускает основное приложение после авторизации"""
    try:
        logger.info("--- Starting Main App ---")
        app = PhotoToolsApp()
        
        # Проверяем обновления в фоне
        try:
            from updater import check_updates_on_startup
            app.after(2000, lambda: check_updates_on_startup(app))
        except Exception as e:
            logger.warning(f"Update check failed: {e}")
        
        app.mainloop()
        logger.info("--- Main App Closed ---")
    except Exception as e:
        logger.critical(f"FATAL ERROR: {e}")
        logger.critical(traceback.format_exc())


if __name__ == "__main__":
    try:
        logger.info("--- Global Start ---")
        
        # Импортируем систему лицензирования
        from license_manager import license_manager, LicenseManager
        from login_window import LoginWindow
        
        # Проверяем интернет
        if not LicenseManager.check_internet_connection():
            messagebox.showerror("Ошибка", "Требуется подключение к интернету для запуска приложения")
            sys.exit(1)
        
        # Проверяем есть ли сохранённая сессия
        cached_user = license_manager._load_local_auth()
        if cached_user:
            # Пробуем автологин
            logger.info(f"Trying auto-login for: {cached_user}")
            # Получаем пароль из кэша невозможно, показываем окно входа
        
        # Показываем окно входа
        login = LoginWindow(on_success_callback=start_main_app)
        login.mainloop()
        
        logger.info("--- Global End ---")
    except Exception as e:
        logger.critical(f"FATAL ERROR: {e}")
        logger.critical(traceback.format_exc())
        sys.stdout.flush()
        sys.stderr.flush()

