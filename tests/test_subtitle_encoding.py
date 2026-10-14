"""Subtitle exports must honor their own settings without hidden global overrides."""
import json
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import subtitle_encoding as encoding


class SubtitleEncodingTests(unittest.TestCase):
    def args(self, settings, video=None, audio='aac'):
        streams = [dict(codec_type='video', codec_name='hevc', bit_rate='2500000')]
        streams += [dict(codec_type='audio', codec_name=audio)]
        # Explicit keys allow a caller to replace codec/bitrate below.
        streams[0].update(video or {})
        with patch.object(encoding.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps(dict(streams=streams)))), \
             patch.object(encoding, 'select_export_encoder', return_value='hevc_nvenc') as select:
            notes=[]
            result=encoding.encoding_args(settings, 'source.mp4', 'captions.ass', notes.append)
            return result, select.call_args, notes

    def test_default_matches_source_and_copies_audio(self):
        args, call, _ = self.args({})
        self.assertEqual(call.args[0], 'auto_hevc')
        self.assertEqual(call.kwargs['bitrate'], 2500000)
        self.assertEqual(args[args.index('-c:a')+1], 'copy')
        self.assertEqual(args[args.index('-tag:v')+1], 'hvc1')
        self.assertIn('subtitles=captions.ass', args[args.index('-vf')+1])
        self.assertNotIn('-r', args)

    def test_explicit_bitrate_and_stereo_are_honored(self):
        args, call, _ = self.args(dict(codec='hevc',encoder='hevc_nvenc',rate='bitrate',bitrate=4.25,
                                      audio='aac',audio_bitrate=256,channels='stereo'))
        self.assertEqual(call.args[0], 'hevc_nvenc')
        self.assertEqual(call.kwargs['bitrate'], 4250000)
        self.assertEqual(args[args.index('-b:a')+1], '256k')
        self.assertEqual(args[args.index('-ac')+1], '2')

    def test_quality_does_not_use_source_bitrate(self):
        args, call, _ = self.args(dict(codec='av1',rate='quality',quality=27,preset='slow'))
        self.assertEqual(call.args[:3], ('auto_av1',27,'slow'))
        self.assertIsNone(call.kwargs['bitrate'])
        self.assertEqual(args[args.index('-cq')+1], '27')

    def test_missing_source_metadata_has_explicit_fallback(self):
        _, call, notes = self.args({}, dict(codec_name='vp9',bit_rate='N/A'))
        self.assertEqual(call.args[:2], ('auto',23))
        self.assertIsNone(call.kwargs['bitrate'])
        self.assertTrue(any('H.264' in n for n in notes))
        self.assertTrue(any('quality 23' in n for n in notes))

    def test_incompatible_audio_auto_encodes_and_copy_fails(self):
        args, _, _ = self.args({},audio='dts')
        self.assertEqual(args[args.index('-c:a')+1], 'aac')
        with self.assertRaisesRegex(ValueError,'cannot be copied'):
            self.args(dict(audio='copy'),audio='dts')

    def test_invalid_or_contradictory_settings_fail(self):
        for settings in [dict(codec='hevc',encoder='h264_nvenc'),dict(audio='copy',channels='stereo'),
                         dict(quality=-1),dict(quality=52),dict(quality=20.5),dict(bitrate=float('nan')),
                         dict(bitrate=201),dict(audio_bitrate=10),dict(rate='copy')]:
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                encoding.validate_settings(settings)
