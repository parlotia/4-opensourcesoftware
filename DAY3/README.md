# DAY3 开源自动化运维作业（TIG 监控平台 + 钉钉告警）

## 作业背景

本次作业要求搭建 **TIG（Telegraf + InfluxDB + Grafana）** 监控平台，通过 **SNMP 轮询** 和 **gRPC Telemetry 推送** 两条数据路径采集 Cisco C8Kv 路由器的 CPU、内存、接口流量指标，配合 Grafana 可视化 + 告警规则 + **钉钉 Webhook** 通知，实现网络设备性能监控的端到端闭环。

### 作业四大任务

1. Docker Compose 一键启动 TIG 三件套
2. SNMP 监控路径：Telegraf SNMP 插件 → InfluxDB → Grafana Dashboard
3. gRPC 监控路径：Cisco MDT 推送 → Telegraf gRPC 插件 → InfluxDB → Grafana Dashboard
4. CPU 告警 + 钉钉通知：Grafana Alert Rule → DingDing Contact Point → 钉钉群机器人

---

## 实验环境

| 设备 | 管理 IP | 角色 |
|------|---------|------|
| C8Kv1 | 10.10.1.201 | 路由器 1（IOS XE 17.08.01a） |
| C8Kv2 | 10.10.1.202 | 路由器 2（IOS XE 17.08.01a） |
| Linux Server | 10.10.1.205 | TIG 平台宿主机（Rocky 9） |

**容器版本（按课程要求）：**

| 组件 | 镜像版本 | 端口 |
|------|---------|------|
| InfluxDB | `influxdb:2.7.9` | 8086 |
| Telegraf | `telegraf:1.31.2` | 57000 (gRPC) |
| Grafana | `grafana/grafana:11.1.1` | 3000 |

---

## 项目结构

```
DAY3/
├── Code/
│   ├── docker-compose.yml              # 一键启动 TIG 三服务
│   ├── telegraf.conf                   # Telegraf 配置（SNMP + gRPC 双输入）
│   ├── dingtalk.env.example            # .env 模板（学员复制为 .env 填入 Webhook URL）
│   ├── grafana/
│   │   ├── dashboards/
│   │   │   ├── SNMP_Dashboard.json     # SNMP 监控仪表板（课程提供）
│   │   │   └── GRPC_Dashboard.json     # gRPC 监控仪表板（课程提供）
│   │   └── provisioning/
│   │       ├── datasources/
│   │       │   └── influxdb.yml        # InfluxDB 2.x Flux 数据源
│   │       ├── dashboards/
│   │       │   └── dashboards.yml      # Dashboard 自动加载器
│   │       └── alerting/
│   │           ├── alert_rules.yaml    # CPU 告警规则（SNMP + gRPC）
│   │           └── alert_resources.yaml # DingDing 联系点 + 通知策略
│   └── router/
│       └── c8kv_telemetry_config.txt   # 路由器 SNMP + gRPC Telemetry 配置参考
└── README.md
```

---

## 架构与数据流

```
┌─────────────────────────────────────────────────────────┐
│  路由器（C8Kv1 / C8Kv2）                                │
│                                                         │
│  [SNMP Agent] ←────── Telegraf 每 10s GET ──────────┐   │
│  [gRPC MDT]  ─────── 路由器每 10s PUSH ──────────┐  │   │
└─────────────────────────────────────────────────────┼──┼─┘
                                                     │  │
┌────────────────────────────────────────────────────┼──┼─┐
│  Docker Compose (10.10.1.205)                      │  │  │
│                                                    ▼  ▼  │
│  ┌─────────────┐    ┌──────────────┐    ┌──────────────┐│
│  │  Telegraf    │───▶│  InfluxDB 2  │◀───│   Grafana    ││
│  │  :57000(gRPC)│    │  :8086       │    │   :3000      ││
│  └─────────────┘    └──────────────┘    └──────┬───────┘│
│                                                 │        │
│                                          Alert Rule      │
│                                                 │        │
│                                          DingDing        │
│                                          Contact Point   │
└─────────────────────────────────────────────────┼────────┘
                                                  │
                                                  ▼
                                        钉钉群机器人 Webhook
```

---

## 监控指标对照

| 维度 | SNMP（主动轮询） | gRPC（被动接收） |
|------|-----------------|-----------------|
| CPU | `CPUTotal5sec-iosd` (OID 1.3.6.1.4.1.9.2.1.56.0) | `five_seconds` (YANG: process-cpu-ios-xe-oper) |
| 内存 | `MemoryUsed` + `MemoryFree` (CISCO-PROCESS-MIB) | `memory-statistic` (YANG: memory-ios-xe-oper) |
| 接口 | `ifInOctets` / `ifOutOctets` (IF-MIB) | `interfaces/interface/statistics` (YANG: interfaces-ios-xe-oper) |

---

## 运行步骤

### 1. 配置路由器（SNMP + gRPC Telemetry）

在 C8Kv1 和 C8Kv2 上执行 `router/c8kv_telemetry_config.txt` 中的命令：

```
snmp-server community qytangro RO
netconf-yang

telemetry ietf subscription 666
 encoding encode-kvgpb
 filter xpath /process-cpu-ios-xe-oper:cpu-usage/cpu-utilization/five-seconds
 stream yang-push
 update-policy periodic 1000
 receiver ip address 10.10.1.205 57000 protocol grpc-tcp

! ... 667(内存) / 671(接口) 类似
```

### 2. 配置钉钉 Webhook

将钉钉群机器人 Webhook URL 写入 `.env`：

```bash
cp dingtalk.env.example .env
# 编辑 .env，填入实际 Webhook URL
```

### 3. 一键启动

```bash
cd /netdevops/homework/4.opensourcesoftware/DAY3/Code
docker compose up -d
```

三个容器自动完成：
- InfluxDB：初始化 org=qytang / bucket=qytdb / admin token
- Telegraf：SNMP 轮询 + gRPC 监听 :57000
- Grafana：自动加载数据源、Dashboard、告警规则、钉钉联系点

### 4. 验证数据入库

```bash
# SNMP 数据
curl -s -H "Authorization: Token qytang-day3-token" \
  -H "Content-Type: application/vnd.flux" \
  -d 'from(bucket:"qytdb") |> range(start:-5m) |> filter(fn:(r) => r._measurement == "C8Kv_Snmp_v2c") |> last()' \
  http://localhost:8086/api/v2/query?org=qytang

# gRPC 数据
curl -s -H "Authorization: Token qytang-day3-token" \
  -H "Content-Type: application/vnd.flux" \
  -d 'from(bucket:"qytdb") |> range(start:-5m) |> filter(fn:(r) => r._measurement == "Cisco-IOS-XE-process-cpu-oper:cpu-usage/cpu-utilization") |> last()' \
  http://localhost:8086/api/v2/query?org=qytang
```

### 5. 测试告警 + 钉钉通知

```bash
python3 generate_traffic.py
```

---

## Grafana Dashboard 说明

### SNMP Dashboard（2×2 布局）
| 位置 | 面板 | 数据来源 |
|------|------|---------|
| 左上 | 路由器CPU利用率 | C8Kv_Snmp_v2c / CPUTotal5sec-iosd |
| 右上 | 路由器内存利用率 | C8Kv_Snmp_v2c / MemoryUsed+MemoryFree 计算 |
| 左下 | 路由器 接口速率入向 | interface_table / InSpeed |
| 右下 | 路由器 接口速率出向 | interface_table / OutSpeed |

### GRPC Dashboard（2×2 布局）
| 位置 | 面板 | 数据来源 |
|------|------|---------|
| 左上 | CPU利用率 | cpu-usage/cpu-utilization / five_seconds |
| 右上 | 内存利用率 | memory-statistics / memory_utilization 计算 |
| 左下 | 接口速率入向 | interfaces-state/interface/statistics |
| 右下 | 接口速率出向 | interfaces-state/interface/statistics |

---

## 告警规则

| 规则名称 | 数据源 | 条件 | 通知方式 |
|---------|--------|------|---------|
| 【告警】C8Kv SNMP IOSd CPU 超过 3% | SNMP measurement / CPUTotal5sec-iosd | max > 3% | 钉钉群机器人 |
| 【告警】C8Kv gRPC CPU 超过 3% | gRPC measurement / five_seconds | max > 3% | 钉钉群机器人 |

评估间隔：10s | Pending 时间：0s（立即触发） | 无数据状态：OK

---

## 访问信息

| 服务 | URL | 账号 |
|------|-----|------|
| Grafana | http://10.10.1.205:3000 | admin / Cisc0123 |
| InfluxDB | http://10.10.1.205:8086 | admin / Cisc0123 |

---

## 截图清单

| # | 截图内容 | 截什么 |
|---|---------|--------|
| ① | `docker compose up -d` 终端输出 | 完整终端：三个容器 Creating → Started，无报错 |
| ② | `docker compose ps` 终端输出 | 显示三行服务全部 Up + 端口映射（8086/57000/3000） |
| ③ | SNMP Dashboard 全貌 | Grafana 浏览器：选 Last 15 min，4 个面板（CPU/内存/入向/出向）全部有曲线 |
| ④ | GRPC Dashboard 全貌 | Grafana 浏览器：选 Last 15 min，4 个面板全部有曲线（C8Kv1 + C8Kv2 双线） |
| ⑤ | Grafana Alerting → Alert rules | 展开 Day3 TIG > day3_cpu_group，显示 2 条规则名称 + State（Normal 或 Firing） |
| ⑥ | Grafana Alerting → Contact points | 截到 day3-dingtalk 条目，类型 DingDing，状态 Provisioned |
| ⑦ | 钉钉群告警消息 | 手机/PC 钉钉截图：显示「【告警】C8Kv SNMP IOSd CPU 超过 3%」和 gRPC 两条通知 |
| ⑧ | InfluxDB Data Explorer（SNMP） | 浏览器打开 http://IP:8086 → Data Explorer，查询 bucket=qytdb / measurement=C8Kv_Snmp_v2c，显示有数据行 |
| ⑨ | InfluxDB Data Explorer（gRPC） | 同上，measurement=Cisco-IOS-XE-process-cpu-oper:cpu-usage/cpu-utilization，显示有数据行 |

---

## 提交文件清单

| 文件 | 说明 |
|------|------|
| `docker-compose.yml` | TIG 三服务编排（InfluxDB 2.7.9 + Telegraf 1.31.2 + Grafana 11.1.1） |
| `telegraf.conf` | Telegraf 全配置：SNMP 轮询 + gRPC 监听 + InfluxDB 2.x 写入 |
| `SNMP_Dashboard.json` | SNMP 监控 Dashboard（CPU/内存/接口 2×2，课程提供） |
| `GRPC_Dashboard.json` | gRPC 监控 Dashboard（CPU/内存/接口 2×2，课程提供） |
| `alert_resources.yaml` | DingDing 联系点 + 通知策略 |
| `alert_rules.yaml` | CPU 告警规则（SNMP + gRPC 双路径，阈值 > 3%） |
| `dashboards.yml` | Dashboard 自动加载器配置 |
| `influxdb.yml` | InfluxDB 2.x Flux 数据源自动配置 |
