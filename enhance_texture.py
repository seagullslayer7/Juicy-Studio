"""Bounded luminance-detail recovery from a reference image, not generative detail."""
import numpy as np
from PIL import Image


def recover_texture(result, reference, amount, radius=1.2):
    """Recover attenuated fine structure without doubling strong/shifted edges.

    Reference and result must have matching geometry. Small residuals, strong
    edges, and regions with substantial low-frequency disagreement are rejected.
    No filtering occurs at zero strength. The delta is bounded in 8-bit levels
    and applied equally to RGB channels, preserving chroma except at clipping.
    """
    if amount<=0:return result
    from scipy.ndimage import gaussian_filter
    output=np.asarray(result,dtype=np.float32)
    original=np.asarray(reference.resize(result.size,Image.Resampling.BICUBIC),dtype=np.float32)
    weights=np.array([.2126,.7152,.0722],dtype=np.float32)
    reference_y=original@weights;result_y=output@weights
    reference_low=gaussian_filter(reference_y,radius,mode='reflect')
    result_low=gaussian_filter(result_y,radius,mode='reflect')
    source_detail=reference_y-reference_low;result_detail=result_y-result_low
    amplitude=np.abs(source_detail)
    missing=np.maximum(0,amplitude-np.abs(result_detail))
    # Require agreement in edge polarity (or an almost-flat restored area).
    agreement=(source_detail*result_detail>=0)|(np.abs(result_detail)<.75)
    noise_gate=np.clip((amplitude-1.5)/3,0,1)
    edge_gate=np.clip((32-amplitude)/12,0,1)
    structure_gate=np.clip((20-np.abs(reference_low-result_low))/12,0,1)
    delta=np.sign(source_detail)*np.minimum(missing,8)*noise_gate*edge_gate*structure_gate*agreement
    delta*=min(1.,float(amount))
    return Image.fromarray(np.rint(np.clip(output+delta[...,None],0,255)).astype(np.uint8))


def recover_source_texture(result,source,amount):
    # Match the detail band to approximately one original pixel, not output
    # pixels; otherwise enlargement would hide the remaining source texture.
    ratio=max(result.width/source.width,result.height/source.height)
    return recover_texture(result,source,amount,radius=max(.8,min(4.,ratio*.8)))


def source_guided_detail(result,source):
    """Keep source geometry/colors; admit only bounded, aligned AI fine detail.

    No semantic/anatomical claims: every RGB pixel stays within six levels of
    the bicubic source before encoding. Flat areas and conflicting edges retain
    the source, sacrificing reconstruction in exchange for greater fidelity.
    """
    from scipy.ndimage import gaussian_filter
    original=np.asarray(source.resize(result.size,Image.Resampling.BICUBIC),dtype=np.float32)
    enhanced=np.asarray(result,dtype=np.float32)
    weights=np.array([.2126,.7152,.0722],np.float32)
    radius=max(.8,min(4.,max(result.width/source.width,result.height/source.height)*.6))
    src=original@weights;dst=enhanced@weights
    src_low=gaussian_filter(src,radius);dst_low=gaussian_filter(dst,radius)
    src_detail=src-src_low;dst_detail=dst-dst_low
    gate=np.clip((np.abs(src_detail)-1.5)/3,0,1)
    gate*=np.clip((16-np.abs(src_low-dst_low))/10,0,1)
    gate*=src_detail*dst_detail>0
    delta=np.clip(dst_detail-src_detail,-6,6)*gate
    return Image.fromarray(np.rint(np.clip(original+delta[...,None],0,255)).astype(np.uint8))


def protect_source_structure(result,source,source_blend=0,protect=True):
    """Reduce large local changes; this is not an anatomical correctness check.

    A fixed source blend always applies. Optional protection increases that
    blend where blurred luminance differs substantially, retaining more original
    structure without treating newly sharpened fine texture as a shape change.
    """
    source_blend=max(0.,min(1.,float(source_blend)))
    if not protect and source_blend==0:return result
    reference=source.resize(result.size,Image.Resampling.BICUBIC)
    if source_blend==1:return reference
    output=np.asarray(result,dtype=np.float32);original=np.asarray(reference,dtype=np.float32)
    alpha=source_blend
    if protect:
        from scipy.ndimage import gaussian_filter
        ratio=max(result.width/source.width,result.height/source.height)
        drift=(output-original)@np.array([.2126,.7152,.0722],np.float32)
        drift=np.abs(gaussian_filter(drift,max(1.2,min(6.,ratio*1.2)),mode='reflect'))
        adaptive=np.clip((drift-10)/30,0,.85)
        alpha=source_blend+(1-source_blend)*adaptive[...,None]
    return Image.fromarray(np.rint(np.clip(output*(1-alpha)+original*alpha,0,255)).astype(np.uint8))
