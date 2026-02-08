@echo off
chcp 65001 >nul
title PhotoTools
echo.
echo 🚀 Запуск PhotoTools...
echo.

:: Проверяем Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python не найден!
    echo.
    echo Установите Python с сайта: https://www.python.org/downloads/
    echo При установке обязательно поставьте галочку "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

:: Устанавливаем зависимости (Windows-специфичный файл)
echo 📦 Проверка зависимостей...
if exist requirements_windows.txt (
    pip install -r requirements_windows.txt --quiet 2>nul
) else (
    pip install -r requirements.txt --quiet 2>nul
)

:: Запускаем
echo ✅ Запуск приложения...
python photo_tools.py

:: Если ошибка
if errorlevel 1 (
    echo.
    echo ❌ Произошла ошибка при запуске
    pause
)
