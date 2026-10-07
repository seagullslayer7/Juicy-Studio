"""Codec fallback, rate control, and container compatibility regressions."""
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import video_encoding as v
import enhance_worker as e


class EncodingTests(unittest.TestCase):
    def test_automatic_fallback_stays_with_selected_codec(self):
        tried = []
        def run(command, **kwargs):
            encoder = command[command.index('-c:v')+1]; tried.append(encoder)
            return SimpleNamespace(returncode=0 if encoder == 'libx265' else 1, stderr='unsupported')
        with patch.object(v.subprocess, 'run', side_effect=run):
            result = v.select_export_encoder('auto_hevc', '18', 'medium')
        self.assertEqual(result, 'libx265')
        self.assertEqual(tried, list(v.CODECS['hevc'][1]))

    def test_manual_unavailable_encoder_never_silently_falls_back(self):
        with patch.object(v.subprocess, 'run', return_value=SimpleNamespace(returncode=1, stderr='no device')) as run:
            with self.assertRaisesRegex(RuntimeError, 'hevc_amf is unavailable'):
                v.select_export_encoder('hevc_amf', '18', 'medium')
        self.assertEqual(run.call_count, 1)

    def test_bitrate_mode_does_not_keep_quality_rate_control(self):
        for _, encoders in v.CODECS.values():
            for encoder in encoders:
                with self.subTest(encoder=encoder):
                    args = v.encoder_options(encoder, '18', 'medium', '8000000')
                    self.assertEqual(args[args.index('-b:v')+1], '8000000')
                    for option in ('-crf', '-cq', '-qp_i', '-qp_p', '-global_quality'):
                        self.assertNotIn(option, args)

    def test_settings_reject_mismatch_and_invalid_values(self):
        for change in ({'codec':'hevc','encoder':'h264_nvenc'}, {'encoder':'copy'}, {'codec':'vp9'},
                       {'rate_control':'cbr'}, {'rate_control':'bitrate','bitrate':'nan'},
                       {'rate_control':'bitrate','bitrate':'-1'}, {'preset':'invalid'},
                       {'quality':'52'}, {'audio':'arbitrary'}, {'container':'avi'}):
            with self.subTest(change=change), self.assertRaises(ValueError): e.validate_settings(change)

    def test_old_jobs_keep_h264_copy_audio_defaults(self):
        settings = e.export_settings({})
        self.assertEqual(settings['codec'], 'h264')
        self.assertEqual(e.audio_options(settings, '.mp4', [{'codec_name':'aac'}]), ['-c:a','copy'])
        self.assertEqual(e.export_settings({'encoder':'libx265'})['codec'], 'hevc')

    def test_audio_compatibility_and_bitrate(self):
        source = [{'codec_name':'dts'}]
        with self.assertRaisesRegex(ValueError, 'MKV'):
            e.audio_options(e.export_settings({}), '.mp4', source)
        self.assertEqual(e.audio_options(e.export_settings({'audio':'aac','audio_bitrate':'320'}), '.mp4', source),
                         ['-c:a','aac','-b:a','320k'])
        for audio in ('flac','libopus'):
            settings = e.export_settings({'audio':audio})
            with self.assertRaisesRegex(ValueError, 'MKV'): e.audio_options(settings, '.mp4', source)
            self.assertIn(audio, e.audio_options(settings, '.mkv', source))

    def test_stereo_requires_encoding_and_preserves_original_default(self):
        with self.assertRaisesRegex(ValueError,'requires audio encoding'):
            e.export_settings({'audio':'copy','audio_channels':'stereo'})
        with self.assertRaisesRegex(ValueError,'channels'):
            e.export_settings({'audio_channels':'surprise'})
        for codec in ('aac','libopus','flac'):
            settings=e.export_settings({'audio':codec,'audio_channels':'stereo'})
            args=e.audio_options(settings,'.mkv',[{'codec_name':'aac','channels':4}])
            self.assertEqual(args[-2:],['-ac:a','2'])
        original=e.audio_options(e.export_settings({}),'.mkv',[{'codec_name':'aac','channels':4}])
        self.assertEqual(original,['-c:a','copy'])

    def test_probe_uses_actual_frame_rate_and_bitrate(self):
        with patch.object(v.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as run:
            v.select_export_encoder('hevc_nvenc', '18', 'fast', bitrate='4000000', fps='60000/1001',
                                    transforms=['-vf','scale=3840:2160'])
        command = run.call_args.args[0]
        self.assertIn('color=size=640x480:rate=60000/1001', command)
        self.assertIn('scale=3840:2160', command)
        self.assertIn('4000000', command)

    def test_amf_av1_quantizer_uses_its_own_scale(self):
        args = v.encoder_options('av1_amf', '18', 'medium')
        self.assertEqual(args[args.index('-qp_i')+1], '90')
