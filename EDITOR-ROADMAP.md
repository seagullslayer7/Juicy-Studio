# Toward a focused video editor

Direction: one editing project that combines cuts, censor regions, subtitles,
translation, and enhancement. **Juicy Studio** is the selected product name,
retaining the orange identity. Existing projects and the published JuicyCensor
3.0 release remain supported.

## First: finish Enhance

The 3.1 prototype establishes local AI upscaling and preview comparison. Before
calling it a stable release, validate the desktop launch/build, longer clips,
motion consistency, GPU detection, and cleanup; persist preferences; improve
target-resolution choices and preview controls. Keep unsupported HDR workflows
explicit instead of silently degrading their color or dynamic range.

## Next: shared projects and basic editing

Build the project data model before adding more independent workspace features.
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
researched. The development UI uses the new name; legacy package filenames and
installer identity remain in place until the upgrade migration is tested. A rename
must also account for installer upgrade identity, project associations, settings
paths, and GitHub links; changing a title alone is not a complete migration.
