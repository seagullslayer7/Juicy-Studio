# Juicy Studio 1.0.0

JuicyCensor becomes **Juicy Studio**, bringing editing, censorship, multilingual subtitles, translation and enhancement into one shared project.

## Editing and projects

- Edit opens first, with a media bin, linked video/audio lanes and a preview player.
- Trim, split, reorder and remove clips, with Undo/Redo. Adjust speed, volume, color, canvas and output frame rate.
- Save `.juicy` projects. The Projects window offers recent files, search and recovery copies; missing media can be relinked.
- Censor and subtitle edits follow timeline cuts and speed changes across workspaces. Enhanced output can become project media; Undo restores the previous timeline.
- Separate video/audio lanes have add/remove controls. They organize a linked sequence; overlapping layers and independent audio mixing remain future work.

## Enhancement and export

- Local animation/live-action upscaling, target resolutions through 4K, short before/after previews and finished-output playback.
- Persistent NVIDIA inference and pipeline improvements, source-color handling and source-guided blending.
- Optional BSRGAN/SwinIR whole-frame restoration, GFPGAN face restoration, bounded texture recovery and structure protection on supported backends.
- H.264, H.265/HEVC and AV1 options, quality/bitrate controls, stereo audio and output FPS conversion. FPS conversion repeats/drops frames; it does not generate motion.
- Elapsed/remaining-time progress and preview-based size estimates. AI restoration can introduce artifacts and cannot guarantee detail or anatomy.

## Subtitles, playback and interface

- Video exports accept an editor track or an existing SRT/VTT/ASS/SSA file, with dedicated video/audio controls.
- Standalone MKV subtitle export can preserve source streams and add a switchable subtitle track.
- Audio-output selection and reconnection, compact vertical volume popups and improved preview playback.
- Aligned headers, icon toolbars, hover explanations and searchable built-in guides.
- Fixed dark-theme guide text and bundled SVG rendering. Updated README, screenshots, branding, executable metadata and installer for 1.0.0.

## Installation and maintenance

- Repaired private Python environment creation to avoid Windows untrusted-mount-point errors during setup.
- Per-user installation; optional model downloads and reuse of compatible cached files. System Python, Visual Studio and a separate CUDA Toolkit are not required.
- Storage cleanup previews temporary files, speech alignments and logs while keeping saved work/models. Linked folders are skipped.
- Uninstall can retain local data or remove installation-owned runtime, models, settings, projects and exports after confirmation. External files are preserved.
- Studio previews update under the same installer identity. JuicyCensor remains separate; old releases stay available.

## Downloads and limits

Use **Setup.exe** to install, **Portable.zip** for a complete portable app, or **Source.zip** to build it yourself. SHA256SUMS.txt covers all three. First launch downloads the selected processing environment; models require additional space. Windows 10 (1809+) / Windows 11 x64; unsigned installer.

The release is checked with the automated suite, synthetic playback/export, shared-project timing, switchable MKV subtitles, cleanup boundaries, resizing and packaged UI checks. See VALIDATION.md for exact checks.

No layered compositing, independent audio mixing, transitions or keyframes yet. HDR timeline export is unsupported. Clip color edits render at export; the source preview shows original color. Smart translation suggestions need review; optional online AI uses the user's own key.

The WhisperX-compatible runtime pins PyTorch 2.8. GitHub flags three upstream low/medium advisories, duplicated across the CPU/CUDA manifests: [LSTM cell](https://github.com/advisories/GHSA-qfhq-4f3w-5fph), [TorchScript](https://github.com/advisories/GHSA-rrmf-rvhw-rf47), and [sequence unpacking](https://github.com/advisories/GHSA-vgrw-7cvw-pwgx). They are not fixed in this release; a runtime upgrade requires separate compatibility validation.

---

## JuicyCensor release history

# JuicyCensor 3.0.0

JuicyCensor now brings censorship, multilingual subtitles, translation, and a customizable editing workspace together in one Windows app.

## Subtitles & Translation

- A dedicated bilingual editor beside the familiar Censor workspace, sharing the video queue.
- Multilingual Whisper transcription on NVIDIA CUDA, AMD/Intel Vulkan, or CPU, with alphabetical language lists and model compatibility guidance.
- Source and translation columns, text search, precise Start/End controls, add/remove, split/merge, playback of a selected line, and Undo/Redo.
- Local Audio → English translation and optional Smart translate with a local text-model server or the user's own online API key. Nearby lines and scene notes supply context; suggestions are reviewed before acceptance. Online mode requires explicit consent and keeps keys in memory only.
- Save/autosave bilingual .juice.json projects, including timing, subtitle style, context, and pending suggestions.
- Import SRT, VTT, and ASS. Export SRT/VTT, styled ASS, MP4 with subtitles burned into the picture, or MKV with a switchable styled track.
- Quiet speech / whispers option for subtitle transcription. English-only models are rejected for incompatible languages; multilingual base is the new optional starter model.

## Waveforms and precise editing

- Waveforms load automatically in the background and reuse cached audio data.
- Visible sound peaks, cue text and duration, a time ruler, zoom/pan, and Fit controls.
- Drag whole subtitle blocks or censor regions to move them; drag either edge to trim. Escape cancels the drag. Subtitle changes support Undo/Redo and autosave.
- A compact waveform-height slider reveals quiet peaks without changing playback volume.
- Switching videos discards stale waveform results, and videos without audio report that clearly.

## A cleaner, customizable interface

- Compact File, Edit, View, Settings, and Help menus alongside the two workspace tabs.
- Balanced video/transcript panes with draggable edges, a neatly aligned line editor, and a queue that can be shown or hidden.
- A small × on queued videos removes the entry while preserving the file and saved edits.
- Consistent citrus icons, useful tooltips, aligned labels and time controls, a compact status badge, and refined sliders and buttons.
- Full-screen support with F11/Esc, restoreable panel layout, and elapsed/estimated remaining time during processing.
- View → Appearance: live previews for background, accent, selection, waveform, and progress colors; saturation, brightness, highlight strength, spacing, and corner controls.
- Orange grove, Midnight, Berry, and Graphite presets, plus named custom presets. Save keeps the look; Cancel restores it; Reset to Orange returns to the default. Exported subtitle styling stays separate.

## Censoring and compatibility

- Interrupted English word-alignment downloads now retry in small verified ranges. An incomplete cached checkpoint is repaired before use, and a replacement is saved only after all ranges and the archive integrity check pass.
- Unicode word matching now preserves accented and non-Latin text, including character-aligned Japanese/Chinese phrases. Censoring still requires a supported alignment model and appropriate word lists.
- Original/censored playback, searchable censor transcripts, manual regions, adjustable skips, volume/speed controls, and export presets remain available.
- Retains the Windows model-download privilege fix, installer Python-probe recovery, NVIDIA/AMD/CPU processing, hardware/software encoder selection, and 480p–4K export options from 2.x.
- Version labels, executable metadata, README graphics, screenshots, and setup wording are updated for 3.0.0.

## Downloads and updating

- **Windows-x64-Setup.exe** — recommended installer; choose a destination and follow first-run setup if required.
- **Windows-x64-Portable.zip** — extract the complete folder to a writable location.
- **Source.zip** — source and build inputs for developers.
- **SHA256SUMS.txt** — checksums for all three downloads.

Close the app and install into the existing installation folder. Settings, word lists, appearance, projects, and downloaded runtime/model files are preserved; compatible environments are reused. For portable updates, back up the folder and preserve those files while replacing application files. On an upgrade from English-only 2.x settings, select a multilingual model before transcribing other languages.

## Practical notes

Local text-model servers are a separate optional installation. Online translation requires your own compatible service and may incur charges. Review automated transcription/translation before exporting. Censor transcripts and subtitle projects are separate. ASS import retains text/timing, not complex styles or effects. MP4 subtitles are permanent; MKV subtitles can be switched off in a compatible player.

Windows 10 (1809+) / Windows 11 x64. The application is unsigned. See VALIDATION.md for test coverage and limits.

<details>
<summary><strong>Earlier release changes included in 3.0</strong></summary>

# JuicyCensor 2.1.0

- Compare Original and Censored audio inside the review workspace. The first censored preview prepares a cached video using the same audio filters as export, without re-encoding the video stream.
- Editing a censor region or changing sound settings resets playback to Original so stale previews cannot hide changes. Existing Start/End fields and Apply adjust each region precisely.
- Browse and search the new Transcript tab; click a timestamped row to seek. Older reviews gain transcripts on analysis while preserving manual region edits.
- Added elapsed time and approximate time remaining below the progress bar. Estimates begin on the first run from video length and processing settings, then update from live transcription, alignment, and rendering progress.
- Preserved installer recovery, model-download fixes, and confirmed AMD RX 9060 XT support from earlier releases.

# JuicyCensor 2.0.3

- Polished Settings labels and explanations, and removed the RX 9060 XT pending-validation notice following user confirmation.
- Updated visible app/version labels and README screenshots for 2.0.3.

- Recover from Windows error 448 when uv finishes downloading Python but cannot
  create its optional minor-version directory link.
- Verify the exact Python version, 64-bit architecture, and required standard-library
  modules before continuing through the direct interpreter path.
- Keep other setup failures and cancellation visible; incomplete setup is never marked ready.
- Reuse the existing 2.0 processing runtime. Existing installations do not need to
  download Python, packages, or models again just to apply this patch.

# JuicyCensor 2.0.2

- Fixed WinError 1314 when downloading speech models on Windows accounts without
  symbolic-link privileges. Model caching now uses ordinary files on Windows.
- Reuses existing downloads and the 2.0 processing runtime; no new CUDA or Python
  installation is required for this update.
- Install over the existing application folder, then retry the failed analysis or
  setup. Settings and custom word lists are preserved.

# JuicyCensor 2.0.1

- Corrected the sidebar badge and first-run setup title to display 2.0.1.

- Centered the Start and End labels within their spaces, alongside centered timestamp values.
- Changed the subtitle to “Detect. Review. Filter the Juice.”
- Replaced the shipped word and phrase lists with ordinary profanity; removed slurs
  and the old non-profanity phrases. Existing user lists remain preserved on upgrade.
- Refreshed the README with an orange banner, a current screenshot, and clearer model
  download instructions.
- Reuses the 2.0.0 processing runtime; no dependency upgrade is needed for this patch.

# JuicyCensor 2.0.0

The new orange-themed desktop app combines detection, playback review and export.

- NVIDIA CUDA, AMD/other Vulkan and CPU speech processing.
- Saved region editing, scissors selection, timeline zoom/pan, configurable skipping,
  preview speed and volume controls.
- Export folder/filename options, MP4/Matroska, quality presets with Custom settings,
  up to 4K resolution limits, and hardware/software encoding options.
- Windows installer with destination selection and a portable ZIP.
- First-run setup for private Python, verified dependencies, runtimes and starter models.

Choose the Setup.exe for installation or extract the entire Portable.zip. The automatic
GitHub Source code archive is not a ready-to-run app. Internet is required for initial
runtime setup. The app is not code-signed.

AMD integrated Radeon and NVIDIA RTX 5060 Ti were tested locally. RX 9060 XT and a
separate physical clean PC remain untested. Review detected censor regions before sharing.



</details>
