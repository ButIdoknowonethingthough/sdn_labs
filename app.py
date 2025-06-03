from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import asyncssh
import asyncio
import os
from pydantic import BaseModel
import shutil
import subprocess
import base64
import re
import shlex
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

async def ssh_command(vm_ip, vm_user, private_key_str, command, timeout=60):
    try:
        private_key = asyncssh.import_private_key(private_key_str.strip())
        async with asyncssh.connect(
            vm_ip, username=vm_user, client_keys=[private_key], known_hosts=None
        ) as conn:
            result = await conn.run(command, timeout=timeout, check=False)
            
            if result.exit_status == 0:
                return result.stdout  # Возвращаем только stdout при успехе
            else:
                return f"⚠️ Команда завершилась с ошибкой (код {result.exit_status}):\n{result.stderr or 'Нет сообщения в stderr'}"
                
    except Exception as e:
        return f"❌ Ошибка SSH: {str(e)}"


async def kill_process_on_port(vm_ip, vm_user, private_key_str, port):
    command = f"sudo fuser -k {port}/tcp"
    return await ssh_command(vm_ip, vm_user, private_key_str, command)

@app.get("/")
async def control_panel(request: Request):
    return templates.TemplateResponse("stand.html", {"request": request})

@app.post("/start_controller")
async def start_controller(
    vm_choice: str = Form(...),
    controller_type: str = Form(...),
):
    commands = {
        "Opendaylight": "cd /opt/opendaylight/distribution-karaf-0.4.0-Beryllium && sudo ./bin/karaf",
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
    command: str = Form(..., description="Команда для Mininet (pingall, h1 ping h2 и т.д.)"),
    wait_for_output: bool = Form(False, description="Ожидать вывод команды"),
    timeout: int = Form(10, description="Таймаут ожидания вывода (секунды)"),
):
    """
    Отправляет команду в Mininet через screen с возможностью получения вывода
    через буфер screen (без зависимости от лог-файлов)
    """
    # 1. Проверка активной сессии
    check_cmd = "sudo screen -ls mininet_session"
    try:
        result = await ssh_command(vm2_ip, vm2_user, private_key_vm2_str, check_cmd)
        if "mininet_session" not in result:
            return "⚠️ Нет активной сессии Mininet. Запустите через /run_mininet."
    except Exception as e:
        return f"❌ Ошибка проверки сессии: {str(e)}"

    # 2. Подготовка и отправка команды
    try:
        # Валидация команды
        if not re.match(r"^[a-zA-Z0-9\s\._\-@:]+$", command):
            raise ValueError("Обнаружены недопустимые символы в команде")
        
        safe_command = shlex.quote(command)
        send_cmd = f'sudo screen -S mininet_session -X stuff {safe_command}$(printf "\\r")'
        
        if not wait_for_output:
            # Простая отправка без ожидания вывода
            await ssh_command(vm2_ip, vm2_user, private_key_vm2_str, send_cmd)
            return f"✅ Команда '{command}' успешно отправлена"
        
        # 3. Очистка буфера перед выполнением
        await ssh_command(
            vm2_ip, vm2_user, private_key_vm2_str,
            "sudo screen -S mininet_session -X clear"
        )
        
        # 4. Отправка команды
        await ssh_command(vm2_ip, vm2_user, private_key_vm2_str, send_cmd)
        
        # 5. Ожидание выполнения (адаптивное)
        await asyncio.sleep(1)  # Минимальная пауза
        
        # 6. Чтение буфера screen
        output = await ssh_command(
            vm2_ip, vm2_user, private_key_vm2_str,
            "sudo screen -S mininet_session -X hardcopy -h /dev/stdout",
            timeout=timeout
        )
        
        # Очистка лишних управляющих символов
        cleaned_output = re.sub(r'\x1b\[[0-9;]*[mK]', '', output)  # Удаляем ANSI коды
        cleaned_output = re.sub(r'\r\n', '\n', cleaned_output)      # Нормализуем переносы
        
        return f"🔹 Вывод команды '{command}':\n{cleaned_output}"
    
    except asyncio.TimeoutError:
        return "⏳ Таймаут ожидания вывода команды"
    except ValueError as ve:
        return f"❌ Недопустимая команда: {str(ve)}"
    except Exception as e:
        return f"⚠️ Ошибка выполнения: {str(e)}"
    


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
        base_command = custom_command.strip()
        
        # Проверяем, является ли кастомная команда очисткой (mn -c или sudo mn -c)
        is_clean_command = any(
            cmd in base_command.lower()
            for cmd in ["mn -c", "sudo mn -c", "mn --clean"]
        )
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
        
        is_clean_command = (command_type == "Clean Mininet")
    
    # Для команд очистки (включая кастомные с mn -c)
    if is_clean_command:
        # 1. Выполняем очистку Mininet
        clean_cmd = f"echo 'vagrant' | sudo -S {base_command}"
        clean_result = await ssh_command(vm2_ip, vm2_user, private_key_vm2_str, clean_cmd)
        
        # 2. Убиваем screen-сессию, если она существует
        check_session_cmd = "sudo screen -ls | grep mininet_session"
        session_status = await ssh_command(vm2_ip, vm2_user, private_key_vm2_str, check_session_cmd)
        
        if "mininet_session" in session_status:
            kill_session_cmd = "sudo screen -XS mininet_session quit"
            kill_result = await ssh_command(vm2_ip, vm2_user, private_key_vm2_str, kill_session_cmd)
            return f"{clean_result}\n\nScreen-сессия mininet_session была удалена.\n{kill_result}"
        else:
            return f"{clean_result}\n\nАктивная screen-сессия mininet_session не найдена."
    else:
        # Остальные команды запускаем в screen-сессии
        command = f"echo 'vagrant' | sudo -S screen -dmS mininet_session {base_command}"
        
        try:
            result = await ssh_command(vm2_ip, vm2_user, private_key_vm2_str, command)
            
            # Проверяем статус screen-сессии
            check_cmd = "sudo screen -ls | grep mininet_session"
            session_status = await ssh_command(vm2_ip, vm2_user, private_key_vm2_str, check_cmd)
            
            if "mininet_session" in session_status:
                return f"Mininet успешно запущен в screen-сессии.\n{session_status}"
            else:
                return f"Команда выполнена, но не удалось создать screen-сессии.\n{result}"
            
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
sudo mnexec -a "$PID" python3 /tmp/scapy_script.py
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
    vm_choice: str = Form(..., description="Выберите VM для запуска терминала"),
    port: int = Form(8080, description="Порт для ttyd (по умолчанию 8080)"),
    command: str = Form("bash", description="Команда для запуска (по умолчанию bash)"),
):
    try:
        # Выбираем целевую VM
        if vm_choice == "VM1":
            vm_ip = vm1_ip
            vm_user = vm1_user
            private_key_str = private_key_vm1_str
        elif vm_choice == "VM2":
            vm_ip = vm2_ip
            vm_user = vm2_user
            private_key_str = private_key_vm2_str
        else:
            raise HTTPException(status_code=400, detail="Неверный выбор VM")

        kill_cmd = f"sudo pkill -f 'ttyd.*{port}' || true"
        await ssh_command(vm_ip, vm_user, private_key_str, kill_cmd)

        check_installed_cmd = "which ttyd || echo 'not installed'"
        installed = await ssh_command(vm_ip, vm_user, private_key_str, check_installed_cmd)
        
        if "not installed" in installed:
            install_cmd = "sudo apt-get update && sudo apt-get install -y ttyd"
            await ssh_command(vm_ip, vm_user, private_key_str, install_cmd)

        start_cmd = f"nohup ttyd -p {port} {command} > /dev/null 2>&1 &"
        result = await ssh_command(vm_ip, vm_user, private_key_str, start_cmd)

        check_cmd = f"pgrep -f 'ttyd.*{port}'"
        await asyncio.sleep(1)  # Даем время на запуск
        pid = await ssh_command(vm_ip, vm_user, private_key_str, check_cmd)

        if not pid.strip():
            raise HTTPException(status_code=500, detail="Не удалось запустить ttyd")

        return {
            "success": True,
            "url": f"http://{vm_ip}:{port}",
            "message": f"ttyd запущен на {vm_choice} ({vm_ip}) порту {port}. Откройте URL в браузере."
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при запуске ttyd на {vm_choice}: {str(e)}"
        )
    
@app.post("/stop_ttyd")
async def stop_ttyd(
    vm_choice: str = Form(...),
    port: int = Form(...),
):
    try:
        if vm_choice == "VM1":
            vm_ip = vm1_ip
            vm_user = vm1_user
            private_key_str = private_key_vm1_str
        elif vm_choice == "VM2":
            vm_ip = vm2_ip
            vm_user = vm2_user
            private_key_str = private_key_vm2_str
        else:
            raise HTTPException(status_code=400, detail="Неверный выбор VM")

        # 1. Убиваем процесс ttyd
        kill_cmd = f"sudo pkill -f 'ttyd.*{port}' || echo 'No process to kill'"
        kill_result = await ssh_command(vm_ip, vm_user, private_key_str, kill_cmd)

        # 2. Освобождаем порт
        free_port_cmd = f"sudo fuser -k {port}/tcp || echo 'Port already free'"
        await ssh_command(vm_ip, vm_user, private_key_str, free_port_cmd)

        # 3. Проверяем что процесс убит
        check_cmd = f"pgrep -f 'ttyd.*{port}' || echo 'Not running'"
        check_result = await ssh_command(vm_ip, vm_user, private_key_str, check_cmd)

        if "Not running" not in check_result:
            return {
                "success": False,
                "message": f"Не удалось остановить ttyd на {vm_choice}. Остались процессы: {check_result}"
            }

        return {
            "success": True,
            "message": f"ttyd на {vm_choice} (порт {port}) успешно остановлен"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при остановке ttyd: {str(e)}"
        )


@app.post("/run_python_script")
async def run_python_script(
    vm_choice: str = Form(...),
    python_script: str = Form(...),
    host_name: str = Form("h1", description="Имя хоста в Mininet, где выполнять скрипт (по умолчанию h1)"),
):
    """
    Выполняет Python скрипт на указанной VM (только VM2) 
    с возможностью запуска внутри Mininet хоста
    """
    if vm_choice == "VM1":
        return "Python скрипты можно выполнять только на VM2."

    # Если host_name не указан, выполняем на самой VM2
    if not host_name.strip():
        command = f"""
        cat > /tmp/python_script.py << 'EOF'
{python_script}
EOF
        python3 /tmp/python_script.py
        """
    else:
        # Если указан host_name, выполняем внутри Mininet хоста через mnexec
        command = f"""
        cat > /tmp/python_script.py << 'EOF'
{python_script}
EOF
        PID=$(pgrep -f "bash.*{host_name}")
        sudo mnexec -a "$PID" python3 /tmp/python_script.py
        """
    
    return await ssh_command(vm2_ip, vm2_user, private_key_vm2_str, command)

@app.post("/upload_python_script")
async def upload_python_script(
    vm_choice: str = Form(...),
    python_file: UploadFile = File(...),
    host_name: str = Form("h1", description="Имя хоста в Mininet, где выполнять скрипт (по умолчанию h1)"),
):
    """
    Загружает и выполняет Python скрипт из файла на указанной VM (только VM2)
    с возможностью запуска внутри Mininet хоста
    """
    if vm_choice == "VM1":
        return "Python скрипты можно выполнять только на VM2."
    
    contents = await python_file.read()
    python_script = contents.decode()
    
    # Если host_name не указан, выполняем на самой VM2
    if not host_name.strip():
        command = f"""
        cat > /tmp/python_script.py << 'EOF'
{python_script}
EOF
        python3 /tmp/python_script.py
        """
    else:
        # Если указан host_name, выполняем внутри Mininet хоста через mnexec
        command = f"""
        cat > /tmp/python_script.py << 'EOF'
{python_script}
EOF
        PID=$(pgrep -f "bash.*{host_name}")
        sudo mnexec -a "$PID" python3 /tmp/python_script.py
        """
    
    return await ssh_command(vm2_ip, vm2_user, private_key_vm2_str, command)
