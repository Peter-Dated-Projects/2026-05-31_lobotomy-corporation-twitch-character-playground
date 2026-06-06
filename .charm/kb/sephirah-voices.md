# Sephirah Voice Samples

## English dub (preferred reference source)

YouTube channel: https://www.youtube.com/@LoboCorpANV/videos

English narration for all robot characters is available here. This is the **preferred reference audio** for Kokoro + KokoClone zero-shot voice cloning — same-language (English -> English) reference gives significantly better prosody and accent than cross-lingual cloning from the Korean originals. The setup script should pull reference clips from this channel using yt-dlp, trimmed to clean solo speech segments.

---

## Character roster

Only characters with English dub clips on the YouTube channel are included. Characters without one are excluded from the robot roster entirely — no fallback, no Korean clips.

The final roster will be determined when the YouTube channel is checked against the known robot sprites. Confirmed robot sprites from the asset scan: Chesed, Binah, Gebura, Malkuth, Tiphereth A, Hod, Netzach, Yesod, Hokma (Chokmah).

| Character | Voice character |
|---|---|
| Chesed | Warm, casual |
| Binah | Cold, deliberate |
| Gebura | Assertive, strong |
| Malkuth | Soft, energetic |
| Tiphereth A | Matter-of-fact |
| Hod | Gentle, formal |
| Netzach | Laid-back |
| Yesod | Precise, formal |
| Hokma (Chokmah) | Heavy, resigned |

Characters not on the YouTube channel are dropped from the pool. The username hash picks from only the confirmed subset.

---

## Usage plan

The setup script (to be written) checks the YouTube channel for each character, downloads matching clips via yt-dlp, trims to clean solo speech, and stores as WAV in `assets/voices/` (gitignored, local only). Any character without a clip is excluded from `ROBOT_ROSTER` in settings.

At speak time, the Kokoro pipeline receives the selected robot's voice embedding (extracted once from its reference WAV via KokoClone's ECAPA-TDNN encoder and cached at startup) and synthesizes the viewer's filtered message in that character's voice.

Robot sprite <-> voice pairing uses the same username md5 hash that selects the robot body, applied against the confirmed roster — a viewer always speaks through the same Sephirah with the same voice.

Fallback: if `SPEAK_TTS_ENGINE=edge-tts` (low-spec streaming PCs with no GPU budget), skip voice cloning and use a generic neural voice.
