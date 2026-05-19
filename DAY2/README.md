# DAY2 开源自动化运维作业（Nornir）

## 作业背景
本次作业要求安装 **Nornir**，并使用 Nornir 批量配置两台 Cisco C8Kv 路由器。配置目标与第 1 天保持一致，但实现方式从 Ansible playbook 改为 **Nornir Python 程序 + inventory 数据 + Jinja2 模板**。

## 实验环境
| 设备 | 管理 IP | 用户 | 角色 |
|---|---|---|---|
| C8Kv1 | 10.10.1.201 | admin / Cisc0123 | 路由器 1（IOS XE 17.08.01a） |
| C8Kv2 | 10.10.1.202 | admin / Cisc0123 | 路由器 2（IOS XE 17.08.01a） |
| Linux Server | 10.10.1.205 | - | Syslog 服务器（真实环境） |

## 项目结构
```
4.opensourcesoftware/DAY2/
├── .venv/                        # 独立 Python venv
├── Code/
│   ├── config.yaml               # Nornir 主配置（指定 inventory 插件 + 路径）
│   ├── inventory/
│   │   ├── hosts.yaml            # C8Kv1 / C8Kv2 设备差异数据
│   │   ├── groups.yaml           # cisco_ios 通用连接参数
│   │   └── defaults.yaml         # 共用：登录凭据 + DNS + 用户 + Syslog
│   ├── templates/
│   │   ├── system.j2             # hostname / DNS / domain
│   │   ├── users.j2              # qytadmin / otheradmin
│   │   ├── interfaces.j2         # Loopback0 + Gi2
│   │   ├── ospf.j2               # OSPFv2 进程 1
│   │   └── logging.j2            # console + syslog host
│   ├── vault/                    # （可选）vault 密码加密目录
│   ├── nornir_final_task.py      # 主任务：连通性 + 渲染 + 下发 + print_result
│   ├── verify_task.py            # 验证：4 条 show 命令
│   └── requirements.txt          # 依赖清单
├── screenshots/                   # 12 张截图
├── README.md
└── 朱峰烁作业_opensourcesoftware_Day2.docx
```

## 依赖版本
| 组件 | 版本 |
|---|---|
| nornir | 3.5.0 |
| nornir-utils | 0.2.0 |
| nornir-jinja2 | 0.2.0 |
| nornir-netmiko | 1.0.1 |
| netmiko | 4.6.0 |
| Jinja2 | 3.1.6 |
| ruamel.yaml | 0.19.1 |

## 配置目标（数据驱动，不在 Python 里硬编码）

### 共用项（写在 defaults.yaml）
- 域名：`qytang.com`
- DNS：`114.114.114.114, 8.8.8.8`
- 用户：`qytadmin (priv 15)` + `otheradmin (priv 1)`
- Syslog：`logging console notifications` + `logging host 10.10.1.205`（真实 Linux 服务器）

### 差异项（写在 hosts.yaml）
| 设备 | hostname | Loopback0 | Gi2 | OSPF router-id |
|---|---|---|---|---|
| C8Kv1 | C8Kv1 | 1.1.1.1/24 | 61.128.1.1/24 | 1.1.1.1 |
| C8Kv2 | C8Kv2 | 2.2.2.2/24 | 61.128.1.2/24 | 2.2.2.2 |

OSPF 进程 1：两条 network（Lo 段 + 61.128.1.0/24），全部 area 0。

## 运行步骤

```bash
# 1. 进入项目，激活 venv
cd /netdevops/homework/4.opensourcesoftware/DAY2/Code
source ../.venv/bin/activate

# 2. 主任务（连通性 + 渲染 + 下发 + print_result）
python nornir_final_task.py

# 3. 验证（4 条 show 命令）
python verify_task.py
```

## 验证结果（已通过）

```
C8Kv1:
  GigabitEthernet2  61.128.1.1  YES manual up   up
  Loopback0         1.1.1.1     YES manual up   up
  router ospf 1
   router-id 1.1.1.1
   network 1.1.1.0 0.0.0.255 area 0
   network 61.128.1.0 0.0.0.255 area 0
  logging console notifications
  logging host 10.10.1.205
  username qytadmin / otheradmin / admin   ✅

C8Kv2:
  GigabitEthernet2  61.128.1.2  YES manual up   up
  Loopback0         2.2.2.2     YES manual up   up
  router ospf 1
   router-id 2.2.2.2
   network 2.2.2.0 0.0.0.255 area 0
   network 61.128.1.0 0.0.0.255 area 0
  logging console notifications
  logging host 10.10.1.205
  username qytadmin / otheradmin / admin   ✅
```

## 截图清单（共 12 张，对应作业 6 类提交标准）

| # | 文件 | 用途 |
|---|---|---|
| ① | `screenshots/01_config_yaml.png` | Nornir 主配置 |
| ② | `screenshots/02_hosts_yaml.png` | hosts.yaml（密码打码） |
| ③ | `screenshots/03_groups_yaml.png` | groups.yaml |
| ④ | `screenshots/04_defaults_yaml.png` | defaults.yaml（密码打码） |
| ⑤–⑨ | `05_tpl_system / 06_tpl_users / 07_tpl_interfaces / 08_tpl_ospf / 09_tpl_logging.png` | 5 个 Jinja2 模板 |
| ⑩ | `10_nornir_main.png` | nornir_final_task.py 主程序 |
| ⑪ | `11_print_result.png` | 主任务完整执行（含 print_result） |
| ⑫ | `12_verify.png` | 接口/OSPF/Logging/Username 验证 |

## 安全说明
- `hosts.yaml / defaults.yaml` 截图中所有 `password / secret` 字段已替换为 `********`
- 课堂模板里的 `192.168.1.100/101` 是示例占位，本作业按真实环境用 `10.10.1.205`
- 未启用 vault（用明文密码 + 截图打码方案，符合作业说明的"如果不使用 vault 请注意截图打码"要求）
