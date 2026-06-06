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
