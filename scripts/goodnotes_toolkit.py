#!/usr/bin/env python3
"""Observed-profile Goodnotes tools. No dependency on user files or machine paths."""
from __future__ import annotations

import argparse
import collections
import copy
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import shutil
import struct
import sys
import tempfile
import uuid
import zipfile


class FormatError(ValueError):
    """Input is outside the supported observed profile."""


def require(condition, message):
    if not condition:
        raise FormatError(message)


def varint(data, pos=0):
    value = 0
    for shift in range(0, 70, 7):
        require(pos < len(data), "Truncated varint")
        byte = data[pos]
        pos += 1
        if shift == 63:
            require(byte <= 1, "Varint exceeds 64 bits")
        value |= (byte & 127) << shift
        if byte < 128:
            return value, pos
    raise FormatError("Varint exceeds 64 bits")


def vi(value):
    require(isinstance(value, int) and 0 <= value < 2**64, "Invalid unsigned integer")
    out = bytearray()
    while value > 127:
        out.append((value & 127) | 128)
        value >>= 7
    out.append(value)
    return bytes(out)


def spans(data):
    """Return field/value/raw-span tuples; preserve unknown fields byte-for-byte."""
    pos = 0
    result = []
    while pos < len(data):
        start = pos
        key, pos = varint(data, pos)
        field, wire = key >> 3, key & 7
        require(0 < field < 2**29, "Invalid protobuf field number")
        if wire == 0:
            value, pos = varint(data, pos)
        elif wire == 2:
            size, pos = varint(data, pos)
            require(size <= len(data) - pos, "Truncated length-delimited field")
            value = data[pos:pos + size]
            pos += size
        elif wire in (1, 5):
            size = 8 if wire == 1 else 4
            require(size <= len(data) - pos, "Truncated fixed-width field")
            value = data[pos:pos + size]
            pos += size
        else:
            raise FormatError(f"Unsupported protobuf wire type {wire}")
        result.append((field, wire, value, data[start:pos]))
    return result


def fields(data):
    return [(f, w, v) for f, w, v, raw in spans(data)]


def get(data, field, default=None):
    return next((v for f, w, v in fields(data) if f == field), default)


def encode(fs):
    out = bytearray()
    for field, wire, value in fs:
        out += vi(field * 8 + wire)
        out += vi(value) if wire == 0 else vi(len(value)) + value if wire == 2 else value
    return bytes(out)


def put(data, field, value):
    parsed = spans(data)
    require(sum(f == field for f, w, v, raw in parsed) == 1, f"Expected one field {field}")
    return b"".join(encode([(f, w, value)]) if f == field else raw for f, w, v, raw in parsed)


def putpath(data, path, value):
    return put(data, path[0], value if len(path) == 1 else putpath(get(data, path[0]), path[1:], value))


def split_frames(data):
    pos = 0
    result = []
    while pos < len(data):
        start = pos
        size, pos = varint(data, pos)
        require(size <= len(data) - pos, "Truncated message frame")
        end = pos + size
        result.append((data[pos:end], data[start:end]))
        pos = end
    return result


def frames(data):
    return [b for b, raw in split_frames(data)]


def framed(messages):
    return b"".join(vi(len(b)) + b for b in messages)


def kind(record):
    fs = fields(record)
    require(len(fs) == 2 and fs[0][:2] == (1, 2) and fs[1][1] == 2, "Unexpected event envelope")
    return fs[1][0]


def body(record):
    kind(record)
    return fields(record)[1][2]


def uid():
    return str(uuid.uuid4()).upper().encode("ascii")


def digest_file(path):
    with Path(path).open("rb") as stream:
        return digest_stream(stream)


def digest_stream(stream):
    h = hashlib.sha256()
    for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
        h.update(chunk)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    require(not path.exists(), f"Report already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)


def open_archive(path):
    archive = zipfile.ZipFile(path)
    try:
        names = archive.namelist()
        require(len(names) == len(set(names)), "Duplicate ZIP member names")
        for info in archive.infolist():
            name = info.filename
            p = PurePosixPath(name)
            require(not p.is_absolute() and ".." not in p.parts and "\\" not in name and ":" not in name,
                    f"Unsafe archive member: {name}")
            require(not info.flag_bits & 1, "Encrypted ZIP entries are unsupported")
            require((info.external_attr >> 16) & 0o170000 != 0o120000, "Symlink ZIP entries are unsupported")
        return archive
    except Exception:
        archive.close()
        raise


def events_of(archive):
    return frames(archive.read("index.events.pb"))


def mutation_profile(archive):
    require(get(archive.read("schema.pb"), 1) == 35, "Mutation requires observed schema 35")


def pdf_attachment(archive):
    found = []
    for info in archive.infolist():
        if info.filename.startswith("attachments/") and not info.is_dir():
            with archive.open(info) as stream:
                if stream.read(5) == b"%PDF-":
                    found.append(info.filename)
    require(len(found) == 1, "This operation requires exactly one embedded PDF")
    return found[0]


def pdf_reader(data):
    from pypdf import PdfReader
    return PdfReader(io.BytesIO(data))


def bookmarks(pdf):
    result = []

    def visit(items, depth=0):
        for item in items:
            if isinstance(item, list):
                visit(item, depth + 1)
            else:
                page = pdf.get_destination_page_number(item)
                require(page is not None and 0 <= page < len(pdf.pages), "Unresolved PDF bookmark destination")
                result.append({"title": item.title, "pdf_page": page + 1, "depth": depth})
    visit(pdf.outline)
    return result


def mapping(events, page_count=None):
    pages = {get(body(b), 2): body(b) for b in events if kind(b) == 2}
    layers = {get(body(b), 2): body(b) for b in events if kind(b) == 54}
    layer_to_page = {}
    page_to_layer = {}
    for lid, layer in layers.items():
        pid = get(get(layer, 3), 1)
        require(pid in pages, "Layer points to an unknown page")
        page = get(pages[pid], 5)
        require(isinstance(page, int) and page > 0, "Unexpected PDF page reference")
        require(page not in page_to_layer, "Ambiguous layers/pages; inspect state manually")
        layer_to_page[lid] = page
        page_to_layer[page] = lid
    if page_count is not None:
        require(sorted(page_to_layer) == list(range(1, page_count + 1)), "Notebook/PDF page mapping is incomplete")
        require(len(pages) == len(layers) == page_count, "Unexpected page/layer state")
    return pages, layers, layer_to_page, page_to_layer


def lz4_block(data, history=b"", limit=64 * 1024 * 1024):
    out = bytearray(history[-65536:])
    base = len(out)
    pos = 0

    def extended(value):
        nonlocal pos
        if value != 15:
            return value
        while True:
            require(pos < len(data), "Truncated LZ4 length")
            byte = data[pos]
            pos += 1
            value += byte
            if byte != 255:
                return value
    while pos < len(data):
        token = data[pos]
        pos += 1
        count = extended(token >> 4)
        require(count <= len(data) - pos, "Truncated LZ4 literals")
        require(len(out) - base + count <= limit, "LZ4 output limit exceeded")
        out += data[pos:pos + count]
        pos += count
        if pos == len(data):
            break
        require(pos + 2 <= len(data), "Truncated LZ4 match offset")
        offset = int.from_bytes(data[pos:pos + 2], "little")
        pos += 2
        require(0 < offset <= len(out), "Invalid LZ4 match offset")
        count = extended(token & 15) + 4
        require(len(out) - base + count <= limit, "LZ4 output limit exceeded")
        for _ in range(count):
            out.append(out[-offset])
    return bytes(out[base:])


def unpack_apple(data, limit=64 * 1024 * 1024):
    pos = 0
    out = bytearray()
    while True:
        require(pos + 4 <= len(data), "Missing Apple LZ4 terminator")
        magic = data[pos:pos + 4]
        pos += 4
        if magic == b"bv4$":
            return bytes(out), len(data) - pos
        if magic == b"bv41":
            require(pos + 8 <= len(data), "Truncated Apple LZ4 header")
            raw, compressed = struct.unpack_from("<II", data, pos)
            pos += 8
            require(raw <= limit - len(out) and compressed <= len(data) - pos, "Invalid Apple LZ4 sizes")
            block = lz4_block(data[pos:pos + compressed], bytes(out[-65536:]), raw)
            require(len(block) == raw, "Apple LZ4 decoded size mismatch")
            out += block
            pos += compressed
        elif magic == b"bv4-":
            require(pos + 4 <= len(data), "Truncated Apple raw-block header")
            raw = struct.unpack_from("<I", data, pos)[0]
            pos += 4
            require(raw <= limit - len(out) and raw <= len(data) - pos, "Invalid Apple raw-block size")
            out += data[pos:pos + raw]
            pos += raw
        else:
            raise FormatError(f"Unknown Apple frame marker {magic!r}")


def compressed_leaves(data, depth=0):
    if depth > 20:
        return
    if data.startswith((b"bv41", b"bv4-")):
        yield unpack_apple(data)
        return
    try:
        parsed = fields(data)
    except FormatError:
        return
    for f, w, v in parsed:
        if w == 2:
            yield from compressed_leaves(v, depth + 1)


def inspect(archive):
    es = events_of(archive)
    counts = collections.Counter(kind(b) for b in es)
    notes = [i for i in archive.infolist() if i.filename.startswith("notes/") and not i.is_dir()]
    result = {"schema_fields": fields(archive.read("schema.pb")), "members": len(archive.namelist()),
              "event_counts": dict(counts), "outline_event_count": counts[65],
              "outline_distinct_ids": len({get(body(b), 2) for b in es if kind(b) == 65}),
              "note_files": len(notes), "nonempty_note_files": sum(i.file_size > 0 for i in notes),
              "complete_format_support": False, "goodnotes_import_tested": False}
    try:
        member = pdf_attachment(archive)
        pdf = pdf_reader(archive.read(member))
        result.update(pdf_member=member, pdf_pages=len(pdf.pages), pdf_bookmarks=len(bookmarks(pdf)))
        _, _, l2p, p2l = mapping(es, len(pdf.pages))
        result["page_mapping_verified"] = True
        note_index = {get(b, 1): get(b, 2).decode("utf-8") for b in frames(archive.read("index.notes.pb"))}
        bindings = []
        for page, lid in sorted(p2l.items()):
            n = uuid.UUID(lid.decode()).int
            nid = str(uuid.UUID(int=(n & ~255) | ((n + 1) & 255))).upper().encode()
            bindings.append({"pdf_page": page, "layer_id": lid.decode(), "notes_member": note_index.get(nid),
                             "association": "observed-last-byte-rule" if nid in note_index else "unresolved"})
        result["page_note_bindings"] = bindings
    except (FormatError, KeyError, ValueError) as exc:
        result["mapping_issue"] = str(exc)
    return result


def extract(archive, directory):
    root = Path(directory)
    require(not root.exists(), "Extraction requires a new output directory")
    root.mkdir(parents=True)
    for info in archive.infolist():
        target = root / "raw" / info.filename
        if info.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as src, target.open("xb") as dst:
                shutil.copyfileobj(src, dst)
            if info.filename.startswith("attachments/"):
                with target.open("rb") as stream:
                    is_pdf = stream.read(5) == b"%PDF-"
                if is_pdf:
                    destination = root / "pdf" / (Path(info.filename).name + ".pdf")
                    destination.parent.mkdir(exist_ok=True)
                    shutil.copyfile(target, destination)
    result = inspect(archive)
    typed, candidates, failures, strokes, trailers = [], [], [], 0, 0
    _, _, l2p, _ = mapping(events_of(archive))
    bindings = {row["notes_member"]: row["pdf_page"] for row in result.get("page_note_bindings", []) if row["notes_member"]}
    for info in archive.infolist():
        if info.filename.startswith("notes/") and info.file_size:
            try:
                for index, msg in enumerate(frames(archive.read(info))):
                    for f, w, v in fields(msg):
                        if f == 7 and w == 2:
                            raw, trailer = unpack_apple(get(v, 2))
                            require(raw.startswith(b"tpl\0"), "Decoded stroke does not have a TPL header")
                            target = root / "decoded-strokes" / Path(info.filename).name / f"{index:06d}.tpl"
                            target.parent.mkdir(parents=True, exist_ok=True)
                            target.write_bytes(raw)
                            strokes += 1
                            trailers += trailer
                        elif f == 21 and w == 2:
                            for raw, trailer in compressed_leaves(v):
                                text = get(get(raw, 1, b""), 1)
                                if isinstance(text, bytes):
                                    typed.append({"member": info.filename, "pdf_page": bindings.get(info.filename),
                                                  "text": text.decode("utf-8"), "trailer_bytes": trailer})
            except (FormatError, KeyError, TypeError, UnicodeError) as exc:
                failures.append({"member": info.filename, "issue": str(exc)})
        elif info.filename.startswith("search/") and not info.is_dir():
            try:
                data = archive.read(info)
                parsed = fields(data)
                page = l2p.get(get(data, 5))
                for f, w, v in parsed:
                    if f == 6 and w == 2:
                        alts = [x.decode("utf-8") for k, t, x in fields(v) if k == 3 and t == 2]
                        if alts:
                            candidates.append({"member": info.filename, "pdf_page": page, "candidates": alts})
            except (FormatError, UnicodeError):
                pass  # Attachment search data has a different framed shape; original bytes are preserved.
    result.update(decoded_stroke_records=strokes, stroke_trailer_bytes=trailers, typed_text_objects=typed,
                  recognition_candidates=candidates, extraction_issues=failures,
                  accurate_transcription=False, final_visible_state_reconstructed=False)
    write_json(root / "extraction.json", result)
    return result


def native_signature(payload, latest, l2p, seen=None):
    seen = set() if seen is None else set(seen)
    oid = get(payload, 2)
    require(oid not in seen, "Native outline parent cycle")
    seen.add(oid)
    title = get(get(payload, 5), 1, b"").decode("utf-8")
    parent = get(get(payload, 6), 1, b"")
    ancestors = ()
    if parent:
        require(parent in latest, "Unknown native outline parent")
        parent_sig = native_signature(latest[parent], latest, l2p, seen)
        ancestors = parent_sig[2] + (parent_sig[0],)
    layer = get(payload, 1)
    require(layer in l2p, "Unknown native outline destination")
    return title, l2p[layer], ancestors


def bookmark_signatures(items):
    result, stack = [], {}
    for item in items:
        depth = item["depth"]
        require(depth == 0 or depth - 1 in stack, "Invalid PDF outline hierarchy")
        ancestors = tuple(stack[i] for i in range(depth))
        result.append((item["title"], item["pdf_page"], ancestors))
        stack[depth] = item["title"]
        for level in list(stack):
            if level > depth:
                del stack[level]
    return result


def register(value=None):
    revision = encode([(1, 0, 1), (2, 0, uuid.uuid4().int & 0xffffffff)])
    return encode(([(1, 2, value)] if value is not None else []) + [(2, 2, revision)])


def add_outline_data(archive, reference=None):
    mutation_profile(archive)
    es = events_of(archive)
    pdf = pdf_reader(archive.read(pdf_attachment(archive)))
    items = bookmarks(pdf)
    require(items, "Embedded PDF has no bookmarks")
    require(max(x["depth"] for x in items) <= 3, "More than four outline levels are unverified")
    _, _, l2p, p2l = mapping(es, len(pdf.pages))
    doc = get(body(next(b for b in es if kind(b) == 30)), 1)
    current = [body(b) for b in es if kind(b) == 65]
    latest = {get(p, 2): p for p in current}
    known = {native_signature(p, latest, l2p) for p in latest.values()}
    wanted = bookmark_signatures(items)
    overlap = known & set(wanted)
    if set(wanted) <= known:
        return None, {"status": "already-present", "pdf_bookmarks": len(items), "app_visibility_verified": False}
    require(not overlap, "Partial existing native matches; inspect state/merging rather than adding duplicates")
    mode = "inferred-synthesis"
    templates = None
    if reference:
        mutation_profile(reference)
        ref_es = events_of(reference)
        _, _, ref_l2p, _ = mapping(ref_es)
        templates = [body(b) for b in ref_es if kind(b) == 65][-len(items):]
        require(len(templates) == len(items), "Reference has too few native records")
        ref_latest = {get(p, 2): p for p in templates}
        require(len(ref_latest) == len(items), "Reference suffix contains updates/duplicate IDs")
        require([native_signature(p, ref_latest, ref_l2p) for p in templates] == wanted,
                "Reference titles/destinations/hierarchy do not match current PDF")
        mode = "reference-shape-transfer"
    else:
        require(current, "No native template; supply a matching working reference")
    max_ms = max((get(p, 14, 0) for p in current), default=0)
    max_clock = max((struct.unpack("<d", get(p, 10))[0] for p in current), default=0)
    require(math.isfinite(max_clock), "Invalid outline event clock")
    appended, manifest, stack = [], [], {}
    for index, item in enumerate(items):
        layer = p2l[item["pdf_page"]]
        node = uid()
        require(node not in latest, "UUID collision")
        parent = stack.get(item["depth"] - 1, b"") if item["depth"] else b""
        p = templates[index] if templates is not None else current[0]
        for field, value in [(1, layer), (2, node), (17, doc), (11, uid()),
                             (10, struct.pack("<d", max_clock + index + 1)), (14, max_ms + index + 1)]:
            p = put(p, field, value)
        if templates is not None:
            if parent:
                p = putpath(p, [6, 1], parent)
        else:
            p = put(p, 3, register())
            p = put(p, 4, register())
            p = put(p, 5, register(item["title"].encode("utf-8")))
            p = put(p, 6, register(parent if parent else None))
            p = put(p, 15, register(get(get(p, 15), 1, b"")))
        appended.append(encode([(1, 2, layer), (65, 2, p)]))
        stack[item["depth"]] = node
        for level in list(stack):
            if level > item["depth"]:
                del stack[level]
        manifest.append(dict(item, id=node.decode(), parent_id=parent.decode(), layer_id=layer.decode()))
    new_latest = {get(body(b), 2): body(b) for b in appended}
    require([native_signature(body(b), new_latest, l2p) for b in appended] == wanted, "Native verification failed")
    result = archive.read("index.events.pb") + framed(appended)
    return result, {"status": "written", "mode": mode, "pdf_bookmarks": len(items),
                    "native_entries_added": len(appended), "original_events_preserved": len(es),
                    "entries": manifest, "goodnotes_import_of_this_output_tested": False}


def resource_hashes(page):
    result, seen = [], set()

    def visit(obj, path):
        if hasattr(obj, "idnum"):
            key = obj.idnum, obj.generation
            if key in seen:
                return
            seen.add(key)
            obj = obj.get_object()
        if hasattr(obj, "get_data"):
            result.append((path, hashlib.sha256(obj.get_data()).hexdigest()))
        if isinstance(obj, dict):
            for k in sorted(obj):
                if k not in ("/Parent", "/P"):
                    visit(obj.raw_get(k), path + "/" + str(k))
        elif isinstance(obj, list):
            for i, value in enumerate(obj):
                visit(value, path + "/" + str(i))
    visit(page.get("/Resources", {}), "resources")
    return result


def check_pdf_body(old_pdf, new_pdf, prepend):
    require(0 <= prepend <= 100, "Prepend must be between 0 and 100")
    require(len(new_pdf.pages) == len(old_pdf.pages) + prepend, "New PDF page count differs from requested mapping")
    for index, old in enumerate(old_pdf.pages):
        new = new_pdf.pages[index + prepend]
        for key in ("mediabox", "cropbox", "rotation"):
            require(getattr(old, key) == getattr(new, key), f"Body page {index + 1}: {key} changed")
        a, b = old.get_contents(), new.get_contents()
        require((a.get_data() if a else b"") == (b.get_data() if b else b""), f"Body page {index + 1}: content changed")
        require(resource_hashes(old) == resource_hashes(new), f"Body page {index + 1}: resources changed")


def note_id(layer):
    value = uuid.UUID(layer.decode()).int
    return str(uuid.UUID(int=(value & ~255) | ((value + 1) & 255))).upper().encode()


def replace_pdf_data(archive, pdf_data, prepend):
    mutation_profile(archive)
    member = pdf_attachment(archive)
    old_pdf, new_pdf = pdf_reader(archive.read(member)), pdf_reader(pdf_data)
    check_pdf_body(old_pdf, new_pdf, prepend)
    es = events_of(archive)
    pages, layers, _, p2l = mapping(es, len(old_pdf.pages))
    require(sum(kind(b) == 2 for b in es) == len(pages) and sum(kind(b) == 54 for b in es) == len(layers),
            "Page/layer history requires manual resolution")
    attachments = {get(body(b), 1): body(b) for b in es if kind(b) == 6}
    require(sum(kind(b) == 6 for b in es) == len(attachments), "Attachment history requires manual resolution")
    indexed = frames(archive.read("index.attachments.pb"))
    require(set(get(b, 1) for b in indexed) == set(attachments), "Attachment index/event mismatch")
    require(all(get(b, 2).decode() == member for b in indexed), "Non-PDF attachments need manual handling")
    coverage = []
    for p in attachments.values():
        require(get(p, 5) == len(archive.read(member)), "Stale PDF attachment size")
        start, count = get(get(p, 12), 1), get(get(p, 12), 2)
        require(isinstance(start, int) and isinstance(count, int) and 0 < count <= 100, "Unexpected attachment range")
        coverage.extend(range(start, start + count))
    require(sorted(coverage) == list(range(1, len(old_pdf.pages) + 1)), "Attachment ranges overlap or have gaps")
    for p in pages.values():
        aid = get(p, 4)
        require(aid in attachments, "Unknown page attachment")
        a = attachments[aid]
        start, count = get(get(a, 12), 1), get(get(a, 12), 2)
        require(start <= get(p, 5) < start + count, "Page outside attachment range")
    replacements = {member: pdf_data}
    additions = {}
    new_pages, new_layers, new_notes, new_index = [], [], [], []
    new_attachment = None
    if prepend:
        require(len(new_pdf.pages) <= 999, "Fixed-width layer ordering above 999 pages is unverified")
        for lid, p in layers.items():
            old_page = next(page for page, layer in p2l.items() if layer == lid)
            require(get(get(p, 4), 1) == f"4HRnd{old_page:03d}".encode(), "Unrecognized layer sort-key profile")
        templates = {}
        for k in (2, 6, 54, 104):
            matches = [body(b) for b in es if kind(b) == k]
            require(matches, f"Missing template event {k}")
            templates[k] = matches[0]
        aid = uid()
        new_attachment = put(put(put(templates[6], 1, aid), 5, len(pdf_data)), 11, uid())
        new_attachment = putpath(putpath(new_attachment, [12, 1], 1), [12, 2], prepend)
        replacements["index.attachments.pb"] = framed([encode([(1, 2, aid), (2, 2, member.encode())])]) + archive.read("index.attachments.pb")
        size = get(templates[2], 8)
        scale = struct.unpack("<f", get(size, 1))[0] / float(old_pdf.pages[0].mediabox.width)
        existing_note_paths = set(archive.namelist())
        for i in range(1, prepend + 1):
            pid, lid = uid(), uid()
            nid = note_id(lid)
            path = "notes/" + nid.decode()
            require(path not in existing_note_paths, "New note UUID collision")
            existing_note_paths.add(path)
            p = templates[2]
            for f, value in ((2, pid), (4, aid), (5, i), (11, uid())):
                p = put(p, f, value)
            p = put(p, 8, encode([(1, 5, struct.pack("<f", float(new_pdf.pages[i-1].mediabox.width) * scale)),
                                 (2, 5, struct.pack("<f", float(new_pdf.pages[i-1].mediabox.height) * scale))]))
            new_pages.append(encode([(1, 2, pid), (2, 2, p)]))
            l = putpath(putpath(put(templates[54], 2, lid), [3, 1], pid), [4, 1], f"4HRnd{i:03d}".encode())
            l = put(l, 11, uid())
            new_layers.append(encode([(1, 2, lid), (54, 2, l)]))
            n = put(put(put(templates[104], 2, nid), 11, uid()), 15, uid())
            new_notes.append(encode([(1, 2, nid), (104, 2, n)]))
            new_index.append(encode([(1, 2, nid), (2, 2, path.encode())]))
            additions[path] = b""
        replacements["index.notes.pb"] = framed(new_index) + archive.read("index.notes.pb")
    changed, inserted = [], set()
    for old, raw_frame in split_frames(archive.read("index.events.pb")):
        k, p = kind(old), body(old)
        if new_attachment is not None and k == 6 and k not in inserted:
            changed.append(framed([encode([(1, 2, get(new_attachment, 1)), (6, 2, new_attachment)])]))
            inserted.add(k)
        if prepend and k in (2, 54, 104) and k not in inserted:
            changed.append(framed({2: new_pages, 54: new_layers, 104: new_notes}[k]))
            inserted.add(k)
        if k == 6:
            p = put(p, 5, len(pdf_data))
            if prepend:
                p = putpath(p, [12, 1], get(get(p, 12), 1) + prepend)
        elif prepend and k == 2:
            p = put(p, 5, get(p, 5) + prepend)
        elif prepend and k == 54:
            order = get(get(p, 4), 1).decode()
            p = putpath(p, [4, 1], f"4HRnd{int(order[5:]) + prepend:03d}".encode())
        changed.append(raw_frame if p == body(old) else framed([put(old, k, p)]))
    replacements["index.events.pb"] = b"".join(changed)
    if prepend:
        for aid in attachments:
            name = "search/" + aid.decode()
            if name not in archive.namelist():
                continue  # An unindexed attachment is allowed; do not fabricate recognition data.
            updates = []
            for b, raw in split_frames(archive.read(name)):
                page = get(b, 2)
                require(isinstance(page, int) and page in coverage, "Unexpected attachment search-cache shape")
                updates.append(put(b, 2, page + prepend))
            replacements[name] = framed(updates)
    result_es = frames(replacements["index.events.pb"])
    rp, rl, _, _ = mapping(result_es, len(new_pdf.pages))
    if prepend:
        ordered = sorted(rl.values(), key=lambda p: get(get(p, 4), 1))
        require([get(rp[get(get(l, 3), 1)], 5) for l in ordered] == list(range(1, len(new_pdf.pages)+1)), "Layer order mismatch")
    for pid, original in pages.items():
        require(put(rp[pid], 5, get(original, 5)) == original, "Unexpected original-page change")
    return replacements, additions, {"status": "written", "original_pdf_pages": len(old_pdf.pages),
        "pdf_pages": len(new_pdf.pages), "front_pages_added": prepend, "original_body_verified": True,
        "preview_preserved": True, "goodnotes_import_of_this_output_tested": False,
        "native_outline_conversion_performed": False}


def repack_verified(source, output, replacements, additions=None):
    source, output = Path(source), Path(output)
    require(source.resolve() != output.resolve() and not output.exists(), "Use a new output path")
    output.parent.mkdir(parents=True, exist_ok=True)
    before = digest_file(source)
    fd, temp = tempfile.mkstemp(prefix=".goodnotes-", suffix=".tmp", dir=output.parent)
    os.close(fd)
    temp = Path(temp)
    try:
        with open_archive(source) as src, zipfile.ZipFile(temp, "w", allowZip64=True) as dst:
            require(set(replacements) <= set(src.namelist()), "Replacement names not present in source")
            require(not set(additions or {}) & set(src.namelist()), "Added members collide with source")
            dst.comment = src.comment
            for info in src.infolist():
                if info.filename in replacements:
                    dst.writestr(copy.copy(info), replacements[info.filename])
                elif info.is_dir():
                    dst.writestr(copy.copy(info), b"")
                else:
                    with src.open(info) as a, dst.open(copy.copy(info), "w", force_zip64=True) as b:
                        shutil.copyfileobj(a, b)
            for name, data in (additions or {}).items():
                dst.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
        preserved = []
        with open_archive(source) as src, open_archive(temp) as result:
            require(result.testzip() is None, "Output CRC failed")
            require(set(result.namelist()) == set(src.namelist()) | set(additions or {}), "Output inventory mismatch")
            for name in src.namelist():
                if name in replacements:
                    require(result.read(name) == replacements[name], "Patched member mismatch")
                else:
                    with src.open(name) as a, result.open(name) as b:
                        old_hash, new_hash = digest_stream(a), digest_stream(b)
                    require(old_hash == new_hash, f"Preserved member changed: {name}")
                    preserved.append({"member": name, "sha256": new_hash})
            for name, data in (additions or {}).items():
                require(result.read(name) == data, "Added member mismatch")
        require(digest_file(source) == before, "Source changed during operation")
        # A late-created output must never be replaced. Exclusive creation reserves the name.
        with output.open("xb"):
            pass
        try:
            os.replace(temp, output)
        except Exception:
            output.unlink()
            raise
        return {"source_sha256": before, "output_sha256": digest_file(output), "zip_crc_ok": True,
                "source_immutable": True, "preserved_members": preserved}
    finally:
        if temp.exists():
            temp.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("inspect"); p.add_argument("input"); p.add_argument("--report")
    p = commands.add_parser("extract"); p.add_argument("input"); p.add_argument("--out-dir", required=True)
    p = commands.add_parser("add-outlines"); p.add_argument("input"); p.add_argument("--output", required=True); p.add_argument("--reference")
    p = commands.add_parser("replace-pdf"); p.add_argument("input"); p.add_argument("pdf"); p.add_argument("--prepend", type=int, default=0); p.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    with open_archive(args.input) as archive:
        if args.command == "inspect":
            report = inspect(archive)
            if args.report:
                write_json(args.report, report)
        elif args.command == "extract":
            report = extract(archive, args.out_dir)
        else:
            output = Path(args.output)
            report_path = output.with_suffix(".verification.json")
            require(not output.exists() and not report_path.exists(), "Output/report path already exists")
            if args.command == "add-outlines":
                if args.reference:
                    with open_archive(args.reference) as reference:
                        patch, report = add_outline_data(archive, reference)
                else:
                    patch, report = add_outline_data(archive)
                if patch is None:
                    print(json.dumps(report, ensure_ascii=False, indent=2))
                    return 0
                replacements, additions = {"index.events.pb": patch}, {}
            else:
                replacements, additions, report = replace_pdf_data(archive, Path(args.pdf).read_bytes(), args.prepend)
            report.update(repack_verified(args.input, output, replacements, additions))
            report.update(source=str(Path(args.input).resolve()), output=str(output.resolve()))
            write_json(report_path, report)
    summary = {k: v for k, v in report.items() if k not in ("entries", "preserved_members", "page_note_bindings", "recognition_candidates", "typed_text_objects")}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FormatError, zipfile.BadZipFile, KeyError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2)
