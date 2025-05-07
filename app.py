from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import paramiko
import io

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# SSH Configuration
private_key_vm1_str = """-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAA
AAtzc2gtZWQyNTUxOQAAACBo1RwQXgg3Iws8WIFKhbDoTAwrtv7ywuWpxYAl
28jLlwAAAJD8PbIb/D2yGwAAAAtzc2gtZWQyNTUxOQAAACBo1RwQXgg3Iws8
WIFKhbDoTAwrtv7ywuWpxYAl28jLlwAAAEDgUv0q4XDTXHMDeE7LKpmoKl3r
cxuv3dpfRtxT51DiSmjVHBBeCDcjCzxYgUqFsOhMDCu2/vLC5anFgCXbyMuX
AAAAB3ZhZ3JhbnQBAgMEBQY=
-----END OPENSSH PRIVATE KEY-----
"""

private_key_vm2_str = """-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAA
AAtzc2gtZWQyNTUxOQAAACB63c2+X3uaP8+rc6MogJsTYSoWJAsufkUPGfeU
UHcTkQAAAJAOz0/ADs9PwAAAAAtzc2gtZWQyNTUxOQAAACB63c2+X3uaP8+r
c6MogJsTYSoWJAsufkUPGfeUUHcTkQAAAECVcKy8CoX80mpHQUoJV5MN4NEg
uJqx/r8PEEAoVExom3rdzb5fe5o/z6tzoyiAmxNhKhYkCy5+RQ8Z95RQdxOR
AAAAB3ZhZ3JhbnQBAgMEBQY=
-----END OPENSSH PRIVATE KEY-----
"""

vm1_ip = "192.168.56.10"
vm1_user = "vagrant"
vm2_ip = "192.168.56.20"
vm2_user = "vagrant"

def ssh_command(vm_ip, vm_user, private_key_str, command):
    """Execute SSH command"""
    try:
        private_key = paramiko.Ed25519Key.from_private_key(io.StringIO(private_key_str))
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(vm_ip, username=vm_user, pkey=private_key)

        stdin, stdout, stderr = client.exec_command(command)
        output = stdout.read().decode()
        error = stderr.read().decode()

        client.close()

        if error:
            return f"Ошибка при выполнении команды: {error}"
        else:
            return f"Команда выполнена успешно:\n{output}"

    except Exception as e:
        return f"Произошла ошибка: {e}"

@app.get("/")
async def control_panel(request: Request):
    return templates.TemplateResponse("control_panel.html", {"request": request})

@app.post("/start_controller")
async def start_controller(
    vm_choice: str = Form(...),
    controller_type: str = Form(...)
):
    commands = {
        "Opendaylight": "cd /opt/opendaylight/distribution-karaf-0.4.0-Beryllium && ./bin/start",
        "ONOS": "cd /opt/onos/onos-1.15.0 && ./bin/onos-service start",
        "Ryu": "ryu-manager --verbose ryu.app.simple_switch_13"
    }
    
    command = commands.get(controller_type)
    if not command:
        return "Выберите корректный тип контроллера."
    
    if vm_choice == "VM1":
        return ssh_command(vm1_ip, vm1_user, private_key_vm1_str, command)
    elif vm_choice == "VM2":
        return ssh_command(vm2_ip, vm2_user, private_key_vm2_str, command)
    else:
        return "Выберите корректную виртуальную машину."

@app.post("/stop_controller")
async def stop_controller(
    vm_choice: str = Form(...),
    controller_type: str = Form(...)
):
    commands = {
        "Opendaylight": "cd /opt/opendaylight/distribution-karaf-0.4.0-Beryllium && ./bin/stop",
        "ONOS": "cd /opt/onos/onos-1.15.0 && ./bin/onos-service stop",
        "Ryu": "pkill -f ryu-manager"
    }
    
    command = commands.get(controller_type)
    if not command:
        return "Выберите корректный тип контроллера."
    
    if vm_choice == "VM1":
        return ssh_command(vm1_ip, vm1_user, private_key_vm1_str, command)
    elif vm_choice == "VM2":
        return ssh_command(vm2_ip, vm2_user, private_key_vm2_str, command)
    else:
        return "Выберите корректную виртуальную машину."

@app.post("/run_mininet")
async def run_mininet(
    vm_choice: str = Form(...), 
    command_name: str = Form(...),
    controller_ip: str = Form("192.168.56.10"),
    controller_port: str = Form("6633")
):
    if vm_choice == "VM1":
        return "Mininet доступен только на VM2."
    
    mininet_commands = {
        "Create Simple Topology": f"sudo mn --topo linear,3 --mac --controller=remote,ip={controller_ip},port={controller_port} --switch ovs,protocols=OpenFlow13",
        "Ping All": f"sudo mn --controller=remote,ip={controller_ip} --topo=single,3 --test pingall",
        "Test Connectivity": f"sudo mn --controller=remote,ip={controller_ip} --topo=linear,4 --test iperf",
        "Start CLI": f"sudo mn --controller=remote,ip={controller_ip} --topo=tree,depth=2,fanout=3",
        "Clean Mininet": "sudo mn -c"
    }

    command = mininet_commands.get(command_name, "echo 'Неизвестная команда'")
    return ssh_command(vm2_ip, vm2_user, private_key_vm2_str, command)