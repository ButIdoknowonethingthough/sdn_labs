#!/bin/bash

# Этот скрипт устанавливает Mininet на Ubuntu в VirtualBox.
# Перед запуском убедитесь, что система обновлена и имеет доступ к интернету.

echo "=== Начинаем установку Mininet ==="

# 1. Обновление системы
echo "=== Обновление пакетов ==="
sudo apt update && sudo apt upgrade -y

# 2. Установка необходимых зависимостей
echo "=== Установка зависимостей ==="
sudo apt install -y git python3 python3-pip build-essential cmake

# 3. Клонирование репозитория Mininet
echo "=== Клонирование репозитория Mininet ==="
if [ ! -d "mininet" ]; then
    git clone https://github.com/mininet/mininet.git
else
    echo "Репозиторий Mininet уже клонирован."
fi

# 4. Переход в директорию Mininet
cd mininet || { echo "Ошибка: Не удалось найти директорию Mininet."; exit 1; }

# 5. Выбор версии Mininet (по умолчанию последняя стабильная)
echo "=== Установка Mininet ==="
sudo util/install.sh -a

# 6. Проверка установки
echo "=== Проверка установки Mininet ==="
mn --version
if [ $? -eq 0 ]; then
    echo "Mininet успешно установлен!"
else
    echo "Ошибка: Mininet не установлен. Проверьте логи выше."
    exit 1
fi

# 7. Дополнительные настройки (опционально)
echo "=== Установка дополнительных компонентов (Open vSwitch, Wireshark) ==="
sudo apt install -y openvswitch-switch wireshark ttyd

# 8. Завершение
echo "=== Установка завершена ==="
echo "Теперь вы можете запустить Mininet с помощью команды 'sudo mn'."
