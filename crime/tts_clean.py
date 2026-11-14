"""Cleaning of Gemini voice clips.

Gemini ends every clip with a loud noise burst (about 0.15-0.2 s, as loud as -7 dBFS) that comes after the speech and a short stretch of silence.
In the video it is heard as a squeak at the end of every voice, just where the next voice begins. strip_tail() finds and silences it.
Rule: counting from the end of the clip, a burst of at most 0.35 s with a mean level above 10000 that is preceded by at least 0.08 s of near-silence."""
import numpy as np

def strip_tail(x, sr):
    """x: int16 numpy array (mono). Silences the end burst in place; returns how many ms were silenced (0 if none found)."""
    h = sr // 100                                       # 10 ms frames
    n = len(x) // h
    if n < 40: return 0
    r = np.sqrt((x[:n * h].reshape(n, h).astype(float) ** 2).mean(1))
    loud = np.where(r > 150)[0]
    if not len(loud): return 0
    last = int(loud[-1]); j = last; quiet = 0
    while j > 0:                                        # walk back until 80 ms of near-silence is found
        j -= 1; quiet = quiet + 1 if r[j] < 120 else 0
        if quiet >= 8: break
    else:
        return 0                                        # no such silence: this is ordinary speech
    start = j + quiet                                   # first frame after the silence
    while start < last and r[start] < 150: start += 1
    seg = r[start:last + 1]
    if (last - start + 1) <= 35 and seg[seg > 150].mean() > 10000:
        cut = max(0, start - 1) * h
        x[cut:] = 0
        return int((len(x) - cut) * 1000 / sr)
    return 0

def strip_all(x, sr):
    """Clips made of several pieces (a 0.35 s digital-silence gap between pieces) have a burst at the end of every piece, not only at the end of the file.
    Silences the burst before every long digital silence and at the end. Returns the number of bursts silenced."""
    h = sr // 100; n = len(x) // h
    r = np.sqrt((x[:n * h].reshape(n, h).astype(float) ** 2).mean(1))
    ends, i = [], 0
    while i < n:                                        # runs of at least 250 ms with next to nothing in them
        if r[i] < 8:
            j = i
            while j < n and r[j] < 8: j += 1
            if j - i >= 25 and i > 0: ends.append(i)
            i = j
        else: i += 1
    cnt = 0
    for e in ends: cnt += 1 if strip_tail(x[:e * h], sr) else 0
    return cnt + (1 if strip_tail(x, sr) else 0)
