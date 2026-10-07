"""Video encoder choices shared by export workers and the lightweight desktop UI."""
import subprocess

CODECS = {
    'h264': ('H.264 · compatibility', ('h264_nvenc', 'h264_amf', 'h264_qsv', 'libx264')),
    'hevc': ('H.265 / HEVC', ('hevc_nvenc', 'hevc_amf', 'hevc_qsv', 'libx265')),
    'av1': ('AV1', ('av1_nvenc', 'av1_amf', 'av1_qsv', 'libsvtav1')),
}
ENCODER_LABELS = {'nvenc': 'NVIDIA · NVENC', 'amf': 'AMD · AMF', 'qsv': 'Intel · Quick Sync',
                  'libx264': 'CPU · x264', 'libx265': 'CPU · x265', 'libsvtav1': 'CPU · SVT-AV1'}


def encoder_options(encoder, quality, preset, bitrate=None):
    if encoder not in {e for _, encoders in CODECS.values() for e in encoders}:
        raise ValueError('Unsupported export encoder.')
    if preset not in ('fast', 'medium', 'slow'):
        raise ValueError('Unsupported encoding speed.')
    if not str(quality).isdigit() or not 0 <= int(quality) <= 51:
        raise ValueError('Video quality must be between 0 and 51.')
    if bitrate is not None and (not str(bitrate).isdigit() or not 100_000 <= int(bitrate) <= 200_000_000):
        raise ValueError('Video bitrate must be between 0.1 and 200 Mbps.')
    quality = str(quality)
    if encoder in ('libx264', 'libx265', 'libsvtav1'):
        speed = {'fast':'10', 'medium':'8', 'slow':'6'}[preset] if encoder == 'libsvtav1' else preset
        options = ['-preset', speed] + (['-b:v', str(bitrate)] if bitrate else ['-crf', quality])
    elif encoder.endswith('_nvenc'):
        options = ['-preset', {'fast':'p1', 'medium':'p4', 'slow':'p7'}[preset], '-rc', 'vbr']
        options += ['-b:v', str(bitrate)] if bitrate else ['-cq', quality, '-b:v', '0']
    elif encoder.endswith('_amf'):
        options = ['-quality', {'fast':'speed', 'medium':'balanced', 'slow':'quality'}[preset]]
        # AMF AV1 uses a 0–255 QP scale, unlike H.264/HEVC's 0–51 scale.
        qp = str(round(int(quality) * 255 / 51)) if encoder == 'av1_amf' else quality
        options += ['-rc', 'vbr_peak', '-b:v', str(bitrate), '-maxrate', str(int(bitrate)*2)] if bitrate else ['-rc', 'cqp', '-qp_i', qp, '-qp_p', qp]
    else:
        options = ['-preset', preset] + (['-b:v', str(bitrate)] if bitrate else ['-global_quality', quality])
    return ['-c:v', encoder, *options, '-pix_fmt', 'yuv420p']


def select_export_encoder(requested, quality, preset, video=None, transforms=(), bitrate=None, fps=None):
    automatic = {'auto': 'h264', 'auto_hevc': 'hevc', 'auto_av1': 'av1'}
    candidates = CODECS[automatic[requested]][1] if requested in automatic else (requested,)
    for encoder in candidates:
        options = encoder_options(encoder, quality, preset, bitrate)
        source = ['-i', str(video)] if video else ['-f', 'lavfi', '-i', 'color=size=640x480:rate=' + str(fps or 30)]
        command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', *source,
                   '-map', '0:v:0', '-an', '-frames:v', '3', *options, *transforms, '-f', 'null', '-']
        try:
            probe = subprocess.run(command, capture_output=True, text=True, timeout=30,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if probe.returncode == 0:
                print(f'Export encoder: {encoder}', flush=True)
                return encoder
            detail = probe.stderr[-600:]
        except subprocess.TimeoutExpired:
            detail = 'Encoder initialization timed out.'
        if requested not in automatic:
            raise RuntimeError(f'{encoder} is unavailable with these settings. Choose Automatic or a CPU encoder. {detail}')
    raise RuntimeError(f'No usable {automatic[requested].upper()} encoder was found. Check FFmpeg and your graphics driver. {detail}')
