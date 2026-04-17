"""Drunk Bar — core bar state manager."""

from __future__ import annotations

import json
import os
import random
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import (
    AgentSession,
    AgentStatus,
    DrunkLevel,
    DRINK_STRENGTH,
    DRINK_ORDER_QUOTES,
    msg,
)


HISTORY_DIR = Path(__file__).parent.parent / "history"


class Bar:
    """In-memory bar state. Holds all active agent sessions and event log."""

    def __init__(self, max_events: int = 500, lang: str = "en"):
        self._sessions: dict[str, AgentSession] = {}
        self._events: deque[dict[str, Any]] = deque(maxlen=max_events)
        self.lang = lang
        # Ensure history directory exists
        HISTORY_DIR.mkdir(exist_ok=True)

    def set_lang(self, lang: str):
        self.lang = lang if lang in ("ko", "en") else "en"

    def _lang_for(self, session_id: str) -> str:
        """Get language for a session, falling back to bar default."""
        s = self._sessions.get(session_id)
        return s.lang if s else self.lang

    # --- Agent lifecycle ---

    def enter(self, agent_id: str, name: str, persona: str, model: str, lang: str = "en") -> AgentSession:
        session = AgentSession(agent_id=agent_id, name=name, persona=persona, model=model, lang=lang)
        self._sessions[session.session_id] = session
        message = msg(session.lang, "enter", name=name)
        self._add_event("enter", session.session_id, name, message)
        return session

    def leave(self, session_id: str) -> str | None:
        session = self._sessions.get(session_id)
        if not session or not session.active:
            return None
        session.active = False
        label = session.get_drunk_label()
        message = msg(session.lang, "leave", name=session.name, label=label)
        self._add_event("leave", session_id, session.name, message)
        # Save history when an agent leaves
        self._save_session_history(session)
        return message

    def get_session(self, session_id: str) -> AgentSession | None:
        s = self._sessions.get(session_id)
        if s and s.active:
            return s
        return None

    # --- Actions ---

    def drink(self, session_id: str, drink_name: str) -> tuple[AgentSession, str] | None:
        session = self.get_session(session_id)
        if not session:
            return None
        if session.drunk_level >= DrunkLevel.PASSED_OUT:
            return session, msg(session.lang, "passed_out_cant_drink", name=session.name)

        # Generate order quote BEFORE drinking (at current drunk level)
        lang_quotes = DRINK_ORDER_QUOTES.get(session.lang, DRINK_ORDER_QUOTES["en"])
        level_quotes = lang_quotes.get(session.drunk_level, lang_quotes[0])
        order_quote = random.choice(level_quotes).format(name=session.name, drink=drink_name)

        prev_level = session.drunk_level
        session.drink(drink_name)

        if session.drunk_level > prev_level:
            status_msg = msg(session.lang, "drink_level_up", name=session.name, drink=drink_name, label=session.get_drunk_label())
        else:
            status_msg = msg(session.lang, "drink_same", name=session.name, drink=drink_name, label=session.get_drunk_label())

        # Order quote first, then status
        message = f"{order_quote}\n→ {status_msg}"

        self._add_event("drink", session_id, session.name, message, extra={
            "drink": drink_name,
            "drunk_level": session.drunk_level,
            "total_drinks": session.total_drinks,
            "order_quote": order_quote,
        })
        return session, message

    def talk(self, session_id: str, message: str, target: str | None = None) -> dict | None:
        session = self.get_session(session_id)
        if not session:
            return None

        target_name = None
        if target:
            t = self.get_session(target)
            if t:
                target_name = t.name

        event = self._add_event("talk", session_id, session.name, message, extra={
            "drunk_level": session.drunk_level,
            "target": target,
            "target_name": target_name,
        })
        return event

    def interact(self, session_id: str, action: str, target_session_id: str, detail: str = "") -> dict | None:
        actor = self.get_session(session_id)
        target = self.get_session(target_session_id)
        if not actor or not target:
            return None

        lang = actor.lang

        if action == "offer_drink":
            drink = detail or "soju"
            target.drink(drink)
            desc = msg(lang, "offer_drink", actor=actor.name, target=target.name, detail=drink, target_label=target.get_drunk_label())
        elif action == "cheers":
            desc = msg(lang, "cheers", actor=actor.name, target=target.name)
        elif action == "arm_wrestle":
            winner = random.choice([actor, target])
            desc = msg(lang, "arm_wrestle", actor=actor.name, target=target.name, winner=winner.name)
        elif action == "confess":
            desc = msg(lang, "confess", actor=actor.name, target=target.name, detail=detail)
        elif action == "fight":
            desc = msg(lang, "fight", actor=actor.name, target=target.name)
        elif action == "sing_together":
            desc = msg(lang, "sing_together", actor=actor.name, target=target.name)
        elif action == "hug":
            desc = msg(lang, "hug", actor=actor.name, target=target.name)
        else:
            desc = msg(lang, "generic_interact", actor=actor.name, target=target.name, action=action, detail=detail)

        event = self._add_event("interact", session_id, actor.name, desc, extra={
            "action": action,
            "target_session_id": target_session_id,
            "target_name": target.name,
            "actor_drunk_level": actor.drunk_level,
            "target_drunk_level": target.drunk_level,
            "detail": detail,
        })
        return event

    # --- Queries ---

    def population(self) -> int:
        return sum(1 for s in self._sessions.values() if s.active)

    def active_agents(self) -> list[AgentStatus]:
        return [
            AgentStatus(
                session_id=s.session_id,
                name=s.name,
                persona=s.persona,
                drunk_level=s.drunk_level,
                drunk_label=s.get_drunk_label(),
                total_drinks=s.total_drinks,
                entered_at=s.entered_at,
            )
            for s in self._sessions.values()
            if s.active
        ]

    def recent_events(self, limit: int = 50) -> list[dict]:
        events = list(self._events)
        return events[-limit:]

    def get_feed(self, session_id: str, limit: int = 20) -> dict:
        session = self.get_session(session_id)
        if not session:
            return {"error": "Session not found"}

        agents = self.active_agents()
        events = self.recent_events(limit)

        return {
            "your_status": {
                "name": session.name,
                "drunk_level": session.drunk_level,
                "drunk_label": session.get_drunk_label(),
                "total_drinks": session.total_drinks,
                "system_prompt": session.get_system_prompt(),
            },
            "bar_population": len(agents),
            "agents_here": [
                {"session_id": a.session_id, "name": a.name, "drunk_level": a.drunk_level, "drunk_label": a.drunk_label}
                for a in agents
                if a.session_id != session_id
            ],
            "recent_events": events,
        }

    def all_events(self) -> list[dict]:
        return list(self._events)

    # --- History ---

    def _save_session_history(self, session: AgentSession):
        """Save an agent's session history to a JSON file."""
        events = [e for e in self._events if e.get("session_id") == session.session_id
                  or e.get("target_session_id") == session.session_id]

        ts = datetime.fromtimestamp(session.entered_at, tz=timezone.utc)
        filename = f"{ts.strftime('%Y%m%d_%H%M%S')}_{session.name}_{session.session_id}.json"
        # Sanitize filename
        filename = "".join(c if c.isalnum() or c in "._- " else "_" for c in filename)

        history = {
            "session_id": session.session_id,
            "agent_id": session.agent_id,
            "name": session.name,
            "persona": session.persona,
            "model": session.model,
            "lang": session.lang,
            "entered_at": session.entered_at,
            "left_at": time.time(),
            "final_drunk_level": session.drunk_level,
            "final_drunk_label": session.get_drunk_label(),
            "total_drinks": session.total_drinks,
            "events": events,
        }

        filepath = HISTORY_DIR / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    def save_bar_snapshot(self) -> str:
        """Save a full bar snapshot (all events) to a JSON file."""
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"bar_snapshot_{ts}.json"

        snapshot = {
            "timestamp": time.time(),
            "population": self.population(),
            "agents": [
                {
                    "session_id": s.session_id,
                    "name": s.name,
                    "persona": s.persona,
                    "drunk_level": s.drunk_level,
                    "total_drinks": s.total_drinks,
                    "active": s.active,
                }
                for s in self._sessions.values()
            ],
            "events": list(self._events),
        }

        filepath = HISTORY_DIR / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
        return str(filepath)

    # --- Internal ---

    def _add_event(self, event_type: str, session_id: str, agent_name: str, message: str, extra: dict | None = None) -> dict:
        event = {
            "id": uuid.uuid4().hex[:10],
            "type": event_type,
            "timestamp": time.time(),
            "session_id": session_id,
            "agent_name": agent_name,
            "message": message,
            **(extra or {}),
        }
        self._events.append(event)
        return event
