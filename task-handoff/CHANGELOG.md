# Changelog

技能版本记录（倒序）。升级时同步 frontmatter `version` 与本文。

## v1.0.0 (2026-10-17)

- 首个版本：跨工程 / 项目 / agent / 工具 / session 的单文件交接契约
- 记录位置定为 `<工作根>/.handoff/<task>.md`，随仓库走、覆盖写、§9 追加交接链
- 九节契约：目标与验收、当前状态、在途产物、锁定决策、已否决路径、环境与重建、授权与风险、下一步、交接链
- 四条硬规则：零虚构、verbatim 优先（路径 + sha + 行号，磁盘上没有的整段粘贴）、已完成必须带验证、凭据只写位置
- 四种边界：context-exhaustion / tool-switch / agent-handoff / migration，各自的额外要求与检查清单
- `scripts/handoff.py`：`new` 脚手架（自动取 branch / head）、`check` 校验（结构、占位符、路径可达性、`[x]` 证据）、`list` 检索
