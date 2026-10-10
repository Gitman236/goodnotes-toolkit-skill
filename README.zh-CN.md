# Goodnotes Toolkit 技能

[English](README.md) | [简体中文](README.zh-CN.md)

一个可复用的 Codex 技能，用于检查和提取 `.goodnotes` 文件、保留可编辑笔记并替换兼容的 PDF 底稿，以及将 PDF 书签转换为 Goodnotes 原生大纲。

它还可以提取输入文字、笔画数据和手写识别候选。它不是完整格式解释器、精确笔画渲染器或准确的手写转录工具。

原生大纲记录格式和四级层次已在一个 schema-35 笔记文件上由使用者确认导入有效。其他文件仍需进行结构核验，并在 Goodnotes 内实际导入检查。详见 [技能说明](SKILL.md)、[格式说明](references/format.md)和[操作流程](references/workflows.md)。

## 安装与使用

克隆本仓库，将技能文件复制到 `~/.codex/skills/goodnotes-toolkit/`（或 `$CODEX_HOME/skills/goodnotes-toolkit/`）。请一起保留 `SKILL.md`、`LICENSE`、`NOTICE.md`、`agents/`、`scripts/` 和 `references/`。如未发现技能，可启动新的 Codex 会话。

```sh
python -m pip install -r requirements.txt
python scripts/goodnotes_toolkit.py --help
python scripts/goodnotes_toolkit.py inspect notebook.goodnotes --report inspect.json
python scripts/goodnotes_toolkit.py add-outlines notebook.goodnotes --reference working.goodnotes --output outlined.goodnotes
python -m unittest discover -s tests -v
```

在 Codex 中调用：`使用 $goodnotes-toolkit，将这份笔记的 PDF 书签转换为原生大纲，并保留我的笔记。`

报告和提取结果可能含有私密笔记文字。本仓库仅包含通用脚本、技术说明和合成测试，不包含教材、PDF、真实手写样本、账户凭据或私密测试文件。

## 许可证与声明

仓库代码和技能文档采用 [MIT License](LICENSE)，著作权声明为 Copyright (c) 2026 Gitman236。第三方依赖和笔记内容仍适用各自的许可证及权利。

完整版权说明、使用范围、技术限制和侵权反馈流程见 [NOTICE.md](NOTICE.md)。该文件仅提供英文版，不修改 MIT License，也不为其添加额外限制。
