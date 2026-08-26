# 13F Institutional Evidence System
# v0.5.1 Final User Delivery Layer — Delivery Report

> Date: 2026-08-26 | One-click dashboard + data update + beginner guide

---

# 用户现在怎么用

**第一步：打开哪个文件夹。**
打开 `13f-intelligence` 文件夹。

**第二步：双击哪个文件。**
双击 `START_13F_DASHBOARD.bat`（或 `双击打开13F看板.bat`）。

**第三步：浏览器会出现什么。**
几秒后默认浏览器自动打开 `http://localhost:8501`，出现「13F 机构持仓情报系统」。
那个黑色小窗口不要关（它是看板后台）。

**第四步：点哪个菜单查机构。**
左侧点「机构」，选择一家机构（如 Berkshire Hathaway），看它最新季度的
NEW / ADD / REDUCE / EXIT、Top 持仓、重复动作。

**第五步：点哪个菜单查股票。**
左侧点「证券」，输入 Ticker（如 GOOGL）、CUSIP 或发行方名称；有歧义时手动选正确的。

**第六步：在哪里看大家最近 NEW/ADD/REDUCE/EXIT。**
左侧点「活动探索」，选一个排序指标（如「独立机构增持计数」），看中性事实排行。

**第七步：怎么加入自己的股票。**
左侧点「我的组合」，在「我的持仓」里输入股票并点「查找并添加」；删除时勾选后点「保存修改」。
下次打开自动载入，不需要编辑任何文件。

**第八步：怎么更新最新 SEC 数据。**
双击 `UPDATE_13F_DATA.bat`，等待几分钟；看到 `Update OK. ...` 即成功。
失败也不会破坏现有数据（看 `data\last_update.log`）。

**第九步：怎么关闭。**
直接关掉黑色窗口，或双击 `STOP_13F_DASHBOARD.bat`。

详细说明见根目录 `README_USER.md`。

---

# 当前看板数据（实际读取数据库）

```text
CURRENT_DATA_REPORT_PERIOD        = 2026-06-30
LATEST_EFFECTIVE_FILING_DATE      = 2026-08-14
LATEST_INGESTED_FILING_ACCESSION  = 0001013594-26-000915
MANAGERS_TRACKED                  = 29
CURRENT_CYCLE_MANAGER_COVERAGE    = 25 / 29
STALE_MANAGER_COUNT               = 4
AMENDMENTS_IN_LATEST_CYCLE        = 0  (all periods: 12)
LAST_LOCAL_UPDATE                 = 2026-08-26T11:11:02Z (update --check success)
SECURITY_IDENTITY_STATUS          = VERIFIED 6,028 / AMBIGUOUS 743 / CONFLICT 216 / UNRESOLVED 5,365 / NON_EQUITY 442 (13,005 total)
HOLDINGS_PROCESSED                = 600,173
POSITION_CHANGES                  = 336,175
```

报告季度（2026-06-30）≠ 实时持仓；13F 允许最长 45 天延迟，filing 日期为 2026-08-14。

---

# 技术交付说明

## Repository

- Baseline SHA: `dcfa839`（v0.5 final）
- Final SHA: 见 git log（本报告所在 commit）
- Commits: 本次交付的 coherent commits（见下）
- Git status: clean

## What Was Delivered

1. **一键启动**：`START_13F_DASHBOARD.bat` + 中文别名 `双击打开13F看板.bat`
   （定位仓库根、检查 Python/Streamlit、启动 `streamlit run app/app.py`、自动开浏览器、
   失败时显示可读错误并停留）。`STOP_13F_DASHBOARD.bat` 定向结束 8501 端口进程。
2. **一键更新**：`UPDATE_13F_DATA.bat` → `scripts/update_data.py`
   （复用现有 `ingest`（SEC 下载）→ `normalize` → `analyze`；幂等；写
   `data/last_update.json` 状态 + `data/last_update.log`；失败不清库、退出码正确）。
3. **初学者指南**：`README_USER.md`（九步 + 每页说明 + 更新 + 排查 + 关闭 + 限制）。
4. **Overview**：DATA STATUS 块（报告季度/filing 日期/最近本地更新/机构覆盖/陈旧/修订/
   身份状态/最新 accession）；「两个日期的区别」说明；「如何使用本看板」快速开始；
   更新状态与日志引用。
5. **My Portfolio UI 编辑器**：页面内添加/删除/权重/保存/重载（持久化到
   `config/portfolio.csv` 既有契约），歧义搜索必须手动选择，不静默取第一个。
6. **入门帮助**：每个核心页加入「如何使用本页」；方法论页改为初学者可读版
   （13F 是什么、NEW/ADD/REDUCE/EXIT/权重/重复活动、为什么不是推荐、限制）。
7. **可验证性**：Overview 显示最近入库 filing accession 与更新日志路径；
   用户可区分「看板软件是新的」与「SEC 数据刚刷新」。
8. **入口修复**：新增 `src/thirteenf/__main__.py`，使 README 的
   `python -m thirteenf ...` 命令真实可用。

## Tests

- 新增用户验收测试 `tests/product/test_user_delivery.py`（TASK 1-12）：
  launcher 文件与真实启动（health 200）、Overview 实际数据、机构/证券/发行方/CUSIP 搜索、
  歧义不静默、Activity Explorer 事实排序、组合 UI 编辑器（临时文件隔离，不动真实
  portfolio.csv）、更新编排路径、质量状态可见、无预测词。
- 全量 pytest 通过（含 FACT / research / resolver / semantic / v0.3 / v0.4 / v0.5 / 新交付测试）。
- Launcher 测试：`streamlit run app/app.py` 在独立端口启动并响应 health（PASS）。
- Update workflow 测试：`python scripts/update_data.py --check` 退出码 0、
  `data/last_update.json` success=true（filings=339, holdings=600173）（PASS）。
- Package build/install smoke：wheel 构建 + 安装后 import 通过。

## User Acceptance Results (TASK 1-12)

1. Launcher starts dashboard and browser page responds: PASS
2. Overview shows actual report period / filing freshness: PASS
3. Search a manager and retrieve latest changes: PASS
4. Search a verified security by ticker: PASS
5. Search by issuer name: PASS
6. Search by CUSIP: PASS
7. Ambiguous search does not silently select first result: PASS
8. Activity Explorer returns factual NEW/ADD/REDUCE/EXIT rankings: PASS
9. My Portfolio UI add/save/reload/remove (isolated temp file): PASS
10. UPDATE workflow safe smoke (orchestration path): PASS
11. Stale/amended/unresolved states visibly propagate: PASS
12. No predictive terminology or scores reappear: PASS

## Final Status

```text
FINAL_USER_DELIVERY_LAYER_STATUS   = DELIVERED
ONE_CLICK_DASHBOARD_STATUS         = PASS
ONE_CLICK_DATA_UPDATE_STATUS       = PASS
BEGINNER_USER_GUIDE_STATUS         = PASS
MY_PORTFOLIO_UI_EDIT_STATUS        = PASS
ORIGINAL_REFERENCE_FEATURE_PARITY  = PASS
EVIDENCE_PRODUCT_STATUS            = CANDIDATE_READY_FOR_REAL_USE
PREDICTIVE_RESEARCH_STOP_RULE      = TRIGGERED
REAL_WORLD_EVIDENCE_UTILITY        = INSUFFICIENT_OBSERVATION
```

## Engineering Freeze

交付完成。不再自动创建 v0.5.2 / v0.6。下一步是**用户打开看板并实际使用**；
只有真实使用暴露 correctness / update / usability / misleading-presentation 缺陷时才重开工程。

