# 13F Institutional Intelligence System

> 将 SEC Form 13F 原始披露转化为结构化、可验证、可追溯的机构持仓行为证据，并用于
> 投资组合的交叉验证。

## 当前交付状态（2026-09-10 源码候选版）

**商用状态：NOT_READY；本分支用于源码审阅，不是已放行的生产服务。**

当前是带确定性分析内核的证据研究看板，不是已验收的无人值守商业服务。
已从冻结的真实 SEC 原件独立重建两份 v3 候选库，29 个机构、343 份申报；
16 个有原文矛盾的机构季度按批准政策隔离，不改原始数字。
Gate 1 自动对账和 Gate 2 自动核验已通过；Gate 2 人工签字仍未完成，正式发布仍被阻止。
旧 schema v2 数据库未被覆盖。不能把 HTTP `ok`、自动测试或隔离批准当成商用验收。
当前 CI 改为只读离线测试，临时阻止旧流程直接发布未验证镜像；这不等于自动发布已经完成。
公开交接见 [候选源码说明与验收状态](reports/releases/source-preview-2026-09-10/README.md)。
人工 Gate 2 为 `NOT_REVIEWED`；不包含生产镜像、数据库、原始缓存或私人持仓。
本分支的公开不等于 VPS 已更新，也不等于自动更新、回滚和通知已完成。

### 已批准隔离政策的明确入口（离线，非发布）

```powershell
python -m thirteenf normalize --raw-root data/raw --db-path data/private/review-candidate.db --methodology 0.1.1 --quarantine-policy config/source_quarantine.json
```

日常更新脚本也支持显式 `--quarantine-policy config/source_quarantine.json`。
不提供政策时仍严格拒绝控制总数不一致。政策只覆盖固定16份双 checksum 原件；
新异常、新字节、缺少批准原件或需要解封的 amendment 必须重新审查，不能自动扩容。
候选建库成功不触发提交、推送、镜像发布或 VPS 更新。

## 项目是什么

- SEC EDGAR 13F-HR / 13F-HR/A 的确定性 ingestion、normalization、position change
  分析、manager taxonomy、weighted consensus、1Q/4Q/8Q trend、My Portfolio 交叉验证。
- 所有数字由确定性代码计算；原始 filing 保存 checksum 可回溯；CUSIP→ticker 映射
  全部带来源，未验证一律 `UNRESOLVED`。

## 项目不是什么

- 不是荐股系统，不产生 BUY / SELL 信号，不进行自动交易。
- 不用第三方数据库或 LLM 替代 SEC 原始数据作为事实真相源。
- 13F 不是完整投资观点：不披露空头，衍生品披露不完整，不提供真实成本、精确交易时机。

## 安装

要求 Python >= 3.11。

```powershell
git clone --branch codex/unattended-refresh-deploy https://github.com/fancy0121/13f-intelligence.git
cd 13f-intelligence
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
```

## 更新数据（从 SEC 下载原始 filing）

先在环境变量 `SEC_USER_AGENT` 中设置真实的维护名称与联系邮箱。不要提交进 Git；
`.env.example` 只是格式示例，项目不会自动加载 `.env`。占位邮箱会在联网前被拒绝。

```powershell
python -m thirteenf ingest --managers config/managers.csv
```

仅 `validation_status=VERIFIED` 或 `VERIFIED_WITH_SCOPE` 且带 CIK 的机构会进入 ingestion；REQUIRES_REVIEW
机构不会下载。下载内容保存到 `data/raw/`（gitignored），每条含 `manifest.json`
（checksum、source URL、时间戳）。

## 构建数据库与计算分析

```powershell
python -m thirteenf normalize          # raw -> SQLite (offline)
python -m thirteenf score              # 应用治理评分（默认全部 NOT_APPROVED）
python -m thirteenf analyze            # 评分变更后重算；weights + changes + consensus + trends + quality
```

一键重建：

```powershell
python -m thirteenf rebuild
```

## 启动 UI

```powershell
streamlit run app/app.py
```

目前七个页面：总览 / 机构 / 证券 / 活动探索 / 我的组合 / 方法论与限制 / 研究观察。
界面使用中英文；公司中文名未核验时明确显示“中文名待核验”，不自动编造。
活动探索是描述性事实排序，不是 Weighted Consensus 页面。
治理评分尚未批准时，共识及趋势不得作为已有生产能力宣传。

本地 UI 保存的实际持仓位于被 Git 忽略的 `data/private/portfolio.csv`；
旧 `config/portfolio.csv` 仅供首次兼容读取。公开模式的组合与研究记录仅保留在当前服务端会话内存，
不落盘，不读取全局持仓文件；不等于浏览器本地存储。CLI 的 `--portfolio` 参数可显式指定私有组合路径。
公开模式还要求真实 Gate 报告绑定的发布清单，缺失或与数据/代码校验不符即显示 `NOT_VALIDATED`。
本仓库目前没有可用于生产的发布清单；测试中的合成清单不能复制用于上线。

### Manager Scope（VERIFIED_WITH_SCOPE）

同一品牌可能对应多个 SEC filing entity（如 PERSHING SQUARE INC 与 PSCM L.P.）。
系统明确声明追踪的 filing entity，不合并平行/历史实体。详见
`docs/manager_scope.md`；Managers 页面会展示 scope 备注。

### 未解析证券优先级清单（人工审核用）

系统不做自动 CUSIP→ticker 映射。需要人工维护映射时，可生成按“持有机构数 /
最新季度总市值”排序的未解析清单（仅事实，不猜测）：

```powershell
python scripts/prioritize_unresolved.py
```

输出 `reports/unresolved_priority.md`。人工核对后，将已验证条目写入
`config/ticker_mappings.csv`（带 mapping_source / verified_at / verified_by），
再重新执行 `normalize` + `analyze`。

## 运行测试

```powershell
pytest
```

## Gate 验收

```powershell
python scripts/gate1_reconciliation.py
python scripts/gate2_review.py
```

报告输出到 `reports/`。

## 文档

- [docs/methodology.md](docs/methodology.md)
- [docs/manager_scoring.md](docs/manager_scoring.md)
- [docs/data_model.md](docs/data_model.md)
- [docs/limitations.md](docs/limitations.md)

## 状态

源码候选版可供审阅和离线测试，不宣称完整 v0.1 或商用交付。
人工 Gate 2：`NOT_REVIEWED`；Gate 3：`PENDING_REAL_WORLD_VALIDATION`。
