"""One project shared by the editing, dialogue and enhancement workspaces."""
import copy
import hashlib
import json
from pathlib import Path
from uuid import uuid4
from PySide6.QtCore import QUrl
import editor_project as model
from subtitle_document import new_document, cue
CENSOR_SETTINGS=('censor_mode','beep_file','beep_frequency','beep_volume','pulse_on','pulse_off')


class ProjectSession:
    def __init__(self,host,root):
        self.host,self.root=host,root
        self.path=None;self.key=None;self.preparing=False;self.syncing=False
        self.subtitle_signature=None

    def matches(self,path):return bool(self.path and path and Path(path)==Path(self.path) and not self.syncing)

    def persist(self,before):
        editor=self.host.editor
        if before==editor.doc:return
        editor.history.record(before)
        model.validate(editor.doc);model.save(editor.doc,editor.autosave)
        editor.refresh()

    def sync_censors(self,state):
        if self.syncing or not state:return
        editor=self.host.editor;before=copy.deepcopy(editor.doc)
        if self.matches(state['video']):
            model.replace_timeline_annotations(editor.doc,'censors',state['events'])
            model.replace_timeline_annotations(editor.doc,'words',state.get('words',[]))
        else:
            for media in editor.doc['media'].values():
                if Path(media['path'])==Path(state['video']):
                    media['censors']=copy.deepcopy(state['events']);media['words']=copy.deepcopy(state.get('words',[]))
        if before!=editor.doc or self.matches(state['video']):
            editor.doc['censor_settings']={k:self.host.config[k] for k in CENSOR_SETTINGS if k in self.host.config}
            editor.doc['censor_settings']['censor_mode']=self.host.mode.currentData()
            self.persist(before)

    def sync_subtitles(self,document):
        if self.syncing:return
        editor=self.host.editor;before=copy.deepcopy(editor.doc)
        if self.matches(document.get('video')):
            model.replace_timeline_annotations(editor.doc,'subtitles',document['cues'])
        else:
            for media in editor.doc['media'].values():
                if Path(media['path'])==Path(document.get('video','')):media['subtitles']=copy.deepcopy(document['cues'])
        if before!=editor.doc or self.matches(document.get('video')):
            editor.doc['subtitle_settings']={k:copy.deepcopy(v) for k,v in document.items() if k not in ('video','cues')}
            editor.doc['subtitle_track']='translation' if self.host.subtitles.preview_track.currentData()=='translation' else 'source'
            self.persist(before)
            self.subtitle_signature=self.subtitles_signature()

    def subtitles_signature(self):
        doc=self.host.editor.doc
        return json.dumps([model.mapped_annotations(doc,'subtitles'),doc.get('subtitle_settings',{})],sort_keys=True)

    def inherit_sources(self):
        for media in self.host.editor.doc['media'].values():
            saved=self.host.reviews.get(media['path'])
            if saved:
                media['censors']=copy.deepcopy(saved[0]['events']);media['words']=copy.deepcopy(saved[0].get('words',[]))
                self.host.editor.doc['censor_settings']={k:self.host.config[k] for k in CENSOR_SETTINGS if k in self.host.config}
                self.host.editor.doc['censor_settings']['censor_mode']=self.host.mode.currentData()
            if self.host.subtitles.video_path==media['path']:
                media['subtitles']=copy.deepcopy(self.host.subtitles.doc['cues'])
                self.host.editor.doc['subtitle_settings']={k:copy.deepcopy(v) for k,v in self.host.subtitles.doc.items() if k not in ('video','cues')}
                self.host.editor.doc['subtitle_track']='translation' if self.host.subtitles.preview_track.currentData()=='translation' else 'source'

    def prepare(self):
        doc=self.host.editor.doc
        if not doc['clips']:return False
        try:key=model.view_key(doc)
        except OSError as exc:self.host.set_status('Relink missing project media before opening its tools: '+str(exc));return True
        if len(doc['clips'])==1:
            clip=doc['clips'][0];media=doc['media'][clip['media']]
            neutral=all(clip.get('color',{}).get(k,v)==v for k,v in (('brightness',0),('contrast',1),('saturation',1)))
            if clip['in']==0 and abs(clip['out']-media['duration'])<.001 and clip['speed']==1 and clip['gain']==1 and neutral:
                self.key=key;self.load_views(media['path']);return True
        target=self.root/'cache/project-playback'/('project-'+key+'.mkv')
        if target.is_file():
            self.key=key;self.load_views(str(target));return True
        if self.host.process is not None:
            self.host.set_status('Finish or cancel processing before changing the project workspace.');return True
        self.preparing=True;self.path=None
        self.host.player.stop();self.host.player.setSource(QUrl());self.host.subtitles.clear_video();self.host.enhance.clear_video()
        self.host.state=None;self.host.refresh_regions()
        self.host.filename.setText('Project · '+doc['name']+' · preparing playback')
        self.host.start_job({'action':'editor_materialize','project':copy.deepcopy(doc),'output':str(target),
                             'key':key,'partial_token':uuid4().hex})
        return True

    def materialized(self,data):
        self.preparing=False;self.key=data['key'];self.load_views(data['output'])
        self.host.set_status('Project ready. Changes in these tools return to the same editing timeline.')

    def load_views(self,path):
        self.syncing=True
        try:
            old=self.path;self.path=path;doc=self.host.editor.doc;host=self.host
            host.config.update({k:v for k,v in doc.get('censor_settings',{}).items() if k in CENSOR_SETTINGS})
            if doc.get('censor_settings',{}).get('censor_mode'):
                host.mode.setCurrentIndex(max(0,host.mode.findData(doc['censor_settings']['censor_mode'])))
            host.invalidate_preview(switch=False)
            host.player.setSource(QUrl.fromLocalFile(path))
            stat=Path(path).stat();fingerprint=hashlib.sha256(f'{Path(path).resolve()}|{stat.st_size}|{stat.st_mtime_ns}'.encode()).hexdigest()[:16]
            host.state={'video':path,'duration':model.duration(doc),'fingerprint':fingerprint,
                'events':[dict(e,matched=e.get('matched','Censor region'),kind=e.get('kind','manual'),source=e.get('source','manual')) for e in model.mapped_annotations(doc,'censors')],'words':model.mapped_annotations(doc,'words'),
                'word_count':len(model.mapped_annotations(doc,'words')),'backend':'project','config':host.config,'schema':3}
            host.state_path=str(self.root/'cache/project-reviews'/(self.key+'.json'))
            host.filename.setText('Project · '+doc['name']);host.filename.setToolTip('Shared editing project')
            signature=self.subtitles_signature()
            if old!=path or host.subtitles.video_path!=path or signature!=self.subtitle_signature:
                host.subtitles.edit_timer.stop()
                host.subtitles.load_video(path)
                subtitle_doc=new_document(path);subtitle_doc.update(copy.deepcopy(doc.get('subtitle_settings',{})))
                for item in model.mapped_annotations(doc,'subtitles'):
                    if round(item['end'],3)<=round(item['start'],3):continue
                    value=cue(item['start'],item['end'],item.get('source',item.get('text','')),item.get('translation',''))
                    value.update({k:v for k,v in item.items() if k not in ('start','end')})
                    subtitle_doc['cues'].append(value)
                host.subtitles.doc=subtitle_doc;host.subtitles.refresh();self.subtitle_signature=signature
                host.subtitles.preview_track.setCurrentIndex(max(0,host.subtitles.preview_track.findData(doc.get('subtitle_track','source'))))
            if host.enhance.video_path!=path:host.enhance.load_video(path)
            host.refresh_regions();host.waveform.load(path)
            host.queue_dock.hide();host.queue_toggle.hide()
        finally:self.syncing=False
        if self.host.workspaces.currentIndex()==1:self.host.subtitles.activate_preview()

    def leave(self):self.path=None;self.key=None;self.subtitle_signature=None

    def enhanced_result(self,data):
        if not self.matches(self.host.enhance.video_path):return
        self.host.editor.doc['enhancement_export']=dict(data,key=model.view_key(self.host.editor.doc))
        model.save(self.host.editor.doc,self.host.editor.autosave)

    def can_apply_enhancement(self):
        result=self.host.editor.doc.get('enhancement_export',{})
        try:return bool(result and Path(result['output']).is_file() and result['key']==model.view_key(self.host.editor.doc))
        except (OSError,KeyError):return False

    def apply_enhancement(self):
        if self.host.process or not self.can_apply_enhancement():
            self.host.set_status('Export an enhanced version of the current project first.');return
        editor=self.host.editor;before=copy.deepcopy(editor.doc);data=editor.doc['enhancement_export']
        length=min(model.duration(editor.doc),data['length'])
        annotations={kind:model.mapped_annotations(editor.doc,kind) for kind in ('subtitles','censors','words')}
        source_audio=any(editor.doc['media'][c['media']]['audio'] for c in editor.doc['clips'])
        encoder=data.get('encoder','h264')
        codec='hevc' if 'hevc' in encoder or '265' in encoder else 'av1' if 'av1' in encoder else 'h264'
        media={'path':str(Path(data['output']).resolve()),'duration':data['length'],'width':data['width'],'height':data['height'],
               'audio':source_audio,'video_stream':0,'video_codec':codec,'transfer':'',**annotations}
        key=model.add_media(editor.doc,media)
        editor.doc['previous_timeline']={'clips':copy.deepcopy(editor.doc['clips']),'output':copy.deepcopy(editor.doc['output'])}
        editor.doc['clips']=[];editor.selected_id=model.append_clip(editor.doc,key);editor.doc['clips'][0]['out']=length
        editor.doc['output'].update(width=data['width'],height=data['height'])
        if data.get('output_fps'):
            from fractions import Fraction
            editor.doc['output']['fps']=float(Fraction(data['output_fps']))
        self.persist(before);self.leave();editor.seek(0);self.host.select_workspace(3)
        self.host.set_status('Enhanced video applied to the project. Censor regions and subtitles remain editable; Undo restores the original timeline.')

    def restore_before_enhancement(self):
        editor=self.host.editor;previous=editor.doc.get('previous_timeline')
        if self.host.process or not previous:return
        before=copy.deepcopy(editor.doc)
        editor.doc['clips']=copy.deepcopy(previous['clips']);editor.doc['output']=copy.deepcopy(previous['output'])
        editor.doc.pop('previous_timeline',None);self.persist(before);self.leave();self.host.select_workspace(3);editor.seek(0)

    def project_export_job(self,job):
        """Subtitle export stays on original project media, never the cache video."""
        if job['action']!='subtitle_export' or not self.matches(job.get('video')):return job
        doc=copy.deepcopy(self.host.editor.doc)
        if job.get('document'):
            model.replace_timeline_annotations(doc,'subtitles',job['document']['cues'])
            doc['subtitle_settings']={k:copy.deepcopy(v) for k,v in job['document'].items() if k not in ('video','cues')}
            doc['subtitle_track']=job.get('track','source')
        settings=job.get('video_export_settings',{})
        codec=settings.get('codec','source')
        if codec=='source':
            source_codecs={doc['media'][c['media']].get('video_codec') for c in doc['clips']}
            codec=next(iter(source_codecs)) if len(source_codecs)==1 and source_codecs<={'h264','hevc','av1'} else 'h264'
        selected=settings.get('encoder','auto')
        encoder={'h264':'auto','hevc':'auto_hevc','av1':'auto_av1'}[codec] if selected=='auto' else selected
        encoding={'encoder':encoder,'quality':settings.get('quality',23),'preset':settings.get('preset','medium'),'audio_bitrate':settings.get('audio_bitrate',320)}
        if settings.get('rate')=='bitrate':encoding['bitrate']=round(settings['bitrate']*1e6)
        elif settings.get('rate','source')=='source':
            if all(doc['media'][c['media']].get('video_bitrate') for c in doc['clips']):
                encoding['bitrate']=min(200000000,max(100000,round(sum(doc['media'][c['media']]['video_bitrate']*(c['out']-c['in'])/c['speed'] for c in doc['clips'])/model.duration(doc))))
        return {'action':'editor_export','project':doc,'output':job['output'],'partial_token':uuid4().hex,
            'burn_subtitles':Path(job['output']).suffix.lower()=='.mp4',
            'soft_subtitles':Path(job['output']).suffix.lower()=='.mkv','subtitle_file':job.get('subtitle_file'),
            'mute_censors':self.host.editor.mute.isChecked(),'encoding':encoding}
