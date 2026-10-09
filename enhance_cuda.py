"""Persistent CUDA inference. Imported only by the private processing worker."""
import hashlib
from pathlib import Path
import urllib.request
from uuid import uuid4

WEIGHTS = {
    'SwinIR-L-GAN.pth': ('https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/003_realSR_BSRGAN_DFOWMFC_s64w8_SwinIR-L_x4_GAN.pth', 142473939, '99adfa91350a84c99e946c1eb3d8fce34bc28f57d807b09dc8fe40a316328c0a'),
    'SwinIR-L-PSNR.pth': ('https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/003_realSR_BSRGAN_DFOWMFC_s64w8_SwinIR-L_x4_PSNR.pth', 142473947, '450be6eac63a59959b55a83df6743444de9f018547f81d16f699b3680d366ad7'),
    'BSRGAN.pth': ('https://github.com/cszn/KAIR/releases/download/v1.0/BSRGAN.pth', 67046751, '5d505a0766160921e0388d76e1ddf08cb114303990f9080432bf2b1c988b1c54'),
    'GFPGANv1.4.pth': ('https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth', 348632874, 'e2cd4703ab14f4d01fd1383a8a8b266f9a5833dacee8e6a79d3bf21a1b6be5ad'),
    'face_detection_yunet_2023mar.onnx': ('https://media.githubusercontent.com/media/opencv/opencv_zoo/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_detection_yunet/face_detection_yunet_2023mar.onnx', 232589, '8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4'),
    'realesr-animevideov3.pth': ('v0.2.5.0', 2504012, 'b8a8376811077954d82ca3fcf476f1ac3da3e8a68a4f4d71363008000a18b75d'),
    'realesr-general-x4v3.pth': ('v0.2.5.0', 4885111, '8dc7edb9ac80ccdc30c3a5dca6616509367f05fbc184ad95b731f05bece96292'),
    'realesr-general-wdn-x4v3.pth': ('v0.2.5.0', 4885111, '1641f8c4464b9f097c9fdda5589273713f67cf59f3d909e0bd688f0cee269dca'),
    'RealESRGAN_x2plus.pth': ('v0.2.1', 67061725, '49fafd45f8fd7aa8d31ab2a22d14d91b536c34494a5cfe31eb5d89c2fa266abb'),
    'RealESRGAN_x4plus.pth': ('v0.1.0', 67040989, '4fa0d38905f75ac06eb49a7951b426670021be3018265fd191d2125df9d682f1'),
}


def model_choice(profile, width, height, output, content='live'):
    if content == 'animation': return 4, ('realesr-animevideov3.pth',)
    if profile == 'balanced':
        return 4, ('realesr-general-x4v3.pth', 'realesr-general-wdn-x4v3.pth')
    if profile == 'bsrgan': return 4, ('BSRGAN.pth',)
    if profile in ('swinir_detail','swinir_fidelity'):
        return 4, ('SwinIR-L-'+('GAN' if profile=='swinir_detail' else 'PSNR')+'.pth',)
    if profile == 'detail4': return 4, ('RealESRGAN_x4plus.pth',)
    if profile != 'detail': raise ValueError('Choose Balanced or Detail restoration.')
    scale = 2 if max(output[0]/width, output[1]/height) <= 2 else 4
    return scale, (f'RealESRGAN_x{scale}plus.pth',)


def verified(path, size, digest):
    if not path.is_file() or path.stat().st_size != size: return False
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest() == digest


def ensure_weights(folder, names, emit):
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        tag, size, digest = WEIGHTS[name]
        target = folder/name
        if verified(target, size, digest): continue
        partial = target.with_name(name+'.'+uuid4().hex+'.partial')
        try:
            url = tag if tag.startswith('https://') else f'https://github.com/xinntao/Real-ESRGAN/releases/download/{tag}/{name}'
            emit('stage', message=f'Downloading AI model · {name}', phase='load', percent=0)
            with urllib.request.urlopen(url, timeout=60) as response, partial.open('wb') as stream:
                count = 0
                while chunk := response.read(1024*1024):
                    count += len(chunk)
                    if count > size: raise ValueError('AI model download exceeds its expected size.')
                    stream.write(chunk)
                    emit('stage', message=f'Downloading AI model · {name} · {count/size:.0%}', phase='load', percent=0)
            if not verified(partial, size, digest): raise ValueError('AI model integrity check failed; retry the download.')
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)


class CudaEnhancer:
    def __init__(self, root, profile, width, height, output, gpu, emit, content='live', denoise=.15, preserve_colors=True):
        import torch
        from enhance_networks import SRVGGNetCompact, RRDBNet
        if not torch.cuda.is_available(): raise ValueError('NVIDIA CUDA is unavailable. Install the NVIDIA runtime or choose Vulkan.')
        index = 0 if gpu == 'auto' else int(gpu)
        if not 0 <= index < torch.cuda.device_count(): raise ValueError('The selected CUDA GPU is unavailable.')
        self.torch = torch
        self.device = torch.device('cuda', index)
        self.width, self.height, self.output = width, height, output
        self.scale, names = model_choice(profile, width, height, output, content)
        self.profile = profile
        self.preserve_colors=preserve_colors
        folder = Path(root)/'tools/enhance/torch-models'
        ensure_weights(folder, names, emit)
        emit('stage', message=f'Loading {profile} AI model · {torch.cuda.get_device_name(index)}', phase='load', percent=0)
        swinir=content=='live' and profile in ('swinir_detail','swinir_fidelity')
        if swinir:
            from enhance_swinir_network import SwinIR
            net=SwinIR(upscale=4,in_chans=3,img_size=64,window_size=8,img_range=1.,depths=[6]*9,
                embed_dim=240,num_heads=[8]*9,mlp_ratio=2,upsampler='nearest+conv',resi_connection='3conv')
        else:
            net = (SRVGGNetCompact(num_conv=16, upscale=4) if content == 'animation' else
                   SRVGGNetCompact(num_conv=32, upscale=4) if profile == 'balanced' else RRDBNet(3,3,scale=self.scale))
        states = []
        for name in names:
            checkpoint = torch.load(folder/name, map_location='cpu', weights_only=True)
            states.append(checkpoint.get('params_ema', checkpoint.get('params', checkpoint)))
        # Blend the official strong/weak weights at the selected denoise strength.
        state = states[0] if len(states) == 1 else {k:denoise*states[0][k]+(1-denoise)*states[1][k] for k in states[0]}
        if profile == 'bsrgan' and content == 'live': state = bsrgan_parameters(state)
        net.load_state_dict(state, strict=True)
        self.net = net.eval().requires_grad_(False).to(device=self.device, dtype=torch.float16, memory_format=torch.channels_last)
        free, _ = torch.cuda.mem_get_info(self.device)
        self.tile = 0 if width*height <= 1280*720 and free >= 6*1024**3 else 512
        if swinir:self.tile=0 if width*height<=512*512 and free>=6*1024**3 else 256
        self.pad = 40 if profile == 'balanced' or content == 'animation' else 64
        self.name = f'CUDA · {torch.cuda.get_device_name(index)} · {"animation" if content == "animation" else profile} · native {self.scale}×'

    def _infer(self, tensor):
        torch = self.torch
        if not self.tile: return self.net(tensor)
        h,w = tensor.shape[-2:]
        result = torch.empty((1,3,h*self.scale,w*self.scale),device=self.device,dtype=tensor.dtype)
        for top in range(0,h,self.tile):
            for left in range(0,w,self.tile):
                bottom,right = min(h,top+self.tile),min(w,left+self.tile)
                y0,x0 = max(0,top-self.pad),max(0,left-self.pad)
                y1,x1 = min(h,bottom+self.pad),min(w,right+self.pad)
                patch = self.net(tensor[:,:,y0:y1,x0:x1].contiguous(memory_format=torch.channels_last))
                s=self.scale
                result[:,:,top*s:bottom*s,left*s:right*s] = patch[:,:,(top-y0)*s:(bottom-y0)*s,(left-x0)*s:(right-x0)*s]
        return result

    def process(self, raw):
        import numpy as np
        torch = self.torch
        with torch.inference_mode():
            array = np.frombuffer(raw,dtype=np.uint8).reshape(self.height,self.width,3).copy()
            tensor = torch.from_numpy(array).permute(2,0,1).unsqueeze(0).to(self.device,dtype=torch.float16,memory_format=torch.channels_last).div_(255)
            # RRDB x2 pixel-unshuffles input, requiring even dimensions.
            if self.scale == 2:
                tensor = torch.nn.functional.pad(tensor,(0,self.width%2,0,self.height%2),mode='replicate')
            while True:
                try:
                    result = self._infer(tensor)
                    break
                except torch.cuda.OutOfMemoryError:
                    if self.tile and self.tile <= 128: raise RuntimeError('Not enough GPU memory for enhancement. Close other GPU applications.')
                    self.tile = 512 if not self.tile else self.tile//2
                    torch.cuda.empty_cache()
            result = result[:,:,:self.height*self.scale,:self.width*self.scale].float().clamp_(0,1)
            if result.shape[-2:] != (self.output[1],self.output[0]):
                result = torch.nn.functional.interpolate(result,size=(self.output[1],self.output[0]),mode='bicubic',align_corners=False,antialias=True)
            if self.preserve_colors:
                original=tensor[:,:,:self.height,:self.width].float()
                original=torch.nn.functional.interpolate(original,size=(self.output[1],self.output[0]),mode='bicubic',align_corners=False,antialias=True).clamp_(0,1)
                weights=result.new_tensor([.2126,.7152,.0722]).view(1,3,1,1)
                result=original+((result-original)*weights).sum(dim=1,keepdim=True)
            if not torch.isfinite(result).all(): raise RuntimeError('AI output contains invalid pixels; processing stopped to protect the export.')
            return result.clamp_(0,1).mul_(255).round_().to(torch.uint8).squeeze(0).permute(1,2,0).contiguous().cpu().numpy().tobytes()


def bsrgan_parameters(state):
    """BSRGAN uses the same x4 RRDB topology with different parameter names."""
    names={'RRDB_trunk':'body','RDB1':'rdb1','RDB2':'rdb2','RDB3':'rdb3',
           'trunk_conv':'conv_body','upconv1':'conv_up1','upconv2':'conv_up2','HRconv':'conv_hr'}
    return {'.'.join(names.get(part,part) for part in key.split('.')):value for key,value in state.items()}
