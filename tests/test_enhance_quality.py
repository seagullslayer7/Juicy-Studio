from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from enhance_quality import color_pipeline,automatic_bitrate,preserve_chroma_array,preview_size_estimate


class EnhancementQualityTests(unittest.TestCase):
    def test_tagged_source_matrix_and_range_survive_rgb_conversion(self):
        decode,encode,tags,note=color_pipeline(dict(width=720,height=404,color_space='bt709',color_range='pc',color_primaries='bt709',color_transfer='bt709'))
        self.assertIn('in_color_matrix=bt709',decode);self.assertIn('in_range=full',decode)
        self.assertIn('out_color_matrix=bt709',encode);self.assertIn('out_range=tv',encode)
        self.assertEqual(tags[:4],['-colorspace','bt709','-color_range','tv'])
        self.assertNotIn('assumed',note)

    def test_untagged_assumptions_are_reported_and_can_be_overridden(self):
        sd=dict(width=720,height=404)
        self.assertIn('bt601',color_pipeline(sd)[0]);self.assertIn('assumed',color_pipeline(sd)[3])
        self.assertIn('bt709',color_pipeline(dict(width=1280,height=720))[0])
        self.assertIn('bt709',color_pipeline(sd,'bt709')[0])
        with self.assertRaises(ValueError):color_pipeline(sd,'invalid')

    def test_auto_budget_avoids_unbounded_quality_size(self):
        args=(1280,720,59,(2560,1440),2836748)
        av1=int(automatic_bitrate(*args,'av1','live'));h264=int(automatic_bitrate(*args,'h264','live'))
        self.assertTrue(8_000_000<=av1<=10_000_000)
        self.assertLess(av1,h264)
        self.assertLess(av1,46_500_000/4)
        self.assertEqual(automatic_bitrate(160,90,12,(320,180),0,'hevc','live'),'1000000')

    def test_chroma_preservation_keeps_source_color_with_ai_brightness(self):
        import numpy as np
        from PIL import Image
        source=Image.new('RGB',(4,4),(100,70,50));ai=Image.new('RGB',(8,8),(80,110,90))
        result=np.asarray(preserve_chroma_array(ai,source))[4,4].astype(float)
        self.assertAlmostEqual(result[0]-result[1],30,delta=1)
        self.assertAlmostEqual(result[1]-result[2],20,delta=1)
        y=np.array([.2126,.7152,.0722])
        self.assertAlmostEqual(result@y,np.array([80,110,90])@y,delta=1)

    def test_preview_size_estimate_includes_ratio_and_uncertainty(self):
        text=preview_size_estimate(10_000_000,5,1000,500_000_000)
        self.assertIn('2.0 GB',text);self.assertIn('4.0×',text);self.assertIn('Varies',text)
