# Juicy Studio · Enhance development preview

This branch adds a working enhancement prototype and the Juicy Studio preview
branding. The published JuicyCensor 3.0 release is
unchanged. Open **View → Enhance workspace** or press **Ctrl+3**.

1. Add a video through File or the shared queue.
2. Choose an AI backend. Automatic uses the installed NVIDIA CUDA runtime for
   live action; animation and other GPUs use Vulkan. Vulkan setup downloads a
   verified 43 MiB archive. CUDA downloads only the selected model on first use:
   about 9.3 MiB for Balanced or 64 MiB for each Detail model. Verified files are
   reused. No separate CUDA toolkit is required.
3. Choose Animation or Live action and an **Output resolution**, then a preview
   start and 2–10 second length. The header shows source → output dimensions.
4. Generate a preview. Play and seek the Original/Enhanced panels together.
   Only the original panel plays audio.
5. Choose the video codec, encoder, and file format, then export a new file.
   Audio defaults to copying every original track without re-encoding. Choose
   MKV for incompatible source audio, or AAC to make an MP4-compatible copy.

## Encoding controls

| Control | Choices |
| --- | --- |
| Video codec | H.264, H.265/HEVC, AV1 |
| Video encoder | Automatic, NVIDIA NVENC, AMD AMF, Intel Quick Sync, CPU |
| Rate control | Quality target (0–51, lower is better), or average bitrate (0.1–200 Mbps) |
| Encoding speed | Fast, Balanced, Slower |
| File format | MP4 or MKV |
| Audio | Original, AAC, Opus, FLAC |
| Audio bitrate | 128, 192, 256, or 320 kbps per AAC/Opus track |

## Output resolution

Choose **720p**, **1080p**, **1440p/QHD**, **4K/UHD**, or **2×/4× source size**.
The default remains 2×. Presets fit the image within 1280×720, 1920×1080,
2560×1440, or 3840×2160, swapping the bounds for portrait footage. No cropping,
stretching, or letterboxing is added; dimensions round to even pixels for video
encoding. For example, 4:3 footage at 1080p becomes 1440×1080, while a portrait
9:16 video becomes 1080×1920. A smaller target downscales, as stated in the UI.

Animation automatically chooses the smallest sufficient 2×, 3×, or 4× AI model.
CUDA live action offers Balanced, a lightweight 4× general-video model with
moderate denoising, and Detail, a heavier native 2× model for targets up to 2× or
4× for larger targets. Balanced can smooth more texture; compare a short preview
before choosing. Vulkan live action retains its 4× Detail model. Antialiased
bicubic resizing on CUDA, or Lanczos on Vulkan, fits the requested dimensions.
Targets beyond 4× source size include conventional enlargement after
AI, which the UI explains; they do not recover unlimited detail. Preview and full
export use the same sizing logic, and changing resolution invalidates a preview.

Automatic tests hardware encoders and then CPU for the chosen codec; it never
silently changes HEVC/AV1 to H.264. Manual selections fail with an explanation
before AI processing if the encoder cannot initialize at the output resolution
and frame rate. Hardware support depends on the GPU, driver, and FFmpeg build.
CPU encoding does not replace the CUDA or Vulkan requirement for AI inference.

Quality values use the encoder's CRF/CQ/QP mode and are not directly comparable
between codecs. Zero is not a universal lossless setting. Bitrate is an average
target, not an exact file-size guarantee. Slower encoding can improve compression
but does not change AI model speed. Output remains 8-bit SDR.

Original audio preserves compressed packet data. AAC and Opus are lossy;
FLAC preserves decoded audio without further loss but cannot restore missing
detail. Opus/FLAC use MKV. MP4 HEVC uses the `hvc1` tag. Comparison playback uses
the original audio only. Shared Export settings also offer automatic codec
selection and AV1 on AMD, Intel, and CPU in addition to NVIDIA.

## Implemented

- Real-ESRGAN ncnn Vulkan on NVIDIA/AMD graphics, with automatic or explicit GPU
  index selection (these indices need not match the speech engine).
- Native 2×/3×/4× animation models and a 4× live-action model, with aspect-aware
  final resizing to the selected output dimensions.
- Codec-aware automatic and explicit NVIDIA/AMD/Intel/CPU encoding, with quality,
  bitrate, speed, audio, and container controls described above.
- CUDA keeps the model resident for the job and streams raw frames without PNG
  round trips. Vulkan uses bounded adaptive batches of up to 16 frames.
- Shared cancellation, elapsed time, live FPS, and a remaining-time estimate
  based on recent completed frames, including progress below 1%. Model loading
  is excluded from processing speed; final muxing shows a separate finalizing
  status. Estimates adapt to speed changes and are not guaranteed finish times.
  Existing output files and input videos are never overwritten.
- Original audio packet data preserved when copying audio; partial files and
  frame batches are removed after normal completion, failure, or GUI cancellation.

## Limits before release

8-bit SDR, square-pixel, rotation-normalized files only. HDR/high-bit-depth and
anamorphic files are rejected explicitly. Variable-frame-rate inputs become
constant-frame-rate at their average rate. Source dimensions are limited to 3840
pixels per side; output to 7680 per side. Frame-based restoration can flicker or
invent detail.

Enhancement currently works on the selected file, not unsaved censor edits or
subtitle overlays. Export censor edits first; burn subtitles after enhancement.
Side-by-side previews synchronize to the original player with drift correction;
they are not a frame-locked scientific comparison.

Resume after cancellation, selective Vulkan model downloads,
GPU names from this backend, persisted enhancement preferences, automatic
cross-workspace export composition, and wider hardware/quality validation remain
future work. Do not label this a finished 3.1 release.

## Verification

78 automated regression/boundary tests pass with GUI dependencies installed. A real six-frame synthetic clip was
enhanced using animation on Vulkan device 1 and live-action on device 0, with
320×180 output from 160×90 input. MP4 and MKV duration/dimensions and unchanged
audio packet hashes were checked. Native Qt checks cover actual preview creation,
paired seeking/playback, model changes, queue removal, and workspace switching.
These short tests establish functionality, not long-video quality or performance.

Additional real exports verify HEVC/NVENC MP4 with unchanged audio and `hvc1`,
CPU SVT-AV1 with Opus in MKV, and bitrate-targeted H.264/AAC MP4. Codec metadata,
dimensions, and duration were checked. UI checks cover codec/vendor selection,
dependent controls, audio/container compatibility, and 1280–1920 pixel layouts.
AMD and Intel codec paths still need real-device verification.

On an RTX 5060 Ti, a 60-frame 720p/59fps synthetic clip exported to 1440p AV1
in 11.63 seconds with CUDA Balanced (5.16 fps including startup) and 25.23 seconds
with Detail (2.38 fps). This is roughly 19× and 9× the earlier 0.27 fps run;
short synthetic tests are not a guarantee for other footage or GPUs. Both
outputs retained all 60 frames, the original frame rate, and identical audio
packet hashes. Quality checks compared tiled/full-frame results and both
profiles on the publisher's sample image. GUI checks verify live ETA, elapsed
time, fractional progress, finalization, and cancellation cleanup.

Resolution checks cover landscape, portrait, 4:3, square, ultrawide, even-pixel
rounding, downscaling, model selection, and size limits. Real animation exports
to 720p, 1080p, and 4K were checked for dimensions and duration, including native
3×/4× model paths. A GUI-generated 1080p preview was also verified.

The native preview executable was also launched on the Windows desktop and
completed a six-frame 2× enhancement with NVENC encoding. Its writable working
files are staged separately from the source checkout. A blocked job-file write
now leaves the window open with an explanation instead of crashing at startup;
the test suite covers that failure path, and the native UI checks cover retry.

Backend: https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan
