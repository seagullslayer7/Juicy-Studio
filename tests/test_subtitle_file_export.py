"""External export keeps formatting instead of round-tripping through plain cues."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_enhance import scratch
from subtitle_document import new_document, cue, export_text
from subtitle_worker import prepare_export_subtitles


class SubtitleFileExportTests(unittest.TestCase):
    def test_external_ass_keeps_styles_and_override_tags(self):
        doc=new_document();doc['cues']=[cue(.2,1.2,'Styled text')]
        text=export_text(doc,'ass').replace('Styled text',r'{\pos(240,90)\i1}Styled text')
        with scratch() as folder:
            root=Path(folder);source=root/'captions with spaces.ass';source.write_text(text,encoding='utf-8-sig')
            dest=root/'output';dest.mkdir()
            result,font=prepare_export_subtitles({'subtitle_file':str(source)},dest)
            self.assertEqual(result.read_text(encoding='utf-8-sig'),text)
            self.assertIsNone(font)
            self.assertEqual(source.read_text(encoding='utf-8-sig'),text)

    def test_external_srt_works_without_editor_document(self):
        text='1\n00:00:00,200 --> 00:00:01,200\n<i>Hello</i>\n'
        with scratch() as folder:
            root=Path(folder);source=root/'source.srt';source.write_text(text,encoding='utf-8')
            dest=root/'output';dest.mkdir()
            result,_=prepare_export_subtitles({'subtitle_file':str(source)},dest)
            self.assertEqual(result.suffix,'.srt')
            self.assertEqual(result.read_text(encoding='utf-8-sig'),text)

    def test_invalid_external_file_fails_without_creating_captions(self):
        with scratch() as folder:
            root=Path(folder);dest=root/'output';dest.mkdir()
            for name,data in [('empty.srt',b''),('bad.vtt',b'not subtitles'),('bad.ass',b'\xff'),('file.txt',b'text')]:
                source=root/name;source.write_bytes(data)
                with self.subTest(name=name),self.assertRaises(ValueError):
                    prepare_export_subtitles({'subtitle_file':str(source)},dest)
            self.assertEqual(list(dest.iterdir()),[])

    def test_editor_track_export_remains_supported(self):
        doc=new_document();doc['cues']=[cue(0,1,'Original')];doc['cues'][0]['translation']='Translation'
        with scratch() as folder:
            result,font=prepare_export_subtitles({'document':doc,'track':'translation'},folder)
            text=result.read_text(encoding='utf-8-sig')
            self.assertIn('Translation',text);self.assertNotIn('Original',text)
            self.assertEqual(font,doc['style']['font'])
