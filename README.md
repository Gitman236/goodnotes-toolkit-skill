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
