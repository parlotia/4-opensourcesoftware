# 开源自动化运维软件 DAY5 — EFK NetFlow 流量可视化

## 作业背景

使用 Docker Compose 一键部署 Elasticsearch + Kibana + Filebeat NetFlow 平台，接收路由器导出的 NetFlow v9 流量数据，在 Kibana 中完成"按协议分布"和"按源 IP 分布"两个饼图，并组合为统一 Dashboard。

## 实验环境

| 组件 | 版本/地址 |
|------|-----------|
| Linux 服务器 | 10.10.1.205 (Rocky Linux 9.7) |
| C8Kv1 路由器 | 10.10.1.201 |
| Elasticsearch | 7.17.21 |
| Kibana | 7.17.21 |
| Filebeat | 7.17.21 |
| NetFlow 监听端口 | UDP 2055 |

## 项目结构

```
DAY5/Code/
├── docker-compose.yml                  # 三容器编排（ES + Kibana + Filebeat）
└── filebeat-netflow/
    ├── filebeat.yml                    # Filebeat 主配置（输出到 ES）
    ├── netflow.yml                     # NetFlow 模块配置
    ├── netflow-mod-ip.js              # JS处理器：NAT后真实IP提取
    └── netflow-mod-domain.js          # JS处理器：缺失域名补全
```

## 架构数据流

```
┌─────────────┐     NetFlow v9      ┌──────────────────┐      写入       ┌───────────────┐
│   C8Kv1     │ ──── UDP:2055 ────▶ │  Filebeat        │ ──────────────▶ │ Elasticsearch │
│  路由器      │                     │  (netflow module)│                 │  (9200)       │
└─────────────┘                     └──────────────────┘                 └───────┬───────┘
                                                                                  │
                                                                                  ▼
                                                                         ┌───────────────┐
                                                                         │    Kibana     │
                                                                         │   (5601)      │
                                                                         └───────────────┘
```

## 路由器 NetFlow 配置

```
flow record Qytang-Record
 match ipv4 source address
 match ipv4 destination address
 match ipv4 protocol
 match transport destination-port
 match transport source-port
 match interface input
 collect counter bytes

flow exporter Netflow-Exporter
 destination 10.10.1.205
 transport udp 2055
 template data timeout 30

flow monitor Monitor1
 exporter Netflow-Exporter
 record Qytang-Record
!
interface GigabitEthernet1
 ip flow monitor Monitor1 input
 ip flow monitor Monitor1 output
!
interface GigabitEthernet2
 ip flow monitor Monitor1 input
 ip flow monitor Monitor1 output
```

## 运行步骤

```bash
# 1. 进入代码目录
cd DAY5/Code/

# 2. 一键启动
docker compose up -d

# 3. 验证 ES 集群健康
curl http://localhost:9200/_cluster/health?pretty

# 4. 验证 Kibana 可访问
curl -o /dev/null -w "%{http_code}" http://localhost:5601/api/status

# 5. 等待 NetFlow 数据（约30-60秒）
curl http://localhost:9200/_cat/indices?v | grep filebeat
```

## Kibana 可视化配置

### 饼图一：By Protocol（按协议排序）

| 配置项 | 值 |
|--------|-----|
| Metric | Sum of `network.bytes` |
| Bucket | Terms on `network.transport` |
| Order | Descending by metric |

### 饼图二：By IP（按源 IP 排序）

| 配置项 | 值 |
|--------|-----|
| Metric | Sum of `network.bytes` |
| Bucket | Terms on `source.ip` |
| Order | Descending by metric |

### Dashboard

将两个饼图并排放入同一 Dashboard，命名为 "NetFlow Dashboard"。

## 访问地址

| 服务 | URL |
|------|-----|
| Elasticsearch | http://10.10.1.205:9200 |
| Kibana 首页 | http://10.10.1.205:5601 |
| Visualize Library | http://10.10.1.205:5601/app/visualize |
| NetFlow Dashboard | http://10.10.1.205:5601/app/dashboards |

## 截图清单

1. Visualize Library 列表（显示 By Protocol 和 By IP 两个可视化）
2. By Protocol 饼图效果
3. By IP 饼图效果
4. NetFlow Dashboard 最终效果（两图并排）

## 提交文件清单

| 文件 | 说明 |
|------|------|
| `docker-compose.yml` | 三容器编排配置 |
| `filebeat-netflow/filebeat.yml` | Filebeat 输出配置 |
| `filebeat-netflow/netflow.yml` | NetFlow 模块启用 |
| `filebeat-netflow/netflow-mod-ip.js` | IP 提取处理器 |
| `filebeat-netflow/netflow-mod-domain.js` | 域名补全处理器 |
| `README.md` | 本文档 |
