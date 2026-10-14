import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import editor_project as model
from storage_cleanup import inventory, clear

class StorageTests(unittest.TestCase):
    def test_only_selected_generated_files_are_deleted(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paths = ['cache/audio/a.wav', 'cache/alignments/a.json', 'cache/reviews/edit.json', 'cache/editor-projects/autosave.juicy', 'cache/subtitle-projects/edit.json', 'models/base.bin', 'outputs/video.mp4', 'projects/edit.juicy', 'other.txt']
            for relative in paths:
                file = root / relative; file.parent.mkdir(parents=True, exist_ok=True); file.write_bytes(b'123')
            files, blocked = inventory(root, ['Speech alignments'])
            self.assertEqual([str(p.relative_to(root)).replace('\\', '/') for p, _ in files], ['cache/alignments/a.json'])
            self.assertFalse(blocked)
            self.assertEqual(clear(root, ['Speech alignments']), (3, []))
            for relative in paths:
                self.assertEqual((root / relative).exists(), relative != 'cache/alignments/a.json')

    def test_linked_cache_ancestor_is_skipped(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); file = root / 'cache/audio/source.wav'; file.parent.mkdir(parents=True); file.write_bytes(b'protected')
            from storage_cleanup import linked
            with patch('storage_cleanup.linked', side_effect=lambda p: p == root / 'cache' or linked(p)):
                files, blocked = inventory(root, ['Temporary processing files'])
                self.assertFalse(files); self.assertTrue(blocked)
                clear(root, ['Temporary processing files'])
            self.assertEqual(file.read_bytes(), b'protected')

    def test_link_created_after_inventory_is_rechecked(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); file = root / 'cache/audio/a.wav'; file.parent.mkdir(parents=True); file.write_bytes(b'123')
            with patch('storage_cleanup.inventory', return_value=([(file, 3)], [])), patch('storage_cleanup.linked', side_effect=lambda p: p == root / 'cache'):
                count, failures = clear(root, ['Temporary processing files'])
            self.assertEqual(count, 0); self.assertTrue(failures); self.assertTrue(file.exists())

class TrackTests(unittest.TestCase):
    def test_defaults_and_legacy_projects(self):
        doc = model.new_project(); self.assertEqual([t['kind'] for t in model.tracks(doc)], ['video', 'audio'])
        del doc['tracks']; model.validate(doc)
        self.assertEqual(model.clip_track(doc, {}, 'audio'), 'a1')

    def test_remove_populated_track_preserves_clip_timing_and_history(self):
        doc = model.new_project(); media = model.add_media(doc, {'path':'sample.mp4','duration':5.,'audio':True})
        model.append_clip(doc, media); clip = doc['clips'][0]
        track = model.add_track(doc, 'audio'); clip['audio_track'] = track
        model.validate(doc); before = copy.deepcopy(doc); history = model.History(); history.record(doc)
        model.remove_track(doc, track); model.validate(doc)
        self.assertEqual(clip['audio_track'], 'a1'); self.assertEqual(model.duration(doc), 5.)
        self.assertEqual(history.undo(doc), before)
        with self.assertRaises(ValueError): model.remove_track(doc, 'a1')

    def test_invalid_cross_type_assignment_is_rejected(self):
        doc = model.new_project(); media = model.add_media(doc, {'path':'sample.mp4','duration':5.,'audio':True})
        model.append_clip(doc, media); doc['clips'][0]['audio_track'] = 'v1'
        with self.assertRaises(ValueError): model.validate(doc)
