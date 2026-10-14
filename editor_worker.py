"""Render the edit in one encode, including silent sources and mixed dimensions."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
from uuid import uuid4
from editor_project import validate, duration, mapped_annotations
from video_encoding import select_export_encoder, encoder_options


def probe(path):
    path = Path(path).resolve()
    if not path.is_file(): raise FileNotFoundError('Media file is missing: ' + str(path))
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)],
                            capture_output=True, text=True, timeout=30,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode: raise ValueError('Could not read this media file: ' + path.name)
    data = json.loads(result.stdout)
    video = next((s for s in data['streams'] if s['codec_type']=='video' and not s.get('disposition', {}).get('attached_pic')), None)
    if not video: raise ValueError('Choose a file with a video track: ' + path.name)
    return {'path': str(path), 'duration': float(data['format']['duration']),
            'width': video['width'], 'height': video['height'],
            'video_codec':video.get('codec_name'),'video_bitrate':int(video.get('bit_rate') or 0),
            'audio': any(s['codec_type']=='audio' for s in data['streams']),
            'transfer': video.get('color_transfer', ''), 'video_stream': video['index']}


def graph(project, burn=False, mute=False, censor_config=None):
    validate(project)
    output = project['output']; w, h, fps = output['width'], output['height'], output['fps']
    inputs, filters, pairs = [], [], []
    for i, clip in enumerate(project['clips']):
        media = project['media'][clip['media']]
        length = (clip['out']-clip['in'])/clip['speed']
        inputs += ['-ss', str(clip['in']), '-t', str(clip['out']-clip['in']), '-i', media['path']]
        color = clip.get('color', {})
        brightness, contrast, saturation = (float(color.get(k, default)) for k, default in (('brightness',0),('contrast',1),('saturation',1)))
        if not -.5 <= brightness <= .5 or not .5 <= contrast <= 2 or not 0 <= saturation <= 2:
            raise ValueError('Invalid color adjustment.')
        filters.append(f'[{i}:{media.get("video_stream",0)}]setpts=(PTS-STARTPTS)/{clip["speed"]},'
            f'scale={w}:{h}:force_original_aspect_ratio=decrease:force_divisible_by=2,'
            f'pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},format=yuv420p,'
            f'eq=brightness={brightness}:contrast={contrast}:saturation={saturation}[v{i}]')
        if media['audio']:
            speed = clip['speed']; tempo = []
            while speed > 2: tempo.append('atempo=2'); speed /= 2
            while speed < .5: tempo.append('atempo=0.5'); speed *= 2
            tempo.append(f'atempo={speed}')
            filters.append(f'[{i}:a:0]asetpts=PTS-STARTPTS,' + ','.join(tempo) +
                f',volume={clip["gain"]},aresample=48000,aformat=channel_layouts=stereo,apad,atrim=duration={length}[a{i}]')
        else:
            filters.append(f'anullsrc=r=48000:cl=stereo,atrim=duration={length},asetpts=PTS-STARTPTS[a{i}]')
        pairs.append(f'[v{i}][a{i}]')
    if not pairs: raise ValueError('Add clips to the timeline before exporting.')
    filters.append(''.join(pairs) + f'concat=n={len(pairs)}:v=1:a=1[vout][aout]')
    video, audio = 'vout', 'aout'
    if burn:
        filters.append('[vout]subtitles=edit.ass[vfinal]'); video = 'vfinal'
    if mute:
        events = mapped_annotations(project, 'censors')
        if events:
            config=censor_config or project.get('censor_settings',{'censor_mode':'mute'})
            mode=config.get('censor_mode','mute')
            if mode=='mute':
                expression = '+'.join(f'between(t,{e["start"]},{e["end"]})' for e in events)
                filters.append(f"[aout]volume=0:enable='{expression}'[afinal]"); audio = 'afinal'
            else:
                import autocensor as censor
                regions=censor.merge_events([censor.Event(e['start'],e['end'],e.get('matched','Manual'),e.get('kind','manual'),e.get('source','manual')) for e in events],0)
                if not 80<=float(config.get('beep_frequency',1000))<=12000 or not 0<=float(config.get('beep_volume',.8))<=1:
                    raise ValueError('Invalid censor tone settings.')
                if mode=='custom_beep':
                    beep=Path(config['beep_path'])
                    if not beep.is_file():raise ValueError('Custom censor sound is missing.')
                    filters.append(censor.build_custom_beep_filter(regions,duration(project),float(config.get('beep_volume',.8))).replace('[0:a]','[aout]').replace('[1:a]',f'[{len(project["clips"])}:a:0]'))
                    inputs+=['-stream_loop','-1','-i',str(beep)]
                elif mode in ('continuous_beep','pulse_beep'):
                    for key in ('pulse_on','pulse_off'):
                        if not .01<=float(config.get(key,.2))<=10:raise ValueError('Invalid pulse timing.')
                    filters.append(censor.build_generated_tone_filter(regions,duration(project),config,mode=='pulse_beep').replace('[0:a]','[aout]'))
                else:raise ValueError('Unsupported project censor style.')
                audio='outa'
    return inputs, ';\n'.join(filters), video, audio


def run_editor_job(job, emit):
    from runtime_paths import configure_runtime
    configure_runtime()
    if job['action']=='editor_import':
        media=[]
        for i, path in enumerate(job['paths']):
            media.append(probe(path)); emit('stage', message='Reading media', percent=100*(i+1)/len(job['paths']))
        emit('editor_media', media=media); return
    materialize=job['action']=='editor_materialize'
    if job['action'] not in ('editor_export','editor_materialize'): raise ValueError('Unknown editor job.')
    project=validate(job['project'])
    used_media={clip['media'] for clip in project['clips']}
    for media_id in used_media:
        media=project['media'][media_id]
        if not Path(media['path']).is_file(): raise FileNotFoundError('Relink missing media before export: '+media['path'])
        if media.get('transfer') in ('smpte2084','arib-std-b67'):
            raise ValueError('HDR editing export is not supported yet. Use an SDR source to preserve predictable color.')
    output=Path(job['output']).resolve()
    if materialize and output.exists():
        existing=probe(output)
        if abs(existing['duration']-duration(project))>.15:raise ValueError('Project playback cache is incomplete. Remove it and retry.')
        emit('editor_materialized',output=str(output),key=job['key']);return
    if output.suffix.lower() not in ('.mp4','.mkv'): raise ValueError('Choose MP4 or MKV.')
    if output.exists() or any(output==Path(m['path']).resolve() for m in project['media'].values()):
        raise ValueError('Choose a new output filename; source files are preserved.')
    output.parent.mkdir(parents=True, exist_ok=True)
    partial=output.with_name(output.stem+'.'+job['partial_token']+'.partial'+output.suffix)
    annotations=mapped_annotations(project,'subtitles') if (job.get('burn_subtitles') or job.get('soft_subtitles')) and not materialize else []
    config=dict(project.get('censor_settings',{'censor_mode':'mute'}))
    from runtime_paths import __file__ as runtime_file
    config['beep_path']=str(Path(runtime_file).parent/config.get('beep_file','beep.mp3'))
    has_subtitles=bool(annotations or job.get('subtitle_file')) and not materialize
    inputs, filters, video, audio=graph(project, has_subtitles and job.get('burn_subtitles',False), job.get('mute_censors',False) and not materialize,config)
    emit('estimate', duration=duration(project)); emit('stage', message='Preparing project playback' if materialize else 'Preparing timeline export',percent=0)
    encoding=job.get('encoding',{})
    encoder=None if materialize else select_export_encoder(encoding['encoder'],encoding['quality'],encoding['preset'],bitrate=encoding.get('bitrate'))
    try:
        with tempfile.TemporaryDirectory(prefix='juicy-edit-') as scratch:
            folder=Path(scratch)
            subtitle_input=[];subtitle_mapping=[]
            if has_subtitles:
                from subtitle_document import new_document, cue, export_text
                if job.get('subtitle_file'):
                    from subtitle_worker import prepare_export_subtitles
                    subtitle,_=prepare_export_subtitles(job,folder)
                    filters=filters.replace('subtitles=edit.ass','subtitles='+subtitle.name)
                else:
                    doc=new_document();doc.update(project.get('subtitle_settings',{}))
                    track=project.get('subtitle_track','source')
                    doc['cues']=[cue(e['start'],e['end'],e.get(track,e.get('text',''))) for e in annotations if round(e['end'],3)>round(e['start'],3)]
                    (folder/'edit.ass').write_text(export_text(doc,'ass','source'),encoding='utf-8')
                    subtitle=folder/'edit.ass'
                if job.get('soft_subtitles'):
                    if output.suffix.lower()!='.mkv':raise ValueError('Switchable project subtitles require MKV.')
                    index=sum(arg=='-i' for arg in inputs)
                    subtitle_input=['-i',str(subtitle)]
                    subtitle_mapping=['-map',f'{index}:0','-c:s','ass','-metadata:s:s:0','title=Subtitles','-disposition:s:0','default']
            (folder/'graph.txt').write_text(filters,encoding='utf-8')
            command=['ffmpeg','-hide_banner','-nostdin','-v','error',*inputs,*subtitle_input,'-filter_complex_threads','2',
                     '-filter_complex_script','graph.txt','-map',f'[{video}]','-map',f'[{audio}]',
                     *(['-c:v','ffv1','-level','3','-threads','4'] if materialize else encoder_options(encoder,encoding['quality'],encoding['preset'],encoding.get('bitrate'))),
                     *(['-c:a','pcm_s24le'] if materialize else ['-c:a','aac','-b:a',str(encoding['audio_bitrate'])+'k']),
                     *subtitle_mapping,'-t',str(duration(project)),'-progress','pipe:1','-nostats',
                     *(['-movflags','+faststart'] if output.suffix.lower()=='.mp4' else []),str(partial)]
            with (folder/'error.log').open('w+') as errors:
                process=subprocess.Popen(command,cwd=folder,stdout=subprocess.PIPE,stderr=errors,text=True,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                try:
                    for line in process.stdout:
                        if line.startswith('out_time_us='):
                            try: percent=min(99,float(line.split('=',1)[1])/1e6/duration(project)*100)
                            except ValueError: continue
                            emit('stage',message='Preparing project playback' if materialize else 'Exporting edit',percent=percent,phase='render',phase_percent=percent)
                    if process.wait():
                        errors.seek(0); raise RuntimeError('Timeline export failed: '+errors.read()[-1600:])
                finally:
                    if process.poll() is None: process.kill(); process.wait()
                    process.stdout.close()
            partial.rename(output)
    finally: partial.unlink(missing_ok=True)
    emit('editor_materialized' if materialize else 'editor_exported',output=str(output),**({'key':job['key']} if materialize else {}))
