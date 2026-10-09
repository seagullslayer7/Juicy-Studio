"""Explicit encoding settings for subtitle burn-in; MKV remuxes bypass these."""
import json
import subprocess

from video_encoding import CODECS, encoder_options, select_export_encoder

DEFAULTS = dict(codec='source', encoder='auto', rate='source', quality=23,
                bitrate=12.0, preset='medium', audio='auto', audio_bitrate=320,
                channels='original')
MP4_AUDIO = {'aac', 'mp3', 'ac3', 'eac3', 'alac'}


def validate_settings(values):
    settings = dict(DEFAULTS, **values)
    choices = dict(codec=('source', *CODECS), rate=('source', 'quality', 'bitrate'),
                   preset=('fast', 'medium', 'slow'), audio=('auto', 'copy', 'aac'),
                   channels=('original', 'stereo'))
    for name, allowed in choices.items():
        if settings[name] not in allowed:
            raise ValueError(f'Unsupported subtitle export {name}.')
    allowed = ('auto',) if settings['codec'] == 'source' else ('auto', *CODECS[settings['codec']][1])
    if settings['encoder'] not in allowed:
        raise ValueError('Choose an encoder that matches the selected video codec.')
    for name, low, high in [('quality', 0, 51), ('bitrate', .1, 200), ('audio_bitrate', 64, 512)]:
        try:
            number = float(settings[name])
            if not low <= number <= high or (name != 'bitrate' and not number.is_integer()):
                raise ValueError()
        except (ValueError, TypeError):
            raise ValueError(f'{name.replace("_", " ").capitalize()} must be between {low} and {high}.') from None
        settings[name] = number if name == 'bitrate' else int(number)
    if settings['audio'] == 'copy' and settings['channels'] != 'original':
        raise ValueError('Choose AAC or Automatic audio to convert to stereo.')
    return settings


def encoding_args(values, video, subtitle_name, notify=lambda message: None):
    settings = validate_settings(values)
    probe = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(video)],
                           capture_output=True, text=True, timeout=30,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if probe.returncode:
        raise ValueError('Could not read the source video and audio information.')
    streams = json.loads(probe.stdout).get('streams', [])
    picture = next((s for s in streams if s.get('codec_type') == 'video'), None)
    if picture is None:
        raise ValueError('The source has no video stream.')
    audio = [s for s in streams if s.get('codec_type') == 'audio']
    codec = settings['codec']
    if codec == 'source':
        codec = picture.get('codec_name')
        if codec not in CODECS:
            codec = 'h264'
            notify('The source codec cannot be used for MP4 burn-in; using H.264.')
    bitrate = None
    if settings['rate'] == 'bitrate':
        bitrate = round(settings['bitrate'] * 1_000_000)
    elif settings['rate'] == 'source':
        try:
            bitrate = int(picture.get('bit_rate', 0))
        except (ValueError, TypeError):
            bitrate = 0
        if not 100_000 <= bitrate <= 200_000_000:
            bitrate = None
            notify('Source video bitrate is unavailable or outside the supported range; using quality 23.')
            settings['quality'] = 23
    encoder = settings['encoder']
    if encoder == 'auto':
        encoder = {'h264': 'auto', 'hevc': 'auto_hevc', 'av1': 'auto_av1'}[codec]
    transforms = ['-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2']
    notify('Checking the selected video encoder…')
    encoder = select_export_encoder(encoder, settings['quality'], settings['preset'],
                                    video, transforms, bitrate=bitrate)
    args = encoder_options(encoder, settings['quality'], settings['preset'], bitrate)
    if codec == 'hevc':
        args += ['-tag:v', 'hvc1']
    transforms[1] += ',subtitles=' + subtitle_name
    args += transforms
    compatible = all(s.get('codec_name') in MP4_AUDIO for s in audio)
    if settings['audio'] == 'copy' and not compatible:
        raise ValueError('The source audio cannot be copied into MP4. Choose Automatic or AAC audio.')
    if settings['audio'] != 'aac' and compatible and settings['channels'] == 'original':
        args += ['-c:a', 'copy']
    else:
        args += ['-c:a', 'aac', '-b:a', str(settings['audio_bitrate']) + 'k']
        if settings['channels'] == 'stereo':
            args += ['-ac', '2']
    notify(f'Exporting subtitles with {encoder}' + (f' · {bitrate/1_000_000:.2f} Mbps target' if bitrate else f' · quality {settings["quality"]}'))
    return args
