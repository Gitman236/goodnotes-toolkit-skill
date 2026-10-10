"""Synthetic archives only: no real notebooks, textbooks, titles, or ink fixtures."""
from pathlib import Path
import sys
import tempfile
import unittest
import io
import struct
import zipfile

from pypdf import PdfWriter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import goodnotes_toolkit as gn


def event(k, target, payload):
    return gn.encode([(1, 2, target), (k, 2, payload)])


def synthetic_pdf(pages=2, prepend=0, outlines=True):
    writer = PdfWriter()
    for _ in range(prepend):
        writer.add_blank_page(width=300, height=400)
    for _ in range(pages):
        writer.add_blank_page(width=600, height=800)
    if outlines:
        root = writer.add_outline_item("Section A", prepend)
        writer.add_outline_item("Detail A", prepend + min(1, pages - 1), parent=root)
    data = io.BytesIO()
    writer.write(data)
    return data.getvalue()


def make_archive(path, pdf_data=None):
    pdf_data = synthetic_pdf() if pdf_data is None else pdf_data
    doc, aid, blob = gn.uid(), gn.uid(), gn.uid()
    es = [event(30, doc, gn.encode([(1, 2, doc)]))]
    attachment = gn.encode([(1, 2, aid), (2, 2, blob), (5, 0, len(pdf_data)), (6, 2, doc),
                            (10, 1, struct.pack("<d", 1)), (11, 2, gn.uid()),
                            (12, 2, gn.encode([(1, 0, 1), (2, 0, 2)]))])
    es.append(event(6, aid, attachment))
    layers, notes = [], {}
    for page in range(1, 3):
        pid, lid = gn.uid(), gn.uid()
        nid = gn.note_id(lid)
        layers.append(lid)
        p = gn.encode([(1, 2, doc), (2, 2, pid), (4, 2, aid), (5, 0, page),
                       (8, 2, gn.encode([(1, 5, struct.pack("<f", 600)), (2, 5, struct.pack("<f", 800))])),
                       (11, 2, gn.uid())])
        l = gn.encode([(1, 2, doc), (2, 2, lid), (3, 2, gn.register(pid)),
                       (4, 2, gn.register(f"4HRnd{page:03d}".encode())), (11, 2, gn.uid())])
        n = gn.encode([(2, 2, nid), (11, 2, gn.uid()), (15, 2, gn.uid())])
        es += [event(2, pid, p), event(54, lid, l), event(104, nid, n)]
        # An unknown operation and a synthetic typed-text object must survive.
        typed_raw = gn.encode([(1, 2, gn.encode([(1, 2, b"Synthetic typed text")]))])
        compressed = b"bv4-" + struct.pack("<I", len(typed_raw)) + typed_raw + b"bv4$"
        typed_object = gn.encode([(32, 2, gn.encode([(1, 2, gn.encode([(2, 2, compressed)]))]))])
        notes["notes/" + nid.decode()] = gn.framed([gn.encode([(106, 2, b"uninterpreted")]), gn.encode([(21, 2, typed_object)])])
    oid = gn.uid()
    native = gn.encode([(1, 2, layers[0]), (2, 2, oid), (3, 2, gn.register()), (4, 2, gn.register()),
                        (5, 2, gn.register(b"Legacy Example")), (6, 2, gn.register()),
                        (10, 1, struct.pack("<d", 100)), (11, 2, gn.uid()), (13, 0, 1234),
                        (14, 0, 1000), (15, 2, gn.register(b"")), (16, 0, 26), (17, 2, doc)])
    es += [event(65, layers[0], native), event(106, doc, gn.encode([(900, 2, b"future-event")]))]
    blob_path = "attachments/" + blob.decode()
    members = {
        "schema.pb": gn.encode([(1, 0, 35)]), "document.info.pb": b"",
        "index.events.pb": gn.framed(es),
        "index.attachments.pb": gn.framed([gn.encode([(1, 2, aid), (2, 2, blob_path.encode())])]),
        "index.notes.pb": gn.framed([gn.encode([(1, 2, name[6:].encode()), (2, 2, name.encode())]) for name in notes]),
        "index.search.pb": b"", blob_path: pdf_data,
        "search/" + aid.decode(): gn.framed([gn.encode([(2, 0, p), (3, 2, b"")]) for p in (1, 2)]),
        "thumbnail.jpg": b"opaque-preview-preserved", **notes,
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as out:
        for name, data in members.items():
            out.writestr(name, data)


class WireTests(unittest.TestCase):
    def test_unknown_and_noncanonical_field_bytes_preserved(self):
        data = b"\x08\x81\x00" + gn.encode([(888, 2, b"unknown"), (2, 0, 5)])
        new = gn.put(data, 2, 7)
        self.assertEqual(new[:3], data[:3])
        self.assertEqual(gn.get(new, 888), b"unknown")
        self.assertEqual(gn.get(new, 2), 7)

    def test_truncated_records_and_frames_rejected(self):
        for data in (b"\x12\x05ab", b"\x0d\0", b"\x80"):
            with self.assertRaises(gn.FormatError): gn.fields(data)
        with self.assertRaises(gn.FormatError): gn.frames(b"\x05a")

    def test_lz4_cross_block_history_and_trailer(self):
        data = b"bv4-" + struct.pack("<I", 4) + b"abcd"
        # A four-byte match using the preceding raw block as dictionary, then a literal.
        compressed = b"\x00\x04\x00\x10X"
        data += b"bv41" + struct.pack("<II", 5, len(compressed)) + compressed + b"bv4$TAIL"
        self.assertEqual(gn.unpack_apple(data), (b"abcdabcdX", 4))
        with self.assertRaises(gn.FormatError): gn.unpack_apple(data, limit=8)
        with self.assertRaises(gn.FormatError): gn.lz4_block(b"\x00\x00\x00")


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / "source.goodnotes"
        make_archive(self.source)

    def tearDown(self):
        self.tmp.cleanup()

    def test_outline_synthesis_preservation_and_idempotence(self):
        with gn.open_archive(self.source) as z:
            old = z.read("index.events.pb")
            patch, report = gn.add_outline_data(z)
        self.assertEqual(report["native_entries_added"], 2)
        self.assertTrue(patch.startswith(old))
        output = self.root / "outlined.goodnotes"
        gn.repack_verified(self.source, output, {"index.events.pb": patch})
        with gn.open_archive(output) as z:
            again, report = gn.add_outline_data(z)
        self.assertIsNone(again)
        self.assertEqual(report["status"], "already-present")

    def test_reference_transfer_remaps_current_document_and_layers(self):
        with gn.open_archive(self.source) as z:
            patch, _ = gn.add_outline_data(z)
        reference = self.root / "working.goodnotes"
        gn.repack_verified(self.source, reference, {"index.events.pb": patch})
        second = self.root / "new-ids.goodnotes"
        make_archive(second)
        with gn.open_archive(second) as z, gn.open_archive(reference) as ref:
            transferred, report = gn.add_outline_data(z, ref)
            current_doc = gn.get(gn.body(gn.events_of(z)[0]), 1)
            _, _, l2p, _ = gn.mapping(gn.events_of(z))
        self.assertEqual(report["mode"], "reference-shape-transfer")
        for b in gn.frames(transferred)[-2:]:
            self.assertEqual(gn.get(gn.body(b), 17), current_doc)
            self.assertIn(gn.get(gn.body(b), 1), l2p)

    def test_prepend_updates_mapping_preserves_notes_unknown_events(self):
        with gn.open_archive(self.source) as z:
            original_unknown = [b for b in gn.events_of(z) if gn.kind(b) == 106]
            patches, added, report = gn.replace_pdf_data(z, synthetic_pdf(prepend=1), 1)
        output = self.root / "replaced.goodnotes"
        audit = gn.repack_verified(self.source, output, patches, added)
        self.assertTrue(audit["source_immutable"])
        with gn.open_archive(output) as z:
            events = gn.events_of(z)
            _, _, _, p2l = gn.mapping(events, 3)
            self.assertEqual(sorted(p2l), [1, 2, 3])
            self.assertEqual([b for b in events if gn.kind(b) == 106], original_unknown)
            self.assertEqual(gn.inspect(z)["note_files"], 3)

    def test_layout_changes_and_wrong_schema_refused(self):
        writer = PdfWriter()
        for _ in range(2): writer.add_blank_page(width=500, height=800)
        data = io.BytesIO(); writer.write(data)
        with gn.open_archive(self.source) as z:
            with self.assertRaises(gn.FormatError): gn.replace_pdf_data(z, data.getvalue(), 0)
        wrong = self.root / "wrong.goodnotes"
        gn.repack_verified(self.source, wrong, {"schema.pb": gn.encode([(1, 0, 99)])})
        with gn.open_archive(wrong) as z:
            with self.assertRaises(gn.FormatError): gn.add_outline_data(z)

    def test_extract_typed_text_and_opaque_member(self):
        with gn.open_archive(self.source) as z:
            report = gn.extract(z, self.root / "extracted")
        self.assertEqual(len(report["typed_text_objects"]), 2)
        self.assertEqual(report["typed_text_objects"][0]["text"], "Synthetic typed text")
        self.assertEqual((self.root / "extracted/raw/thumbnail.jpg").read_bytes(), b"opaque-preview-preserved")

    def test_output_collision_and_unsafe_member_refused(self):
        before = gn.digest_file(self.source)
        with self.assertRaises(gn.FormatError): gn.repack_verified(self.source, self.source, {})
        self.assertEqual(gn.digest_file(self.source), before)
        evil = self.root / "evil.goodnotes"
        with zipfile.ZipFile(evil, "w") as z: z.writestr("../outside", b"no")
        with self.assertRaises(gn.FormatError): gn.open_archive(evil)


if __name__ == "__main__":
    unittest.main()
