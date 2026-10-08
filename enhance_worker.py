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
import time
from collections import deque
import urllib.request
from uuid import uuid4
import zipfile
from video_encoding import CODECS, encoder_options, select_export_encoder
from enhance_resolution import TARGETS, output_size, model_scale
from enhance_quality import color_pipeline, automatic_bitrate, preserve_chroma_array
from enhance_framerate import frame_rates

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
        'models/realesr-animevideov3-x3.bin', 'models/realesr-animevideov3-x3.param',
        'models/realesr-animevideov3-x4.bin', 'models/realesr-animevideov3-x4.param',
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
        raise ValueError('Source dimensions exceed the enhancement limit of 3840 pixels per side.')
    if stream.get('sample_aspect_ratio', '1:1') not in ('1:1', '0:1', 'N/A'):
        raise ValueError('Convert this video to square pixels before enhancement.')
    return dict(width=width, height=height, fps=str(fps), duration=duration,
                video_bitrate=int(stream.get('bit_rate') or 0), source_bytes=Path(video).stat().st_size,
                **{key:stream.get(key) for key in ('color_space','color_range','color_primaries','color_transfer','pix_fmt')},
                audio=[s for s in data['streams'] if s['codec_type'] == 'audio'])


def validate_settings(settings):
    if settings.get('processing','ai') not in ('ai','guided','faithful'):raise ValueError('Choose a supported processing mode.')
    frame_rates('30',settings.get('output_fps','source'))
    if settings.get('processing','ai')!='ai' and settings.get('face_restore','off')!='off':
        raise ValueError('Face reconstruction is available in Full AI restoration only.')
    for key in ('texture_recovery','face_texture','source_blend'):
        value=float(settings.get(key,0))
        if not math.isfinite(value) or not 0<=value<=100:raise ValueError('Texture recovery and source blend must be between 0 and 100%.')
    if settings.get('structure_protection','off') not in ('on','off'):raise ValueError('Choose On or Off for source structure protection.')
    if settings.get('face_restore','off') not in ('off','gfpgan'):raise ValueError('Choose Off or GFPGAN face restoration.')
    face_strength=float(settings.get('face_strength',35))
    if not math.isfinite(face_strength) or not 0<=face_strength<=100:raise ValueError('Face strength must be between 0 and 100%.')
    if settings.get('face_restore','off')!='off' and settings.get('model','animation')!='live':raise ValueError('Face restoration is available for live-action footage only.')
    if settings.get('source_color','auto') not in ('auto','bt601','bt709'):raise ValueError('Unsupported source color matrix.')
    if settings.get('colors','source') not in ('source','ai'):raise ValueError('Choose Source colors or AI colors.')
    if str(settings.get('denoise','0.15')) not in ('0','0.15','0.5','1'):raise ValueError('Unsupported denoising strength.')
    if settings.get('backend','auto') not in ('auto','cuda','vulkan'): raise ValueError('Choose a supported AI backend.')
    if settings.get('restoration','balanced') not in ('balanced','detail','detail4','bsrgan'): raise ValueError('Choose a supported restoration model.')
    if settings.get('resolution', '2x') not in TARGETS: raise ValueError('Choose a supported output resolution.')
    model = settings.get('model', 'animation')
    if model not in MODELS: raise ValueError('Choose Animation or Live action.')
    gpu = str(settings.get('gpu', 'auto'))
    if gpu != 'auto' and not re.fullmatch(r'[0-9]{1,2}', gpu): raise ValueError('Invalid graphics device.')
    quality = str(settings.get('quality', '18'))
    if not quality.isdigit() or not 0 <= int(quality) <= 51: raise ValueError('Video quality must be between 0 and 51.')
    encoder = settings.get('encoder', 'auto')
    export_settings(settings)
    return model, gpu, quality, encoder


def export_settings(settings):
    encoder = settings.get('encoder', 'auto')
    inferred = next((c for c, (_, encoders) in CODECS.items() if encoder in encoders), 'h264')
    codec = settings.get('codec', inferred)
    if codec not in CODECS or encoder not in ('auto', *CODECS[codec][1]):
        raise ValueError('Choose an encoder compatible with the selected video codec.')
    rate = settings.get('rate_control', 'quality')
    if rate not in ('auto','quality', 'bitrate'): raise ValueError('Unsupported rate control.')
    bitrate = str(settings.get('bitrate', '12000000')) if rate == 'bitrate' else None
    preset = settings.get('preset', 'medium')
    encoder_options(CODECS[codec][1][-1], str(settings.get('quality', '18')), preset, bitrate)
    audio = settings.get('audio', 'copy')
    if audio not in ('copy', 'aac', 'libopus', 'flac'): raise ValueError('Unsupported audio encoder.')
    channels = settings.get('audio_channels','original')
    if channels not in ('original','stereo'): raise ValueError('Choose Original channels or Stereo (2 channels).')
    if channels == 'stereo' and audio == 'copy': raise ValueError('Stereo downmix requires audio encoding. Choose AAC, Opus, or FLAC.')
    audio_bitrate = str(settings.get('audio_bitrate', '192'))
    if audio_bitrate not in ('128', '192', '256', '320'): raise ValueError('Unsupported audio bitrate.')
    container = settings.get('container', 'mkv')
    if container not in ('mp4', 'mkv'): raise ValueError('Choose MP4 or MKV.')
    return dict(codec=codec, encoder=encoder, preset=preset, bitrate=bitrate, audio=audio,
                audio_bitrate=audio_bitrate, audio_channels=channels, container=container, rate_control=rate)


def audio_options(settings, suffix, streams):
    audio = settings['audio']
    if suffix == '.mp4':
        if audio in ('libopus', 'flac'):
            raise ValueError('Choose MKV for Opus/FLAC audio, or AAC for MP4.')
        if audio == 'copy' and any(s.get('codec_name') not in ('aac','mp3','ac3','eac3','alac') for s in streams):
            raise ValueError('Choose MKV to preserve this video’s audio format, or select AAC for MP4.')
    options = ['-c:a', audio]
    if audio in ('aac', 'libopus'): options += ['-b:a', settings['audio_bitrate']+'k']
    if settings['audio_channels'] == 'stereo': options += ['-ac:a','2']
    return options


def read_frame(stream, size):
    parts, remaining = [], size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk: break
        parts.append(chunk); remaining -= len(chunk)
    if remaining and parts: raise RuntimeError('Video decoding stopped partway through a frame.')
    return b''.join(parts)


def parse_vulkan_devices(text):
    devices = {}
    for match in re.finditer(r'^\[(\d+) (.+?)\]\s+queueC=', text, re.MULTILINE):
        devices[match[1]] = {'id':match[1], 'name':match[2].strip()}
    return list(devices.values())


def enhancement_vulkan_devices():
    executable = runtime_folder()/'realesrgan-ncnn-vulkan.exe'
    if not executable.is_file(): return []
    # ncnn prints its own device IDs before attempting to decode. An absent
    # UUID-named input probes enumeration without processing or writing media.
    absent = runtime_folder()/('device-probe-'+uuid4().hex+'.png')
    try:
        result = subprocess.run([str(executable),'-i',str(absent),'-o',str(absent.with_suffix('.out.png'))],
            cwd=runtime_folder(),capture_output=True,text=True,encoding='utf-8',errors='replace',
            timeout=15,creationflags=FLAGS)
        return parse_vulkan_devices(result.stderr+result.stdout)
    except (OSError,subprocess.TimeoutExpired): return []


def select_backend(settings):
    requested = settings.get('backend','auto')
    if requested == 'vulkan': return 'vulkan'
    try:
        import torch
        available = torch.cuda.is_available()
    except ImportError:
        available = False
    if available: return 'cuda'
    if requested == 'cuda': raise ValueError('NVIDIA CUDA is unavailable. Install the NVIDIA runtime or choose Vulkan.')
    return 'vulkan'


class FrameProgress:
    """Recent measured throughput; excludes downloads and model initialization."""
    def __init__(self, total, clock=time.monotonic):
        self.total, self.clock = total, clock
        self.samples = deque([(clock(),0)])

    def update(self, frames):
        now = self.clock()
        self.samples.append((now,frames))
        while len(self.samples) > 2 and self.samples[1][0] < now-30:
            self.samples.popleft()
        elapsed = now-self.samples[0][0]
        speed = (frames-self.samples[0][1])/elapsed if elapsed >= 1 and frames >= 2 else None
        return dict(frames=frames,total_frames=self.total,speed_fps=speed,
                    remaining_seconds=max(0,self.total-frames)/speed if speed else None)


def enhance(job, emit):
    from PIL import Image
    video, output = Path(job['video']).resolve(), Path(job['output']).resolve()
    if not video.is_file(): raise ValueError('Choose an existing video.')
    if video == output or output.exists(): raise ValueError('Choose a new output filename; existing files are preserved.')
    if output.suffix.lower() not in ('.mp4', '.mkv'): raise ValueError('Choose an MP4 or MKV output.')
    model, gpu, quality, encoder = validate_settings(job.get('settings', {}))
    settings=job.get('settings',{})
    faithful=settings.get('processing','ai')=='faithful'
    guided=settings.get('processing','ai')=='guided'
    backend = 'cpu' if faithful else select_backend(settings)
    if backend=='vulkan' and job.get('settings',{}).get('restoration') in ('detail4','bsrgan'):
        raise ValueError('This whole-frame model requires NVIDIA CUDA. Choose Detail on Vulkan.')
    if backend == 'vulkan' and not runtime_ready(): raise ValueError('Install the enhancement engine from the Enhance tab first.')
    encoding = export_settings(job.get('settings', {}))
    info = probe(video)
    preview = job['action'] == 'enhance_preview'
    start = float(job.get('start', 0)) if preview else 0.
    if preview and (not math.isfinite(float(job.get('length',5))) or not 0 < float(job.get('length',5)) <= 10):
        raise ValueError('Choose a preview of up to 10 seconds.')
    length = min(float(job.get('length', 5)), info['duration'] - start) if preview else info['duration']
    if not math.isfinite(start + length) or start < 0 or length <= 0 or (preview and length > 10):
        raise ValueError('Choose a preview of up to 10 seconds within the video.')
    audio_args = audio_options(encoding, output.suffix.lower(), info['audio'])
    processing_fps,output_fps=frame_rates(info['fps'],settings.get('output_fps','source'))
    dimensions = output_size(info['width'], info['height'], job.get('settings', {}).get('resolution', '2x'))
    out_width, out_height = dimensions
    decode_color,encode_color,color_tags,color_note=color_pipeline(info,job.get('settings',{}).get('source_color','auto'))
    if encoding['rate_control']=='auto':
        encoding['bitrate']=automatic_bitrate(info['width'],info['height'],float(Fraction(output_fps)),dimensions,info.get('video_bitrate'),encoding['codec'],model)
    scale = model_scale(model, info['width'], info['height'], dimensions)
    token = job.get('partial_token', '')
    if not re.fullmatch('[0-9a-f]{32}', token): raise ValueError('Invalid enhancement job identifier.')
    parent = ROOT / 'cache' / 'enhance-jobs'
    parent.mkdir(parents=True, exist_ok=True)
    scratch = parent / token
    scratch.mkdir()
    partial = output.with_name(output.stem + '.' + token + '.partial' + output.suffix)
    output.parent.mkdir(parents=True, exist_ok=True)
    width, height, fps = info['width'], info['height'], processing_fps
    decoder = writer = None
    try:
        emit('stage', message=f'Preparing enhancement · {out_width} × {out_height} · {color_note}', percent=0)
        requested = ('auto' if encoding['codec'] == 'h264' else 'auto_'+encoding['codec']) if encoder == 'auto' else encoder
        encoder = select_export_encoder(requested, quality, encoding['preset'],
            transforms=['-vf', f'scale={out_width}:{out_height}'], bitrate=encoding['bitrate'], fps=output_fps)
        enhancer = None
        if backend == 'cuda':
            from enhance_cuda import CudaEnhancer
            settings=job.get('settings',{})
            enhancer = CudaEnhancer(ROOT,settings.get('restoration','balanced'),width,height,dimensions,gpu,emit,content=model,
                denoise=float(settings.get('denoise','.15')),preserve_colors=settings.get('colors','source')=='source')
            engine_label = enhancer.name
        elif faithful:
            engine_label = 'Faithful resize · no AI reconstruction'
        else:
            engine_label = 'Vulkan · '+('Animation' if model == 'animation' else 'Detail model')
        face_restorer=None
        settings=job.get('settings',{})
        texture_amount=float(settings.get('texture_recovery',0))/100
        source_blend=float(settings.get('source_blend',0))/100
        structure_protection=settings.get('structure_protection','off')=='on'
        from enhance_texture import recover_source_texture,protect_source_structure,source_guided_detail
        if guided:engine_label+=' · source-guided detail'
        if settings.get('face_restore','off')=='gfpgan' and float(settings.get('face_strength',35))>0:
            from enhance_people import FaceRestorer
            face_restorer=FaceRestorer(ROOT,enhancer.device if enhancer else 'cpu',float(settings.get('face_strength',35))/100,emit,
                preserve_colors=settings.get('colors','source')=='source',texture=float(settings.get('face_texture',0))/100)
            engine_label+=' · faces '+('CUDA' if enhancer else 'CPU')
        emit('stage', message=f'Enhancing · {engine_label}', phase='enhance', percent=0)
        with ExitStack() as stack:
            decode_log = stack.enter_context((scratch/'decode.log').open('w+'))
            encode_log = stack.enter_context((scratch/'encode.log').open('w+'))
            decoder = subprocess.Popen(['ffmpeg','-v','error','-nostdin','-ss',str(start),'-i',str(video),
                '-t',str(length),'-map','0:v:0','-vf',f'fps={fps},{decode_color}','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],
                stdout=subprocess.PIPE, stderr=decode_log, creationflags=FLAGS)
            command = ['ffmpeg','-v','error','-nostdin','-n','-f','rawvideo','-pix_fmt','rgb24',
                '-s',f'{out_width}x{out_height}','-r',fps,'-i','pipe:0','-ss',str(start),'-i',str(video),
                '-map','0:v:0','-map','1:a?','-map_metadata','1','-t',str(length),
                *encoder_options(encoder,quality,encoding['preset'],encoding['bitrate']),'-vf',f'{encode_color},fps={output_fps}',
                '-fps_mode','cfr',*color_tags,*audio_args,'-avoid_negative_ts','disabled']
            if encoding['rate_control']=='auto':
                # Target an average with bounded bursts, rather than unlimited CQ.
                command += ['-maxrate',str(round(int(encoding['bitrate'])*1.5)),'-bufsize',str(int(encoding['bitrate'])*3)]
            if output.suffix.lower() == '.mp4':
                command += ['-movflags','+faststart']
                if encoding['codec'] == 'hevc': command += ['-tag:v','hvc1']
            writer = subprocess.Popen(command + [str(partial)], stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL, stderr=encode_log, creationflags=FLAGS)
            inputs, results = scratch/'input', scratch/'result'
            inputs.mkdir(); results.mkdir()
            count = 0
            progress = FrameProgress(max(1,math.ceil(length*float(Fraction(fps)))))
            last_report = time.monotonic()
            while True:
                if enhancer is not None or faithful:
                    raw = read_frame(decoder.stdout,width*height*3)
                    if not raw: break
                    enhanced_raw=(Image.frombytes('RGB',(width,height),raw).resize(dimensions,Image.Resampling.BICUBIC).tobytes()
                                  if faithful else enhancer.process(raw))
                    if not faithful and (guided or face_restorer or texture_amount>0 or source_blend>0 or structure_protection):
                        source_image=Image.frombytes('RGB',(width,height),raw)
                        restored=Image.frombytes('RGB',dimensions,enhanced_raw)
                        restored=(source_guided_detail(restored,source_image) if guided else recover_source_texture(restored,source_image,texture_amount))
                        if face_restorer:restored=face_restorer.process(source_image,restored)
                        restored=protect_source_structure(restored,source_image,source_blend,structure_protection)
                        enhanced_raw=restored.tobytes()
                    writer.stdin.write(enhanced_raw)
                    count += 1
                    # Frame-level CUDA inference keeps weights resident and avoids PNG round trips.
                    if time.monotonic()-last_report >= .5 or count == 1:
                        metrics = progress.update(count)
                        emit('stage',message=f'Enhancing · {count} frames · {out_width} × {out_height} · {engine_label}',
                             phase='enhance',percent=min(98.,count/progress.total*98),**metrics)
                        last_report = time.monotonic()
                    continue
                batch = []
                # Amortize Vulkan startup, with an estimated 384 MiB frame-file budget.
                batch_size = max(1,min(16,(384*1024**2)//(width*height*3*(1+scale*scale))))
                for index in range(batch_size):
                    raw = read_frame(decoder.stdout, width*height*3)
                    if not raw: break
                    name = f'{index:04}.png'
                    Image.frombytes('RGB',(width,height),raw).save(inputs/name)
                    batch.append(name)
                if not batch: break
                engine = MODELS[model][0]
                args = [str(runtime_folder()/'realesrgan-ncnn-vulkan.exe'),'-i',str(inputs),'-o',str(results),
                    '-m',str(runtime_folder()/'models'),'-n',engine,'-s',str(scale),'-t','0','-j','1:2:2','-f','png']
                if gpu != 'auto': args += ['-g',gpu]
                result = subprocess.run(args, capture_output=True, text=True, errors='replace', creationflags=FLAGS)
                if result.returncode: raise RuntimeError('AI enhancement failed. Check the Vulkan driver or try another GPU. '+result.stderr[-500:])
                for name in batch:
                    with Image.open(results/name) as image:
                        if image.size != (width*scale,height*scale): raise RuntimeError('Unexpected AI output dimensions.')
                        image = image.convert('RGB')
                        if image.size != dimensions: image = image.resize(dimensions,Image.Resampling.LANCZOS)
                        if job.get('settings',{}).get('colors','source')=='source':
                            with Image.open(inputs/name) as original: image=preserve_chroma_array(image,original.convert('RGB'))
                        if guided or face_restorer or texture_amount>0 or source_blend>0 or structure_protection:
                            with Image.open(inputs/name) as original:
                                original=original.convert('RGB')
                                image=source_guided_detail(image,original) if guided else recover_source_texture(image,original,texture_amount)
                                if face_restorer:image=face_restorer.process(original,image)
                                image=protect_source_structure(image,original,source_blend,structure_protection)
                        writer.stdin.write(image.tobytes())
                    (inputs/name).unlink(); (results/name).unlink()
                    count += 1
                percent = min(98.,count/(length*float(Fraction(fps)))*98)
                emit('stage', message=f'Enhancing · {count} frames · {out_width} × {out_height} · {engine_label}',
                     phase='enhance',percent=percent,**progress.update(count))
            decoder.stdout.close()
            if decoder.wait() or not count: raise RuntimeError('Video decoding failed or produced no frames.')
            emit('stage',message='Finalizing enhanced video…',phase='finish',percent=99,
                 frames=count,total_frames=count,speed_fps=None,remaining_seconds=None)
            writer.stdin.close()
            if writer.wait():
                encode_log.seek(0)
                raise RuntimeError('Enhanced video encoding failed: '+encode_log.read()[-600:])
        partial.rename(output)
        emit('enhance_preview' if preview else 'enhance_exported', output=str(output), start=start,
             length=min(length,count/float(Fraction(fps))), width=out_width,height=out_height,frames=count,
             output_bytes=output.stat().st_size,source_bytes=info.get('source_bytes',0),source_duration=info['duration'],
             target_bitrate=encoding['bitrate'],color_note=color_note,
             output_fps=output_fps,processing_fps=fps,processing=settings.get('processing','ai'),
             face_restoration=bool(face_restorer),face_frames=face_restorer.frames_with_faces if face_restorer else 0,
             encoder=encoder, audio=encoding['audio'], audio_channels=encoding['audio_channels'], backend=backend)
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
    if job['action'] == 'enhance_install':
        install_runtime(emit)
        emit('enhance_devices',vulkan=enhancement_vulkan_devices())
    elif job['action'] in ('enhance_preview','enhance_export'): enhance(job,emit)
    else: raise ValueError('Unknown enhancement action.')
