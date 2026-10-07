import hashlib
import io
from pathlib import Path
import unittest
from unittest.mock import patch
from test_enhance import scratch
import enhance_cuda as cuda
from enhance_worker import FrameProgress, select_backend, validate_settings


class EnhancementSpeedTests(unittest.TestCase):
    def test_detail_uses_native_two_times_for_small_targets(self):
        self.assertEqual(cuda.model_choice('detail',1280,720,(2560,1440))[0],2)
        self.assertEqual(cuda.model_choice('detail',1280,720,(3840,2160))[0],4)
        self.assertEqual(cuda.model_choice('balanced',1280,720,(2560,1440))[0],4)

    def test_invalid_backend_and_restoration_rejected(self):
        for settings in ({'backend':'unknown'},{'restoration':'unknown'}):
            with self.assertRaises(ValueError):validate_settings(settings)
        with self.assertRaises(ValueError):select_backend({'model':'animation','backend':'cuda'})

    def test_vulkan_selection_does_not_require_cuda(self):
        self.assertEqual(select_backend({'model':'live','backend':'vulkan'}),'vulkan')
        self.assertEqual(select_backend({'model':'animation'}),'vulkan')

    def test_eta_available_below_one_percent_and_excludes_loading(self):
        now=[100.];progress=FrameProgress(87000,lambda:now[0])
        self.assertIsNone(progress.update(1)['remaining_seconds'])
        now[0]+=2
        report=progress.update(20)
        self.assertEqual(report['speed_fps'],10)
        self.assertAlmostEqual(report['remaining_seconds'],8698)

    def test_eta_adapts_to_recent_slowdown(self):
        now=[0.];progress=FrameProgress(10000,lambda:now[0])
        for seconds in range(1,41):
            now[0]=seconds;fast=progress.update(seconds*10)
        for seconds in range(41,81):
            now[0]=seconds;slow=progress.update(400+(seconds-40)*2)
        self.assertAlmostEqual(fast['speed_fps'],10)
        self.assertAlmostEqual(slow['speed_fps'],2)
        self.assertGreater(slow['remaining_seconds'],fast['remaining_seconds'])

    def test_verified_model_reused_without_download(self):
        with scratch() as directory:
            path=Path(directory);data=b'verified model';(path/'model.pth').write_bytes(data)
            manifest={'model.pth':('tag',len(data),hashlib.sha256(data).hexdigest())}
            with patch.dict(cuda.WEIGHTS,manifest),patch.object(cuda.urllib.request,'urlopen',side_effect=AssertionError('network')):
                cuda.ensure_weights(path,('model.pth',),lambda *a,**kw:None)

    def test_corrupt_download_preserves_old_file_and_cleans_partial(self):
        with scratch() as directory:
            path=Path(directory);(path/'model.pth').write_bytes(b'old cache')
            manifest={'model.pth':('tag',3,hashlib.sha256(b'new').hexdigest())}
            with patch.dict(cuda.WEIGHTS,manifest),patch.object(cuda.urllib.request,'urlopen',return_value=io.BytesIO(b'bad')):
                with self.assertRaisesRegex(ValueError,'integrity'):cuda.ensure_weights(path,('model.pth',),lambda *a,**kw:None)
            self.assertEqual((path/'model.pth').read_bytes(),b'old cache')
            self.assertFalse(list(path.glob('*.partial')))
