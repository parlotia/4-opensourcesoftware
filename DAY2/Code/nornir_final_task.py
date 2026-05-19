"""
Nornir 主程序：批量配置两台 C8Kv 路由器
=========================================

执行流程:
    1. 加载 Nornir inventory（hosts.yaml + groups.yaml + defaults.yaml）
    2. 只读连通性测试：show clock
    3. 渲染 5 个 Jinja2 模板生成配置片段
    4. netmiko_send_config 下发拼装后的完整配置
    5. write memory 保存运行配置
    6. 用 print_result 展示每一步执行结果

用法:
    cd Code/
    source ../.venv/bin/activate
    python nornir_final_task.py
"""

from nornir import InitNornir
from nornir.core.task import Task, Result
from nornir_utils.plugins.functions import print_result
from nornir_jinja2.plugins.tasks import template_file
from nornir_netmiko.tasks import netmiko_send_command, netmiko_send_config


# 模板文件加载顺序：决定下发的配置顺序
TEMPLATES = ["system.j2", "users.j2", "interfaces.j2", "ospf.j2", "logging.j2"]


def render_full_config(task: Task) -> Result:
    """逐个渲染 5 个模板，拼成单台设备的完整配置文本。"""
    pieces = []
    for tpl in TEMPLATES:
        r = task.run(
            task=template_file,
            name=f"render {tpl}",
            template=tpl,
            path="templates",
            severity_level=20,  # 中间步骤用 INFO 级别，避免刷屏
        )
        pieces.append(r.result.rstrip())
    full_config = "\n".join(pieces) + "\n"
    return Result(host=task.host, result=full_config)


def deploy_config(task: Task) -> Result:
    """渲染 + 下发 + 保存。"""
    # 1. 渲染
    rendered = task.run(task=render_full_config, name="Render Jinja2 templates").result
    # 2. 下发：按行拆开，过滤 ! 注释行（netmiko 也支持注释，但显式更稳）
    cmd_list = [
        line for line in rendered.splitlines()
        if line.strip() and not line.strip().startswith("!")
    ]
    task.run(
        task=netmiko_send_config,
        name="Push config via netmiko",
        config_commands=cmd_list,
    )
    # 3. 保存
    task.run(
        task=netmiko_send_command,
        name="Save running-config",
        command_string="write memory",
        read_timeout=30,
    )
    return Result(host=task.host, result="deploy ok")


def conn_check(task: Task) -> Result:
    """只读连通性检查。"""
    r = task.run(
        task=netmiko_send_command,
        name="show clock",
        command_string="show clock",
    )
    return Result(host=task.host, result=r.result)


def main() -> None:
    nr = InitNornir(config_file="config.yaml")

    print("=" * 78)
    print("[1/3] Inventory 加载结果：")
    for name, h in nr.inventory.hosts.items():
        print(f"  - {name:6s}  hostname={h.hostname}  groups={list(h.groups)}")

    print("=" * 78)
    print("[2/3] 只读连通性测试 (show clock)：")
    res = nr.run(task=conn_check, name="Connectivity Check")
    print_result(res)

    print("=" * 78)
    print("[3/3] 渲染并下发配置：")
    res = nr.run(task=deploy_config, name="Deploy Config")
    print_result(res)

    failed = [n for n, mr in res.items() if mr.failed]
    if failed:
        print(f"\n[!] 失败的设备: {failed}")
    else:
        print("\n[OK] 所有设备配置下发完成")


if __name__ == "__main__":
    main()
