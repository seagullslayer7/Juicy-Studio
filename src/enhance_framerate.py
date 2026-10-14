"""Exact frame-rate choices shared by the UI and processing worker."""
from fractions import Fraction

FRAME_RATES = [('Source rate (constant output)','source'),('23.976 fps','24000/1001'),
    ('24 fps','24'),('25 fps','25'),('29.97 fps','30000/1001'),('30 fps','30'),
    ('48 fps','48'),('50 fps','50'),('59.94 fps','60000/1001'),('60 fps','60'),
    ('100 fps','100'),('119.88 fps','120000/1001'),('120 fps','120')]


def frame_rates(source, requested='source'):
    if requested not in dict((value,label) for label,value in FRAME_RATES):
        raise ValueError('Choose a supported output frame rate.')
    source=Fraction(source)
    if not 0<source<=120:raise ValueError('Source frame rate must be between 0 and 120 fps.')
    target=source if requested=='source' else Fraction(requested)
    # Drop unneeded frames before expensive AI; duplicate after AI for increases.
    return str(min(source,target)),str(target)
