# Juicy Studio · Enhance development preview

This branch adds a working enhancement prototype and the Juicy Studio preview
branding. The published JuicyCensor 3.0 release is
unchanged. Open **View → Enhance workspace** or press **Ctrl+3**.

1. Add a video through File or the shared queue.
2. Choose an AI backend. Automatic uses the installed NVIDIA CUDA runtime for
   animation and live action; other GPUs use Vulkan. Vulkan setup downloads a
   verified 43 MiB archive. CUDA downloads only the selected model on first use:
   about 2.4 MiB for Animation, 9.3 MiB for Balanced, or 64 MiB for each Detail model. Verified files are
   reused. No separate CUDA toolkit is required.
3. Choose Animation or Live action and an **Output resolution**, then a preview
   start and 2–10 second length. The header shows source → output dimensions.
4. Generate a preview. Play, pause, resume, or seek the Original/Enhanced panels
   together. The compact seek bar shows current time and duration; the result
   heading shows the source time range. Once a result is ready, only its audio
   plays, so downmixing and audio encoding can be checked. Before generation,
   playback uses the original audio. The sound button mutes either source.
5. Choose the video codec, encoder, and file format, then export a new file.
   Audio defaults to copying every original track without re-encoding. Choose
   MKV for incompatible source audio, or AAC to make an MP4-compatible copy.
   Completed exports replace the short preview in the comparison player, so the
   full result can be reviewed against the original without reopening it.

## Encoding controls

| Control | Choices |
| --- | --- |
| Video codec | H.264, H.265/HEVC, AV1 |
| Video encoder | Automatic, NVIDIA NVENC, AMD AMF, Intel Quick Sync, CPU |
| Rate control | Automatic balanced size (default), Quality target (0–51, lower is better), or average bitrate (0.1–200 Mbps) |
| Encoding speed | Fast, Balanced, Slower |
| File format | MP4 or MKV |
| Audio | Original, AAC, Opus, FLAC |
| Audio bitrate | 128, 192, 256, or 320 kbps per AAC/Opus track |
| Audio channels | Original channels, or Stereo (2 channels) |

The **Audio** tab keeps these choices together. Stereo downmixes every audio
track for devices/players that cannot handle multichannel audio. Selecting it
with Original audio switches to AAC at 320 kbps because stream copying cannot
change channel layout. Existing AAC, Opus, and FLAC selections are kept. Selecting
Original audio again restores Original channels. Stereo AAC in MP4 is the broad
compatibility option; it is re-encoded, not a lossless copy. Original remains the
default and preserves all tracks without re-encoding.

## Output resolution

HEVC and Automatic balanced size are the new defaults. Automatic estimates an
average video bitrate from source bitrate, target resolution, frame rate, and
codec, with bounded bursts. It avoids unconstrained quality encoding as the
starting point. After a preview, the workspace estimates the full export size
from that sample and shows its size relative to the source. This is an estimate:
different scenes can require different amounts of data. Quality target remains
available and can produce much larger files.

Use **Fit**, **Zoom 2×**, or **Zoom 4×** by the playback controls. Drag either
zoomed panel to move both views to the same normalized position. These controls
only affect comparison playback, not the exported resolution.

Choose **720p**, **1080p**, **1440p/QHD**, **4K/UHD**, or **2×/4× source size**.
The default remains 2×. Presets fit the image within 1280×720, 1920×1080,
2560×1440, or 3840×2160, swapping the bounds for portrait footage. No cropping,
stretching, or letterboxing is added; dimensions round to even pixels for video
encoding. For example, 4:3 footage at 1080p becomes 1440×1080, while a portrait
9:16 video becomes 1080×1920. A smaller target downscales, as stated in the UI.

Vulkan animation chooses the smallest sufficient 2×, 3×, or 4× AI model. CUDA
animation uses the official lightweight 4× anime-video model, then resizes to
the requested target. It stays resident across frames just like CUDA live action.
CUDA live action offers Balanced, a lightweight 4× general-video model with
adjustable denoising (Low by default), and Detail, a heavier native 2× model for targets up to 2× or
4× for larger targets. Off/Low retains more texture; Strong smooths more noise.
Denoising strength applies only to CUDA Balanced. Compare a short preview
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
the generated audio when available. Shared Export settings also offer automatic codec
selection and AV1 on AMD, Intel, and CPU in addition to NVIDIA.

## Implemented

### Whole-frame fidelity modes

**Enhancement → Processing** now offers:

- **AI · source-guided detail** (default): runs the selected whole-frame model,
  then uses the resized original as the output base. Only small, aligned luminance
  texture changes are admitted, bounded to six 8-bit levels before encoding.
  Flat regions and conflicting edges keep the source. This applies throughout
  the image, including bodies and environments, but the result can remain much
  softer than full reconstruction. It cannot recover missing anatomical detail.
- **AI · full restoration**: retains the existing whole-frame reconstruction and
  optional GFPGAN face pass, with texture recovery and source-protection controls.
- **Faithful resize · no AI**: bicubic scaling without model inference, downloads,
  or face reconstruction. Use this when preserving source appearance is more
  important than reconstructing detail. It still resizes/re-encodes pixels.

Face reconstruction is disabled in the first and third modes. Source-guided
detail preserves source color differences regardless of the full-AI color setting.
No mode guarantees perfect anatomy, motion, or artifact-free encoding. These are
fidelity choices, not a new specialized full-body reconstruction model.

### Output frame rate

**Encoding → Output frame rate** offers the source average rate and common rates
from 23.976 through 120 fps, including exact NTSC fractions. Output is constant
frame rate; variable-rate input is normalized. Conversion drops or repeats frames
without changing playback speed or audio pitch. A higher rate does not create
smoother motion or invented intermediate poses; motion interpolation is not used.
For reductions, unnecessary frames are dropped before AI. For increases, frames
are repeated after AI to avoid redundant inference. Automatic bitrate uses the
output rate, and completed previews display it. The existing elapsed time and ETA
track processed frames; final encoding is reported separately.

**Source resolution** is also available, for frame-rate conversion/re-encoding
without enlargement. Odd dimensions round down to even pixels for 4:2:0 codecs.

Validation: 110 automated tests pass, including exact fractional rate selection,
48 fps conversions to 25/29.97/60 fps, frame counts, duration, copied audio packets,
and faithful export with AI initialization explicitly forbidden. Actual CUDA and
Vulkan source-guided exports convert a six-frame sample to 24/25 output frames
while processing only six frames. These short checks do not establish broad
motion/anatomical quality. Public sample comparisons are development-only.

### People and whole-frame detail

**SwinIR Large · detail** and **SwinIR Large · fidelity** are optional CUDA
live-action models. They process the entire frame, including exposed skin, hands,
hair, clothing, and surroundings. Detail uses the author's GAN checkpoint;
Fidelity uses the PSNR checkpoint and can appear softer. These are general
restoration models, not anatomical specialists. Use Full AI restoration to see
their reconstruction; source-guided mode intentionally limits the effect. The
existing optional GFPGAN face pass and final source protection still apply.

Each variant downloads about 136 MiB once, reuses verified weights, and requires
no extra Python packages. Both are substantially slower than BSRGAN. On the local
RTX 5060 Ti, the small 300×348 skin sample took about 0.94–1.07 seconds for SwinIR
inference/resizing versus about 0.32 seconds for BSRGAN (single measurements, not
a throughput guarantee). Larger inputs use overlapping-context tiles with
window-aligned origins; GPU-memory failures reduce the tile size. Vulkan continues
using the existing Detail model and explicitly rejects these CUDA-only choices.

The closer test uses a public swimmer photograph with exposed torso, shoulders,
arms, and hands, reduced to 300×348 and JPEG-compressed before restoration to
600×696. Relative to the reference, SwinIR Fidelity had lower pixel error than
BSRGAN in the selected skin, arm, and hand crops. SwinIR Detail retained a
different, more visible texture appearance but was not a consistent pixel-error
winner. None recovered all original fine skin detail. A second clothed full-body
sample also favored the new variants by the tested crop metric. Still-image
metrics and synthetic pans do not establish naturalness or stability on real
body motion, or prove the absence of distortion.

Verification now totals 112 automated tests. Added checks cover model selection,
packaged architecture/license, tiny/odd input dimensions, finite output, and
deterministic evaluation. Actual CUDA tests load both pinned checkpoints strictly,
compare repeated/full/tiled output (maximum one 8-bit level difference in the
tested crop), and export a panning skin sample with 24 fps output. Full restoration
also runs GFPGAN successfully; source-guided mode bypasses it. GUI selection and
real previews pass, with controls fitting 1280×720 through 1920×1080.

For live action on NVIDIA CUDA, **Whole-frame restoration** offers:

- **Balanced** for speed and adjustable denoising.
- **Detail** for the existing scale-aware Real-ESRGAN model.
- **Detail · full 4× model** to compare the native 4× model even for smaller targets.
- **Whole frame · BSRGAN** as an alternative trained restoration model for the
  entire picture, including body detail, hair, hands, clothing, and surroundings.
  It downloads about 64 MiB once. This is not a body/anatomy-specific model and
  cannot guarantee accurate recovery of missing texture or anatomy. These heavier
  models can be substantially slower than Balanced. Vulkan retains its existing
  whole-frame Detail model.

The separate **People** tab adds **GFPGAN** for detected faces. It is off by default;
start with 25–40% strength and compare a moving preview. The first use downloads
about 333 MiB of verified GFPGAN/YuNet weights. Detection runs on CPU; face
restoration uses the selected CUDA card or CPU alongside Vulkan upscaling. CPU
restoration is slower. It uses existing NumPy, Pillow, ONNX Runtime, and PyTorch;
no new environment or pip installation is needed. Models stay in
`tools/enhance/torch-models` and are reused after integrity checks.

Face restoration is blended into feathered face regions after whole-frame
processing. Source-color preservation also applies to this pass. A 0% strength
bypasses both face processing and the optional downloads. Low-confidence, tiny,
or badly aligned faces are skipped (including eye separation below 12 source
pixels). The result reports how many frames received face restoration; frames
without suitable faces still receive whole-frame restoration. Faces may change
appearance at high strengths. Fixed model noise avoids random noise between
identical frames, but this is not a temporally trained video restorer; motion,
occlusions, and changing detections can still cause flicker. Face restoration
does not repair hands or bodies; those depend on the whole-frame model.

### Texture and source fidelity

The **Detail** tab adds three controls applied to both CUDA and Vulkan output:

- **Source texture recovery**, initially 35%, restores a bounded amount of visible
  source luminance texture that the model attenuates. It rejects tiny residuals,
  strong edges, and areas with substantial structural disagreement. It does not
  invent reliable skin pores, hair strands, or body detail absent from the source.
  High strengths may also retain compression artifacts or noise.
- **Source blend**, initially 15%, mixes the resized original into the final
  picture after all restoration passes. Increase it to retain more of the original
  appearance. At 100% the picture is the bicubic-resized original, although AI
  processing still runs.
- **Protect source structure**, initially On, increases that blend locally where
  broad luminance structure changes substantially. This reduces large changes;
  it is not an anatomy detector and cannot guarantee correct hands, faces, body
  shapes, or other objects. Small distortions can remain, and source blending may
  soften detail or expose doubled edges where a model has shifted features.

In **People**, **Keep face texture** starts at 50%. It retains compatible fine
texture from the whole-frame result when compositing GFPGAN's fixed 512-pixel face,
including at 100% face strength. It does not increase the face model's resolution.
The final source blend/protection also applies to restored faces. Use lower face
strength and compare a moving preview if features change. These controls do not
provide temporal stabilization or guarantee flicker-free motion.

These passes use the existing SciPy dependency and need no additional model
download. They add CPU work: a local single-frame measurement was about 0.21 s at
1080p and 0.90 s at 4K, excluding model inference and encoding. Performance varies
by PC. Setting texture recovery/source blend to 0% and protection Off bypasses
the full-frame fidelity passes; face texture has its own strength control.

### Color handling

The **Color** tab defaults to Preserve source colors: retain the resized
original's color differences while taking luminance detail from the AI result.
Allow AI color changes uses the model's complete output instead. Preservation
reduces model-induced hue and saturation changes, but is not a guarantee of an
identical image, particularly where channels clip near black or white.

Source decoding reads matrix/range tags. Without a matrix tag, Automatic assumes
BT.709 for HD (at least 1280 pixels wide or 720 high), otherwise BT.601. Override
the source matrix if that assumption is wrong. RGB output is explicitly converted
to limited-range BT.709 YUV and tagged, instead of relying on player guesses.
Known source primaries and transfer tags are retained; missing values assume
BT.709. These controls do not add HDR support or repair incorrectly mastered video.

- Real-ESRGAN ncnn Vulkan on NVIDIA/AMD graphics, with automatic or explicit GPU
  selection by detected device name. CUDA and Vulkan enumerate their own cards
  so selections use the correct backend IDs; unavailable devices are not listed.
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
Persisted enhancement preferences, automatic
cross-workspace export composition, and wider hardware/quality validation remain
future work. Do not label this a finished 3.1 release.

## Verification

97 automated regression/boundary tests pass with GUI dependencies installed. A real six-frame synthetic clip was
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

A ten-second synthetic clip also verifies CUDA animation export and a preview
starting two seconds into the source. Player checks cover pause/resume without
rewinding on repeated LoadedMedia events, offset seeking, restart after the end,
automatic full-export comparison, named CUDA/Vulkan devices, and 1280–1920 pixel
layouts. CUDA animation is native 4× with final resizing; the Vulkan animation
path retains its scale-specific models.

Audio validation exports a test file containing two four-channel tracks. Original
retains both four-channel streams with identical audio packet hashes; Stereo AAC
produces two two-channel streams. Tone checks verify audio from all four source
channels survives the downmix. UI checks cover channel/encoder compatibility and
using the generated mix for comparison playback.

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

Color/size validation includes explicit SD/HD/full-range output conversion and
metadata checks, source-chroma preservation, automatic bitrate boundaries, and
an actual CUDA/HEVC preview with a full-size estimate. Two-second user samples
targeted 8.7 Mbps for 720p/59fps live action at 1440p (the prior export was
46.5 Mbps), and 4.8 Mbps for 404p animation at 1080p, using AV1. These demonstrate
size control, not equivalent perceived quality or guaranteed full-video sizes.
Restoration quality still needs scene-by-scene review; AI cannot recover a known
ground truth from missing source detail.

People restoration checks cover similarity alignment, tiny/invalid face rejection,
duplicate suppression, strength/color preservation, feathered compositing at
nonuniform output ratios, model selection, and GUI backend controls. Actual model
tests use public portrait and full-body sample images, including a degraded
reference comparison. Full 4× Detail and BSRGAN reduced pixel error in the tested
body/clothing crop relative to Balanced; this is not a general quality ranking.
A six-frame panning portrait exports successfully using CUDA/BSRGAN/GFPGAN and
Vulkan/CPU-GFPGAN, with six restored-face frames, correct output dimensions/color
tags, and unchanged retained audio packet data. A preview trim may omit AAC
boundary packets. Repeating an identical portrait produces matching face output;
blank frames remain unchanged by the face pass. Real motion quality and AMD
hardware still require wider validation.

Texture/fidelity validation adds eight tests for bypass and full-source output,
bounded recovery, flat/noisy input, disagreement rejection, reduction of an
artificial structural change, retention of fine detail, face compositing at 100%
strength, and invalid settings. CUDA and Vulkan
six-frame exports also pass with texture recovery, source protection, and 100%
GFPGAN enabled. GUI controls fit at 1280×720, 1500×950, and 1920×1080. The public
full-body reference comparison shows a modest fidelity improvement from source
blending; it does not establish anatomical correctness or recovery of missing
texture across real footage.

## Existing subtitle files

The Subtitles & Translation workspace also offers **Export → Video with
subtitles…**. Choose an existing UTF-8 SRT, VTT, ASS, or SSA file, or an editor
track. Export stays available with a video loaded even when the transcript is
empty. External-file export does not replace or modify the editor document.

MP4 burns subtitles into the picture; MKV adds a switchable subtitle track and
copies the original video/audio. External subtitle files are passed through
without stripping their formatting. ASS/SSA styles and positioning are retained;
fonts used by external files need to be installed. Editor Style settings apply
to editor tracks, not external files.

The export dialog has separate **Video** and **Audio** controls for MP4, for both
external files and editor tracks. Choose H.264, HEVC, or AV1 and an automatic,
NVIDIA, AMD, Intel, or CPU encoder; unsupported manual encoders report an error.
Match source bitrate is the default; constant quality (0–51, lower is higher
quality) and target bitrate (0.1–200 Mbps) are also available. The default matches
H.264/HEVC/AV1 sources, falling back to H.264 for other codecs. Missing or
unsupported source bitrate falls back to quality 23. File sizes are not guaranteed.
Source resolution and frame rate are retained, with one-pixel padding when needed.

Audio can be copied, encoded as AAC, or automatically copied when compatible.
Stereo conversion uses AAC; strict Copy keeps the original channels. AAC bitrate
can be chosen separately. MKV copies video/audio and disables encoding controls.
Choices are remembered for the app session and do not change global export settings.

Verification covers all four file extensions in MP4 and MKV, ASS color/position
tags, unchanged compatible audio, MKV video stream copying, invalid files, empty
editor export, and preserving in-progress editor text.

Subtitle export controls were checked with 118 passing regression tests plus
synthetic one-second MP4 exports using NVIDIA HEVC and AV1, source-codec/bitrate
matching, and four-channel to stereo conversion. Copied AAC packets matched the
source exactly; MKV video and audio packets also matched. Both editor tracks and
external files were exercised. The dialog fits a 640×642 logical-pixel area;
hardware-specific AMD/Intel encoders still require testing on those devices.
