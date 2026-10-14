"""Juicy Studio's primary editing workspace."""
import copy
from pathlib import Path
from uuid import uuid4
from PySide6.QtCore import Qt, Signal, QUrl, QRectF
from PySide6.QtGui import QPainter, QPen, QAction, QKeySequence
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QFrame, QSplitter, QListWidget, QListWidgetItem, QSlider, QFileDialog, QMessageBox,
    QDoubleSpinBox, QSpinBox, QTabWidget, QCheckBox, QStyle, QScrollBar, QToolButton, QMenu, QScrollArea)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices
from PySide6.QtMultimediaWidgets import QVideoWidget
import editor_project as project
from subtitle_ui import action, VideoPreview
from subtitle_document import timestamp, new_document
from appearance import color
from video_encoding import CODECS, ENCODER_LABELS
from audio_waveform import WaveformLoader
from playback_controls import VolumeControl
from ui_icons import icon_only, decorate

RULER_HEIGHT = 38
TRACK_HEIGHT = 66
TRACK_STEP = 74


class EditTimeline(QWidget):
    seek = Signal(float)
    selected = Signal(str)
    trimmed = Signal(str, float, float)

    def __init__(self, workspace):
        super().__init__(); self.workspace=workspace; self.zoom=1.; self.offset=0.; self.drag=None
        self.setMinimumHeight(210); self.setMouseTracking(True)
        self.setToolTip('Click to seek. Drag a clip edge to trim. Scroll to zoom; use the scrollbar to pan.')

    @property
    def span(self): return max(1.,project.duration(self.workspace.doc))/self.zoom
    def x(self,time): return 16+(time-self.offset)/self.span*max(1,self.width()-32)
    def time(self,x): return max(0.,min(project.duration(self.workspace.doc),self.offset+(x-16)/max(1,self.width()-32)*self.span))
    def clip_rect(self,start,end,clip=None,kind='video'):
        track_id=project.clip_track(self.workspace.doc,clip or self.workspace.current() or {},kind)
        row=next(i for i,t in enumerate(project.tracks(self.workspace.doc)) if t['id']==track_id)
        return QRectF(self.x(start),RULER_HEIGHT+row*TRACK_STEP,max(1,self.x(end)-self.x(start)),TRACK_HEIGHT)
    def hit(self,pos):
        return next(((c,s,e) for c,s,e in project.spans(self.workspace.doc) if any(self.clip_rect(s,e,c,k).contains(pos) for k in ('video','audio'))),None)
    def paintEvent(self,event):
        painter=QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(),color('background')); painter.setPen(color('muted'))
        for row in range(len(project.tracks(self.workspace.doc))):
            painter.fillRect(QRectF(16,RULER_HEIGHT+row*TRACK_STEP,self.width()-32,TRACK_HEIGHT),color('field'))
        final_label=timestamp(self.offset+self.span).replace(',','.')
        if self.span>=10: final_label=final_label[:-4]
        final_left=self.width()-16-painter.fontMetrics().horizontalAdvance(final_label)-4
        last_right=-100
        for i in range(11):
            t=self.offset+self.span*i/10; x=self.x(t)
            label=timestamp(t).replace(',','.') if self.span<10 else timestamp(t).replace(',','.')[:-4]
            label_width=painter.fontMetrics().horizontalAdvance(label)+4
            if i==10 or (x>=last_right+12 and x+label_width+12<=final_left):
                painter.setPen(color('muted'))
                left=min(x,self.width()-16-label_width)
                painter.drawText(QRectF(left,4,label_width,24),Qt.AlignmentFlag.AlignVCenter,label)
                last_right=left+label_width
            painter.setPen(color('highlight')); painter.drawLine(int(x),30,int(x),self.height()-6)
        painter.setClipRect(QRectF(16,0,max(1,self.width()-32),self.height()))
        for c,start,end in project.spans(self.workspace.doc):
            for kind in ('video','audio'):
                selected=c['id']==self.workspace.selected_id
                painter.setBrush(color('accent') if selected else color('highlight'))
                painter.setPen(QPen(color('accent_text'),2 if selected else 1))
                rect=self.clip_rect(start,end,c,kind); painter.drawRoundedRect(rect.adjusted(1,1,-1,-1),5,5)
                painter.setPen(color('background') if selected else color('text'))
                painter.drawText(rect.adjusted(10,5,-10,-28),Qt.AlignmentFlag.AlignVCenter,
                    painter.fontMetrics().elidedText(Path(self.workspace.doc['media'][c['media']]['path']).name,Qt.TextElideMode.ElideRight,max(1,int(rect.width()-20))))
                painter.drawText(rect.adjusted(10,26,-10,-20),f'{end-start:.2f}s · {c["speed"]:g}×' if kind=='video' else ('Audio' if self.workspace.doc['media'][c['media']]['audio'] else 'Silent'))
                envelope=self.workspace.waveforms.get(self.workspace.doc['media'][c['media']]['path'])
                if envelope and kind=='audio':
                    painter.setPen(QPen(color('on_accent') if selected else color('wave'),1))
                    rate,peaks=envelope['rate'],envelope['peaks']
                    for px in range(max(16,int(rect.left())+8),min(self.width()-16,int(rect.right())-8),3):
                        source=c['in']+(self.offset+(px-16)/max(1,self.width()-32)*self.span-start)*c['speed']
                        lo=max(0,int(source*rate));hi=min(len(peaks),max(lo+1,int((source+3/max(1,self.width()-32)*self.span*c['speed'])*rate)))
                        amplitude=min(1.,max(peaks[lo:hi],default=0)*2.5)*12
                        painter.drawLine(px,int(rect.bottom()-16-amplitude),px,int(rect.bottom()-16+amplitude))
                painter.setPen(QPen(color('accent_text'),2))
                for edge in (rect.left()+5,rect.right()-5): painter.drawLine(int(edge),int(rect.top()+17),int(edge),int(rect.bottom()-18))
        painter.setPen(QPen(color('accent_text'),2)); x=int(self.x(self.workspace.position)); painter.drawLine(x,RULER_HEIGHT-5,x,self.height())
        if not self.workspace.doc['clips']:
            painter.setPen(color('muted')); painter.drawText(QRectF(32,RULER_HEIGHT,self.width()-64,TRACK_HEIGHT),Qt.AlignmentFlag.AlignCenter,'Import videos, then append media to begin your edit')
    def mousePressEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton: return
        found=self.hit(event.position())
        if found:
            c,start,end=found; self.selected.emit(c['id']); kind='audio' if self.clip_rect(start,end,c,'audio').contains(event.position()) else 'video'; rect=self.clip_rect(start,end,c,kind)
            edge='in' if abs(event.position().x()-rect.left())<9 else 'out' if abs(event.position().x()-rect.right())<9 else None
            if edge:self.drag=(copy.deepcopy(c),start,edge,event.position().x()); return
        self.seek.emit(self.time(event.position().x()))
    def mouseMoveEvent(self,event):
        found=self.hit(event.position())
        edge=found and min(abs(event.position().x()-self.x(found[1])),abs(event.position().x()-self.x(found[2])))<9
        self.setCursor(Qt.CursorShape.SizeHorCursor if edge or self.drag else Qt.CursorShape.PointingHandCursor)
    def mouseReleaseEvent(self,event):
        if self.drag:
            c,start,edge,x=self.drag; self.drag=None
            delta=(event.position().x()-x)/max(1,self.width()-32)*self.span*c['speed']
            if edge=='in':c['in']=max(0,min(c['out']-.05,c['in']+delta))
            else:c['out']=min(self.workspace.doc['media'][c['media']]['duration'],max(c['in']+.05,c['out']+delta))
            self.trimmed.emit(c['id'],c['in'],c['out'])
    def wheelEvent(self,event):
        self.zoom=max(1.,min(100.,self.zoom*(1.25 if event.angleDelta().y()>0 else .8)))
        self.workspace.sync_pan(); self.update(); event.accept()


class EditorWorkspace(QWidget):
    job_requested=Signal(dict)
    def __init__(self,host,root,combo,time_edit,splitter):
        super().__init__(); self.host=host; self.root=root; self.combo=combo
        self.doc=project.new_project(); self.history=project.History(); self.path=None
        self.selected_id=None; self.position=0.; self.busy=False; self.loading=False; self.pending=None; self.seek_serial=0
        self.autosave=root/'cache/editor-projects/autosave.juicy'
        self.waveforms={};self.waveform_pending=[];self.waveform_active=None
        self.waveform_loader=WaveformLoader(root,self)
        self.waveform_loader.ready.connect(self.waveform_ready)
        self.waveform_loader.status.connect(self.waveform_status)
        if self.autosave.is_file():
            try:self.doc=project.load(self.autosave)
            except (OSError,ValueError,KeyError,TypeError):pass
        layout=QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.setSpacing(8)
        toolbar=QHBoxLayout()
        self.project_label=QLabel('Untitled edit');self.project_label.setObjectName('paneTitle');toolbar.addWidget(self.project_label)
        toolbar.addStretch()
        self.import_button=action('Import media',self.import_media,'Add video files to the project media bin')
        self.save_button=action('Save project',self.save_project,'Save your non-destructive edit as a .juicy project')
        self.export_button=action('Export edit',self.export,'Render the full timeline to a new MP4 or MKV',True)
        icon_only(self.import_button,'open');icon_only(self.save_button,'save')
        for b in (self.import_button,self.save_button,self.export_button):toolbar.addWidget(b)
        layout.addLayout(toolbar)
        upper=splitter(Qt.Orientation.Horizontal);upper.setChildrenCollapsible(False)
        self.upper=upper
        bin_panel=QFrame();bin_panel.setObjectName('card');bin_layout=QVBoxLayout(bin_panel)
        bin_layout.addWidget(QLabel('Project media'));self.bin=QListWidget();self.bin.itemDoubleClicked.connect(lambda _:self.append_selected());bin_layout.addWidget(self.bin,1)
        bin_layout.addWidget(action('Append to timeline',self.append_selected,'Append the selected source; double-clicking media also appends it'))
        bin_layout.addWidget(action('Relink media…',self.relink,'Choose a replacement location for the selected missing source'))
        self.notes=QLabel();self.notes.setWordWrap(True);self.notes.setObjectName('muted');bin_layout.addWidget(self.notes)
        upper.addWidget(bin_panel)
        preview_panel=QFrame();preview_panel.setObjectName('card');preview_layout=QVBoxLayout(preview_panel)
        self.player=QMediaPlayer(self);self.audio=QAudioOutput(QMediaDevices.defaultAudioOutput(),self);self.audio.setVolume(.65);self.player.setAudioOutput(self.audio)
        self.video=VideoPreview(self.player);self.video.setMinimumSize(240,135);preview_layout.addWidget(self.video,1)
        self.caption_style=new_document()['style']
        transport=QHBoxLayout()
        for icon,tip,callback in ((QStyle.StandardPixmap.SP_MediaSkipBackward,'Go to start',lambda:self.seek(0)),
            (QStyle.StandardPixmap.SP_MediaPlay,'Play or pause the timeline',self.toggle_play),
            (QStyle.StandardPixmap.SP_MediaSkipForward,'Go to end',lambda:self.seek(max(0,project.duration(self.doc)-.04)))):
            b=action('',callback,tip);b.setIcon(host.media_icon(icon));b.setProperty('mediaIcon',icon.value);b.setFixedWidth(36);transport.addWidget(b)
            if icon==QStyle.StandardPixmap.SP_MediaPlay:self.play_button=b
        self.clock=QLabel();transport.addWidget(self.clock,1)
        self.volume_control=VolumeControl(self,host,self.preview_volume)
        self.volume=self.volume_control.slider;self.volume_button=self.volume_control.button
        transport.addWidget(self.volume_button)
        preview_layout.addLayout(transport);upper.addWidget(preview_panel)
        inspector=QTabWidget();self.inspector=inspector;inspector.setMinimumWidth(240)
        clip_page=QWidget();form=QFormLayout(clip_page)
        self.start=time_edit();self.end=time_edit();form.addRow('Source start',self.start);form.addRow('Source end',self.end)
        self.track_choices={}
        for kind in ('video','audio'):
            field=combo();self.track_choices[kind]=field;form.addRow(kind.title()+' track',field)
        self.speed=QDoubleSpinBox();self.speed.setRange(.25,4);self.speed.setSingleStep(.25);self.speed.setSuffix('×');self.speed.setValue(1);form.addRow('Speed',self.speed)
        self.gain=QDoubleSpinBox();self.gain.setRange(0,400);self.gain.setSuffix('%');self.gain.setValue(100);form.addRow('Clip volume',self.gain)
        form.addRow(action('Apply clip changes',self.apply_clip,'Apply trim, speed and volume; the following clips move to keep the timeline continuous'))
        form.addRow(action('Subtitles & Translation…',lambda:host.select_workspace(1),'Edit subtitles for this entire project; changes return automatically'))
        form.addRow(action('Censor project…',lambda:host.select_workspace(0),'Add or analyze censor regions on the edited timeline'))
        inspector.addTab(clip_page,'Clip')
        color_page=QWidget();color_form=QFormLayout(color_page);self.colors={}
        for label,key,lo,hi,default in [('Brightness','brightness',-.5,.5,0),('Contrast','contrast',.5,2,1),('Saturation','saturation',0,2,1)]:
            field=QDoubleSpinBox();field.setRange(lo,hi);field.setDecimals(2);field.setSingleStep(.05);field.setValue(default);self.colors[key]=field;color_form.addRow(label,field)
        color_form.addRow(action('Apply color',self.apply_clip,'Save color adjustments for export. The source preview shows original color.'))
        hint=QLabel('Color adjustments apply to export. Source preview shows the original picture.');hint.setWordWrap(True);hint.setObjectName('muted');color_form.addRow(hint);inspector.addTab(color_page,'Color')
        output_page=QWidget();out=QFormLayout(output_page)
        self.resolution=combo()
        for label,size in [('720p',(1280,720)),('1080p',(1920,1080)),('1440p / QHD',(2560,1440)),('4K / UHD',(3840,2160)),('Portrait 1080p',(1080,1920))]:self.resolution.addItem(label,size)
        out.addRow('Canvas',self.resolution)
        self.fps=QDoubleSpinBox();self.fps.setRange(1,120);self.fps.setDecimals(3);self.fps.setValue(30);out.addRow('Frame rate',self.fps)
        self.codec=combo()
        for key,(label,_) in CODECS.items():self.codec.addItem(label,key)
        out.addRow('Codec',self.codec);self.encoder=combo();out.addRow('Encoder',self.encoder);self.codec.currentIndexChanged.connect(self.populate_encoders);self.populate_encoders()
        self.quality=QSpinBox();self.quality.setRange(0,51);self.quality.setValue(23);self.quality.setToolTip('Lower values retain more detail and create larger files.');out.addRow('Quality',self.quality)
        self.preset=combo()
        for label,value in [('Fast','fast'),('Balanced','medium'),('Slow','slow')]:self.preset.addItem(label,value)
        self.preset.setCurrentIndex(1);out.addRow('Encoding speed',self.preset)
        self.audio_bitrate=combo()
        for n in (128,192,256,320):self.audio_bitrate.addItem(f'{n} kbps',n)
        self.audio_bitrate.setCurrentIndex(3);out.addRow('Stereo AAC',self.audio_bitrate)
        self.burn=QCheckBox('Burn attached subtitles');self.burn.setChecked(True);out.addRow(self.burn)
        self.mute=QCheckBox('Apply project censor regions');self.mute.setToolTip('Uses the censor style chosen in Censor, including generated or custom beeps.');self.mute.setChecked(True);out.addRow(self.mute)
        out.addRow(action('Apply canvas',self.apply_output,'Fit clips to this canvas with letterboxing; no stretching'))
        inspector.addTab(output_page,'Output');upper.addWidget(inspector);upper.setStretchFactor(1,1);upper.setSizes([240,650,290])
        split=splitter(Qt.Orientation.Vertical);split.setChildrenCollapsible(False);split.addWidget(upper)
        timeline_panel=QFrame();timeline_panel.setObjectName('card');tl=QVBoxLayout(timeline_panel);tools=QHBoxLayout()
        self.edit_buttons=[]
        for name,callback,tip in [('Undo',self.undo,'Undo the last project change'),('Redo',self.redo,'Redo a project change'),('Split',self.split_clip,'Split the selected clip at the playhead'),('Remove',self.remove_clip,'Remove the selected clip and close the gap'),('Move left',lambda:self.move_clip(-1),'Move the selected clip earlier'),('Move right',lambda:self.move_clip(1),'Move the selected clip later')]:
            b=icon_only(action(name,callback,tip),{'Undo':'undo','Redo':'redo','Split':'split','Remove':'trash','Move left':'move_left','Move right':'move_right'}[name]);self.edit_buttons.append(b);tools.addWidget(b)
        tools.addStretch()
        for icon,callback,tip in [('zoom_out',lambda:self.zoom(.8),'Zoom out'),('zoom_in',lambda:self.zoom(1.25),'Zoom in'),('fit',lambda:self.zoom(0),'Fit timeline to available width')]:tools.addWidget(icon_only(action('',callback,tip),icon))
        tl.addLayout(tools)
        self.timeline=EditTimeline(self);self.timeline.seek.connect(self.seek);self.timeline.selected.connect(self.select_clip);self.timeline.trimmed.connect(self.trim_clip)
        track_row=QHBoxLayout();track_row.setContentsMargins(0,0,0,0);track_row.setSpacing(0)
        self.track_headers=QWidget();self.track_headers.setFixedWidth(166);self.track_header_layout=QVBoxLayout(self.track_headers);self.track_header_layout.setContentsMargins(0,0,8,0);self.track_header_layout.setSpacing(0)
        track_row.addWidget(self.track_headers);track_row.addWidget(self.timeline,1)
        track_content=QWidget();track_content.setLayout(track_row);self.track_scroll=QScrollArea();self.track_scroll.setWidgetResizable(True);self.track_scroll.setFrameShape(QFrame.Shape.NoFrame);self.track_scroll.setMinimumHeight(210);self.track_scroll.setWidget(track_content);tl.addWidget(self.track_scroll)
        self.pan=QScrollBar(Qt.Orientation.Horizontal);self.pan.setRange(0,10000);self.pan.valueChanged.connect(self.pan_changed);tl.addWidget(self.pan)
        split.addWidget(timeline_panel);split.setStretchFactor(0,3);split.setStretchFactor(1,1);layout.addWidget(split,1)
        self.player.mediaStatusChanged.connect(self.media_loaded);self.player.positionChanged.connect(self.playback_position)
        self.player.playbackStateChanged.connect(self.play_state);self.player.errorOccurred.connect(lambda _,text:host.set_status('Editor preview: '+text))
        for shortcut,callback in [('Space',self.toggle_play),('S',self.split_clip),('Delete',self.remove_clip)]:
            command=QAction(self);command.setShortcut(QKeySequence(shortcut));command.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut);command.triggered.connect(callback);self.addAction(command)
        for field in (self.codec,self.encoder,self.preset,self.audio_bitrate):field.currentIndexChanged.connect(self.remember_export_settings)
        self.quality.valueChanged.connect(self.remember_export_settings)
        for field in (self.burn,self.mute):field.toggled.connect(self.remember_export_settings)
        self.refresh()

    def refresh_tracks(self):
        while self.track_header_layout.count():
            item=self.track_header_layout.takeAt(0)
            if item.widget():item.widget().deleteLater()
        for kind,field in self.track_choices.items():
            field.clear()
            for track in project.tracks(self.doc):
                if track['kind']==kind:field.addItem(track['name'],track['id'])
        heading=QLabel('Tracks');heading.setObjectName('muted');heading.setFixedHeight(RULER_HEIGHT);heading.setContentsMargins(8,0,0,0);self.track_header_layout.addWidget(heading)
        self.track_rows=[]
        for track in project.tracks(self.doc):
            row=QWidget();row.setFixedHeight(TRACK_STEP);layout=QHBoxLayout(row);layout.setContentsMargins(8,0,0,TRACK_STEP-TRACK_HEIGHT);layout.setSpacing(6)
            label=QLabel(track['name']);label.setToolTip(track['name']);layout.addWidget(label,1)
            plus=action('+',lambda checked=False,k=track['kind']:self.add_track(k),'Add another '+track['kind']+' track');plus.setText('');decorate(plus,'plus');plus.setObjectName('trackButton');plus.setFixedSize(26,26);layout.addWidget(plus)
            remove=action('×',lambda checked=False,i=track['id']:self.delete_track(i),'Remove this track; clips move to the first remaining track of the same type');remove.setText('');decorate(remove,'cancel');remove.setObjectName('trackButton');remove.setFixedSize(26,26)
            remove.setEnabled(sum(t['kind']==track['kind'] for t in project.tracks(self.doc))>1);layout.addWidget(remove)
            self.track_rows.append(row);self.track_header_layout.addWidget(row)
        self.track_header_layout.addStretch()
        height=RULER_HEIGHT+TRACK_STEP*len(project.tracks(self.doc))
        self.track_headers.setMinimumHeight(height);self.timeline.setMinimumHeight(height)
    def add_track(self,kind):
        if self.busy:return
        self.history.record(self.doc);project.add_track(self.doc,kind);self.changed()
    def delete_track(self,track_id):
        if self.busy:return
        track=next(t for t in project.tracks(self.doc) if t['id']==track_id)
        if any(project.clip_track(self.doc,c,track['kind'])==track_id for c in self.doc['clips']):
            if QMessageBox.question(self,'Remove track','Move the clips to the first remaining '+track['kind']+' track and remove this track? Timing and media are preserved.')!=QMessageBox.StandardButton.Yes:return
        draft=copy.deepcopy(self.doc)
        try:project.remove_track(draft,track_id)
        except ValueError as exc:self.host.set_status(str(exc));return
        self.history.record(self.doc);self.doc=draft;self.changed()

    def populate_encoders(self):
        self.encoder.clear();self.encoder.addItem('Automatic · best available',{'h264':'auto','hevc':'auto_hevc','av1':'auto_av1'}[self.codec.currentData()])
        for encoder in CODECS[self.codec.currentData()][1]:self.encoder.addItem(ENCODER_LABELS.get(encoder.rsplit('_',1)[-1],ENCODER_LABELS.get(encoder,encoder)),encoder)
    def current(self):return next((c for c in self.doc['clips'] if c['id']==self.selected_id),None)
    def changed(self):
        project.validate(self.doc)
        try:project.save(self.doc,self.autosave)
        except OSError as exc:self.host.set_status('Could not autosave edit: '+str(exc))
        self.player.pause();self.refresh();self.seek(min(self.position,max(0,project.duration(self.doc)-.001)))
        if not self.doc['clips'] and hasattr(self.host,'project_session'):self.host.project_session.leave()
    def refresh(self):
        self.bin.clear()
        missing=0
        for key,media in self.doc['media'].items():
            exists=Path(media['path']).is_file();missing+=not exists
            item=QListWidgetItem(('Missing · ' if not exists else '')+Path(media['path']).name+f'\n{media["width"]} × {media["height"]} · {media["duration"]:.1f}s');item.setData(Qt.ItemDataRole.UserRole,key);item.setToolTip(media['path']);self.bin.addItem(item)
        if self.bin.count():self.bin.setCurrentRow(0)
        self.project_label.setText(self.doc['name']);self.notes.setText(f'{len(self.doc["media"])} sources · {len(self.doc["clips"])} clips'+(f' · {missing} missing' if missing else ''))
        self.loading=True
        self.resolution.setCurrentIndex(max(0,self.resolution.findData((self.doc['output']['width'],self.doc['output']['height']))));self.fps.setValue(self.doc['output']['fps'])
        settings=self.doc.get('export',{})
        if settings:
            codec=next((k for k,(_,encoders) in CODECS.items() if settings['encoder'] in encoders),{'auto':'h264','auto_hevc':'hevc','auto_av1':'av1'}.get(settings['encoder'],'h264'))
            self.codec.setCurrentIndex(max(0,self.codec.findData(codec)))
            self.encoder.setCurrentIndex(max(0,self.encoder.findData(settings['encoder'])))
            self.quality.setValue(settings['quality']);self.preset.setCurrentIndex(max(0,self.preset.findData(settings['preset'])));self.audio_bitrate.setCurrentIndex(max(0,self.audio_bitrate.findData(settings['audio_bitrate'])))
            self.burn.setChecked(settings.get('burn_subtitles',True));self.mute.setChecked(settings.get('mute_censors',True))
        self.loading=False
        self.refresh_tracks();self.select_clip(self.selected_id);self.sync_pan();self.update_clock();self.timeline.update();self.set_busy(self.busy)
        self.load_waveforms()
    def load_waveforms(self):
        for media in self.doc['media'].values():
            path=media['path']
            if media['audio'] and Path(path).is_file() and path not in self.waveforms and path not in self.waveform_pending and path!=self.waveform_active:self.waveform_pending.append(path)
        if self.waveform_active is None and self.waveform_pending:
            self.waveform_active=self.waveform_pending.pop(0);self.waveform_loader.load(self.waveform_active)
    def waveform_ready(self,path,data):
        self.waveforms[path]=data;self.waveform_active=None;self.timeline.update();self.load_waveforms()
    def waveform_status(self,path,message):
        if message!='Reading audio…':
            self.waveforms[path]={'rate':100,'peaks':[]};self.waveform_active=None;self.load_waveforms()
    def select_clip(self,clip_id):
        self.selected_id=clip_id;clip=self.current();self.inspector.widget(0).setEnabled(bool(clip));self.inspector.widget(1).setEnabled(bool(clip))
        if clip:
            for kind,field in self.track_choices.items():field.setCurrentIndex(max(0,field.findData(project.clip_track(self.doc,clip,kind))))
            self.start.setValue(clip['in']);self.end.setValue(clip['out']);self.speed.setValue(clip['speed']);self.gain.setValue(clip['gain']*100)
            for key,field in self.colors.items():field.setValue(clip.get('color',{}).get(key,0 if key=='brightness' else 1))
        self.timeline.update()
    def import_media(self,paths=None,append=False):
        if self.busy:return
        if not paths:paths,_=QFileDialog.getOpenFileNames(self,'Import media','','Video files (*.mp4 *.mkv *.mov *.webm *.avi *.m4v);;All files (*)')
        if paths:self.job_requested.emit({'action':'editor_import','paths':paths,'append':append})
    def receive(self,data):
        if data['type']=='editor_media':
            relink_id=self.host.job.get('relink_id')
            if relink_id:
                media=data['media'][0]
                if any(c['out']>media['duration']+.001 for c in self.doc['clips'] if c['media']==relink_id):
                    self.host.set_status('Replacement source is shorter than an existing trim. Choose the original media.');return
                self.history.record(self.doc)
                old=self.doc['media'][relink_id];self.doc['media'][relink_id]=dict(old,**media);self.changed();return
            self.history.record(self.doc)
            for media in data['media']:
                key=project.add_media(self.doc,media)
                if self.host.job.get('append'):self.selected_id=project.append_clip(self.doc,key)
            self.host.project_session.inherit_sources()
            self.changed();self.host.set_status('Media imported. Double-click a source to append it to the timeline.')
        elif data['type']=='editor_exported':
            self.host.last_output=data['output'];self.host.set_status('Edit exported: '+Path(data['output']).name)
    def append_selected(self):
        if not self.bin.currentItem() or self.busy:return
        self.history.record(self.doc);self.selected_id=project.append_clip(self.doc,self.bin.currentItem().data(Qt.ItemDataRole.UserRole));self.changed()
    def apply_clip(self):
        if self.busy:return
        clip=self.current()
        if not clip:return
        draft=copy.deepcopy(self.doc);target=next(c for c in draft['clips'] if c['id']==clip['id'])
        target.update({kind+'_track':field.currentData() for kind,field in self.track_choices.items()})
        target.update({'in':self.start.value(),'out':self.end.value(),'speed':self.speed.value(),'gain':self.gain.value()/100,'color':{k:f.value() for k,f in self.colors.items()}})
        try:project.validate(draft)
        except ValueError as exc:self.host.set_status(str(exc));return
        self.history.record(self.doc);self.doc=draft;self.changed()
    def trim_clip(self,clip_id,start,end):
        self.select_clip(clip_id);self.start.setValue(start);self.end.setValue(end);self.apply_clip()
    def split_clip(self):
        if self.busy:return
        draft=copy.deepcopy(self.doc)
        try:selected=project.split(draft,self.selected_id,self.position)
        except ValueError as exc:self.host.set_status(str(exc));return
        self.history.record(self.doc);self.doc=draft;self.selected_id=selected;self.changed()
    def remove_clip(self):
        if self.busy:return
        if not self.current():return
        self.history.record(self.doc);self.doc['clips']=[c for c in self.doc['clips'] if c['id']!=self.selected_id];self.selected_id=None;self.changed()
    def move_clip(self,direction):
        if self.busy:return
        clip=self.current()
        if not clip:return
        i=self.doc['clips'].index(clip);j=i+direction
        if not 0<=j<len(self.doc['clips']):return
        self.history.record(self.doc);self.doc['clips'][i],self.doc['clips'][j]=self.doc['clips'][j],clip;self.changed()
    def undo(self):
        if self.busy:return
        if self.host.workspaces.currentIndex()==1:
            if not self.host.subtitles.commit_edit():return
            self.host.subtitles.edit_timer.stop()
        self.doc=self.history.undo(self.doc);self.changed()
        if self.host.workspaces.currentIndex()!=3:self.host.project_session.prepare()
    def redo(self):
        if self.busy:return
        if self.host.workspaces.currentIndex()==1:
            if not self.host.subtitles.commit_edit():return
            self.host.subtitles.edit_timer.stop()
        self.doc=self.history.redo(self.doc);self.changed()
        if self.host.workspaces.currentIndex()!=3:self.host.project_session.prepare()
    def apply_output(self):
        if self.busy:return
        self.history.record(self.doc);w,h=self.resolution.currentData();self.doc['output']={'width':w,'height':h,'fps':self.fps.value()};self.changed()
    def attach_subtitles(self):
        clip=self.current()
        if not clip:return
        if not self.host.subtitles.commit_edit():return
        media=self.doc['media'][clip['media']]
        if Path(self.host.subtitles.video_path or '.')!=Path(media['path']):self.host.set_status('Open this source in Subtitles & Translation first.');return
        track=self.host.subtitles.preview_track.currentData();track='translation' if track=='translation' else 'source'
        self.history.record(self.doc);media['subtitles']=[{'start':c['start'],'end':c['end'],'text':c.get(track,'')} for c in self.host.subtitles.doc['cues'] if c.get(track,'')];self.changed()
        self.host.set_status('Subtitles attached to the source. They follow every edit and can be burned during export.')
    def open_source_workspace(self,index):
        clip=self.current()
        if not clip:return
        path=self.doc['media'][clip['media']]['path'];self.host.add_paths([path])
        if path in self.host.queue_paths:self.host.queue.setCurrentRow(self.host.queue_paths.index(path))
        self.host.select_workspace(index)
    def attach_censors(self):
        clip=self.current();state=self.host.state
        if not clip or not state:return
        media=self.doc['media'][clip['media']]
        if Path(state['video'])!=Path(media['path']):self.host.set_status('Analyze this source in Censor first.');return
        self.history.record(self.doc);media['censors']=copy.deepcopy(state['events']);self.changed();self.host.set_status('Censor regions attached. Enable muting in Output to apply them on export.')
    def relink(self):
        if self.busy:return
        item=self.bin.currentItem()
        if not item:return
        path,_=QFileDialog.getOpenFileName(self,'Relink media')
        if not path:return
        # Probe before accepting a replacement; never silently use a shorter source.
        self.relink_id=item.data(Qt.ItemDataRole.UserRole);self.job_requested.emit({'action':'editor_import','paths':[path],'relink_id':self.relink_id})
    def new_project(self):
        if self.busy:return
        if self.doc['clips'] and QMessageBox.question(self,'New project','The current edit is autosaved. Start a new project?')!=QMessageBox.StandardButton.Yes:return
        if not self.archive_current():return
        self.history=project.History();self.doc=project.new_project();self.path=None;self.selected_id=None;self.position=0;self.changed()
    def archive_current(self):
        if self.doc['media']:
            try:project.save(self.doc,self.root/'cache/editor-projects/recovery'/(uuid4().hex+'.juicy'))
            except OSError as exc:self.host.set_status('Could not preserve the current edit: '+str(exc));return False
        return True
    def open_project(self,recovery=False):
        if self.busy:return
        path,_=QFileDialog.getOpenFileName(self,'Recover edit' if recovery else 'Open editing project',str(self.root/'cache/editor-projects/recovery' if recovery else self.root/'outputs'),'Juicy Studio projects (*.juicy)')
        if not path:return
        self.open_project_path(path,recovery)
    def open_project_path(self,path,recovery=False):
        if self.busy:return
        try:doc=project.load(path)
        except (OSError,ValueError,KeyError,TypeError) as exc:self.host.set_status('Could not open project: '+str(exc));return
        if not self.archive_current():return
        self.history=project.History();self.doc=doc;self.path=None if recovery else Path(path);self.selected_id=None;self.position=0;self.changed()
        self.host.project_session.leave()
        from project_library import remember
        if not recovery:remember(self.root,path)
    def projects(self):
        if self.busy:return
        if not self.host.subtitles.commit_edit():return
        from project_browser import ProjectBrowser
        dialog=ProjectBrowser(self)
        if dialog.exec() and dialog.choice:
            path,recovery=dialog.choice
            self.host.select_workspace(3)
            if path=='new':self.new_project()
            else:self.open_project_path(path,recovery)
    def save_project(self):
        if not self.path:
            folder=self.root/'projects'
            try:folder.mkdir(parents=True,exist_ok=True)
            except OSError as exc:self.host.set_status('Could not create the project folder: '+str(exc));return
            path,_=QFileDialog.getSaveFileName(self,'Save editing project',str(folder/'Untitled.juicy'),'Juicy Studio projects (*.juicy)')
            if not path:return
            self.path=Path(path).with_suffix('.juicy')
        self.doc['name']=self.path.stem
        self.doc['export']=self.export_settings()
        try:
            project.save(self.doc,self.path)
            from project_library import remember
            project.save(self.doc,self.autosave);remember(self.root,self.path);self.refresh();self.host.set_status('Project saved.')
        except (OSError,ValueError) as exc:self.host.set_status('Could not save project: '+str(exc))
    def seek(self,time,play=False):
        self.seek_serial+=1
        self.position=time;found=project.locate(self.doc,time);self.timeline.update();self.update_clock()
        if not found:self.player.stop();self.player.setSource(QUrl());return
        clip,source=found;path=self.doc['media'][clip['media']]['path'];self.playing_clip=clip['id'];self.player.setPlaybackRate(clip['speed'])
        self.preview_volume()
        self.update_caption()
        if self.player.source().toLocalFile()!=path:
            self.pending=(round(source*1000),play);self.player.setSource(QUrl.fromLocalFile(path))
        else:
            self.pending=None;self.player.setPosition(round(source*1000))
            if play:self.player.play()
    def media_loaded(self,status):
        if status==QMediaPlayer.MediaStatus.LoadedMedia and self.pending:
            # A new source can report LoadedMedia synchronously while Qt is
            # still replacing its decoder. Seeking/playing reentrantly there
            # can leave it playing at zero without producing frames.
            from PySide6.QtCore import QTimer
            serial=self.seek_serial
            def resume():
                if serial!=self.seek_serial or not self.pending:return
                ms,play=self.pending;self.pending=None;self.player.setPosition(ms)
                if play:self.player.play()
            QTimer.singleShot(0,resume)
        elif status==QMediaPlayer.MediaStatus.EndOfMedia:
            found=next(((c,s,e) for c,s,e in project.spans(self.doc) if c['id']==getattr(self,'playing_clip',None)),None)
            if found and found[2]<project.duration(self.doc)-.001:self.seek(found[2]+.001,True)
            else:self.position=project.duration(self.doc);self.update_clock();self.timeline.update()
    def toggle_play(self):
        if self.player.playbackState()==QMediaPlayer.PlaybackState.PlayingState:self.player.pause()
        elif self.doc['clips']:self.seek(0 if self.position>=project.duration(self.doc)-.02 else self.position,True)
    def playback_position(self,ms):
        if self.pending or self.player.playbackState()!=QMediaPlayer.PlaybackState.PlayingState:return
        found=next(((c,s,e) for c,s,e in project.spans(self.doc) if c['id']==getattr(self,'playing_clip',None)),None)
        if not found:return
        c,start,end=found
        if ms/1000>=c['out']-.015:
            if end<project.duration(self.doc)-.001:self.seek(end+.001,True)
            else:self.player.pause();self.position=project.duration(self.doc)
        else:self.position=start+(ms/1000-c['in'])/c['speed']
        self.update_clock();self.timeline.update()
        self.update_caption()
    def preview_volume(self,*_):
        found=project.locate(self.doc,self.position)
        self.audio.setVolume(min(1.,self.volume.value()/100*(found[0]['gain'] if found else 1.)))
    def update_caption(self):
        track=self.doc.get('subtitle_track','source')
        self.video.set_caption('\n'.join(e.get(track,e.get('text','')) for e in project.mapped_annotations(self.doc,'subtitles') if e['start']<=self.position<e['end']),self.doc.get('subtitle_settings',{}).get('style',self.caption_style))
    def play_state(self,*_):
        self.play_button.setIcon(self.host.media_icon(QStyle.StandardPixmap.SP_MediaPause if self.player.playbackState()==QMediaPlayer.PlaybackState.PlayingState else QStyle.StandardPixmap.SP_MediaPlay))
    def update_clock(self):self.clock.setText(timestamp(self.position).replace(',','.')+' / '+timestamp(project.duration(self.doc)).replace(',','.'))
    def pan_changed(self,value):self.timeline.offset=value/10000*max(0,project.duration(self.doc)-self.timeline.span);self.timeline.update()
    def sync_pan(self):self.timeline.offset=min(self.timeline.offset,max(0,project.duration(self.doc)-self.timeline.span));self.pan.setEnabled(self.timeline.zoom>1);self.pan.blockSignals(True);self.pan.setValue(round(self.timeline.offset/max(.001,project.duration(self.doc)-self.timeline.span)*10000));self.pan.blockSignals(False)
    def zoom(self,factor):self.timeline.zoom=1 if not factor else max(1,min(100,self.timeline.zoom*factor));self.sync_pan();self.timeline.update()
    def set_busy(self,busy):
        self.busy=busy
        for widget in (self.import_button,self.bin,self.inspector,self.timeline,*self.edit_buttons):widget.setEnabled(not busy)
        self.export_button.setEnabled(not busy and bool(self.doc['clips']));self.save_button.setEnabled(not busy)
    def export(self):
        if not self.doc['clips'] or self.busy:return
        path,_=QFileDialog.getSaveFileName(self,'Export timeline',str(self.root/'outputs'/'studio-edit.mp4'),'MP4 video (*.mp4);;MKV video (*.mkv)')
        if not path:return
        if Path(path).exists():self.host.set_status('Choose a new export filename.');return
        self.doc['export']=self.export_settings()
        self.job_requested.emit({'action':'editor_export','project':copy.deepcopy(self.doc),'output':path,'partial_token':uuid4().hex,
            'burn_subtitles':self.burn.isChecked(),'mute_censors':self.mute.isChecked(),
            'encoding':self.export_settings()})
    def export_settings(self):return {'encoder':self.encoder.currentData(),'quality':self.quality.value(),'preset':self.preset.currentData(),'audio_bitrate':self.audio_bitrate.currentData(),'burn_subtitles':self.burn.isChecked(),'mute_censors':self.mute.isChecked()}
    def remember_export_settings(self,*_):
        if not self.loading:
            self.doc['export']=self.export_settings()
            try:project.save(self.doc,self.autosave)
            except OSError as exc:self.host.set_status('Could not save export preferences: '+str(exc))
    def shutdown(self):self.waveform_pending.clear();self.waveform_loader.close();self.player.stop();self.player.setSource(QUrl());self.player.setVideoOutput(None)
