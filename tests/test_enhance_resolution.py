import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import unittest
from enhance_resolution import output_size, model_scale
from enhance_worker import validate_settings


class ResolutionTests(unittest.TestCase):
    def test_landscape_targets_and_legacy_default(self):
        self.assertEqual(output_size(640,360), (1280,720))
        for target,expected in [('720p',(1280,720)),('1080p',(1920,1080)),
                                ('1440p',(2560,1440)),('2160p',(3840,2160)),('4x',(2560,1440))]:
            with self.subTest(target=target): self.assertEqual(output_size(640,360,target), expected)

    def test_portrait_and_non_widescreen_fit_without_stretch(self):
        self.assertEqual(output_size(360,640,'1080p'), (1080,1920))
        self.assertEqual(output_size(640,480,'1080p'), (1440,1080))
        self.assertEqual(output_size(1000,1000,'2160p'), (2160,2160))
        self.assertEqual(output_size(2560,1080,'2160p'), (3840,1620))

    def test_even_dimensions_and_bounded_aspect_rounding(self):
        for w,h in [(853,479),(479,853),(1921,1081),(101,97)]:
            ow,oh = output_size(w,h,'1440p')
            self.assertEqual(ow%2,0); self.assertEqual(oh%2,0)
            self.assertLessEqual(max(ow,oh),2560)
            self.assertLessEqual(min(ow,oh),1440)
            self.assertLess(abs(ow/oh-w/h),.01)

    def test_downscale_is_explicit_sizing_not_forced_upscale(self):
        self.assertEqual(output_size(3840,2160,'1080p'), (1920,1080))

    def test_invalid_targets_and_limits(self):
        for target in ('8k','custom',None):
            with self.subTest(target=target), self.assertRaises(ValueError):
                validate_settings({'resolution':target})
        with self.assertRaises(ValueError): output_size(3840,2160,'4x')
        with self.assertRaises(ValueError): output_size(0,100,'1080p')

    def test_animation_selects_smallest_sufficient_native_model(self):
        for output,scale in [((1280,720),2),((1920,1080),3),((2560,1440),4),((3840,2160),4),((320,180),2)]:
            self.assertEqual(model_scale('animation',640,360,output),scale)
        self.assertEqual(model_scale('live',640,360,(1280,720)),4)
