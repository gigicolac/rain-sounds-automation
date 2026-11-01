# Upload at least 24 hours before public release

Prepared 1 November 2026. These changes take effect only after merge.

Public release times remain Monday and Wednesday at noon, Friday at 11am,
America/New_York. Build/upload jobs are anchored 28 hours before those slots:

| Public release, New York | Build/upload job starts, New York |
| --- | --- |
| Monday noon | Sunday 8am |
| Wednesday noon | Tuesday 8am |
| Friday 11am | Thursday 7am |

From 2 November 2026, Sydney is 16 hours ahead of New York: jobs start Monday
midnight, Wednesday midnight, and Thursday 11pm Sydney, with public releases
Tuesday 4am, Thursday 4am, and Saturday 3am. The workflow uses New York's time
zone so the release anchors follow US daylight saving automatically; Sydney
conversions change when either region changes its clocks. Actions can start late.

Every intended public upload is transferred as **Private without publishAt**.
The response time is recorded as upload_completed_at before thumbnail or
processing work. Once processing succeeds, the pipeline selects the next free
configured release slot at least 24 hours from the scheduling check. That is at
least 24 hours after transfer, even if transfer or processing was delayed.
Occupied same-channel release slots are skipped. The chosen slot is saved in
history before YouTube is updated, and confirmation is required before the run
is marked complete. Status updates preserve writable audience, disclosure,
licence, embedding and statistics settings.

A processing, thumbnail, history or scheduling failure leaves the new video
private. Resume the recorded video ID, never create another upload. If YouTube
accepted a schedule before the worker stopped, resume reconciles the matching
schedule instead of moving it again. A missing upload completion time or an
unexpected existing schedule fails closed and requires history reconciliation.
An already confirmed video that has since been released is not rescheduled.

Immediate public release (publish_timing=now) is disabled. Explicit private or
unlisted tests stay unscheduled. Existing videos and their visibility are not
changed by this implementation. Future public scheduling uses the existing
youtube.force-ssl grant, already required for automatic comments; no new key is
needed. Authentication verification checks this scope before rendering.

The 28-hour job lead allows four hours for the normal build/upload/processing
path. A job delayed beyond that allowance can miss its intended slot, in which
case it moves to a later free release slot; the 24-hour minimum wins. This buffer
does not certify copyright clearance or prevent later claims. Studio review of
copyright notices remains separate from processing success.

API status update and permission reference:
https://developers.google.com/youtube/v3/docs/videos/update
