#!/bin/bash

# Обновление системы
echo "Обновление системы..."
sudo apt update -y
sudo apt upgrade -y

# Установка необходимых зависимостей
echo "Установка зависимостей..."
sudo apt install -y wget tar openjdk-8-jdk

# Проверка версии Java
java_version=$(java -version 2>&1 | grep version | awk '{print $3}' | tr -d '"')
if [[ $java_version != *"1.8"* ]]; then
    echo "Требуется Java 8. Установите правильную версию Java."
    exit 1
fi

# Создание директории для OpenDaylight
echo "Создание директории для OpenDaylight..."
sudo mkdir -p /opt/opendaylight
cd /opt/opendaylight

# Загрузка дистрибутива ODL
echo "Загрузка OpenDaylight Beryllium..."
wget https://nexus.opendaylight.org/content/groups/public/org/opendaylight/integration/distribution-karaf/0.4.0-Beryllium/distribution-karaf-0.4.0-Beryllium.tar.gz

# Распаковка архива
echo "Распаковка дистрибутива..."
sudo tar -xvzf distribution-karaf-0.4.0-Beryllium.tar.gz
sudo rm distribution-karaf-0.4.0-Beryllium.tar.gz

sudo chown -R vagrant:vagrant /opt/opendaylight
sudo chmod -R 755 /opt/opendaylight


echo "Запуск контроллера"
cd /opt/opendaylight/distribution-karaf-0.4.0-Beryllium

