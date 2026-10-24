# 季度主更新、每周补漏、每月修订 / SEC refresh calendar

## 当前状态

2026-10-24：**SCHEDULE_CONFIGURED_NOT_YET_OBSERVED / NOT_DEPLOYED_PRODUCTION**。
默认分支已配置定时工作流，实际 GitHub→VPS 受限 SSH、故障 Issue 和邮件到达均已验证。
首次完整 SEC 候选采集失败后正在重试，尚未取得完整 Gate 结果；首次定时触发也尚未发生。
专用账号受固定命令限制，不能改写代码、授权文件和冻结基线。
这不是客户数据库自动上线的完成证明。旧 push-to-publish 工作流已替换为只读调度测试，
不构建或推送生产镜像。原有发布阻断与人工 Gate 不得绕过。具体回执见文末。

## 已批准的周期

- 季度主更新：SEC 实际申报截止日后的下一个美国工作日。
- 每周补漏：主更新日之后第 7、14、21、28 天。
- 每月修订：每月 1 日；与补漏重叠时只运行一次。
- UTC 14:17，北京 22:17，科伦坡 19:47。GitHub 排队可能延迟，并非准点 SLA。
- 日历检查每天运行几秒；**不是每天下载 SEC**。仅上述到期日连接 VPS 生成候选。
- 主更新和补漏均复用现有 12Q raw/修订重建；月度修订也通过相同入口检查原始披露，
  不假称已经有专用增量扫描优化。候选成功不等于当季机构已交齐。
- SEC 官方日历明确维护到 2028-12-31；到期后失败并告警，不猜将来假日。
  2029 年前必须补充官方截止日和下一工作日。

来源：[SEC FAQ 25](https://www.sec.gov/rules-regulations/staff-guidance/frequently-asked-questions-about-form-13f)。
本地只读预览：`python scripts/refresh_schedule.py --date 2026-10-23`。

下一批计划时间（工作流已配置；尚未观察到首个定时触发，不能视为准点承诺）：

| 日期 | 工作 |
|---|---|
| 2026-11-01 | 月度修订检查 |
| 2026-11-17 | 2026 Q3 主更新；官方截止日 11-16 |
| 2026-11-24 | 第一次补漏 |
| 2026-12-01 | 第二次补漏 + 月度检查，合并一次 |
| 2026-12-08 | 第三次补漏 |
| 2026-12-15 | 第四次补漏 |

## 激活前提 / Operator prerequisites

1. 完成受控源码交接并确认旧 master push-to-publish 流程已被只读测试替代；本次变更不得携带其他
   未提交代码或敏感配置。PR 的存在不是激活，schedule 只在默认分支执行。
2. VPS 上有经过审查的 `/opt/13f-intelligence` checkout、锁定环境、原始缓存、
   `scripts/refresh_candidate.py` 与本次 `scripts/refresh_schedule.py`。不从 CI 自动覆盖 VPS。
3. 专用低权限 SSH 用户仅能访问所需缓存、候选目录和冻结服务快照；不授予 Docker/root。
   专用 authorized_keys 必须配置 restrict 与固定 command wrapper（`deploy/refresh-command.sh`），
   只接受 inspect/refresh，禁止任意命令/转发。home、.ssh、authorized_keys、代码、wrapper
   均由 root 持有，刷新账号不得修改自己的授权文件或执行代码。
4. 维护人员在 VPS 创建只对该用户可读的 `/etc/thirteenf/refresh.env`（shell 环境文件，
   不进 Git）：`SEC_USER_AGENT` 为真实名称/联系邮箱；`THIRTEENF_SERVING_DB` 为实际
   冻结快照绝对路径；隔离政策只可通过显式 `THIRTEENF_QUARANTINE_POLICY` 指定。
5. GitHub Variables：`REFRESH_HOST`、`REFRESH_USER`、可选 `REFRESH_PORT`。
   GitHub Secrets：`REFRESH_SSH_PRIVATE_KEY`、`REFRESH_SSH_KNOWN_HOSTS`。
   主机公钥必须由可信控制台核对，不通过临时 ssh-keyscan 静默信任。
6. 启用仓库 Issues、允许该单独通知 job 的 issues:write；确认负责人启用 GitHub 邮件
   通知并订阅该 Issue。**GitHub 不保证本程序能够确认收件箱实际到达。**

## 验证方法及不做的事情

- `python -m unittest discover -s tests -p test_refresh_schedule.py -v`：无联网单元测试。
- Actions 手工 `inspect`：仅日历，不访问 SEC/VPS，不制造更新成功记录。
- 手工 `connection-test`：经严格主机校验，只运行受限 SSH 的 inspect 命令，
  验证密钥与连接；不刷新数据，也不代表完整数据链通过。
- 手工 `notification-test`：明确的故障演练，不访问 VPS；应看到一次专用 Issue。
  负责人需核对邮件实际到达；演练 Issue 与真实故障用运行链接区分。
- 到期日 `run` 或 schedule：严格 SSH 主机校验 → 已部署候选入口 → 私有 raw/候选库 →
  独立自动 Gate → 等待人工验收。无 `--offline`；失败退出、保留服务快照。
- 本脚本不替代现有候选入口的 Gate、checksum、锁、原文校验；不执行镜像构建、
  发布、生产换库、自动签字或交易。不存在“定时器配置成功 = 客户看到新数据”。
- Workflow 超时或取消时不自动删除远端锁；维护人员先核实进程和私有回执。
- 通知 job 的自身失败只能由 GitHub Actions 原生失败通知和人工运行检查发现；
  GitHub 故障、任务根本未触发、整条 workflow 被取消时不能保证 Issue 通知。
- GitHub 公开仓库连续 60 天无活动可能停用 schedule；不得靠无意义自动 commit 保活。
  要求长期无人值守前，必须配置独立 VPS timer/watchdog 并实测失联告警，或接受该限制。
  [GitHub 官方 schedule 限制](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)。
- 故障 Issue 不自动关闭：候选成功仍非生产修复，不能把一次 inspect 或候选通过当成恢复上线。

## 本次验证边界

2026-10-24 已完成默认分支发布、VPS 专用受限通道和 GitHub Secrets/Variables 配置。
六个发布文件经独立下载比对一致；调度单元测试 12 项通过。

- [只读 CI](https://github.com/fancy0121/13f-intelligence/actions/runs/40067127950)：成功，不构建或发布镜像。
- [连接演练](https://github.com/fancy0121/13f-intelligence/actions/runs/40067309595)：日历测试与实际受限 SSH 均成功；没有刷新 SEC 或切换生产。
- [通知演练](https://github.com/fancy0121/13f-intelligence/actions/runs/40067341834)：按设计故意失败；通知 job 成功创建并指派 [Issue #3](https://github.com/fancy0121/13f-intelligence/issues/3)。已从负责人邮箱独立查到 Issue 创建、指派及 Actions 失败邮件。
- 首次真实 SEC 候选采集失败：`raw_files=312 failures=1`，accession `0001541617-24-000004` 主文档获取失败。单文档复查 HTTP 200；已启动完整重试，结果尚未验收。不能把连接演练通过解释为全链路数据更新通过。
- 服务基线校验和未变，现有看板健康检查 `ok`；无生产换库。Gate2 人工复核仍为 `NOT_REVIEWED`，Gate3 为 `PENDING_REAL_WORLD_VALIDATION`。

调度状态：`SCHEDULE_CONFIGURED_NOT_YET_OBSERVED`。首次定时触发尚未发生；完整真实候选成功尚未确认。此前的 NOT_ACTIVATED 描述是配置前历史状态，不再代表当前配置。
