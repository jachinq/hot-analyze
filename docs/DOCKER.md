# Docker 部署说明（Debian）

本服务将 **FastAPI + Vue 前端** 打进同一镜像。拓扑约定：

| 服务 | 位置 | 容器内访问方式 |
|------|------|----------------|
| hot-analyze | Docker 容器 | `http://<服务器IP>:8000` |
| hot-collector | **宿主机** | `http://host.docker.internal:8080` |
| 本地大模型（LM Studio / Ollama） | **局域网其他机器** | `http://<局域网IP>:<端口>/v1` |

---

## 1. Debian 安装 Docker

以 root 或 sudo 执行（官方仓库方式）：

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a644 /etc/apt/keyrings/docker.asc

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
| sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker "$USER"
```

重新登录后验证：

```bash
docker version
docker compose version
```

### 1.1 国内网络：配置镜像加速（强烈推荐）

若构建时报 `auth.docker.io` / `registry-1.docker.io` **i/o timeout**，是访问 Docker Hub 不通。在 Debian 上配置 registry mirror 后重启 Docker：

```bash
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json >/dev/null <<'EOF'
{
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://docker.1ms.run"
  ]
}
EOF
sudo systemctl daemon-reload
sudo systemctl restart docker
```

然后重试 `docker compose build`。镜像地址若失效，可换成当前可用的国内加速源。

构建 Python / 前端依赖也可走国内源（编辑 `docker-compose.yml` 的 `build.args`）：

```yaml
args:
  PIP_INDEX_URL: https://pypi.tuna.tsinghua.edu.cn/simple
  NPM_REGISTRY: https://registry.npmmirror.com
```

---

## 2. 部署前准备

在项目根目录：

```bash
# 密钥（不要提交仓库）
cp .env.example .env
# 编辑 .env：至少设置 ENCRYPT_KEY；按需设置 DEEPSEEK_API_KEY 等
# 生成 Fernet 密钥示例：
# python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 数据目录（镜像内以 uid=10001 运行，需可写）
mkdir -p data
sudo chown -R 10001:10001 data
```

编辑 `config.docker.yaml`：

1. **大模型地址**：把 `192.168.1.50` 改成局域网真实 IP 与端口。  
2. **模型名**：与 LM Studio / Ollama 中实际加载的模型 ID 一致。  
3. **collector**：默认 `http://host.docker.internal:8080`，一般无需改（collector 在宿主机）。

宿主机上确认 collector 监听可被 Docker 网桥访问。若 collector **只绑 `127.0.0.1`**，`host.docker.internal` 可能仍可达（经 host-gateway）；若不通，请让 collector 监听 `0.0.0.0:8080`，或改用下文「备选：host 网络」。

---

## 3. 构建与启动

```bash
cd /path/to/hot-analyze

# 构建（前端 + Python 依赖多阶段）
# 若仍超时：先完成 §1.1 镜像加速，再执行
docker compose build

# 后台启动
docker compose up -d

# 日志
docker compose logs -f hot-analyze
```

访问：

- Web / API：`http://<服务器IP>:8000`
- OpenAPI：`http://<服务器IP>:8000/docs`
- 健康检查：`http://<服务器IP>:8000/health`（含 `collector` 字段）

---

## 4. 联通性排查

### 4.1 容器 → 宿主机 collector

```bash
docker compose exec hot-analyze curl -fsS http://host.docker.internal:8080/health
docker compose exec hot-analyze curl -fsS "http://host.docker.internal:8080/api/hot/list?date=$(date +%F)&pageSize=1"
```

失败时检查：

- 宿主机 `curl http://127.0.0.1:8080/health` 是否正常  
- `docker compose` 是否包含 `extra_hosts: host.docker.internal:host-gateway`  
- 宿主机防火墙是否放行来自 Docker 网桥（常见网段 `172.17.0.0/16` 或 `172.18.0.0/16`）访问 8080  

### 4.2 容器 → 局域网大模型

```bash
# 将 IP/端口换成 config.docker.yaml 中的值
docker compose exec hot-analyze curl -fsS http://192.168.1.50:1234/v1/models
```

失败时检查：

- 大模型机器防火墙是否允许本机 Debian 服务器访问  
- 服务是否监听 `0.0.0.0`（不要只绑对端本机回环）  
- 从 **Debian 宿主机** 先 `curl` 同一地址，区分「宿主机不可达」与「仅容器不可达」  

### 4.3 应用内探测

启动后打开设置页或调用连通性 API；也可用：

```bash
curl -fsS http://127.0.0.1:8000/health
```

`collector: true` 表示已能连上采集服务。

---

## 5. 日常运维

```bash
# 停止 / 启动
docker compose stop
docker compose start

# 更新代码后重新构建并滚动
docker compose build
docker compose up -d

# 手动触发一次分析
curl -X POST "http://127.0.0.1:8000/api/jobs/analyze?date=$(date +%F)&sync=true"
```

数据文件在宿主机 `./data/analyzer.db`，重建容器不会丢库（只要保留该目录）。

修改 `config.docker.yaml` 后通常需要重启容器使进程重新加载配置：

```bash
docker compose restart hot-analyze
```

---

## 6. 备选：host 网络

若 bridge + `host.docker.internal` 访问宿主机 collector 有问题，可在 `docker-compose.yml` 中改为：

```yaml
services:
  hot-analyze:
    network_mode: host
    # 使用 host 网络时不要写 ports / extra_hosts
    # collector 可改回 http://127.0.0.1:8080
    # 局域网大模型地址保持不变
```

同时把 `config.docker.yaml` 里 `collector.base_url` 改为 `http://127.0.0.1:8080`。  
`network_mode: host` 仅适用于 **Linux（Debian）**，容器与宿主机共用网络栈。

---

## 7. 镜像与体积说明

- 多阶段：Node 构建前端 → `uv sync --frozen --no-dev` → `python:3.11-slim-bookworm` 运行时  
- 最终镜像只含 venv、`app/`、`frontend/dist`、精简系统库（`libgomp1` 等）  
- 密钥不进镜像；配置与数据库用挂载  

---

## 8. 安全建议

- `.env` 权限：`chmod 600 .env`  
- 勿将含真实密钥的 `.env` / 生产库提交 Git  
- 若仅内网使用，可用防火墙限制 8000 仅内网网段访问  
