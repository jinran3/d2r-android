# Agent 开发规则

本文件是本仓库所有自动化 Agent 的硬性入口。它与 `docs/HANDOFF.zh-CN.md` 配合使用。

## 必须遵守

1. 开工前先读 `docs/HANDOFF.zh-CN.md` 的 frontmatter、`## 当前快照` 和 `## 下一步唯一动作`。
2. `HANDOFF` 是上下文压缩、模型切换、会话重启后的唯一权威续跑入口；聊天摘要不是权威来源。
3. 每完成一个原子任务、修复真实 bug、完成提交/推送、遇到阻塞、准备切换分支或会话时，必须更新 HANDOFF 当前快照，并向 `docs/HANDOFF_LOG.zh-CN.md` 顶部追加日志。
4. 上下文达到 60% 时开始准备交接；达到 75% 时停止扩展范围；达到 85% 或收到压缩通知时冻结代码修改，只做交接、验证和提交。
5. 压缩发生后，第一个工具动作必须是读取 `docs/HANDOFF.zh-CN.md`，第二个动作必须运行 `python tools/agent_handoff_check.py --resume` 并核对 Git 状态；不得直接沿用压缩摘要继续写代码。
6. 新会话必须先运行 `python tools/agent_handoff_check.py --verify`；分支、HEAD、代码工作区或远端不一致时，先修正 HANDOFF，不写业务代码。
7. `## 下一步唯一动作` 只能有一个 READY 动作，必须包含工作目录、命令或编辑目标、成功判据、失败判据、回滚点和证据。
8. 所有“已完成/已验证”结论必须带命令、退出码或产物证据；没跑就写 `NOT RUN`，不能猜测。
9. 超过 5 分钟或高风险操作必须在 HANDOFF_LOG 写 `[BEGIN]`/`[END]`；只有 BEGIN 没有 END 时先检查进程、日志和产物，不能直接重跑。
10. 不提交游戏内容、密钥、存档或构建产物；不回显 `prod.keys`；不把 D2R 数据当作 TotK 数据。
11. **上游有更新要同步，并判断对本项目是否有用**：上游 `jhaizhou-ops/d2r-mobile`（iOS/macOS 原版）与本 fork 的共同祖先是 `sydeEvans/d2r-android`；上游的新提交 / issue 要定期看（`gh` 一律带 `--repo jinran3/d2r-android`，查上游用 `--repo jhaizhou-ops/d2r-mobile`）。同步时只取**对本项目有用**的部分（本 fork 已有 Android 宿主改造与裁剪批次，不要整文件覆盖），并把「这条上游改动对本项目有没有用、为什么」的结论写进 `docs/HANDOFF_LOG.zh-CN.md`。
12. 交接控制面应单独提交并推送；无法提交/推送时，必须在 HANDOFF 中明确标注 `COMMIT: NOT DONE` / `PUSH: NOT DONE` 和恢复命令。
13. 不使用 `git reset --hard`、强制推送或删除未提交改动来“清理”交接状态。

## 新会话恢复顺序

1. 读本文件。
2. 读 `docs/HANDOFF.zh-CN.md`。
3. 运行 `python tools/agent_handoff_check.py --resume`。
4. 运行 `python tools/agent_handoff_check.py --verify`。
5. 检查 `docs/HANDOFF_LOG.zh-CN.md` 是否有未闭合的 `[BEGIN]`。
6. 只执行 `## 下一步唯一动作`，完成后立即更新快照和日志。

## 交接失败保底

无法完成完整交接时，至少更新 HANDOFF frontmatter，并在当前快照写清：

```text
BRANCH:
HEAD:
STATUS:
NEXT:
BLOCKER:
```

然后立即停止新的代码修改。