"""Enhancement workspace: shared queue, paired preview, optional local models."""
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtWidgets import (QWidget, QFrame, QLabel, QVBoxLayout, QHBoxLayout,
    QGridLayout, QSpinBox, QDoubleSpinBox, QPushButton, QSlider, QFileDialog, QMessageBox, QStyle)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from subtitle_ui import action, VideoPreview
from video_encoding import CODECS, ENCODER_LABELS


class EnhanceWorkspace(QWidget):
    job_requested = Signal(dict)

    def __init__(self, host, root, Combo, Timestamp, Spin=QDoubleSpinBox):
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
        settings_row = QGridLayout(self.settings_panel); settings_row.setContentsMargins(16,12,16,12)
        settings_row.setHorizontalSpacing(20); settings_row.setVerticalSpacing(10)
        self.model = Combo(); self.model.addItem('Animation','animation'); self.model.addItem('Live action','live')
        self.model.setToolTip('Animation uses a native 2× video model. Live action runs a 4× model, then reduces to 2× for the final output.')
        self.gpu = Combo(); self.gpu.addItem('Automatic','auto')
        for index in range(4): self.gpu.addItem(f'GPU {index}',str(index))
        self.gpu.setToolTip('Vulkan device index. Automatic lets the enhancement engine choose. Device numbering can differ from speech recognition.')
        self.codec = Combo()
        for value,(label,_) in CODECS.items(): self.codec.addItem(label,value)
        self.codec.setToolTip('H.264 has broad playback support. HEVC and AV1 can reduce file size but require compatible players. Output remains 8-bit SDR.')
        self.encoder = Combo(); self.populate_encoders()
        self.encoder.setToolTip('Automatic tries working hardware, then CPU, for the selected codec. Manual choices are tested before upscaling. Availability depends on your GPU, driver, and FFmpeg build. AI processing uses its own GPU setting.')
        self.rate_control = Combo(); self.rate_control.addItem('Quality target','quality'); self.rate_control.addItem('Bitrate target','bitrate')
        self.rate_control.setToolTip('Quality target lets file size vary with the scene. Bitrate target sets an average video bitrate; actual size and bitrate can vary.')
        self.quality = Spin(); self.quality.setDecimals(0); self.quality.setRange(0,51); self.quality.setValue(18)
        self.quality.setToolTip('Lower values preserve more detail and use more space. Try 18 for high quality or 23 for smaller files. This uses CRF/CQ/QP depending on the encoder; values are not equivalent across codecs and 0 is not a universal lossless mode.')
        self.bitrate = Spin(); self.bitrate.setRange(.1,200); self.bitrate.setDecimals(1); self.bitrate.setSingleStep(1); self.bitrate.setValue(12); self.bitrate.setSuffix(' Mbps')
        self.bitrate.setToolTip('Average video bitrate, excluding audio. Higher resolutions and frame rates generally need more bitrate. This is not a strict file-size limit.')
        self.preset = Combo()
        for label,value in [('Fast','fast'),('Balanced','medium'),('Slower · better compression','slow')]: self.preset.addItem(label,value)
        self.preset.setCurrentIndex(1); self.preset.setToolTip('Controls encoding effort, not AI speed. Slower settings may improve compression. CPU HEVC and AV1 can be slow.')
        self.container = Combo(); self.container.addItem('Matroska (.mkv)','mkv'); self.container.addItem('MP4 (.mp4)','mp4')
        self.container.setToolTip('MKV supports all offered audio formats. MP4 uses AAC or compatible original audio. HEVC MP4 uses the hvc1 tag for player compatibility.')
        self.audio_encoder = Combo()
        for label,value in [('Original · copy all tracks','copy'),('AAC','aac'),('Opus · MKV','libopus'),('FLAC · lossless, MKV','flac')]: self.audio_encoder.addItem(label,value)
        self.audio_encoder.setToolTip('Original copies every audio track without quality loss. AAC/Opus re-encode all tracks. FLAC stores decoded audio losslessly but cannot recover detail already lost in a compressed source. Opus and FLAC select MKV.')
        self.audio_bitrate = Combo()
        for value in (128,192,256,320): self.audio_bitrate.addItem(f'{value} kbps',str(value))
        self.audio_bitrate.setCurrentIndex(1); self.audio_bitrate.setToolTip('Bitrate per audio track for AAC or Opus. Original and FLAC do not use a lossy bitrate setting.')
        fields = [('Content',self.model),('AI graphics card',self.gpu),('Video codec',self.codec),('Video encoder',self.encoder),
                  ('Rate control',self.rate_control),('Quality · lower is better',self.quality),('Video bitrate',self.bitrate),('Encoding speed',self.preset),
                  ('File format',self.container),('Audio',self.audio_encoder),('Audio bitrate',self.audio_bitrate)]
        for index,(label,control) in enumerate(fields):
            column = QVBoxLayout(); column.setSpacing(5); column.addWidget(QLabel(label)); column.addWidget(control)
            settings_row.addLayout(column,index//4,index%4); settings_row.setColumnStretch(index%4,1)
            signal = control.valueChanged if isinstance(control,(QSpinBox,QDoubleSpinBox)) else control.currentIndexChanged
            signal.connect(lambda *args,c=control:self.settings_changed(c))
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
        self.export_button = action('Export enhanced video…',self.export,'Enhance the complete selected file using the chosen video, audio, and format settings')
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
        self.settings_changed()
        self.set_busy(False)

    def settings(self):
        values = {key:getattr(self,key).currentData() for key in ('model','gpu','codec','encoder','rate_control','preset','container','audio_bitrate')}
        values.update(quality=str(int(self.quality.value())),bitrate=str(round(self.bitrate.value()*1_000_000)),audio=self.audio_encoder.currentData())
        return values

    def populate_encoders(self):
        previous = self.encoder.currentData()
        vendor = previous.split('_')[-1] if previous and '_' in previous else 'cpu' if previous and previous.startswith('lib') else 'auto'
        self.encoder.blockSignals(True); self.encoder.clear(); self.encoder.addItem('Automatic · prefer hardware','auto')
        for name in CODECS[self.codec.currentData()][1]:
            self.encoder.addItem(ENCODER_LABELS.get(name,ENCODER_LABELS.get(name.split('_')[-1])),name)
            if (vendor == 'cpu' and name.startswith('lib')) or name.endswith('_'+vendor): self.encoder.setCurrentIndex(self.encoder.count()-1)
        self.encoder.blockSignals(False)

    def settings_changed(self,control=None):
        if control is self.codec: self.populate_encoders()
        if control is self.audio_encoder and self.audio_encoder.currentData() in ('libopus','flac'):
            self.container.setCurrentIndex(self.container.findData('mkv'))
        elif control is self.container and self.container.currentData() == 'mp4' and self.audio_encoder.currentData() in ('libopus','flac'):
            self.audio_encoder.setCurrentIndex(self.audio_encoder.findData('aac'))
        self.quality.setEnabled(self.rate_control.currentData() == 'quality')
        self.bitrate.setEnabled(self.rate_control.currentData() == 'bitrate')
        self.audio_bitrate.setEnabled(self.audio_encoder.currentData() in ('aac','libopus'))
        self.invalidate_preview()

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
        suffix = self.container.currentData()
        name = str(Path(self.video_path).with_name(Path(self.video_path).stem+'_enhanced.'+suffix))
        output,_ = QFileDialog.getSaveFileName(self,'Export enhanced video',name,'Matroska (*.mkv)' if suffix == 'mkv' else 'MP4 (*.mp4)')
        if not output: return
        if not Path(output).suffix: output += '.'+suffix
        if Path(output).suffix.lower() != '.'+suffix:
            QMessageBox.information(self,'File format mismatch','Use the selected file extension, or change File format before exporting.'); return
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
            audio = 'Original audio copied without re-encoding.' if data.get('audio','copy') == 'copy' else 'Audio encoded as '+data['audio'].replace('libopus','Opus').upper()+'.'
            self.host.set_status('Enhanced video exported. '+audio)

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
