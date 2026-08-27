# Hostinger VPS 部署手册（Streamlit 看板，Docker + Caddy）

> 适用：Hostinger **VPS**（共享主机不适用）。
> 镜像：`ghcr.io/fancy0121/13f-intelligence:latest`（公开，无需登录即可 pull）。
> 本手册只负责把已构建好的看板托管到你的 VPS；数据更新走 GitHub Actions
> （见下文「如何更新数据」），不在服务器上跑 SEC 下载。

---

## 0. 架构总览

```
GitHub Actions（push master 自动构建）
   │  构建期：python scripts/update_data.py（SEC 下载 → 建库）
   ▼
GHCR 镜像 ghcr.io/fancy0121/13f-intelligence:latest（内含 SQLite 数据库）
   ▼
你的 VPS：docker run（只读查询，运行期不访问 SEC）
   ▼
Caddy 反向代理（80/443，自动 HTTPS）→ Streamlit 端口 8501（只绑定 127.0.0.1）
   ▼
用户浏览器访问 https://你的域名
```

运行期容器只做只读查询，**不会**实时请求 SEC；数据新鲜度由 13F 季度披露决定
（最多 45 天延迟），不是行情实时。

---

## 1. 准备

- Hostinger VPS 一台，系统选 **Ubuntu 22.04 / 24.04**（hPanel 创建时可选）。
- 一个域名（可选但推荐；没有域名则只能走 IP + HTTP，见第 5 节）。
- 你的本机 SSH 能登录 VPS（Hostinger 创建后会把 root 密码/密钥发到邮箱）。

---

## 2. 登录 VPS 并安装 Docker

在你自己电脑的终端（PowerShell 或 CMD）里：

```bash
ssh root@你的服务器IP
```

登录后执行（Ubuntu 官方安装脚本，一次装完 Docker + Compose 插件）：

```bash
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker
docker --version
```

看到版本号即安装成功。

---

## 3. 拉取镜像并启动容器

```bash
docker pull ghcr.io/fancy0121/13f-intelligence:latest

docker run -d \
  --name thirteenf \
  --restart unless-stopped \
  -p 127.0.0.1:8501:8501 \
  ghcr.io/fancy0121/13f-intelligence:latest
```

说明：

- `-p 127.0.0.1:8501:8501`：**只绑定本机回环地址**，公网无法直接访问 8501，
  由 Caddy 统一对外（更安全）。
- `--restart unless-stopped`：服务器重启 / 容器崩溃后自动拉起。

验证容器起来了：

```bash
docker ps                       # STATUS 应为 Up
docker logs --tail 50 thirteenf # 看到 Streamlit 启动日志
curl -s http://127.0.0.1:8501/_stcore/health   # 输出 ok
```

---

## 4. 安装 Caddy 并配置 HTTPS + 域名

### 4.1 先解析域名

在 Hostinger hPanel（或你的 DNS 服务商）把域名加一条 **A 记录**：

| 类型 | 主机 | 值 |
| ---- | ---- | ---- |
| A    | @（或 www） | 你的 VPS IP |

等待几分钟让 DNS 生效（可用 `ping 你的域名` 看是否解析到 VPS IP）。

### 4.2 安装 Caddy

```bash
apt update
apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt update
apt install -y caddy
```

### 4.3 写 Caddyfile

```bash
nano /etc/caddy/Caddyfile
```

把内容替换为（**把 `你的域名` 换成真实域名**）：

```
你的域名 {
    reverse_proxy 127.0.0.1:8501
}
```

保存后重载：

```bash
systemctl reload caddy
systemctl status caddy
```

Caddy 会自动申请 Let's Encrypt 证书并启用 HTTPS。

---

## 5. 没有域名怎么办（快速体验，仅 HTTP）

跳过第 4 节，改为把 8501 直接暴露（不推荐长期使用，无 HTTPS）：

```bash
# 先删掉只绑定回环的容器
docker rm -f thirteenf
# 重新以 0.0.0.0 启动
docker run -d \
  --name thirteenf \
  --restart unless-stopped \
  -p 8501:8501 \
  ghcr.io/fancy0121/13f-intelligence:latest
```

然后在 Hostinger hPanel → 防火墙（Firewall）放行 **8501** 端口，
浏览器访问 `http://你的服务器IP:8501`。

---

## 6. 防火墙（推荐配置）

Hostinger hPanel → 服务器 → 防火墙：

- 放行 **22**（SSH，务必保留）
- 放行 **80 / 443**（Caddy / HTTPS）
- **不要**放行 8501（按第 4 节配置时，8501 只在服务器内部使用）

---

## 7. 如何更新数据（以后每次更新）

数据在**镜像构建期**生成，所以更新流程是：

1. 本地仓库改完配置/代码后推送到 GitHub：
   ```bash
   git push origin master
   ```
2. GitHub Actions 自动重新构建镜像（约 30-35 分钟，含 SEC 建库），完成后自动推送到 GHCR。
3. 在 VPS 上执行（拉新镜像 + 重建容器，约 1 分钟）：
   ```bash
   docker pull ghcr.io/fancy0121/13f-intelligence:latest
   docker rm -f thirteenf
   docker run -d \
     --name thirteenf \
     --restart unless-stopped \
     -p 127.0.0.1:8501:8501 \
     ghcr.io/fancy0121/13f-intelligence:latest
   ```
4. 刷新页面即可看到新数据（总览页 DATA STATUS 会显示新的更新时间）。

> 提示：也可以写成一个 `update.sh` 一键脚本，以后只跑 `bash update.sh`。

---

## 8. 上线后检查清单

- [ ] `curl -s http://127.0.0.1:8501/_stcore/health` 返回 `ok`
- [ ] 浏览器打开 `https://你的域名` 能正常显示总览页
- [ ] 总览页第一屏 **DATA STATUS** 显示最新报告季度、filing 日期、机构覆盖
- [ ] 数据质量警告（如有缺失/陈旧）正常显示，而不是报错
- [ ] 服务器重启后容器自动恢复（`docker ps` 检查）

---

## 9. 常见问题

### 页面打不开 / 502

```bash
docker logs --tail 100 thirteenf   # 看 Streamlit 日志
curl -s http://127.0.0.1:8501/_stcore/health
systemctl status caddy             # 看 Caddy 是否正常
```

常见原因：容器没起来（`docker ps` 为空 → 重新 `docker run`）、Caddyfile 域名拼错、
DNS 还没生效。

### 想保留用户在本页添加的「我的组合」数据

容器重建会清空运行期写入的数据（例如页面上手动添加的组合）。
如果需要持久化，挂载一个卷（把容器内 `/app/data` 里的用户数据目录映射出来），
具体目录以 `app/app.py` 实际写盘位置为准；本项目默认以「重建即重置」为预期行为，
公开页不建议依赖持久化。

### 端口被占 / 容器冲突

```bash
docker ps -a          # 查看
docker rm -f thirteenf
```

### 镜像拉取失败

确认仓库/镜像公开后重试；或先 `docker pull ghcr.io/fancy0121/13f-intelligence:latest`
看具体报错。

---

## 10. 安全与合规提醒

- 当前看板**无登录认证**（v0.4 范围冻结）。公开地址等于任何人可读；
  页面内容为 evidence-only，不含任何推荐/预测。
- 运行期容器**不访问 SEC**，不涉及 SEC 限流问题（限流只发生在 GitHub Actions 构建期，
  已用 `--rate-limit 0.6` 合规节流）。
- 不要上传 `.env`、密钥或本地敏感配置到服务器；本项目运行不需要任何密钥。
- 若将来加行情 API 等需要 key 的服务，用环境变量注入，不要写进镜像或仓库。

---

## 11. 相关文件

- 镜像构建：`Dockerfile`、`.github/workflows/build-image.yml`
- 数据构建：`scripts/update_data.py`
- 应用入口：`app/app.py`（健康检查 `/_stcore/health`）
- 其他托管方式：`README_DEPLOY.md`
