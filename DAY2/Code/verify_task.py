"""
验证脚本：跑 4 条 show 命令检查接口/OSPF/Logging/Username 配置是否正确
"""
from nornir import InitNornir
from nornir.core.task import Task, Result
from nornir_utils.plugins.functions import print_result
from nornir_netmiko.tasks import netmiko_send_command


VERIFY_COMMANDS = [
    "show ip interface brief | include Loopback0|GigabitEthernet2",
    "show running-config | section router ospf",
    "show running-config | include ^logging",
    "show running-config | include ^username",
]


def verify(task: Task) -> Result:
    outputs = []
    for cmd in VERIFY_COMMANDS:
        r = task.run(
            task=netmiko_send_command,
            name=cmd,
            command_string=cmd,
            read_timeout=20,
        )
        outputs.append(r.result)
    return Result(host=task.host, result="\n".join(outputs))


if __name__ == "__main__":
    nr = InitNornir(config_file="config.yaml")
    res = nr.run(task=verify, name="Verify Configuration")
    print_result(res)
