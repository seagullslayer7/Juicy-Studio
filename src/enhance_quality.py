"""Color conversion and file-size policy for SDR enhancement."""
import math


def color_pipeline(info, override='auto'):
    if override not in ('auto','bt709','bt601'): raise ValueError('Choose Automatic, BT.709, or BT.601 source color.')
    matrices={'bt709':'bt709','bt470bg':'bt601','smpte170m':'bt601','smpte240m':'smpte240m','bt2020nc':'bt2020'}
    tagged=info.get('color_space')
    matrix=matrices.get(tagged)
    assumed=False
    if override!='auto':matrix=override
    elif not matrix:
        if tagged not in (None,'','unknown','unspecified','gbr'):raise ValueError('Unsupported source color matrix for SDR enhancement.')
        matrix='bt709' if info['height']>=720 or info['width']>=1280 else 'bt601'
        assumed=True
    full=info.get('color_range')=='pc' or str(info.get('pix_fmt','')).startswith(('rgb','bgr','gbr','yuvj'))
    decoder=f'scale=in_color_matrix={matrix}:in_range={"full" if full else "tv"}:out_range=full,format=rgb24'
    # Raw RGB carries no source tags. Define conversion AND encoder tags rather
    # than letting HD players guess a matrix for untagged encoded YUV.
    writer='scale=in_range=full:out_range=tv:out_color_matrix=bt709,format=yuv420p'
    primaries=info.get('color_primaries') or 'bt709'
    transfer=info.get('color_transfer') or 'bt709'
    if primaries in ('unknown','unspecified'):primaries='bt709'
    if transfer in ('unknown','unspecified'):transfer='bt709'
    writer+=f',setparams=range=limited:color_primaries={primaries}:color_trc={transfer}:colorspace=bt709'
    tags=['-colorspace','bt709','-color_range','tv','-color_primaries',primaries,'-color_trc',transfer]
    note=f'Source color: {matrix.upper()}' + (' (assumed: source has no matrix tag)' if assumed else '')
    return decoder,writer,tags,note


def automatic_bitrate(width,height,fps,output,source_bitrate,codec,content):
    """An average-rate starting point, not a promise of quality or final size."""
    factor={'h264':.08,'hevc':.05,'av1':.04}[codec]
    resolution_budget=output[0]*output[1]*float(fps)*factor*(.75 if content=='animation' else 1)
    source_budget=max(0,float(source_bitrate or 0))*math.sqrt(output[0]*output[1]/(width*height))*{'h264':1,'hevc':.85,'av1':.75}[codec]
    return str(round(min(200_000_000,max(1_000_000,resolution_budget,source_budget))/100000)*100000)


def size_text(byte_count):
    value=float(byte_count)
    for unit in ('B','KB','MB','GB','TB'):
        if value<1000 or unit=='TB':return f'{value:.1f} {unit}'
        value/=1000


def preview_size_estimate(size,length,source_duration,source_bytes):
    estimate=size*source_duration/max(.001,length)
    ratio=f' · {estimate/source_bytes:.1f}× source size' if source_bytes else ''
    return f'Preview {size_text(size)} · Estimated full export ~{size_text(estimate)}{ratio}. Varies with scene complexity.'


def preserve_chroma_array(enhanced, source):
    """Keep AI luminance detail but use the resized source's color differences."""
    import numpy as np
    from PIL import Image
    original=np.asarray(source.resize(enhanced.size,Image.Resampling.BICUBIC),dtype=np.float32)
    restored=np.asarray(enhanced,dtype=np.float32)
    weights=np.array([.2126,.7152,.0722],dtype=np.float32)
    result=original+(restored@weights-original@weights)[...,None]
    return Image.fromarray(np.clip(np.rint(result),0,255).astype(np.uint8))
