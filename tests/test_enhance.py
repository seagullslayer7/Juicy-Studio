"""Boundary and failure checks for enhancement jobs; no model download needed."""
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import contextmanager
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'src'))
import enhance_worker as e


@contextmanager
def scratch():
    parent=Path(tempfile.gettempdir()).resolve()
    folder=parent/('juicy-enhance-test-'+uuid4().hex)
    folder.mkdir()
    try: yield str(folder)
    finally: e.safe_remove(folder,parent)


class EnhanceTests(unittest.TestCase):
    def test_invalid_model_device_and_encoder_are_rejected(self):
        for settings in ({'model':'../model'},{'gpu':'0,1'},{'gpu':'-1'},{'quality':'-1'},{'encoder':'copy'}):
            with self.subTest(settings=settings), self.assertRaises(ValueError): e.validate_settings(settings)

    def test_short_pipe_reads_are_combined_and_truncation_rejected(self):
        class Short(io.BytesIO):
            def read(self,n): return super().read(min(n,2))
        self.assertEqual(e.read_frame(Short(b'123456'),6),b'123456')
        self.assertEqual(e.read_frame(Short(b''),6),b'')
        with self.assertRaises(RuntimeError): e.read_frame(Short(b'123'),6)

    def test_source_and_existing_output_cannot_be_overwritten(self):
        with scratch() as folder:
            source=Path(folder)/'source.mp4'; source.write_bytes(b'original')
            with patch.object(e,'runtime_ready',return_value=True),self.assertRaises(ValueError):
                e.enhance(dict(action='enhance_export',video=str(source),output=str(source)),lambda *a,**k:None)
            self.assertEqual(source.read_bytes(),b'original')

    def test_bad_preview_bounds_do_not_create_output(self):
        with scratch() as folder:
            source=Path(folder)/'source.mp4'; source.touch(); output=Path(folder)/'output.mkv'
            for start,length in [(float('nan'),1),(-1,1),(0,11),(3,2),(0,0)]:
                with self.subTest(start=start,length=length),patch.object(e,'runtime_ready',return_value=True),patch.object(e,'probe',return_value={'duration':2}),self.assertRaises(ValueError):
                    e.enhance(dict(action='enhance_preview',video=str(source),output=str(output),start=start,length=length),lambda *a,**k:None)
            self.assertFalse(output.exists())

    def test_incompatible_mp4_audio_requests_mkv(self):
        with scratch() as folder:
            source=Path(folder)/'source.mkv'; source.touch()
            with patch.object(e,'runtime_ready',return_value=True),patch.object(e,'probe',return_value={'duration':1,'audio':[{'codec_name':'dts'}]}),self.assertRaisesRegex(ValueError,'MKV'):
                e.enhance(dict(action='enhance_export',video=str(source),output=str(Path(folder)/'out.mp4')),lambda *a,**k:None)

    def test_cleanup_refuses_paths_outside_job_parent(self):
        with scratch() as folder:
            root=Path(folder); other=root/'keep'; other.mkdir()
            with self.assertRaises(ValueError): e.safe_remove(other,root/'wrong')
            self.assertTrue(other.exists())

    def test_hdr_rotation_and_non_square_pixels_are_explicit(self):
        base=dict(codec_type='video',width=320,height=180,avg_frame_rate='30/1',pix_fmt='yuv420p')
        for change in ({'color_transfer':'smpte2084'},{'pix_fmt':'yuv420p10le'}, {'sample_aspect_ratio':'4:3'}, {'side_data_list':[{'rotation':90}]}):
            payload=dict(streams=[dict(base,**change)],format={'duration':'2'})
            result=type('Result',(),{'stdout':json.dumps(payload)})()
            with self.subTest(change=change),patch.object(e,'run',return_value=result),self.assertRaises(ValueError): e.probe('unused')

    def test_complete_runtime_is_reused_without_network(self):
        messages=[]
        with patch.object(e,'runtime_ready',return_value=True),patch.object(e.urllib.request,'urlopen',side_effect=AssertionError('network')):
            e.install_runtime(lambda kind,**values:messages.append(kind))
        self.assertEqual(messages,['enhance_installed'])
