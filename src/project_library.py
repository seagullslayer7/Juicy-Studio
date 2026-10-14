"""A local project index; the media remains at its original locations."""
import json
from pathlib import Path
from uuid import uuid4
from editor_project import load, duration


def recent(root):
    try:
        items=json.loads((Path(root)/'cache/editor-projects/recent.json').read_text(encoding='utf-8'))
        return [p for p in items if isinstance(p,str)][:40] if isinstance(items,list) else []
    except (OSError,ValueError):return []


def remember(root,path):
    path=str(Path(path).resolve());items=[path]+[p for p in recent(root) if p.casefold()!=path.casefold()]
    target=Path(root)/'cache/editor-projects/recent.json';target.parent.mkdir(parents=True,exist_ok=True)
    temporary=target.with_name(uuid4().hex+'.tmp')
    try:
        temporary.write_text(json.dumps(items[:40],indent=2),encoding='utf-8');temporary.replace(target)
    finally:temporary.unlink(missing_ok=True)


def describe(path):
    path=Path(path)
    try:
        stat=path.stat()
        if stat.st_size>16*1024*1024:raise ValueError('Project is too large to preview.')
        doc=load(path)
        return {'path':str(path),'name':doc['name'],'modified':stat.st_mtime,'clips':len(doc['clips']),
            'duration':duration(doc),'sources':len(doc['media']),
            'missing':sum(not Path(m['path']).is_file() for m in doc['media'].values()),'error':''}
    except (OSError,ValueError,KeyError,TypeError) as exc:
        return {'path':str(path),'name':path.stem,'modified':0,'error':'Unavailable: '+str(exc)}
