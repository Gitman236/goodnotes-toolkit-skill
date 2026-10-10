---
name: goodnotes-toolkit
description: Inspect and extract .goodnotes archives, preserve editable notes while replacing a compatible PDF background, and convert embedded PDF bookmarks to Goodnotes native outlines. Use for Goodnotes file parsing, repacking, missing outlines, and handwriting recognition-cache inspection; this is not a complete renderer or handwriting OCR engine.
license: MIT
---

# Goodnotes Toolkit

Use `scripts/goodnotes_toolkit.py` for the observed schema-35 archive profile. The skill distinguishes decoded structure, verbatim preservation, inferred field semantics, and actual Goodnotes import validation. A readable ZIP or intact PDF outline does not prove the app will show a native outline.

## Choose the operation

- Inspect: `python scripts/goodnotes_toolkit.py inspect INPUT.goodnotes --report inspect.json`
- Extract PDF, original layer data, typed text, and handwriting candidates: `python scripts/goodnotes_toolkit.py extract INPUT.goodnotes --out-dir extracted`
- Add native outlines from the embedded PDF: `python scripts/goodnotes_toolkit.py add-outlines INPUT.goodnotes --output outlined.goodnotes --reference KNOWN_WORKING.goodnotes`
- Replace a background with an otherwise identical PDF, optionally with front contents pages: `python scripts/goodnotes_toolkit.py replace-pdf INPUT.goodnotes NEW.pdf --prepend 20 --output replaced.goodnotes`

Run `--help` for options. Python 3.10+ and `pypdf` are required; inspect/extract do not render a PDF. Locate a usable interpreter and install the dependency only if needed. Paths are arguments, never hardcoded to one computer, title, or page count.

## Invariants that matter

1. Read the input before choosing a mutation. Keep the source immutable; use a new output path. The helper rejects duplicate ZIP members, encrypted entries, unsafe extraction paths, and unsupported mutation profiles.
2. For outline repair, use **the current document's** page/layer/document IDs. Goodnotes export/import can remap all of them. A working reference supplies record shape and hierarchy, not destination IDs.
3. Preserve all original events, annotation files, and unknown objects during outline additions. The helper appends only native outline events and verifies every other member byte-for-byte.
4. PDF replacement supports a single embedded PDF with unambiguous contiguous page/layer mappings. It verifies content streams, resource streams, page dimensions, and rotation, then adjusts PDF page references, attachment ranges, layer order, and attachment search-cache page numbers. Added front pages receive their own empty note records. It does not migrate annotations across changed layout.
5. If replacement introduces PDF bookmarks, run `add-outlines` on the replacement result. Replacing a PDF attachment does not execute Goodnotes' normal PDF-import outline conversion.
6. Reports may contain titles, typed notes, or recognition text. Keep them local unless the user explicitly requests sharing. Do not include user notebooks, textbooks, extracted PDFs, credentials, or real-note fixtures when publishing this skill.

Respect third-party copyright and the user's authority to process the supplied files. If the task concerns publication, redistribution, or a rights complaint, read [NOTICE.md](NOTICE.md). The notice does not grant rights to notebook contents or promise immunity from liability; it does not add a routine permission question to ordinary authorized local processing.

## Outline repair

Read [references/workflows.md](references/workflows.md) for native-outline synthesis and reference-transfer modes. A provided working reference must match the input PDF bookmark titles, destinations, and hierarchy; mismatches stop the helper. Without a reference, the helper can synthesize the same observed record shape from an existing source outline record, but application compatibility is unverified. Never label this mode as proven on an unseen file.

Check the resulting report for title count, page targets, parent references, preserved-member checksums, and source immutability. Existing complete matching native outlines cause a no-op; partial matches stop to avoid duplicates. Hidden/deleted/updated existing entries require a targeted analysis of event state, not blindly resetting unknown booleans.

After delivering a new notebook, state whether it has been imported into Goodnotes. The original outline-transfer format was confirmed working by the user, including four levels; that is evidence for this profile, not all Goodnotes versions. If the app still hides outlines, request a re-export after the user manually adds one named test outline and compare the exported events. Avoid repeated speculative repacks.

## Handwriting and scope

Read [references/format.md](references/format.md) when interpreting protobuf fields, compression, or note/search objects. Extraction emits original bytes and structured candidates; it does not claim final visible-object reconstruction. Stroke records can include historical operations. Counts of records are not counts of currently visible strokes.

Handwriting recognition caches include alternative spellings, blank strings, line breaks, symbols, and errors. Do not concatenate the first candidate and present it as an accurate transcript. For actual transcription, render the notebook with the editable notes visible (prefer an app export), visually read it, and check amounts, debit/credit direction, equations, and arrows against the page. Do not invent an accuracy percentage without a visual ground-truth comparison.

For audio, stickers, unusual images, transforms, or unknown schema versions, inspect and preserve bytes, report the unverified area, and extend only after obtaining evidence. Do not advertise full-format support.
