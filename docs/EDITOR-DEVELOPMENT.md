# Juicy Studio editing workspace

Juicy Studio opens in **Edit**. Original media stays intact; a `.juicy`
project stores references, trim points, clip order, speed, volume, source
annotations, canvas settings, and export preferences.

## Make an edit

1. Choose **Import media**, or drop video files into Edit. Imports read metadata
   in the background. Double-click a source to append it to the timeline.
2. Click a clip to select it. Drag either edge to trim, or enter **Source start**
   and **Source end** in the Clip inspector and apply the changes.
3. Click the timeline to place the playhead, then **Split**. **Remove** closes
   the gap. **Move left/right** reorders the selected clip. Undo and Redo cover
   project changes. Scroll to zoom, use the scrollbar to pan, or choose Fit.
4. Set clip speed and volume in Clip. In Color, adjust brightness, contrast,
   and saturation, then apply. The player previews original color; export
   applies the color adjustments. Waveforms load automatically in the background.
5. Save the project with **Ctrl+S** from any workspace. **File → Projects…**
   opens a searchable window of saved/recent projects, the current draft, and
   recovery copies. You can create a project or browse for another `.juicy` file.
   Edits also autosave locally. Missing sources are marked in the bin; use
   **Relink media** to point to the original file at its new location.
   Previous edits are preserved when creating or opening a project; **File →
   Recover autosaved edit** opens those recovery copies. Within Edit, Space plays
   or pauses, S splits at the playhead, and Delete removes the selected clip.
6. In Output, choose the canvas and frame rate, then **Apply canvas**. Clips fit
   with letterboxing, retaining their proportions. Choose H.264, HEVC, or AV1,
   Automatic or a specific encoder, quality, encoding speed, and AAC bitrate.
   **Export edit** creates a new MP4 or MKV. Existing files are not overwritten.

## One project across workspaces

Switch directly between **Edit**, **Censor**, **Subtitles & Translation**, and
**Enhance**. They open the same edited timeline. Censor regions, transcript words,
subtitle text, translations, and subtitle styling return to the project
automatically. The former manual transfer buttons are no longer needed.

For a changed timeline, the app prepares a cached working video with lossless
FFV1 video and PCM audio. This can take time and disk space; progress, elapsed
time, and an estimate appear while it is prepared. The cache is reused until
the edit changes. An unchanged single source opens directly. Analysis reads the
uncensored working audio; final editor/subtitle exports render the original
project media with the current edits and annotations.

If you work on a source in Censor or Subtitles before creating an editing
timeline, its annotations transfer when the source is imported into Edit. Opening
Edit from that standalone source creates its first timeline clip automatically.

Enhance receives the edited project. After a full enhanced export, choose
**Apply enhanced video to project** to use it as editable project media. Existing
subtitle/censor timing carries over. This renders the enhancement into a new
source clip; Undo restores the previous timeline, and **Edit → Restore timeline
before enhancement** also works after saving/reopening. Original source files
stay in the project media bin.

Annotations remain in each clip's source time and are mapped through trims,
splits, speed changes, and reordering. Repeated uses of one source can have
different censor/subtitle edits. Output honors the selected censor style, including
beeps and custom sounds. Censor's audio preview remains available to audition the
result. Edit's player previews source audio with clip volume and speed. Subtitle
MP4 export burns the project subtitles; MKV export creates a switchable subtitle
track while rendering the edited video.

## Current scope

This is the first editor foundation: a continuous primary video track with linked
audio. It supports multiple source clips, including clips without audio, mixed
dimensions/frame rates, color adjustments, and subtitle/censor integration.
Export normalizes audio to stereo AAC and re-encodes video in one pass. It uses
the first audio track from each source. Quality numbers vary in meaning across
encoders; lower numbers generally retain more detail and increase file size.

Additional video/audio tracks, gaps and overlays, transitions, titles, keyframes,
audio mixing, lightweight proxies, clip enhancement effects, and live color preview are
planned next. FPS conversion currently repeats/drops frames; it does not generate
motion-interpolated frames. HDR export is rejected rather than silently changing
dynamic range. Save projects before moving an installed runtime; project media
references can be relinked separately.

Validation includes time-mapping boundaries, undo/redo snapshots, a real render
with mixed-size clips, a speed change, a silent source, burned subtitles, censor
muting, and desktop-workspace navigation. See `EDITOR-ROADMAP.md` for expansion.

## Tracks and storage

Click the speaker icon below the Edit preview for a compact vertical volume
slider, percentage and mute control. Censor, Subtitles and Enhance also use
compact vertical volume controls. Preview volume does not affect exported
audio; use Clip volume to change the mix saved in the video.

**Help → User guide…** (F1) opens the built-in guide window, with topic
navigation, page search, and the bundled README and development guides.

The timeline starts with separate **Video 1** and **Audio 1** lanes. Use the
small **+** and **×** controls beside a lane to add or remove tracks. Assign
a selected clip’s video and audio lanes in the Clip inspector. Removing a
populated lane moves its clips to the first remaining lane of the same type.
At least one video and one audio lane remain. These lanes organize a linked
sequence: trimming stays synchronized, and overlapping layers or independent
audio mixing are not implemented yet. Track assignments save with the project
and support Undo and Redo.

**File → Storage & uninstall…** previews temporary processing files, speech
alignments and logs before removal. Models, projects, subtitle edits, censor
reviews and exports are preserved during cache cleanup. Playback pauses and
working files are rebuilt when needed. Locked files and linked folders are
skipped.

Installed builds offer **Uninstall app** (preserve local data) or **Remove app
and all local data** (also delete this installation’s downloaded runtime,
models, cache, settings, projects and exports). Copy anything you want to keep
outside the installation folder first. External files and shared runtimes are
not removed. Source and portable copies have no registered uninstaller.
