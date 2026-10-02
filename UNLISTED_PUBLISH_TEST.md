# Approved unlisted sourcing test

The user requested a full YouTube publication, unlisted, after viewing the newly
sourced clip 379717. This branch pins that scene and accepted rain recording
695619 for a five-minute upload. The existing channel checks and upload-history
rules still apply; no review bypass or reservation deletion is used.

The workflow accepts per-run visibility without changing the shared repository
variable. Manual runs default to the existing configured setting; scheduled runs
retain the existing fallback. This test explicitly uses unlisted visibility.

IMPORTANT: The storage configuration and manifest on this branch describe a
single-scene private test bundle. Do not merge them into main: the existing
production bundle and eleven-scene configuration remain on main. The new scene
is added to this branch's profile only for the authorized publication. No actual
loop/listening review flags were fabricated. Automatic source/output checks must
pass before upload, and YouTube processing/actual visibility must be verified.

Source/evidence: private sourcing release sourcing-36859935300-1. Test media:
private release unlisted-test-379717-20261001. Original source media is preserved.

Validation on 2026-10-01: publication run 36861051300 stopped at YouTube channel
verification because saved authorisation could not be refreshed. Upload and
history reservation steps were skipped. No YouTube video was created.

The same pinned scene/audio rendered successfully as a full five-minute preview
in run 36861311532. The downloaded output SHA-256 matched the passed quality
report. A local Google consent helper was opened to reconnect the expected
channel and securely update the three matching GitHub secrets; user consent is
still pending. Retry the unlisted publish only after reconnect succeeds. Do not
describe the successful preview as an upload or YouTube processing result.

Completed 2026-10-02: local Google consent verified the expected Calming Rain Sounds
channel and securely replaced all three matching GitHub YouTube secrets. Publishing
run 36966210464 completed successfully. YouTube processing was verified, actual
visibility is unlisted, thumbnail was set, and the final audio duration is 300 seconds.
Video: https://www.youtube.com/watch?v=3igpnr0FEbs

The earlier preview audio cutoff was corrected in f257e44. Corrected preview run
36863317464 had 300 seconds of audio, with sound verified at 75, 150 and 290 seconds.
The production audio fix is isolated in PR #5 and is still awaiting merge approval.
Do not merge this test branch's temporary single-scene storage configuration.
