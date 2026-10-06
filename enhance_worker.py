"""Optional Real-ESRGAN Vulkan video enhancement, isolated in the worker process.

Frames stream through small batches, bounding temporary storage independently of
video length. Input is never modified; only a completed encode becomes output.
"""
from __future__ import annotations
from contextlib import ExitStack, suppress
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import urllib.request
from uuid import uuid4
import zipfile

ROOT = Path(__file__).resolve().parent
FLAGS = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
URL = 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip'
SHA256 = 'abc02804e17982a3be33675e4d471e91ea374e65b70167abc09e31acb412802d'
MODELS = {'animation': ('realesr-animevideov3', 2), 'live': ('realesrgan-x4plus', 4)}


def runtime_folder():
    return ROOT / 'tools' / 'enhance' / 'realesrgan-20220424'


def runtime_ready():
    root = runtime_folder()
    return all((root / name).is_file() for name in (
        'realesrgan-ncnn-vulkan.exe', 'models/realesr-animevideov3-x2.bin',
        'models/realesr-animevideov3-x2.param', 'models/realesrgan-x4plus.bin',
        'models/realesrgan-x4plus.param'))


def install_runtime(emit):
    if runtime_ready():
        emit('enhance_installed')
        return
    parent = runtime_folder().parent
    parent.mkdir(parents=True, exist_ok=True)
    # Stable file supports cleanup after a cancelled download on the next try.
    archive = parent / 'download.partial'
    staging = parent / 'extracting'
    try:
        emit('stage', message='Downloading enhancement engine and models (43 MiB)', percent=0)
        with urllib.request.urlopen(URL, timeout=60) as response, archive.open('wb') as stream:
            total = int(response.headers.get('Content-Length', 0))
            size = 0
            while chunk := response.read(1024 * 1024):
                stream.write(chunk); size += len(chunk)
                if size > 64 * 1024 * 1024:
                    raise ValueError('Enhancement download exceeds its expected size.')
                emit('stage', message='Downloading enhancement engine and models', percent=min(90, size / total * 90) if total else 0)
        with archive.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != SHA256:
                raise ValueError('Enhancement download failed its integrity check. Try again.')
        if staging.exists():
            safe_remove(staging, parent)
        staging.mkdir()
        with zipfile.ZipFile(archive) as bundle:
            for info in bundle.infolist():
                target = (staging / info.filename).resolve()
                if not target.is_relative_to(staging.resolve()):
                    raise ValueError('Unsafe path in enhancement download.')
            bundle.extractall(staging)
        executable = next(staging.rglob('realesrgan-ncnn-vulkan.exe'))
        destination = runtime_folder()
        if destination.exists(): safe_remove(destination, parent)
        executable.parent.rename(destination)
        if not runtime_ready(): raise RuntimeError('The enhancement models are incomplete.')
        emit('enhance_installed')
    finally:
        archive.unlink(missing_ok=True)
        if staging.exists(): safe_remove(staging, parent)


def safe_remove(folder, parent):
    if folder.is_symlink() or folder.resolve().parent != parent.resolve():
        raise ValueError('Unexpected enhancement temporary path.')
    shutil.rmtree(folder)


def run(command, **kwargs):
    return subprocess.run(command, check=True, creationflags=FLAGS, **kwargs)


def probe(video):
    result = run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(video)],
                 capture_output=True, text=True, encoding='utf-8')
    data = json.loads(result.stdout)
    stream = next((s for s in data['streams'] if s['codec_type'] == 'video'), None)
    if not stream: raise ValueError('This file has no video stream.')
    if stream.get('color_transfer') in ('smpte2084', 'arib-std-b67') or '10' in stream.get('pix_fmt', '') or '12' in stream.get('pix_fmt', ''):
        raise ValueError('This prototype supports 8-bit SDR video. HDR/high-bit-depth enhancement is not supported yet.')
    if any(abs(float(s.get('rotation', 0))) > .1 for s in stream.get('side_data_list', [])) or stream.get('tags', {}).get('rotate', '0') != '0':
        raise ValueError('Export a rotation-normalized copy of this video before enhancement.')
    fps = Fraction(stream.get('avg_frame_rate', '0/1'))
    if not 0 < fps <= 120: raise ValueError('Unsupported or missing frame rate (maximum 120 fps).')
    duration = float(data['format'].get('duration', stream.get('duration', 0)))
    if not math.isfinite(duration) or duration <= 0: raise ValueError('The video duration is unavailable.')
    width, height = int(stream['width']), int(stream['height'])
    if width <= 0 or height <= 0 or width * 2 > 7680 or height * 2 > 7680:
        raise ValueError('The 2× output would exceed the prototype’s size limit.')
    if stream.get('sample_aspect_ratio', '1:1') not in ('1:1', '0:1', 'N/A'):
        raise ValueError('Convert this video to square pixels before enhancement.')
    return dict(width=width, height=height, fps=str(fps), duration=duration,
                audio=[s for s in data['streams'] if s['codec_type'] == 'audio'])


def validate_settings(settings):
    model = settings.get('model', 'animation')
    if model not in MODELS: raise ValueError('Choose Animation or Live action.')
    gpu = str(settings.get('gpu', 'auto'))
    if gpu != 'auto' and not re.fullmatch(r'[0-9]{1,2}', gpu): raise ValueError('Invalid graphics device.')
    quality = str(settings.get('quality', '18'))
    if quality not in ('16', '18', '23'): raise ValueError('Unsupported enhancement quality.')
    encoder = settings.get('encoder', 'auto')
    if encoder not in ('auto', 'libx264', 'h264_nvenc', 'h264_amf'): raise ValueError('Unsupported enhancement encoder.')
    return model, gpu, quality, encoder


def read_frame(stream, size):
    parts, remaining = [], size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk: break
        parts.append(chunk); remaining -= len(chunk)
    if remaining and parts: raise RuntimeError('Video decoding stopped partway through a frame.')
    return b''.join(parts)


def enhance(job, emit):
    from PIL import Image
    import autocensor as core
    if not runtime_ready(): raise ValueError('Install the enhancement engine from the Enhance tab first.')
    video, output = Path(job['video']).resolve(), Path(job['output']).resolve()
    if not video.is_file(): raise ValueError('Choose an existing video.')
    if video == output or output.exists(): raise ValueError('Choose a new output filename; existing files are preserved.')
    if output.suffix.lower() not in ('.mp4', '.mkv'): raise ValueError('Choose an MP4 or MKV output.')
    model, gpu, quality, encoder = validate_settings(job.get('settings', {}))
    info = probe(video)
    preview = job['action'] == 'enhance_preview'
    start = float(job.get('start', 0)) if preview else 0.
    if preview and (not math.isfinite(float(job.get('length',5))) or not 0 < float(job.get('length',5)) <= 10):
        raise ValueError('Choose a preview of up to 10 seconds.')
    length = min(float(job.get('length', 5)), info['duration'] - start) if preview else info['duration']
    if not math.isfinite(start + length) or start < 0 or length <= 0 or (preview and length > 10):
        raise ValueError('Choose a preview of up to 10 seconds within the video.')
    if output.suffix.lower() == '.mp4' and any(s.get('codec_name') not in ('aac','mp3','ac3','eac3','alac') for s in info['audio']):
        raise ValueError('Choose MKV to preserve this video’s audio format without re-encoding.')
    token = job.get('partial_token', '')
    if not re.fullmatch('[0-9a-f]{32}', token): raise ValueError('Invalid enhancement job identifier.')
    parent = ROOT / 'cache' / 'enhance-jobs'
    parent.mkdir(parents=True, exist_ok=True)
    scratch = parent / token
    scratch.mkdir()
    partial = output.with_name(output.stem + '.' + token + '.partial' + output.suffix)
    output.parent.mkdir(parents=True, exist_ok=True)
    width, height, fps = info['width'], info['height'], info['fps']
    decoder = writer = None
    try:
        emit('stage', message='Preparing 2× enhancement', percent=0)
        encoder = core.select_export_encoder(encoder, quality, 'medium', transforms=['-vf', f'scale={width*2}:{height*2}'])
        with ExitStack() as stack:
            decode_log = stack.enter_context((scratch/'decode.log').open('w+'))
            encode_log = stack.enter_context((scratch/'encode.log').open('w+'))
            decoder = subprocess.Popen(['ffmpeg','-v','error','-nostdin','-ss',str(start),'-i',str(video),
                '-t',str(length),'-map','0:v:0','-vf',f'fps={fps}','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],
                stdout=subprocess.PIPE, stderr=decode_log, creationflags=FLAGS)
            command = ['ffmpeg','-v','error','-nostdin','-n','-f','rawvideo','-pix_fmt','rgb24',
                '-s',f'{width*2}x{height*2}','-r',fps,'-i','pipe:0','-ss',str(start),'-i',str(video),
                '-map','0:v:0','-map','1:a?','-map_metadata','1','-t',str(length),
                *core.encoder_options(encoder,quality,'medium'),'-c:a','copy','-avoid_negative_ts','disabled']
            if output.suffix.lower() == '.mp4': command += ['-movflags','+faststart']
            writer = subprocess.Popen(command + [str(partial)], stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL, stderr=encode_log, creationflags=FLAGS)
            inputs, results = scratch/'input', scratch/'result'
            inputs.mkdir(); results.mkdir()
            count = 0
            while True:
                batch = []
                # Small batches bound RAM and disk even on long recordings.
                for index in range(4):
                    raw = read_frame(decoder.stdout, width*height*3)
                    if not raw: break
                    name = f'{index:04}.png'
                    Image.frombytes('RGB',(width,height),raw).save(inputs/name)
                    batch.append(name)
                if not batch: break
                engine, scale = MODELS[model]
                args = [str(runtime_folder()/'realesrgan-ncnn-vulkan.exe'),'-i',str(inputs),'-o',str(results),
                    '-m',str(runtime_folder()/'models'),'-n',engine,'-s',str(scale),'-t','128','-j','1:1:1','-f','png']
                if gpu != 'auto': args += ['-g',gpu]
                result = subprocess.run(args, capture_output=True, text=True, errors='replace', creationflags=FLAGS)
                if result.returncode: raise RuntimeError('AI enhancement failed. Check the Vulkan driver or try another GPU. '+result.stderr[-500:])
                for name in batch:
                    with Image.open(results/name) as image:
                        if image.size != (width*scale,height*scale): raise RuntimeError('Unexpected AI output dimensions.')
                        image = image.convert('RGB')
                        if scale != 2: image = image.resize((width*2,height*2),Image.Resampling.LANCZOS)
                        writer.stdin.write(image.tobytes())
                    (inputs/name).unlink(); (results/name).unlink()
                    count += 1
                percent = min(98.,count/(length*float(Fraction(fps)))*98)
                emit('stage', message=f'Enhancing · {count} frames · {width*2} × {height*2} · {encoder}', percent=percent)
            decoder.stdout.close()
            if decoder.wait() or not count: raise RuntimeError('Video decoding failed or produced no frames.')
            writer.stdin.close()
            if writer.wait():
                encode_log.seek(0)
                raise RuntimeError('Enhanced video encoding failed: '+encode_log.read()[-600:])
        partial.rename(output)
        emit('enhance_preview' if preview else 'enhance_exported', output=str(output), start=start,
             length=min(length,count/float(Fraction(fps))), width=width*2,height=height*2,frames=count)
    finally:
        for process in (decoder,writer):
            if process is not None:
                if process.poll() is None: process.kill()
                process.wait()
                for stream in (process.stdin,process.stdout):
                    if stream and not stream.closed:
                        with suppress(OSError): stream.close()
        partial.unlink(missing_ok=True)
        if scratch.exists(): safe_remove(scratch,parent)


def run_enhance_job(job, emit):
    from runtime_paths import configure_runtime
    configure_runtime()
    if job['action'] == 'enhance_install': install_runtime(emit)
    elif job['action'] in ('enhance_preview','enhance_export'): enhance(job,emit)
    else: raise ValueError('Unknown enhancement action.')
