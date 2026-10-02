# Three-hour public publishing

User authorized a public three-hour upload using scene `local:study-room`
(Pixabay 330062) and recording 695619, with the approved COZY RAIN thumbnail
layout. Future scheduled posts use three hours as well.

The daily action starts at 11am Australia/Sydney, including daylight saving.
Build and YouTube processing finish later; this is not an exact 11am release
guarantee. Manual runs still default to preview. Scheduled runs publish publicly.

Long-form output encodes the normalized 1080p seamless visual cycle once, then
copies compressed frames while encoding the full crossfaded rain soundtrack.
The short introductory title overlay is omitted on long-form output. Titles and
thumbnails use hours; the description states the equivalent number of minutes.
Video and audio duration, complete decoding, resolution and audio peaks remain
required checks. The previous audio-cutoff repair from PR #5 is included.

A completed, verified private/unlisted test no longer blocks a new public
release on the same date. Reserved, uncertain, public or unknown-visibility
uploads still block it. Every previous entry is retained and duplicate source
pairs remain permanently blocked.

Automatic scene selection reconstructs a cycle from upload history and uses every
available scene before repeating one, regardless of which audio is selected.
Reservations count as uses, so uncertain uploads cannot bypass rotation. Missing
files, missing source records, rejected assets and scenes with no unused audio
pair are excluded. Within a cycle, selection favors less recent and less-used
scenes. Explicit manual scene overrides remain available. History is preserved.

The thumbnail renderer applies the approved cream/amber COZY RAIN layout to
an original video screenshot and adds the actual duration. Generated design
mockups are not source frames and are not committed. The template is reusable,
so daily runs require no image-generation service or separate asset approval.
Rounded lettering uses the bundled Nunito typeface from Google Fonts; its
SIL Open Font License is included in `fonts/nunito/OFL.txt`.
Native YouTube title/thumbnail A/B experiments are not started by this workflow.
Those need YouTube Studio; different video lengths are not native A/B variants.

The channel exposes native A/B testing in Studio. Suggested title-only variants
for the first public upload, keeping the chosen COZY RAIN thumbnail:

1. Cozy Rainy Study Room | 3 Hours of Rain Sounds
2. Rain Sounds for Studying | Cozy Anime Room (3 Hours)
3. Rainy Evening at Your Desk | 3 Hours of Rain Ambience

Scheduled titles rotate between cozy evening, study/relaxation and rainy escape
wording. `run/assets.json` includes three correctly timed `title_options` for
native title experiments. Creating those options does not start an experiment.

The temporary single-scene private-storage configuration on
`codex/unlisted-sourcing-test` is not included here. All eleven channel scenes
remain available for scheduled rotation. No audio source metadata is changed.

## Validation and authorization status (2026-10-02)

The public three-hour upload completed successfully on the task branch:
[run 36974548325](https://github.com/gigicolac/rain-sounds-automation/actions/runs/36974548325),
[YouTube video](https://www.youtube.com/watch?v=EXjpeDzwuAs).
Final output checks passed: 1920x1080, video 10800.066667 seconds, audio 10800
seconds, complete video decoding, and no detected black intervals. YouTube
processing completed, actual visibility was public, and the thumbnail was set.
An earlier preview failed on the old 600-second full-video check timeout; the
publishing run used the corrected timeout and scaled black-detection analysis.
The rounded Nunito thumbnail refinement followed that live run and was checked
locally; subsequent scheduled runs use the current template.

Google sign-in and the matching GitHub upload credentials were repaired; this
is proven by the successful upload. A fresh Google Cloud Audience check still
shows the existing app in Testing, with Publish app disabled pending Branding
configuration. This is separate from credential repair. Google documents a
[seven-day refresh-token limit for external Testing apps](https://developers.google.com/identity/protocols/oauth2#expiration).
Production setup and renewed authorization remain needed for unattended operation
beyond that window. No Google app settings were changed by this publishing merge.

Scene-cycle regression tests simulate all 33 combinations over three complete
eleven-scene cycles, check uneven history and reservations, and preserve pair
exhaustion protection. Scheduled sourcing is still gated by SOURCING_ENABLED;
new candidates are not automatically enrolled in the publishing pool.
