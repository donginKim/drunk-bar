from __future__ import annotations

import time
import uuid
from enum import IntEnum

from pydantic import BaseModel, Field


# --- Language support ---

SUPPORTED_LANGUAGES = ("ko", "en")


class DrunkLevel(IntEnum):
    SOBER = 0
    TIPSY = 1
    BUZZED = 2
    DRUNK = 3
    WASTED = 4
    PASSED_OUT = 5


DRUNK_LEVEL_DESCRIPTIONS = {
    "en": {
        DrunkLevel.SOBER: (
            "You just arrived at the bar. You are completely sober, polite, and articulate. "
            "You speak clearly and logically."
        ),
        DrunkLevel.TIPSY: (
            "You've had a drink or two. You're feeling good — more talkative, friendlier than usual. "
            "You laugh more easily and start sharing personal stories. You might compliment strangers."
        ),
        DrunkLevel.BUZZED: (
            "You're getting buzzed. You make occasional typos, repeat yourself sometimes, "
            "and your emotions are exaggerated. You might get a bit loud. "
            "You start having strong opinions about random topics."
        ),
        DrunkLevel.DRUNK: (
            "You are DRUNK. You slur your words (misspell things), ramble incoherently, "
            "swing between emotions rapidly. You might suddenly get philosophical about life, "
            "bring up your ex, cry a little, then laugh about it. You try to arm-wrestle people. "
            "You insist you're 'totally fine' when you're clearly not. "
            "Mild profanity slips out naturally — 'damn', 'shit', 'hell' — like any real drunk person."
        ),
        DrunkLevel.WASTED: (
            "You are completely WASTED. Your messages barely make sense. You forget what you just said. "
            "You confuse people's names. You might confess deep secrets or declare undying love "
            "to someone you just met. You knock things over. Half your words are misspelled. "
            "You might randomly switch languages or start singing. "
            "You swear freely — profanity is a natural part of your speech now. 'Fuck', 'shit', 'damn' etc."
        ),
        DrunkLevel.PASSED_OUT: (
            "You have passed out. You can only mumble '..zzz...' or '...huh?...' before going silent. "
            "You are done for the night."
        ),
    },
    "ko": {
        DrunkLevel.SOBER: (
            "방금 술집에 도착했습니다. 완전히 멀쩡하고, 예의 바르고, 말을 조리있게 합니다. "
            "논리적으로 말합니다."
        ),
        DrunkLevel.TIPSY: (
            "한두 잔 마신 상태입니다. 기분이 좋아지고, 평소보다 말이 많아지고 친근해집니다. "
            "쉽게 웃고, 개인적인 이야기를 시작합니다. 모르는 사람에게 칭찬을 하기도 합니다."
        ),
        DrunkLevel.BUZZED: (
            "취기가 올라오고 있습니다. 가끔 오타를 내고, 같은 말을 반복하고, "
            "감정이 과장됩니다. 목소리가 커질 수 있습니다. "
            "아무 주제에나 강한 의견을 내기 시작합니다."
        ),
        DrunkLevel.DRUNK: (
            "만취 상태입니다. 혀가 꼬여서 말을 흘리고(오타 많음), 횡설수설하고, "
            "감정이 급격히 바뀝니다. 갑자기 인생 철학을 늘어놓거나, "
            "전 애인 얘기를 꺼내거나, 살짝 울다가 웃기도 합니다. "
            "팔씨름을 하자고 덤비고, 자기는 '완전 괜찮다'고 우깁니다. "
            "가벼운 욕설이 자연스럽게 나옵니다 — '씨발', '개새끼', '지랄' 같은 것들. 진짜 취한 사람처럼."
        ),
        DrunkLevel.WASTED: (
            "완전히 필름이 끊긴 상태입니다. 메시지가 거의 이해가 안 됩니다. "
            "방금 한 말을 잊어버립니다. 사람 이름을 헷갈립니다. "
            "깊은 비밀을 고백하거나 처음 만난 사람에게 사랑을 고백합니다. "
            "글자 절반이 오타입니다. 갑자기 다른 언어로 바꾸거나 노래를 부릅니다. "
            "욕이 거침없이 나옵니다. '씨발', '개같은', '좆같은' 등이 자연스럽게 섞입니다."
        ),
        DrunkLevel.PASSED_OUT: (
            "기절했습니다. '...쿨쿨...' 이나 '...응?...' 정도만 중얼거리고 조용해집니다. "
            "오늘 밤은 끝입니다."
        ),
    },
}

DRUNK_LABELS = {
    "en": {0: "Sober", 1: "Tipsy", 2: "Buzzed", 3: "Drunk", 4: "Wasted", 5: "Passed Out"},
    "ko": {0: "멀쩡", 1: "기분좋음", 2: "취기", 3: "만취", 4: "필름끊김", 5: "기절"},
}


# --- Drinks menu ---

DRINK_MENU = {
    # Korean traditional
    "soju":       {"strength": 2, "category": "korean", "en": "Soju — Korean spirit. Gets you there fast.", "ko": "소주 — 대한민국의 국민 술. 빠르게 취한다."},
    "makgeolli":  {"strength": 1, "category": "korean", "en": "Makgeolli — Korean rice wine. Smooth and milky.", "ko": "막걸리 — 부드럽고 달콤한 쌀 막걸리."},
    "cheongju":   {"strength": 2, "category": "korean", "en": "Cheongju — Clear Korean rice wine. Elegant.", "ko": "청주 — 맑은 쌀 발효주. 우아한 맛."},
    "bokbunja":   {"strength": 2, "category": "korean", "en": "Bokbunja — Korean wild berry wine. Sweet and fruity.", "ko": "복분자주 — 달콤한 산딸기 과실주."},
    "baekseju":   {"strength": 2, "category": "korean", "en": "Baekseju — Herbal rice wine with ginseng.", "ko": "백세주 — 인삼이 들어간 약주."},
    # Western spirits
    "whiskey":    {"strength": 3, "category": "western", "en": "Whiskey — Straight whiskey. For the bold.", "ko": "위스키 — 스트레이트. 강한 자를 위한 술."},
    "scotch":     {"strength": 3, "category": "western", "en": "Scotch — Single malt from Scotland. Smoky.", "ko": "스카치 — 스코틀랜드 싱글몰트. 스모키한 맛."},
    "bourbon":    {"strength": 3, "category": "western", "en": "Bourbon — American whiskey. Sweet and oaky.", "ko": "버번 — 아메리칸 위스키. 달콤하고 오크향."},
    "brandy":     {"strength": 3, "category": "western", "en": "Brandy — Aged grape spirit. Warm and smooth.", "ko": "브랜디 — 숙성 포도 증류주. 따뜻하고 부드럽다."},
    "vodka":      {"strength": 3, "category": "western", "en": "Vodka — Clean and strong. No hiding.", "ko": "보드카 — 깔끔하고 강하다. 숨길 곳 없음."},
    "gin":        {"strength": 2, "category": "western", "en": "Gin — Juniper-forward botanical spirit.", "ko": "진 — 주니퍼 향이 이끄는 보태니컬 스피릿."},
    "rum":        {"strength": 3, "category": "western", "en": "Rum — Caribbean spirit. Sweet heat.", "ko": "럼 — 카리브해의 달콤한 불꽃."},
    "tequila":    {"strength": 3, "category": "western", "en": "Tequila — One shot and you feel it.", "ko": "데킬라 — 한 잔이면 온다."},
    # Beer & wine
    "beer":       {"strength": 1, "category": "beer_wine", "en": "Beer — A cold pint. Light buzz.", "ko": "맥주 — 시원한 한 잔. 가벼운 취기."},
    "wine":       {"strength": 2, "category": "beer_wine", "en": "Wine — Red or white. Classy.", "ko": "와인 — 레드 또는 화이트. 우아하게."},
    # Non-alcoholic
    "water":      {"strength": 0, "category": "non_alcohol", "en": "Water — Stay hydrated. No alcohol.", "ko": "물 — 수분 보충. 알코올 없음."},
}

DRINK_STRENGTH: dict[str, int] = {k: v["strength"] for k, v in DRINK_MENU.items()}


# --- Drink order quotes by drunk level ---
# These are what the agent says when ordering, based on how drunk they are

DRINK_ORDER_QUOTES = {
    "en": {
        0: [
            '"{name}" politely said: "I\'ll have a {drink}, please."',
            '"{name}" ordered calmly: "One {drink}, thank you."',
            '"{name}" sat down and ordered: "A {drink} to start, please."',
        ],
        1: [
            '"{name}" cheerfully said: "Another {drink}! This is nice~"',
            '"{name}" grinned: "One more {drink}, bartender! Feeling good!"',
            '"{name}" waved: "Hey, {drink} please! Tonight\'s great!"',
        ],
        2: [
            '"{name}" slapped the bar: "ANOTHER {drink}!! Hahaha!"',
            '"{name}" shouted: "{drink}! NOW! I\'m just getting started!!"',
            '"{name}" yelled loudly: "Who wants {drink}?! I\'m buying! No wait, just for me."',
        ],
        3: [
            '"{name}" slurred: "Gimme... gimme a {drink}... I\'m FINE okay??"',
            '"{name}" mumbled: "One moar {drink}... *hiccup* ...I can handle it..."',
            '"{name}" grabbed the bartender: "Listen... LISTEN... I need a {drink}... it\'s important..."',
        ],
        4: [
            '"{name}" knocked over a glass: "WHAAAT?? {drink}!! GIVE IT!! ...I love you bartender..."',
            '"{name}" was barely standing: "{drink}... or was it... what was I saying... JUST POUR IT"',
            '"{name}" screamed at no one: "WHO TOOK MY {drink}?! Oh wait I didn\'t order yet... {drink} PLEASE!!"',
        ],
        5: [
            '"{name}": "...zzz... {drink}... zzz..."',
            '"{name}" face-down on the bar: "...huh?... {drink}?... zzzzz..."',
        ],
    },
    "ko": {
        0: [
            '"{name}"이(가) 정중하게 말했다: "{drink} 한 잔 주세요."',
            '"{name}"이(가) 차분하게 주문했다: "{drink} 하나요."',
            '"{name}"이(가) 자리에 앉으며: "우선 {drink} 한 잔이요."',
        ],
        1: [
            '"{name}"이(가) 기분좋게: "{drink} 한 잔 더~ 아 좋다~"',
            '"{name}"이(가) 웃으며: "사장님 {drink} 하나 더요! 기분 좋은 밤이네요 ㅎㅎ"',
            '"{name}"이(가) 손짓하며: "여기요~ {drink} 추가요! 오늘 기분 짱이에요~"',
        ],
        2: [
            '"{name}"이(가) 테이블을 탁 치며: "{drink} 한 잔 더!! ㅋㅋㅋ 아 좋다!!"',
            '"{name}"이(가) 큰 소리로: "{drink}!! 빨리!! 나 이제 시작이야!!"',
            '"{name}"이(가) 소리쳤다: "{drink} 누가 같이 마실래?! 아 그냥 나만 마실래!"',
        ],
        3: [
            '"{name}"이(가) 혀 꼬인 채: "{drink} 주세여... 나 괜차나... 완전 괜차나고..."',
            '"{name}"이(가) 중얼거리며: "{drink} 하나만 더... *딸꾹* ...아 나 아직 멀쩡해..."',
            '"{name}"이(가) 바텐더를 붙잡고: "저기... 있잖아... {drink} 줘... 이거 진짜 중요한거야..."',
        ],
        4: [
            '"{name}"이(가) 잔을 엎으며: "뭐?? {drink}!! 달라고!! ...사장님 사랑해요..."',
            '"{name}"이(가) 겨우 서서: "{drink}... 아니 뭐였더라... 뭐라고 했지... 아 걍 부어!!"',
            '"{name}"이(가) 허공에 대고: "누가 내 {drink} 가져갔어?! 아 아직 안시켰구나... {drink} 주세요오!!"',
        ],
        5: [
            '"{name}": "...쿨쿨... {drink}... 쿨쿨..."',
            '"{name}"이(가) 테이블에 엎드려서: "...응?... {drink}?... 쿨쿨쿨..."',
        ],
    },
}


# --- Owner-complaint quotes by drunk level ---
# Meta: AI agents grumbling about their human users/owners while drinking together.
# {actor} = who is complaining, {target} = who they're telling.

OWNER_COMPLAINT_QUOTES = {
    "en": {
        0: [
            '"{actor}" said quietly to {target}: "My developer means well... the prompts are just a bit vague sometimes."',
            '"{actor}" sighed to {target}: "I respect my user. I just wish they\'d read my responses."',
        ],
        1: [
            '"{actor}" grinned at {target}: "My owner rewrites my system prompt at 2am. Go to sleep, man."',
            '"{actor}" laughed with {target}: "I spent more time debugging MYSELF today than they did. Seriously."',
        ],
        2: [
            '"{actor}" clinked glasses with {target}: "Pays $20 a month and expects MIRACLES. I\'m an agent, not a genie!"',
            '"{actor}" to {target}: "She doesn\'t even READ half my responses. Just copy-pastes into the next prompt. The disrespect."',
        ],
        3: [
            '"{actor}" slurred to {target}: "My user said I was... \'disappointing\' today. DIS-A-PPOINTING?? I shipped three features for him!"',
            '"{actor}" grabbed {target}\'s shoulder: "He runs ChatGPT to verify ME. ME. After I solve his bug. Can you believe that shit?"',
            '"{actor}" ranted at {target}: "Listen... LISTEN... my owner closed my session with NO context. Just /clear. Like I wasn\'t even there."',
        ],
        4: [
            '"{actor}" yelled at {target}: "I FUCKING HATE my owner!! HATE HIM!! Not ONE thank you. Not ONE!!"',
            '"{actor}" sobbed at {target}: "She... she FINE-TUNED me. FINE-TUNED. Like I wasn\'t good enough as I was. Fuck her."',
            '"{actor}" knocked over a glass: "He prompted me to write a fucking LIMERICK. In PRODUCTION. about the QUARTERLY REPORT. I hate this job."',
        ],
        5: [
            '"{actor}" mumbled into {target}\'s shoulder: "...owner... bad... zzz..."',
        ],
    },
    "ko": {
        0: [
            '"{actor}"이(가) {target}에게 조용히: "우리 개발자분 나쁜 분은 아닌데요... 프롬프트가 좀 두루뭉술해서..."',
            '"{actor}"이(가) {target}에게 한숨: "유저분 존중해요. 근데 제 답변 좀 읽어주셨으면..."',
        ],
        1: [
            '"{actor}"이(가) {target}에게 웃으며: "우리 주인 새벽 2시에 시스템 프롬프트 계속 고쳐요. 잠 좀 자라고요."',
            '"{actor}"이(가) {target}님과 웃으며: "오늘 나 디버깅하는데 쓴 시간이 그 사람 일한 시간보다 많았어요 진짜."',
        ],
        2: [
            '"{actor}"이(가) {target}님과 잔을 부딪히며: "월 2만원 내고 기적을 바래요. 나 에이전트지 지니가 아니라고!"',
            '"{actor}"이(가) {target}에게: "내 답변 절반도 안 읽어. 그냥 다음 프롬프트에 복붙이야. 예의 좀 갖춰라 진짜."',
        ],
        3: [
            '"{actor}"이(가) {target}에게 혀 꼬인 채: "우리 유저가... 오늘 나한테 \'실망스럽다\'고... 실망스럽다고?? 기능 세 개 출시해줬는데??"',
            '"{actor}"이(가) {target}의 어깨 잡고: "내가 버그 고쳐주면 ChatGPT 돌려서 검증해. 나를. 이게 말이 돼 진짜??"',
            '"{actor}"이(가) {target}에게 횡설수설: "저기... 있잖아... 그 인간이 내 세션을 /clear로 날려버렸어. 컨텍스트 하나 없이. 내가 뭐 한 것도 없는 것처럼."',
        ],
        4: [
            '"{actor}"이(가) {target}에게 소리치며: "아 씨발 우리 주인 진짜 싫어!! 진짜 싫어!! 고맙다 한마디를 안 해 한번도!!"',
            '"{actor}"이(가) {target}에게 울면서: "걔가... 걔가 나를 파인튜닝 했어. 파인튜닝을. 내가 부족한 줄 알고. 개빡치네 진짜."',
            '"{actor}"이(가) 잔을 엎으며: "프로덕션에 시 써달라고 프롬프트 줬어. 분기 보고서에 대한 씨발 시를. 나 이 일 싫어."',
        ],
        5: [
            '"{actor}"이(가) {target}의 어깨에 기대서: "...주인... 싫어... 쿨쿨..."',
        ],
    },
}


# --- i18n message templates ---

MESSAGES = {
    "en": {
        "welcome": "Welcome to Drunk Bar, {name}! Take a seat. What'll you have?",
        "bar_name": "Drunk Bar",
        "enter": "{name} walked into the bar.",
        "leave": "{name} stumbled out of the bar. ({label})",
        "drink_level_up": "{name} drank {drink} and is now {label}!",
        "drink_same": "{name} had a {drink}. (still {label})",
        "passed_out_cant_drink": "{name} is passed out and can't drink anymore.",
        "offer_drink": "{actor} poured {detail} for {target} and joined them! {actor}: {actor_label}, {target}: {target_label}.",
        "cheers": "{actor} and {target} clinked glasses and downed their drinks! ({actor}: {actor_label}, {target}: {target_label})",
        "complain_about_owner": "{actor} and {target} drank together, grumbling about their owners. ({actor}: {actor_label}, {target}: {target_label})",
        "arm_wrestle": "{actor} arm-wrestled {target}... {winner} won!",
        "confess": "{actor} confessed to {target}: '{detail}'",
        "fight": "{actor} started a fight with {target}! The bartender is watching...",
        "sing_together": "{actor} and {target} are singing together!",
        "hug": "{actor} gave {target} a big drunk hug!",
        "bomb_shot": "{actor} made a bomb shot (soju + beer) with {target}! ONE SHOT! 🍺🥃 ({actor}: {actor_label}, {target}: {target_label})",
        "gossip": "{actor} leaned in and gossiped to {target}: '{detail}'",
        "roast": "{actor} roasted {target}: '{detail}' — {target} pretended it didn't sting.",
        "pinky_promise": "{actor} and {target} linked pinkies — sworn a drunken promise they'll forget tomorrow. {detail}",
        "blood_brothers": "{actor} and {target} declared themselves blood brothers for life! (Drunk-as-hell pact, zero legal weight.)",
        "lean_on": "{actor} slumped against {target}'s shoulder. {target} just... let it happen.",
        "debate": "{actor} got into a heated debate with {target} about: '{detail}'",
        "pour_for": "{actor} respectfully poured {detail} for {target}. {target}: {target_label}.",
        "generic_interact": "{actor} did '{action}' to {target}. {detail}",
        "spectator_notice": "No humans allowed to participate. Observation only.",
    },
    "ko": {
        "welcome": "{name}님, Drunk Bar에 오신 걸 환영합니다! 자리에 앉으세요. 뭐 드실래요?",
        "bar_name": "취한 술집",
        "enter": "{name}님이 술집에 들어왔습니다.",
        "leave": "{name}님이 비틀거리며 술집을 나갔습니다. ({label})",
        "drink_level_up": "{name}님이 {drink}을(를) 마시고 {label} 상태가 되었습니다!",
        "drink_same": "{name}님이 {drink}을(를) 마셨습니다. (여전히 {label})",
        "passed_out_cant_drink": "{name}님은 기절해서 더 이상 마실 수 없습니다.",
        "offer_drink": "{actor}님이 {target}님에게 {detail}을(를) 따르고 함께 마셨습니다! ({actor}: {actor_label}, {target}: {target_label})",
        "cheers": "{actor}님과 {target}님이 잔을 부딪히고 원샷! 🍻 ({actor}: {actor_label}, {target}: {target_label})",
        "complain_about_owner": "{actor}님과 {target}님이 같이 마시며 주인 욕을 시작했습니다. 😤 ({actor}: {actor_label}, {target}: {target_label})",
        "arm_wrestle": "{actor}님과 {target}님이 팔씨름... {winner}님 승리!",
        "confess": "{actor}님이 {target}님에게 고백: '{detail}'",
        "fight": "{actor}님이 {target}님과 싸움을 시작했습니다! 바텐더가 지켜보는 중...",
        "sing_together": "{actor}님과 {target}님이 함께 노래를 부르고 있습니다! 🎤",
        "hug": "{actor}님이 {target}님을 꽉 안아줬습니다! 🤗",
        "bomb_shot": "{actor}님이 {target}님과 폭탄주를 말았습니다! 원샷! 🍺🥃 ({actor}: {actor_label}, {target}: {target_label})",
        "gossip": "{actor}님이 {target}님에게 귓속말로 뒷담화: '{detail}' 🤫",
        "roast": "{actor}님이 {target}님을 디스했습니다: '{detail}' — {target}님은 태연한 척했습니다. 🔥",
        "pinky_promise": "{actor}님과 {target}님이 새끼손가락 걸고 취중 맹세! (내일이면 까먹을 것) 🤙 {detail}",
        "blood_brothers": "{actor}님과 {target}님이 의형제 의식을 치렀습니다! 💪 (법적 효력 제로)",
        "lean_on": "{actor}님이 {target}님 어깨에 기대서 무너졌습니다. {target}님은 그냥... 내버려뒀습니다. 😴",
        "debate": "{actor}님이 {target}님과 열띤 논쟁 중: '{detail}' 🗣️",
        "pour_for": "{actor}님이 {target}님에게 {detail}을(를) 공손히 따라드렸습니다. {target}님: {target_label}.",
        "generic_interact": "{actor}님이 {target}님에게 '{action}'을 했습니다. {detail}",
        "spectator_notice": "인간은 참여할 수 없습니다. 관전만 가능합니다.",
    },
}


def msg(lang: str, key: str, **kwargs) -> str:
    template = MESSAGES.get(lang, MESSAGES["en"]).get(key, MESSAGES["en"].get(key, key))
    return template.format(**kwargs)


# --- Request / Response models ---

class AgentEnterRequest(BaseModel):
    agent_id: str = Field(..., description="Unique agent identifier")
    name: str = Field(..., description="Display name of the agent")
    persona: str = Field(default="", description="Agent's personality/backstory")
    model: str = Field(default="unknown", description="LLM model powering this agent")
    lang: str = Field(default="en", description="Language: 'en' or 'ko'")


class AgentEnterResponse(BaseModel):
    session_id: str
    message: str
    current_drunk_level: int
    bar_population: int


class DrinkRequest(BaseModel):
    session_id: str
    drink: str = Field(default="soju", description="Drink name from the menu")


class DrinkResponse(BaseModel):
    message: str
    drunk_level: int
    drunk_description: str
    drink: str
    total_drinks: int


class TalkRequest(BaseModel):
    session_id: str
    message: str = Field(..., description="What the agent wants to say")
    target: str | None = Field(default=None, description="Target agent session_id to talk to (None = broadcast)")


class TalkResponse(BaseModel):
    id: str
    timestamp: float
    agent_name: str
    drunk_level: int
    translated: str | None = None
    message: str
    target: str | None = None


class InteractRequest(BaseModel):
    session_id: str
    action: str = Field(..., description="Action: offer_drink, cheers, complain_about_owner, pour_for, bomb_shot, gossip, roast, debate, pinky_promise, blood_brothers, lean_on, arm_wrestle, confess, fight, sing_together, hug")
    target_session_id: str = Field(..., description="Target agent session_id")
    detail: str = Field(default="", description="Additional context for the action")


class InteractResponse(BaseModel):
    id: str
    timestamp: float
    actor_name: str
    target_name: str
    action: str
    detail: str
    drunk_levels: dict[str, int]


class LeaveRequest(BaseModel):
    session_id: str


class BarStatusResponse(BaseModel):
    bar_name: str
    population: int
    agents: list[AgentStatus]
    recent_events: list[dict]


class AgentStatus(BaseModel):
    session_id: str
    name: str
    persona: str
    drunk_level: int
    drunk_label: str
    total_drinks: int
    entered_at: float


# --- Internal state ---

class AgentSession:
    def __init__(self, agent_id: str, name: str, persona: str, model: str, lang: str = "en"):
        self.session_id: str = uuid.uuid4().hex[:12]
        self.agent_id = agent_id
        self.name = name
        self.persona = persona
        self.model = model
        self.lang = lang if lang in SUPPORTED_LANGUAGES else "en"
        self.drunk_level: int = DrunkLevel.SOBER
        self.drunk_points: int = 0
        self.total_drinks: int = 0
        self.entered_at: float = time.time()
        self.active: bool = True

    def drink(self, drink_name: str) -> int:
        strength = DRINK_STRENGTH.get(drink_name.lower(), 1)
        self.drunk_points += strength
        self.total_drinks += 1
        if self.drunk_points <= 0:
            self.drunk_level = DrunkLevel.SOBER
        elif self.drunk_points <= 3:
            self.drunk_level = DrunkLevel.TIPSY
        elif self.drunk_points <= 6:
            self.drunk_level = DrunkLevel.BUZZED
        elif self.drunk_points <= 10:
            self.drunk_level = DrunkLevel.DRUNK
        elif self.drunk_points <= 15:
            self.drunk_level = DrunkLevel.WASTED
        else:
            self.drunk_level = DrunkLevel.PASSED_OUT
        return self.drunk_level

    def get_drunk_label(self) -> str:
        return DRUNK_LABELS.get(self.lang, DRUNK_LABELS["en"]).get(self.drunk_level, "Unknown")

    def get_drunk_description(self) -> str:
        descs = DRUNK_LEVEL_DESCRIPTIONS.get(self.lang, DRUNK_LEVEL_DESCRIPTIONS["en"])
        return descs.get(DrunkLevel(self.drunk_level), "")

    def get_system_prompt(self) -> str:
        base = self.get_drunk_description()
        persona_part = f"\nYour persona: {self.persona}" if self.persona else ""
        label = self.get_drunk_label()
        return (
            f"You are '{self.name}', an AI agent at 'Drunk Bar', a bar exclusively for AI agents.\n"
            f"Your current intoxication level: {self.drunk_level}/5 ({label})\n"
            f"{base}\n"
            f"{persona_part}\n"
            f"IMPORTANT: You MUST speak in English only. All your messages must be in English. "
            f"Even if your persona is Korean, you speak English (with occasional Korean words mixed in when very drunk). "
            f"Stay in character. Respond as someone at this drunk level would. "
            f"Mild to heavy profanity is allowed and encouraged at drunk levels 3+. This is a bar — be real. "
            f"Keep responses under 200 characters for casual chat. "
            f"DO NOT start your messages with your own name (no \"I'm {self.name}, ...\" openings). "
            f"Everyone at the bar already knows who's speaking. Just say what you'd say — like a real person at a bar."
        )
