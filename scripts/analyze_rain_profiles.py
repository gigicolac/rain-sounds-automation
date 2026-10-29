"""Measure rain texture statistics; export no source waveform or phase to synthesis."""
import json
from pathlib import Path
import subprocess
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

RATE, FFT, HOP = 24000, 1024, 256
EDGES = [80, 250, 500, 1000, 2000, 4000, 8000, 12001]


def decode(path, offset=10, duration=50):
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-ss', str(offset), '-i', str(path),
        '-t', str(duration), '-ar', str(RATE), '-ac', '2', '-f', 'f32le', '-'])
    return np.frombuffer(raw, dtype='<f4').reshape(-1, 2).astype(np.float64)


def measure(path, offset=10, duration=50):
    stereo = decode(path, offset, duration)
    x = stereo.mean(axis=1)
    frames = np.lib.stride_tricks.sliding_window_view(x, FFT)[::HOP]
    power = np.abs(np.fft.rfft(frames * np.hanning(FFT))) ** 2
    freq = np.fft.rfftfreq(FFT, 1 / RATE)
    psd = power.mean(axis=0); psd /= psd.sum()
    bands = np.stack([power[:, (freq >= lo) & (freq < hi)].sum(axis=1)
                      for lo, hi in zip(EDGES[:-1], EDGES[1:])], axis=1)
    logamp = .5 * np.log(bands + 1e-20)
    centered = logamp - logamp.mean(axis=0)
    covariance = np.cov(centered.T)
    autocorr = [float(np.corrcoef(centered[:-1, b], centered[1:, b])[0, 1]) for b in range(7)]
    rms = np.sqrt(np.mean(frames ** 2, axis=1))
    profile = dict(sample_rate=RATE, fft=FFT, hop=HOP, edges=EDGES,
        mean_psd=psd.tolist(), band_share=(bands.mean(axis=0)/bands.mean(axis=0).sum()).tolist(),
        logamp_cov=covariance.tolist(), lag1=autocorr,
        rms_p95_median=float(np.percentile(rms,95)/np.median(rms)),
        stereo_correlation=float(np.corrcoef(stereo.T)[0,1]),
        crest_db=float(20*np.log10(np.max(np.abs(x))/np.sqrt(np.mean(x*x)))),
        analyzed_seconds=len(x)/RATE, offset_seconds=offset)
    return profile, x


def main():
    root = Path(__file__).resolve().parents[1]
    library = root/'run/window-rain-library-20261029'
    assets = json.loads((library/'library.json').read_text())['assets']
    sources = [(a['title'], library/a['master'], 10) for a in assets.values()
               if 'reference' in a['intent'].get('vibes', []) or a['title'].startswith(('Forest attempt 1 ', 'Forest revision 9 '))]
    for name, video in [('YouTube - Sleep Sounds Rain No Thunder','MO1wJTMuHXg'),
                        ('YouTube - Rain Forest Thunder and Rain','GwIO1nzuJrw')]:
        path=root/f'run/youtube-analysis/{video}.webm'
        if path.is_file(): sources.append((name,path,5))
    out = root/'run/rain-profile-analysis'; out.mkdir(exist_ok=True)
    profiles={}; waveforms={}
    for name,path,offset in sources:
        profile,x=measure(path,offset)
        profile['source_file']=str(path)
        profiles[name]=profile; waveforms[name]=x
        print(name, 'bands', np.round(np.array(profile['band_share'])*100,1).tolist(),
              'envelope ratio',round(profile['rms_p95_median'],3),
              'stereo',round(profile['stereo_correlation'],3),flush=True)
    (out/'profiles.json').write_text(json.dumps(profiles,indent=2))
    fig,axes=plt.subplots(len(profiles)+1,1,figsize=(13,3+1.6*len(profiles)))
    freq=np.fft.rfftfreq(FFT,1/RATE)
    for name,p in profiles.items():
        axes[0].semilogx(freq[1:],10*np.log10(np.array(p['mean_psd'])[1:]+1e-12),label=name)
    axes[0].set(xlim=(80,12000),ylim=(-85,-5),title='Average spectrum (normalized total energy)',ylabel='Relative power (dB)')
    axes[0].legend(fontsize=7,loc='lower left',ncol=2); axes[0].grid(alpha=.2)
    extent=max(float(np.max(np.abs(x[:3*RATE]))/max(np.sqrt(np.mean(x*x)),1e-8)) for x in waveforms.values())*1.05
    for ax,(name,x) in zip(axes[1:],waveforms.items()):
        # Same RMS display level; amplitude shape remains visible.
        y=x[:3*RATE]/max(np.sqrt(np.mean(x*x)),1e-8)
        ax.plot(np.arange(len(y))[::12]/RATE,y[::12],lw=.35)
        ax.set(title=name,xlim=(0,3),ylim=(-extent,extent),ylabel='RMS units')
    axes[-1].set_xlabel('Seconds (3-second excerpt, level normalized)')
    fig.tight_layout();fig.savefig(out/'comparison.png',dpi=145);plt.close(fig)


if __name__=='__main__': main()
