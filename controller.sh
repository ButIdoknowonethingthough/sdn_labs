echo "Обновление системы..."
sudo apt update -y
sudo apt upgrade -y

# Установка необходимых зависимостей
echo "Установка зависимостей..."
sudo apt install -y wget tar openjdk-8-jdk curl unzip python3 python3-pip

# Проверка версии Java
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
echo "export ONOS_APPS=drivers,openflow,proxy,roadm,fwd" >> ~/.bashrc
source ~/.bashrc

# Установка Ruy (Python-фреймворк для SDN)
echo "Установка Ruy..."
pip3 install ryu
