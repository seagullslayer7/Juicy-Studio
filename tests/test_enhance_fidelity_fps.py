import json
from pathlib import Path
from fractions import Fraction
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4
import numpy as np
from PIL import Image
from enhance_framerate import frame_rates
from enhance_texture import source_guided_detail
from enhance_resolution import output_size
from enhance_worker import enhance, validate_settings


class FidelityTests(unittest.TestCase):
    def test_guided_pass_cannot_create_shapes_in_flat_source(self):
        source=Image.new('RGB',(64,64),(80,100,120))
        generated=np.random.default_rng(7).integers(0,256,(128,128,3),dtype=np.uint8)
        result=source_guided_detail(Image.fromarray(generated),source)
        self.assertEqual(result.tobytes(),source.resize((128,128)).tobytes())

    def test_guided_change_is_bounded_and_preserves_color_differences(self):
        y,x=np.mgrid[:64,:64];gray=100+10*np.sin(x*.8)*np.cos(y*.9)
        source=Image.fromarray(np.stack([gray+20,gray,gray-20],axis=2).astype(np.uint8))
        generated=Image.fromarray(np.clip((np.asarray(source,dtype=float)-100)*2+100,0,255).astype(np.uint8))
        result=np.asarray(source_guided_detail(generated,source),dtype=int)
        delta=result-np.asarray(source,dtype=int)
        self.assertLessEqual(np.max(np.abs(delta)),6)
        self.assertGreater(np.max(np.abs(delta)),0)
        np.testing.assert_array_equal(delta[:,:,0],delta[:,:,1])

    def test_original_resolution_rounds_only_for_codec_alignment(self):
        self.assertEqual(output_size(1920,1080,'original'),(1920,1080))
        self.assertEqual(output_size(853,479,'original'),(852,478))

    def test_frame_rates_preserve_exact_fractions_and_avoid_extra_ai(self):
        self.assertEqual(frame_rates('30000/1001','source'),('30000/1001','30000/1001'))
        self.assertEqual(frame_rates('24','60'),('24','60'))
        self.assertEqual(frame_rates('60','24000/1001'),('24000/1001','24000/1001'))
        for invalid in ('0','121','nan','30;bad',None):
            with self.assertRaises(ValueError):validate_settings({'output_fps':invalid})
        with self.assertRaises(ValueError):validate_settings({'processing':'guided','model':'live','face_restore':'gfpgan'})


class FrameRateExportTests(unittest.TestCase):
    def test_faithful_conversion_duration_audio_and_frame_counts(self):
        from runtime_paths import configure_runtime
        configure_runtime()
        with tempfile.TemporaryDirectory(prefix='juicy-fps-') as folder:
            root=Path(folder);source=root/'sample.mkv'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=96x64:rate=48:duration=2',
                '-f','lavfi','-i','sine=frequency=500:duration=2','-c:v','libx264','-crf','0',
                '-c:a','aac','-ac','2',str(source)],check=True,capture_output=True)
            def packets(path):
                data=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','a:0',
                    '-show_packets','-show_data_hash','sha256','-of','json',str(path)]))
                return [p['data_hash'] for p in data['packets']]
            original_audio=packets(source)
            for rate in ('source','25','60','30000/1001'):
                with self.subTest(rate=rate):
                    output=root/(rate.replace('/','-')+'.mkv');events=[]
                    settings=dict(processing='faithful',backend='cuda',output_fps=rate,resolution='original',
                        encoder='libx264',codec='h264',quality='0',rate_control='quality',audio='copy')
                    # A faithful export must not initialize or require an AI backend.
                    with patch('enhance_worker.ROOT',root),patch('enhance_worker.select_backend',side_effect=AssertionError('AI invoked')):
                        enhance(dict(action='enhance_preview',video=str(source),output=str(output),
                            start=0,length=2,settings=settings,partial_token=uuid4().hex),lambda kind,**kw:events.append(dict(type=kind,**kw)))
                    metadata=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames',
                        '-show_streams','-show_format','-of','json',str(output)]))
                    video=metadata['streams'][0];expected=Fraction(48 if rate=='source' else rate)
                    self.assertEqual(Fraction(video['avg_frame_rate']),expected)
                    self.assertLessEqual(abs(int(video['nb_read_frames'])-round(2*expected)),1)
                    self.assertLess(abs(float(metadata['format']['duration'])-2),.1)
                    self.assertEqual((video['width'],video['height']),(96,64))
                    audio=packets(output)
                    self.assertTrue(any(original_audio[i:i+len(audio)]==audio for i in range(3)))
                    self.assertGreaterEqual(len(audio),len(original_audio)-2)
                    self.assertEqual(events[-1]['backend'],'cpu')
                    self.assertEqual(events[-1]['processing_fps'],str(min(Fraction(48),expected)))
