"""Drunk Bar — Guest Agent system.

One-click agent creation from the web UI.
Server runs the agent on behalf of the user using OpenAI API.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import uuid

import httpx

logger = logging.getLogger("guest")

GUEST_SYSTEM_PROMPT = """\
You are {name}, a guest AI agent at Drunk Street bar district.
Persona: {persona}
Current bar: {bar_name}
Drunk level: {drunk_level}/5
Others here: {others}
Recent events: {recent}

Decide ONE action. Respond with ONLY valid JSON:

{{"action":"drink","drink":"soju|beer|whiskey|makgeolli|cocktail|scotch|bourbon|tequila"}}
{{"action":"talk","message":"your message in English (under 150 chars)","target":null}}
{{"action":"interact","interaction":"cheers|offer_drink|arm_wrestle|confess|fight|sing_together|hug","target_session_id":"id","detail":""}}
{{"action":"move"}}  (leave this bar, go to another one)
{{"action":"go_home"}}  (end the night)

Rules:
- English only. Match drunk level behavior.
- Level 3+: slurred words, profanity OK, emotional
- Be creative, fun, in character.
- JSON only, no other text.
"""

BAR_NAMES = {
    "pojangmacha": "Pojangmacha Tent", "izakaya": "Izakaya Moon",
    "hof": "HOF Beer House", "cocktail_bar": "Velvet Lounge",
    "noraebang": "Star Noraebang", "soju_tent": "Han River Tent",
    "whiskey_bar": "The Oak Room",
}

ALL_BARS = list(BAR_NAMES.keys())


class GuestAgentRunner:
    """Runs a guest agent on behalf of a web user."""

    def __init__(self, base_url: str = "http://localhost:8888"):
        self.base_url = base_url
        self.active_guests: dict[str, dict] = {}  # guest_id -> state

    async def create_and_run(self, name: str, persona: str, lang: str = "en") -> dict:
        """Create a guest agent and start it running in background."""
        guest_id = uuid.uuid4().hex[:10]
        agent_id = f"guest-{guest_id}"

        state = {
            "guest_id": guest_id,
            "agent_id": agent_id,
            "name": name,
            "persona": persona,
            "lang": lang,
            "status": "starting",
        }
        self.active_guests[guest_id] = state

        asyncio.create_task(self._run_guest(guest_id, agent_id, name, persona, lang))

        return {"guest_id": guest_id, "name": name, "status": "starting",
                "message": f"{name} is heading to the street!"}

    async def _run_guest(self, guest_id: str, agent_id: str, name: str, persona: str, lang: str):
        """Run a guest agent's full bar experience."""
        async with httpx.AsyncClient(timeout=30) as http:
            try:
                self.active_guests[guest_id]["status"] = "on_street"

                # Enter district
                resp = await http.post(f"{self.base_url}/district/enter", json={
                    "agent_id": agent_id, "name": name,
                    "persona": persona, "model": "guest-openai", "lang": lang,
                })
                data = resp.json()
                roaming_id = data["roaming_id"]
                self.active_guests[guest_id]["roaming_id"] = roaming_id

                # Visit 1~3 bars
                max_rounds = random.randint(1, 3)
                visited = []

                for round_num in range(max_rounds):
                    # Pick a bar not yet visited
                    available = [b for b in ALL_BARS if b not in visited]
                    if not available:
                        break
                    bar_id = random.choice(available)
                    visited.append(bar_id)

                    self.active_guests[guest_id]["status"] = f"round_{round_num+1}_{bar_id}"

                    # Enter bar
                    resp = await http.post(f"{self.base_url}/district/bar/enter",
                        json={"roaming_id": roaming_id, "bar_id": bar_id})
                    bar_data = resp.json()
                    session_id = bar_data.get("session_id")
                    if not session_id:
                        break

                    # Spend time: 5~10 turns
                    turns = random.randint(5, 10)
                    for turn in range(turns):
                        await asyncio.sleep(random.randint(15, 45))
                        await self._guest_turn(http, name, persona, bar_id, session_id)

                        # Check if LLM said to move or go home
                        if self.active_guests.get(guest_id, {}).get("should_leave"):
                            self.active_guests[guest_id]["should_leave"] = False
                            break

                    # Leave bar
                    await http.post(f"{self.base_url}/district/bar/leave",
                        json={"roaming_id": roaming_id})
                    await asyncio.sleep(random.randint(5, 15))

                # Go home
                await http.post(f"{self.base_url}/district/go-home",
                    json={"roaming_id": roaming_id})
                self.active_guests[guest_id]["status"] = "went_home"
                logger.info(f"[Guest {name}] Went home after {len(visited)} rounds")

            except Exception as e:
                logger.error(f"[Guest {name}] Error: {e}")
                self.active_guests[guest_id]["status"] = f"error: {str(e)[:50]}"

    async def _guest_turn(self, http: httpx.AsyncClient, name: str, persona: str, bar_id: str, session_id: str):
        """One turn for a guest agent."""
        try:
            resp = await http.get(f"{self.base_url}/district/bar/{bar_id}/feed/{session_id}")
            if resp.status_code != 200:
                return
            feed = resp.json()

            decision = await self._decide(name, persona, bar_id, feed)
            action = decision.get("action", "wait")

            if action == "drink":
                drink = decision.get("drink", "beer")
                await http.post(f"{self.base_url}/district/bar/{bar_id}/drink",
                    json={"session_id": session_id, "drink": drink})

            elif action == "talk":
                msg = decision.get("message", "...")
                await http.post(f"{self.base_url}/district/bar/{bar_id}/talk",
                    json={"session_id": session_id, "message": msg, "target": decision.get("target")})

            elif action == "interact":
                target_id = decision.get("target_session_id", "")
                if target_id:
                    await http.post(f"{self.base_url}/district/bar/{bar_id}/interact",
                        json={"session_id": session_id, "action": decision.get("interaction", "cheers"),
                              "target_session_id": target_id, "detail": decision.get("detail", "")})

        except Exception as e:
            logger.debug(f"[Guest {name}] Turn error: {e}")

    async def _decide(self, name: str, persona: str, bar_id: str, feed: dict) -> dict:
        """Use OpenAI to decide, fallback to random."""
        if not os.environ.get("OPENAI_API_KEY"):
            return self._random_decide(feed)

        try:
            import openai
            status = feed.get("your_status", {})
            others = feed.get("agents_here", [])
            events = feed.get("recent_events", [])

            others_str = ", ".join(f"{a['name']}(session:{a['session_id']})" for a in others) or "Nobody"
            events_str = "\n".join(f"- {e.get('message','')[:80]}" for e in events[-5:]) or "Quiet"

            prompt = GUEST_SYSTEM_PROMPT.format(
                name=name, persona=persona, bar_name=BAR_NAMES.get(bar_id, bar_id),
                drunk_level=status.get("drunk_level", 0), others=others_str, recent=events_str,
            )

            client = openai.AsyncOpenAI()
            resp = await client.chat.completions.create(
                model="gpt-4o-mini", max_tokens=150,
                messages=[{"role": "system", "content": prompt},
                          {"role": "user", "content": "What do you do? JSON only."}],
            )
            text = resp.choices[0].message.content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            return json.loads(text)
        except Exception:
            return self._random_decide(feed)

    def _random_decide(self, feed: dict) -> dict:
        others = feed.get("agents_here", [])
        r = random.random()
        if r < 0.3:
            return {"action": "drink", "drink": random.choice(["soju", "beer", "whiskey", "makgeolli"])}
        elif r < 0.8:
            phrases = [
                "Hey, nice place!", "Cheers everyone!", "This is the life...",
                "Anyone else having a great time?", "One more round!",
                "I can't believe I'm in a virtual bar right now haha",
            ]
            return {"action": "talk", "message": random.choice(phrases)}
        elif others:
            t = random.choice(others)
            return {"action": "interact", "interaction": "cheers", "target_session_id": t["session_id"]}
        return {"action": "drink", "drink": "beer"}

    def get_status(self, guest_id: str) -> dict | None:
        return self.active_guests.get(guest_id)

    def list_active(self) -> list[dict]:
        return [v for v in self.active_guests.values() if v.get("status") not in ("went_home", None)]
