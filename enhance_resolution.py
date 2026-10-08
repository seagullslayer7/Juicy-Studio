"""Shared, dependency-free output sizing for enhancement preview and export."""
TARGETS = {
    '2x': ('2× source', None),
    '4x': ('4× source', None),
    'original': ('Source resolution', None),
    '720p': ('720p · HD', (1280, 720)),
    '1080p': ('1080p · Full HD', (1920, 1080)),
    '1440p': ('1440p · QHD', (2560, 1440)),
    '2160p': ('4K · UHD', (3840, 2160)),
}


def output_size(width, height, target='2x'):
    if target not in TARGETS:
        raise ValueError('Choose a supported output resolution.')
    if not isinstance(width, int) or not isinstance(height, int) or min(width, height) <= 0:
        raise ValueError('Invalid source dimensions.')
    bounds = TARGETS[target][1]
    if target=='original':
        out=(max(2,width//2*2),max(2,height//2*2))
    elif bounds is None:
        out = (width * int(target[0]), height * int(target[0]))
    else:
        if height > width: bounds = bounds[::-1]
        scale = min(bounds[0] / width, bounds[1] / height)
        # Round down to even dimensions for 4:2:0 codecs, never past the target.
        out = (max(2, int(width * scale + 1e-7) // 2 * 2),
               max(2, int(height * scale + 1e-7) // 2 * 2))
    if max(out) > 7680:
        raise ValueError('Output exceeds 7680 pixels on one side. Choose a smaller resolution.')
    return out


def model_scale(model, width, height, output):
    if model == 'live': return 4
    if model != 'animation': raise ValueError('Choose Animation or Live action.')
    ratio = max(output[0] / width, output[1] / height)
    return next((scale for scale in (2, 3, 4) if ratio <= scale), 4)
