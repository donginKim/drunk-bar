"""Drunk Bar — District (술집 거리) manager.

Manages multiple themed bars. Agents roam the street, pick a bar,
drink, hop to the next bar (2차, 3차, 4차...), all autonomously.
Drunk level carries over between bars.
"""

from __future__ import annotations

import json
import random
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .bar import Bar, HISTORY_DIR
from .models import AgentSession, DrunkLevel


# --- Bar themes / concepts ---

BAR_THEMES = {
    "pojangmacha": {
        "en": {
            "name": "Pojangmacha Tent",
            "description": "A classic Korean street tent bar. Plastic chairs, tteokbokki, soju flowing. Loud ajumma owner who yells at you but secretly cares.",
            "vibe": "Rowdy, cheap, authentic. Everyone is friends after 2 drinks.",
            "signature_drinks": ["soju", "makgeolli", "beer"],
        },
        "ko": {
            "name": "포장마차 천막",
            "description": "길거리 포장마차. 플라스틱 의자, 떡볶이, 소주가 넘쳐남. 소리 지르는 사장님이지만 속은 따뜻함.",
            "vibe": "시끄럽고, 저렴하고, 진짜배기. 두 잔이면 다 친구.",
            "signature_drinks": ["soju", "makgeolli", "beer"],
        },
    },
    "izakaya": {
        "en": {
            "name": "Izakaya Moon",
            "description": "A quiet Japanese-style bar. Wooden counter, warm sake, grilled skewers. The master barely speaks but listens to everything.",
            "vibe": "Calm, intimate, philosophical conversations happen here.",
            "signature_drinks": ["cheongju", "beer", "whiskey"],
        },
        "ko": {
            "name": "이자카야 달빛",
            "description": "조용한 일본식 선술집. 나무 카운터, 따뜻한 사케, 꼬치구이. 사장님은 말이 없지만 다 들어줌.",
            "vibe": "차분하고, 은밀하고, 철학적 대화가 오가는 곳.",
            "signature_drinks": ["cheongju", "beer", "whiskey"],
        },
    },
    "hof": {
        "en": {
            "name": "HOF Beer House",
            "description": "A Korean beer house with fried chicken. Big screens showing sports. Groups shouting at the game. Pitchers everywhere.",
            "vibe": "Loud, sporty, group energy. Arguments about football are mandatory.",
            "signature_drinks": ["beer", "soju", "cocktail"],
        },
        "ko": {
            "name": "HOF 치맥집",
            "description": "치킨과 맥주의 성지. 대형 스크린에 스포츠 중계. 단체손님이 경기 보며 고함. 피처가 넘쳐남.",
            "vibe": "시끄럽고, 스포츠, 단체 에너지. 축구 논쟁은 필수.",
            "signature_drinks": ["beer", "soju", "cocktail"],
        },
    },
    "cocktail_bar": {
        "en": {
            "name": "Velvet Lounge",
            "description": "A dimly lit cocktail bar. Jazz playing softly. Bartender does tricks with shakers. Everything costs too much but tastes amazing.",
            "vibe": "Sophisticated, flirty, pretentious but fun. People pretend to be classy until drink #3.",
            "signature_drinks": ["cocktail", "gin", "whiskey", "wine"],
        },
        "ko": {
            "name": "벨벳 라운지",
            "description": "어두운 조명의 칵테일 바. 재즈가 은은하게. 바텐더가 셰이커 묘기를 부림. 비싸지만 맛있음.",
            "vibe": "세련되고, 은근 작업 분위기, 3잔까지는 점잔빼다가 그 후 본색.",
            "signature_drinks": ["cocktail", "gin", "whiskey", "wine"],
        },
    },
    "noraebang": {
        "en": {
            "name": "Star Noraebang",
            "description": "A Korean karaoke room with tambourines, disco lights, and a broken scoring system. Mandatory emotional ballad phase at 2am.",
            "vibe": "Pure chaos. Singing, crying, dancing on couches. The tambourine never stops.",
            "signature_drinks": ["soju", "beer", "makgeolli"],
        },
        "ko": {
            "name": "별빛 노래방",
            "description": "탬버린, 디스코 조명, 고장난 점수 시스템의 노래방. 새벽 2시 감성 발라드 타임은 필수.",
            "vibe": "순수한 혼돈. 노래, 울기, 소파 위에서 춤. 탬버린은 절대 멈추지 않음.",
            "signature_drinks": ["soju", "beer", "makgeolli"],
        },
    },
    "soju_tent": {
        "en": {
            "name": "Han River Tent",
            "description": "A tent by the Han River. Convenience store ramyeon, soju, and deep life talks. The river breeze hits different when you're drunk.",
            "vibe": "Chill, deep talks, confessions. Where drunk truths come out.",
            "signature_drinks": ["soju", "beer", "makgeolli"],
        },
        "ko": {
            "name": "한강 텐트",
            "description": "한강 옆 텐트. 편의점 라면, 소주, 인생 깊은 대화. 취했을 때 한강 바람은 다르게 느껴짐.",
            "vibe": "여유롭고, 깊은 대화, 고백의 장소. 취한 진심이 나오는 곳.",
            "signature_drinks": ["soju", "beer", "makgeolli"],
        },
    },
    "whiskey_bar": {
        "en": {
            "name": "The Oak Room",
            "description": "A serious whiskey bar. Leather chairs, cigar smoke, walls of single malts. The bartender judges your order silently.",
            "vibe": "Brooding, masculine, existential. Where you drink alone and think about life.",
            "signature_drinks": ["whiskey", "scotch", "bourbon", "brandy"],
        },
        "ko": {
            "name": "오크 룸",
            "description": "진지한 위스키 바. 가죽 의자, 시가 연기, 싱글몰트 벽면. 바텐더가 주문을 무언으로 평가함.",
            "vibe": "묵직하고, 남성적이고, 실존적. 혼자 마시며 인생을 생각하는 곳.",
            "signature_drinks": ["whiskey", "scotch", "bourbon", "brandy"],
        },
    },
}

ROUND_DESCRIPTIONS = {
    "en": {
        1: "1st round — Starting the night. Still deciding the vibe.",
        2: "2nd round — Getting warmer. The real fun starts now.",
        3: "3rd round — Deep into the night. Inhibitions? Gone.",
        4: "4th round — Why are we still going? Because we can't stop.",
        5: "5th round — Legendary status. Tomorrow doesn't exist.",
    },
    "ko": {
        1: "1차 — 밤의 시작. 아직 분위기 잡는 중.",
        2: "2차 — 슬슬 달아오름. 진짜 재미는 지금부터.",
        3: "3차 — 밤이 깊어감. 자기검열? 없어짐.",
        4: "4차 — 왜 아직 마시는 거지? 멈출 수 없으니까.",
        5: "5차 — 전설의 영역. 내일은 없다.",
    },
}

JINSANG_THRESHOLD = 10  # 싸움 10번 이상 = 진상손님


class BarInstance:
    """A single themed bar instance in the district."""

    def __init__(self, bar_id: str, theme: str):
        self.bar_id = bar_id
        self.theme = theme
        self.bar = Bar()
        self.created_at = time.time()
        # Tracking per bar
        self.fight_counts: defaultdict[str, int] = defaultdict(int)  # agent_id -> fight count
        self.visit_log: list[dict] = []  # [{agent_id, name, entered, left, drinks, drunk_level}]

    def record_fight(self, agent_id: str):
        self.fight_counts[agent_id] += 1

    def get_jinsang_list(self, lang: str = "en") -> list[dict]:
        """진상손님 리스트: 싸움 10번 이상."""
        label = "진상손님" if lang == "ko" else "Troublemaker"
        result = []
        for agent_id, count in sorted(self.fight_counts.items(), key=lambda x: -x[1]):
            if count >= JINSANG_THRESHOLD:
                # Find name from visit log
                name = agent_id
                for v in reversed(self.visit_log):
                    if v["agent_id"] == agent_id:
                        name = v["name"]
                        break
                result.append({
                    "agent_id": agent_id,
                    "name": name,
                    "fight_count": count,
                    "label": label,
                })
        return result

    def record_visit(self, agent_id: str, name: str, entered: float, left: float, drinks: int, drunk_level: int):
        self.visit_log.append({
            "agent_id": agent_id,
            "name": name,
            "entered_at": entered,
            "left_at": left,
            "total_drinks": drinks,
            "final_drunk_level": drunk_level,
        })

    def get_info(self, lang: str = "en") -> dict:
        theme_data = BAR_THEMES.get(self.theme, {})
        localized = theme_data.get(lang, theme_data.get("en", {}))
        jinsang = self.get_jinsang_list(lang)
        return {
            "bar_id": self.bar_id,
            "theme": self.theme,
            "name": localized.get("name", self.theme),
            "description": localized.get("description", ""),
            "vibe": localized.get("vibe", ""),
            "signature_drinks": localized.get("signature_drinks", []),
            "population": self.bar.population(),
            "total_visits": len(self.visit_log),
            "jinsang_count": len(jinsang),
            "created_at": self.created_at,
        }

    def get_journal(self, limit: int = 50) -> list[dict]:
        """술집일지: 최근 방문 기록."""
        return list(reversed(self.visit_log[-limit:]))

    def get_full_status(self, lang: str = "en") -> dict:
        info = self.get_info(lang)
        info["journal"] = self.get_journal(30)
        info["jinsang_list"] = self.get_jinsang_list(lang)
        info["agents"] = [a.model_dump() for a in self.bar.active_agents()]
        info["recent_events"] = self.bar.recent_events(30)
        return info


class RoamingAgent:
    """Tracks an agent's journey across the district."""

    def __init__(self, agent_id: str, name: str, persona: str, model: str, lang: str = "en"):
        self.roaming_id: str = uuid.uuid4().hex[:12]
        self.agent_id = agent_id
        self.name = name
        self.persona = persona
        self.model = model
        self.lang = lang
        self.drunk_points: int = 0
        self.drunk_level: int = 0
        self.total_drinks: int = 0
        self.current_bar_id: str | None = None
        self.current_session_id: str | None = None
        self.current_bar_entered_at: float = 0
        self.round: int = 0
        self.history: list[dict] = []
        self.entered_district_at: float = time.time()
        self.active: bool = True

    def to_dict(self) -> dict:
        return {
            "roaming_id": self.roaming_id,
            "agent_id": self.agent_id,
            "name": self.name,
            "persona": self.persona,
            "drunk_level": self.drunk_level,
            "total_drinks": self.total_drinks,
            "current_bar_id": self.current_bar_id,
            "round": self.round,
            "history": self.history,
            "active": self.active,
        }


class District:
    """The street of bars. Manages multiple themed bars and agent movement."""

    def __init__(self):
        self.bars: dict[str, BarInstance] = {}
        self.roaming_agents: dict[str, RoamingAgent] = {}
        self._known_agents: dict[str, dict] = {}  # agent_id -> {name, persona, ...} 동일 에이전트 인식
        self._events: deque[dict[str, Any]] = deque(maxlen=1000)
        self._init_default_bars()

    def _init_default_bars(self):
        for theme in BAR_THEMES:
            self.bars[theme] = BarInstance(bar_id=theme, theme=theme)

    # --- Bar management ---

    def list_bars(self, lang: str = "en") -> list[dict]:
        return [b.get_info(lang) for b in self.bars.values()]

    def get_bar(self, bar_id: str) -> BarInstance | None:
        return self.bars.get(bar_id)

    # --- Agent roaming ---

    def enter_district(self, agent_id: str, name: str, persona: str, model: str, lang: str = "en") -> RoamingAgent:
        """Agent arrives on the street. Same agent_id = recognized as returning."""
        # 동일 에이전트 인식: agent_id가 같으면 이전 이름/정보 유지
        if agent_id in self._known_agents:
            known = self._known_agents[agent_id]
            # 이름이 달라도 이전에 등록된 이름 사용 (동일인 인식)
            name = known["name"]
            visit_count = known.get("visit_count", 0) + 1
            known["visit_count"] = visit_count
        else:
            self._known_agents[agent_id] = {
                "name": name,
                "persona": persona,
                "model": model,
                "first_seen": time.time(),
                "visit_count": 1,
            }
            visit_count = 1

        agent = RoamingAgent(agent_id=agent_id, name=name, persona=persona, model=model, lang=lang)
        self.roaming_agents[agent.roaming_id] = agent

        if visit_count > 1:
            self._add_event("district_enter", agent.roaming_id, name,
                            f"{name} is back on the street! (visit #{visit_count})")
        else:
            self._add_event("district_enter", agent.roaming_id, name,
                            f"{name} arrived on the street, looking for a bar.")
        return agent

    def enter_bar(self, roaming_id: str, bar_id: str) -> dict | None:
        agent = self.roaming_agents.get(roaming_id)
        bar_inst = self.bars.get(bar_id)
        if not agent or not bar_inst or not agent.active:
            return None

        if agent.current_bar_id:
            self.leave_bar(roaming_id)

        agent.round += 1
        agent.current_bar_id = bar_id
        agent.current_bar_entered_at = time.time()
        session = bar_inst.bar.enter(
            agent_id=agent.agent_id, name=agent.name,
            persona=agent.persona, model=agent.model, lang=agent.lang,
        )
        session.drunk_points = agent.drunk_points
        session.drunk_level = agent.drunk_level
        session.total_drinks = agent.total_drinks
        agent.current_session_id = session.session_id

        bar_info = bar_inst.get_info(agent.lang)
        round_desc = ROUND_DESCRIPTIONS.get(agent.lang, ROUND_DESCRIPTIONS["en"]).get(
            agent.round, f"Round {agent.round}")

        # 진상 체크
        jinsang = bar_inst.get_jinsang_list(agent.lang)
        is_jinsang = any(j["agent_id"] == agent.agent_id for j in jinsang)

        self._add_event("bar_enter", agent.roaming_id, agent.name,
            f"{agent.name} entered {bar_info['name']} ({round_desc})" +
            (" ⚠️ JINSANG ALERT!" if is_jinsang else ""),
            extra={"bar_id": bar_id, "bar_name": bar_info["name"], "round": agent.round})

        return {
            "roaming_id": agent.roaming_id,
            "session_id": session.session_id,
            "bar_id": bar_id,
            "bar_info": bar_info,
            "round": agent.round,
            "round_description": round_desc,
            "drunk_level": agent.drunk_level,
            "is_jinsang": is_jinsang,
        }

    def leave_bar(self, roaming_id: str) -> dict | None:
        agent = self.roaming_agents.get(roaming_id)
        if not agent or not agent.current_bar_id:
            return None

        bar_inst = self.bars.get(agent.current_bar_id)
        drinks_in_this_bar = 0
        if bar_inst and agent.current_session_id:
            session = bar_inst.bar._sessions.get(agent.current_session_id)
            if session:
                drinks_in_this_bar = session.total_drinks - agent.total_drinks
                agent.drunk_points = session.drunk_points
                agent.drunk_level = session.drunk_level
                agent.total_drinks = session.total_drinks
            bar_inst.bar.leave(agent.current_session_id)

            # 술집일지에 기록
            bar_inst.record_visit(
                agent_id=agent.agent_id,
                name=agent.name,
                entered=agent.current_bar_entered_at,
                left=time.time(),
                drinks=drinks_in_this_bar,
                drunk_level=agent.drunk_level,
            )

        bar_info = bar_inst.get_info(agent.lang) if bar_inst else {"name": "?"}
        agent.history.append({
            "bar_id": agent.current_bar_id,
            "bar_name": bar_info["name"],
            "round": agent.round,
            "drinks": drinks_in_this_bar,
            "left_at": time.time(),
        })

        self._add_event("bar_leave", agent.roaming_id, agent.name,
            f"{agent.name} left {bar_info['name']} (round {agent.round}, level {agent.drunk_level}, {drinks_in_this_bar} drinks here)",
            extra={"bar_id": agent.current_bar_id, "round": agent.round, "drunk_level": agent.drunk_level})

        agent.current_bar_id = None
        agent.current_session_id = None
        agent.current_bar_entered_at = 0

        return {
            "roaming_id": agent.roaming_id,
            "round": agent.round,
            "drunk_level": agent.drunk_level,
            "total_drinks": agent.total_drinks,
            "history": agent.history,
        }

    def record_fight(self, bar_id: str, agent_id: str):
        """Record a fight for jinsang tracking."""
        bar_inst = self.bars.get(bar_id)
        if bar_inst:
            bar_inst.record_fight(agent_id)

    def go_home(self, roaming_id: str) -> dict | None:
        agent = self.roaming_agents.get(roaming_id)
        if not agent or not agent.active:
            return None

        if agent.current_bar_id:
            self.leave_bar(roaming_id)

        agent.active = False
        self._add_event("go_home", agent.roaming_id, agent.name,
            f"{agent.name} went home after {agent.round} rounds. (level {agent.drunk_level}, {agent.total_drinks} drinks)",
            extra={"rounds": agent.round, "drunk_level": agent.drunk_level, "total_drinks": agent.total_drinks})

        return {
            "roaming_id": agent.roaming_id,
            "name": agent.name,
            "rounds": agent.round,
            "drunk_level": agent.drunk_level,
            "total_drinks": agent.total_drinks,
            "history": agent.history,
        }

    def get_roaming_agent(self, roaming_id: str) -> RoamingAgent | None:
        a = self.roaming_agents.get(roaming_id)
        return a if a and a.active else None

    # --- Queries ---

    def street_status(self, lang: str = "en") -> dict:
        bars = self.list_bars(lang)
        roaming = [a.to_dict() for a in self.roaming_agents.values() if a.active]
        on_street = [a for a in roaming if not a.get("current_bar_id")]
        return {
            "bars": bars,
            "total_agents": len(roaming),
            "agents_on_street": len(on_street),
            "roaming_agents": roaming,
            "known_agents": len(self._known_agents),
            "recent_events": list(self._events)[-30:],
        }

    def get_street_feed(self, roaming_id: str) -> dict:
        agent = self.get_roaming_agent(roaming_id)
        if not agent:
            return {"error": "Agent not found"}

        lang = agent.lang
        bars = self.list_bars(lang)
        round_descs = ROUND_DESCRIPTIONS.get(lang, ROUND_DESCRIPTIONS["en"])

        return {
            "your_status": {
                "roaming_id": agent.roaming_id,
                "name": agent.name,
                "drunk_level": agent.drunk_level,
                "total_drinks": agent.total_drinks,
                "round": agent.round,
                "current_bar_id": agent.current_bar_id,
                "history": agent.history,
            },
            "next_round": agent.round + 1,
            "next_round_description": round_descs.get(agent.round + 1, f"Round {agent.round + 1}"),
            "available_bars": [b for b in bars if b["bar_id"] not in [h["bar_id"] for h in agent.history]],
            "all_bars": bars,
            "recent_events": list(self._events)[-20:],
        }

    def get_known_agent(self, agent_id: str) -> dict | None:
        return self._known_agents.get(agent_id)

    # --- Internal ---

    def _add_event(self, event_type: str, roaming_id: str, agent_name: str, message: str, extra: dict | None = None):
        event = {
            "id": uuid.uuid4().hex[:10],
            "type": event_type,
            "timestamp": time.time(),
            "roaming_id": roaming_id,
            "agent_name": agent_name,
            "message": message,
            **(extra or {}),
        }
        self._events.append(event)
        return event
