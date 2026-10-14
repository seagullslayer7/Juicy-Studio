"""Optional local face restoration; whole-frame restoration stays independent.

YuNet output decoding follows OpenCV's FaceDetectorYN tensor format.
Detector weights: OpenCV Zoo (MIT, licenses/YuNet-LICENSE.txt).
GFPGAN architecture/model: TencentARC (licenses/GFPGAN-LICENSE.txt).
No OpenCV/BasicSR package or separate Python installation is required.
"""
from pathlib import Path
import numpy as np
from PIL import Image


TEMPLATE = np.array([[192.98138,239.94708],[318.90277,240.1936],
                     [256.63416,314.01935],[201.26117,371.41043],
                     [313.08905,371.15118]],dtype=np.float64)


def face_transform(landmarks):
    """Least-squares similarity transform: source pixels -> aligned 512px face."""
    points=np.asarray(landmarks,dtype=np.float64)
    if points.shape!=(5,2) or not np.isfinite(points).all():return None
    if np.linalg.norm(points[0]-points[1])<12:return None
    design=np.zeros((10,4));target=TEMPLATE.reshape(-1)
    design[::2,0]=points[:,0];design[::2,1]=-points[:,1];design[::2,2]=1
    design[1::2,0]=points[:,1];design[1::2,1]=points[:,0];design[1::2,3]=1
    coeff,_,rank,_=np.linalg.lstsq(design,target,rcond=None)
    if rank<4 or np.sqrt(np.mean((design@coeff-target)**2))>18:return None
    a,b,x,y=coeff
    if a*a+b*b<1e-8:return None
    return np.array([[a,-b,x],[b,a,y],[0,0,1.]])


def select_faces(rows, threshold=.9, limit=8):
    """Filter confidence, tiny/invalid faces, and overlapping detections."""
    selected=[]
    for row in sorted(rows,key=lambda r:float(r[-1]),reverse=True):
        if not np.isfinite(row).all() or row[-1]<threshold or min(row[2:4])<32:continue
        x,y,w,h=row[:4]
        duplicate=False
        for old in selected:
            ox,oy,ow,oh=old[:4]
            overlap=max(0,min(x+w,ox+ow)-max(x,ox))*max(0,min(y+h,oy+oh)-max(y,oy))
            if overlap/max(1,w*h+ow*oh-overlap)>.3:duplicate=True;break
        if not duplicate:
            selected.append(row)
            if len(selected)==limit:break
    return selected


class FaceDetector:
    def __init__(self,path):
        import onnxruntime as ort
        options=ort.SessionOptions();options.intra_op_num_threads=2
        self.session=ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider'])
        self.input=self.session.get_inputs()[0].name
        self.outputs=[node.name for node in self.session.get_outputs()]

    def detect(self,image):
        # Fixed 640px letterbox keeps model dimensions and small-face cost bounded.
        factor=min(640/image.width,640/image.height)
        w,h=max(1,round(image.width*factor)),max(1,round(image.height*factor))
        resized=np.asarray(image.resize((w,h),Image.Resampling.BILINEAR))
        pixels=np.zeros((640,640,3),np.float32);pixels[:h,:w]=resized[:,:,::-1]
        blobs=dict(zip(self.outputs,self.session.run(None,{self.input:pixels.transpose(2,0,1)[None]})))
        rows=[]
        for stride in (8,16,32):
            scores=np.sqrt(np.clip(blobs[f'cls_{stride}'].reshape(-1),0,1)*np.clip(blobs[f'obj_{stride}'].reshape(-1),0,1))
            boxes=blobs[f'bbox_{stride}'].reshape(-1,4);points=blobs[f'kps_{stride}'].reshape(-1,5,2)
            for index in np.flatnonzero(scores>=.9):
                y,x=divmod(int(index),640//stride)
                center=(boxes[index,:2]+[x,y])*stride
                size=np.exp(np.clip(boxes[index,2:],-10,10))*stride
                if center[0]>=w or center[1]>=h:continue
                landmarks=(points[index]+[x,y])*stride
                # Use actual resized dimensions to undo rounding independently.
                ratios=np.array([image.width/w,image.height/h])
                rows.append(np.r_[(center-size/2)*ratios,size*ratios,(landmarks*ratios).reshape(-1),scores[index]])
        return select_faces(rows)


def face_mask():
    y,x=np.mgrid[:512,:512]
    radius=np.sqrt(((x-256)/175)**2+((y-290)/210)**2)
    weight=np.clip((1-radius)/.3,0,1)
    weight=weight*weight*(3-2*weight)
    return Image.fromarray(np.rint(weight*255).astype(np.uint8))


def composite_face(background,restored,matrix,source_size,strength,preserve_colors=True,texture=0):
    """Warp a feathered face into the output; pixels outside its mask are untouched."""
    if strength<=0:return background
    sx,sy=background.width/source_size[0],background.height/source_size[1]
    mapping=matrix@np.diag([1/sx,1/sy,1])  # output -> aligned face
    inverse=np.linalg.inv(mapping)
    corners=np.array([[0,0,1],[512,0,1],[512,512,1],[0,512,1]])@inverse.T
    left,top=np.maximum(0,np.floor(corners[:,:2].min(axis=0))).astype(int)
    right,bottom=np.minimum(background.size,np.ceil(corners[:,:2].max(axis=0))).astype(int)
    if left>=right or top>=bottom:return background
    local=mapping@np.array([[1,0,left],[0,1,top],[0,0,1]])
    coefficients=tuple(local[:2].reshape(-1))
    size=(right-left,bottom-top)
    restored=restored.transform(size,Image.Transform.AFFINE,coefficients,Image.Resampling.BICUBIC)
    mask=face_mask().transform(size,Image.Transform.AFFINE,coefficients,Image.Resampling.BILINEAR)
    base_image=background.crop((left,top,right,bottom))
    if texture>0:
        from enhance_texture import recover_texture
        # GFPGAN emits 512px faces. Preserve finer texture from the full-frame
        # result where upsampling that fixed face would otherwise erase it.
        restored=recover_texture(restored,base_image,texture,radius=max(1.,min(4.,max(size)/512)))
    base=np.asarray(base_image,dtype=np.float32)
    result=np.asarray(restored,dtype=np.float32)
    if preserve_colors:
        result=base+((result-base)@np.array([.2126,.7152,.0722],np.float32))[...,None]
    alpha=np.asarray(mask,dtype=np.float32)[...,None]*(strength/255)
    blended=np.clip(np.rint(base+(result-base)*alpha),0,255).astype(np.uint8)
    background.paste(Image.fromarray(blended),(left,top))
    return background


class FaceRestorer:
    def __init__(self,root,device,strength,emit,preserve_colors=True,texture=0):
        import torch
        from enhance_cuda import ensure_weights
        from enhance_face_network import GFPGANv1Clean
        folder=Path(root)/'tools/enhance/torch-models'
        ensure_weights(folder,('GFPGANv1.4.pth','face_detection_yunet_2023mar.onnx'),emit)
        emit('stage',message='Loading optional face restoration · GFPGAN v1.4',phase='load',percent=0)
        self.torch=torch;self.device=torch.device(device);self.strength=strength
        self.preserve_colors=preserve_colors
        self.texture=texture
        self.detector=FaceDetector(folder/'face_detection_yunet_2023mar.onnx')
        self.net=GFPGANv1Clean(out_size=512,num_style_feat=512,channel_multiplier=2,
            fix_decoder=False,num_mlp=8,input_is_latent=True,different_w=True,narrow=1,sft_half=True)
        checkpoint=torch.load(folder/'GFPGANv1.4.pth',map_location='cpu',weights_only=True)
        self.net.load_state_dict(checkpoint['params_ema'],strict=True)
        # FP32 avoids overflow in StyleGAN's modulation/demodulation layers.
        self.net=self.net.eval().requires_grad_(False).to(self.device)
        self.faces_restored=0;self.frames_with_faces=0

    def process(self,source,enhanced):
        torch=self.torch
        if self.strength<=0:return enhanced
        restored_count=0
        for face in self.detector.detect(source):
            matrix=face_transform(face[4:14].reshape(5,2))
            if matrix is None:continue
            crop=source.transform((512,512),Image.Transform.AFFINE,tuple(np.linalg.inv(matrix)[:2].reshape(-1)),Image.Resampling.BICUBIC)
            pixels=np.asarray(crop,dtype=np.float32)/127.5-1
            tensor=torch.from_numpy(pixels.transpose(2,0,1).copy())[None].to(self.device)
            with torch.inference_mode():
                result=self.net(tensor,return_rgb=False,randomize_noise=False)[0]
                if not torch.isfinite(result).all():raise RuntimeError('Face restoration produced invalid pixels. Turn it off and retry.')
                result=((result[0].clamp(-1,1)+1)*127.5).round().byte().permute(1,2,0).cpu().numpy()
            enhanced=composite_face(enhanced,Image.fromarray(result),matrix,source.size,self.strength,self.preserve_colors,self.texture)
            restored_count+=1
        self.faces_restored+=restored_count
        self.frames_with_faces+=bool(restored_count)
        return enhanced
