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
