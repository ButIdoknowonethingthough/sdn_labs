from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import asyncssh
import io
from typing import Optional
import asyncio
import os

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# SSH Configuration
private_key_vm1_str = """-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAA
AAtzc2gtZWQyNTUxOQAAACDNZN9whhmzffqlgN7/CRRBkycc4AwX6lc4iVVI
djNB8gAAAJAgg0ZkIINGZAAAAAtzc2gtZWQyNTUxOQAAACDNZN9whhmzffql
gN7/CRRBkycc4AwX6lc4iVVIdjNB8gAAAEAkhT/KmVNMKEAghTklX/wblnXO
yh8hPC1xunlvCNjQoc1k33CGGbN9+qWA3v8JFEGTJxzgDBfqVziJVUh2M0Hy
AAAAB3ZhZ3JhbnQBAgMEBQY=
-----END OPENSSH PRIVATE KEY-----
"""

private_key_vm2_str = """-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAA
AAtzc2gtZWQyNTUxOQAAACBNdxhgOSpAXWuVDJErKoimPniMSVE8nXqk2qcM
xhfkpQAAAJB1oHdldaB3ZQAAAAtzc2gtZWQyNTUxOQAAACBNdxhgOSpAXWuV
DJErKoimPniMSVE8nXqk2qcMxhfkpQAAAEB6VuJaF7vjF8nwd/oGCkgSGuj6
hwHPyCnRR+Vz9l/4qE13GGA5KkBda5UMkSsqiKY+eIxJUTydeqTapwzGF+Sl
AAAAB3ZhZ3JhbnQBAgMEBQY=
-----END OPENSSH PRIVATE KEY-----
"""

vm1_ip = "192.168.56.10"
vm1_user = "vagrant"
vm2_ip = "192.168.56.20"
vm2_user = "vagrant"

async def ssh_command(vm_ip, vm_user, private_key_str, command, timeout=10):
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
        "Opendaylight": "cd /opt/opendaylight/distribution-karaf-0.4.0-Beryllium && ./bin/start",
        "ONOS": "cd /opt/onos/onos-1.15.0 && ./bin/onos-service start",
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
        "ONOS": "cd /opt/onos/onos-1.15.0 && ./bin/onos-service stop",
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

@app.post("/run_mininet")
async def run_mininet(
    vm_choice: str = Form(...),
    command_name: str = Form(...),
    controller_ip: str = Form("192.168.56.10"),
    controller_port: str = Form("6633"),
):
    if vm_choice == "VM1":
        return "Mininet доступен только на VM2."
    
    mininet_commands = {
        "Create Simple Topology": f"sudo mn --topo linear,3 --mac --controller=remote,ip={controller_ip},port={controller_port} --switch ovs,protocols=OpenFlow13",
        "Ping All": f"sudo mn --controller=remote,ip={controller_ip} --topo=single,3 --test pingall",
        "Test Connectivity": f"sudo mn --controller=remote,ip={controller_ip} --topo=linear,4 --test iperf",
        "Start CLI": f"sudo mn --controller=remote,ip={controller_ip} --topo=tree,depth=2,fanout=3",
        "Clean Mininet": "sudo mn -c",
    }

    command = mininet_commands.get(command_name)
    if not command:
        return "Неизвестная команда Mininet."
    
    return await ssh_command(vm2_ip, vm2_user, private_key_vm2_str, command)

@app.post("/run_scapy")
async def run_scapy(
    vm_choice: str = Form(...),
    scapy_script: str = Form(...),
):
    if vm_choice == "VM1":
        return "Scapy скрипты можно выполнять только на VM2."
    
    # Сохраняем скрипт во временный файл и выполняем
    command = f"""
    cat > /tmp/scapy_script.py << 'EOF'
{scapy_script}
EOF
   sudo python3 /tmp/scapy_script.py
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
