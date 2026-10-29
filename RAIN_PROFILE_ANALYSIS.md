# Rain waveform and texture analysis - 29 October 2026

Measured 50-second excerpts from both approved local tracks, forest attempt 1,
revision 9, and two YouTube examples. These are excerpt-level measurements,
not a listening approval or a survey of all sleep-rain audio.

YouTube sources (local analysis excerpts only, not included in synthesis):
- Sleep Sounds Rain No Thunder: https://www.youtube.com/watch?v=MO1wJTMuHXg
- Rain Forest Thunder and Rain: https://www.youtube.com/watch?v=GwIO1nzuJrw
  This example includes thunder in its premise and is excluded as a synthesis target.

## Findings

The approved references have stronger, more persistent variation in their upper
frequency bands. Their bandwise log-amplitude standard deviation is about 0.17
in the 2-8 kHz range, compared with about 0.10 in attempts 1 and 9. Their stereo
correlation is about 0.55, versus about 0.06-0.07 in the earlier synthesized
attempts. Increasing treble in revision 9 changed average brightness but did not
fix these temporal/stereo differences.

The YouTube examples have considerably more low-frequency energy and stronger
left/right correlation (0.70-0.76). They are different sound designs, not evidence
that all sleep-rain should have a single spectrum. Both approved references use
the same underlying recording, so they are not independent natural examples.

## New synthesis

Measured attempt 11 uses the approved reference spectrum, band-envelope covariance,
persistence and stereo correlation as targets. Measured attempt 12 blends 90 percent
of that spectral target with 10 percent of the no-thunder example, with a slightly
more centered stereo image. The thunder example contributes no synthesis target.

The generator uses fresh noise carriers, fresh phase and fresh stochastic multiband
envelopes. No source waveform samples, envelope sequences or event timings are
copied. Average power-spectrum bins and coarse statistical parameters are the only
inputs. No source audio is embedded in either generated candidate.

Using identical analysis settings, reference short-term level ratios (95th percentile
to median) are 1.25-1.32; attempts 1/9 are 1.13-1.15; new attempts 11/12 are 1.26/1.24.
Stereo correlations of the new outputs are 0.55 and 0.65. This is closer to the
measured target, but matching statistics does not establish perceptual naturalness.

Both new outputs are 90 seconds, passed duration/peak/silence/provenance checks,
and remain pending full listening and loop review. They appear in Rain Atelier
under `measured-rain`, with repeat-boundary auditions. No publishing changes.

## Artifacts and reproduction

- `run/rain-profile-analysis/comparison.png`: normalized spectrum and waveform plots.
  RMS means root mean square; waveform panels use the same RMS display level.
- `run/rain-profile-analysis/profiles.json`: measured source statistics.
- `run/profiled-rain-attempt-20261029/`: generated packages, exact statistical targets,
  measured output profiles, masters, listening copies and technical reports.
- `scripts/analyze_rain_profiles.py`: local-source measurement and plotting.
- `scripts/create_profiled_rain_review.py --output run/NEW-DIRECTORY`: fresh generation.

The analysis helper yt-dlp is isolated under ignored `run/analysis-tools`.
No project dependency file or publishing runtime was changed. Source files and
analysis outputs remain outside Git. Generator smoke checks passed for finite
stereo data, duration, pre-master headroom, same-seed reproduction and distinct
seeds. The full publishing test suite was not rerun for this local experiment.
