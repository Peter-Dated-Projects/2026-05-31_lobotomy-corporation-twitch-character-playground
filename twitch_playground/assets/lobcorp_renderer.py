"""Composite real LobCorp art from layered sprite sheets into SpriteSets.

This is the conversion layer the pure-data character defs deliberately avoid:
character_defs.py says WHICH sheet and WHICH extracted variant make up each
layer; here we turn those references into actual pygame surfaces by blitting the
layer stack (see the architecture KB note) onto a transparent canvas, then slice
the result into the four animation clips the sim consumes.

Robustness is a hard requirement: the real sheets live in a local asset drop
that is NOT in the repo. If the drop is absent, or any sheet/variant fails to
load, LobCorpProvider degrades to PlaceholderProvider art for that character and
warns once -- the app and the test suite must never crash from missing assets.

Like every provider, LobCorpProvider builds surfaces with convert_alpha() (via
the sprite cache), so it must be instantiated AFTER pygame.display.set_mode().
"""

from __future__ import annotations

import pygame

from twitch_playground import settings
from twitch_playground.assets.character_defs import (
    CHARACTER_DEFS,
    DEFAULT_CHARACTER_ID,
    CharacterDef,
    CharacterLayer,
    assign_character,
)
from twitch_playground.assets.provider import PlaceholderProvider, SpriteSet
from twitch_playground.assets.sprite_extraction import SpriteSheetCache

# Static base sheets shared by every character (full on-disk names, see the
# sprite-sheet catalog). These back layers #2/#4/#6 of the stack and are NOT
# part of any CharacterDef -- the bare body is the same for everyone; only the
# clothes, hair, and face on top of it vary.
HEAD_SHEET = "Head-resources.assets-1476.png"
SKELETON_SHEET = "skeleton-resources.assets-1259.png"  # bare torso
SKELETON2_SHEET = "skeleton2-resources.assets-1077.png"  # bare limb frames

# Outfit sheets pack: index 0 = torso, 1-2 = hands, 3-10 = 8 animation limb
# frames (see the catalog). Walk advances through those 8 limb frames.
CLOTHES_LIMB_BASE = 3
CLOTHES_LIMB_FRAMES = 8


def _canvas() -> pygame.Surface:
    """A fresh fully-transparent character-sized canvas."""
    return pygame.Surface((settings.SPRITE_W, settings.SPRITE_H), pygame.SRCALPHA).convert_alpha()


def _work_canvas() -> pygame.Surface:
    """A fresh transparent 4x working canvas parts are composited onto.

    Parts are scaled and placed here (where they have room), then the finished
    composite is downscaled to a character-sized canvas as the last step.
    """
    return pygame.Surface((settings.WORK_W, settings.WORK_H), pygame.SRCALPHA).convert_alpha()


def _center() -> tuple[int, int]:
    return settings.SPRITE_W // 2, settings.SPRITE_H // 2


def _work_center() -> tuple[int, int]:
    return settings.WORK_W // 2, settings.WORK_H // 2


def _scale_part(surf: pygame.Surface, factor: float) -> pygame.Surface:
    """Scale a native part by `factor` for placement on the work canvas.

    smoothscale gives a far cleaner result than nearest-neighbour when shrinking
    the large (100-275px) native crops down to work-canvas size, and preserves
    per-pixel alpha in pygame-ce.
    """
    if factor == 1.0:
        return surf
    w = max(1, round(surf.get_width() * factor))
    h = max(1, round(surf.get_height() * factor))
    return pygame.transform.smoothscale(surf, (w, h))


def _face(layers: dict[str, CharacterLayer], emotion: str) -> CharacterLayer:
    """Pick the emotion-specific face layer, falling back to "default".

    Every face dict is guaranteed to carry a "default" key (see the def
    convention), so an unknown or missing emotion (e.g. "battle" for an eyes
    dict that only has default/closed/dead/panic) resolves cleanly.
    """
    return layers.get(emotion, layers["default"])


def compose_character(
    char_def: CharacterDef,
    emotion: str,
    anim_frame: int,
    cache: SpriteSheetCache,
) -> pygame.Surface:
    """Blit one fully-composited character frame onto a transparent canvas.

    Layers are drawn back-to-front in the order documented by the layer-stack
    note; each is centered at the canvas center plus its tunable offset from
    settings.LAYER_OFFSETS (y grows downward, so a negative dy lifts a layer).
    Limb layers advance with anim_frame; face layers are chosen by emotion;
    optional glasses/weapon layers are skipped when the def leaves them None.

    Raises whatever the sprite cache raises (missing sheet, out-of-range
    variant); the caller is responsible for the graceful-fallback policy.
    """
    canvas = _work_canvas()
    cx, cy = _work_center()

    def place(surf: pygame.Surface, offset_key: str) -> None:
        scaled = _scale_part(surf, settings.LAYER_SCALES.get(offset_key, 1.0))
        dx, dy = settings.LAYER_OFFSETS.get(offset_key, (0, 0))
        canvas.blit(scaled, scaled.get_rect(center=(cx + dx, cy + dy)))

    limb_frame = anim_frame % cache.variant_count(SKELETON2_SHEET)
    clothes_limb = CLOTHES_LIMB_BASE + (anim_frame % CLOTHES_LIMB_FRAMES)

    # 1 rear hair (behind everything)
    place(cache.get(char_def.rear_hair.file, char_def.rear_hair.variant), "rear_hair")
    # 2 bare body limbs, animated
    place(cache.get(SKELETON2_SHEET, limb_frame), "body_limbs")
    # 3 clothed limbs, animated
    place(cache.get(char_def.clothes, clothes_limb), "clothes_limbs")
    # 4 bare body torso (static)
    place(cache.get(SKELETON_SHEET, 0), "body_torso")
    # 5 clothed torso
    place(cache.get(char_def.clothes, 0), "clothes_torso")
    # 6 head circle (static base)
    place(cache.get(HEAD_SHEET, 0), "head")
    # 7 front hair
    place(cache.get(char_def.front_hair.file, char_def.front_hair.variant), "front_hair")
    # 8-10 face, keyed by emotion
    brow = _face(char_def.eyebrows, emotion)
    eyes = _face(char_def.eyes, emotion)
    mouth = _face(char_def.mouth, emotion)
    place(cache.get(brow.file, brow.variant), "eyebrows")
    place(cache.get(eyes.file, eyes.variant), "eyes")
    place(cache.get(mouth.file, mouth.variant), "mouth")
    # 11 glasses (optional overlay, sits over the eyes)
    if char_def.glasses is not None:
        place(cache.get(char_def.glasses.file, char_def.glasses.variant), "eyes")
    # 12 weapon (optional, side offset)
    if char_def.weapon is not None:
        place(cache.get(char_def.weapon.file, char_def.weapon.variant), "weapon")

    # Downscale the finished 4x composite to the canonical clip-frame size.
    # smoothscale antialiases the shrink so the dense face features survive
    # legibly at 32x40 instead of aliasing into noise.
    return pygame.transform.smoothscale(canvas, (settings.SPRITE_W, settings.SPRITE_H))


def _recenter(surf: pygame.Surface) -> pygame.Surface:
    """Blit an arbitrarily-sized surface centered onto a character canvas.

    Any overflow is clipped, so the result is always exactly (SPRITE_W,
    SPRITE_H) -- the size the rest of the engine expects from every clip frame.
    """
    canvas = _canvas()
    canvas.blit(surf, surf.get_rect(center=_center()))
    return canvas


def _bob(base: pygame.Surface, dy: int) -> pygame.Surface:
    """A copy of base shifted vertically by dy px (used for the breathing bob)."""
    canvas = _canvas()
    canvas.blit(base, (0, dy))
    return canvas


def _scaled(base: pygame.Surface, sx: float, sy: float) -> pygame.Surface:
    """Scale base by (sx, sy) and recenter back onto a character canvas.

    transform.scale preserves per-pixel alpha; recentering keeps the frame at
    the canonical (SPRITE_W, SPRITE_H) regardless of the scaled size.
    """
    w = max(1, round(settings.SPRITE_W * sx))
    h = max(1, round(settings.SPRITE_H * sy))
    return _recenter(pygame.transform.scale(base, (w, h)))


class LobCorpProvider:
    """Builds SpriteSets by compositing real LobCorp sheets, with a placeholder
    safety net.

    One SpriteSheetCache is shared across every character so each sheet is read
    and segmented only once. Results are cached per character_id. If compositing
    a character raises for any reason (asset drop missing, sheet unreadable,
    variant index out of range), that character silently falls back to
    PlaceholderProvider art and a single warning is logged for the session.
    """

    def __init__(self) -> None:
        self._cache: dict[str, SpriteSet] = {}
        self._sheets = SpriteSheetCache()
        self._fallback = PlaceholderProvider()
        self._warned = False

    def get_sprite_set(self, character_id: str) -> SpriteSet:
        if character_id not in self._cache:
            char_def = self._resolve(character_id)
            try:
                self._cache[character_id] = self._build(char_def)
            except Exception as exc:  # any load/extract failure -> degrade
                self._warn(character_id, exc)
                self._cache[character_id] = self._fallback.get_sprite_set(character_id)
        return self._cache[character_id]

    def _resolve(self, character_id: str) -> CharacterDef:
        """Map a character_id to a CharacterDef.

        A named character matches directly; any other id (a viewer username)
        is assigned a stable character via assign_character. DEFAULT is a final
        guard, though assign_character always returns a valid key.
        """
        if character_id in CHARACTER_DEFS:
            return CHARACTER_DEFS[character_id]
        assigned = assign_character(character_id)
        return CHARACTER_DEFS.get(assigned) or CHARACTER_DEFS[DEFAULT_CHARACTER_ID]

    def _build(self, char_def: CharacterDef) -> SpriteSet:
        """Composite every clip at all three emotion faces (L5).

        ``compose_character`` selects the face layers by ``emotion``, so we run
        the clip build once per face and key the results into ``emotion_frames``.
        Pre-rendering keeps the hot path a dict lookup + blit (no per-frame
        compositing) at the cost of ~3x face memory -- fine at our scale. The
        "default" variant doubles as ``SpriteSet.frames`` so the resting clips are
        still reachable without an emotion key.
        """
        emotion_frames = {
            emotion: self._build_clips(char_def, emotion)
            for emotion in ("default", "battle", "panic")
        }
        return SpriteSet(emotion_frames["default"], emotion_frames)

    def _build_clips(
        self, char_def: CharacterDef, emotion: str
    ) -> dict[str, list[pygame.Surface]]:
        """Composite the four required clips for one emotion face per the
        animation-clips table."""
        base = compose_character(char_def, emotion, 0, self._sheets)

        # idle: hold frame 0, with a 1px upward breathing bob on the off-beat.
        idle = [base, _bob(base, -1)]
        # walk: the 8 limb-animation frames (frame 0 reuses the base composite).
        walk = [base] + [
            compose_character(char_def, emotion, i, self._sheets) for i in range(1, 8)
        ]
        # jump: a stretched airborne pose (narrower + taller), held near-static.
        jump = [_scaled(base, 0.85, 1.2), _scaled(base, 0.80, 1.3)]
        # hug: widen outward then back in (approximated as a whole-sprite
        # horizontal scale; per the clips table the clothed torso swells
        # 1.0 -> 1.2 -> 1.4 -> 1.2).
        hug = [_scaled(base, sx, 1.0) for sx in (1.0, 1.2, 1.4, 1.2)]

        return {"idle": idle, "walk": walk, "jump": jump, "hug": hug}

    def _warn(self, character_id: str, exc: Exception) -> None:
        if not self._warned:
            self._warned = True
            print(
                f"[lobcorp] could not composite real sprites "
                f"(first failure on {character_id!r}: {exc!r}); "
                f"falling back to placeholder art"
            )
