# Juicy Studio video editor roadmap

Direction: one editing project that combines cuts, censor regions, subtitles,
translation, and enhancement. **Juicy Studio** is the selected product name,
retaining the orange identity. Existing projects and the published JuicyCensor
3.0 release remain supported.

## Editor foundation: included in Juicy Studio 1.0

Edit is now the primary workspace. A versioned `.juicy` project references a
media bin and a continuous video/audio timeline. The first implementation adds
trim by dragging edges or entering source times, split, reorder, ripple removal,
undo/redo, autosave and recovery, relinking, speed, volume, basic color controls,
and MP4/MKV export with H.264, HEVC, or AV1 and hardware/CPU encoder selection.

Source subtitles and censor regions attach to media, and one central mapping
handles their timing through cuts and speed changes. Attached subtitle text is
visible in the editor preview and can be burned on export; attached censor
regions can be muted on export. The existing dialogue and enhancement workspaces
remain available. See [editing workflow and limits](EDITOR-DEVELOPMENT.md).

## Next: multiple tracks and responsive editing

1. Add independent video and audio tracks, clip gaps, drag positioning, track
   mute/solo/lock, and snapping. Extend the project/render model first so preview
   and export agree about compositing and timing.
2. Add titles, overlays, opacity, transforms, fades, and a small set of useful
   transitions. Keyframes should share one interpolation model with export.
3. Build proxy media and short render caching for responsive playback and live
   color/effect previews. Include a clear comparison against the source.
4. Add audio mixing, fades, peak meters, volume envelopes, and multiple source
   audio-track selection. Test cuts and speed changes for sync and boundary clicks.
5. Integrate enhancement as a clip effect in the editing project, with reusable
   frame caches and one final encode. Finish HDR/color-management support before
   allowing HDR export.

## Continue validating Enhance

The 3.1 prototype establishes local AI upscaling and preview comparison. Before
calling it a stable release, validate the desktop launch/build, longer clips,
motion consistency, GPU detection, and cleanup; persist preferences; improve
preview controls and long-video performance. Target-resolution choices are now
implemented. Keep unsupported HDR workflows
explicit instead of silently degrading their color or dynamic range.

## Shared-project design requirements

Extend the project data model before adding more independent workspace features.
A project should reference original media and store edits separately:

- A media bin shared by every workspace, with clear missing-file relinking.
- A primary video/audio timeline with trim, split, reorder, delete-gap, and undo.
- Censor regions and subtitles attached to clips so they move with edits.
- Autosave, project versioning, and import/migration of existing subtitle work.
- One export view for the complete result, preserving original audio when edits
  and the container allow stream copying. Explain when processing requires
  audio/video re-encoding.

Define source-time versus timeline-time mapping centrally. Do not copy timing
conversion into each workspace; a trim or split must update playback, censoring,
subtitle timing, and export consistently. Test edit boundaries and audio sync.

## Then: deliberate expansion

Add additional tracks, volume envelopes, simple transitions, and basic color
controls after the single-track workflow is reliable. Build proxy media and
background render caching for responsive previews. Add denoising or restoration
only with meaningful comparison controls and temporal-quality validation.

For normal SDR work, compose the final image in this order: source selection and
edits, image enhancement, then subtitle/text overlays. Avoid repeated intermediate
lossy encodes. Reuse the same processing graph for preview and final export.

## Product boundaries

Aim first at people preparing dialogue-heavy videos, translated clips, and
cleaned-up footage. Do not claim to replace a full professional editor immediately.
Keep speech and enhancement models optional and local by default. Preserve the
option to use an online translation provider with a user-supplied key.

Selected name: **Juicy Studio**. Name/domain/trademark availability has not been
researched. Juicy Studio 1.0 uses the new name. Its installer preserves the Studio preview
identity and updates its branding; JuicyCensor remains a separate installation.
Existing JuicyCensor downloads and release history remain available. Projects
reference their original media, so retain those files when moving installations.
