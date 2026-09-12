# Gate 2 人工核验手册 / Human review worksheet

**状态：NOT_REVIEWED。以下数值均为程序核对材料，不是人工签字，不是投资建议。**

## 怎么核验

1. 打开每条记录的上季、本季 SEC 信息表和封面，按 CUSIP + PUT/CALL + SH/PRN 找到全部相同行；不要只核对发行人名字。
2. 查看每季全部有效组件，依照 RESTATEMENT / NEW HOLDINGS 语义还原；同一证券可能有多行，股数及金额需要按方法论汇总。
3. 独立计算两季股数与权重：该证券有效披露金额 ÷ 当季全部有效披露金额。下面的权重是比例，不是百分数；乘100才是百分数。不要把缺失端空值改成0。
4. NEW/EXIT 必须确认另一季有效信息表中确实没有该键，不能凭下面的空 provenance 就下结论。ADD/REDUCE/UNCHANGED 按股数判定，并另外核对权重方向。
5. 如有不一致，在原CSV的 reviewer_notes 记录，不填 MATCH。全部核对一致后才由真人填写 human_result=MATCH、reviewer=真实审核人、review_date=实际日期（YYYY-MM-DD）。
6. 不更改CSV的 transition_id、计算字段或版本字段。本批必须核验完整38条、5家机构；本手册不代替CSV，也不代签。

原始清单：[manual-review.csv](manual-review.csv)；SHA-256 `182cc2d7c32b42e82be9c89056b7202b61a9a9a5a15d1f645fabeb8ff16070d5`。

核验使用的是2026-09-07冻结原件；SEC链接当前返回的内容如与本地checksum不同，应报告差异，不能覆盖冻结原件。

## 1. STATE STREET CORP · 60937PAD8

- 记录：`T-a96f82017f43f18a7341`；上季 `2023-09-30` → 本季 `2023-12-31`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | NEW | NEW |
| 上季股数 / Previous shares | NULL（缺失） | NULL（缺失） |
| 本季股数 / Current shares | 24587000 | 24587000 |
| 上季权重比例 / Previous weight | NULL（缺失） | NULL（缺失） |
| 本季权重比例 / Current weight | 2.3656371555703466e-05 | 2.3656371555703466e-05 |

### 原件入口 / SEC originals

**上季 / Previous：2023-09-30**

- `0000093751-23-000703`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/infotable-CU10020230630_v1.xml)
  - 信息表 SHA-256：`a36759d2da76630fd0163db2ba635da2bdce34d12af42b5b432d3b7a8564f15d`；封面 SHA-256：`d756b96085dff1609d00d5eedb0b86a50022e2b8e5f674fa1b254a908e9c1733`。
- 匹配原始行定位：无匹配行；必须人工核验该季全部有效组件以确认缺席。

**本季 / Current：2023-12-31**

- `0000093751-24-000484`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/XML_Infotable_V1.xml)
  - 信息表 SHA-256：`8b95818717c77a4497931c5cf1c6e8f6c742c46bd42e41db7c16e0e6b3385554`；封面 SHA-256：`c53c18fa4559c7f62a33bd2c79feae545104faae347c186caf26a49e002e1de7`。
- 匹配原始行定位：`0000093751-24-000484` 第 `4428` 个 infoTable 元素

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 2. VANGUARD GROUP INC · 00288U106

- 记录：`T-8982bab138ddd8136f7d`；上季 `2023-09-30` → 本季 `2023-12-31`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | NEW | NEW |
| 上季股数 / Previous shares | NULL（缺失） | NULL（缺失） |
| 本季股数 / Current shares | 13112 | 13112 |
| 上季权重比例 / Previous weight | NULL（缺失） | NULL（缺失） |
| 本季权重比例 / Current weight | 1.635599346400789e-08 | 1.635599346400789e-08 |

### 原件入口 / SEC originals

**上季 / Previous：2023-09-30**

- `0001104659-23-126756`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/102909/000110465923126756/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/102909/000110465923126756/infotable.xml)
  - 信息表 SHA-256：`a9d1d17087667a949b167500a3992a4763feb7332ce081800e8c178be10fa4f8`；封面 SHA-256：`94eb46f283eeea11440be81f4c40c15ec26186ad3b1df7c0dd587bd7530700f2`。
- 匹配原始行定位：无匹配行；必须人工核验该季全部有效组件以确认缺席。

**本季 / Current：2023-12-31**

- `0001104659-24-032991`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/102909/000110465924032991/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/102909/000110465924032991/infotable.xml)
  - 信息表 SHA-256：`caff8f8e3ce25560cf3a92e99ee0fce907dc575c9ff93f4831bdcebb6c04ffa8`；封面 SHA-256：`95e538839fb382732a896b08d083865e723aa4bd76344e889210557e4754bd2c`。
- 匹配原始行定位：`0001104659-24-032991` 第 `91` 个 infoTable 元素

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 3. MAVERICK CAPITAL LTD · 00402L107

- 记录：`T-104faf7e9938f2f9ce20`；上季 `2023-09-30` → 本季 `2023-12-31`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | NEW | NEW |
| 上季股数 / Previous shares | NULL（缺失） | NULL（缺失） |
| 本季股数 / Current shares | 53359 | 53359 |
| 上季权重比例 / Previous weight | NULL（缺失） | NULL（缺失） |
| 本季权重比例 / Current weight | 0.0007072007246445168 | 0.0007072007246445168 |

### 原件入口 / SEC originals

**上季 / Previous：2023-09-30**

- `0000947871-23-001078`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/934639/000094787123001078/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/934639/000094787123001078/infotable.xml)
  - 信息表 SHA-256：`035ca589465ff64f146992bb7d60582d249c1f210819d8f511aacdc2ca156b1d`；封面 SHA-256：`0ff3ca5731089afaee49bd845ed6091eb0f7ad726c019160ae1ed802b7df9e92`。
- 匹配原始行定位：无匹配行；必须人工核验该季全部有效组件以确认缺席。

**本季 / Current：2023-12-31**

- `0000947871-24-000140`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/934639/000094787124000140/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/934639/000094787124000140/infotable.xml)
  - 信息表 SHA-256：`d1c046f85affd709fcc947c8120af7551e9959880fba1eff606ecbfd5d7e69dc`；封面 SHA-256：`c1cd0b02ddd01a4f62d43c3f2a83ce693873d02db327f11d6ae755a7f52e7c1d`。
- 匹配原始行定位：`0000947871-24-000140` 第 `3` 个 infoTable 元素

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 4. SOROS FUND MANAGEMENT LLC · 02156B103

- 记录：`T-946bc1943f935f49d113`；上季 `2023-09-30` → 本季 `2023-12-31`。
- PUT/CALL：`PUT`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | NEW | NEW |
| 上季股数 / Previous shares | NULL（缺失） | NULL（缺失） |
| 本季股数 / Current shares | 61700 | 61700 |
| 上季权重比例 / Previous weight | NULL（缺失） | NULL（缺失） |
| 本季权重比例 / Current weight | 0.0003805429157792732 | 0.0003805429157792732 |

### 原件入口 / SEC originals

**上季 / Previous：2023-09-30**

- `0000902664-23-005529`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/1029160/000090266423005529/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/1029160/000090266423005529/infotable.xml)
  - 信息表 SHA-256：`a58bebdebf82b9bb92494a689ff0855defa262b62c56449b98d37abd91c339d7`；封面 SHA-256：`45b11ca633353ae12621177ae58c637047ec01419eaca38039222ed0f3b947ad`。
- 匹配原始行定位：无匹配行；必须人工核验该季全部有效组件以确认缺席。

**本季 / Current：2023-12-31**

- `0000902664-24-001751`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/1029160/000090266424001751/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/1029160/000090266424001751/infotable.xml)
  - 信息表 SHA-256：`07d931b10590e03f8bbb8ae69cadeae6454b6d62eb93b2c3e4b884849ac79f07`；封面 SHA-256：`41bb5226f45218bf1c48ae0b00ec15bf031f8228bad1d3b690dd8e1b45804ff0`。
- 匹配原始行定位：`0000902664-24-001751` 第 `9` 个 infoTable 元素

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 5. RENAISSANCE TECHNOLOGIES LLC · 90137F202

- 记录：`T-eca69c8100ca268c30ed`；上季 `2023-09-30` → 本季 `2023-12-31`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | NEW | NEW |
| 上季股数 / Previous shares | NULL（缺失） | NULL（缺失） |
| 本季股数 / Current shares | 67000 | 67000 |
| 上季权重比例 / Previous weight | NULL（缺失） | NULL（缺失） |
| 本季权重比例 / Current weight | 1.8573900846078332e-07 | 1.8573900846078332e-07 |

### 原件入口 / SEC originals

**上季 / Previous：2023-09-30**

- `0001037389-23-000124`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/1037389/000103738923000124/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/1037389/000103738923000124/renaissance13Fq32023_holding.xml)
  - 信息表 SHA-256：`2db75ee8adba85526bb2addb109acdb76e7b2ed2c46d6134209bf035b4a97eb6`；封面 SHA-256：`fe79a022ac1d8736f8813d844cb053882d72174b9c2fc3d4f0b01aeb8e448861`。
- 匹配原始行定位：无匹配行；必须人工核验该季全部有效组件以确认缺席。

**本季 / Current：2023-12-31**

- `0001037389-24-000071`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/1037389/000103738924000071/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/1037389/000103738924000071/renaissance13Fq42023_holding.xml)
  - 信息表 SHA-256：`e16da13ca9c353d74473441d230f914ccaebd4c4d4d6dae19eb2833cdb90d958`；封面 SHA-256：`ffa96a599c3a5947529a7419cab88110b26e94c1fb766704e2514caa648dcc32`。
- 匹配原始行定位：`0001037389-24-000071` 第 `7` 个 infoTable 元素

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 6. STATE STREET CORP · 55405YAB6

- 记录：`T-45546c5605d6f045b985`；上季 `2023-09-30` → 本季 `2023-12-31`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | NEW | NEW |
| 上季股数 / Previous shares | NULL（缺失） | NULL（缺失） |
| 本季股数 / Current shares | 10180000 | 10180000 |
| 上季权重比例 / Previous weight | NULL（缺失） | NULL（缺失） |
| 本季权重比例 / Current weight | 6.105152978439658e-06 | 6.105152978439658e-06 |

### 原件入口 / SEC originals

**上季 / Previous：2023-09-30**

- `0000093751-23-000703`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/infotable-CU10020230630_v1.xml)
  - 信息表 SHA-256：`a36759d2da76630fd0163db2ba635da2bdce34d12af42b5b432d3b7a8564f15d`；封面 SHA-256：`d756b96085dff1609d00d5eedb0b86a50022e2b8e5f674fa1b254a908e9c1733`。
- 匹配原始行定位：无匹配行；必须人工核验该季全部有效组件以确认缺席。

**本季 / Current：2023-12-31**

- `0000093751-24-000484`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/XML_Infotable_V1.xml)
  - 信息表 SHA-256：`8b95818717c77a4497931c5cf1c6e8f6c742c46bd42e41db7c16e0e6b3385554`；封面 SHA-256：`c53c18fa4559c7f62a33bd2c79feae545104faae347c186caf26a49e002e1de7`。
- 匹配原始行定位：`0000093751-24-000484` 第 `4430` 个 infoTable 元素

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 7. STATE STREET CORP · 81807M304

- 记录：`T-37893047caea5086544a`；上季 `2023-09-30` → 本季 `2023-12-31`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | NEW | NEW |
| 上季股数 / Previous shares | NULL（缺失） | NULL（缺失） |
| 本季股数 / Current shares | 19377 | 19377 |
| 上季权重比例 / Previous weight | NULL（缺失） | NULL（缺失） |
| 本季权重比例 / Current weight | 1.9415836912328938e-08 | 1.9415836912328938e-08 |

### 原件入口 / SEC originals

**上季 / Previous：2023-09-30**

- `0000093751-23-000703`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/infotable-CU10020230630_v1.xml)
  - 信息表 SHA-256：`a36759d2da76630fd0163db2ba635da2bdce34d12af42b5b432d3b7a8564f15d`；封面 SHA-256：`d756b96085dff1609d00d5eedb0b86a50022e2b8e5f674fa1b254a908e9c1733`。
- 匹配原始行定位：无匹配行；必须人工核验该季全部有效组件以确认缺席。

**本季 / Current：2023-12-31**

- `0000093751-24-000484`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/XML_Infotable_V1.xml)
  - 信息表 SHA-256：`8b95818717c77a4497931c5cf1c6e8f6c742c46bd42e41db7c16e0e6b3385554`；封面 SHA-256：`c53c18fa4559c7f62a33bd2c79feae545104faae347c186caf26a49e002e1de7`。
- 匹配原始行定位：`0000093751-24-000484` 第 `4` 个 infoTable 元素

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 8. STATE STREET CORP · 00510M104

- 记录：`T-8f752101126df7ad5d20`；上季 `2023-09-30` → 本季 `2023-12-31`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | NEW | NEW |
| 上季股数 / Previous shares | NULL（缺失） | NULL（缺失） |
| 本季股数 / Current shares | 28566 | 28566 |
| 上季权重比例 / Previous weight | NULL（缺失） | NULL（缺失） |
| 本季权重比例 / Current weight | 5.321662161244794e-08 | 5.321662161244794e-08 |

### 原件入口 / SEC originals

**上季 / Previous：2023-09-30**

- `0000093751-23-000703`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/infotable-CU10020230630_v1.xml)
  - 信息表 SHA-256：`a36759d2da76630fd0163db2ba635da2bdce34d12af42b5b432d3b7a8564f15d`；封面 SHA-256：`d756b96085dff1609d00d5eedb0b86a50022e2b8e5f674fa1b254a908e9c1733`。
- 匹配原始行定位：无匹配行；必须人工核验该季全部有效组件以确认缺席。

**本季 / Current：2023-12-31**

- `0000093751-24-000484`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/XML_Infotable_V1.xml)
  - 信息表 SHA-256：`8b95818717c77a4497931c5cf1c6e8f6c742c46bd42e41db7c16e0e6b3385554`；封面 SHA-256：`c53c18fa4559c7f62a33bd2c79feae545104faae347c186caf26a49e002e1de7`。
- 匹配原始行定位：`0000093751-24-000484` 第 `58` 个 infoTable 元素

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 9. STATE STREET CORP · 0076CA104

- 记录：`T-7cb26b5a3d41116cb582`；上季 `2023-09-30` → 本季 `2023-12-31`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | NEW | NEW |
| 上季股数 / Previous shares | NULL（缺失） | NULL（缺失） |
| 本季股数 / Current shares | 13395 | 13395 |
| 上季权重比例 / Previous weight | NULL（缺失） | NULL（缺失） |
| 本季权重比例 / Current weight | 3.7528594257352486e-08 | 3.7528594257352486e-08 |

### 原件入口 / SEC originals

**上季 / Previous：2023-09-30**

- `0000093751-23-000703`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/infotable-CU10020230630_v1.xml)
  - 信息表 SHA-256：`a36759d2da76630fd0163db2ba635da2bdce34d12af42b5b432d3b7a8564f15d`；封面 SHA-256：`d756b96085dff1609d00d5eedb0b86a50022e2b8e5f674fa1b254a908e9c1733`。
- 匹配原始行定位：无匹配行；必须人工核验该季全部有效组件以确认缺席。

**本季 / Current：2023-12-31**

- `0000093751-24-000484`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/XML_Infotable_V1.xml)
  - 信息表 SHA-256：`8b95818717c77a4497931c5cf1c6e8f6c742c46bd42e41db7c16e0e6b3385554`；封面 SHA-256：`c53c18fa4559c7f62a33bd2c79feae545104faae347c186caf26a49e002e1de7`。
- 匹配原始行定位：`0000093751-24-000484` 第 `85` 个 infoTable 元素

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 10. STATE STREET CORP · 68243Q106

- 记录：`T-cb8ad3e4f9a5d067a924`；上季 `2023-09-30` → 本季 `2023-12-31`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | ADD | ADD |
| 上季股数 / Previous shares | 539171 | 539171 |
| 本季股数 / Current shares | 577808 | 577808 |
| 上季权重比例 / Previous weight | 2.092753956365003e-06 | 2.092753956365003e-06 |
| 本季权重比例 / Current weight | 3.0297062024803247e-06 | 3.0297062024803247e-06 |

### 原件入口 / SEC originals

**上季 / Previous：2023-09-30**

- `0000093751-23-000703`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/infotable-CU10020230630_v1.xml)
  - 信息表 SHA-256：`a36759d2da76630fd0163db2ba635da2bdce34d12af42b5b432d3b7a8564f15d`；封面 SHA-256：`d756b96085dff1609d00d5eedb0b86a50022e2b8e5f674fa1b254a908e9c1733`。
- 匹配原始行定位：`0000093751-23-000703` 第 `1` 个 infoTable 元素

**本季 / Current：2023-12-31**

- `0000093751-24-000484`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/XML_Infotable_V1.xml)
  - 信息表 SHA-256：`8b95818717c77a4497931c5cf1c6e8f6c742c46bd42e41db7c16e0e6b3385554`；封面 SHA-256：`c53c18fa4559c7f62a33bd2c79feae545104faae347c186caf26a49e002e1de7`。
- 匹配原始行定位：`0000093751-24-000484` 第 `1` 个 infoTable 元素

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 11. STATE STREET CORP · 88025U109

- 记录：`T-4b8e1e92b973ded2521b`；上季 `2023-09-30` → 本季 `2023-12-31`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | ADD | ADD |
| 上季股数 / Previous shares | 1460637 | 1460637 |
| 本季股数 / Current shares | 1559228 | 1559228 |
| 上季权重比例 / Previous weight | 3.3408721437974684e-05 | 3.3408721437974684e-05 |
| 本季权重比例 / Current weight | 4.2440994585446736e-05 | 4.2440994585446736e-05 |

### 原件入口 / SEC originals

**上季 / Previous：2023-09-30**

- `0000093751-23-000703`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/infotable-CU10020230630_v1.xml)
  - 信息表 SHA-256：`a36759d2da76630fd0163db2ba635da2bdce34d12af42b5b432d3b7a8564f15d`；封面 SHA-256：`d756b96085dff1609d00d5eedb0b86a50022e2b8e5f674fa1b254a908e9c1733`。
- 匹配原始行定位：`0000093751-23-000703` 第 `2` 个 infoTable 元素

**本季 / Current：2023-12-31**

- `0000093751-24-000484`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/XML_Infotable_V1.xml)
  - 信息表 SHA-256：`8b95818717c77a4497931c5cf1c6e8f6c742c46bd42e41db7c16e0e6b3385554`；封面 SHA-256：`c53c18fa4559c7f62a33bd2c79feae545104faae347c186caf26a49e002e1de7`。
- 匹配原始行定位：`0000093751-24-000484` 第 `2` 个 infoTable 元素

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 12. STATE STREET CORP · 68247Q102

- 记录：`T-4e40b92a59a31a236e6f`；上季 `2023-09-30` → 本季 `2023-12-31`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | ADD | ADD |
| 上季股数 / Previous shares | 94420 | 94420 |
| 本季股数 / Current shares | 97970 | 97970 |
| 上季权重比例 / Previous weight | 1.3612282407514956e-07 | 1.3612282407514956e-07 |
| 本季权重比例 / Current weight | 7.38625773100383e-08 | 7.38625773100383e-08 |

### 原件入口 / SEC originals

**上季 / Previous：2023-09-30**

- `0000093751-23-000703`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/infotable-CU10020230630_v1.xml)
  - 信息表 SHA-256：`a36759d2da76630fd0163db2ba635da2bdce34d12af42b5b432d3b7a8564f15d`；封面 SHA-256：`d756b96085dff1609d00d5eedb0b86a50022e2b8e5f674fa1b254a908e9c1733`。
- 匹配原始行定位：`0000093751-23-000703` 第 `3` 个 infoTable 元素

**本季 / Current：2023-12-31**

- `0000093751-24-000484`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/XML_Infotable_V1.xml)
  - 信息表 SHA-256：`8b95818717c77a4497931c5cf1c6e8f6c742c46bd42e41db7c16e0e6b3385554`；封面 SHA-256：`c53c18fa4559c7f62a33bd2c79feae545104faae347c186caf26a49e002e1de7`。
- 匹配原始行定位：`0000093751-24-000484` 第 `3` 个 infoTable 元素

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 13. STATE STREET CORP · 336901103

- 记录：`T-5ae46f94459d88b5fa1a`；上季 `2023-09-30` → 本季 `2023-12-31`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | ADD | ADD |
| 上季股数 / Previous shares | 499621 | 499621 |
| 本季股数 / Current shares | 540203 | 540203 |
| 上季权重比例 / Previous weight | 1.1660393826975526e-05 | 1.1660393826975526e-05 |
| 本季权重比例 / Current weight | 1.4438527754097092e-05 | 1.4438527754097092e-05 |

### 原件入口 / SEC originals

**上季 / Previous：2023-09-30**

- `0000093751-23-000703`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/infotable-CU10020230630_v1.xml)
  - 信息表 SHA-256：`a36759d2da76630fd0163db2ba635da2bdce34d12af42b5b432d3b7a8564f15d`；封面 SHA-256：`d756b96085dff1609d00d5eedb0b86a50022e2b8e5f674fa1b254a908e9c1733`。
- 匹配原始行定位：`0000093751-23-000703` 第 `5` 个 infoTable 元素

**本季 / Current：2023-12-31**

- `0000093751-24-000484`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/XML_Infotable_V1.xml)
  - 信息表 SHA-256：`8b95818717c77a4497931c5cf1c6e8f6c742c46bd42e41db7c16e0e6b3385554`；封面 SHA-256：`c53c18fa4559c7f62a33bd2c79feae545104faae347c186caf26a49e002e1de7`。
- 匹配原始行定位：`0000093751-24-000484` 第 `5` 个 infoTable 元素

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 14. STATE STREET CORP · 88554D205

- 记录：`T-3e1bc8a8cd3de5f5a636`；上季 `2023-09-30` → 本季 `2023-12-31`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | ADD | ADD |
| 上季股数 / Previous shares | 5836638 | 5836638 |
| 本季股数 / Current shares | 6965400 | 6965400 |
| 上季权重比例 / Previous weight | 1.5890511003223977e-05 | 1.5890511003223977e-05 |
| 本季权重比例 / Current weight | 2.1513843656211977e-05 | 2.1513843656211977e-05 |

### 原件入口 / SEC originals

**上季 / Previous：2023-09-30**

- `0000093751-23-000703`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/infotable-CU10020230630_v1.xml)
  - 信息表 SHA-256：`a36759d2da76630fd0163db2ba635da2bdce34d12af42b5b432d3b7a8564f15d`；封面 SHA-256：`d756b96085dff1609d00d5eedb0b86a50022e2b8e5f674fa1b254a908e9c1733`。
- 匹配原始行定位：`0000093751-23-000703` 第 `12` 个 infoTable 元素

**本季 / Current：2023-12-31**

- `0000093751-24-000484`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/XML_Infotable_V1.xml)
  - 信息表 SHA-256：`8b95818717c77a4497931c5cf1c6e8f6c742c46bd42e41db7c16e0e6b3385554`；封面 SHA-256：`c53c18fa4559c7f62a33bd2c79feae545104faae347c186caf26a49e002e1de7`。
- 匹配原始行定位：`0000093751-24-000484` 第 `12` 个 infoTable 元素

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 15. STATE STREET CORP · 90137F202

- 记录：`T-4c636fcf38414eeadf9c`；上季 `2023-09-30` → 本季 `2023-12-31`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | REDUCE | REDUCE |
| 上季股数 / Previous shares | 52374 | 52374 |
| 本季股数 / Current shares | 52134 | 52134 |
| 上季权重比例 / Previous weight | 2.839598008779302e-08 | 2.839598008779302e-08 |
| 本季权重比例 / Current weight | 4.7215354086724204e-09 | 4.7215354086724204e-09 |

### 原件入口 / SEC originals

**上季 / Previous：2023-09-30**

- `0000093751-23-000703`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/infotable-CU10020230630_v1.xml)
  - 信息表 SHA-256：`a36759d2da76630fd0163db2ba635da2bdce34d12af42b5b432d3b7a8564f15d`；封面 SHA-256：`d756b96085dff1609d00d5eedb0b86a50022e2b8e5f674fa1b254a908e9c1733`。
- 匹配原始行定位：`0000093751-23-000703` 第 `7` 个 infoTable 元素

**本季 / Current：2023-12-31**

- `0000093751-24-000484`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/XML_Infotable_V1.xml)
  - 信息表 SHA-256：`8b95818717c77a4497931c5cf1c6e8f6c742c46bd42e41db7c16e0e6b3385554`；封面 SHA-256：`c53c18fa4559c7f62a33bd2c79feae545104faae347c186caf26a49e002e1de7`。
- 匹配原始行定位：`0000093751-24-000484` 第 `7` 个 infoTable 元素

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 16. STATE STREET CORP · 90138Q108

- 记录：`T-9f1630e9cbe51fa9eb21`；上季 `2023-09-30` → 本季 `2023-12-31`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | REDUCE | REDUCE |
| 上季股数 / Previous shares | 6613987 | 6613987 |
| 本季股数 / Current shares | 5736198 | 5736198 |
| 上季权重比例 / Previous weight | 3.5856058904886283e-06 | 3.5856058904886283e-06 |
| 本季权重比例 / Current weight | 2.5487715882914834e-06 | 2.5487715882914834e-06 |

### 原件入口 / SEC originals

**上季 / Previous：2023-09-30**

- `0000093751-23-000703`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/infotable-CU10020230630_v1.xml)
  - 信息表 SHA-256：`a36759d2da76630fd0163db2ba635da2bdce34d12af42b5b432d3b7a8564f15d`；封面 SHA-256：`d756b96085dff1609d00d5eedb0b86a50022e2b8e5f674fa1b254a908e9c1733`。
- 匹配原始行定位：`0000093751-23-000703` 第 `8` 个 infoTable 元素

**本季 / Current：2023-12-31**

- `0000093751-24-000484`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/XML_Infotable_V1.xml)
  - 信息表 SHA-256：`8b95818717c77a4497931c5cf1c6e8f6c742c46bd42e41db7c16e0e6b3385554`；封面 SHA-256：`c53c18fa4559c7f62a33bd2c79feae545104faae347c186caf26a49e002e1de7`。
- 匹配原始行定位：`0000093751-24-000484` 第 `8` 个 infoTable 元素

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 17. STATE STREET CORP · 901384107

- 记录：`T-b8bfa7905f7d165a7fe0`；上季 `2023-09-30` → 本季 `2023-12-31`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | REDUCE | REDUCE |
| 上季股数 / Previous shares | 1069125 | 1069125 |
| 本季股数 / Current shares | 977590 | 977590 |
| 上季权重比例 / Previous weight | 2.3238503577070926e-06 | 2.3238503577070926e-06 |
| 本季权重比例 / Current weight | 2.0304056608880152e-06 | 2.0304056608880152e-06 |

### 原件入口 / SEC originals

**上季 / Previous：2023-09-30**

- `0000093751-23-000703`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/infotable-CU10020230630_v1.xml)
  - 信息表 SHA-256：`a36759d2da76630fd0163db2ba635da2bdce34d12af42b5b432d3b7a8564f15d`；封面 SHA-256：`d756b96085dff1609d00d5eedb0b86a50022e2b8e5f674fa1b254a908e9c1733`。
- 匹配原始行定位：`0000093751-23-000703` 第 `9` 个 infoTable 元素

**本季 / Current：2023-12-31**

- `0000093751-24-000484`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/XML_Infotable_V1.xml)
  - 信息表 SHA-256：`8b95818717c77a4497931c5cf1c6e8f6c742c46bd42e41db7c16e0e6b3385554`；封面 SHA-256：`c53c18fa4559c7f62a33bd2c79feae545104faae347c186caf26a49e002e1de7`。
- 匹配原始行定位：`0000093751-24-000484` 第 `9` 个 infoTable 元素

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 18. STATE STREET CORP · 90214J101

- 记录：`T-6554e3e3dde13048cac1`；上季 `2023-09-30` → 本季 `2023-12-31`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | REDUCE | REDUCE |
| 上季股数 / Previous shares | 1732777 | 1732777 |
| 本季股数 / Current shares | 1615090 | 1615090 |
| 上季权重比例 / Previous weight | 2.373193855628098e-06 | 2.373193855628098e-06 |
| 本季权重比例 / Current weight | 9.662736275870704e-07 | 9.662736275870704e-07 |

### 原件入口 / SEC originals

**上季 / Previous：2023-09-30**

- `0000093751-23-000703`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/infotable-CU10020230630_v1.xml)
  - 信息表 SHA-256：`a36759d2da76630fd0163db2ba635da2bdce34d12af42b5b432d3b7a8564f15d`；封面 SHA-256：`d756b96085dff1609d00d5eedb0b86a50022e2b8e5f674fa1b254a908e9c1733`。
- 匹配原始行定位：`0000093751-23-000703` 第 `10` 个 infoTable 元素

**本季 / Current：2023-12-31**

- `0000093751-24-000484`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/XML_Infotable_V1.xml)
  - 信息表 SHA-256：`8b95818717c77a4497931c5cf1c6e8f6c742c46bd42e41db7c16e0e6b3385554`；封面 SHA-256：`c53c18fa4559c7f62a33bd2c79feae545104faae347c186caf26a49e002e1de7`。
- 匹配原始行定位：`0000093751-24-000484` 第 `10` 个 infoTable 元素

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 19. STATE STREET CORP · 90214JAB7

- 记录：`T-52e4d559addd4646c5ba`；上季 `2023-09-30` → 本季 `2023-12-31`。
- PUT/CALL：`NONE`；份额单位：`PRN`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | REDUCE | REDUCE |
| 上季股数 / Previous shares | 9416000 | 9416000 |
| 本季股数 / Current shares | 7416000 | 7416000 |
| 上季权重比例 / Previous weight | 3.1513521682497364e-06 | 3.1513521682497364e-06 |
| 本季权重比例 / Current weight | 1.8615875441790255e-06 | 1.8615875441790255e-06 |

### 原件入口 / SEC originals

**上季 / Previous：2023-09-30**

- `0000093751-23-000703`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/infotable-CU10020230630_v1.xml)
  - 信息表 SHA-256：`a36759d2da76630fd0163db2ba635da2bdce34d12af42b5b432d3b7a8564f15d`；封面 SHA-256：`d756b96085dff1609d00d5eedb0b86a50022e2b8e5f674fa1b254a908e9c1733`。
- 匹配原始行定位：`0000093751-23-000703` 第 `11` 个 infoTable 元素

**本季 / Current：2023-12-31**

- `0000093751-24-000484`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/XML_Infotable_V1.xml)
  - 信息表 SHA-256：`8b95818717c77a4497931c5cf1c6e8f6c742c46bd42e41db7c16e0e6b3385554`；封面 SHA-256：`c53c18fa4559c7f62a33bd2c79feae545104faae347c186caf26a49e002e1de7`。
- 匹配原始行定位：`0000093751-24-000484` 第 `11` 个 infoTable 元素

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 20. STATE STREET CORP · 81807M205

- 记录：`T-3cbb189480debdbe46db`；上季 `2023-09-30` → 本季 `2023-12-31`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | EXIT | EXIT |
| 上季股数 / Previous shares | 89826 | 89826 |
| 本季股数 / Current shares | NULL（缺失） | NULL（缺失） |
| 上季权重比例 / Previous weight | 3.8799873282365685e-08 | 3.8799873282365685e-08 |
| 本季权重比例 / Current weight | NULL（缺失） | NULL（缺失） |

### 原件入口 / SEC originals

**上季 / Previous：2023-09-30**

- `0000093751-23-000703`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/infotable-CU10020230630_v1.xml)
  - 信息表 SHA-256：`a36759d2da76630fd0163db2ba635da2bdce34d12af42b5b432d3b7a8564f15d`；封面 SHA-256：`d756b96085dff1609d00d5eedb0b86a50022e2b8e5f674fa1b254a908e9c1733`。
- 匹配原始行定位：`0000093751-23-000703` 第 `4` 个 infoTable 元素

**本季 / Current：2023-12-31**

- `0000093751-24-000484`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/XML_Infotable_V1.xml)
  - 信息表 SHA-256：`8b95818717c77a4497931c5cf1c6e8f6c742c46bd42e41db7c16e0e6b3385554`；封面 SHA-256：`c53c18fa4559c7f62a33bd2c79feae545104faae347c186caf26a49e002e1de7`。
- 匹配原始行定位：无匹配行；必须人工核验该季全部有效组件以确认缺席。

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 21. STATE STREET CORP · 00152K101

- 记录：`T-5c653228f2c3d90ce1d7`；上季 `2023-09-30` → 本季 `2023-12-31`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | EXIT | EXIT |
| 上季股数 / Previous shares | 12356 | 12356 |
| 本季股数 / Current shares | NULL（缺失） | NULL（缺失） |
| 上季权重比例 / Previous weight | 2.9798284937181406e-09 | 2.9798284937181406e-09 |
| 本季权重比例 / Current weight | NULL（缺失） | NULL（缺失） |

### 原件入口 / SEC originals

**上季 / Previous：2023-09-30**

- `0000093751-23-000703`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/infotable-CU10020230630_v1.xml)
  - 信息表 SHA-256：`a36759d2da76630fd0163db2ba635da2bdce34d12af42b5b432d3b7a8564f15d`；封面 SHA-256：`d756b96085dff1609d00d5eedb0b86a50022e2b8e5f674fa1b254a908e9c1733`。
- 匹配原始行定位：`0000093751-23-000703` 第 `21` 个 infoTable 元素

**本季 / Current：2023-12-31**

- `0000093751-24-000484`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/XML_Infotable_V1.xml)
  - 信息表 SHA-256：`8b95818717c77a4497931c5cf1c6e8f6c742c46bd42e41db7c16e0e6b3385554`；封面 SHA-256：`c53c18fa4559c7f62a33bd2c79feae545104faae347c186caf26a49e002e1de7`。
- 匹配原始行定位：无匹配行；必须人工核验该季全部有效组件以确认缺席。

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 22. STATE STREET CORP · G0543H109

- 记录：`T-ebec002624b6979bc493`；上季 `2023-09-30` → 本季 `2023-12-31`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | EXIT | EXIT |
| 上季股数 / Previous shares | 19900 | 19900 |
| 本季股数 / Current shares | NULL（缺失） | NULL（缺失） |
| 上季权重比例 / Previous weight | 1.1883992970955584e-07 | 1.1883992970955584e-07 |
| 本季权重比例 / Current weight | NULL（缺失） | NULL（缺失） |

### 原件入口 / SEC originals

**上季 / Previous：2023-09-30**

- `0000093751-23-000703`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/infotable-CU10020230630_v1.xml)
  - 信息表 SHA-256：`a36759d2da76630fd0163db2ba635da2bdce34d12af42b5b432d3b7a8564f15d`；封面 SHA-256：`d756b96085dff1609d00d5eedb0b86a50022e2b8e5f674fa1b254a908e9c1733`。
- 匹配原始行定位：`0000093751-23-000703` 第 `22` 个 infoTable 元素

**本季 / Current：2023-12-31**

- `0000093751-24-000484`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/XML_Infotable_V1.xml)
  - 信息表 SHA-256：`8b95818717c77a4497931c5cf1c6e8f6c742c46bd42e41db7c16e0e6b3385554`；封面 SHA-256：`c53c18fa4559c7f62a33bd2c79feae545104faae347c186caf26a49e002e1de7`。
- 匹配原始行定位：无匹配行；必须人工核验该季全部有效组件以确认缺席。

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 23. STATE STREET CORP · 000380204

- 记录：`T-2f562490d3893562e1bf`；上季 `2023-09-30` → 本季 `2023-12-31`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | EXIT | EXIT |
| 上季股数 / Previous shares | 387600 | 387600 |
| 本季股数 / Current shares | NULL（缺失） | NULL（缺失） |
| 上季权重比例 / Previous weight | 4.863645681402563e-06 | 4.863645681402563e-06 |
| 本季权重比例 / Current weight | NULL（缺失） | NULL（缺失） |

### 原件入口 / SEC originals

**上季 / Previous：2023-09-30**

- `0000093751-23-000703`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/infotable-CU10020230630_v1.xml)
  - 信息表 SHA-256：`a36759d2da76630fd0163db2ba635da2bdce34d12af42b5b432d3b7a8564f15d`；封面 SHA-256：`d756b96085dff1609d00d5eedb0b86a50022e2b8e5f674fa1b254a908e9c1733`。
- 匹配原始行定位：`0000093751-23-000703` 第 `30` 个 infoTable 元素

**本季 / Current：2023-12-31**

- `0000093751-24-000484`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/XML_Infotable_V1.xml)
  - 信息表 SHA-256：`8b95818717c77a4497931c5cf1c6e8f6c742c46bd42e41db7c16e0e6b3385554`；封面 SHA-256：`c53c18fa4559c7f62a33bd2c79feae545104faae347c186caf26a49e002e1de7`。
- 匹配原始行定位：无匹配行；必须人工核验该季全部有效组件以确认缺席。

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 24. STATE STREET CORP · 00444P108

- 记录：`T-da106119bb7890239ef8`；上季 `2023-09-30` → 本季 `2023-12-31`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | EXIT | EXIT |
| 上季股数 / Previous shares | 53035 | 53035 |
| 本季股数 / Current shares | NULL（缺失） | NULL（缺失） |
| 上季权重比例 / Previous weight | 2.4278892896528193e-08 | 2.4278892896528193e-08 |
| 本季权重比例 / Current weight | NULL（缺失） | NULL（缺失） |

### 原件入口 / SEC originals

**上季 / Previous：2023-09-30**

- `0000093751-23-000703`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/infotable-CU10020230630_v1.xml)
  - 信息表 SHA-256：`a36759d2da76630fd0163db2ba635da2bdce34d12af42b5b432d3b7a8564f15d`；封面 SHA-256：`d756b96085dff1609d00d5eedb0b86a50022e2b8e5f674fa1b254a908e9c1733`。
- 匹配原始行定位：`0000093751-23-000703` 第 `49` 个 infoTable 元素

**本季 / Current：2023-12-31**

- `0000093751-24-000484`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/XML_Infotable_V1.xml)
  - 信息表 SHA-256：`8b95818717c77a4497931c5cf1c6e8f6c742c46bd42e41db7c16e0e6b3385554`；封面 SHA-256：`c53c18fa4559c7f62a33bd2c79feae545104faae347c186caf26a49e002e1de7`。
- 匹配原始行定位：无匹配行；必须人工核验该季全部有效组件以确认缺席。

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 25. STATE STREET CORP · 320551104

- 记录：`T-280880cc4d8cc4e22b47`；上季 `2023-09-30` → 本季 `2023-12-31`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | UNCHANGED | UNCHANGED |
| 上季股数 / Previous shares | 67187 | 67187 |
| 本季股数 / Current shares | 67187 | 67187 |
| 上季权重比例 / Previous weight | 1.3560659401790142e-07 | 1.3560659401790142e-07 |
| 本季权重比例 / Current weight | 1.5294282334664804e-07 | 1.5294282334664804e-07 |

### 原件入口 / SEC originals

**上季 / Previous：2023-09-30**

- `0000093751-23-000703`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/infotable-CU10020230630_v1.xml)
  - 信息表 SHA-256：`a36759d2da76630fd0163db2ba635da2bdce34d12af42b5b432d3b7a8564f15d`；封面 SHA-256：`d756b96085dff1609d00d5eedb0b86a50022e2b8e5f674fa1b254a908e9c1733`。
- 匹配原始行定位：`0000093751-23-000703` 第 `6` 个 infoTable 元素

**本季 / Current：2023-12-31**

- `0000093751-24-000484`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/XML_Infotable_V1.xml)
  - 信息表 SHA-256：`8b95818717c77a4497931c5cf1c6e8f6c742c46bd42e41db7c16e0e6b3385554`；封面 SHA-256：`c53c18fa4559c7f62a33bd2c79feae545104faae347c186caf26a49e002e1de7`。
- 匹配原始行定位：`0000093751-24-000484` 第 `6` 个 infoTable 元素

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 26. STATE STREET CORP · 00430H201

- 记录：`T-55627ba75cb3338b6e82`；上季 `2023-09-30` → 本季 `2023-12-31`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | UNCHANGED | UNCHANGED |
| 上季股数 / Previous shares | 23535 | 23535 |
| 本季股数 / Current shares | 23535 | 23535 |
| 上季权重比例 / Previous weight | 7.50368944437851e-08 | 7.50368944437851e-08 |
| 本季权重比例 / Current weight | 4.487428579353987e-08 | 4.487428579353987e-08 |

### 原件入口 / SEC originals

**上季 / Previous：2023-09-30**

- `0000093751-23-000703`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/infotable-CU10020230630_v1.xml)
  - 信息表 SHA-256：`a36759d2da76630fd0163db2ba635da2bdce34d12af42b5b432d3b7a8564f15d`；封面 SHA-256：`d756b96085dff1609d00d5eedb0b86a50022e2b8e5f674fa1b254a908e9c1733`。
- 匹配原始行定位：`0000093751-23-000703` 第 `42` 个 infoTable 元素

**本季 / Current：2023-12-31**

- `0000093751-24-000484`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/XML_Infotable_V1.xml)
  - 信息表 SHA-256：`8b95818717c77a4497931c5cf1c6e8f6c742c46bd42e41db7c16e0e6b3385554`；封面 SHA-256：`c53c18fa4559c7f62a33bd2c79feae545104faae347c186caf26a49e002e1de7`。
- 匹配原始行定位：`0000093751-24-000484` 第 `39` 个 infoTable 元素

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 27. STATE STREET CORP · 00444T209

- 记录：`T-6ed88a96b3eea0b52f34`；上季 `2023-09-30` → 本季 `2023-12-31`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | UNCHANGED | UNCHANGED |
| 上季股数 / Previous shares | 22182 | 22182 |
| 本季股数 / Current shares | 22182 | 22182 |
| 上季权重比例 / Previous weight | 7.1340665054294e-09 | 7.1340665054294e-09 |
| 本季权重比例 / Current weight | 7.930350602966432e-09 | 7.930350602966432e-09 |

### 原件入口 / SEC originals

**上季 / Previous：2023-09-30**

- `0000093751-23-000703`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/infotable-CU10020230630_v1.xml)
  - 信息表 SHA-256：`a36759d2da76630fd0163db2ba635da2bdce34d12af42b5b432d3b7a8564f15d`；封面 SHA-256：`d756b96085dff1609d00d5eedb0b86a50022e2b8e5f674fa1b254a908e9c1733`。
- 匹配原始行定位：`0000093751-23-000703` 第 `47` 个 infoTable 元素

**本季 / Current：2023-12-31**

- `0000093751-24-000484`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/XML_Infotable_V1.xml)
  - 信息表 SHA-256：`8b95818717c77a4497931c5cf1c6e8f6c742c46bd42e41db7c16e0e6b3385554`；封面 SHA-256：`c53c18fa4559c7f62a33bd2c79feae545104faae347c186caf26a49e002e1de7`。
- 匹配原始行定位：`0000093751-24-000484` 第 `44` 个 infoTable 元素

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 28. STATE STREET CORP · 33830Q109

- 记录：`T-0d3c24f64f3b668f5cb4`；上季 `2023-09-30` → 本季 `2023-12-31`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | ADD | ADD |
| 上季股数 / Previous shares | 658650 | 658650 |
| 本季股数 / Current shares | 666266 | 666266 |
| 上季权重比例 / Previous weight | 8.253853227569119e-07 | 8.253853227569119e-07 |
| 本季权重比例 / Current weight | 4.569460818632096e-07 | 4.569460818632096e-07 |

### 原件入口 / SEC originals

**上季 / Previous：2023-09-30**

- `0000093751-23-000703`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375123000703/infotable-CU10020230630_v1.xml)
  - 信息表 SHA-256：`a36759d2da76630fd0163db2ba635da2bdce34d12af42b5b432d3b7a8564f15d`；封面 SHA-256：`d756b96085dff1609d00d5eedb0b86a50022e2b8e5f674fa1b254a908e9c1733`。
- 匹配原始行定位：`0000093751-23-000703` 第 `17` 个 infoTable 元素

**本季 / Current：2023-12-31**

- `0000093751-24-000484`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/XML_Infotable_V1.xml)
  - 信息表 SHA-256：`8b95818717c77a4497931c5cf1c6e8f6c742c46bd42e41db7c16e0e6b3385554`；封面 SHA-256：`c53c18fa4559c7f62a33bd2c79feae545104faae347c186caf26a49e002e1de7`。
- 匹配原始行定位：`0000093751-24-000484` 第 `17` 个 infoTable 元素

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 29. STATE STREET CORP · P5626F128

- 记录：`T-77540e8232c6213e0487`；上季 `2023-12-31` → 本季 `2024-03-31`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | NEW | NEW |
| 上季股数 / Previous shares | NULL（缺失） | NULL（缺失） |
| 本季股数 / Current shares | 35642 | 35642 |
| 上季权重比例 / Previous weight | NULL（缺失） | NULL（缺失） |
| 本季权重比例 / Current weight | 3.7933231098969544e-07 | 3.7933231098969544e-07 |

### 原件入口 / SEC originals

**上季 / Previous：2023-12-31**

- `0000093751-24-000484`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375124000484/XML_Infotable_V1.xml)
  - 信息表 SHA-256：`8b95818717c77a4497931c5cf1c6e8f6c742c46bd42e41db7c16e0e6b3385554`；封面 SHA-256：`c53c18fa4559c7f62a33bd2c79feae545104faae347c186caf26a49e002e1de7`。
- 匹配原始行定位：无匹配行；必须人工核验该季全部有效组件以确认缺席。

**本季 / Current：2024-03-31**

- `0000093751-24-000592`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375124000592/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375124000592/XML_Infotable.xml)
  - 信息表 SHA-256：`7f026f5016182287b2dfa033797d4e6873a4cc19c39aa1baccc90730160e7bc2`；封面 SHA-256：`913ef885fb089f3260c2fc7fe29b3558d3dd240153f87b1a875328eba2a4840b`。
- 匹配原始行定位：`0000093751-24-000592` 第 `2053` 个 infoTable 元素

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 30. STATE STREET CORP · 433921103

- 记录：`T-c20a41797967d5d3d7b9`；上季 `2024-03-31` → 本季 `2024-06-30`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | NEW | NEW |
| 上季股数 / Previous shares | NULL（缺失） | NULL（缺失） |
| 本季股数 / Current shares | 3123045 | 3123045 |
| 上季权重比例 / Previous weight | NULL（缺失） | NULL（缺失） |
| 本季权重比例 / Current weight | 4.2031563108453964e-06 | 4.2031563108453964e-06 |

### 原件入口 / SEC originals

**上季 / Previous：2024-03-31**

- `0000093751-24-000592`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375124000592/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375124000592/XML_Infotable.xml)
  - 信息表 SHA-256：`7f026f5016182287b2dfa033797d4e6873a4cc19c39aa1baccc90730160e7bc2`；封面 SHA-256：`913ef885fb089f3260c2fc7fe29b3558d3dd240153f87b1a875328eba2a4840b`。
- 匹配原始行定位：无匹配行；必须人工核验该季全部有效组件以确认缺席。

**本季 / Current：2024-06-30**

- `0000093751-24-000681`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375124000681/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375124000681/XML_Infotable.xml)
  - 信息表 SHA-256：`8d23b36b0d4e7acecb850b15e0b236feba97c0be96f5ee6b2ff81a45f1872bd5`；封面 SHA-256：`9c5f5fe1379e3e94e30b725616067827fda8c99d6824a6d71970210e90dd3213`。
- 匹配原始行定位：`0000093751-24-000681` 第 `1898` 个 infoTable 元素

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 31. STATE STREET CORP · G11448100

- 记录：`T-9409587d78c126d4ef15`；上季 `2024-06-30` → 本季 `2024-09-30`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | NEW | NEW |
| 上季股数 / Previous shares | NULL（缺失） | NULL（缺失） |
| 本季股数 / Current shares | 192882 | 192882 |
| 上季权重比例 / Previous weight | NULL（缺失） | NULL（缺失） |
| 本季权重比例 / Current weight | 6.145263274029447e-07 | 6.145263274029447e-07 |

### 原件入口 / SEC originals

**上季 / Previous：2024-06-30**

- `0000093751-24-000681`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375124000681/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375124000681/XML_Infotable.xml)
  - 信息表 SHA-256：`8d23b36b0d4e7acecb850b15e0b236feba97c0be96f5ee6b2ff81a45f1872bd5`；封面 SHA-256：`9c5f5fe1379e3e94e30b725616067827fda8c99d6824a6d71970210e90dd3213`。
- 匹配原始行定位：无匹配行；必须人工核验该季全部有效组件以确认缺席。

**本季 / Current：2024-09-30**

- `0000093751-24-000933`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375124000933/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375124000933/XML_Infotable.xml)
  - 信息表 SHA-256：`4d88bb81dc8965d957004412877a811e9978553b20c125088d7a00cac0aef671`；封面 SHA-256：`85f31d62af2d43b13feafe294b1edfeedf8d09a5503416348a30c753df6767ab`。
- 匹配原始行定位：`0000093751-24-000933` 第 `575` 个 infoTable 元素

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 32. STATE STREET CORP · 006351308

- 记录：`T-e9fa1adaaa201e9355c6`；上季 `2024-09-30` → 本季 `2024-12-31`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | NEW | NEW |
| 上季股数 / Previous shares | NULL（缺失） | NULL（缺失） |
| 本季股数 / Current shares | 12520 | 12520 |
| 上季权重比例 / Previous weight | NULL（缺失） | NULL（缺失） |
| 本季权重比例 / Current weight | 1.8646043705642403e-07 | 1.8646043705642403e-07 |

### 原件入口 / SEC originals

**上季 / Previous：2024-09-30**

- `0000093751-24-000933`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375124000933/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375124000933/XML_Infotable.xml)
  - 信息表 SHA-256：`4d88bb81dc8965d957004412877a811e9978553b20c125088d7a00cac0aef671`；封面 SHA-256：`85f31d62af2d43b13feafe294b1edfeedf8d09a5503416348a30c753df6767ab`。
- 匹配原始行定位：无匹配行；必须人工核验该季全部有效组件以确认缺席。

**本季 / Current：2024-12-31**

- `0000093751-25-000123`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375125000123/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375125000123/XML_Infotable.xml)
  - 信息表 SHA-256：`7e74510635f9f502d1e1f3eff8885311ec526dd7757f3419c77079371a2aa693`；封面 SHA-256：`3a9c485ee5185f456550aecf99a013f490538ee7173a19a317876392215ea977`。
- 匹配原始行定位：`0000093751-25-000123` 第 `56` 个 infoTable 元素

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 33. STATE STREET CORP · G0457F107

- 记录：`T-a333f70998598a4b1dbc`；上季 `2024-12-31` → 本季 `2025-03-31`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | NEW | NEW |
| 上季股数 / Previous shares | NULL（缺失） | NULL（缺失） |
| 本季股数 / Current shares | 35719 | 35719 |
| 上季权重比例 / Previous weight | NULL（缺失） | NULL（缺失） |
| 本季权重比例 / Current weight | 1.1863755008176475e-07 | 1.1863755008176475e-07 |

### 原件入口 / SEC originals

**上季 / Previous：2024-12-31**

- `0000093751-25-000123`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375125000123/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375125000123/XML_Infotable.xml)
  - 信息表 SHA-256：`7e74510635f9f502d1e1f3eff8885311ec526dd7757f3419c77079371a2aa693`；封面 SHA-256：`3a9c485ee5185f456550aecf99a013f490538ee7173a19a317876392215ea977`。
- 匹配原始行定位：无匹配行；必须人工核验该季全部有效组件以确认缺席。

**本季 / Current：2025-03-31**

- `0000093751-25-000351`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375125000351/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375125000351/XML_Infotable.xml)
  - 信息表 SHA-256：`4a921b6ec50fe38adfeab98e5905935878e9d8a0bb7ba40f477cce77e307f8fc`；封面 SHA-256：`ab719198c94e72e9ebf7c096a1af1457b72af71032501d98dd02d93a629c30fe`。
- 匹配原始行定位：`0000093751-25-000351` 第 `306` 个 infoTable 元素

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 34. STATE STREET CORP · 07725L102

- 记录：`T-15b84d5ffdac6868688e`；上季 `2025-03-31` → 本季 `2025-06-30`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | NEW | NEW |
| 上季股数 / Previous shares | NULL（缺失） | NULL（缺失） |
| 本季股数 / Current shares | 13778 | 13778 |
| 上季权重比例 / Previous weight | NULL（缺失） | NULL（缺失） |
| 本季权重比例 / Current weight | 1.2500481055877845e-06 | 1.2500481055877845e-06 |

### 原件入口 / SEC originals

**上季 / Previous：2025-03-31**

- `0000093751-25-000351`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375125000351/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375125000351/XML_Infotable.xml)
  - 信息表 SHA-256：`4a921b6ec50fe38adfeab98e5905935878e9d8a0bb7ba40f477cce77e307f8fc`；封面 SHA-256：`ab719198c94e72e9ebf7c096a1af1457b72af71032501d98dd02d93a629c30fe`。
- 匹配原始行定位：无匹配行；必须人工核验该季全部有效组件以确认缺席。

**本季 / Current：2025-06-30**

- `0000093751-25-000521`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375125000521/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375125000521/XML_Infotable.xml)
  - 信息表 SHA-256：`db7df77142f61924fc2220fd2b12d19dea53f9760f50263817f52e9db20b4a19`；封面 SHA-256：`b3f1ea1714d17a0a558ef707f2400903b272888910b9580bb21dc171b363e0e6`。
- 匹配原始行定位：`0000093751-25-000521` 第 `503` 个 infoTable 元素

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 35. STATE STREET CORP · G21082105

- 记录：`T-3370c3bdbda7ece90650`；上季 `2025-06-30` → 本季 `2025-09-30`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | NEW | NEW |
| 上季股数 / Previous shares | NULL（缺失） | NULL（缺失） |
| 本季股数 / Current shares | 6100 | 6100 |
| 上季权重比例 / Previous weight | NULL（缺失） | NULL（缺失） |
| 本季权重比例 / Current weight | 8.750816120485238e-08 | 8.750816120485238e-08 |

### 原件入口 / SEC originals

**上季 / Previous：2025-06-30**

- `0000093751-25-000521`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375125000521/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375125000521/XML_Infotable.xml)
  - 信息表 SHA-256：`db7df77142f61924fc2220fd2b12d19dea53f9760f50263817f52e9db20b4a19`；封面 SHA-256：`b3f1ea1714d17a0a558ef707f2400903b272888910b9580bb21dc171b363e0e6`。
- 匹配原始行定位：无匹配行；必须人工核验该季全部有效组件以确认缺席。

**本季 / Current：2025-09-30**

- `0000093751-25-000651`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375125000651/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375125000651/XML_Infotable.xml)
  - 信息表 SHA-256：`4a2df53ee15261e6d5255691f0a9b89abf6db6e2444a4e90abadddc69cc87caf`；封面 SHA-256：`3c292d3398b3f94365de6472fbab12195a9e2ffe7d6331f05ec7803a198f1c4a`。
- 匹配原始行定位：`0000093751-25-000651` 第 `834` 个 infoTable 元素

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 36. STATE STREET CORP · G10830100

- 记录：`T-4b9c9d42ced5d59e80fe`；上季 `2025-09-30` → 本季 `2025-12-31`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | NEW | NEW |
| 上季股数 / Previous shares | NULL（缺失） | NULL（缺失） |
| 本季股数 / Current shares | 231120 | 231120 |
| 上季权重比例 / Previous weight | NULL（缺失） | NULL（缺失） |
| 本季权重比例 / Current weight | 1.2637948366211372e-07 | 1.2637948366211372e-07 |

### 原件入口 / SEC originals

**上季 / Previous：2025-09-30**

- `0000093751-25-000651`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375125000651/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375125000651/XML_Infotable.xml)
  - 信息表 SHA-256：`4a2df53ee15261e6d5255691f0a9b89abf6db6e2444a4e90abadddc69cc87caf`；封面 SHA-256：`3c292d3398b3f94365de6472fbab12195a9e2ffe7d6331f05ec7803a198f1c4a`。
- 匹配原始行定位：无匹配行；必须人工核验该季全部有效组件以确认缺席。

**本季 / Current：2025-12-31**

- `0000093751-26-000100`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375126000100/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375126000100/XML_Infotable.xml)
  - 信息表 SHA-256：`a9fe82d8bdbe52794e069a7918b90857ceff6c220fc8907c3f33599fa7e426e7`；封面 SHA-256：`4af771b8f055ea0d643243ff5f19cbab3d310f651b515b55ac38957f1c598bbf`。
- 匹配原始行定位：`0000093751-26-000100` 第 `519` 个 infoTable 元素

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 37. STATE STREET CORP · 38911N206

- 记录：`T-80d4433da7f03d1e10f8`；上季 `2025-12-31` → 本季 `2026-03-31`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | NEW | NEW |
| 上季股数 / Previous shares | NULL（缺失） | NULL（缺失） |
| 本季股数 / Current shares | 3471 | 3471 |
| 上季权重比例 / Previous weight | NULL（缺失） | NULL（缺失） |
| 本季权重比例 / Current weight | 7.425288055906137e-08 | 7.425288055906137e-08 |

### 原件入口 / SEC originals

**上季 / Previous：2025-12-31**

- `0000093751-26-000100`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375126000100/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375126000100/XML_Infotable.xml)
  - 信息表 SHA-256：`a9fe82d8bdbe52794e069a7918b90857ceff6c220fc8907c3f33599fa7e426e7`；封面 SHA-256：`4af771b8f055ea0d643243ff5f19cbab3d310f651b515b55ac38957f1c598bbf`。
- 匹配原始行定位：无匹配行；必须人工核验该季全部有效组件以确认缺席。

**本季 / Current：2026-03-31**

- `0000093751-26-000315`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375126000315/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375126000315/XML_Infotable.xml)
  - 信息表 SHA-256：`1bb85b28ed78a0b64f7457e79c637eca057627e2970fe4e849e4f2fcad2f5b8c`；封面 SHA-256：`524cf1f281e6b8896c20f8229fd68ced7c4dbe93574e0de94e9ed5be3eb5beaf`。
- 匹配原始行定位：`0000093751-26-000315` 第 `1698` 个 infoTable 元素

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________

## 38. STATE STREET CORP · M4056D110

- 记录：`T-6fbb9c687f888e8942fd`；上季 `2026-03-31` → 本季 `2026-06-30`。
- PUT/CALL：`NONE`；份额单位：`SH`。

| 核验项 / Item | 独立程序 / Reference | 产品程序 / Production |
|---|---|---|
| 变化类型 / Change | NEW | NEW |
| 上季股数 / Previous shares | NULL（缺失） | NULL（缺失） |
| 本季股数 / Current shares | 185903 | 185903 |
| 上季权重比例 / Previous weight | NULL（缺失） | NULL（缺失） |
| 本季权重比例 / Current weight | 4.908901684370442e-06 | 4.908901684370442e-06 |

### 原件入口 / SEC originals

**上季 / Previous：2026-03-31**

- `0000093751-26-000315`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375126000315/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375126000315/XML_Infotable.xml)
  - 信息表 SHA-256：`1bb85b28ed78a0b64f7457e79c637eca057627e2970fe4e849e4f2fcad2f5b8c`；封面 SHA-256：`524cf1f281e6b8896c20f8229fd68ced7c4dbe93574e0de94e9ed5be3eb5beaf`。
- 匹配原始行定位：无匹配行；必须人工核验该季全部有效组件以确认缺席。

**本季 / Current：2026-06-30**

- `0000093751-26-000507`，角色 `BASE`：[封面 / Cover](https://www.sec.gov/Archives/edgar/data/93751/000009375126000507/primary_doc.xml) · [信息表 / Holdings](https://www.sec.gov/Archives/edgar/data/93751/000009375126000507/XML_Infotable.xml)
  - 信息表 SHA-256：`c94b04f276823fd8229ce616aba95f480b262c88d5a7684f186db630da561d03`；封面 SHA-256：`f0e6a21fe80427b383bbd4641fe1c1494e5028de47013ea866a41269d7a778fa`。
- 匹配原始行定位：`0000093751-26-000507` 第 `1268` 个 infoTable 元素

真人结论 / Human result：____________　审核人 / Reviewer：____________　日期 / Date：____________
