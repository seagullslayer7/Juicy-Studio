"""Face alignment/compositing boundaries without downloading model weights."""
import unittest
import numpy as np
from PIL import Image
from enhance_people import TEMPLATE,face_transform,select_faces,composite_face
from enhance_cuda import model_choice,bsrgan_parameters
from enhance_worker import validate_settings


class PeopleEnhancementTests(unittest.TestCase):
    def test_face_alignment_preserves_rotation_scale_and_translation(self):
        angle=.2;scale=2.3
        matrix=np.array([[scale*np.cos(angle),-scale*np.sin(angle),31],
                         [scale*np.sin(angle),scale*np.cos(angle),-14],[0,0,1]])
        source=(np.c_[TEMPLATE,np.ones(5)]@np.linalg.inv(matrix).T)[:,:2]
        np.testing.assert_allclose(face_transform(source),matrix,atol=1e-6)

    def test_tiny_and_invalid_faces_are_skipped(self):
        self.assertIsNone(face_transform(TEMPLATE/20))
        self.assertIsNone(face_transform(np.full((5,2),float('nan'))))
        invalid=TEMPLATE.copy();invalid[2]+=[200,300]
        self.assertIsNone(face_transform(invalid))

    def test_duplicate_detections_and_low_confidence_are_skipped(self):
        face=np.r_[50,50,100,100,TEMPLATE.reshape(-1),.99]
        duplicate=face.copy();duplicate[:2]+=2;duplicate[-1]=.98
        weak=face.copy();weak[0]=300;weak[-1]=.7
        self.assertEqual(len(select_faces([face,duplicate,weak])),1)

    def test_face_mask_changes_only_face_region_and_respects_strength(self):
        base=Image.new('RGB',(512,512),(100,80,60));restored=Image.new('RGB',(512,512),(180,180,180))
        self.assertEqual(composite_face(base.copy(),restored,np.eye(3),(512,512),0).tobytes(),base.tobytes())
        result=np.asarray(composite_face(base.copy(),restored,np.eye(3),(512,512),.35))
        np.testing.assert_array_equal(result[0,0],[100,80,60])
        self.assertGreater(result[290,256,0],100)
        self.assertEqual(int(result[290,256,0])-int(result[290,256,1]),20)

    def test_face_compositing_handles_nonuniform_even_pixel_resize(self):
        base=Image.new('RGB',(1024,768),(50,50,50));restored=Image.new('RGB',(512,512),(150,150,150))
        result=np.asarray(composite_face(base,restored,np.eye(3),(512,512),.5))
        np.testing.assert_array_equal(result[435,512],[100,100,100])
        np.testing.assert_array_equal(result[0,0],[50,50,50])

    def test_face_settings_reject_invalid_values_and_animation(self):
        for options in ({'face_restore':'bad'},{'model':'live','face_strength':'nan'},
                        {'model':'live','face_strength':101},{'face_restore':'gfpgan','model':'animation'}):
            with self.subTest(options=options),self.assertRaises(ValueError):validate_settings(options)
        validate_settings({'model':'live','face_restore':'gfpgan','face_strength':35})

    def test_whole_frame_models_use_their_own_weights(self):
        self.assertEqual(model_choice('bsrgan',720,404,(1920,1076)),(4,('BSRGAN.pth',)))
        self.assertEqual(model_choice('detail4',1280,720,(1920,1080)),(4,('RealESRGAN_x4plus.pth',)))
        state=bsrgan_parameters({'RRDB_trunk.2.RDB1.conv1.weight':'weight','upconv1.bias':'bias'})
        self.assertEqual(state,{'body.2.rdb1.conv1.weight':'weight','conv_up1.bias':'bias'})
