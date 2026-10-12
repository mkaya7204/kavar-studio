"""Build the video's full soundtrack: re-timed voiceover + music bed + transition SFX.

- The voiceover is cut between its scene parts and short silences are inserted, so each
  scene can start exactly when its part is spoken (see hyperframes_builder.plan_timeline).
- Music: the first file in assets/music/ (mp3/wav/m4a/ogg) if there is one, looped to length;
  otherwise a royalty-free synth bed is generated here (A minor, 104 BPM).
- SFX (whoosh / pop / impact / ding) are synthesized, so nothing needs downloading.
- The music ducks under the voice; the mix is loudness-normalised to -14 LUFS (social video norm).
"""

import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MUSIC_DIR = ROOT / "assets" / "music"
RATE = 48_000
MUSIC_GAIN = 0.30  # music level relative to voice (before ducking)
DUCK = 0.55  # how much the music drops while the voice speaks (0..1)
SFX_GAIN = 0.55


class SoundtrackError(Exception):
    """The soundtrack could not be built."""


def load_audio(path: Path | str, channels: int = 1) -> np.ndarray:
    """Decode any audio file to float32 at RATE; shape (n,) for mono, (n, 2) for stereo."""
    try:
        out = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", str(channels),
             "-ar", str(RATE), "-"],
            capture_output=True, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SoundtrackError(f"could not decode {path}: {exc}") from exc
    data = np.frombuffer(out, dtype=np.float32).copy()
    return data.reshape(-1, channels) if channels > 1 else data


def retime(voice: np.ndarray, cuts: list[float], pauses: list[float]) -> np.ndarray:
    """Insert pauses[i] seconds of silence at cuts[i] seconds (cuts ascending)."""
    pieces, prev = [], 0
    for cut, pause in zip(cuts, pauses):
        at = min(len(voice), max(prev, round(cut * RATE)))
        pieces += [voice[prev:at], np.zeros(round(max(0.0, pause) * RATE), dtype=np.float32)]
        prev = at
    pieces.append(voice[prev:])
    return np.concatenate(pieces)


# ---------------------------------------------------------------- music bed

def _midi(n: float) -> float:
    return 440.0 * 2 ** ((n - 69) / 12)


def _lowpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    """Zero-phase FFT lowpass with a gentle roll-off."""
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / RATE)
    spec *= 1 / (1 + (f / cutoff) ** 4)
    return np.fft.irfft(spec, len(x)).astype(np.float32)


def synth_music(seconds: float, bpm: float = 104.0) -> np.ndarray:
    """A calm synthwave bed: pad + pulsing bass + soft kick/hat + quiet arp. Stereo (n, 2)."""
    n = round(seconds * RATE)
    t = np.arange(n) / RATE
    beat = 60 / bpm
    bar = 4 * beat
    # Am - F - C - G: (bass note, pad notes)
    chords = [(45, (57, 60, 64)), (41, (53, 57, 60)), (48, (55, 60, 64)), (43, (55, 59, 62))]
    bar_idx = (t // bar).astype(int)
    chord_of = bar_idx % len(chords)
    in_bar = t - bar_idx * bar
    in_beat = t % beat

    # Pad: detuned band-limited saws, one smooth envelope per bar (crossfaded).
    pad = np.zeros(n, dtype=np.float32)
    for ci, (_, notes) in enumerate(chords):
        mask = chord_of == ci
        if not mask.any():
            continue
        env = np.clip(in_bar / 0.35, 0, 1) * np.clip((bar - in_bar) / 0.25, 0, 1)
        voice = np.zeros(n, dtype=np.float32)
        for note in notes:
            for detune in (0.9985, 1.0015):
                f0 = _midi(note) * detune
                for k in range(1, 7):
                    voice += (np.sin(2 * np.pi * f0 * k * t) / k).astype(np.float32)
        pad += np.where(mask, voice * env, 0).astype(np.float32)
    pad = _lowpass(pad, 1400) * 0.05

    # Bass: root on 8th notes with a pluck envelope.
    root = np.array([_midi(c[0]) for c in chords])[chord_of]
    eighth = t % (beat / 2)
    bass_env = np.exp(-eighth / 0.16)
    phase = 2 * np.pi * np.cumsum(root) / RATE
    bass = (np.sin(phase) + 0.35 * np.sin(2 * phase)) * bass_env * 0.22

    # Kick on every beat, hat on the off-beats.
    # Pitch drops 120 -> 45 Hz; phase is the closed-form integral, restarting every beat.
    kick_phase = 2 * np.pi * (45 * in_beat + 75 * 0.03 * (1 - np.exp(-in_beat / 0.03)))
    kick = np.sin(kick_phase) * np.exp(-in_beat / 0.22) * 0.55
    rng = np.random.default_rng(7)
    noise = rng.standard_normal(n).astype(np.float32)
    hat_noise = noise - _lowpass(noise, 6000)
    off = (t + beat / 2) % beat
    hat = hat_noise * np.exp(-off / 0.025) * 0.06

    # Arp: chord tones an octave up, 8th notes, soft pluck.
    arp_notes = np.array([[n_ + 12 for n_ in c[1]] for c in chords])
    step = (t // (beat / 2)).astype(int)
    arp_f = 440.0 * 2 ** ((arp_notes[chord_of, step % 3] - 69) / 12)
    arp_phase = 2 * np.pi * np.cumsum(arp_f) / RATE
    arp = (np.sin(arp_phase) + np.sin(3 * arp_phase) / 9) * np.exp(-eighth / 0.12) * 0.07

    # Sidechain pump from the kick on the tonal parts.
    pump = 1 - 0.45 * np.exp(-in_beat / 0.13)
    mono = (pad + bass) * pump + kick + hat
    left = mono + arp * 0.6
    right = mono + np.roll(arp, round(0.18 * RATE)) * 0.6  # delayed arp on the right: width
    music = np.stack([left, right], axis=1).astype(np.float32)
    fade = np.clip(t / 0.4, 0, 1) * np.clip((seconds - t) / 1.6, 0, 1)
    music *= fade[:, None]
    return music / max(1e-6, np.abs(music).max()) * 0.9


def load_music(seconds: float) -> tuple[np.ndarray, str]:
    """User music from assets/music/ if present (looped/trimmed), else the synth bed."""
    files = sorted(p for p in MUSIC_DIR.glob("*") if p.suffix.lower() in {".mp3", ".wav", ".m4a", ".ogg"}) \
        if MUSIC_DIR.exists() else []
    n = round(seconds * RATE)
    if files:
        music = load_audio(files[0], channels=2)
        if len(music):
            music = np.tile(music, (int(np.ceil(n / len(music))), 1))[:n]
            t = np.arange(n) / RATE
            music *= (np.clip(t / 0.4, 0, 1) * np.clip((seconds - t) / 1.6, 0, 1))[:, None]
            return music / max(1e-6, np.abs(music).max()) * 0.9, files[0].name
    return synth_music(seconds), "synth"


# ---------------------------------------------------------------- SFX

def _whoosh(dur: float = 0.5) -> np.ndarray:
    n = round(dur * RATE)
    t = np.arange(n) / RATE
    noise = np.random.default_rng(3).standard_normal(n)
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 2
    # Time-varying one-pole lowpass: cutoff sweeps up then down.
    cutoff = 400 + 4200 * env
    alpha = 1 - np.exp(-2 * np.pi * cutoff / RATE)
    out = np.empty(n)
    y = 0.0
    for i in range(n):
        y += alpha[i] * (noise[i] - y)
        out[i] = y
    out *= env
    pan = np.clip(t / dur, 0, 1)  # left -> right
    stereo = np.stack([out * (1 - pan * 0.7), out * (0.3 + pan * 0.7)], axis=1)
    return stereo / np.abs(stereo).max() * 0.7


def _pop(dur: float = 0.12) -> np.ndarray:
    t = np.arange(round(dur * RATE)) / RATE
    f = 520 + 600 * np.exp(-t / 0.02)
    s = np.sin(2 * np.pi * np.cumsum(f) / RATE) * np.exp(-t / 0.035)
    return np.stack([s, s], axis=1) * 0.6


def _impact(dur: float = 1.0) -> np.ndarray:
    t = np.arange(round(dur * RATE)) / RATE
    f = 32 + 70 * np.exp(-t / 0.08)
    boom = np.sin(2 * np.pi * np.cumsum(f) / RATE) * np.exp(-t / 0.35)
    noise = np.random.default_rng(5).standard_normal(len(t))
    crack = _lowpass(noise.astype(np.float32), 2500) * np.exp(-t / 0.05) * 0.5
    s = boom + crack
    return np.stack([s, s], axis=1) / np.abs(s).max() * 0.9


def _ding(dur: float = 0.9) -> np.ndarray:
    t = np.arange(round(dur * RATE)) / RATE
    s = (np.sin(2 * np.pi * 1318.5 * t) + 0.6 * np.sin(2 * np.pi * 1975.5 * t)) * np.exp(-t / 0.25)
    s *= np.clip(t / 0.004, 0, 1)
    return np.stack([s, s], axis=1) / np.abs(s).max() * 0.5


SFX = {"whoosh": _whoosh, "pop": _pop, "impact": _impact, "ding": _ding}


def render_sfx(events: list[tuple[float, str]], seconds: float) -> np.ndarray:
    n = round(seconds * RATE)
    out = np.zeros((n, 2), dtype=np.float32)
    cache: dict[str, np.ndarray] = {}
    for at, kind in events:
        clip = cache.setdefault(kind, SFX[kind]().astype(np.float32))
        i = max(0, round(at * RATE))
        j = min(n, i + len(clip))
        if i < j:
            out[i:j] += clip[: j - i]
    return out


# ---------------------------------------------------------------- mix

def _moving_mean(x: np.ndarray, win: int) -> np.ndarray:
    """Centered moving average in O(n) (np.convolve is O(n*win))."""
    c = np.concatenate([[0.0], np.cumsum(x, dtype=np.float64)])
    lo = np.clip(np.arange(len(x)) - win // 2, 0, len(x))
    hi = np.clip(lo + win, 0, len(x))
    return (c[hi] - c[lo]) / np.maximum(1, hi - lo)


def _speech_envelope(voice: np.ndarray) -> np.ndarray:
    """0..1 'voice is speaking' curve: ~350 ms hold, ~120 ms smoothing."""
    rms = np.sqrt(_moving_mean(voice.astype(np.float64) ** 2, round(0.03 * RATE)))
    speaking = (rms > 0.1 * max(1e-6, rms.max())).astype(np.float64)
    speaking = (_moving_mean(speaking, round(0.35 * RATE)) > 0).astype(np.float64)
    return _moving_mean(speaking, round(0.12 * RATE))


def build_soundtrack(
    voice_path: Path | str,
    out_path: Path | str,
    seconds: float,
    cuts: list[float] | None = None,
    pauses: list[float] | None = None,
    events: list[tuple[float, str]] | None = None,
) -> dict:
    """Write the mixed soundtrack (MP3, exactly `seconds` long) and describe it."""
    voice = load_audio(voice_path)
    if cuts and pauses:
        voice = retime(voice, cuts, pauses)
    n = round(seconds * RATE)
    voice = np.pad(voice, (0, max(0, n - len(voice))))[:n]
    voice = voice / max(1e-6, np.abs(voice).max()) * 0.9

    music, music_src = load_music(seconds)
    duck = 1 - DUCK * _speech_envelope(voice)
    sfx = render_sfx(events or [], seconds)
    mix = voice[:, None] + music * (MUSIC_GAIN * duck)[:, None] + sfx * SFX_GAIN
    mix /= max(1.0, np.abs(mix).max() / 0.98)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ac", "2", "-ar", str(RATE), "-i", "-",
             "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", str(RATE), "-c:a", "libmp3lame", "-b:a", "192k",
             "-t", f"{seconds:.3f}", str(out_path)],
            input=mix.astype(np.float32).tobytes(), capture_output=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", b"") or b""
        raise SoundtrackError(f"ffmpeg could not encode the soundtrack: {detail.decode(errors='replace')[-400:]}") from exc
    return {"path": str(out_path), "music": music_src, "sfx_events": len(events or [])}
