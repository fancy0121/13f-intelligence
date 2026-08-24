# Manager Scope — VERIFIED_WITH_SCOPE 说明 (v0.1.1)

## 为什么需要 scope

部分品牌（product label）对应多个 SEC filing entity。系统不会把相似实体静默合并，
而是明确声明“本系统追踪哪一个具体 filing entity”。

## 当前 VERIFIED_WITH_SCOPE 清单

| Product label | Tracked entity | CIK | 不合并的平行/历史实体 |
|---|---|---|---|
| Pershing Square Capital Management | Pershing Square Capital Management, L.P. | 1336528 | PERSHING SQUARE INC (2026053, 2025-08 起独立申报) |
| Appaloosa Management | Appaloosa LP | 1656456 | APPALOOSA MANAGEMENT LP (1006438, 2016 前历史) |
| Soros Fund Management | SOROS FUND MANAGEMENT LLC | 1029160 | SOROS CAPITAL MANAGEMENT LLC (1748240, 2020 起平行申报) |
| ValueAct Capital | ValueAct Holdings, L.P. | 1418814 | ValueAct Capital Management L.P. (1351069, 2008 前历史) |
| Vanguard Group | VANGUARD GROUP INC | 102909 | Vanguard 各子实体（Advisers Inc / Fiduciary Trust 等） |

## 用户界面说明

- Managers 页面展示该机构的 tracked filing entity。
- Stocks / Consensus 仅基于 tracked entity 的数据。
- 平行实体不会被合并进 consensus；历史实体不会被当作当前持仓。

