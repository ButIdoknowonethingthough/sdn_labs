from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import asyncssh
import asyncio
import os
from pydantic import BaseModel
import shutil
import subprocess

app = FastAPI()



# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# SSH Configuration
private_key1_path = os.path.join('.vagrant', 'machines', 'sdn-controller', 'virtualbox', 'private_key')
private_key2_path = os.path.join('.vagrant', 'machines', 'mininet-host', 'virtualbox', 'private_key')

# Load private keys
try:
    with open(private_key1_path, 'r') as file:
        private_key_vm1_str = file.read()
    print("Приватный ключ VM1 успешно загружен")
except FileNotFoundError:
    print(f"Ошибка: файл приватного ключа VM1 не найден по пути: {private_key1_path}")
    private_key_vm1_str = None
except Exception as e:
    print(f"Другая ошибка при чтении файла VM1: {str(e)}")
    private_key_vm1_str = None
    
try:
    with open(private_key2_path, 'r') as file:
        private_key_vm2_str = file.read()
    print("Приватный ключ VM2 успешно загружен")
except FileNotFoundError:
    print(f"Ошибка: файл приватного ключа VM2 не найден по пути: {private_key2_path}")
    private_key_vm2_str = None
except Exception as e:
    print(f"Другая ошибка при чтении файла VM2: {str(e)}")
    private_key_vm2_str = None

# VM Configuration
vm1_ip = "192.168.56.10"
vm1_user = "vagrant"
vm2_ip = "192.168.56.20"
vm2_user = "vagrant"

async def ssh_command(vm_ip, vm_user, private_key_str, command, timeout=30):
    try:
        private_key = asyncssh.import_private_key(private_key_str.strip())
        async with asyncssh.connect(
            vm_ip, username=vm_user, client_keys=[private_key], known_hosts=None
        ) as conn:
            result = await conn.run(command, timeout=timeout)
            return f"Успешно:\n{result.stdout}" if not result.stderr else f"Ошибка: {result.stderr}"
    except Exception as e:
        return f"Ошибка SSH: {str(e)}"

async def kill_process_on_port(vm_ip, vm_user, private_key_str, port):
    command = f"sudo fuser -k {port}/tcp"
    return await ssh_command(vm_ip, vm_user, private_key_str, command)

@app.get("/")
async def control_panel(request: Request):
    return templates.TemplateResponse("control_panel.html", {"request": request})

@app.post("/start_controller")
async def start_controller(
    vm_choice: str = Form(...),
    controller_type: str = Form(...),
):
    commands = {
        "Opendaylight": "cd /opt/opendaylight/distribution-karaf-0.4.0-Beryllium && sudo ./bin/start",
        "ONOS": "cd /opt/onos/onos-2.0.0 && ./bin/onos-service start",
        "Ryu": "ryu-manager --verbose ryu.app.simple_switch_13",
    }
    
    command = commands.get(controller_type)
    if not command:
        return "Неверный тип контроллера."
    
    if vm_choice == "VM1":
        return await ssh_command(vm1_ip, vm1_user, private_key_vm1_str, command)
    elif vm_choice == "VM2":
        return await ssh_command(vm2_ip, vm2_user, private_key_vm2_str, command)
    else:
        return "Неверная VM."

@app.post("/stop_controller")
async def stop_controller(
    vm_choice: str = Form(...),
    controller_type: str = Form(...),
):
    commands = {
        "Opendaylight": "cd /opt/opendaylight/distribution-karaf-0.4.0-Beryllium && ./bin/stop",
        "ONOS": "cd /opt/onos/onos-2.0.0 && ./bin/onos-service stop",
        "Ryu": "pkill -f ryu-manager",
    }
    
    command = commands.get(controller_type)
    if not command:
        return "Неверный тип контроллера."
    
    if vm_choice == "VM1":
        result = await ssh_command(vm1_ip, vm1_user, private_key_vm1_str, command)
        if controller_type == "Opendaylight":
            await kill_process_on_port(vm1_ip, vm1_user, private_key_vm1_str, "8181")
        return result
    elif vm_choice == "VM2":
        result = await ssh_command(vm2_ip, vm2_user, private_key_vm2_str, command)
        if controller_type == "Opendaylight":
            await kill_process_on_port(vm2_ip, vm2_user, private_key_vm2_str, "8181")
        return result
    else:
        return "Неверная VM."

@app.post("/send_mininet_command")
async def send_mininet_command(
    command: str = Form(..., description="Команда для отправки в Mininet (например, pingall, h1 ping h2 и т.д.)"),
    wait_for_output: bool = Form(False, description="Ожидать вывод команды"),
    timeout: int = Form(10, description="Таймаут ожидания вывода в секундах"),
):
    """
    Отправляет команду в запущенную сессию Mininet через screen.
    """
    # Проверяем, есть ли активная screen-сессия
    check_cmd = "sudo screen -ls | grep mininet_session"
    try:
        session_status = await ssh_command(vm2_ip, vm2_user, private_key_vm2_str, check_cmd)
    except Exception as e:
        return f"Ошибка при проверке сессий: {str(e)}"
    
    if "mininet_session" not in session_status:
        return "Нет активной сессии Mininet. Сначала запустите Mininet через /run_mininet."
    
    # Подготавливаем команду для отправки
    # Экранируем кавычки и специальные символы
    escaped_command = command.replace('"', '\\"').replace('$', '\\$')
    send_cmd = f'sudo screen -S mininet_session -X stuff "{escaped_command}\n"'
    
    try:
        # Отправляем команду
        await ssh_command(vm2_ip, vm2_user, private_key_vm2_str, send_cmd)
        
        if wait_for_output:
            # Если нужно получить вывод, читаем из лога screen
            output_cmd = f"sudo tail -n 20 /var/log/screen/mininet_session.log"
            output = await ssh_command(vm2_ip, vm2_user, private_key_vm2_str, output_cmd, timeout=timeout)
            return f"Команда '{command}' отправлена. Вывод:\n{output}"
        else:
            return f"Команда '{command}' успешно отправлена в сессию Mininet."
            
    except asyncio.TimeoutError:
        return "Команда отправлена, но превышен таймаут ожидания вывода."
    except Exception as e:
        return f"Ошибка при отправке команды: {str(e)}"
    


@app.post("/run_mininet")
async def run_mininet(
    vm_choice: str = Form(...),
    command_type: str = Form(...),
    custom_command: str = Form(""),
    controller_ip: str = Form("192.168.56.10"),
    controller_port: str = Form("6633"),
):
    if vm_choice == "VM1":
        return "Mininet доступен только на VM2."
    
    # Определяем базовую команду
    if command_type == "custom":
        if not custom_command.strip():
            return "Введите команду Mininet."
        base_command = custom_command
    else:
        mininet_commands = {
            "Create Simple Topology": (
                f"mn --topo linear,3 --mac "
                f"--controller=remote,ip={controller_ip},port={controller_port} "
                "--switch ovs,protocols=OpenFlow13"
            ),
            "Ping All": (
                f"mn --controller=remote,ip={controller_ip} "
                "--topo=single,3 --test pingall"
            ),
            "Test Connectivity": (
                f"mn --controller=remote,ip={controller_ip} "
                "--topo=linear,4 --test iperf"
            ),
            "Start CLI": (
                f"mn --controller=remote,ip={controller_ip} "
                "--topo=tree,depth=2,fanout=3"
            ),
            "Clean Mininet": "mn -c",
        }
        
        base_command = mininet_commands.get(command_type)
        if not base_command:
            return "Неизвестная команда Mininet."
    
    # Для команды очистки не используем screen
    if command_type == "Clean Mininet":
        command = f"echo 'vagrant' | sudo -S {base_command}"
    else:
        # Остальные команды запускаем в screen-сессии
        command = f"echo 'vagrant' | sudo -S screen -dmS mininet_session {base_command}"
    
    try:
        result = await ssh_command(vm2_ip, vm2_user, private_key_vm2_str, command)
        
        # Проверяем статус screen-сессии для не-clean команд
        if command_type != "Clean Mininet":
            check_cmd = "sudo screen -ls | grep mininet_session"
            session_status = await ssh_command(vm2_ip, vm2_user, private_key_vm2_str, check_cmd)
            if "mininet_session" in session_status:
                return f"Mininet успешно запущен в screen-сессии.\n{session_status}"
            else:
                return f"Команда выполнена, но не удалось создать screen-сессию.\n{result}"
        
        return result
    except asyncio.TimeoutError:
        return "Команда выполнена, но превышен таймаут ожидания вывода."

@app.post("/run_scapy")
async def run_scapy(
    vm_choice: str = Form(...),
    scapy_script: str = Form(...),
    host_name: str = Form(...),
):
    if vm_choice == "VM1":
        return "Scapy скрипты можно выполнять только на VM2."

    command = f"""
cat > /tmp/scapy_script.py << 'EOF'
{scapy_script}
EOF
PID=$(pgrep -f "bash.*{host_name}")
sudo mnexec -a $PID python3 /tmp/scapy_script.py
"""
    return await ssh_command(vm2_ip, vm2_user, private_key_vm2_str, command)

@app.post("/upload_scapy")
async def upload_scapy(
    vm_choice: str = Form(...),
    scapy_file: UploadFile = File(...),
):
    if vm_choice == "VM1":
        return "Scapy скрипты можно выполнять только на VM2."
    
    contents = await scapy_file.read()
    scapy_script = contents.decode()
    
    command = f"""
    cat > /tmp/scapy_script.py << 'EOF'
{scapy_script}
EOF
    python3 /tmp/scapy_script.py
    """
    
    return await ssh_command(vm2_ip, vm2_user, private_key_vm2_str, command)



VAGRANT_DIR = "D:\\sdn_lab"  # Укажите вашу директорию с Vagrantfile
class CommandRequest(BaseModel):
    command: str

@app.post("/api/execute")
async def execute_command(request: CommandRequest):  # ← Используем модель
    try:
        result = subprocess.run(
            f"vagrant {request.command}",  # ← Доступ через request.command
            shell=True,
            cwd="D:\\sdn_lab",
            text=True,
            capture_output=True
        )
        return {
            "success": True,
            "output": result.stdout,
            "error": result.stderr
        }
    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "output": e.stdout,
            "error": e.stderr
        }


@app.post("/start_ttyd")
async def start_ttyd(
    port: int = Form(8080, description="Порт для ttyd (по умолчанию 8080"),
    command: str = Form("bash", description="Команда для запуска (по умолчанию bash)"),
):
    """
    Запускает ttyd (веб-терминал) на VM2 и возвращает URL для доступа.
    """
    try:
        # 1. Убиваем процесс, если уже занят порт
        kill_cmd = f"sudo pkill -f 'ttyd.*{port}' || true"
        await ssh_command(vm2_ip, vm2_user, private_key_vm2_str, kill_cmd)

        # 2. Запускаем ttyd в фоне (с nohup)
        start_cmd = f"nohup ttyd -p {port} {command} > /dev/null 2>&1 &"
        result = await ssh_command(vm2_ip, vm2_user, private_key_vm2_str, start_cmd)

        # 3. Проверяем, что процесс запустился
        check_cmd = f"pgrep -f 'ttyd.*{port}'"
        await asyncio.sleep(1)  # Даем время на запуск
        pid = await ssh_command(vm2_ip, vm2_user, private_key_vm2_str, check_cmd)

        if not pid.strip():
            raise HTTPException(status_code=500, detail="Не удалось запустить ttyd")

        return {
            "success": True,
            "url": f"http://{vm2_ip}:{port}",
            "message": f"ttyd запущен на порту {port}. Откройте URL в браузере."
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при запуске ttyd: {str(e)}"
        )
