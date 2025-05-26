# sdn_labs

Этот репозиторий содержит `Vagrantfile` для автоматической развёртки 2 виртуальных машины с Ubuntu 22.04. На 1 машине будет установлен sdn-contoller OpenDayLight, на 2 машине будет установлен Mininet.

## Как использовать

1. Установите [Vagrant](https://drive.google.com/file/d/135jOX1ZB2_PfssNw6KiVQj-vvbXKZOR1/view?usp=sharing) и [VirtualBox](https://www.virtualbox.org/).
2. Клонируйте репозиторий:
   ```bash
   git clone https://github.com/ButIdoknowonethingthough/sdn_labs.git
   cd sdn_labs
   ```
3. Запустите виртуальную машину:
   ```bash
   vagrant up
   ```
4. После завершения настройки подключитесь к VM по SSH:
   ```bash
   vagrant ssh "sdn-controller"
   vagrant ssh "mininet-host"
   ```

5. Для повторного запуска используйте:
   ```bash
   vagrant up --no-provision"
   
   ```

## Дополнительные команды
- Остановить VM: `vagrant halt`
- Удалить VM: `vagrant destroy`
