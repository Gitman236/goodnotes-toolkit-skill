# Reusable workflows

## Inspect and extract

`inspect` reports members, schema, event counts, distinct outlines, PDF attachments/bookmarks, page/layer bindings, and note-file associations. Read-only inspection can report unknown event kinds; unsupported mutation layouts are not guessed.

`extract` writes all original members under `raw/`, recognized PDFs under `pdf/`, and decoded stroke blobs under `decoded-strokes/`. Its JSON report includes typed-text objects, recognition candidates, decompression issues, and trailer sizes. Use a new directory. Real extracted content stays outside the published skill.

## Restore native outlines

```sh
python scripts/goodnotes_toolkit.py add-outlines notebook.goodnotes --reference working.goodnotes --output outlined.goodnotes
```

The reference mode locates the last N native outline events in the reference, where N is the current embedded PDF bookmark count. It verifies that this set has unique IDs and exactly matches the current PDF titles, page numbers, and hierarchy. It then copies the proven record shapes while allocating new item/event IDs and mapping target layers/document IDs to the current notebook. Original source events remain an exact byte prefix.

If the reference differs, stop and inspect; do not adapt titles or destinations silently. The source and reference are both local files. Neither is packaged or published.

If a matching working reference is unavailable, omit `--reference`. The helper uses an existing source outline record and the observed creation-state shape. It verifies structure but reports this as inferred synthesis, requiring an app import test. A source without an outline template needs a compatible reference; the script does not manufacture an unobserved schema from nothing.

The source must have one PDF and one unambiguous layer per PDF page. Duplicate/partial existing matching outlines are detected by title, page, and ancestor-title path. A complete match is a no-op. Partial matches stop; removal, restoration of hidden state, or merging requires targeted analysis. More than four levels stops the mutation because deeper nesting has not been validated by this workflow.

## Replace a PDF and prepend contents

```sh
python scripts/goodnotes_toolkit.py replace-pdf notebook.goodnotes with-contents.pdf --prepend 20 --output replaced.goodnotes
python scripts/goodnotes_toolkit.py add-outlines replaced.goodnotes --reference working.goodnotes --output replaced-outlined.goodnotes
```

`--prepend 0` supports replacing with a same-page-count PDF whose content/layout invariants still match, for example added PDF bookmarks without body changes. Positive values support front-added pages only. Nonuniform insertion, deletion, or reordering is outside this executable helper; it needs an explicit old→new mapping and a new tested implementation.

All original pages must match the new PDF at `old_page + prepend`, including decoded content streams, recursive resource-stream checksums, geometry, and rotation. This prevents accidental annotation drift. A cleaner scan or reflowed edition will fail these checks; do not bypass them and describe alignment as proven.

For supported front insertion, preserve original logical attachment IDs and shift their ranges. Add one new attachment range for at most 100 front pages and reference the same PDF member. Create empty notes and page/layer records for added pages; remap each original layer sort key from `4HRndNNN` to its shifted key. The helper limits total pages to 999 because the validated fixed-width sort-key pattern would need additional investigation beyond that.

The preview is preserved (it may still show the original cover); this has no effect on page links. If the user requests preview refresh, render the new first PDF page and replace only `thumbnail.jpg`, verifying it separately.

## Verify and report

Mutation outputs are written via a temporary sibling and moved into place only after verification. Existing destinations are refused. For outlines, every member except `index.events.pb` must hash identically. For replacement, all original note files and handwriting caches must hash identically; only an explicit allowlist of members is changed. Run CRC, member uniqueness, target, hierarchy, attachment-range, source-hash, and original-event checks. Save the structured report beside the new archive.

Application validation is separate. State which format has a user-confirmed import and which output has only structural verification. If a working shape stops being recognized after an app update, compare an app-generated re-export after adding a named manual outline. Do not overwrite notebooks or publish personal notebook content while investigating.
