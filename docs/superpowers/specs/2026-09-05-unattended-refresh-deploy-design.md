# 无人值守数据刷新与生产发布设计

> 状态：方案 A 已获产品负责人批准；数据正确性与安全审查结论已纳入；等待书面规格复核
>
> 日期：2026-09-05
> 范围：SEC 数据刷新、分析正确性修复、发布硬门、GHCR 镜像、VPS 自动部署、回滚和 GitHub 通知

## 1. 背景与结论

当前系统已有 SEC 采集、SQLite 标准化、确定性分析、Streamlit 看板、GHCR 镜像和 VPS 容器，但还不能安全地称为“无人值守”。审查发现以下发布阻断项：

- 同一证券在一个 filing 中出现多行时，分析层会覆盖而不是聚合；现有数据库的 effective filings 中实际存在大量此类行。
- 现有 Gate 1 复用生产 parser，Gate 2 未正确处理 amendment，旧的 `PASS` 不能作为独立正确性证明。
- amendment 的 `RESTATEMENT` 与 `ADD_NEW_HOLDINGS` 语义尚未保存，不能一律视为“最新版替代全部旧数据”。
- 原始 manifest 的真实抓取时间为空，缓存命中也不能证明 SEC 端未变化。
- 当前 Docker 构建会在可缓存镜像层中访问 SEC；定时 workflow 可能发布旧数据。
- 当前发布没有测试硬门、不可变 digest 部署、失败回滚或 GitHub Issue 通知。

因此实施必须先修正数据语义和 Gate，再建设自动发布。旧 Gate 报告全部视为历史记录，不作为本次上线依据；生产 VPS 在新链路完成验收前保持不变。

## 2. 目标与非目标

### 目标

1. 定时发现当前启用机构最近 12 个报告季度的新 `13F-HR`、`13F-HR/A`。
2. 对 SEC 原始文件执行可追溯、幂等、失败闭锁的采集、标准化和确定性分析。
3. 正确处理 amendment restatement、add-new-holdings 和同一证券多行聚合。
4. 只有测试、数据质量、Gate 1、Gate 2 全部通过时才生成生产 release bundle。
5. 只按不可变 GHCR digest 部署到 VPS；候选失败不触碰生产，正式切换失败自动恢复旧容器。
6. 刷新、发布、部署或回滚失败时创建或更新 GitHub Issue，并使用 GitHub 账户通知设置发送邮件。
7. 同样的 raw、代码、配置和 methodology version 产生同样的分析与 release identity。

### 非目标

- 不让 Streamlit 实时请求 SEC。
- 不增加自动交易、买卖建议、估值、行情或 AI 解释。
- 不把 Gate 3 伪造为通过；其状态保持 `PENDING_REAL_WORLD_VALIDATION`。
- 不在公开仓库、镜像层、artifact、日志或 Issue 中泄露 SSH 私钥、SEC 联系信息或其他凭据。
- 不把 `latest` 当成生产部署身份。
- 本次不引入 Kubernetes、云数据库、复杂队列或 Caddy/域名迁移。

## 3. 总体架构

```text
GitHub schedule / trusted master push / manual dispatch
                         |
                         v
                 refresh-and-release
       SEC discovery -> content-addressed raw staging
                         |
                         v
        secure parse -> clean staging DB -> deterministic analytics
                         |
                         v
       release manifest + data/code/config fingerprints
                         |
                         v
      pytest -> quality gate -> Gate 1 -> Gate 2 -> bundle verify
                         |
                  all hard gates PASS
                         |
                         v
      build image from the already-validated bundle (no SEC access)
                         |
                   registry digest
                         |
                         v
       restricted SSH -> VPS candidate -> production switch
                         |
                  success or rollback
                         |
                         v
             GitHub Issue failure/recovery notice
```

系统由四个清晰边界组成：

1. **Refresh**：发现并保存 SEC 证据，不发布。
2. **Release**：从 clean staging 构建 DB、分析、Gate 报告和不可变 bundle。
3. **Image**：只封装已通过 Gate 的 bundle，不联网抓 SEC。
4. **Deploy**：只接受固定仓库的 digest，不理解 SEC 或分析逻辑。

## 4. SEC 发现、下载与原始证据

### 4.1 发现

- 读取 `data.sec.gov/submissions/CIK##########.json`，并跟随其中 `filings.files` 指向的历史 submissions 分片，保证最近 12Q 不因 recent 列表截断而遗漏。
- 只接受 `13F-HR` 与 `13F-HR/A`；CIK、accession、report period、filing date、accepted time 和 source URL 均从 SEC 元数据取得。
- 以“当前 UTC 日期、季度结束日、法定 45 天披露窗口”计算 expected quarter；不能用数据库里已有的最大季度冒充最新应有季度。

### 4.2 网络边界

- release 模式必须提供真实、可联系的 `SEC_USER_AGENT`；缺失或仍含 `example.com` 时立即失败。
- 配置统一命名为 `SEC_RATE_LIMIT_RPS`，校验为有限正数并使用保守默认值；不再把 RPS 误称为秒数。
- 仅允许 HTTPS 且最终重定向主机属于 `sec.gov`/`www.sec.gov`/`data.sec.gov`。
- 支持 `Retry-After`、有限次数重试和指数退避；429、5xx、超时、DNS、TLS 或内容校验错误均记录明确失败。
- 对响应体、gzip 解压后大小和 XML 节点数设置上限，避免无限内存/磁盘消耗。
- XML 禁用 DTD、外部实体和网络加载；malformed XML 不使用“修复后继续”的隐式 recovery。

### 4.3 原始保存与远端重验证

- 每个 accession 至少保存 submission metadata、cover/primary document、information table 和抓取 manifest。
- 原始文件按 SHA-256 内容寻址保存；accession manifest 引用具体 content object。若 SEC 同 accession 内容变化，保留旧对象并新增版本，不原地销毁证据。
- manifest 至少包含 CIK、accession、form type、report period、filing/accepted time、source/final URL、实际 HTTP 响应完成时间、ETag/Last-Modified（如有）、status、byte size、checksum 和 parser version。
- 缓存只能加速，不能作为“SEC 没变化”的证据。每轮对 12Q 范围做远端 discovery，并对已知文件使用可信条件请求；服务端不支持条件验证时按受控频率重新取回并比对 checksum。
- raw 路径写为相对 release root 的可移植路径，不保存开发机绝对路径。
- 任一新或变化 filing 下载、校验、cover parse、information-table parse 失败，整轮不得发布。

## 5. Amendment 状态机

SEC 官方语义区分两种 amendment：

- `RESTATEMENT`：提交完整更正后的 filing，替换此前有效集合。
- `ADD_NEW_HOLDINGS`：只提交新增条目，补充当前有效集合。

因此 effective quarter 不是简单的“最新 accession”。每个 manager/report period 按 `accepted_at`、`amendment_number`、accession 的确定性顺序运行状态机：

1. 原始 `13F-HR` 建立 base。
2. 遇到 `RESTATEMENT`，清空此前 base/additions，以该 amendment 作为新 base。
3. 遇到 `ADD_NEW_HOLDINGS`，将该 amendment 作为新的 supplement 加入当前 base。
4. 后续 restatement 再次重置；后续 add-new-holdings 再追加。
5. amendment type、number、accepted time 任一缺失或冲突时，标记 `AMENDMENT_PENDING` 并阻止发布，不猜测。

数据库保留每个原始 filing，并新增：

- `filings.amendment_number`
- `filings.amendment_type`
- `filings.accepted_at`
- `filings.primary_doc_path` / `primary_doc_checksum`
- `filings.info_table_path` / `info_table_checksum`
- `filings.amends_filing_id`：指向同 manager/quarter 时间序列中的直接前一 filing，仅表示审计链，不表达 replace/merge。
- `effective_periods`：每个 manager/quarter 的派生状态与 state hash。
- `effective_filing_components`：记录 effective period 使用的 base 和 supplement accessions 及顺序。

新增 amendment 必须改变 raw/effective fingerprint，并只重建受影响季度起向后的 position changes、consensus、trend 和 quality；实现可以为简化而确定性重建全部派生表，但结果必须等价。

## 6. Raw holdings 与经济持仓聚合

`holdings` 继续一行不差地保存 SEC information table 行，以 `(filing_id, row_ordinal)` 唯一，不对原始行做去重或覆盖。

分析层新增可重建的 `effective_positions`，经济持仓 key 为：

```text
(effective_period_id, security_id/CUSIP, normalized_put_call, ssh_prnamt_type)
```

规则：

- `put_call` 只允许 `NULL`、`CALL`、`PUT`，三者绝不合并。
- `ssh_prnamt_type` 至少区分 `SH` 与 `PRN`，不同计量单位绝不相加。
- 同一 key 的 raw 行按精确整数求和 `shares` 和 `value`；投资裁量、other manager 和 voting-authority 分行作为 provenance 保留，但在 manager-level exposure 中合计。
- 任一应为数字的 `shares`/`value` 缺失、负数、溢出或解析失败，不按零处理，标记 inconsistent 并阻止发布。
- `portfolio_weight = aggregated_position_value / sum(all aggregated effective position values)`；分母为零时输出 `INSUFFICIENT_DATA`。
- top holdings、Manager 页面、Stock 页面、Portfolio、position changes、consensus 和 trend全部只读 `effective_positions`，不能直接把原始行或 original+amendment 混合统计。
- exact duplicate raw rows 不被静默删除；作为质量异常保留并由 Gate 报告。

Position change 继续按相邻可用季度的同一经济持仓 key 计算 `NEW/ADD/REDUCE/EXIT/UNCHANGED`。若计量类型变化、历史缺失或有效集合不完整，返回 `INSUFFICIENT_DATA`，不得制造 change type。

## 7. Clean staging 与发布身份

每次 release 从空 staging 目录开始：

1. 将验证过的 content-addressed raw 对象按 manifest 装配。
2. 从零建 SQLite schema、manager 配置、security master、raw holdings 和 effective state。
3. 确定性重建 position changes、consensus、trend 和 quality。
4. checkpoint SQLite，禁止把 WAL/SHM 状态带入 bundle。
5. 生成 release manifest 并执行只读回检。

release manifest 包含：

- runtime source tree hash（只含会影响运行/数据的代码，不用整个 Git SHA）
- Git commit SHA（仅审计元数据）
- Python/runtime/lock hash
- methodology version 和相关文档 hash
- managers/security mapping config hash
- raw manifest fingerprint
- effective-state fingerprint
- SQLite SHA-256
- Gate 报告 SHA-256 与状态
- Gate 3 固定状态

release identity 由会影响结果的代码、锁文件、配置、methodology 和 raw fingerprints 组成。纯文档或无关文件变化不制造新数据 release。

## 8. Gate 与质量门

### 8.1 通用约束

- Gate 以 SQLite URI `mode=ro`/immutable 打开数据库；运行前后 DB SHA 必须一致。
- 所有报告写入独立输出目录，不修改被验收 bundle。
- 报告绑定 raw fingerprint、effective fingerprint、DB SHA、runtime tree hash、methodology version 和 Gate implementation hash。
- `PRAGMA integrity_check`、`foreign_key_check`、raw/manifest 完整性、有效集合完整性和 bundle 回读均为硬门。
- 当前启用 manager 是覆盖率固定分母；latest expected quarter 覆盖率低于 80% 时失败。
- 最新 expected quarter 的新/变更 filing 存在 failed、malformed、unknown amendment 或 silent skip 时失败。

### 8.2 Gate 1 — Data Correctness

- 使用独立 reference extractor 直接从原始 XML 提取关键字段，不调用生产 `parse_info_table`。
- 按 release fingerprint 派生固定抽样，至少覆盖 5 managers × 3 quarters × 10 rows；实际不足时报告真实数量并失败，禁止虚增 sample count。
- 样本跨 manager，且在数据存在时强制包含 amendment、PUT、CALL 和 unresolved CUSIP。
- 逐行核对 CUSIP、issuer、shares、value、put/call、share type；必须 100% 匹配。
- 覆盖声明只基于实际抽样行，不得用全库存在性替代样本覆盖。

### 8.3 Gate 2 — Analytical Correctness

- 使用与生产共享的“规范文档”，但使用独立实现选择 effective component 状态和重算经济持仓，不能调用生产 aggregation/change 函数。
- original/amendment 绝不作为相邻季度；add-new-holdings 按 supplement 语义合并。
- 每轮自动抽样至少 30 个真实 transitions，跨至少 5 managers，核对 aggregated shares/value、portfolio weight、weight direction 和 change type。
- 样本覆盖 `NEW/ADD/REDUCE/EXIT/UNCHANGED`；真实数据存在 shares 上升但 weight 下降时必须覆盖。若某类无候选，报告真实候选数并按既定 Gate policy 失败，不伪造。
- 首次生产切换保留人工审阅的 30 个 transition 报告；methodology/aggregation/effective-state 版本变化时，自动发布保持闭锁，直到生成并批准新的人工基线。
- 仅 manager 1 或单一策略类别的样本不合格。

### 8.4 Gate 3

Gate 3 只允许为 `PENDING_REAL_WORLD_VALIDATION`，不作为例行数据发布的硬门，也不得被 workflow 改写为 PASS。

## 9. GitHub Actions

### 9.1 `ci.yml`

触发：pull request 和 push。

- 完全离线运行单元、集成、回归测试和 Python 编译检查。
- job 权限只有 `contents: read`。
- 不读取 secrets、不访问 SEC、不写 package/Issue、不使用 production environment。
- 禁止 `pull_request_target`。

### 9.2 `refresh-and-release.yml`

触发：

- trusted `master` push。
- 每周二、周五 04:17 UTC。
- `workflow_dispatch`，但脚本验证运行 ref 必须是 `refs/heads/master`。

步骤：

1. 精确 checkout 触发 SHA，`persist-credentials: false`。
2. 远端 discovery/revalidation、clean staging、分析、manifest。
3. pytest、质量门、Gate 1、Gate 2、bundle 回读。
4. 上传不含凭据的 manifest、Gate 报告和质量摘要 artifact。
5. 查询同 release identity 的已知 registry digest。
6. 若 identity 未发布，构建并推送唯一 run tag、runtime hash tag 和便利性的 `latest`，读取 registry digest。
7. 若 identity 已发布但 VPS readback 不是该 digest，仍进入部署重试；只有 registry 与 VPS 都一致时才返回 `NO_CHANGE`。

约束：

- workflow/job 权限逐 job 最小化：build 才有 `packages: write`，通知才有 `issues: write`，deploy 才能读取 production secrets。
- GitHub expressions 先进入 env，再经 allowlist/regex 校验并加引号，不直接拼入 shell。
- workflow concurrency 防止 GitHub 侧重叠；进入生产切换后的运行不被新运行强制取消。
- PR cache 与 release cache 隔离；cache 只是加速，不参与证据、identity 或 `NO_CHANGE` 判断。
- Actions 引用固定完整 commit SHA；Python 依赖使用带 hashes 的锁文件；Python 基础镜像固定 digest。
- 启用 master branch protection、workflow/deploy `CODEOWNERS`、production environment 分支限制，以及公开仓库 secret scanning/push protection（平台能力允许时）。

## 10. 镜像与运行时

- Dockerfile 不访问 SEC，只显式复制运行所需代码、静态配置和本轮已验证 release bundle；不再 `COPY . .`。
- 构建后在镜像内回读 release manifest、SQLite SHA 和 Gate hashes；不一致则 build 失败。
- 镜像以 non-root 用户运行；production 使用 `--read-only`、writable tmpfs、`--cap-drop ALL`、`no-new-privileges`、PID/内存/CPU 限制。
- public UI 的 SQLite connection 使用 immutable read-only 模式，不执行 WAL、迁移或写入；任何运行状态写入 tmpfs 或标准输出。
- 镜像标签至少包含唯一 run tag 与 runtime hash；`latest` 仅供人工发现，deploy wrapper 拒绝裸 tag。
- 生产接受的唯一格式为：

```text
ghcr.io/fancy0121/13f-intelligence@sha256:<64 lowercase hex>
```

## 11. VPS 部署、切换与回滚

### 11.1 一次性 bootstrap

1. 创建无交互 shell、无密码、非 root、非 docker-group 的专用 deploy 账号。
2. 安装 root-owned、deploy 账号不可修改的窄入口和 root deploy helper。
3. `authorized_keys` 使用 `restrict,command=...`；入口只接受 `deploy <allowed digest>`。
4. sudoers 只允许入口调用固定 root helper；端口、容器名、bind address、资源限制和 env 文件均由 root-owned host config 固定，workflow 无权覆盖。
5. GitHub secret 保存经带外核验的固定 host key；运行时禁止 `ssh-keyscan`，强制 `StrictHostKeyChecking=yes`。
6. host 使用 `flock` 防止绕过 GitHub concurrency 的并发部署。

### 11.2 每次部署

1. 校验 digest 格式与固定 GHCR 仓库，拉取指定 digest。
2. 启动 `thirteenf-candidate` 于 `127.0.0.1:18501`。
3. 候选同时通过有界 HTTP health、容器内 bundle/DB hash 回读和 release fingerprint 检查。
4. 候选失败：删除候选，当前生产容器保持运行，返回 `CANDIDATE_FAILED`。
5. 候选成功：停止但不删除旧 `thirteenf`，改名为唯一 backup；用同 digest 和固定参数启动新 `thirteenf`。
6. 正式容器再次通过 HTTP、bundle 和 digest readback 后，返回 `DEPLOYED`，再清理过旧 backup；至少保留最近一个已知健康 image/container 直到验收完成。
7. 正式失败：删除失败的新容器，将 backup 恢复为 `thirteenf` 并启动；旧版健康通过后返回 `ROLLED_BACK`。
8. 旧版恢复也失败时返回 `ROLLBACK_FAILED`，不得报告成功。

当前实际公开方式为 VPS `0.0.0.0:8501`，本次为避免同时引入域名/Caddy 迁移而保持该方式，并在文档中明确它不是 HTTPS。正式 bind/port 写死在 root-owned host config，GitHub workflow 无权改变。后续 HTTPS 反向代理作为独立安全迭代，不伪装为本次已完成。

## 12. GitHub Issue 与邮件通知

- 独立通知 job 使用 `if: always()`，只拥有 `issues: write`。
- 使用固定 label（而非仅凭标题）查找 automation incident；无开放 Issue 时创建，有则追加评论，避免重复 Issue。
- Issue 内容只允许固定字段：失败阶段、Actions run URL、commit SHA、release fingerprint、image digest（如有）和 `CANDIDATE_FAILED/ROLLED_BACK/ROLLBACK_FAILED` 枚举。
- 不上传 shell command、环境变量、SSH 输出、SEC User-Agent、原始异常请求头或 secrets。
- Issue 指派仓库所有者；只有完整成功且 VPS digest/bundle readback 一致后才追加恢复评论并关闭。
- “Issue 创建成功”不等于“邮件已收到”。最终验收必须由仓库所有者实际确认 GitHub 邮件到达；未确认时标记 `EMAIL_DELIVERY_UNKNOWN`。

## 13. Secrets 与 GitHub 配置

### Production environment secrets

- `VPS_SSH_PRIVATE_KEY`
- `VPS_SSH_KNOWN_HOSTS`

### Repository/refresh secret

- `SEC_USER_AGENT`

### Variables

- `VPS_HOST`
- `VPS_PORT`
- `VPS_USER`
- `MIN_MANAGER_COVERAGE`（固定为 `0.80`，变更需 methodology review）
- `SEC_RATE_LIMIT_RPS`（受代码上下界约束）

SSH key 不进入 build arg、cache、artifact、镜像或 Issue；runner 临时 key 文件权限为 `0600`，并由 trap 在所有退出路径清理。GHCR 使用短期 `GITHUB_TOKEN`，不创建长期 package token。

## 14. 测试策略

### 数据与分析

- SEC User-Agent 缺失/example 拒绝、RPS 边界、重试、重定向 host、响应/解压大小上限。
- fetch timestamp 来自实际响应；条件请求与同 accession checksum 变化保留旧对象。
- recent + historical submissions 分片发现 12Q。
- DTD/entity/network XML 被拒，malformed XML 失败。
- amendment cover metadata：restatement、add-new-holdings、多 amendment、未知 type 闭锁。
- raw row 保真；同 CUSIP 多行按 `(CUSIP, put_call, share type)` 聚合；CALL/PUT/普通股不合并。
- null、负数、溢出、zero denominator、missing history 返回错误或 `INSUFFICIENT_DATA`。
- 所有产品查询只使用 effective positions；original/amendment 不重复计数。
- NEW/ADD/REDUCE/EXIT/UNCHANGED、shares 上升但 weight 下降。

### Release/Gate

- clean rebuild 两次得到相同 fingerprints。
- manifest 排序、runtime tree hash、DB hash 和 Gate hash 稳定。
- 新 amendment 改变 fingerprint 并列出受影响季度；纯无关文档变化不改变 release identity。
- Gate 1 独立 extractor 的故意 parser mismatch 能被发现。
- Gate 2 对重复行、supplement、restatement、跨 manager stratification 的故意分析错误能被发现。
- Gate read-only：运行前后 DB SHA 不变。
- expected quarter/45-day window、固定分母覆盖率、malformed/failed/unknown amendment 硬失败。
- 已发布 identity 但 VPS digest 不一致时不会错误 `NO_CHANGE`。

### Docker/部署/通知

- 镜像构建期间无法访问 SEC 且仍能完成。
- bundle 被篡改时镜像回读失败。
- public container non-root/read-only 启动并完成五页 smoke test。
- deploy wrapper 拒绝裸 tag、错误仓库、无效 digest、额外参数和并发调用。
- candidate 失败不停止生产；正式失败恢复原容器；rollback 失败返回独立状态。
- Issue payload allowlist 和 secret redaction。

## 15. 实施与提交边界

按以下 checkpoint 实施，每个 checkpoint 先测试后提交，且不混入当前未提交的 UI/中英文化工作：

1. **Correctness foundation**：SEC metadata/timestamp/network hardening、amendment state、effective aggregation、产品查询修复、schema migration/rebuild、Gate 1/2 重写。
2. **Release bundle**：clean staging、quality gate、fingerprints、manifest、read-only verification、dependency locks。
3. **Trusted automation**：最小权限 CI、refresh/release、GHCR digest、Issue notification。
4. **Hardened runtime**：non-root/read-only Docker、public-mode read-only DB、bundle readback。
5. **VPS deployment**：host scripts、forced command、flock、candidate/promote/rollback tests 和一次性 bootstrap。
6. **Production validation**：首次 manual refresh、Gate reports、GHCR digest、VPS inspect/readback、故障演练、Issue 和真实邮件证据。

任何 checkpoint Gate FAIL 即停止，不进入下一个。不得为“自动化完成”降低正确性或安全门槛。

## 16. 最终验收

以下条件全部满足才可称为“无人值守链路已交付”：

1. PR/push CI 在无 secrets、无 SEC 网络条件下实际通过。
2. 手动 release run 实际从 SEC 完成 discovery/revalidation 和 clean rebuild。
3. 当前数据不存在未知 amendment type；effective component 状态可追溯。
4. 聚合修复后的全量分析重建完成，旧 Gate 报告已被新报告替代。
5. Gate 1 真实检查数量满足要求且 100% 匹配。
6. Gate 2 自动独立复算 PASS，并存在跨 manager 的人工基线审阅报告。
7. Gate 报告 fingerprint、DB SHA 与 release manifest 完全一致，Gate 运行前后 DB 未变化。
8. GHCR 存在唯一 tag 和不可变 digest，镜像内 bundle 回读一致。
9. VPS `docker inspect`、容器内 readback 与 workflow digest/release fingerprint 一致。
10. 公共健康检查返回 200，五个页面 smoke test 通过。
11. 候选失败演练不影响生产；正式失败演练能恢复旧容器；回滚也失败时能正确告警。
12. 失败工作流创建/更新固定 GitHub Issue，恢复后关闭。
13. 仓库所有者实际确认收到 GitHub Issue 邮件；否则状态为 `EMAIL_DELIVERY_UNKNOWN`。
14. master protection、production environment 限制、pinned Actions、secret scanning/push protection 已通过 GitHub readback 核验；平台不支持项明确标记。
15. schedule 在默认分支启用；首次真实 scheduled run 完成前，状态为 `SCHEDULE_CONFIGURED_NOT_YET_OBSERVED`。
16. Gate 3 仍为 `PENDING_REAL_WORLD_VALIDATION`。

## 17. 外部依赖与明确阻塞项

实施代码不需要再选择架构方案，但生产配置前必须具备：

- 一个真实、可联系且不写入公开日志的 SEC User-Agent。
- GitHub production environment secrets/variables 的写权限。
- VPS 一次性 root bootstrap 权限。
- 仓库所有者愿意通过一次测试 Issue 实际确认邮件到达。

缺少其中任一项时，对应外部验收标记 `UNKNOWN`，不得声称生产自动化已经交付。

## 18. 权威依据

- SEC Form 13F FAQ：amendment restatement 必须重交完整 filing 并 supersede 原 filing；add-new-holdings 只包含新增条目并 supplement 当前 filing。
  - https://www.sec.gov/rules-regulations/staff-guidance/division-investment-management-frequently-asked-questions/frequently-asked-questions-about-form-13f
- SEC Form 13F Special Instructions：amendment 必须二选一为完整 restatement 或只增加 holdings entries。
  - https://www.sec.gov/pdf/form13f.pdf
