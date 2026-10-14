"""Explicit installation-local cleanup. Never follow reparse points."""
import os
import stat
from pathlib import Path

CATEGORIES = {
    'Temporary processing files': ('cache/audio', 'cache/previews', 'cache/waveforms', 'cache/enhance-previews', 'cache/enhance-jobs', 'cache/project-playback', 'cache/jobs', 'cache/ffmpeg_filters', 'cache/downloads', 'cache/uv'),
    'Speech alignments': ('cache/alignments',),
    'Processing logs': ('logs',),
}

def linked(path):
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & 0x400)

def inventory(root, categories):
    root = Path(root).absolute()
    if linked(root): raise ValueError('Cleanup cannot operate on a linked installation folder.')
    files, blocked = [], []
    def walk(path):
        try:
            if linked(path): blocked.append(str(path)); return
            if path.is_dir():
                for child in path.iterdir(): walk(child)
            elif path.is_file(): files.append((path, path.stat().st_size))
        except FileNotFoundError: pass
    for category in categories:
        for relative in CATEGORIES[category]:
            path = root / relative
            # Check every ancestor, including cache itself.
            parents = list(path.relative_to(root).parts)
            current = root
            for part in parents:
                current = current / part
                if current.exists() and linked(current): blocked.append(str(current)); break
            else: walk(path)
    return files, sorted(set(blocked))

def clear(root, categories):
    files, blocked = inventory(root, categories)
    removed = 0; failures = list(blocked)
    for path, size in files:
        try:
            # Recheck ancestry immediately before deletion.
            current = path
            while current != Path(root).absolute():
                if linked(current): raise ValueError('Linked path was skipped.')
                current = current.parent
            path.unlink(); removed += size
        except (OSError, ValueError) as exc: failures.append(str(path) + ': ' + str(exc))
    return removed, failures
