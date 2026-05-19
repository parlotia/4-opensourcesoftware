# 开源自动化运维 DAY1 - Ansible 批量配置 Cisco C8Kv 路由器

## 作业背景

本次作业要求使用 **Ansible** 批量配置两台 Cisco C8Kv 路由器（C8Kv1 / C8Kv2）。
重点不是手工敲命令，而是把"连接信息 / 配置数据 / 执行逻辑"拆分到不同文件中，
通过 `inventory_hostname` 让同一份 playbook 根据数据自动下发到对应设备，
完成 hostname、域名、DNS、用户、接口、OSPF、Logging 相关配置。

### 作业核心要求

1. 使用 `inventory.yml` 保存设备连接信息
2. 使用 `data.yml` 保存待下发的网络配置数据
3. 使用 `playbook.yml` 读取 `data.yml`，按 `inventory_hostname` 取数据并下发
4. 优先使用 Cisco IOS 专用模块：
   - `cisco.ios.ios_system` / `ios_user` / `ios_l3_interfaces` /
     `ios_interfaces` / `ios_ospfv2` / `ios_logging_global`
   - `ios_config` 仅用于 `save_when` 保存配置

---

## 实验环境

| 设备 | IP | 角色 |
|------|-----|------|
| C8Kv1 | 10.10.1.201 | 业务路由器 1 |
| C8Kv2 | 10.10.1.202 | 业务路由器 2 |
| Linux 服务器（Rocky 9） | 10.10.1.205 | Ansible 控制节点 |

**账号信息：** `admin / Cisc0123`（直接以 privilege 15 登录，无独立 enable secret）

**软件版本（按作业要求固定）：**

| 组件 | 版本 |
|------|------|
| ansible-core | 2.15.13 |
| cisco.ios | 9.2.0 |
| ansible.netcommon | 7.2.0 |
| ansible.utils | 5.1.2 |
| ansible-pylibssh | 1.4.0 |

---

## 依赖安装

```bash
cd /netdevops/homework/4.opensourcesoftware/DAY1
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install ansible-core==2.15.13 ansible-pylibssh==1.4.0

cd Code
ansible-galaxy collection install \
    cisco.ios:9.2.0 ansible.netcommon:7.2.0 ansible.utils:5.1.2 \
    -p ./collections
```

---

## 配置目标

### 共用配置（两台设备一致）

- `ip name-server 114.114.114.114 8.8.8.8`
- `ip domain name qytang.com`
- 用户：`qytadmin` (privilege 15) / `otheradmin` (privilege 1)，password type = `secret`
- `logging console notifications`
- `logging host 10.10.1.205`（Linux 服务器为本环境真实 SYSLOG 服务器，作业模板中 192.168.1.100/101 为示例占位，按真实环境调整）

### 差异化配置（按设备）

| 项目 | C8Kv1 | C8Kv2 |
|------|-------|-------|
| hostname | `C8Kv1` | `C8Kv2` |
| Loopback0 | `1.1.1.1/24` | `2.2.2.2/24` |
| GigabitEthernet2 | `61.128.1.1/24` | `61.128.1.2/24` |
| OSPF router-id | `1.1.1.1` | `2.2.2.2` |
| OSPF network | `1.1.1.0 0.0.0.255 area 0` + `61.128.1.0 0.0.0.255 area 0` | `2.2.2.0 0.0.0.255 area 0` + `61.128.1.0 0.0.0.255 area 0` |

---

## 目录结构

```
DAY1/
├── README.md
├── .venv/                        # Python 虚拟环境
└── Code/
    ├── ansible.cfg               # Ansible 主配置
    ├── inventory.yml             # 设备清单（连接信息）
    ├── data.yml                  # 业务配置数据
    ├── playbook.yml              # 主 playbook
    ├── verify.yml                # 验证 playbook（show 命令）
    ├── cleanup.yml               # 清理 playbook（恢复裸机管理状态）
    └── collections/              # Ansible Collections（cisco.ios 等）
```

---

## 配置文件说明

### 1. `ansible.cfg`

```ini
[defaults]
inventory = inventory.yml
host_key_checking = False
retry_files_enabled = False
stdout_callback = default
timeout = 30
interpreter_python = auto_silent
collections_path = ./collections

[persistent_connection]
command_timeout = 60
connect_timeout = 30
```

### 2. `inventory.yml`

只存放设备连接信息，组名 `C8Kv`，主机名 `C8Kv1` / `C8Kv2`。
连接方式 `ansible.netcommon.network_cli` + `libssh`。
**📷 截图：`inventory.yml` 文件内容（敏感密码请打码）**

### 3. `data.yml`

按 `inventory_hostname` 索引接口与 OSPF 数据：

- `c8kv_system`：domain_name + name_servers
- `c8kv_user_db`：用户列表（qytadmin / otheradmin）
- `c8kv_interfaces[<host>]`：接口与 IP
- `c8kv_ospf[<host>]`：router_id + networks
- `c8kv_logging`：console 等级 + syslog hosts

**📷 截图：`data.yml` 文件内容**

### 4. `playbook.yml`

7 个 task，按顺序：
1. `ios_system` → hostname / domain / DNS
2. `ios_user` → 创建本地用户（`no_log: true`）
3. `ios_l3_interfaces` → 配置 L3 接口 IP
4. `ios_interfaces` → `enabled: true` 启用接口
5. `ios_ospfv2` → router-id + networks 一次性配齐
6. `ios_logging_global` → console + hosts
7. `ios_config` → `save_when: modified` 保存

**📷 截图：`playbook.yml` 文件内容**

---

## 运行与验证

### 1. 检查 inventory

```bash
cd /netdevops/homework/4.opensourcesoftware/DAY1/Code
source ../.venv/bin/activate
ansible-inventory --list
```

应能看到 `C8Kv` 组下有 `C8Kv1` 和 `C8Kv2`。

### 2. 测试连通性

```bash
ansible C8Kv -m cisco.ios.ios_command -a "commands='show clock'"
```

两台设备均返回 `SUCCESS` 与时间戳。
**📷 截图：`show clock` 两台设备 SUCCESS 输出**

### 3. 语法检查 + dry-run

```bash
ansible-playbook --syntax-check playbook.yml
ansible-playbook --check playbook.yml
```

### 4. 正式下发

```bash
ansible-playbook playbook.yml
```

预期 PLAY RECAP：

```
C8Kv1 : ok=7 changed=4 failed=0
C8Kv2 : ok=7 changed=4 failed=0
```

**📷 截图：`ansible-playbook playbook.yml` 完整执行输出（含 PLAY RECAP）**

### 5. 验证下发结果

```bash
ansible-playbook verify.yml
```

`verify.yml` 会执行下面 4 条 `show` 命令并打印：

- `show ip interface brief | include Loopback0|GigabitEthernet2`
- `show running-config | section router ospf`
- `show running-config | include ^logging`
- `show running-config | include ^username`

**预期输出（C8Kv1）：**

```
GigabitEthernet2  61.128.1.1  YES manual up/up
Loopback0         1.1.1.1     YES other  up/up
router ospf 1
 router-id 1.1.1.1
 network 1.1.1.0 0.0.0.255 area 0
 network 61.128.1.0 0.0.0.255 area 0
logging console notifications
logging host 10.10.1.205
username qytadmin privilege 15 secret 9 ...
username otheradmin secret 9 ...
```

**📷 截图：`verify.yml` 4 项验证输出（接口 / OSPF / Logging / Username）**

---

## 踩坑记录

### 1. 接口网段冲突 `overlaps with GigabitEthernet3`

**现象**：首次下发 `GigabitEthernet2 = 61.128.1.x/24` 时报：

```
% 61.128.1.0 overlaps with GigabitEthernet3
```

**根因**：设备上 `GigabitEthernet3` 残留同网段地址，IOS 不允许两个接口同网段共存。

**修复**：先用 ad-hoc 命令清除 G3 IP，再重跑 playbook：

```bash
ansible C8Kv -m cisco.ios.ios_config \
  -a "lines='no ip address' parents='interface GigabitEthernet3'"
```

### 2. `no username` 触发交互式 [confirm]

**现象**：清理 playbook 中 `no username qytadmin` 卡住超时：

```
This operation will remove all username related configurations
with same name.Do you want to continue? [confirm]
```

**根因**：IOS 删除用户会要求二次确认，`ios_config` 不支持自动应答 prompt。

**修复**：用 `paramiko.invoke_shell()` 手工发回车确认（见 `cleanup.yml` 注释，
或用脚本通过 SSH 直接交互）。

### 3. `ansible_become_method: enable` 与 priv 15 用户

**现象**：admin 用户登录后已是 priv 15，再 `enable` 不会提示密码，
但 inventory 里仍配置了 `ansible_become_password: Cisc0123`，无副作用。

**说明**：保留 become 配置可以兼容低权限用户场景，更通用。

### 4. `show run | section` 在 ad-hoc 中需注意引号

**现象**：直接用 `ansible -a "commands='show run | section router ospf'"` 报
`Invalid input detected at '^' marker`，外层引号被 shell 截断。

**修复**：把验证命令写到 `verify.yml` 的 `commands:` 列表里执行，避免 shell 解析。

---

## 完整数据流

```
data.yml (业务数据)
  ↓ vars_files
playbook.yml
  ↓ inventory_hostname 索引
[ios_system / ios_user / ios_l3_interfaces / ios_interfaces /
 ios_ospfv2 / ios_logging_global / ios_config]
  ↓ network_cli + libssh
inventory.yml (连接信息)
  ↓
C8Kv1 (10.10.1.201)  /  C8Kv2 (10.10.1.202)
  ↓
verify.yml → show 命令验证
```

---

## 截图清单（提交时按此顺序）

| 序号 | 截图内容 | 位置 |
|------|----------|------|
| ① | `ansible.cfg` 文件内容 | Code/ansible.cfg |
| ② | `inventory.yml` 文件内容（密码打码） | Code/inventory.yml |
| ③ | `data.yml` 文件内容 | Code/data.yml |
| ④ | `playbook.yml` 文件内容 | Code/playbook.yml |
| ⑤ | `ansible-inventory --list` 输出 | 终端 |
| ⑥ | `ansible C8Kv -m cisco.ios.ios_command -a "commands='show clock'"` 两台 SUCCESS | 终端 |
| ⑦ | `ansible-playbook --syntax-check playbook.yml` 通过 | 终端 |
| ⑧ | `ansible-playbook playbook.yml` 完整执行 + PLAY RECAP（ok=7 changed=4） | 终端 |
| ⑨ | `verify.yml` 4 项验证输出（接口 / OSPF / Logging / Username）| 终端 |

---

## 文件清单

| 文件 | 说明 |
|------|------|
| `Code/ansible.cfg` | Ansible 主配置 |
| `Code/inventory.yml` | 设备连接信息 |
| `Code/data.yml` | 业务配置数据（按 inventory_hostname 索引） |
| `Code/playbook.yml` | 主 playbook（7 task） |
| `Code/verify.yml` | 验证 playbook |
| `Code/cleanup.yml` | 配置清理 playbook（仅保留管理 + SSH） |
| `Code/collections/` | cisco.ios / ansible.netcommon / ansible.utils |
