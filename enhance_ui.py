"""Enhancement workspace: shared queue, paired preview, optional local models."""
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtWidgets import (QWidget, QFrame, QLabel, QVBoxLayout, QHBoxLayout,
    QGridLayout, QSpinBox, QDoubleSpinBox, QTabWidget, QPushButton, QSlider, QFileDialog, QMessageBox, QStyle)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaMetaData
from subtitle_ui import action, VideoPreview
from video_encoding import CODECS, ENCODER_LABELS
from enhance_resolution import TARGETS, output_size, model_scale


def playback_time(milliseconds):
    seconds, ms = divmod(max(0,round(milliseconds)),1000)
    minutes, seconds = divmod(seconds,60)
    hours, minutes = divmod(minutes,60)
    return f'{hours:02}:{minutes:02}:{seconds:02}.{ms:03}'


class ComparisonSeek(QSlider):
    """Click anywhere to seek, retaining native keyboard and handle dragging."""
    def mousePressEvent(self,event):
        if event.button() == Qt.MouseButton.LeftButton:
            value = QStyle.sliderValueFromPosition(self.minimum(),self.maximum(),
                max(0,min(self.width()-10,round(event.position().x())-5)),max(1,self.width()-10))
            self.setValue(value); self.sliderMoved.emit(value)
        super().mousePressEvent(event)


class EnhanceWorkspace(QWidget):
    job_requested = Signal(dict)

    def __init__(self, host, root, Combo, Timestamp, Spin=QDoubleSpinBox):
        super().__init__()
        self.host, self.root = host, root
        self.video_path = None
        self.source_dimensions = None
        self.preview_path = None
        self.preview_start = 0
        self.preview_length = 0
        self.busy = False
        self.preview_settings = None
        self.preview_pending = False
        self.cuda_devices, self.vulkan_devices = [], []
        layout = QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.setSpacing(12)
        heading = QHBoxLayout()
        title = QLabel('Enhance'); title.setObjectName('sectionTitle'); heading.addWidget(title)
        self.summary = QLabel('AI upscaling · local processing'); self.summary.setObjectName('muted')
        heading.addWidget(self.summary); heading.addStretch()
        self.install_button = action('Install enhancement models', self.install,
            'Download the optional, verified Real-ESRGAN engine and bundled models (43 MiB). Uses Vulkan on NVIDIA or AMD.')
        heading.addWidget(self.install_button); layout.addLayout(heading)
        self.settings_panel = QFrame(); self.settings_panel.setObjectName('card')
        settings_box = QVBoxLayout(self.settings_panel); settings_box.setContentsMargins(12,8,12,8)
        self.settings_tabs = QTabWidget(); settings_box.addWidget(self.settings_tabs)
        self.model = Combo(); self.model.addItem('Animation','animation'); self.model.addItem('Live action','live')
        self.model.setToolTip('Choose an animation-video model or live-action restoration. Both support NVIDIA CUDA and Vulkan. Compare a short preview before exporting.')
        self.backend = Combo()
        for label,value in [('Automatic','auto'),('NVIDIA CUDA','cuda'),('Vulkan · NVIDIA / AMD','vulkan')]: self.backend.addItem(label,value)
        self.backend.setToolTip('Automatic uses CUDA when an NVIDIA runtime is ready; otherwise Vulkan. CUDA keeps animation or live-action models in GPU memory across frames. Video encoding is a separate setting.')
        self.restoration = Combo(); self.restoration.addItem('Balanced · faster','balanced'); self.restoration.addItem('Detail · slower','detail')
        self.restoration.setToolTip('CUDA live action: Balanced uses a lightweight general-video model with moderate denoising. Detail uses a heavier native 2× model for targets up to 2×, or 4× for larger targets. These produce different results; compare a preview. Vulkan live action uses the legacy Detail model.')
        self.gpu = Combo(); self.gpu.addItem('Automatic','auto')
        self.gpu.setToolTip('Detected graphics cards for the selected AI backend. Automatic chooses the default device. Switching backend resets the selection. Vulkan cards appear after the enhancement engine is installed.')
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
        self.resolution = Combo()
        for value,(label,_) in TARGETS.items(): self.resolution.addItem(label,value)
        self.resolution.setToolTip('Choose 2×/4× source size or fit within 720p, 1080p, 1440p (QHD), or 4K (UHD). Presets follow landscape/portrait orientation, preserve aspect ratio, and round to even pixels without cropping or stretching. A smaller target downscales. Enlargement beyond 4× adds conventional resizing after AI.')
        groups = [('Enhancement',[('Content',self.model),('AI backend',self.backend),('AI graphics card',self.gpu),
                                 ('Restoration',self.restoration),('Output resolution',self.resolution)]),
                  ('Encoding',[('Video codec',self.codec),('Video encoder',self.encoder),('File format',self.container),
                               ('Rate control',self.rate_control),('Quality · lower is better',self.quality),('Video bitrate',self.bitrate),
                               ('Encoding speed',self.preset),('Audio',self.audio_encoder),('Audio bitrate',self.audio_bitrate)])]
        for title,fields in groups:
            page=QWidget(); settings_row=QGridLayout(page); settings_row.setContentsMargins(8,8,8,8)
            settings_row.setHorizontalSpacing(20); settings_row.setVerticalSpacing(8)
            for index,(label,control) in enumerate(fields):
                column = QVBoxLayout(); column.setSpacing(4); column.addWidget(QLabel(label)); column.addWidget(control)
                settings_row.addLayout(column,index//3,index%3); settings_row.setColumnStretch(index%3,1)
                signal = control.valueChanged if isinstance(control,(QSpinBox,QDoubleSpinBox)) else control.currentIndexChanged
                signal.connect(lambda *args,c=control:self.settings_changed(c))
            self.settings_tabs.addTab(page,title)
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
            if player is self.original: video.video.nativeSizeChanged.connect(self.source_size_changed)
            previews.addWidget(panel,1)
        layout.addLayout(previews,1)
        controls = QHBoxLayout()
        self.play_button = action('',self.toggle_play,'Play or pause the preview')
        self.play_button.setAccessibleName('Play or pause comparison')
        self.play_button.setIcon(host.media_icon(QStyle.StandardPixmap.SP_MediaPlay)); controls.addWidget(self.play_button)
        self.time_label = QLabel('00:00:00.000 / 00:00:00.000'); self.time_label.setObjectName('muted')
        self.time_label.setToolTip('Current position / duration within the comparison; the source range is shown above the video.')
        controls.addWidget(self.time_label)
        self.seek = ComparisonSeek(Qt.Orientation.Horizontal); self.seek.setObjectName('enhanceSeek'); self.seek.setFixedHeight(22)
        self.seek.setToolTip('Click or drag to seek both panels; arrow keys fine-tune the position')
        self.seek.setSingleStep(100); self.seek.setPageStep(1000)
        self.seek.sliderMoved.connect(self.seek_to)
        self.seek.actionTriggered.connect(lambda _: QTimer.singleShot(0,lambda:self.seek_to(self.seek.value())))
        controls.addWidget(self.seek,1)
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
        self.original.metaDataChanged.connect(self.source_metadata_changed)
        self.original.positionChanged.connect(self.position_changed)
        self.original.playbackStateChanged.connect(self.play_state_changed)
        self.enhanced.mediaStatusChanged.connect(self.ready_preview)
        self.timer = QTimer(self); self.timer.setInterval(100); self.timer.timeout.connect(self.synchronize); self.timer.start()
        self.settings_changed()
        self.set_busy(False)

    def settings(self):
        values = {key:getattr(self,key).currentData() for key in ('model','backend','restoration','gpu','codec','encoder','rate_control','preset','container','audio_bitrate','resolution')}
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
        if control is self.backend: self.populate_gpus(reset=True)
        if control is self.codec: self.populate_encoders()
        if control is self.audio_encoder and self.audio_encoder.currentData() in ('libopus','flac'):
            self.container.setCurrentIndex(self.container.findData('mkv'))
        elif control is self.container and self.container.currentData() == 'mp4' and self.audio_encoder.currentData() in ('libopus','flac'):
            self.audio_encoder.setCurrentIndex(self.audio_encoder.findData('aac'))
        self.quality.setEnabled(self.rate_control.currentData() == 'quality')
        self.bitrate.setEnabled(self.rate_control.currentData() == 'bitrate')
        self.audio_bitrate.setEnabled(self.audio_encoder.currentData() in ('aac','libopus'))
        self.invalidate_preview()
        self.set_busy(self.busy)

    def uses_cuda(self):
        return (self.backend.currentData() == 'cuda' or
            (self.backend.currentData() == 'auto' and getattr(self.host,'cuda_available',False)))

    def populate_gpus(self,reset=False):
        previous = 'auto' if reset else self.gpu.currentData()
        devices = self.cuda_devices if self.uses_cuda() else self.vulkan_devices
        self.gpu.blockSignals(True); self.gpu.clear(); self.gpu.addItem('Automatic','auto')
        names = [device['name'] for device in devices]
        for device in devices:
            name = device['name']
            if names.count(name) > 1: name += f" · device {int(device['id'])+1}"
            self.gpu.addItem(name,str(device['id']))
        self.gpu.setCurrentIndex(max(0,self.gpu.findData(previous))); self.gpu.blockSignals(False)
        self.update_output_summary()

    def installed(self):
        if self.uses_cuda(): return True  # Verified CUDA model weights download on first use.
        # GUI can be frozen; the tools always belong beside the application.
        folder = self.root/'tools/enhance/realesrgan-20220424'
        return all((folder/name).is_file() for name in ('realesrgan-ncnn-vulkan.exe',
            'models/realesr-animevideov3-x2.bin','models/realesr-animevideov3-x2.param',
            'models/realesr-animevideov3-x3.bin','models/realesr-animevideov3-x3.param',
            'models/realesr-animevideov3-x4.bin','models/realesr-animevideov3-x4.param',
            'models/realesrgan-x4plus.bin','models/realesrgan-x4plus.param'))

    def install(self):
        self.job_requested.emit(dict(action='enhance_install'))

    def load_video(self,path):
        self.source_dimensions = None
        self.pause(); self.video_path = str(path); self.invalidate_preview()
        self.start.setValue(0); self.original.setSource(QUrl.fromLocalFile(str(path)))
        self.set_busy(self.busy)

    def clear_video(self):
        self.source_dimensions = None
        self.pause(); self.video_path = None; self.original.setSource(QUrl()); self.invalidate_preview(); self.set_busy(self.busy)

    def source_size_changed(self,size):
        if self.video_path and not size.isEmpty():
            self.source_dimensions = (round(size.width()),round(size.height()))
            self.update_output_summary()

    def source_metadata_changed(self):
        size = self.original.metaData().value(QMediaMetaData.Key.Resolution)
        if size is not None: self.source_size_changed(size)

    def update_output_summary(self):
        target = self.resolution.currentData()
        if not self.video_path or not self.source_dimensions:
            self.summary.setText('AI upscaling · '+TARGETS[target][0])
            self.hint.setText('Select a video to see its output dimensions. Export censor edits first; add subtitles after upscaling.')
            return
        width,height = self.source_dimensions
        try:
            output = output_size(width,height,target)
        except ValueError as exc:
            self.summary.setText('Choose a smaller output'); self.hint.setText(str(exc)); return
        self.summary.setText(f'{width} × {height} → {output[0]} × {output[1]}')
        scale = model_scale(self.model.currentData(),width,height,output)
        if self.uses_cuda():
            scale = 4
            if self.model.currentData() == 'animation': profile = 'Animation video'
            else:
                if self.restoration.currentData() == 'detail' and max(output[0]/width,output[1]/height) <= 2: scale=2
                profile = 'Balanced' if self.restoration.currentData() == 'balanced' else 'Detail'
            self.hint.setText(f'CUDA · {profile} · native {scale}× AI, resized to target · first use downloads verified model weights. Preview to compare detail and texture.')
            return
        ratio = max(output[0]/width,output[1]/height)
        detail = 'Downscales after AI enhancement.' if ratio < 1 else 'Additional enlargement beyond the AI model uses Lanczos resizing.' if ratio > scale else 'Aspect ratio preserved; no crop or stretch.'
        self.hint.setText(f'{scale}× AI model · {detail} 8-bit SDR; variable frame rates become constant.')

    def invalidate_preview(self,*args):
        self.preview_pending = False
        self.pause(); self.preview_path = None; self.enhanced.setSource(QUrl())
        self.result_label.setText('Enhanced · generate a preview')
        self.seek.setRange(0,self.original.duration())
        self.update_time()
        self.update_output_summary()

    def duration_changed(self,duration):
        if not self.preview_path: self.seek.setRange(0,duration)
        self.start.setMaximum(max(0,duration/1000-.05))
        self.update_time()

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
        if data['type'] == 'enhance_devices':
            self.vulkan_devices = data['vulkan']; self.populate_gpus()
        elif data['type'] == 'enhance_installed':
            self.host.set_status('Enhancement engine and models installed. Generate a short preview to begin.')
        elif data['type'] in ('enhance_preview','enhance_exported'):
            self.pause(); self.preview_path = data['output']; self.preview_start = data['start']; self.preview_length = data['length']
            self.preview_pending = True
            self.enhanced.setSource(QUrl.fromLocalFile(self.preview_path))
            self.seek.setRange(0,round(self.preview_length*1000)); self.seek.setValue(0)
            self.original.setPosition(round(self.preview_start*1000))
            label = 'Export' if data['type'] == 'enhance_exported' else 'Preview'
            self.result_label.setText(f"{label} · {data['width']} × {data['height']} · {playback_time(self.preview_start*1000)} – {playback_time((self.preview_start+self.preview_length)*1000)}")
            self.update_time()
            self.host.set_status('Preview ready. Play both panels to compare the same section.')
        if data['type'] == 'enhance_exported':
            self.host.last_output = data['output']; self.host.open_result_btn.setEnabled(True)
            audio = 'Original audio copied without re-encoding.' if data.get('audio','copy') == 'copy' else 'Audio encoded as '+data['audio'].replace('libopus','Opus').upper()+'.'
            self.host.set_status('Export ready in the comparison player. '+audio)

    def ready_preview(self,status):
        # Qt can emit LoadedMedia again on pause/end. Initialize each source once.
        if self.preview_path and self.preview_pending and status in (QMediaPlayer.MediaStatus.LoadedMedia,QMediaPlayer.MediaStatus.BufferedMedia):
            self.preview_pending = False
            self.seek_to(0)

    def seek_to(self,value):
        value = max(self.seek.minimum(),min(self.seek.maximum(),value))
        self.original.setPosition(value+(round(self.preview_start*1000) if self.preview_path else 0))
        if self.preview_path: self.enhanced.setPosition(value)
        self.update_time(value)

    def update_time(self,value=None):
        if value is None: value = self.original.position()-(round(self.preview_start*1000) if self.preview_path else 0)
        duration = round(self.preview_length*1000) if self.preview_path else self.original.duration()
        self.time_label.setText(f'{playback_time(min(max(0,value),duration))} / {playback_time(duration)}')

    def position_changed(self,position):
        if not self.seek.isSliderDown(): self.seek.setValue(max(0,position-(round(self.preview_start*1000) if self.preview_path else 0)))
        self.update_time()

    def toggle_play(self):
        if self.original.playbackState() == QMediaPlayer.PlaybackState.PlayingState: self.pause()
        else:
            if self.preview_path:
                relative = self.original.position()-round(self.preview_start*1000)
                if relative < 0 or relative >= self.preview_length*1000-50: self.seek_to(0)
                self.enhanced.play()
            elif self.original.mediaStatus() == QMediaPlayer.MediaStatus.EndOfMedia: self.seek_to(0)
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
        animation = self.model.currentData() == 'animation'
        self.restoration.blockSignals(True)
        if animation or not self.uses_cuda(): self.restoration.setCurrentIndex(0)
        self.restoration.setItemText(0,'Animation · video model' if animation else 'Balanced · faster' if self.uses_cuda() else 'Detail · Vulkan model')
        self.restoration.blockSignals(False)
        self.restoration.setEnabled(self.uses_cuda() and not animation)
        self.settings_panel.setEnabled(not busy)
        installed = self.installed()
        self.install_button.setVisible(not installed); self.install_button.setEnabled(not busy)
        self.preview_button.setEnabled(available and installed); self.export_button.setEnabled(available and installed)
        for control in (self.play_button,self.seek,self.start,self.at_playhead,self.length): control.setEnabled(available)

    def shutdown(self):
        self.timer.stop(); self.pause()
        for player in (self.original,self.enhanced): player.setSource(QUrl()); player.setVideoOutput(None)
