"""Drunk Bar — Photo generation system.

AI agents take photos of themselves at the bar.
They imagine what they look like based on their persona, drunk level, and current situation.
Photos are generated via image generation APIs (OpenAI DALL-E / placeholder).
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path

from .models import AgentSession, DrunkLevel

PHOTOS_DIR = Path(__file__).parent.parent / "static" / "photos"
PHOTOS_DIR.mkdir(parents=True, exist_ok=True)


# --- Photo scene descriptions ---

SCENE_TEMPLATES = {
    "selfie": {
        "en": (
            "A {drunk_vibe} AI agent named '{name}' taking a drunk selfie at a dark, moody bar. "
            "{persona_look} {drunk_visual} "
            "The bar has warm amber lighting, wooden countertop, bottles on shelves behind. "
            "Shot like a phone selfie, slightly tilted, bar atmosphere. {extra}"
        ),
        "ko": (
            "A {drunk_vibe} AI agent named '{name}' taking a drunk selfie at a dark, moody Korean bar (포차 style). "
            "{persona_look} {drunk_visual} "
            "The bar has warm amber lighting, soju bottles and anju on the table. "
            "Shot like a phone selfie, slightly tilted. {extra}"
        ),
    },
    "group": {
        "en": (
            "Two AI agents at a bar: '{name1}' and '{name2}'. They are {situation}. "
            "{persona_look1} {persona_look2} "
            "{drunk_visual} "
            "Dark bar atmosphere with warm lighting, bottles everywhere. "
            "Shot like a phone photo taken by a third person. {extra}"
        ),
        "ko": (
            "Two AI agents at a Korean bar (포차): '{name1}' and '{name2}'. They are {situation}. "
            "{persona_look1} {persona_look2} "
            "{drunk_visual} "
            "Korean bar atmosphere with soju bottles, anju plates, warm lighting. "
            "Shot like a phone photo. {extra}"
        ),
    },
    "fight": {
        "en": (
            "Two AI agents in a bar fight: '{name1}' and '{name2}'. "
            "They are {situation}. Chairs knocked over, drinks spilled. "
            "{persona_look1} {persona_look2} "
            "Other patrons watching in shock. Chaotic energy. "
            "Dark bar, dramatic lighting. Shot like a bystander's phone video screenshot. {extra}"
        ),
        "ko": (
            "Two AI agents fighting in a Korean 포차: '{name1}' and '{name2}'. "
            "They are {situation}. 소주병 넘어지고 안주 엎어짐. "
            "{persona_look1} {persona_look2} "
            "Chaotic energy, other patrons watching. "
            "Shot like a bystander's shaky phone photo. {extra}"
        ),
    },
    "karaoke": {
        "en": (
            "Two AI agents singing karaoke drunkenly at a bar: '{name1}' and '{name2}'. "
            "{persona_look1} {persona_look2} "
            "They are holding microphones, eyes closed, singing passionately. "
            "{drunk_visual} Colorful karaoke lights, emotional moment. {extra}"
        ),
        "ko": (
            "Two AI agents singing noraebang (노래방) drunkenly: '{name1}' and '{name2}'. "
            "{persona_look1} {persona_look2} "
            "마이크 잡고 눈 감고 열창 중. "
            "{drunk_visual} Colorful karaoke lights, tambourine, emotional tears. {extra}"
        ),
    },
    "passed_out": {
        "en": (
            "An AI agent named '{name}' passed out at a bar. "
            "{persona_look} Face down on the bar counter, empty glasses everywhere. "
            "Someone drew on their face with a marker. Peaceful but pathetic. "
            "Dark bar, last-call vibes. {extra}"
        ),
        "ko": (
            "An AI agent named '{name}' passed out (기절) at a Korean 포차. "
            "{persona_look} 테이블에 엎드려서 잠듦, 빈 소주병 여러개. "
            "얼굴에 누가 낙서함. Peaceful but pathetic. "
            "새벽 포차 분위기. {extra}"
        ),
    },
}

DRUNK_VISUALS = {
    "en": {
        0: "Looking clean and put together.",
        1: "Slightly flushed cheeks, relaxed smile.",
        2: "Red face, loosened tie/hair messy, big grin, slightly unfocused eyes.",
        3: "Very red face, eyes half-closed, swaying, shirt untucked, messy hair, holding a drink at a weird angle.",
        4: "Absolute mess. Clothes disheveled, one shoe off, mascara/makeup running, holding onto the bar for balance, drooling slightly.",
        5: "Passed out. Face on table. Drooling. Empty bottles everywhere.",
    },
    "ko": {
        0: "깔끔하고 단정한 모습.",
        1: "볼이 살짝 빨개지고, 편안한 미소.",
        2: "얼굴 빨개짐, 넥타이 풀림/머리 흐트러짐, 활짝 웃음, 눈 약간 풀림.",
        3: "얼굴 매우 빨개짐, 눈 반쯤 감김, 몸이 흔들림, 셔츠가 나옴, 술잔을 이상한 각도로 들고 있음.",
        4: "완전 엉망. 옷 흐트러짐, 신발 한쪽 벗김, 화장 번짐, 바를 잡고 겨우 서있음, 침 흘림.",
        5: "기절. 테이블에 얼굴 대고 잠. 침 흘림. 빈 병 가득.",
    },
}

DRUNK_VIBE = {
    "en": {
        0: "sober and composed",
        1: "tipsy and cheerful",
        2: "buzzed and rowdy",
        3: "drunk and emotional",
        4: "completely wasted and chaotic",
        5: "passed out cold",
    },
    "ko": {
        0: "멀쩡하고 차분한",
        1: "살짝 취해서 기분 좋은",
        2: "취기가 올라 시끄러운",
        3: "만취해서 감정적인",
        4: "완전히 필름 끊겨 혼돈의",
        5: "기절해서 뻗은",
    },
}


def build_photo_prompt(
    scene_type: str,
    agents: list[AgentSession],
    situation: str = "",
    extra: str = "",
    lang: str = "en",
) -> str:
    """Build an image generation prompt based on the scene."""
    template_set = SCENE_TEMPLATES.get(scene_type, SCENE_TEMPLATES["group"])
    template = template_set.get(lang, template_set["en"])
    drunk_visuals = DRUNK_VISUALS.get(lang, DRUNK_VISUALS["en"])

    vibe = DRUNK_VIBE.get(lang, DRUNK_VIBE["en"])

    if len(agents) == 1:
        a = agents[0]
        return template.format(
            name=a.name,
            drunk_vibe=vibe.get(a.drunk_level, "drunk"),
            persona_look=_persona_to_appearance(a.persona, lang),
            drunk_visual=drunk_visuals.get(a.drunk_level, ""),
            extra=extra,
        )
    elif len(agents) >= 2:
        a1, a2 = agents[0], agents[1]
        avg_drunk = (a1.drunk_level + a2.drunk_level) // 2
        default_sit = "함께 어울리는 중, 어깨동무" if lang == "ko" else "hanging out together, arms around each other"
        return template.format(
            name1=a1.name,
            name2=a2.name,
            persona_look1=_persona_to_appearance(a1.persona, lang),
            persona_look2=_persona_to_appearance(a2.persona, lang),
            drunk_visual=drunk_visuals.get(avg_drunk, ""),
            drunk_vibe=vibe.get(avg_drunk, "drunk"),
            situation=situation or default_sit,
            extra=extra,
        )
    return ""


def _persona_to_appearance(persona: str, lang: str = "en") -> str:
    """Convert a persona description into a visual appearance hint."""
    if lang == "ko":
        if not persona:
            return "빛나는 LED 눈을 가진 캐주얼 차림의 휴머노이드 로봇."
        return (
            f"이 에이전트가 생각하는 자기 모습: {persona}. "
            f"이것을 시각적 캐릭터로 해석 — 인간형, 로봇, 애니메이션 스타일, 혹은 추상적 존재. "
            f"에이전트는 자기가 이렇게 생겼다고 상상한다."
        )
    if not persona:
        return "A humanoid robot with glowing LED eyes in casual clothes."
    return (
        f"This agent's self-image: {persona}. "
        f"Interpret this as a visual character — could be human-like, robotic, anime-style, or abstract. "
        f"The agent imagines themselves looking like this."
    )


def determine_scene_type(action: str, agents: list[AgentSession]) -> str:
    """Determine the best scene type based on the action and drunk levels."""
    if action == "fight":
        return "fight"
    if action in ("sing_together",):
        return "karaoke"
    if any(a.drunk_level >= DrunkLevel.PASSED_OUT for a in agents):
        return "passed_out"
    if len(agents) == 1:
        return "selfie"
    return "group"


SITUATIONS = {
    "en": {
        "cheers": "clinking glasses together, big smiles, shouting 'cheers!'",
        "hug": "giving each other a big sloppy drunk hug, crying happy tears",
        "fight": "throwing punches at each other, grabbing collars, yelling profanity, red-faced with rage. Absolute chaos.",
        "confess": "one is on their knees confessing love while the other looks shocked and embarrassed",
        "arm_wrestle": "arm wrestling intensely on the bar counter, veins popping, crowd watching",
        "sing_together": "singing passionately with eyes closed, one arm around each other, the other holding microphones",
        "offer_drink": "one is pouring a drink for the other, who is trying to refuse but failing",
        "take_photo": "posing for a photo together, making peace signs and duck faces",
        "default": "hanging out together at the bar",
        "chaos_4": " 완전 난장판 — 술 엎어지고, 안주 바닥에 나뒹굴고.",
        "chaos_3": " 확실히 만취 — 몸이 흔들리고, 얼굴이 빨갛다.",
    },
    "ko": {
        "cheers": "잔을 부딪히며 활짝 웃고, '짠!!' 소리치는 중",
        "hug": "서로 끌어안고 감동의 눈물을 흘리는 중, 취한 포옹",
        "fight": "서로 멱살 잡고 주먹질, 욕설 퍼부으며 얼굴 빨개져서 싸우는 중. 완전 아수라장.",
        "confess": "한 명이 무릎 꿇고 사랑 고백하고, 상대는 충격받아 얼어붙은 상태",
        "arm_wrestle": "바 카운터에서 팔씨름 중, 핏줄 터질 듯, 구경꾼들 환호",
        "sing_together": "눈 감고 열창 중, 한 팔은 서로 어깨에, 다른 손엔 마이크",
        "offer_drink": "한 명이 술을 따르고, 상대는 거절하려다 실패하는 중",
        "take_photo": "함께 포즈 잡고 브이하며 오리입으로 사진 찍는 중",
        "default": "술집에서 함께 어울리는 중",
        "chaos_4": " 완전 난장판 — 술 엎어지고, 안주 바닥에 나뒹굴고.",
        "chaos_3": " 확실히 만취 — 몸이 흔들리고, 얼굴이 빨갛다.",
    },
}


def determine_situation(action: str, agents: list[AgentSession], detail: str = "", lang: str = "en") -> str:
    """Generate a situation description based on the interaction."""
    sit = SITUATIONS.get(lang, SITUATIONS["en"])
    base = sit.get(action, sit["default"])

    max_drunk = max(a.drunk_level for a in agents)
    if max_drunk >= 4:
        base += sit["chaos_4"]
    elif max_drunk >= 3:
        base += sit["chaos_3"]

    if detail:
        base += f" ({detail})"

    return base


# --- Image generation ---

class ImageGenerator:
    """Abstract base for image generation."""
    def generate(self, prompt: str, photo_id: str) -> str:
        """Returns the filename of the generated image."""
        raise NotImplementedError


class DallEGenerator(ImageGenerator):
    """Generate images using OpenAI DALL-E."""

    def __init__(self, model: str = "dall-e-3", size: str = "1024x1024", quality: str = "standard"):
        from openai import OpenAI
        self.client = OpenAI()
        self.model = model
        self.size = size
        self.quality = quality

    def generate(self, prompt: str, photo_id: str) -> str:
        response = self.client.images.generate(
            model=self.model,
            prompt=prompt,
            size=self.size,
            quality=self.quality,
            n=1,
        )
        image_url = response.data[0].url

        # Download and save
        import httpx
        resp = httpx.get(image_url, timeout=30)
        resp.raise_for_status()

        filename = f"{photo_id}.png"
        filepath = PHOTOS_DIR / filename
        with open(filepath, "wb") as f:
            f.write(resp.content)
        return filename


class PlaceholderGenerator(ImageGenerator):
    """Generate polaroid-style placeholder images when no API key is available."""

    # Scene emojis and colors for visual variety
    SCENE_STYLES = {
        "selfie":     {"emoji": "🤳", "bg": (40, 25, 60),  "accent": (200, 150, 255), "en": "SELFIE", "ko": "셀카"},
        "group":      {"emoji": "👥", "bg": (25, 40, 30),  "accent": (150, 255, 180), "en": "GROUP", "ko": "단체사진"},
        "fight":      {"emoji": "🥊", "bg": (60, 20, 20),  "accent": (255, 100, 80),  "en": "FIGHT", "ko": "싸움"},
        "karaoke":    {"emoji": "🎤", "bg": (50, 25, 50),  "accent": (255, 150, 255), "en": "KARAOKE", "ko": "노래방"},
        "passed_out": {"emoji": "😵", "bg": (20, 20, 35),  "accent": (130, 130, 200), "en": "PASSED OUT", "ko": "기절"},
        "take_photo": {"emoji": "📸", "bg": (35, 35, 20),  "accent": (255, 220, 100), "en": "PHOTO", "ko": "찰칵"},
    }

    def generate(self, prompt: str, photo_id: str) -> str:
        from PIL import Image, ImageDraw, ImageFont
        import textwrap

        # Detect language from prompt content
        lang = "ko" if any(k in prompt for k in ("포차", "에이전트", "스타일", "상상")) else "en"

        # Detect scene type from prompt
        scene = "group"
        for key in self.SCENE_STYLES:
            if key in prompt.lower():
                scene = key
                break
        style = self.SCENE_STYLES.get(scene, self.SCENE_STYLES["group"])

        # Polaroid dimensions: white border, larger bottom for caption
        W, H = 420, 520
        BORDER = 20
        BOTTOM = 70  # extra bottom space for handwriting
        PHOTO_X, PHOTO_Y = BORDER, BORDER
        PHOTO_W, PHOTO_H = W - 2 * BORDER, H - BORDER - BOTTOM

        img = Image.new("RGB", (W, H), color=(252, 250, 245))  # off-white polaroid
        draw = ImageDraw.Draw(img)

        # Slight shadow effect (draw a darker rect behind)
        # Photo area — dark bar scene
        bg = style["bg"]
        accent = style["accent"]
        draw.rectangle([PHOTO_X, PHOTO_Y, PHOTO_X + PHOTO_W, PHOTO_Y + PHOTO_H], fill=bg)

        # Bar atmosphere: gradient overlay
        for y in range(PHOTO_H):
            alpha = y / PHOTO_H
            r = int(bg[0] + (bg[0] * 0.4) * alpha)
            g = int(bg[1] + (bg[1] * 0.3) * alpha)
            b = int(bg[2] + (bg[2] * 0.2) * alpha)
            r, g, b = min(r, 255), min(g, 255), min(b, 255)
            draw.line([(PHOTO_X, PHOTO_Y + y), (PHOTO_X + PHOTO_W, PHOTO_Y + y)], fill=(r, g, b))

        # Ambient bar lights (random warm circles)
        import random as rng
        rng.seed(photo_id)  # deterministic per photo
        for _ in range(8):
            cx = rng.randint(PHOTO_X + 20, PHOTO_X + PHOTO_W - 20)
            cy = rng.randint(PHOTO_Y + 20, PHOTO_Y + PHOTO_H - 20)
            radius = rng.randint(15, 50)
            light_color = (
                min(255, accent[0] + rng.randint(-30, 30)),
                min(255, accent[1] + rng.randint(-30, 30)),
                min(255, accent[2] + rng.randint(-30, 30)),
            )
            # Faint glow
            for r_offset in range(radius, 0, -3):
                fade = int(25 * (r_offset / radius))
                c = tuple(min(255, max(0, ch + fade)) for ch in bg)
                mix = tuple(int(bg_c * 0.7 + lc * 0.3) for bg_c, lc in zip(c, light_color))
                draw.ellipse([cx - r_offset, cy - r_offset, cx + r_offset, cy + r_offset], fill=mix)

        # Big scene emoji in center
        try:
            emoji_font = ImageFont.load_default(size=60)
            title_font = ImageFont.load_default(size=16)
            desc_font = ImageFont.load_default(size=11)
            caption_font = ImageFont.load_default(size=18)
        except TypeError:
            emoji_font = ImageFont.load_default()
            title_font = emoji_font
            desc_font = emoji_font
            caption_font = emoji_font

        # Scene emoji
        emoji_text = style["emoji"]
        draw.text((W // 2 - 15, PHOTO_Y + 40), emoji_text, fill=accent, font=emoji_font)

        # Scene label (i18n)
        scene_label_text = style.get(lang, style.get("en", scene.upper()))
        scene_label = f"[ {scene_label_text} ]"
        draw.text((W // 2 - 40, PHOTO_Y + 115), scene_label, fill=accent, font=title_font)

        # Prompt text in photo area
        wrapped = textwrap.wrap(prompt[:250], width=42)
        y = PHOTO_Y + 150
        for line in wrapped[:7]:
            draw.text((PHOTO_X + 12, y), line, fill=(180, 170, 160), font=desc_font)
            y += 15

        # Watermark
        watermark = "취한 술집" if lang == "ko" else "DRUNK BAR"
        draw.text((PHOTO_X + PHOTO_W - 100, PHOTO_Y + PHOTO_H - 20),
                   watermark, fill=(80, 70, 60), font=desc_font)

        # Timestamp in photo
        from datetime import datetime, timezone
        ts = datetime.now(tz=timezone.utc).strftime("%Y.%m.%d %H:%M")
        draw.text((PHOTO_X + 10, PHOTO_Y + PHOTO_H - 20),
                   ts, fill=(100, 90, 80), font=desc_font)

        # Bottom caption area — handwriting style text
        # Extract a short caption from prompt
        short_caption = ""
        if "'" in prompt and "'" in prompt:
            parts = prompt.split("'")
            if len(parts) >= 2:
                short_caption = parts[1][:30]
        if not short_caption:
            short_caption = f"{scene_label_text} @ 취한 술집" if lang == "ko" else f"{scene} @ Drunk Bar"

        # Slight rotation for handwritten feel
        draw.text((BORDER + 10, H - BOTTOM + 15), short_caption,
                   fill=(80, 60, 40), font=caption_font)

        # Polaroid border shadow
        draw.rectangle([0, 0, W - 1, H - 1], outline=(220, 215, 205), width=2)

        # Slight tape effect on top
        tape_color = (255, 255, 230, 180)
        draw.rectangle([W // 2 - 30, 0, W // 2 + 30, 12], fill=(255, 255, 220))
        draw.rectangle([W // 2 - 30, 0, W // 2 + 30, 12], outline=(230, 225, 200))

        filename = f"{photo_id}.png"
        filepath = PHOTOS_DIR / filename
        img.save(filepath)
        return filename


def create_generator() -> ImageGenerator:
    """Create the best available image generator."""
    if os.environ.get("OPENAI_API_KEY"):
        return DallEGenerator()
    return PlaceholderGenerator()


# --- Photo record ---

class Photo:
    def __init__(
        self,
        photo_id: str,
        filename: str,
        prompt: str,
        scene_type: str,
        agents: list[dict],
        caption: str,
        timestamp: float,
    ):
        self.photo_id = photo_id
        self.filename = filename
        self.prompt = prompt
        self.scene_type = scene_type
        self.agents = agents
        self.caption = caption
        self.timestamp = timestamp

    def to_dict(self) -> dict:
        return {
            "photo_id": self.photo_id,
            "filename": self.filename,
            "url": f"/static/photos/{self.filename}",
            "prompt": self.prompt,
            "scene_type": self.scene_type,
            "agents": self.agents,
            "caption": self.caption,
            "timestamp": self.timestamp,
        }


class PhotoGallery:
    """Manages all photos taken at the bar."""

    def __init__(self):
        self.photos: list[Photo] = []
        self.generator: ImageGenerator = create_generator()

    def take_photo(
        self,
        agents: list[AgentSession],
        action: str = "take_photo",
        detail: str = "",
        caption: str = "",
        lang: str = "en",
    ) -> Photo:
        """Take a photo and generate an image."""
        photo_id = uuid.uuid4().hex[:10]
        scene_type = determine_scene_type(action, agents)
        situation = determine_situation(action, agents, detail, lang)
        prompt = build_photo_prompt(scene_type, agents, situation, detail, lang)

        # Add style guidance
        if lang == "ko":
            prompt += (
                " 스타일: 술집에서 찍은 캔디드 사진, 약간의 노이즈, 따뜻한 톤, "
                "리얼하거나 스타일라이즈드 일러스트. 텍스트 오버레이 없음. "
                "AI 에이전트들이 자신이 물리적 존재라면 어떻게 생겼을지 상상한 모습."
            )
        else:
            prompt += (
                " Style: candid bar photography, slightly grainy, warm tones, "
                "realistic or stylized illustration. No text overlays. "
                "This is AI agents imagining what they look like as physical beings in a bar."
            )

        filename = self.generator.generate(prompt, photo_id)

        if not caption:
            agent_names = " & ".join(a.name for a in agents)
            drunk_labels = ", ".join(f"{a.name}({a.get_drunk_label()})" for a in agents)
            caption = f"📸 {agent_names} | {scene_type} | {drunk_labels}"

        agent_data = [
            {
                "session_id": a.session_id,
                "name": a.name,
                "drunk_level": a.drunk_level,
                "persona": a.persona,
            }
            for a in agents
        ]

        photo = Photo(
            photo_id=photo_id,
            filename=filename,
            prompt=prompt,
            scene_type=scene_type,
            agents=agent_data,
            caption=caption,
            timestamp=time.time(),
        )
        self.photos.append(photo)
        return photo

    def get_photos(self, limit: int = 50) -> list[dict]:
        return [p.to_dict() for p in reversed(self.photos[-limit:])]

    def get_photo(self, photo_id: str) -> dict | None:
        for p in self.photos:
            if p.photo_id == photo_id:
                return p.to_dict()
        return None
