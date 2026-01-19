#!/usr/bin/env python3
"""
Perspective Engine - Модуль коррекции перспективы

Основан на алгоритмах из:
- GIMP EZ-Perspective (Nils R. Barth, Public Domain)
- Darktable rotate and perspective module
- OpenCV perspective transformation

Реализует профессиональную коррекцию перспективы как в GIMP/Darktable/Lightroom:
- Up/Down (Pitch, Tilt) - наклон камеры вверх/вниз
- Left/Right (Yaw, Swing) - поворот камеры влево/вправо  
- Rotation (Roll, Twist) - вращение в плоскости изображения
- Автоматическое определение вертикалей/горизонталей
- Guided Upright - коррекция по нарисованным линиям

Автор адаптации: Fotya Tools
"""

import numpy as np
from math import pi, sin, cos, sqrt, atan2, degrees, radians
import cv2

# ============================================================
# GIMP-STYLE PERSPECTIVE TRANSFORMATION
# Основано на EZ-Perspective плагине для GIMP
# ============================================================

class GIMPPerspective:
    """
    Коррекция перспективы в стиле GIMP EZ-Perspective.
    
    Использует Tait-Bryan углы (zyx Euler angles):
    - pitch (ud) - вращение вокруг X (вверх/вниз)
    - yaw (lr) - вращение вокруг Y (влево/вправо)
    - roll (rot) - вращение вокруг Z (поворот в плоскости)
    """
    
    def __init__(self, width, height, focal_length_mm=50):
        """
        Инициализация.
        
        Args:
            width: ширина изображения в пикселях
            height: высота изображения в пикселях
            focal_length_mm: эффективное фокусное расстояние в мм (по диагонали)
        """
        self.width = width
        self.height = height
        self.focal_length = focal_length_mm
        
        # Вычисляем глубину (z_fix) в пикселях
        # Масштабируем по диагонали изображения
        image_diagonal = sqrt(width * width + height * height)
        diagonal_35mm = 12 * sqrt(13)  # sqrt(36² + 24²) = диагональ 35мм кадра
        self.z_fix = image_diagonal * focal_length_mm / diagonal_35mm
        
        # Центр изображения
        self.center_x = width / 2.0
        self.center_y = height / 2.0
    
    def _proj_trans_point(self, ud_deg, lr_deg, rot_deg, x_in, y_in):
        """
        Трансформация отдельной точки через 3D вращение.
        
        Применяет вращения в порядке: X (pitch), Y (yaw), Z (roll),
        затем проецирует обратно на плоскость z = z_fix.
        
        Args:
            ud_deg: угол pitch в градусах
            lr_deg: угол yaw в градусах
            rot_deg: угол roll в градусах
            x_in, y_in: входные координаты (относительно центра)
        
        Returns:
            (x_out, y_out): трансформированные координаты
        """
        # Конвертируем в радианы
        ud = radians(ud_deg)
        lr = radians(lr_deg)
        rot = radians(rot_deg)
        
        # Начальные координаты
        x, y, z = x_in, y_in, self.z_fix
        
        # Вращение вокруг X (pitch / up-down)
        x, y, z = (
            x,
            cos(ud) * y - sin(ud) * z,
            sin(ud) * y + cos(ud) * z,
        )
        
        # Вращение вокруг Y (yaw / left-right)
        x, y, z = (
            cos(lr) * x - sin(lr) * z,
            y,
            sin(lr) * x + cos(lr) * z,
        )
        
        # Вращение вокруг Z (roll / rotation)
        x, y, z = (
            cos(rot) * x - sin(rot) * y,
            sin(rot) * x + cos(rot) * y,
            z,
        )
        
        # Проекция обратно на плоскость z = z_fix
        if abs(z) < 1e-10:
            z = 1e-10  # Защита от деления на ноль
        z_scale = self.z_fix / z
        x_out = x * z_scale
        y_out = y * z_scale
        
        return x_out, y_out
    
    def _transform_frame_ud(self, frame, ud_deg):
        """Трансформация кадра по pitch (up/down) с коррекцией масштаба."""
        # Трансформируем все 4 угла
        transformed = []
        for x, y in frame:
            tx, ty = self._proj_trans_point(ud_deg, 0, 0, x, y)
            transformed.append((tx, ty))
        
        # Коррекция масштаба и сдвига
        # Вычисляем как изменилась центральная линия
        scx, cy = self._proj_trans_point(ud_deg, 0, 0, 100, 0)
        
        # Центрируем (убираем сдвиг)
        result = []
        for tx, ty in transformed:
            result.append((tx, ty - cy))
        
        # Масштабируем (сохраняем пропорции)
        scale = 100 / scx if abs(scx) > 1e-6 else 1.0
        result = [(x * scale, y * scale) for x, y in result]
        
        return result
    
    def _transform_frame_lr(self, frame, lr_deg):
        """Трансформация кадра по yaw (left/right) с коррекцией масштаба."""
        # Трансформируем все 4 угла
        transformed = []
        for x, y in frame:
            tx, ty = self._proj_trans_point(0, lr_deg, 0, x, y)
            transformed.append((tx, ty))
        
        # Коррекция масштаба и сдвига
        cx, scy = self._proj_trans_point(0, lr_deg, 0, 0, 100)
        
        # Центрируем
        result = []
        for tx, ty in transformed:
            result.append((tx - cx, ty))
        
        # Масштабируем
        scale = 100 / scy if abs(scy) > 1e-6 else 1.0
        result = [(x * scale, y * scale) for x, y in result]
        
        return result
    
    def _transform_frame_rot(self, frame, rot_deg):
        """Трансформация кадра по roll (rotation) - без коррекции масштаба."""
        result = []
        for x, y in frame:
            tx, ty = self._proj_trans_point(0, 0, rot_deg, x, y)
            result.append((tx, ty))
        return result
    
    def compute_perspective_corners(self, pitch_deg, yaw_deg, roll_deg):
        """
        Вычисляет координаты углов после перспективной трансформации.
        
        Это основная функция - она возвращает 4 точки для cv2.getPerspectiveTransform()
        
        Args:
            pitch_deg: наклон вверх/вниз в градусах
            yaw_deg: поворот влево/вправо в градусах
            roll_deg: вращение в плоскости в градусах
        
        Returns:
            numpy array shape (4, 2) с координатами углов [UL, UR, LL, LR]
        """
        # Начальные углы (относительно центра)
        frame = [
            (0 - self.center_x, 0 - self.center_y),           # Upper Left
            (self.width - self.center_x, 0 - self.center_y),  # Upper Right
            (0 - self.center_x, self.height - self.center_y), # Lower Left
            (self.width - self.center_x, self.height - self.center_y),  # Lower Right
        ]
        
        # Применяем трансформации последовательно (как в GIMP)
        frame = self._transform_frame_ud(frame, pitch_deg)
        frame = self._transform_frame_lr(frame, yaw_deg)
        frame = self._transform_frame_rot(frame, roll_deg)
        
        # Возвращаем координаты обратно к абсолютным
        result = []
        for x, y in frame:
            result.append([x + self.center_x, y + self.center_y])
        
        return np.array(result, dtype=np.float32)
    
    def get_perspective_matrix(self, pitch_deg, yaw_deg, roll_deg):
        """
        Получает матрицу перспективной трансформации для OpenCV.
        
        Returns:
            3x3 матрица гомографии для cv2.warpPerspective()
        """
        # Исходные углы
        src_pts = np.array([
            [0, 0],
            [self.width, 0],
            [0, self.height],
            [self.width, self.height]
        ], dtype=np.float32)
        
        # Трансформированные углы
        dst_pts = self.compute_perspective_corners(pitch_deg, yaw_deg, roll_deg)
        
        # Вычисляем матрицу гомографии
        M = cv2.getPerspectiveTransform(src_pts, dst_pts)
        
        return M


# ============================================================
# DARKTABLE-STYLE PERSPECTIVE CORRECTION
# Основано на модуле rotate and perspective из Darktable
# ============================================================

class DarktablePerspective:
    """
    Коррекция перспективы в стиле Darktable.
    
    Использует матрицу внутренних параметров камеры (K) и
    матрицу вращения (R) для построения гомографии H = K * R * K^-1
    """
    
    def __init__(self, width, height):
        self.width = width
        self.height = height
        
        # Фокусное расстояние (в пикселях) - немного больше диагонали
        self.focal = 1.2 * max(width, height)
        
        # Матрица внутренних параметров камеры
        self.K = np.array([
            [self.focal, 0, width / 2.0],
            [0, self.focal, height / 2.0],
            [0, 0, 1]
        ], dtype=np.float32)
        
        self.K_inv = np.linalg.inv(self.K)
    
    @staticmethod
    def _rotation_x(theta):
        """Матрица вращения вокруг оси X (pitch)"""
        c, s = cos(theta), sin(theta)
        return np.array([
            [1, 0, 0],
            [0, c, -s],
            [0, s, c]
        ], dtype=np.float32)
    
    @staticmethod
    def _rotation_y(theta):
        """Матрица вращения вокруг оси Y (yaw)"""
        c, s = cos(theta), sin(theta)
        return np.array([
            [c, 0, s],
            [0, 1, 0],
            [-s, 0, c]
        ], dtype=np.float32)
    
    @staticmethod
    def _rotation_z(theta):
        """Матрица вращения вокруг оси Z (roll)"""
        c, s = cos(theta), sin(theta)
        return np.array([
            [c, -s, 0],
            [s, c, 0],
            [0, 0, 1]
        ], dtype=np.float32)
    
    def get_homography(self, yaw_deg, pitch_deg, roll_deg):
        """
        Строит матрицу гомографии H = K * R * K^-1
        
        Args:
            yaw_deg: поворот влево/вправо (горизонтальный keystone)
            pitch_deg: наклон вверх/вниз (вертикальный keystone)
            roll_deg: вращение в плоскости
        
        Returns:
            3x3 матрица гомографии
        """
        # Конвертируем в радианы
        yaw = radians(yaw_deg)
        pitch = radians(pitch_deg)
        roll = radians(roll_deg)
        
        # Комбинированная матрица вращения R = Ry * Rx * Rz
        R = self._rotation_y(yaw) @ self._rotation_x(pitch) @ self._rotation_z(roll)
        
        # Гомография
        H = self.K @ R @ self.K_inv
        
        return H.astype(np.float32)
    
    def normalize_homography(self, H):
        """
        Нормализует гомографию, фиксируя центр изображения.
        Предотвращает "улёт" изображения при больших углах.
        """
        cx, cy = self.width / 2.0, self.height / 2.0
        center_pt = np.array([cx, cy, 1.0])
        
        # Где оказывается центр после трансформации
        transformed = H @ center_pt
        transformed /= transformed[2]
        
        # Сдвиг для возврата центра
        tx = cx - transformed[0]
        ty = cy - transformed[1]
        
        T = np.array([
            [1, 0, tx],
            [0, 1, ty],
            [0, 0, 1]
        ], dtype=np.float32)
        
        return T @ H


# ============================================================
# AUTOMATIC LINE DETECTION (как в Lightroom Upright)
# ============================================================

class AutoPerspective:
    """
    Автоматическое определение перспективы по линиям.
    Аналог Lightroom Auto Upright / Darktable automatic perspective.
    """
    
    def __init__(self, image):
        """
        Args:
            image: numpy array (H, W, 3) RGB изображение
        """
        self.image = image
        self.height, self.width = image.shape[:2]
        self.lines = []
        self.vertical_lines = []
        self.horizontal_lines = []
    
    def detect_lines(self, min_length_ratio=0.1):
        """
        Детектирует линии на изображении.
        
        Args:
            min_length_ratio: минимальная длина линии как доля от размера изображения
        """
        # Конвертируем в grayscale
        gray = cv2.cvtColor(self.image, cv2.COLOR_RGB2GRAY)
        
        # Bilateral filter для сохранения краёв
        gray = cv2.bilateralFilter(gray, 9, 75, 75)
        
        # Детекция краёв
        edges = cv2.Canny(gray, 30, 100, apertureSize=3)
        
        # Морфологические операции
        kernel = np.ones((3, 3), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=1)
        edges = cv2.erode(edges, kernel, iterations=1)
        
        # Hough Lines
        min_length = int(min(self.height, self.width) * min_length_ratio)
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=50,
                               minLineLength=min_length, maxLineGap=20)
        
        if lines is None:
            return
        
        # Классифицируем линии
        for line in lines:
            x1, y1, x2, y2 = line[0]
            length = sqrt((x2-x1)**2 + (y2-y1)**2)
            angle = degrees(atan2(y2 - y1, x2 - x1))
            
            line_data = {
                'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2,
                'length': length,
                'angle': angle
            }
            
            self.lines.append(line_data)
            
            # Классификация
            abs_angle = abs(angle)
            if 60 < abs_angle < 120:  # Вертикальные
                self.vertical_lines.append(line_data)
            elif abs_angle < 30 or abs_angle > 150:  # Горизонтальные
                self.horizontal_lines.append(line_data)
    
    def estimate_correction(self):
        """
        Оценивает необходимую коррекцию на основе детектированных линий.
        
        Returns:
            dict с ключами 'pitch', 'yaw', 'roll' (в градусах)
        """
        pitch = 0.0
        yaw = 0.0
        roll = 0.0
        
        # Анализ вертикальных линий для pitch
        if self.vertical_lines:
            # Средний угол отклонения от вертикали
            angles = []
            weights = []
            for line in self.vertical_lines:
                angle = line['angle']
                # Нормализуем к вертикали (90 или -90)
                if angle > 0:
                    deviation = angle - 90
                else:
                    deviation = angle + 90
                angles.append(deviation)
                weights.append(line['length'])
            
            # Взвешенное среднее
            if weights:
                total_weight = sum(weights)
                pitch = sum(a * w for a, w in zip(angles, weights)) / total_weight
        
        # Анализ горизонтальных линий для roll
        if self.horizontal_lines:
            angles = []
            weights = []
            for line in self.horizontal_lines:
                angle = line['angle']
                # Нормализуем к горизонтали (0 или 180)
                if abs(angle) > 90:
                    deviation = angle - 180 if angle > 0 else angle + 180
                else:
                    deviation = angle
                angles.append(deviation)
                weights.append(line['length'])
            
            if weights:
                total_weight = sum(weights)
                roll = sum(a * w for a, w in zip(angles, weights)) / total_weight
        
        return {
            'pitch': np.clip(pitch, -45, 45),
            'yaw': np.clip(yaw, -45, 45),
            'roll': np.clip(roll, -45, 45)
        }


# ============================================================
# GUIDED UPRIGHT (как в Lightroom)
# ============================================================

class GuidedUpright:
    """
    Коррекция перспективы по нарисованным пользователем линиям.
    Аналог Lightroom Guided Upright.
    """
    
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.guides = []  # [(x1, y1, x2, y2, type), ...]
    
    def add_guide(self, x1, y1, x2, y2, guide_type='auto'):
        """
        Добавляет направляющую линию.
        
        Args:
            x1, y1, x2, y2: координаты линии
            guide_type: 'vertical', 'horizontal', или 'auto' (определить автоматически)
        """
        if guide_type == 'auto':
            angle = abs(degrees(atan2(y2 - y1, x2 - x1)))
            if 45 < angle < 135:
                guide_type = 'vertical'
            else:
                guide_type = 'horizontal'
        
        length = sqrt((x2-x1)**2 + (y2-y1)**2)
        
        self.guides.append({
            'x1': x1, 'y1': y1,
            'x2': x2, 'y2': y2,
            'type': guide_type,
            'length': length
        })
    
    def clear_guides(self):
        """Очищает все направляющие."""
        self.guides = []
    
    def solve(self):
        """
        Решает систему для нахождения оптимальных углов коррекции.
        
        Использует scipy.optimize.minimize для минимизации отклонения
        линий от вертикали/горизонтали.
        
        Returns:
            dict с ключами 'yaw', 'pitch', 'roll' (в градусах)
        """
        if len(self.guides) < 1:
            return {'yaw': 0, 'pitch': 0, 'roll': 0}
        
        try:
            from scipy.optimize import minimize
        except ImportError:
            # Fallback без scipy
            return self._solve_simple()
        
        dt = DarktablePerspective(self.width, self.height)
        
        def objective(params):
            yaw, pitch, roll = params
            H = dt.get_homography(yaw, pitch, roll)
            
            total_error = 0.0
            
            for guide in self.guides:
                # Трансформируем точки линии
                p1 = np.array([guide['x1'], guide['y1'], 1.0])
                p2 = np.array([guide['x2'], guide['y2'], 1.0])
                
                q1 = H @ p1
                q1 /= q1[2]
                q2 = H @ p2
                q2 /= q2[2]
                
                # Угол трансформированной линии
                dx = q2[0] - q1[0]
                dy = q2[1] - q1[1]
                angle = degrees(atan2(dy, dx))
                
                if guide['type'] == 'vertical':
                    # Цель: 90° или -90°
                    deviation = abs(abs(angle) - 90)
                else:
                    # Цель: 0° или 180°
                    deviation = abs(angle)
                    if deviation > 90:
                        deviation = abs(180 - deviation)
                
                total_error += deviation ** 2 * guide['length']
            
            return total_error
        
        # Оптимизация
        x0 = [0.0, 0.0, 0.0]
        bounds = [(-60, 60), (-60, 60), (-45, 45)]
        
        result = minimize(objective, x0, method='L-BFGS-B', bounds=bounds, tol=1e-5)
        
        return {
            'yaw': result.x[0],
            'pitch': result.x[1],
            'roll': result.x[2]
        }
    
    def _solve_simple(self):
        """Простое решение без scipy."""
        pitch = 0.0
        roll = 0.0
        
        for guide in self.guides:
            angle = degrees(atan2(guide['y2'] - guide['y1'], guide['x2'] - guide['x1']))
            
            if guide['type'] == 'vertical':
                if angle > 0:
                    pitch += (angle - 90) * guide['length']
                else:
                    pitch += (angle + 90) * guide['length']
            else:
                roll += angle * guide['length']
        
        total_v = sum(g['length'] for g in self.guides if g['type'] == 'vertical') or 1
        total_h = sum(g['length'] for g in self.guides if g['type'] == 'horizontal') or 1
        
        return {
            'yaw': 0,
            'pitch': np.clip(pitch / total_v, -45, 45),
            'roll': np.clip(roll / total_h, -45, 45)
        }


# ============================================================
# ВЫСОКОУРОВНЕВЫЙ API
# ============================================================

def apply_perspective_correction(image, pitch=0, yaw=0, roll=0, 
                                 method='darktable', focal_length=50):
    """
    Применяет коррекцию перспективы к изображению.
    
    Args:
        image: numpy array (H, W, 3)
        pitch: наклон вверх/вниз в градусах
        yaw: поворот влево/вправо в градусах
        roll: вращение в плоскости в градусах
        method: 'gimp' или 'darktable'
        focal_length: фокусное расстояние в мм (для GIMP метода)
    
    Returns:
        numpy array - скорректированное изображение
    """
    h, w = image.shape[:2]
    
    if method == 'gimp':
        engine = GIMPPerspective(w, h, focal_length)
        M = engine.get_perspective_matrix(pitch, yaw, roll)
    else:  # darktable
        engine = DarktablePerspective(w, h)
        M = engine.get_homography(yaw, pitch, roll)
        M = engine.normalize_homography(M)
    
    # Применяем трансформацию
    result = cv2.warpPerspective(image, M, (w, h),
                                 flags=cv2.INTER_LANCZOS4,
                                 borderMode=cv2.BORDER_CONSTANT,
                                 borderValue=(0, 0, 0))
    
    return result


def auto_perspective_correction(image):
    """
    Автоматическая коррекция перспективы.
    
    Args:
        image: numpy array (H, W, 3)
    
    Returns:
        tuple: (corrected_image, correction_params)
    """
    auto = AutoPerspective(image)
    auto.detect_lines()
    params = auto.estimate_correction()
    
    corrected = apply_perspective_correction(
        image, 
        pitch=params['pitch'],
        yaw=params['yaw'],
        roll=params['roll']
    )
    
    return corrected, params


# ============================================================
# ТЕСТИРОВАНИЕ
# ============================================================

if __name__ == '__main__':
    print("Perspective Engine - модуль коррекции перспективы")
    print("=" * 50)
    print()
    print("Доступные классы:")
    print("  - GIMPPerspective: коррекция в стиле GIMP EZ-Perspective")
    print("  - DarktablePerspective: коррекция в стиле Darktable")
    print("  - AutoPerspective: автоматическое определение")
    print("  - GuidedUpright: коррекция по направляющим")
    print()
    print("Функции:")
    print("  - apply_perspective_correction(image, pitch, yaw, roll)")
    print("  - auto_perspective_correction(image)")
    print()
    print("Пример использования:")
    print("  from perspective_engine import apply_perspective_correction")
    print("  result = apply_perspective_correction(img, pitch=5, yaw=-3, roll=2)")
