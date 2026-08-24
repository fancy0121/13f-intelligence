# 13F Institutional Intelligence System

> 将 SEC Form 13F 原始披露转化为结构化、可验证、可追溯的机构持仓行为证据，并用于
> 投资组合的交叉验证。

## 项目是什么

- SEC EDGAR 13F-HR / 13F-HR/A 的确定性 ingestion、normalization、position change
  分析、manager taxonomy、weighted consensus、1Q/4Q/8Q trend、My Portfolio 交叉验证。
- 所有数字由确定性代码计算；原始 filing 保存 checksum 可回溯；CUSIP→ticker 映射
  全部带来源，未验证一律 `UNRESOLVED`。

## 项目不是什么

- 不是荐股系统，不产生 BUY / SELL 信号，不进行自动交易。
- 不用第三方数据库或 LLM 替代 SEC 原始数据作为事实真相源。
- 13F 不是完整投资观点：不披露空头、衍生品、成本、精确交易时机。

## 安装

要求 Python >= 3.11。

```powershell
cd C:\Users\ASUS\Documents\挣钱项目组\13f-intelligence
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
```

## 更新数据（从 SEC 下载原始 filing）

```powershell
python -m thirteenf ingest --managers config/managers.csv
```

仅 `validation_status=VERIFIED` 且带 CIK 的机构会进入 ingestion；REQUIRES_REVIEW
机构不会下载。下载内容保存到 `data/raw/`（gitignored），每条含 `manifest.json`
（checksum、source URL、时间戳）。

## 构建数据库与计算分析

```powershell
python -m thirteenf normalize          # raw -> SQLite (offline)
python -m thirteenf analyze            # weights + position changes + consensus + trends + quality
python -m thirteenf score              # 应用治理评分（默认全部 NOT_APPROVED）
```

一键重建：

```powershell
python -m thirteenf rebuild
```

## 启动 UI

```powershell
streamlit run app/app.py
```

五个页面：总览 / 机构 / 个股 / 共识 / 我的组合（界面中文，标识符英文）。

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

v0.1 已交付（见最终执行报告）。Gate 3 真实世界验证前保持
`PENDING_REAL_WORLD_VALIDATION`。
