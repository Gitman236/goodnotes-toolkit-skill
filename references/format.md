# Observed archive profile

This is a reverse-engineered profile, not an official Goodnotes schema. Structural parsing and byte preservation are established; some semantic names remain inferred. Mutations are restricted to `schema.pb` with protobuf field 1 = 35. That number is a schema marker, not an app-version number.

## Members

| Member | Observation |
| --- | --- |
| `attachments/<UUID>` | May contain a complete `%PDF-` payload; several logical attachment IDs can reference one member. Other attachment types must be preserved. |
| `index.attachments.pb` | Framed mappings: field 1 logical attachment ID, field 2 member path. |
| `index.events.pb` | Length-delimited protobuf event records. Unknown event types survive mutations. |
| `index.notes.pb` | Framed mappings: field 1 note ID, field 2 `notes/` path. |
| `notes/<UUID>` | Empty pages may have zero-byte files. Nonempty files contain framed messages and object payloads. |
| `index.search.pb`, `search/<UUID>` | Page recognition caches and attachment search caches have different shapes. |
| `thumbnail.jpg` | Preview; it is not a rendered representation of all notes. |
| `document.info.pb` | Was empty in observed files; do not infer that it is always empty. |

Protobuf wire types 0, 1, 2, and 5 are parsed. Unknown numeric fields are retained. Groups are rejected rather than discarded. Original field bytes and event frame prefixes survive when untouched.

## Events used by mutations

Outer field 1 identifies the event's target. The following second outer field selects the observed event kind:

| Kind | Inner fields used |
| --- | --- |
| 30 | Document ID in field 1. |
| 2 | Document ID 1; page ID 2; logical attachment ID 4; **1-based global PDF page** 5; display size 8 (float fields 1, 2). |
| 54 | Document ID 1; layer ID 2; page ID nested at 3 → 1; sort string nested at 4 → 1. Observed strings `4HRnd001` … `4HRnd388`. |
| 6 | Attachment ID 1; binary-member UUID 2; byte size 5; document ID 6; range 12 with start 1 and count 2. Several ranges share the PDF bytes. |
| 65 | Native outline target-layer ID 1; item ID 2; title register 5 → 1; parent-item register 6 → 1, absent for roots; document ID 17. |
| 104 | Note-metadata ID 2. Used only for new blank pages, cloned from a compatible existing record. |

Outline records include state registers in 3/4, double clock in 10, event UUID in 11, integer actor metadata in 13, timestamp in 14, a register in 15, and an observed format value 26 in 16. Preserve state-register shape from the working reference. In fallback synthesis use the original creation shape with no value in registers 3/4. Their later boolean values have not been semantically established. Do not call them deleted/collapsed flags as a fact.

Registers are usually protobuf field 1 (value, optional) and field 2 (revision submessage). A revision uses integer fields 1 and 2. Replacing only the value keeps the existing revision bytes; new synthesized registers get a revision counter and random integer as in the tested pattern.

Original outline event history can contain repeated item IDs. For example, 164 events represented 134 unique item IDs in one notebook. Count and analyze unique items separately from history. A latest-by-file-order map is useful for the observed export profile; it is not a universal CRDT merge algorithm.

## Notes and compression

An observed note-file ID is the associated layer UUID with its **last byte incremented modulo 256 without carry**. One `...FF` layer became a `...00` note ID. This is a sample-derived association, not a universal UUID rule. The helper tests whether the ID exists in the actual note index; it does not force this association during read-only extraction.

In `notes/` frames, outer field 7 contained stroke objects; nested field 2 contained Apple framed LZ4. The decoded payload starts `tpl\0` (TPL serialization). The helper decompresses it and preserves `.tpl` bytes, but does not decode all pressure, width, transform, eraser, or rendering semantics.

Apple frame markers: `bv41` = compressed block with little-endian decoded/compressed sizes; `bv4-` = raw block; `bv4$` = terminator. The decoder retains a 64 KiB history for blocks and bounds output growth. Any bytes after the terminator are reported as trailer bytes rather than silently interpreted as part of the TPL payload.

An observed typed-text object used outer field 21, with compressed data nested below field 32; the decoded protobuf contained a text value at 1 → 1. This was successfully read as UTF-8. Other text encodings remain unverified.

Page `search/` data used field 5 for the layer ID, repeated field 6 for recognition groups, and group field 3 for text candidates. Groups have positional data as well; the helper preserves the original cache and extracts candidates without inventing reading order.

Attachment `search/` data instead contained framed protobuf records with field 2 = global PDF page number. Its text fields may be empty. Replacement shifts these page numbers only after validating that shape.

## Evidence and limits

The first replacement notebook had 368 body pages plus 20 inserted contents pages, with hand ink reported intact by the user. Explicitly writing the 837 PDF bookmarks as native outline events was then reported working. A re-exported notebook changed document/page/layer UUIDs; transfer remapped all references onto that notebook, preserving 22 nonempty note files.

Inspection of that sample decompressed 1,977 stroke records and read 395 recognition groups spanning 21 PDF pages. These counts are observations, not constants or accuracy measurements. There was no visual transcription ground truth. No sample notebooks or their text are bundled in this repository.
