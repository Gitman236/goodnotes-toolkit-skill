# Goodnotes Toolkit Skill

A reusable Codex skill for `.goodnotes` archive inspection, local extraction, safe PDF-background replacement, and explicit conversion of PDF bookmarks into editable Goodnotes native outlines.

**中文：** 整理自实际解析与导入测试的可复用技能。可保留新增手写笔记、替换兼容的 PDF 底稿、补写原生大纲，并提取手写识别候选。它不是完整格式解释器，也不是准确转录或精确笔画渲染工具。

The native-outline event shape and four-level nesting were confirmed working by the user on an observed schema-35 notebook. Other files still require structural checks and an app import test. See [SKILL.md](SKILL.md), [format notes](references/format.md), and [workflows](references/workflows.md).

## Install and use

Clone this repository, then copy its skill files into `~/.codex/skills/goodnotes-toolkit/` (or `$CODEX_HOME/skills/goodnotes-toolkit/`). Keep `SKILL.md`, `agents/`, `scripts/`, and `references/` together. Start a new Codex session if needed for discovery.

```sh
python -m pip install -r requirements.txt
python scripts/goodnotes_toolkit.py --help
python scripts/goodnotes_toolkit.py inspect notebook.goodnotes --report inspect.json
python scripts/goodnotes_toolkit.py add-outlines notebook.goodnotes --reference working.goodnotes --output outlined.goodnotes
python -m unittest discover -s tests -v
```

Invoke in Codex: `Use $goodnotes-toolkit to restore this notebook's PDF bookmarks as native outlines while preserving my notes.`

Reports and extraction outputs may contain private notebook text. This repository contains only generic scripts, documentation, and synthetic tests. No textbook, PDF, handwriting sample, credential, or private fixture is included.

## Copyright, disclaimer, and takedown requests / 版权声明与侵权处理

本项目为独立、非官方的技术工具，不隶属于 Goodnotes，也未获得其官方背书或认证。Goodnotes 名称、商标及相关产品权利归各自权利人所有；文档、教材、笔记、图片及其他第三方内容的权利同样归其权利人所有。

请仅处理你有权访问、使用和修改的文件。学习研究、个人备份或格式转换的用途不会自动赋予版权许可；请勿使用本工具未经授权传播教材、他人笔记或其他受保护内容，也请勿将私密文件或提取结果上传至本仓库。

**侵权反馈与删除：** 如认为仓库内容侵犯你的权利，请通过 [GitHub Issues](https://github.com/Gitman236/goodnotes-toolkit-skill/issues/new) 提供相关作品说明、被投诉的具体文件或链接，以及权利或授权依据。经核实存在侵权的内容将及时删除、下架或修正。公开 Issue 中请勿上传敏感身份资料或私密原稿；正式版权通知可使用 [GitHub 官方 DMCA 提交通道](https://github.com/contact/dmca)。

工具按现状提供，无法保证兼容所有 Goodnotes 版本、完整解释全部数据或准确识别手写内容。请保留原文件，并检查新文件的导入效果。本声明不构成第三方内容使用授权，也不免除任何依法不能排除的责任。

See [the full bilingual notice / 完整中英文声明](references/copyright.md) for scope, limitations, and the reporting procedure.
