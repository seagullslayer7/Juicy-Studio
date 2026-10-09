"""Optional SwinIR selection, package contents, and inference boundary handling."""
from pathlib import Path
import unittest
import torch
from enhance_swinir_network import SwinIR
from enhance_cuda import model_choice, WEIGHTS
from enhance_worker import validate_settings
from build_release import PAYLOAD_FILES


class SwinIRTests(unittest.TestCase):
    def test_profiles_choose_distinct_verified_weights(self):
        for profile,flavor in [('swinir_detail','GAN'),('swinir_fidelity','PSNR')]:
            scale,names=model_choice(profile,320,180,(640,360))
            self.assertEqual((scale,names),(4,('SwinIR-L-'+flavor+'.pth',)))
            url,size,digest=WEIGHTS[names[0]]
            self.assertTrue(url.startswith('https://github.com/JingyunLiang/SwinIR/releases/'))
            self.assertGreater(size,140_000_000);self.assertEqual(len(digest),64)
            validate_settings(dict(model='live',restoration=profile))
        self.assertIn('enhance_swinir_network.py',PAYLOAD_FILES)
        self.assertTrue((Path(__file__).resolve().parents[1]/'licenses/SwinIR-LICENSE.txt').is_file())

    def test_odd_and_tiny_shapes_produce_finite_exact_fourfold_output(self):
        # Small topology exercises the actual shifted-window/padding code on CPU.
        model=SwinIR(upscale=4,in_chans=3,img_size=8,window_size=8,img_range=1.,
            depths=[2],embed_dim=12,num_heads=[3],mlp_ratio=2,upsampler='nearest+conv',resi_connection='3conv').eval()
        with torch.inference_mode():
            for height,width in ((8,8),(9,11),(1,3)):
                source=torch.linspace(0,1,height*width*3).reshape(1,3,height,width)
                result=model(source)
                self.assertEqual(tuple(result.shape),(1,3,height*4,width*4))
                self.assertTrue(torch.isfinite(result).all())
                torch.testing.assert_close(result,model(source),rtol=0,atol=0)
