#!/bin/bash

echo "Обновление системы..."
sudo apt update -y
sudo apt upgrade -y

# Установка необходимых зависимостей
echo "Установка зависимостей..."
sudo apt install -y wget tar openjdk-8-jdk curl unzip python3 python3-pip ttyd

echo "Установка Python 3.8..."
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install -y python3.8 python3.8-distutils

# Установка pip для Python 3.8
curl https://bootstrap.pypa.io/get-pip.py  -o get-pip.py
sudo python3.8 get-pip.py
rm get-pip.py
# Настройка JAVA_HOME
echo "Настройка JAVA_HOME..."
java_home_path=$(readlink -f /usr/bin/java | sed 's:bin/java::')
echo "export JAVA_HOME=$java_home_path" >> ~/.bashrc
echo "export PATH=\$PATH:\$JAVA_HOME/bin" >> ~/.bashrc  # Добавляем Java в PATH

# Проверка версии Java
source ~/.bashrc  # Обновляем текущую сессию
java_version=$(java -version 2>&1 | grep version | awk '{print $3}' | tr -d '"')
if [[ $java_version != *"1.8"* ]]; then
    echo "Требуется Java 8. Установите правильную версию Java."
    exit 1
fi

# Установка OpenDaylight Beryllium
echo "Установка OpenDaylight..."
sudo mkdir -p /opt/opendaylight
cd /opt/opendaylight
wget https://nexus.opendaylight.org/content/groups/public/org/opendaylight/integration/distribution-karaf/0.4.0-Beryllium/distribution-karaf-0.4.0-Beryllium.tar.gz
sudo tar -xvzf distribution-karaf-0.4.0-Beryllium.tar.gz
sudo rm distribution-karaf-0.4.0-Beryllium.tar.gz
sudo chown -R vagrant:vagrant /opt/opendaylight
sudo chmod -R 755 /opt/opendaylight

# Установка features для OpenDaylight
echo "Установка features для OpenDaylight..."
cd /opt/opendaylight/distribution-karaf-0.4.0-Beryllium/bin
./karaf <<EOF
feature:install odl-restconf
feature:install odl-l2switch-switch
feature:install odl-mdsal-apidocs
feature:install odl-dlux-all
feature:install odl-openflowplugin-all
logout
EOF

# Установка ONOS
echo "Установка ONOS..."
cd /opt
sudo mkdir -p onos
cd onos
wget https://repo1.maven.org/maven2/org/onosproject/onos-releases/1.15.0/onos-1.15.0.tar.gz
sudo tar -xvzf onos-1.15.0.tar.gz
sudo rm onos-1.15.0.tar.gz
sudo chown -R vagrant:vagrant /opt/onos
sudo chmod -R 755 /opt/onos

# Добавление переменных окружения для ONOS
echo "export ONOS_ROOT=/opt/onos" >> ~/.bashrc
echo "export ONOS_APPS=drivers,openflow,proxyarp,roadm,fwd,gui2" >> ~/.bashrc
source ~/.bashrc

# Установка Ruy (Python-фреймворк для SDN)
echo "Установка Ruy..."
pip3 install ryu

echo "Установка завершена! Переменная JAVA_HOME добавлена в ~/.bashrc"
