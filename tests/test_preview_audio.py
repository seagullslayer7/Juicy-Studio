"""Exercise real Qt output replacement and device fallback without audible playback."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from types import SimpleNamespace, MethodType
from PySide6.QtWidgets import QApplication, QWidget, QComboBox, QSlider
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices
from subtitle_ui import SubtitleWorkspace


class PreviewAudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_reconnect_preserves_volume_and_replaces_attached_output(self):
        owner = QWidget()
        owner.player = QMediaPlayer(owner)
        owner.audio = QAudioOutput(owner)
        owner.player.setAudioOutput(owner.audio)
        owner.volume = QSlider(); owner.volume.setValue(37)
        owner.audio_device = QComboBox()
        owner.audio_device.addItem('Disconnected device', b'missing-device')
        messages = []
        owner.host = SimpleNamespace(set_status=messages.append)
        owner.reconnect_audio = MethodType(SubtitleWorkspace.reconnect_audio, owner)
        old = owner.audio
        owner.reconnect_audio()
        self.assertIsNot(old, owner.audio)
        self.assertEqual(owner.player.audioOutput(), owner.audio)
        self.assertAlmostEqual(owner.audio.volume(), .37, places=5)
        self.assertEqual(owner.audio.device().id(), QMediaDevices.defaultAudioOutput().id())
        self.assertTrue(messages)
        SubtitleWorkspace.refresh_audio_devices(owner)
        self.assertIsNone(owner.audio_device.currentData())
        self.assertEqual(len(messages), 1)  # Device refresh is quiet.
        owner.deleteLater()
        self.app.processEvents()
