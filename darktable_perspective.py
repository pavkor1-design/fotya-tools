#!/usr/bin/env python3
"""
Darktable Perspective Correction - Точная реализация алгоритма из Darktable

Исходный код: https://github.com/darktable-org/darktable/blob/master/src/iop/ashift.c
Документация: https://darktable-org.github.io/dtdocs/en/module-reference/processing-modules/rotate-perspective/

Алгоритм основан на программе ShiftN от Marcus Hebel (http://www.shiftn.de/)

Параметры модуля Darktable:
- rotation: поворот изображения (градусы)
- lensshift_v: вертикальный сдвиг объектива (keystone вертикальный)
- lensshift_h: горизонтальный сдвиг объектива (keystone горизонтальный)
- shear: сдвиг/наклон
- f_length_kb: фокусное расстояние (по умолчанию 28mm)
- orthocorr: ортогональная коррекция (0-100%)
- aspect: соотношение сторон

Автор адаптации: Fotya Tools
"""

import numpy as np
from math import pi, sin, cos, sqrt, exp, atan, radians, degrees
import cv2


# Константы из Darktable
DEFAULT_F_LENGTH = 28.0  # Фокусное расстояние по умолчанию (мм)


def deg2rad(deg):
    """Конвертация градусов в радианы"""
    return deg * pi / 180.0


def mat3mul(result, m1, m2):
    """Умножение матриц 3x3"""
    for i in range(3):
        for j in range(3):
            result[i][j] = sum(m1[i][k] * m2[k][j] for k in range(3))


def mat3mulv(result, m, v):
    """Умножение матрицы 3x3 на вектор"""
    for i in range(3):
        result[i] = sum(m[i][j] * v[j] for j in range(3))


def mat3inv(result, m):
    """Инверсия матрицы 3x3"""
    try:
        m_np = np.array(m, dtype=np.float64)
        inv = np.linalg.inv(m_np)
        for i in range(3):
            for j in range(3):
                result[i][j] = inv[i][j]
        return False  # Success
    except:
        return True  # Error


class DarktableAshift:
    """
    Точная реализация модуля ashift (rotate and perspective) из Darktable.
    
    Алгоритм выполняет 10 шагов трансформации:
    1. Flip x/y координат (Darktable использует y:x:1 формат)
    2. Поворот вокруг центра
    3. Применение shear (сдвига)
    4. Вертикальный lens shift
    5. Горизонтальное сжатие (компенсация)
    6. Flip x/y обратно
    7. Горизонтальный lens shift
    8. Вертикальное сжатие (компенсация)
    9. Применение aspect ratio
    10. Коррекция смещения (чтобы не было отрицательных координат)
    """
    
    def __init__(self, width, height, focal_length=DEFAULT_F_LENGTH):
        """
        Args:
            width: ширина изображения
            height: высота изображения
            focal_length: фокусное расстояние в мм (по умолчанию 28mm как в Darktable)
        """
        self.width = width
        self.height = height
        self.f_length_kb = focal_length
    
    def _homography(self, rotation, shift_v, shift_h, shear=0.0, 
                    orthocorr=0.0, aspect=1.0, forward=True):
        """
        Вычисляет матрицу гомографии точно как в Darktable ashift.c
        
        Args:
            rotation: угол поворота в градусах
            shift_v: вертикальный lens shift (keystone вертикальный)
            shift_h: горизонтальный lens shift (keystone горизонтальный)
            shear: параметр сдвига
            orthocorr: ортогональная коррекция (0-100)
            aspect: соотношение сторон
            forward: True для прямой трансформации, False для обратной
        
        Returns:
            numpy array 3x3 - матрица гомографии
        """
        u = float(self.width)
        v = float(self.height)
        
        phi = deg2rad(rotation)
        cosi = cos(phi)
        sini = sin(phi)
        ascale = sqrt(aspect)
        
        # Параметры из ShiftN
        f_global = self.f_length_kb
        
        # Вертикальный lens shift
        horifac = 1.0 - orthocorr / 100.0
        exppa_v = exp(shift_v)
        fdb_v = f_global / (14.4 + (v / u - 1) * 7.2)
        rad_v = fdb_v * (exppa_v - 1.0) / (exppa_v + 1.0)
        alpha_v = max(-1.5, min(1.5, atan(rad_v)))  # CLAMP
        rt_v = sin(0.5 * alpha_v)
        r_v = max(0.1, 2.0 * (horifac - 1.0) * rt_v * rt_v + 1.0)
        
        # Горизонтальный lens shift
        vertifac = 1.0 - orthocorr / 100.0
        exppa_h = exp(shift_h)
        fdb_h = f_global / (14.4 + (u / v - 1) * 7.2)
        rad_h = fdb_h * (exppa_h - 1.0) / (exppa_h + 1.0)
        alpha_h = max(-1.5, min(1.5, atan(rad_h)))  # CLAMP
        rt_h = sin(0.5 * alpha_h)
        r_h = max(0.1, 2.0 * (vertifac - 1.0) * rt_h * rt_h + 1.0)
        
        # Инициализация матриц
        def zeros():
            return [[0.0] * 3 for _ in range(3)]
        
        def identity():
            m = zeros()
            m[0][0] = m[1][1] = m[2][2] = 1.0
            return m
        
        def multiply(m1, m2):
            result = zeros()
            mat3mul(result, m1, m2)
            return result
        
        # Step 1: flip x and y coordinates (Darktable uses y:x:1 format)
        minput = zeros()
        minput[0][1] = 1.0
        minput[1][0] = 1.0
        minput[2][2] = 1.0
        
        # Step 2: rotation around center
        mwork = zeros()
        mwork[0][0] = cosi
        mwork[0][1] = -sini
        mwork[1][0] = sini
        mwork[1][1] = cosi
        mwork[0][2] = -0.5 * v * cosi + 0.5 * u * sini + 0.5 * v
        mwork[1][2] = -0.5 * v * sini - 0.5 * u * cosi + 0.5 * u
        mwork[2][2] = 1.0
        
        moutput = multiply(mwork, minput)
        
        # Step 3: apply shearing
        mwork = zeros()
        mwork[0][0] = 1.0
        mwork[0][1] = shear
        mwork[1][1] = 1.0
        mwork[1][0] = shear
        mwork[2][2] = 1.0
        
        minput = moutput
        moutput = multiply(mwork, minput)
        
        # Step 4: apply vertical lens shift
        mwork = zeros()
        mwork[0][0] = exppa_v
        mwork[1][0] = 0.5 * ((exppa_v - 1.0) * u) / v
        mwork[1][1] = 2.0 * exppa_v / (exppa_v + 1.0)
        mwork[1][2] = -0.5 * ((exppa_v - 1.0) * u) / (exppa_v + 1.0)
        mwork[2][0] = (exppa_v - 1.0) / v
        mwork[2][2] = 1.0
        
        minput = moutput
        moutput = multiply(mwork, minput)
        
        # Step 5: horizontal compression
        mwork = zeros()
        mwork[0][0] = 1.0
        mwork[1][1] = r_v
        mwork[1][2] = 0.5 * u * (1.0 - r_v)
        mwork[2][2] = 1.0
        
        minput = moutput
        moutput = multiply(mwork, minput)
        
        # Step 6: flip x and y back
        mwork = zeros()
        mwork[0][1] = 1.0
        mwork[1][0] = 1.0
        mwork[2][2] = 1.0
        
        minput = moutput
        moutput = multiply(mwork, minput)
        
        # Step 7: apply horizontal lens shift
        mwork = zeros()
        mwork[0][0] = exppa_h
        mwork[1][0] = 0.5 * ((exppa_h - 1.0) * v) / u
        mwork[1][1] = 2.0 * exppa_h / (exppa_h + 1.0)
        mwork[1][2] = -0.5 * ((exppa_h - 1.0) * v) / (exppa_h + 1.0)
        mwork[2][0] = (exppa_h - 1.0) / u
        mwork[2][2] = 1.0
        
        minput = moutput
        moutput = multiply(mwork, minput)
        
        # Step 8: vertical compression
        mwork = zeros()
        mwork[0][0] = 1.0
        mwork[1][1] = r_h
        mwork[1][2] = 0.5 * v * (1.0 - r_h)
        mwork[2][2] = 1.0
        
        minput = moutput
        moutput = multiply(mwork, minput)
        
        # Step 9: apply aspect ratio scaling
        mwork = zeros()
        mwork[0][0] = 1.0 * ascale
        mwork[1][1] = 1.0 / ascale
        mwork[2][2] = 1.0
        
        minput = moutput
        moutput = multiply(mwork, minput)
        
        # Step 10: find x/y offsets and apply correction
        umin = float('inf')
        vmin = float('inf')
        
        # Visit all four corners
        for y in [0, self.height - 1]:
            for x in [0, self.width - 1]:
                pi = [float(x), float(y), 1.0]
                po = [0.0, 0.0, 0.0]
                mat3mulv(po, moutput, pi)
                if po[2] != 0:
                    umin = min(umin, po[0] / po[2])
                    vmin = min(vmin, po[1] / po[2])
        
        mwork = identity()
        mwork[0][2] = -umin
        mwork[1][2] = -vmin
        
        minput = moutput
        moutput = multiply(mwork, minput)
        
        # Convert to numpy and optionally invert
        homograph = np.array(moutput, dtype=np.float32)
        
        if not forward:
            try:
                homograph = np.linalg.inv(homograph)
            except:
                homograph = np.eye(3, dtype=np.float32)
        
        return homograph
    
    def get_homography(self, rotation=0, vertical=0, horizontal=0, 
                       shear=0, orthocorr=0, aspect=1.0, forward=True):
        """
        Получить матрицу гомографии с удобными параметрами.
        
        Args:
            rotation: поворот в градусах
            vertical: вертикальная коррекция (keystone) -100..100
            horizontal: горизонтальная коррекция (keystone) -100..100
            shear: сдвиг -100..100
            orthocorr: ортогональная коррекция 0..100
            aspect: соотношение сторон
            forward: True для прямой трансформации
        
        Returns:
            numpy array 3x3
        """
        # Конвертируем параметры в формат Darktable
        # В Darktable shift_v и shift_h - это экспоненциальные параметры
        # Наши слайдеры -100..100 нужно преобразовать
        shift_v = vertical / 50.0  # Масштабируем для разумного диапазона
        shift_h = horizontal / 50.0
        shear_val = shear / 100.0
        
        return self._homography(rotation, shift_v, shift_h, shear_val, 
                               orthocorr, aspect, forward)
    
    def apply(self, image, rotation=0, vertical=0, horizontal=0,
              shear=0, orthocorr=0, aspect=1.0):
        """
        Применить коррекцию перспективы к изображению.
        
        Args:
            image: numpy array (H, W, 3)
            rotation: поворот в градусах
            vertical: вертикальная коррекция -100..100
            horizontal: горизонтальная коррекция -100..100
            shear: сдвиг -100..100
            orthocorr: ортогональная коррекция 0..100
            aspect: соотношение сторон
        
        Returns:
            numpy array - скорректированное изображение
        """
        H = self.get_homography(rotation, vertical, horizontal, 
                                shear, orthocorr, aspect, forward=False)
        
        result = cv2.warpPerspective(image, H, (self.width, self.height),
                                     flags=cv2.INTER_LANCZOS4,
                                     borderMode=cv2.BORDER_CONSTANT,
                                     borderValue=(0, 0, 0))
        return result


def is_neutral(rotation, shift_v, shift_h, shear=0, aspect=1.0):
    """
    Проверяет, являются ли параметры нейтральными (как в Darktable _isneutral)
    """
    eps = 1e-4
    return (abs(rotation) < eps and 
            abs(shift_v) < eps and 
            abs(shift_h) < eps and
            abs(shear) < eps and
            abs(aspect - 1.0) < eps)


# ============================================================
# СРАВНЕНИЕ С ТЕКУЩЕЙ РЕАЛИЗАЦИЕЙ
# ============================================================

def compare_implementations():
    """
    Сравнивает реализацию Darktable с текущей реализацией в photo_tools.py
    
    Основные отличия:
    
    1. ФОКУСНОЕ РАССТОЯНИЕ:
       - Darktable: DEFAULT_F_LENGTH = 28.0mm
       - Текущая: f = sqrt(w*w + h*h) * 0.8 (80% диагонали в пикселях)
       
    2. ФОРМАТ КООРДИНАТ:
       - Darktable: использует (y:x:1) формат, требует flip
       - Текущая: использует (x:y:1) напрямую
       
    3. LENS SHIFT:
       - Darktable: экспоненциальная функция exp(shift)
       - Текущая: линейное вращение через матрицу R
       
    4. КОМПЕНСАЦИЯ:
       - Darktable: отдельные шаги сжатия (r_v, r_h)
       - Текущая: нормализация центра
       
    5. SHEAR:
       - Darktable: есть параметр shear
       - Текущая: нет параметра shear
       
    6. ORTHOCORR:
       - Darktable: есть ортогональная коррекция
       - Текущая: нет
    """
    print("=" * 60)
    print("СРАВНЕНИЕ РЕАЛИЗАЦИЙ КОРРЕКЦИИ ПЕРСПЕКТИВЫ")
    print("=" * 60)
    print()
    print("DARKTABLE (ashift.c):")
    print("  - Основан на ShiftN от Marcus Hebel")
    print("  - Использует экспоненциальный lens shift")
    print("  - 10 шагов трансформации")
    print("  - Фокусное расстояние: 28mm по умолчанию")
    print("  - Есть shear и orthocorr параметры")
    print()
    print("ТЕКУЩАЯ РЕАЛИЗАЦИЯ (photo_tools.py):")
    print("  - Использует матрицу вращения K * R * K^-1")
    print("  - Линейное вращение через yaw/pitch/roll")
    print("  - Фокусное расстояние: 80% диагонали")
    print("  - Нет shear и orthocorr")
    print()
    print("РЕКОМЕНДАЦИИ:")
    print("  1. Добавить параметр shear в UI")
    print("  2. Использовать экспоненциальный lens shift как в Darktable")
    print("  3. Добавить orthocorr для лучшей компенсации")
    print("  4. Использовать фокусное расстояние из EXIF или 28mm по умолчанию")


# ============================================================
# ТЕСТИРОВАНИЕ
# ============================================================

if __name__ == '__main__':
    print("Darktable Perspective Correction Module")
    print("=" * 50)
    print()
    print("Это точная реализация алгоритма из Darktable ashift.c")
    print()
    print("Параметры:")
    print("  - rotation: поворот (градусы)")
    print("  - vertical: вертикальный keystone (-100..100)")
    print("  - horizontal: горизонтальный keystone (-100..100)")
    print("  - shear: сдвиг (-100..100)")
    print("  - orthocorr: ортогональная коррекция (0..100)")
    print("  - aspect: соотношение сторон")
    print()
    print("Пример использования:")
    print("  from darktable_perspective import DarktableAshift")
    print("  dt = DarktableAshift(width, height)")
    print("  result = dt.apply(image, rotation=5, vertical=20, horizontal=-10)")
    print()
    
    compare_implementations()
