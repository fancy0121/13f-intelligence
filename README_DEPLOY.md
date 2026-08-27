# 公开部署指南（Streamlit 看板托管）

> 版本：v0.5.1 交付层补充。本指南只负责**把现有看板托管到公网**，
> 不改变任何产品/研究逻辑。预测研究保持冻结（`PREDICTIVE_RESEARCH_STOP_RULE=TRIGGERED`），
> 公开页面仍然是 **evidence-only**，不含任何推荐/评分/预测。

## 0. 先看明白的事

- 看板是 **Python + SQLite + Streamlit**，不是纯静态站点，所以**不能**用 GitHub Pages 直接托管。
- 数据库约 150MB（600k+ holdings），**不能提交进 git**。
- 因此采用「**Docker 构建期建库**」：镜像构建时运行
  `python scripts/update_data.py`（从 SEC 下载原始 filing → 生成数据库），
  之后容器只做只读查询。
- 数据仍是 13F 披露：**最多 45 天延迟、按季度更新**，不是行情实时。

仓库已提供的部署资产：

- `requirements.txt` — 运行依赖
- `streamlit_app.py` — 通用入口（Streamlit Cloud 用）
- `Dockerfile` — 构建期建库 + 启动看板
- `render.yaml` — Render 一键配置
- `scripts/update_data.py` — 复用现有 ingest/normalize/analyze（含 `--rate-limit`）
- `deploy/hostinger_vps.md` — Hostinger VPS 部署手册（Docker + Caddy + HTTPS）

---

## 方案 A1：Hugging Face Spaces（推荐，Docker，免费）

1. 打开 https://huggingface.co/new-space
2. Space name 随意（如 `13f-evidence`）；**SDK 选 Docker**；License 随意。
3. 把本仓库推送到这个 Space 的 git：
   ```
   git remote add hf https://huggingface.co/spaces/<你的用户名>/<space名>
   git push hf master
   ```
4. HF 会自动按 `Dockerfile` 构建（构建期会联网从 SEC 建库，约 5-15 分钟）。
5. 构建完成后，你的看板地址：
   `https://<你的用户名>-<space名>.hf.space`

## 方案 A2：Render（Docker，免费额度，可持久盘）

1. 把本仓库推到 GitHub（公开或私有均可）。
2. Render 控制台 → New → Web Service → 选择该仓库。
3. 环境选 Docker；Render 会自动读取 `render.yaml`（或手动填：
   Dockerfile 路径 `./Dockerfile`，健康检查 `/_stcore/health`）。
4. 首次部署构建约 10-20 分钟（含建库）；之后自动重建。
5. 地址：`https://<service名>.onrender.com`

## 方案 A3：Streamlit Community Cloud（快速试，但注意数据规模）

- 支持入口 `streamlit_app.py`，但免费实例无持久盘、冷启动会重建，150MB 数据库
  **不适合**长期使用。仅建议作为体验性尝试；正式对外请用 A1/A2。
- 如需使用：推送到 GitHub → share.streamlit.io → New app → 选择仓库与
  `streamlit_app.py`。

## 本地验证（推送前先做一遍）

```powershell
python -m pytest -q                 # 全量测试
python scripts/update_data.py --check   # 离线构建路径 smoke（已在本仓库验证 exit 0）
```

Docker 本地构建验证（可选）：

```bash
docker build -t thirteenf-evidence .
docker run --rm -p 8501:8501 thirteenf-evidence
```

浏览器打开 `http://localhost:8501`。

## 上线后用户会看到

- 与本地完全一致的 6 个页面：总览 / 机构 / 证券 / 活动探索 / 我的组合 / 方法论（+研究观察）。
- 总览第一屏是 **DATA STATUS**：最新报告季度、filing 日期、本地更新时间、机构覆盖、
  陈旧、修订、身份解析状态。
- 「我的组合」在公网上每次部署后从空开始（可自行添加；数据保存在容器内，重建会清空）。

## 治理与安全红线（部署时必须遵守）

- 不要上传：`.env`、`data/raw/`、`data/real_use/`、`data/last_update.*`、
  `data/resolution_cache/`（`.dockerignore` 已默认排除）。
- 不要添加任何预测/评分/推荐文案（语言政策见 `docs/product_language_policy.md`）。
- SEC 拉取必须节流（默认 0.6s/请求，已合规）。
- 若担心滥用：在托管平台开启限流/访问控制；本项目当前无认证（v0.4 范围冻结）。
- 公网部署属于新阶段：正式对外前建议外部评审确认
  `EVIDENCE_PRODUCT_STATUS=CANDIDATE_READY_FOR_REAL_USE` 与
  `REAL_WORLD_EVIDENCE_UTILITY=INSUFFICIENT_OBSERVATION` 的状态说明。

## 常见问题

- **页面报「数据库不存在」**：构建期建库失败 → 检查 `Dockerfile` 构建日志；
  本地先跑 `python scripts/update_data.py --rate-limit 0.6` 确认能成功。
- **SEC 下载慢/失败**：网络被限 → 提高 `--rate-limit` 到 1-2 秒重试。
- **端口**：容器内 `$PORT` 由平台注入；本地默认 8501。
