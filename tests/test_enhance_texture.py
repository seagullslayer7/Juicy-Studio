"""Source fidelity and bounded texture recovery, without model downloads."""
import unittest
import numpy as np
from PIL import Image
from enhance_texture import recover_texture, protect_source_structure
from enhance_people import composite_face
from enhance_worker import validate_settings


def texture(size=128, amplitude=12):
    y,x=np.mgrid[:size,:size]
    values=np.rint(120+amplitude*np.sin(x*1.2)*np.cos(y*.9)).astype(np.uint8)
    return Image.fromarray(np.repeat(values[...,None],3,axis=2))


class TextureTests(unittest.TestCase):
    def test_disabled_processing_and_full_source_blend(self):
        original=texture(); result=Image.new('RGB',(256,256),(90,110,130))
        self.assertIs(recover_texture(result,original,0),result)
        self.assertIs(protect_source_structure(result,original,0,False),result)
        self.assertEqual(protect_source_structure(result,original,1).tobytes(),
                         original.resize(result.size,Image.Resampling.BICUBIC).tobytes())

    def test_recovers_attenuated_texture_with_bounded_changes(self):
        original=texture(); result=texture(amplitude=3)
        recovered=np.asarray(recover_texture(result,original,1)).astype(float)
        before=np.asarray(result).astype(float); reference=np.asarray(original).astype(float)
        self.assertLess(np.mean((recovered-reference)**2),np.mean((before-reference)**2)*.5)
        self.assertLessEqual(np.max(np.abs(recovered-before)),8)
        np.testing.assert_array_equal(recovered[:,:,0],recovered[:,:,1])

    def test_flat_and_tiny_noise_are_not_amplified(self):
        result=Image.new('RGB',(128,128),(120,120,120))
        for original in (result,texture(amplitude=1)):
            self.assertEqual(recover_texture(result,original,1).tobytes(),result.tobytes())

    def test_recovery_rejects_strong_disagreement(self):
        original=texture(); result=Image.new('RGB',original.size,(180,180,180))
        self.assertEqual(recover_texture(result,original,1).tobytes(),result.tobytes())

    def test_protection_reduces_invented_shape_without_touching_background(self):
        source=np.full((128,128,3),100,dtype=np.uint8); changed=source.copy()
        changed[35:90,45:75]=210
        result=np.asarray(protect_source_structure(Image.fromarray(changed),Image.fromarray(source)))
        self.assertLess(np.mean(np.abs(result.astype(float)-source)),
                        np.mean(np.abs(changed.astype(float)-source))*.3)
        np.testing.assert_array_equal(result[:20],source[:20])

    def test_protection_keeps_small_fine_detail(self):
        result=texture(amplitude=6); source=Image.new('RGB',result.size,(120,120,120))
        self.assertEqual(protect_source_structure(result,source).tobytes(),result.tobytes())

    def test_full_face_strength_can_retain_frame_texture(self):
        source=texture(512); face=Image.new('RGB',source.size,(120,120,120))
        without=np.asarray(composite_face(source.copy(),face,np.eye(3),source.size,1,texture=0))
        with_texture=np.asarray(composite_face(source.copy(),face,np.eye(3),source.size,1,texture=.5))
        self.assertGreater(with_texture[260:310,235:275].std(),without[260:310,235:275].std())
        np.testing.assert_array_equal(with_texture[0],without[0])

    def test_rejects_invalid_fidelity_settings(self):
        for key in ('texture_recovery','face_texture','source_blend'):
            for value in (-1,101,float('nan'),float('inf')):
                with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                    validate_settings({key:value})
        with self.assertRaises(ValueError):validate_settings({'structure_protection':'invalid'})
        validate_settings({'texture_recovery':35,'face_texture':50,'source_blend':15,'structure_protection':'on'})
