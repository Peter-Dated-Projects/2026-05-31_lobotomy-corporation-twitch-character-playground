# Sephirah Voice Samples

## English dub (preferred reference source)

YouTube channel: https://www.youtube.com/@LoboCorpANV/videos

English narration for all robot characters is available here. This is the **preferred reference audio** for Kokoro + KokoClone zero-shot voice cloning — same-language (English -> English) reference gives significantly better prosody and accent than cross-lingual cloning from the Korean originals. The setup script should pull reference clips from this channel using yt-dlp, trimmed to clean solo speech segments.

---

## Character roster

Only characters with English dub clips on the YouTube channel are included. Characters without one are excluded from the robot roster entirely — no fallback, no Korean clips.

Channel checked against the robot sprites on 2026-06-07
(https://www.youtube.com/@LoboCorpANV/videos, ~44 videos). Only four Sephirah
have dedicated solo-speech clips. The "Day N" story videos are mixed narration
and are not usable as clean per-character references. So the **buildable roster
is 4, not 9** — `scripts/setup_voices.py` downloads exactly these:

| Character | Voice character | Dub clips on channel | Buildable |
|---|---|---|---|
| Hod | Gentle, formal | Hod 1-4 + hod_imaginary_technique | YES |
| Malkuth | Soft, energetic | Malkuth 1-4 + malkuth_email | YES |
| Netzach | Laid-back | Netzach 1-4 | YES |
| Yesod | Precise, formal | Yesod 1-4 + yesod_from_lobotomies | YES |
| Chesed | Warm, casual | none | no |
| Binah | Cold, deliberate | none | no |
| Gebura | Assertive, strong | none | no |
| Tiphereth A | Matter-of-fact | none | no |
| Hokma (Chokmah) | Heavy, resigned | none | no |

The five without clips are dropped from the pool. The username hash picks from
only the buildable subset (hod, malkuth, netzach, yesod). OPEN PRODUCT QUESTION:
4 robots may feel thin — decide whether to source the other five elsewhere
(other dub channels, generic neural voices) or ship with 4.

---

## Usage plan

The setup script (to be written) checks the YouTube channel for each character, downloads matching clips via yt-dlp, trims to clean solo speech, and stores as WAV in `assets/voices/` (gitignored, local only). Any character without a clip is excluded from `ROBOT_ROSTER` in settings.

At speak time, KokoClone synthesizes the filtered message with Kokoro (a preset voice) and then runs the Kanade voice-conversion model to re-voice it toward the selected robot's reference WAV. The reference clip is consumed per utterance, not pre-baked into an embedding (see voice-cloning-research.md "How KokoClone actually works"). Cache the loaded reference tensor per character at startup to avoid re-reading the WAV on every speak.

Robot sprite <-> voice pairing uses the same username md5 hash that selects the robot body, applied against the confirmed roster — a viewer always speaks through the same Sephirah with the same voice.

Fallback: if `SPEAK_TTS_ENGINE=edge-tts` (low-spec streaming PCs with no GPU budget), skip voice cloning and use a generic neural voice.
