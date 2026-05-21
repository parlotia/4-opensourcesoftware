# DAY4 开源自动化运维作业（gNMIc + Prometheus + Grafana）

## 作业背景

本次作业要求使用 **gNMIc + Prometheus + Grafana** 搭建 gNMI Dial-In 模式的网络设备监控平台。gNMIc 主动连接 Cisco C9800 无线控制器的 gNMI server，订阅 CPU、内存和接口计数器数据，通过 Prometheus pull 模型暴露 metrics，最终在 Grafana 中展示四个核心面板。

### 与 DAY3 的区别

| 维度 | DAY3 (TIG) | DAY4 (gNMIc + Prometheus) |
|------|-----------|--------------------------|
| 采集方式 | Telegraf SNMP 轮询 + gRPC Dial-Out 推送 | gNMIc gNMI Dial-In 主动订阅 |
| 时序数据库 | InfluxDB 2.x (Flux) | Prometheus (PromQL) |
| 采集器 | Telegraf | gNMIc |
| 数据流向 | 设备 → Telegraf → InfluxDB → Grafana | gNMIc → 设备 (订阅) → gNMIc → Prometheus → Grafana |
| 设备 | C8Kv (IOS XE 17.08) | C9800-CL (IOS XE 17.14) |

---

## 实验环境

| 设备 | 管理 IP | 角色 |
|------|---------|------|
| C9800-CL | 10.10.1.203 | 无线控制器（IOS XE 17.14.01）|
| Linux Server | 10.10.1.205 | 监控平台宿主机（Rocky 9）|

**容器版本：**

| 组件 | 镜像版本 | 端口 |
|------|---------|------|
| gNMIc | `ghcr.io/openconfig/gnmic:latest` | 9804 |
| Prometheus | `prom/prometheus:latest` | 9090 |
| Grafana | `grafana/grafana:11.1.1` | 3000 |

---

## 项目结构

```
DAY4/
├── Code/
│   ├── docker-compose.yml                          # 一键启动三服务
│   ├── gnmic.yaml                                  # gNMIc 设备连接 + 订阅 + Prometheus 输出
│   ├── prometheus.yml                              # Prometheus 抓取 gNMIc :9804/metrics
│   ├── cert/
│   │   └── ca.cer                                  # qytang CA 根证书（TLS 验证）
│   └── grafana/
│       ├── dashboards/
│       │   └── GNMIc_Prometheus_Dashboard.json     # Dashboard（4 面板：CPU/内存/接口入/出）
│       └── provisioning/
│           ├── datasources/
│           │   └── prometheus.yml                  # Prometheus 数据源自动加载
│           └── dashboards/
│               └── dashboards.yml                  # Dashboard 自动加载器
└── README.md
```

---

## 架构与数据流

```
┌──────────────────────────────────────────────────────────────┐
│  C9800-CL 无线控制器（10.10.1.203）                           │
│                                                              │
│  [gNMI Server :9339] ◀── gNMIc Dial-In Subscribe ──────┐    │
│   · TLS (qytang CA 签发证书)                             │    │
│   · STREAM sample 每 10s                                 │    │
└──────────────────────────────────────────────────────────┼────┘
                                                          │
┌─────────────────────────────────────────────────────────┼────┐
│  Docker Compose (10.10.1.205)                           │    │
│                                                         ▼    │
│  ┌─────────────┐    ┌──────────────┐    ┌──────────────────┐ │
│  │   gNMIc     │───▶│  Prometheus  │◀───│     Grafana      │ │
│  │   :9804     │    │  :9090       │    │     :3000        │ │
│  │  /metrics   │    │  每 10s 抓取  │    │  PromQL 查询     │ │
│  └─────────────┘    └──────────────┘    └──────────────────┘ │
│                                                              │
│  gNMI Subscribe ──▶ Prometheus metrics ──▶ PromQL ──▶ 图表  │
└──────────────────────────────────────────────────────────────┘
```

**数据链路四步走：**

1. C9800 开启 gNMI server（端口 9339），使用 qytang CA 签发的 TLS 证书
2. gNMIc 以用户名/密码 + CA 证书连接设备，订阅 CPU/内存/接口计数器三个 YANG 路径
3. gNMIc 将收到的数据转换为 Prometheus metrics，暴露在 `:9804/metrics`
4. Prometheus 每 10s 抓取 `gnmic:9804`，Grafana 通过 PromQL 查询展示四个面板

---

## gNMI 订阅路径说明

| 订阅名 | YANG 路径 | 采集内容 | 产生的 Prometheus 指标 |
|--------|----------|---------|----------------------|
| `cpu` | `/components/component/cpu/utilization/state/instant` | CPU 瞬时利用率 (%) | `gnmic_cpu_components_component_cpu_utilization_state_instant` |
| `memory` | `/system/memory/state` | 系统物理内存 / 已用内存 | `gnmic_memory_system_memory_state_physical` / `_reserved` |
| `interface-counters` | `/interfaces/interface/state/counters` | 接口累计收发字节数 | `gnmic_interface_counters_..._in_octets` / `_out_octets` |

> **注意**：C9800-CL 对 OpenConfig CPU 路径 `/components/component/cpu/utilization/state` 整体订阅会返回 `Canceled by operator` 错误（内部 uint8_t 溢出），需精确到 `instant` 叶子节点才能正常工作。

---

## gNMI 证书体系

本作业使用 **qytang CA** 签发的完整证书链，与老师环境一致，gNMIc **无需 skip-verify**：

```
qytang CA 根证书 (ca.cer)
    └── 签发 C9800 服务器证书 (含 IP SAN: 10.10.1.203)
            └── 导入 C9800 PKCS12 (trustpoint: QYTCA-GNMI)
                    └── gNMIc 用 tls-ca 验证
```

C9800 关键配置：

```
gnxi
gnxi secure-server
gnxi secure-port 9339
gnxi secure-trustpoint QYTCA-GNMI
```

---

## 运行步骤

### 1. 确认 C9800 gNMI 服务已开启

```bash
# SSH 登录 C9800 验证
ssh admin@10.10.1.203
show running-config | section gnxi
# 应显示 gnxi / gnxi secure-server / gnxi secure-port 9339 / gnxi secure-trustpoint QYTCA-GNMI
```

### 2. 一键启动

```bash
cd /netdevops/homework/4.opensourcesoftware/DAY4/Code
docker compose up -d
docker compose ps
```

三个容器自动完成：
- **gNMIc**：连接 C9800 :9339，订阅三类数据，暴露 `:9804/metrics`
- **Prometheus**：每 10s 抓取 `gnmic:9804`，存储时序数据
- **Grafana**：自动加载 QYT Prometheus 数据源 + Day4 Dashboard

### 3. 验证 gNMIc 连接

```bash
# 查看 gNMIc 日志，确认无 error/cancel
docker compose logs -f gnmic

# 验证 metrics 输出
curl http://127.0.0.1:9804/metrics | grep gnmic_cpu
curl http://127.0.0.1:9804/metrics | grep gnmic_memory
curl http://127.0.0.1:9804/metrics | grep gnmic_interface_counters.*octets
```

### 4. 验证 Prometheus 抓取

```bash
# Prometheus Targets 页面
http://10.10.1.205:9090/targets
# 确认 gnmic:9804 状态为 UP
```

### 5. 访问 Grafana Dashboard

```bash
http://10.10.1.205:3000
# admin / Cisc0123
# 自动加载文件夹：Day4 gNMIc
# Dashboard：Day4 · gNMIc + Prometheus（C9800）
```

---

## Dashboard 说明

### Day4 · gNMIc + Prometheus（C9800） — 2×2 布局

| 位置 | 面板 | PromQL | 单位 |
|------|------|--------|------|
| 左上 | CPU 利用率（%） | `gnmic_cpu_components_component_cpu_utilization_state_instant` | percent (0-100) |
| 右上 | 内存利用率（%） | `(gnmic_memory_system_memory_state_reserved / gnmic_memory_system_memory_state_physical) * 100` | percent (0-100) |
| 左下 | 接口速率入向（bps） | `sum by (source, interface_name) (rate(gnmic_interface_counters_..._in_octets[1m]) * 8)` | bps |
| 右下 | 接口速率出向（bps） | `sum by (source, interface_name) (rate(gnmic_interface_counters_..._out_octets[1m]) * 8)` | bps |

> 接口计数器返回 octets（字节），乘以 8 转换为 bits，`rate()` 函数计算每秒速率。

---

## 访问信息

| 服务 | URL | 账号 |
|------|-----|------|
| Grafana | http://10.10.1.205:3000 | admin / Cisc0123 |
| Prometheus | http://10.10.1.205:9090 | 无需登录 |
| gNMIc Metrics | http://10.10.1.205:9804/metrics | 无需登录 |

---

## 截图清单

| # | 截图内容 | 截什么 |
|---|---------|--------|
| ① | `docker compose up -d` 终端输出 | 完整终端：三个容器 Creating → Started，无报错 |
| ② | `docker compose ps` 终端输出 | 显示三行服务全部 Up + 端口映射（9804/9090/3000） |
| ③ | Prometheus Targets 页面 | 浏览器：gnmic:9804 状态为 UP，Last Scrape 正常刷新 |
| ④ | Grafana Dashboard 全貌 | 浏览器：选 Last 15 min，4 个面板（CPU/内存/入向/出向）全部有数据 |
| ⑤ | `curl metrics` 终端输出 | 终端：`curl http://127.0.0.1:9804/metrics` 显示 gnmic_cpu / gnmic_memory 指标 |

---

## 踩坑记录

### 1. C9800 实际 IP 确认

老师提供的 10.10.1.205 实际是 Linux 服务器本机 IP，C9800 真实管理 IP 为 10.10.1.203，需通过网段扫描确认。

### 2. CPU 订阅 "Canceled by operator"

C9800-CL 对 OpenConfig 路径 `/components/component/cpu/utilization/state` 的整体订阅会因内部 uint8_t 值溢出返回错误。解决方案：将路径精确到叶子节点 `/components/component/cpu/utilization/state/instant`。

### 3. qytang CA 证书体系搭建

C9800 默认使用自签名证书（无 IP SAN），gNMIc 无法通过 IP 进行 TLS 验证。最终方案：用 qytang CA 私钥签发包含 `IP:10.10.1.203` SAN 的服务器证书，生成 PKCS12 导入 C9800，实现与老师环境一致的 CA 验证链。

### 4. C9800 时钟偏差

C9800 时钟被设置为北京时间但标记为 UTC，导致签发的证书 `notBefore` 在"未来"。修复：`clock set` 纠正为正确 UTC 时间后重新生成证书。

---

## 提交文件清单

| 文件 | 说明 |
|------|------|
| `docker-compose.yml` | 三服务编排（gNMIc + Prometheus + Grafana 11.1.1） |
| `gnmic.yaml` | gNMIc 全配置：设备连接 + 三路订阅 + Prometheus 输出 |
| `prometheus.yml` | Prometheus 抓取配置：gnmic:9804 每 10s |
| `cert/ca.cer` | qytang CA 根证书（TLS 验证） |
| `GNMIc_Prometheus_Dashboard.json` | Dashboard JSON（CPU/内存/接口入向/出向 2×2 布局） |
| `prometheus.yml` (datasources) | Grafana Prometheus 数据源自动加载 |
| `dashboards.yml` | Dashboard 自动加载器配置 |
