"""Enhancement workspace: shared queue, paired preview, optional local models."""
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtWidgets import (QWidget, QFrame, QLabel, QVBoxLayout, QHBoxLayout,
    QFormLayout, QPushButton, QSlider, QFileDialog, QMessageBox, QStyle)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from subtitle_ui import action, VideoPreview


class EnhanceWorkspace(QWidget):
    job_requested = Signal(dict)

    def __init__(self, host, root, Combo, Timestamp):
        super().__init__()
        self.host, self.root = host, root
        self.video_path = None
        self.preview_path = None
        self.preview_start = 0
        self.preview_length = 0
        self.busy = False
        self.preview_settings = None
        layout = QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.setSpacing(12)
        heading = QHBoxLayout()
        title = QLabel('Enhance'); title.setObjectName('sectionTitle'); heading.addWidget(title)
        self.summary = QLabel('2× AI upscaling · local processing'); self.summary.setObjectName('muted')
        heading.addWidget(self.summary); heading.addStretch()
        self.install_button = action('Install enhancement models', self.install,
            'Download the optional, verified Real-ESRGAN engine and bundled models (43 MiB). Uses Vulkan on NVIDIA or AMD.')
        heading.addWidget(self.install_button); layout.addLayout(heading)
        self.settings_panel = QFrame(); self.settings_panel.setObjectName('card')
        settings_row = QHBoxLayout(self.settings_panel); settings_row.setContentsMargins(16,12,16,12); settings_row.setSpacing(24)
        self.model = Combo(); self.model.addItem('Animation','animation'); self.model.addItem('Live action','live')
        self.model.setToolTip('Animation uses a native 2× video model. Live action runs a 4× model, then reduces to 2× for the final output.')
        self.gpu = Combo(); self.gpu.addItem('Automatic','auto')
        for index in range(4): self.gpu.addItem(f'GPU {index}',str(index))
        self.gpu.setToolTip('Vulkan device index. Automatic lets the enhancement engine choose. Device numbering can differ from speech recognition.')
        self.encoder = Combo()
        for label,value in [('Automatic','auto'),('NVIDIA H.264','h264_nvenc'),('AMD H.264','h264_amf'),('CPU H.264','libx264')]: self.encoder.addItem(label,value)
        self.encoder.setToolTip('Automatic tests available encoders. Encoding is separate from the GPU running the AI model.')
        self.quality = Combo()
        for label,value in [('Very high','16'),('High','18'),('Balanced','23')]: self.quality.addItem(label,value)
        self.quality.setCurrentIndex(1)
        self.quality.setToolTip('Controls video compression after upscaling. Audio is copied without re-encoding.')
        for label,control in [('Content',self.model),('Graphics card',self.gpu),('Encoder',self.encoder),('Quality',self.quality)]:
            column = QVBoxLayout(); column.addWidget(QLabel(label)); column.addWidget(control); settings_row.addLayout(column,1)
            control.currentIndexChanged.connect(self.invalidate_preview)
        layout.addWidget(self.settings_panel)
        previews = QHBoxLayout(); previews.setSpacing(12)
        self.original = QMediaPlayer(self); self.enhanced = QMediaPlayer(self)
        self.audio = QAudioOutput(self); self.audio.setVolume(.6); self.original.setAudioOutput(self.audio)
        # Only the original plays audio; both panels follow one playback position.
        for title,player in [('Original',self.original),('Enhanced · generate a preview',self.enhanced)]:
            panel = QFrame(); panel.setObjectName('card'); box = QVBoxLayout(panel); box.setContentsMargins(14,12,14,14)
            label = QLabel(title); box.addWidget(label)
            if player is self.enhanced: self.result_label = label
            video = VideoPreview(player); video.setMinimumSize(200,160); box.addWidget(video,1)
            previews.addWidget(panel,1)
        layout.addLayout(previews,1)
        controls = QHBoxLayout()
        self.play_button = action('',self.toggle_play,'Play or pause the preview')
        self.play_button.setAccessibleName('Play or pause comparison')
        self.play_button.setIcon(host.media_icon(QStyle.StandardPixmap.SP_MediaPlay)); controls.addWidget(self.play_button)
        self.seek = QSlider(Qt.Orientation.Horizontal); self.seek.setToolTip('Seek both panels to the same moment')
        self.seek.sliderMoved.connect(self.seek_to); controls.addWidget(self.seek,1)
        self.mute = action('Sound on',self.toggle_mute,'Toggle original audio; enhanced preview never plays duplicate audio')
        controls.addWidget(self.mute); layout.addLayout(controls)
        footer = QHBoxLayout(); footer.setSpacing(12)
        footer.addWidget(QLabel('Preview starts at'))
        self.start = Timestamp(); self.start.setRange(0,864000); self.start.setValue(0); footer.addWidget(self.start)
        self.at_playhead = action('Use playhead',self.use_playhead,'Set the preview start to the current original-video position')
        footer.addWidget(self.at_playhead)
        self.length = Combo()
        for seconds in (2,5,10): self.length.addItem(f'{seconds} seconds',seconds)
        self.length.setCurrentIndex(1); footer.addWidget(self.length)
        footer.addStretch()
        self.preview_button = action('Generate preview',self.generate_preview,'Enhance only this short section and compare before exporting',True)
        self.export_button = action('Export enhanced video…',self.export,'Enhance the complete selected file to MP4 or MKV; keep all original audio tracks')
        footer.addWidget(self.preview_button); footer.addWidget(self.export_button); layout.addLayout(footer)
        self.hint = QLabel('Select a video from the shared queue. Export censor edits first; add subtitle burn-in after upscaling.')
        self.hint.setWordWrap(True); self.hint.setObjectName('muted'); layout.addWidget(self.hint)
        for player in (self.original,self.enhanced):
            player.errorOccurred.connect(lambda error,text:self.host.set_status('Enhancement preview unavailable: '+text))
        self.original.durationChanged.connect(self.duration_changed)
        self.original.positionChanged.connect(self.position_changed)
        self.original.playbackStateChanged.connect(self.play_state_changed)
        self.enhanced.mediaStatusChanged.connect(self.ready_preview)
        self.timer = QTimer(self); self.timer.setInterval(100); self.timer.timeout.connect(self.synchronize); self.timer.start()
        self.set_busy(False)

    def settings(self):
        return {key:getattr(self,key).currentData() for key in ('model','gpu','encoder','quality')}

    def installed(self):
        # GUI can be frozen; the tools always belong beside the application.
        folder = self.root/'tools/enhance/realesrgan-20220424'
        return all((folder/name).is_file() for name in ('realesrgan-ncnn-vulkan.exe',
            'models/realesr-animevideov3-x2.bin','models/realesr-animevideov3-x2.param',
            'models/realesrgan-x4plus.bin','models/realesrgan-x4plus.param'))

    def install(self):
        self.job_requested.emit(dict(action='enhance_install'))

    def load_video(self,path):
        self.pause(); self.video_path = str(path); self.invalidate_preview()
        self.start.setValue(0); self.original.setSource(QUrl.fromLocalFile(str(path)))
        self.hint.setText('2× output · 8-bit SDR · variable frame rates become constant. Export censor edits first; add subtitles after upscaling.')
        self.set_busy(self.busy)

    def clear_video(self):
        self.pause(); self.video_path = None; self.original.setSource(QUrl()); self.invalidate_preview(); self.set_busy(self.busy)

    def invalidate_preview(self,*args):
        self.pause(); self.preview_path = None; self.enhanced.setSource(QUrl())
        self.result_label.setText('Enhanced · generate a preview')
        self.seek.setRange(0,self.original.duration())

    def duration_changed(self,duration):
        if not self.preview_path: self.seek.setRange(0,duration)
        self.start.setMaximum(max(0,duration/1000-.05))

    def use_playhead(self): self.start.setValue(self.original.position()/1000)

    def generate_preview(self):
        if not self.video_path or self.busy: return
        token = uuid4().hex
        output = self.root/'cache/enhance-previews'/f'{token}.mkv'
        self.preview_settings = self.settings()
        self.pause()
        self.job_requested.emit(dict(action='enhance_preview',video=self.video_path,output=str(output),
            partial_token=token,settings=self.settings(),start=self.start.value(),length=self.length.currentData()))

    def export(self):
        if not self.video_path or self.busy: return
        name = str(Path(self.video_path).with_name(Path(self.video_path).stem+'_enhanced.mkv'))
        output,_ = QFileDialog.getSaveFileName(self,'Export enhanced video',name,'Matroska (*.mkv);;MP4 (*.mp4)')
        if not output: return
        if Path(output).exists():
            QMessageBox.information(self,'Choose a new filename','Existing files are preserved. Choose a different output filename.'); return
        self.pause()
        self.job_requested.emit(dict(action='enhance_export',video=self.video_path,output=output,
            partial_token=uuid4().hex,settings=self.settings()))

    def receive(self,data):
        if data['type'] == 'enhance_installed':
            self.host.set_status('Enhancement engine and models installed. Generate a short preview to begin.')
        elif data['type'] == 'enhance_preview':
            self.pause(); self.preview_path = data['output']; self.preview_start = data['start']; self.preview_length = data['length']
            self.enhanced.setSource(QUrl.fromLocalFile(self.preview_path))
            self.seek.setRange(0,round(self.preview_length*1000)); self.seek.setValue(0)
            self.original.setPosition(round(self.preview_start*1000))
            self.result_label.setText(f"Enhanced · {data['width']} × {data['height']}")
            self.host.set_status('Preview ready. Play both panels to compare the same section.')
        elif data['type'] == 'enhance_exported':
            self.host.last_output = data['output']; self.host.open_result_btn.setEnabled(True)
            self.host.set_status('Enhanced video exported. Original audio copied without re-encoding.')

    def ready_preview(self,status):
        if self.preview_path and status == QMediaPlayer.MediaStatus.LoadedMedia: self.seek_to(0)

    def seek_to(self,value):
        self.original.setPosition(value+(round(self.preview_start*1000) if self.preview_path else 0))
        if self.preview_path: self.enhanced.setPosition(value)

    def position_changed(self,position):
        if not self.seek.isSliderDown(): self.seek.setValue(max(0,position-(round(self.preview_start*1000) if self.preview_path else 0)))

    def toggle_play(self):
        if self.original.playbackState() == QMediaPlayer.PlaybackState.PlayingState: self.pause()
        else:
            if self.preview_path:
                relative = self.original.position()-round(self.preview_start*1000)
                if relative < 0 or relative >= self.preview_length*1000-50: self.seek_to(0)
                self.enhanced.play()
            self.original.play()

    def play_state_changed(self,state):
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.play_button.setIcon(self.host.media_icon(QStyle.StandardPixmap.SP_MediaPause if playing else QStyle.StandardPixmap.SP_MediaPlay))

    def synchronize(self):
        if not self.preview_path or self.original.playbackState() != QMediaPlayer.PlaybackState.PlayingState: return
        position = self.original.position()-round(self.preview_start*1000)
        if position >= self.preview_length*1000-30:
            self.pause(); return
        if abs(self.enhanced.position()-position) > 100: self.enhanced.setPosition(max(0,position))

    def toggle_mute(self):
        self.audio.setMuted(not self.audio.isMuted()); self.mute.setText('Sound off' if self.audio.isMuted() else 'Sound on')

    def pause(self):
        self.original.pause(); self.enhanced.pause()
        if self.preview_path:
            self.enhanced.setPosition(max(0,self.original.position()-round(self.preview_start*1000)))

    def set_busy(self,busy):
        self.busy = busy; available = bool(self.video_path) and not busy
        self.settings_panel.setEnabled(not busy)
        installed = self.installed()
        self.install_button.setVisible(not installed); self.install_button.setEnabled(not busy)
        self.preview_button.setEnabled(available and installed); self.export_button.setEnabled(available and installed)
        for control in (self.play_button,self.seek,self.start,self.at_playhead,self.length): control.setEnabled(available)

    def shutdown(self):
        self.timer.stop(); self.pause()
        for player in (self.original,self.enhanced): player.setSource(QUrl()); player.setVideoOutput(None)
