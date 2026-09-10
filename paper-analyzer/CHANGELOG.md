# Changelog

技能版本记录（倒序）。升级技能时在 frontmatter `version` 与此处同步登记；报告模板 0.6 的"技能版本"行取 frontmatter 值。

## v2.3.0 (2026-09-10)

- 文献检索不依赖宿主：宿主无 WebSearch 工具时改用本机 websearch MCP（`search_papers` 聚合 arXiv/OpenAlex/Crossref/OpenReview + `search_web` 通用兜底）；MCP 聚合结果仍须打开核对后才能写入报告

## v2.2.2 (2026-09-10)

- 修复：Python 环境解析改为**先询问使用人**——探测候选（uv 项目环境/uv 隔离环境/系统 python）后 AskUserQuestion 请使用人选定（推荐 uv 隔离环境，任意目录可用），同会话沿用；不再静默落到系统默认解释器；命令示例与脚本 docstring 同步 uv 形式

## v2.2.1 (2026-09-10)

- 修复：清理 `ocr_output/` 缓存前必须先迁移底稿引用的 `imgs/` 等图片资源进产物目录（保持相对路径、确认链接可达），杜绝底稿插图死链；4.6 明确图片资源同属底稿

## v2.2.0 (2026-09-10)

- 多模态图片分析四级回退：主模型直接看 → `multimodal-vision` 子智能体 → 默认图片解析工具（`analyze_image` / Read 读图）→ caption 降级并标注"未直接核验"；能力不确定时询问使用人
- 补强设计类场景：UI / HCI / 系统论文的界面与交互设计评估；委派示例分方法类 / 设计类
- 图片理解一律按报告推断对待，与 caption、正文引用交叉核对

## v2.1.0 (2026-08-26)

- PaddleOCR 引擎升级 PaddleOCR-VL-1.6，移除 mineru 备选，单引擎化；Token 维持 `PADDLEOCR_TOKEN` 环境变量
- 产物目录规则：分析产物集中 `<论文名>_分析_<日期>/`（报告、底稿、脚本、assets），完整转换底稿必须保留
- 补回三处审稿锚点：2.1 理论基础与学术渊源 / 3.2 实验设置合理性 / 7.1 创新性裁定

## v2.0.0 (2026-08-26)

- 对齐 paper-reading-skill v2：报告结构改为理解顺序（0 三分钟读懂 → 7 最终判断，附录 A-D）
- 论文类型适配（理论 / 方法 / 系统 / 数据集 / 实证 / 综述），废除公式、表格硬配额
- Claim—Evidence—Verdict 总表作为报告主骨架，五级证据强度（新增"被反证"）
- 废除默认 10 分制评分，改为可行动判断 + 最小判别路径；文献检索目标导向、不凑数
- 新增 `references/report-writing-guidelines.md`（深度完整性契约七条）

## v1.0.0 (2026-06-09)

- 初版：双引擎提取（PaddleOCR-VL + mineru 备选）、固定 0-7 章审稿结构、PaddlePaddle 代码实现
