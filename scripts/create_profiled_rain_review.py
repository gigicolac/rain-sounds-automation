"""Fresh stochastic rain from coarse measured spectrum/modulation/stereo statistics.

This synthesis reads statistics only: no reference samples, phases, envelope
sequences or event timings are carried into the output.
"""
import argparse
import json
from pathlib import Path
import subprocess
import wave
import numpy as np
from analyze_rain_profiles import RATE, FFT, HOP, EDGES, measure
from asset_library import write_json
from channel_profile import digest
from media_quality import audio_report, ffmpeg, probe


def synthesize(profile, seed, duration=90):
    rng=np.random.default_rng(seed); count=int(duration*RATE)
    bins=np.fft.rfftfreq(count,1/RATE)
    target=np.interp(bins,np.fft.rfftfreq(FFT,1/RATE),profile['mean_psd'])
    target[bins<80]=0
    # Broad overlapping statistical bands, rather than copied fine spectral peaks.
    centers=np.sqrt(np.array(EDGES[:-1])*np.array(EDGES[1:]))
    logbins=np.log(np.maximum(bins,1)); logcenters=np.log(centers)
    weights=np.stack([np.interp(logbins,logcenters,np.eye(7)[b],left=float(b==0),right=float(b==6)) for b in range(7)])
    steps=int(np.ceil(count/HOP))+2
    covariance=np.array(profile['logamp_cov'])
    eig,vec=np.linalg.eigh(covariance)
    transform=vec@np.diag(np.sqrt(np.maximum(eig,0)))
    rho=float(np.clip(np.median(profile['lag1']),.15,.96))
    z=np.zeros((steps,7)); z[0]=transform@rng.standard_normal(7)
    innovations=rng.standard_normal((steps,7))@transform.T*np.sqrt(1-rho*rho)
    for t in range(1,steps): z[t]=rho*z[t-1]+innovations[t]
    # Lower-frequency measurement noise should not cause huge artificial swells.
    mods=np.exp(np.clip(z-.5*np.diag(covariance),-1.8,1.8))
    result=np.zeros((count,2),dtype=np.float32)
    correlation=float(np.clip(profile['stereo_correlation'],0,.95))
    for band in range(7):
        shaping=np.sqrt(target*weights[band])
        def carrier():
            noise=rng.standard_normal(count).astype(np.float32)
            return np.fft.irfft(np.fft.rfft(noise)*shaping,n=count).astype(np.float32)
        shared=carrier()
        modulation=np.interp(np.arange(count),np.arange(steps)*HOP,mods[:,band])
        for channel in range(2):
            signal=np.sqrt(correlation)*shared+np.sqrt(1-correlation)*carrier()
            result[:,channel]+=signal*modulation
    result*=.95/max(float(np.max(np.abs(result))),.0001)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()): raise ValueError('Use a new folder; preserve existing candidates')
    args.output.mkdir(parents=True,exist_ok=True)
    root=Path(__file__).resolve().parents[1]
    profiles=json.loads((root/'run/rain-profile-analysis/profiles.json').read_text())
    reference=profiles['Week 2 / 20 - Ranger cabin shelter']
    youtube=profiles['YouTube - Sleep Sounds Rain No Thunder']
    hybrid=dict(reference)
    hybrid['mean_psd']=(.9*np.array(reference['mean_psd'])+.1*np.array(youtube['mean_psd'])).tolist()
    hybrid['logamp_cov']=(.9*np.array(reference['logamp_cov'])+.1*np.array(youtube['logamp_cov'])).tolist()
    hybrid['stereo_correlation']=.65
    targets=[('11-reference-statistics','Measured attempt 11 - forest reference texture',reference),
             ('12-sleep-forest-balance','Measured attempt 12 - forest with sleep-rain balance',hybrid)]
    records=[]
    for index,(slug,title,target) in enumerate(targets):
        seed=2026102950+index; folder=args.output/slug;folder.mkdir()
        print('Synthesizing '+title,flush=True)
        samples=synthesize(target,seed)
        raw=folder/'synthesized.wav'
        with wave.open(str(raw),'wb') as stream:
            stream.setnchannels(2);stream.setsampwidth(2);stream.setframerate(RATE)
            stream.writeframes((samples*32767).astype('<i2').tobytes())
        initial=audio_report(raw);gain=-22-float(initial['loudness']['input_i'])
        master=folder/(slug+'.flac')
        subprocess.run([ffmpeg(),'-y','-v','error','-i',str(raw),'-af',
            f'volume={gain}dB,alimiter=limit=0.63:level=false,afade=t=in:d=0.1,afade=t=out:st=89.9:d=0.1',
            '-ar','48000','-c:a','flac',str(master)],check=True)
        report=audio_report(master);report['duration_seconds']=float(probe(master)['format']['duration'])
        report['technical_pass']=report['duration_seconds']==90 and report['peak_db']<-.1 and not report['silence_seconds']
        write_json(folder/'quality.json',report)
        subprocess.run([ffmpeg(),'-y','-v','error','-i',str(master),'-c:a','libmp3lame','-b:a','192k',str(folder/'listen.mp3')],check=True)
        statistics={k:target[k] for k in ('mean_psd','logamp_cov','lag1','stereo_correlation')}
        write_json(folder/'statistical-target.json',statistics)
        generated,_=measure(master)
        write_json(folder/'measured-output-profile.json',generated)
        print('Output envelope ratio',round(generated['rms_p95_median'],3),'stereo',round(generated['stereo_correlation'],3),flush=True)
        records.append(dict(id=f'custom-audio:profiled-{seed}-{slug}',title=title,path=str(master.relative_to(args.output)),
            duration=90,sha256=digest(master),generator_sha256=digest(Path(__file__)),
            generator_source_url='local:scripts/create_profiled_rain_review.py',
            components=[dict(kind='procedural',seed=seed,method='Fresh noise carriers and random multiband envelopes matched to coarse statistical spectrum, covariance, persistence and stereo correlation; no source samples or source timing',
                             profile=dict(source=None,target=slug,statistics_sha256=digest(folder/'statistical-target.json')))],
            intent=dict(heaviness='heavy',environment='forest',vibes=['measured-rain','comparison','dense']),
            target_lufs=float(report['loudness']['input_i']),technical_pass=report['technical_pass'],
            review=dict(approved=False,status='pending',labels={},notes='Statistically guided experiment; full listening and boundary review required')))
    write_json(args.output/'candidates.json',records)


if __name__=='__main__': main()
