"""Non-destructive editing, with one central source/timeline time mapping."""
import copy
import json
import math
import hashlib
from pathlib import Path
from uuid import uuid4

SCHEMA = 1


def new_project():
    return {'schema': SCHEMA, 'name': 'Untitled edit', 'media': {}, 'clips': [],
            'tracks': [{'id': 'v1', 'kind': 'video', 'name': 'Video 1'}, {'id': 'a1', 'kind': 'audio', 'name': 'Audio 1'}],
            'output': {'width': 1920, 'height': 1080, 'fps': 30}}


def tracks(project):
    return project.get('tracks', [{'id': 'v1', 'kind': 'video', 'name': 'Video 1'}, {'id': 'a1', 'kind': 'audio', 'name': 'Audio 1'}])


def clip_track(project, clip, kind):
    return clip.get(kind + '_track', next(t['id'] for t in tracks(project) if t['kind'] == kind))


def add_track(project, kind):
    if kind not in ('video', 'audio'): raise ValueError('Choose a video or audio track.')
    project['tracks'] = copy.deepcopy(tracks(project))
    track = {'id': uuid4().hex, 'kind': kind, 'name': kind.title() + ' ' + str(1 + sum(t['kind'] == kind for t in project['tracks']))}
    project['tracks'].append(track)
    return track['id']


def remove_track(project, track_id):
    current = next(t for t in tracks(project) if t['id'] == track_id)
    replacement = next((t for t in tracks(project) if t['kind'] == current['kind'] and t['id'] != track_id), None)
    if replacement is None: raise ValueError('Keep at least one video and one audio track.')
    for clip in project['clips']:
        if clip_track(project, clip, current['kind']) == track_id: clip[current['kind'] + '_track'] = replacement['id']
    project['tracks'] = [t for t in tracks(project) if t['id'] != track_id]


def validate_annotations(media,annotations):
    if not isinstance(annotations,dict):raise ValueError('Invalid clip annotations.')
    for kind in ('subtitles','censors','words'):
        values=annotations.get(kind,[])
        if not isinstance(values,list):raise ValueError('Invalid annotation list.')
        for item in values:
            if not isinstance(item,dict) or not all(isinstance(item.get(k),(int,float)) and math.isfinite(item[k]) for k in ('start','end')) or not 0<=item['start']<item['end']<=media['duration']+.05:
                raise ValueError('Invalid source annotation timing.')
            if kind=='subtitles' and any(not isinstance(item.get(k,''),str) for k in ('text','source','translation','suggestion')):
                raise ValueError('Invalid subtitle text.')


def validate(project):
    if not isinstance(project,dict) or project.get('schema') != SCHEMA: raise ValueError('Unsupported editing project version.')
    if not isinstance(project.get('name'),str) or not isinstance(project.get('media'),dict) or not isinstance(project.get('clips'),list):raise ValueError('Invalid editing project.')
    ids = set()
    track_list = tracks(project)
    if not isinstance(track_list, list) or any(not isinstance(t, dict) or not isinstance(t.get('id'), str) or not isinstance(t.get('name'), str) or t.get('kind') not in ('video', 'audio') for t in track_list):
        raise ValueError('Invalid timeline tracks.')
    if len({t['id'] for t in track_list}) != len(track_list) or any(not any(t['kind'] == k for t in track_list) for k in ('video', 'audio')):
        raise ValueError('Keep one video and one audio track, with unique track IDs.')
    for key, media in project['media'].items():
        if not isinstance(media.get('path'), str) or not math.isfinite(media['duration']) or media['duration'] <= 0:
            raise ValueError('Invalid source media.')
        validate_annotations(media,media)
    for clip in project['clips']:
        if clip['id'] in ids or clip['media'] not in project['media']: raise ValueError('Invalid clip reference.')
        ids.add(clip['id'])
        for kind in ('video', 'audio'):
            if not any(t['id'] == clip_track(project, clip, kind) and t['kind'] == kind for t in track_list): raise ValueError('Invalid clip track.')
        validate_annotations(project['media'][clip['media']],clip.get('annotations',{}))
        start, end, speed, gain = (float(clip[k]) for k in ('in', 'out', 'speed', 'gain'))
        if not all(math.isfinite(v) for v in (start, end, speed, gain)) or not 0 <= start < end <= project['media'][clip['media']]['duration'] + .001:
            raise ValueError('Trim must be within the source, with End after Start.')
        if not .25 <= speed <= 4 or not 0 <= gain <= 4: raise ValueError('Invalid playback speed or volume.')
    output = project['output']
    if any(type(output[k]) is not int or not 64 <= output[k] <= 7680 or output[k] % 2 for k in ('width', 'height')):
        raise ValueError('Output dimensions must be even numbers between 64 and 7680.')
    if not math.isfinite(output['fps']) or not 1 <= output['fps'] <= 120: raise ValueError('Frame rate must be between 1 and 120.')
    return project


def add_media(project, media):
    for key, item in project['media'].items():
        if item['path'] == media['path']: return key
    key = uuid4().hex
    project['media'][key] = dict(media, subtitles=media.get('subtitles', []), censors=media.get('censors', []))
    return key


def append_clip(project, media_id):
    clip = {'id': uuid4().hex, 'media': media_id, 'in': 0.,
            'out': project['media'][media_id]['duration'], 'speed': 1., 'gain': 1.}
    project['clips'].append(clip)
    return clip['id']


def spans(project):
    time = 0.
    for clip in project['clips']:
        end = time + (clip['out'] - clip['in']) / clip['speed']
        yield clip, time, end
        time = end


def duration(project):
    return sum((c['out'] - c['in']) / c['speed'] for c in project['clips'])


def locate(project, time):
    for clip, start, end in spans(project):
        if start <= time < end:
            return clip, clip['in'] + (time - start) * clip['speed']
    return None


def split(project, clip_id, timeline_time):
    for index, (clip, start, end) in enumerate(spans(project)):
        if clip['id'] != clip_id: continue
        if not start + .04 < timeline_time < end - .04: raise ValueError('Place the playhead inside the selected clip to split it.')
        source_time = clip['in'] + (timeline_time - start) * clip['speed']
        right = copy.deepcopy(clip)
        right.update(id=uuid4().hex, **{'in': source_time})
        clip['out'] = source_time
        project['clips'].insert(index + 1, right)
        return right['id']
    raise ValueError('Select a clip first.')


def mapped_annotations(project, kind):
    result = []
    for clip, offset, _ in spans(project):
        items=clip.get('annotations',{}).get(kind,project['media'][clip['media']].get(kind, []))
        for index,item in enumerate(items):
            start, end = max(clip['in'], item['start']), min(clip['out'], item['end'])
            if end-start > .000001:
                origin=item.get('_origin_id',item.get('id',str(index)))
                result.append(dict(item, start=round(offset + (start-clip['in'])/clip['speed'],6),
                                   end=round(offset + (end-clip['in'])/clip['speed'],6),
                                   id=clip['id']+':'+origin,_origin_id=origin))
    return result


def replace_timeline_annotations(project,kind,items):
    """Project tools edit timeline time; store results in each clip's source time."""
    for item in items:
        if not all(isinstance(item.get(k),(int,float)) and math.isfinite(item[k]) for k in ('start','end')) or not 0<=item['start']<item['end']<=duration(project)+.05:
            raise ValueError('Annotations must be within the edited project.')
    for clip,offset,end in spans(project):
        values=[]
        for item in items:
            start,stop=max(offset,item['start']),min(end,item['end'])
            if stop-start>.000001:
                values.append(dict(item,start=round(clip['in']+(start-offset)*clip['speed'],6),
                                   end=round(clip['in']+(stop-offset)*clip['speed'],6),
                                   _origin_id=item.get('_origin_id',item.get('id',uuid4().hex))))
        clip.setdefault('annotations',{})[kind]=values


def view_key(project):
    """Derived media changes with edits, not with subtitle/censor annotations."""
    sources={}
    for clip in project['clips']:
        media=project['media'][clip['media']];path=Path(media['path']);stat=path.stat()
        sources[clip['media']]=[str(path.resolve()),stat.st_size,stat.st_mtime_ns]
    clips=[{k:v for k,v in c.items() if k!='annotations'} for c in project['clips']]
    return hashlib.sha256(json.dumps([sources,clips,project['output']],sort_keys=True).encode()).hexdigest()[:24]


def save(project, path):
    validate(project)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + '.' + uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps(project, indent=2, ensure_ascii=False), encoding='utf-8')
        temporary.replace(target)
    finally: temporary.unlink(missing_ok=True)


def load(path):
    return validate(json.loads(Path(path).read_text(encoding='utf-8')))


class History:
    def __init__(self): self.past, self.future = [], []
    def record(self, project):
        self.past.append(copy.deepcopy(project)); self.past = self.past[-100:]; self.future.clear()
    def undo(self, project):
        if not self.past: return project
        self.future.append(copy.deepcopy(project)); return self.past.pop()
    def redo(self, project):
        if not self.future: return project
        self.past.append(copy.deepcopy(project)); return self.future.pop()
