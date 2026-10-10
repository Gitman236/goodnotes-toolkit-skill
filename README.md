# Goodnotes Toolkit Skill

[English](README.md) | [简体中文](README.zh-CN.md)

A reusable Codex skill for `.goodnotes` archive inspection, local extraction, safe PDF-background replacement, and explicit conversion of PDF bookmarks into editable Goodnotes native outlines.

It can extract typed text, stroke payloads, and handwriting recognition candidates. It is not a complete format interpreter, precise ink renderer, or handwriting transcription engine.

The native-outline event shape and four-level nesting were confirmed working by the user on an observed schema-35 notebook. Other files still require structural checks and an app import test. See [SKILL.md](SKILL.md), [format notes](references/format.md), and [workflows](references/workflows.md).

## Install and use

Clone this repository, then copy its skill files into `~/.codex/skills/goodnotes-toolkit/` (or `$CODEX_HOME/skills/goodnotes-toolkit/`). Keep `SKILL.md`, `LICENSE`, `NOTICE.md`, `agents/`, `scripts/`, and `references/` together. Start a new Codex session if needed for discovery.

```sh
python -m pip install -r requirements.txt
python scripts/goodnotes_toolkit.py --help
python scripts/goodnotes_toolkit.py inspect notebook.goodnotes --report inspect.json
python scripts/goodnotes_toolkit.py add-outlines notebook.goodnotes --reference working.goodnotes --output outlined.goodnotes
python -m unittest discover -s tests -v
```

Invoke in Codex: `Use $goodnotes-toolkit to restore this notebook's PDF bookmarks as native outlines while preserving my notes.`

Reports and extraction outputs may contain private notebook text. This repository contains only generic scripts, documentation, and synthetic tests. No textbook, PDF, handwriting sample, credential, or private fixture is included.

## License and notice

Repository code and associated skill documentation are licensed under the [MIT License](LICENSE). Copyright (c) 2026 Gitman236. Third-party dependencies and notebook contents retain their respective licenses and rights.

This is an independent, unofficial project. Process only files you are authorized to access, use, and modify. Preserve originals and check outputs before relying on them.

See [NOTICE.md](NOTICE.md) for copyright ownership, authorized use, technical limitations, and the takedown reporting procedure. The notice is provided in English and does not modify or add restrictions to the MIT License.
