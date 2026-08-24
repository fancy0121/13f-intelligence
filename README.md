# 13F Institutional Intelligence System

> 将 SEC Form 13F 原始披露转化为结构化、可验证、可追溯的机构持仓行为证据，并用于
> 投资组合的交叉验证。

本项目**不是**荐股系统，**不产生** BUY / SELL 信号，**不进行**自动交易。

## 项目是什么 / 不是什么

- 是：SEC EDGAR 13F-HR / 13F-HR/A 的确定性 ingestion、normalization、change 分析、
  manager taxonomy、weighted consensus、trend、My Portfolio 交叉验证。
- 不是：根据“聪明钱”推荐股票；AI 预测；第三方数据库替代 SEC；完整投资观点。

## 安装

```powershell
cd C:\Users\ASUS\Documents\挣钱项目组\13f-intelligence
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

## 更新数据

```powershell
python -m thirteenf ingest --managers config/managers.csv
```

## 启动 UI

```powershell
streamlit run app/app.py
```

## 运行测试

```powershell
pytest
```

## 重新构建数据库

```powershell
python -m thirteenf rebuild
```

## 文档

- [docs/methodology.md](docs/methodology.md)
- [docs/manager_scoring.md](docs/manager_scoring.md)
- [docs/data_model.md](docs/data_model.md)
- [docs/limitations.md](docs/limitations.md)

## 状态

构建中。最终交付状态以 `V0_1_RELEASE_STATUS` 为准。

