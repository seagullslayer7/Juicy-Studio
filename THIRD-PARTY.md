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
(v0.2.5.0 general/weak-denoise, v0.2.1 x2plus, v0.1.0 x4plus). Exact filenames,
sizes, and SHA-256 digests are pinned in `enhance_cuda.py`. Weights are verified
before loading and are not bundled in release installers. CUDA processing uses
the existing private PyTorch environment and its retained license notices.
