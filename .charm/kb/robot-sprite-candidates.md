# Robot Sprite Candidates

Scanned from: `/Users/petthepotat/Downloads/drive-download-20260606T214433Z-3-001/Sephirah + Ayin & Myo/`

All Robot-named files are **single static images** on a transparent background. Angela and Ayin body files are **sprite sheets** (standing body left, facial expression grid right — no face composited in, faces are separate).

---

## Tier 1 - Explicit Robot variants

These are the in-game Sephirah robot body sprites. Each is a labeled standing humanoid robot, fully self-contained on transparent background. The name of the character is displayed on the robot's chassis as a glowing LED label.

- Chesed: `/Users/petthepotat/Downloads/drive-download-20260606T214433Z-3-001/Sephirah + Ayin & Myo/Chesed/ChesedRobot-resources.assets-1402.png` -- standing dark-armored robot, blue glowing eye, "Chesed" label, holding a paper card, clean single image
- Binah: `/Users/petthepotat/Downloads/drive-download-20260606T214433Z-3-001/Sephirah + Ayin & Myo/Binah/BinahRobot-resources.assets-3006.png` -- bulky dark robot with gold hex-pattern chest, yellow glowing eye, "Binah" label, wispy tentacle-like leg extensions
- Gebura: `/Users/petthepotat/Downloads/drive-download-20260606T214433Z-3-001/Sephirah + Ayin & Myo/Gebura/GeburahRobot-resources.assets-1306.png` -- battle-scarred crimson/dark robot, red glowing eye, "Gebura" label, aggressive posture
- Hod: `/Users/petthepotat/Downloads/drive-download-20260606T214433Z-3-001/Sephirah + Ayin & Myo/Hod/HodRobot-resources.assets-3317.png` -- not visually confirmed, Robot-named, consistent with set
- Malkuth: `/Users/petthepotat/Downloads/drive-download-20260606T214433Z-3-001/Sephirah + Ayin & Myo/Malkuth/MalkuthRobot-resources.assets-4607.png` -- brown/khaki robot, yellow glowing circle eye, "MA1KUTH" LED label, holding a clipboard, single image
- Malkuth (right-facing): `/Users/petthepotat/Downloads/drive-download-20260606T214433Z-3-001/Sephirah + Ayin & Myo/Malkuth/MalkuthRobot_right-resources.assets-3260.png` -- same character, alternate pose (likely mirrored or right-facing variant)
- Netzach: `/Users/petthepotat/Downloads/drive-download-20260606T214433Z-3-001/Sephirah + Ayin & Myo/Netzach/NetzachRobot-resources.assets-3893.png` -- not visually confirmed, Robot-named, consistent with set
- Tiphereth A: `/Users/petthepotat/Downloads/drive-download-20260606T214433Z-3-001/Sephirah + Ayin & Myo/Tiphereth/TipherethRobot_a-resources.assets-4265.png` -- brown/gold robot with ribbon/bow, green glowing eye, "TIPHERETH" label, standing pose
- Tiphereth A (angry): `/Users/petthepotat/Downloads/drive-download-20260606T214433Z-3-001/Sephirah + Ayin & Myo/Tiphereth/tipherethRobot_a_Angry-resources.assets-4301.png` -- emotion variant of Tiphereth A robot (two files with same name: -1312 and -4301, likely duplicate or near-duplicate)
- Tiphereth (legacy/base): `/Users/petthepotat/Downloads/drive-download-20260606T214433Z-3-001/Sephirah + Ayin & Myo/Tiphereth/TiphererthRobot-resources.assets-1441.png` -- not visually confirmed, likely older or base Tiphereth robot
- Yesod: `/Users/petthepotat/Downloads/drive-download-20260606T214433Z-3-001/Sephirah + Ayin & Myo/Yesod/YesodRobot-resources.assets-2820.png` -- not visually confirmed, Robot-named, consistent with set
- Chokmah (Benjamin): `/Users/petthepotat/Downloads/drive-download-20260606T214433Z-3-001/Sephirah + Ayin & Myo/Benjamin/ChokmahRobot-resources.assets-3407.png` -- not visually confirmed, Robot-named, consistent with set

---

## Tier 2 - Full-body standing sprites (usable as robot body)

These characters lack a Robot variant. Their body files are sprite sheets: the standing body occupies the left portion of the image; the right portion is a grid of facial expression overlays (eyes/brows). They have no face composited in -- the body is headless/faceless, suitable for the same compositing approach as the employee sprites.

- Angela: `/Users/petthepotat/Downloads/drive-download-20260606T214433Z-3-001/Sephirah + Ayin & Myo/Angela/Angela-resources.assets-2638.png` -- sprite sheet: standing full-body (light-blue twintail hair, black/white formal coat), no face composited, facial expression grid in right half. Static single canvas.
- Ayin: `/Users/petthepotat/Downloads/drive-download-20260606T214433Z-3-001/Sephirah + Ayin & Myo/Ayin/Ayin-resources.assets-3484.png` -- sprite sheet: standing full-body (dark hair, white lab coat, formal attire), no face composited, smaller facial expression grid in right half.

Note: Carmen has no portrait-free body file identified (only `Carmen-resources.assets-4672.png` + shadow + background variants). Myo has only Rabbit-related files and partial face assets, not a standing humanoid body.

---

## Excluded

- **All `*RobotPortrait` files** (e.g. `ChesedRobotPortrait`, `BinahRobotPortrait`, etc.) -- close-up face/head portraits of the robot bodies, not full standing sprites.
- **All `*Portrait` files** -- character face portraits, no body.
- **All `*CG*` files** -- full-scene CG cutscenes, not sprites.
- **All `*Past` / `*PastPortrait` files** -- flashback/younger versions, portrait format.
- **`TipherethRobot_b-resources.assets-3720.png`** -- this is Tiphereth B's destroyed robot as horizontal wreckage debris, not a standing body; not usable as a speaking sprite.
- **`TiphererthRobotBroke` and `TiphererthRobotDie`** -- damaged/dead state variants of Tiphereth; structural damage or collapsed pose, not clean standing sprites.
- **`chesedBoss`, `tipeboss`** -- boss encounter versions with different proportions.
- **Rabbits folder** -- non-humanoid enemy/faction assets (rabbit soldiers, field effects, helmet items).
- **Myo folder** -- contains only rabbit helmet assets, bullet effects, and a team roster UI image; no humanoid body sprite.
- **`binahCG*`, `binahSpawn`, `BinahShadow`** -- scene assets, not character sprites.
- **Shadow files (`chesed_Shadow`, `m_Shadow*`, etc.)** -- drop-shadow layer assets.
- **Background files (`AngelaBackground`, `yesodBK`, `officeBK`, etc.)** -- scene backgrounds.

---

## Other Finds

### Ordeals/Fixers and Ordeals/Sweeper

**Verdict: not usable as standing body sprites.**

Both directories contain sprite-part sheets -- body parts (head, torso, limbs, weapon) laid out scattered on a transparent background, not assembled into a single standing figure. These are rigging/animation source sheets.

- Fixers bodies (4 files, all named `body-resources.assets-*.png`): humanoid characters in gold/blue or dark armored styles, but parts-exploded. No single assembled standing sprite.
- Sweeper files (`cleaner`, `10`, `2h`, `3h`): dark mechanical creature with insect/crab proportions and red glowing eyes. Non-humanoid silhouette even if assembled. Not suitable as a speaking character body.

### Speech Balloon

`/Users/petthepotat/Downloads/drive-download-20260606T214433Z-3-001/Unknown/AgentSpeechBalloon-resources.assets-892.png`

**Usable as speech bubble frame.**

Simple near-square flat-color panel: gray fill with a salmon/red-coral border (~8px). No pointer/tail, no decorations -- purely a rectangular container. Clean and minimal. Suitable as the speech bubble background when compositing viewer text over the robot body. Would need a text renderer layered on top; the frame itself contributes no pointer, so position relative to the robot head should be chosen by the game engine.

### Unsure/

Nothing relevant. All files are Korean-named screen effect animation frames:
- `화면노이즈_*` (screen noise, 13 frames)
- `환상체탈출노이즈_*` (aberration/phantom escape noise, 14 frames)
- `지구본본_*` (globe animation, 1 visible frame)

All are abstract animated overlays (noise, distortion). No humanoid sprites.

### Temp Special Effects folder

No speaking/voice-specific effects. All files are generic combat and particle FX. Two categories worth noting for future pairing:

- **Electricity/sparkle** -- `CFX_ElectricSparkle`, `CFX_T_Anim7_Electricity`: could layer over a robot body as a "signal transmitting" speaking aura.
- **Bubble** -- `CFX_T_Anim4_Bubble`, `CFX_T_Bubble`: bubble-pop animations that could animate a speech bubble appearing.

Everything else (flame, smoke, slash, teleport, shadow, waterfall, hit) is combat-purpose and not relevant to a speaking animation.
