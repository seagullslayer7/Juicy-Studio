# Juicy Studio · Enhance development preview

This branch adds a working enhancement prototype and the Juicy Studio preview
branding. The published JuicyCensor 3.0 release is
unchanged. Open **View → Enhance workspace** or press **Ctrl+3**.

1. Add a video through File or the shared queue.
2. Install the optional enhancement engine and models (43 MiB download). The
   fixed official archive is SHA-256 checked before extraction; subsequent uses
   reuse the installed files. No separate CUDA toolkit is required.
3. Choose Animation or Live action, then a preview start and 2–10 second length.
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

Automatic tests hardware encoders and then CPU for the chosen codec; it never
silently changes HEVC/AV1 to H.264. Manual selections fail with an explanation
before AI processing if the encoder cannot initialize at the output resolution
and frame rate. Hardware support depends on the GPU, driver, and FFmpeg build.
CPU encoding does not replace the Vulkan requirement for AI inference.

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
- Native 2× animation model; live-action 4× model followed by a Lanczos reduction
  to 2× output. The labels distinguish this from a native 2× live-action model.
- Codec-aware automatic and explicit NVIDIA/AMD/Intel/CPU encoding, with quality,
  bitrate, speed, audio, and container controls described above.
- Four-frame batches bound temporary storage independently of video duration.
- Shared cancellation, elapsed time, and a remaining-time estimate based on live
  frame progress. Existing output files and input videos are never overwritten.
- Original audio packet data preserved when copying audio; partial files and
  frame batches are removed after normal completion, failure, or GUI cancellation.

## Limits before release

8-bit SDR, square-pixel, rotation-normalized files only. HDR/high-bit-depth and
anamorphic files are rejected explicitly. Variable-frame-rate inputs become
constant-frame-rate at their average rate. Output is fixed at 2×, with a maximum
width/height of 7680. Frame-based restoration can flicker or invent detail.

Enhancement currently works on the selected file, not unsaved censor edits or
subtitle overlays. Export censor edits first; burn subtitles after enhancement.
Side-by-side previews synchronize to the original player with drift correction;
they are not a frame-locked scientific comparison.

Resume after cancellation, selectable target resolutions, per-model downloads,
GPU names from this backend, persisted enhancement preferences, automatic
cross-workspace export composition, and wider hardware/quality validation remain
future work. Do not label this a finished 3.1 release.

## Verification

65 automated regression/boundary tests pass with GUI dependencies installed. A real six-frame synthetic clip was
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

The native preview executable was also launched on the Windows desktop and
completed a six-frame 2× enhancement with NVENC encoding. Its writable working
files are staged separately from the source checkout. A blocked job-file write
now leaves the window open with an explanation instead of crashing at startup;
the test suite covers that failure path, and the native UI checks cover retry.

Backend: https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan
