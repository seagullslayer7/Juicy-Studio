# Enhance · 3.1 development preview

This branch adds a working enhancement prototype. The published 3.0 release is
unchanged. Open **View → Enhance workspace** or press **Ctrl+3**.

1. Add a video through File or the shared queue.
2. Install the optional enhancement engine and models (43 MiB download). The
   fixed official archive is SHA-256 checked before extraction; subsequent uses
   reuse the installed files. No separate CUDA toolkit is required.
3. Choose Animation or Live action, then a preview start and 2–10 second length.
4. Generate a preview. Play and seek the Original/Enhanced panels together.
   Only the original panel plays audio.
5. Export a new MP4 or MKV. All audio tracks are copied without re-encoding;
   choose MKV when the source audio format cannot be copied into MP4.

## Implemented

- Real-ESRGAN ncnn Vulkan on NVIDIA/AMD graphics, with automatic or explicit GPU
  index selection (these indices need not match the speech engine).
- Native 2× animation model; live-action 4× model followed by a Lanczos reduction
  to 2× output. The labels distinguish this from a native 2× live-action model.
- Automatic hardware encoder selection, NVIDIA/AMD H.264, or CPU H.264 encoding.
  CPU encoding does **not** replace the Vulkan requirement for AI inference.
- Four-frame batches bound temporary storage independently of video duration.
- Shared cancellation, elapsed time, and a remaining-time estimate based on live
  frame progress. Existing output files and input videos are never overwritten.
- Original audio packet data preserved in full-video exports; partial files and
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

56 automated regression/boundary tests pass. A real six-frame synthetic clip was
enhanced using animation on Vulkan device 1 and live-action on device 0, with
320×180 output from 160×90 input. MP4 and MKV duration/dimensions and unchanged
audio packet hashes were checked. Native Qt checks cover actual preview creation,
paired seeking/playback, model changes, queue removal, and workspace switching.
These short tests establish functionality, not long-video quality or performance.

Backend: https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan
