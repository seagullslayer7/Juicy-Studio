# Third-party components

JuicyCensor application code is MIT licensed; see LICENSE. This does not replace
the licenses of its dependencies.

## Included in the installer / portable ZIP

- PySide6 / Qt 6.11.2 and Shiboken: LGPLv3/GPL/commercial licensing as applicable.
  The unmodified dynamically loaded GUI libraries remain in `_internal`. Notices
  from the official wheels are included under `licenses/*6.11.2.dist-info`.
  Source: https://code.qt.io/cgit/pyside/pyside-setup.git/tag/?h=v6.11.2 and
  https://download.qt.io/archive/qt/6.11/6.11.2/submodules/ .
  License information: https://doc.qt.io/qtforpython-6/licenses.html .
  Users can replace the dynamic libraries with compatible builds; JuicyCensor does
  not prevent debugging modifications to LGPL components.
- uv 0.12.17: MIT OR Apache-2.0. Both licenses are included in `licenses`.
  Source and build instructions: https://github.com/astral-sh/uv/tree/0.12.17 .
- ANTLR Python runtime 4.9.3: BSD-3-Clause. `vendor_wheels` includes a pure-Python
  wheel built from the hash-verified PyPI source archive, to avoid a compiler/build
  dependency on end-user PCs. Its license is included in the wheel and `licenses`.
  Source: https://pypi.org/project/antlr4-python3-runtime/4.9.3/#files .
- The frozen interpreter is CPython 3.12.14 (PSF license, included). PyInstaller
  bootloader licensing includes its distribution exception:
  https://pyinstaller.org/en/stable/license.html .

## Downloaded with user consent during runtime setup

- CPython 3.12.14 via Astral python-build-standalone (PSF and dependency notices).
  https://github.com/astral-sh/python-build-standalone/releases/tag/20260901
- FFmpeg 7.1.1 shared build from Gyan, GPL-enabled. The installer downloads the
  original verified archive directly; runtime files and its accompanying docs are
  extracted under `tools/ffmpeg-shared`.
  https://github.com/GyanD/codexffmpeg/releases/tag/7.1.1
  https://ffmpeg.org/releases/ffmpeg-7.1.1.tar.xz
- whisper.cpp Vulkan 1.8.4 distributed by Lemonade SDK (MIT components):
  https://github.com/lemonade-sdk/whisper.cpp-builds/releases/tag/v1.8.4
  https://github.com/ggml-org/whisper.cpp/tree/v1.8.4
- Python packages: exact versions and archive hashes are in requirements-cpu.lock
  and requirements-cuda.lock. Installed package licenses are retained in the private
  environment's dist-info directories. Includes PyTorch, WhisperX, faster-whisper,
  CTranslate2, Hugging Face libraries and their dependencies.
- Models/tokenizer data download from their publishers. See
  https://huggingface.co/ggerganov/whisper.cpp,
  https://huggingface.co/Systran/faster-whisper-base.en and
  https://pytorch.org/audio/stable/pipelines.html .

The source distribution includes JuicyCensor's build specification and installer
script. Keep the licenses and notices with redistributed application files.

Optional enhancement download: Real-ESRGAN ncnn Vulkan (20220424 Windows build),
including publisher-supplied models and its README retained in the installed
directory. Engine source and MIT license:
https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan . Model project and BSD-3-Clause
license: https://github.com/xinntao/Real-ESRGAN . This optional archive is not
bundled in JuicyCensor's installer.

CUDA enhancement uses adapted BSD-3-Clause network definitions in
`enhance_networks.py`: Real-ESRGAN SRVGGNetCompact from commit
`a4abfb2979a7bbff3f69f58f58ae324608821e27` and BasicSR RRDBNet from commit
`8d56e3a045f9fb3e1d8872f92ee4a4f07f886b0a`. Training initialization and registry
dependencies were removed; pretrained parameter names and architectures remain
compatible. Full notices are in `licenses/Real-ESRGAN-LICENSE.txt` and
`licenses/BasicSR-LICENSE.txt`. Sources:
https://github.com/xinntao/Real-ESRGAN and https://github.com/XPixelGroup/BasicSR .

Optional CUDA weights download directly from the official Real-ESRGAN releases
(v0.2.5.0 animevideov3/general/weak-denoise, v0.2.1 x2plus, v0.1.0 x4plus). Exact filenames,
sizes, and SHA-256 digests are pinned in `enhance_cuda.py`. Weights are verified
before loading and are not bundled in release installers. CUDA processing uses
the existing private PyTorch environment and its retained license notices.

Optional people-restoration components:

- GFPGAN v1.4 weights from TencentARC's official v1.3.0 release. The clean
  GFPGAN/StyleGAN2 architecture files at commit
  `7552a7791caad982045a7bbe5634bbf1cd5c8679` are combined in
  `enhance_face_network.py`. Registry/training initialization dependencies are
  removed, external decoder loading is disabled, and inference uses fixed model
  noise. See `licenses/GFPGAN-LICENSE.txt` for Apache-2.0 and included notices.
  https://github.com/TencentARC/GFPGAN
- YuNet face detector from OpenCV Zoo commit
  `47534e27c9851bb1128ccc0102f1145e27f23f98`, March 2023 ONNX model. MIT license
  retained in `licenses/YuNet-LICENSE.txt`. Detection tensor decoding in
  `enhance_people.py` uses the documented FaceDetectorYN output format; inference
  runs through the existing ONNX Runtime dependency.
  https://github.com/opencv/opencv_zoo/tree/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_detection_yunet
- BSRGAN weights from the author's KAIR v1.0 release. Parameters are renamed to
  the equivalent existing BasicSR RRDB x4 topology; no BSRGAN architecture source
  is bundled. See `licenses/BSRGAN-LICENSE.txt` (Apache-2.0).
  https://github.com/cszn/BSRGAN and https://github.com/cszn/KAIR/releases/tag/v1.0

Model URLs, byte counts, and SHA-256 digests are pinned in `enhance_cuda.py`.
Weights download only when their corresponding optional feature is selected.
They are not included in installer/source distributions. Checkpoints load with
PyTorch's weights-only loader. Whole-frame upscaling and face restoration are
separate stages; neither guarantees faithful reconstruction of missing detail.

Optional SwinIR Large whole-frame restoration:

- `enhance_swinir_network.py` is adapted from JingyunLiang/SwinIR commit
  `6545850fbf8df298df73d81f3e8cba638787c8bd`, `models/network_swinir.py`.
  The original author credits and Apache-2.0 license are retained in the source
  and `licenses/SwinIR-LICENSE.txt`. Changes remove the timm dependency and demo,
  use Torch initialization/evaluation-only stochastic depth, preserve attention
  mask dtype, specify meshgrid indexing, and handle tiny images with replicate
  padding. Pretrained topology and parameter keys are unchanged.
- Detail and Fidelity use the author's v0.0 real-world SwinIR-L x4 GAN and PSNR
  checkpoints. Each is a separate optional download of about 136 MiB, verified
  by pinned byte count and SHA-256 before `weights_only=True` loading. No new
  package installation is required; weights are excluded from release bundles.
  https://github.com/JingyunLiang/SwinIR

Public restoration-test images and generated comparisons stay outside the source
and release bundles. The closer swimmer sample is JD Lasica's photo of Ryan
Lochte before 100 butterfly (2013), CC BY 2.0, obtained via Wikimedia Commons.
Development comparisons crop/resize/compress and restore that photo:
https://commons.wikimedia.org/wiki/File:Ryan_Lochte_before_100_butterfly_(9001310871).jpg
https://creativecommons.org/licenses/by/2.0/
