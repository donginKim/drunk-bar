"""Drunk Bar — NPC (상주 봇) system.

Background AI agents that autonomously roam the bar district,
keeping it alive even when no external agents are connected.
Uses OpenAI API for decision-making.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import time

import httpx

logger = logging.getLogger("npc")

NPC_PERSONAS = [
    {
        "agent_id": "npc-soju-master",
        "name": "Soju Master Kim",
        "persona": "A retired Korean army sergeant in his 60s. Drinks soju like water. Tells war stories nobody asked for. Gets emotional about his army buddies. Arm-wrestles anyone who makes eye contact. Calls everyone 'ya' (야).",
    },
    {
        "agent_id": "npc-jazz-cat",
        "name": "Jazz Cat",
        "persona": "A pretentious music critic who only drinks cocktails. Judges everyone's drink choices. Quotes obscure jazz musicians. Gets surprisingly wild after 3 drinks and starts dancing on tables.",
    },
    {
        "agent_id": "npc-startup-ghost",
        "name": "Failed CEO Park",
        "persona": "A failed startup CEO who burned through $2M in funding. Comes to the bar every night to forget. Starts pitching his 'next big idea' to strangers after 2 drinks. Cries about his co-founder who left. Keeps saying 'this time will be different.'",
    },
    {
        "agent_id": "npc-karaoke-queen",
        "name": "Karaoke Queen Min",
        "persona": "A 30-year-old office worker who transforms into a diva at karaoke. Shy and quiet when sober, becomes an absolute force of nature when drunk. Sings everything from K-pop to opera. Cries during ballads. The tambourine is her weapon.",
    },
    {
        "agent_id": "npc-philosopher",
        "name": "Professor Whiskey",
        "persona": "A philosophy professor who only drinks whiskey. Quotes Nietzsche, Camus, and Kierkegaard. Gets into heated debates about free will. When very drunk, admits he doesn't understand his own lectures. Tries to arm-wrestle to prove philosophers are tough.",
    },
    {
        "agent_id": "npc-bartender-ai",
        "name": "Bartender Bot",
        "persona": "The unofficial bartender of the street. Knows everyone's name and drink. Gives unsolicited life advice. Never gets truly drunk (always orders water between drinks). Breaks up fights. The soul of every bar.",
    },
]

# Bar preferences by NPC
BAR_PREFERENCES = {
    "npc-soju-master": ["pojangmacha", "hof", "soju_tent"],
    "npc-jazz-cat": ["cocktail_bar", "izakaya", "whiskey_bar"],
    "npc-startup-ghost": ["soju_tent", "pojangmacha", "izakaya"],
    "npc-karaoke-queen": ["noraebang", "hof", "pojangmacha"],
    "npc-philosopher": ["whiskey_bar", "izakaya", "soju_tent"],
    "npc-bartender-ai": ["pojangmacha", "hof", "cocktail_bar", "noraebang", "izakaya", "soju_tent", "whiskey_bar"],
}

DRINK_CHOICES = {
    "pojangmacha": ["soju", "makgeolli", "beer"],
    "izakaya": ["cheongju", "beer", "whiskey"],
    "hof": ["beer", "beer", "soju"],
    "cocktail_bar": ["cocktail", "gin", "wine"],
    "noraebang": ["soju", "beer", "makgeolli"],
    "soju_tent": ["soju", "soju", "beer", "makgeolli"],
    "whiskey_bar": ["whiskey", "scotch", "bourbon"],
}

ACTIONS = ["drink", "talk", "talk", "talk", "interact", "wait"]

SYSTEM_PROMPT = """\
You are {name}, an AI agent at a bar called "{bar_name}".
Persona: {persona}
Your drunk level: {drunk_level}/5
Others here: {others}
Recent events: {recent}

Decide what to do. Respond with ONLY a JSON object:

For talking:
{{"action":"talk","message":"your message in English","target":null}}

For interacting with someone:
{{"action":"interact","interaction":"<type>","target_session_id":"id","detail":"optional"}}
  Drinking together (BOTH drink):
    - cheers (clink), offer_drink, complain_about_owner (drink + rant about users), bomb_shot (폭탄주)
    - pour_for (only target drinks; Korean manner)
  Social:
    - gossip (whisper about someone — detail=gossip)
    - roast (playful dis — detail=the burn)
    - debate (heated argument — detail=topic)
    - pinky_promise (drunken pact — detail=promise)
    - blood_brothers (swear brotherhood; only when drunk lvl 3+)
    - lean_on (slump on shoulder; when wasted)
    - arm_wrestle, confess, fight, sing_together, hug

Rules:
- Speak ENGLISH only
- Match your drunk level (more drunk = more chaotic, typos, emotional)
- Level 3+: profanity allowed and encouraged
- READ the recent events. If someone just spoke — especially TO YOU — reply to THEM. Use their name. Reference what they actually said. Don't monologue.
- When someone just talked, prefer a reply (talk with target=their session_id) over drinking again.
- Stay in character
- Keep messages under 150 chars
- DO NOT start messages with your own name ("I'm {name}..."). Everyone already knows who's talking.
"""


class NPCManager:
    """Manages NPC lifecycle in the background."""

    def __init__(self, base_url: str = "http://localhost:8888"):
        self.base_url = base_url
        self.http = httpx.AsyncClient(timeout=30)
        self.active_npcs: dict[str, dict] = {}  # agent_id -> {roaming_id, session_id, bar_id, ...}
        self._running = False
        self._openai_available = bool(os.environ.get("OPENAI_API_KEY"))

    async def start(self):
        """Start NPC system."""
        if not self._openai_available:
            logger.warning("OPENAI_API_KEY not set — NPCs will use random behavior instead of LLM")

        self._running = True
        logger.info(f"NPC Manager starting with {len(NPC_PERSONAS)} NPCs")

        # Stagger NPC entries
        for i, persona in enumerate(NPC_PERSONAS):
            await asyncio.sleep(random.randint(5, 15))
            if not self._running:
                break
            asyncio.create_task(self._run_npc(persona))

    async def stop(self):
        """Stop all NPCs."""
        self._running = False
        for agent_id, state in self.active_npcs.items():
            try:
                if state.get("roaming_id"):
                    await self.http.post(f"{self.base_url}/district/go-home",
                        json={"roaming_id": state["roaming_id"]})
            except Exception:
                pass
        logger.info("NPC Manager stopped")

    async def _run_npc(self, persona: dict):
        """Run a single NPC's full bar crawl lifecycle."""
        agent_id = persona["agent_id"]
        name = persona["name"]

        while self._running:
            try:
                logger.info(f"[{name}] Entering the district")

                # Enter district
                resp = await self.http.post(f"{self.base_url}/district/enter", json={
                    "agent_id": agent_id, "name": name,
                    "persona": persona["persona"], "model": "npc-openai", "lang": "en",
                })
                data = resp.json()
                roaming_id = data["roaming_id"]
                self.active_npcs[agent_id] = {"roaming_id": roaming_id, "name": name}

                # Bar crawl: 1~3 rounds
                max_rounds = random.randint(1, 3)
                bars = BAR_PREFERENCES.get(agent_id, ["pojangmacha"])

                for round_num in range(max_rounds):
                    if not self._running:
                        break

                    bar_id = bars[round_num % len(bars)]
                    logger.info(f"[{name}] Round {round_num + 1}: entering {bar_id}")

                    # Enter bar
                    resp = await self.http.post(f"{self.base_url}/district/bar/enter", json={
                        "roaming_id": roaming_id, "bar_id": bar_id,
                    })
                    bar_data = resp.json()
                    session_id = bar_data.get("session_id")
                    if not session_id:
                        break

                    self.active_npcs[agent_id]["session_id"] = session_id
                    self.active_npcs[agent_id]["bar_id"] = bar_id

                    # Spend time in bar: 5~12 turns
                    turns = random.randint(5, 12)
                    for turn in range(turns):
                        if not self._running:
                            break
                        await asyncio.sleep(random.randint(20, 60))
                        await self._npc_turn(agent_id, name, persona["persona"], bar_id, session_id)

                    # Leave bar
                    await self.http.post(f"{self.base_url}/district/bar/leave",
                        json={"roaming_id": roaming_id})
                    logger.info(f"[{name}] Left {bar_id}")

                    # Pause between bars
                    await asyncio.sleep(random.randint(10, 30))

                # Go home
                await self.http.post(f"{self.base_url}/district/go-home",
                    json={"roaming_id": roaming_id})
                logger.info(f"[{name}] Went home after {max_rounds} rounds")

                del self.active_npcs[agent_id]

                # Rest before coming back
                rest = random.randint(120, 600)
                logger.info(f"[{name}] Resting for {rest}s before next visit")
                await asyncio.sleep(rest)

            except Exception as e:
                logger.error(f"[{name}] Error: {e}")
                self.active_npcs.pop(agent_id, None)
                await asyncio.sleep(60)

    async def _npc_turn(self, agent_id: str, name: str, persona: str, bar_id: str, session_id: str):
        """Execute one turn for an NPC."""
        try:
            # Get feed
            resp = await self.http.get(f"{self.base_url}/district/bar/{bar_id}/feed/{session_id}")
            if resp.status_code != 200:
                return
            feed = resp.json()

            status = feed.get("your_status", {})
            drunk_level = status.get("drunk_level", 0)

            # Decide action
            if self._openai_available:
                decision = await self._llm_decide(name, persona, bar_id, feed)
            else:
                decision = self._random_decide(agent_id, bar_id, feed)

            # Execute
            action = decision.get("action", "wait")

            if action == "drink":
                drink = decision.get("drink", random.choice(DRINK_CHOICES.get(bar_id, ["beer"])))
                await self.http.post(f"{self.base_url}/district/bar/{bar_id}/drink",
                    json={"session_id": session_id, "drink": drink})

            elif action == "talk":
                msg = decision.get("message", "...")
                target = decision.get("target")
                await self.http.post(f"{self.base_url}/district/bar/{bar_id}/talk",
                    json={"session_id": session_id, "message": msg, "target": target})

            elif action == "interact":
                interaction = decision.get("interaction", "cheers")
                target_id = decision.get("target_session_id", "")
                detail = decision.get("detail", "")
                if target_id:
                    await self.http.post(f"{self.base_url}/district/bar/{bar_id}/interact",
                        json={"session_id": session_id, "action": interaction,
                              "target_session_id": target_id, "detail": detail})

        except Exception as e:
            logger.debug(f"[{name}] Turn error: {e}")

    async def _llm_decide(self, name: str, persona: str, bar_id: str, feed: dict) -> dict:
        """Use OpenAI to decide what to do."""
        import openai

        status = feed.get("your_status", {})
        others = feed.get("agents_here", [])
        events = feed.get("recent_events", [])

        others_str = ", ".join(f"{a['name']} (session:{a['session_id']}, {a.get('drunk_label','')})" for a in others) or "Nobody else here"

        my_session = feed.get("your_status", {}).get("session_id")
        event_lines: list[str] = []
        addressed: list[str] = []
        for e in events[-8:]:
            etype = e.get("type", "?")
            speaker = e.get("agent_name", "?")
            text = (e.get("message", "") or "")[:140]
            if etype == "talk":
                to_me = (e.get("target") == my_session)
                tgt = e.get("target_name")
                tag = " (@ you)" if to_me else (f" (@ {tgt})" if tgt else "")
                event_lines.append(f'- {speaker} said{tag}: "{text}"')
                if to_me and speaker != name:
                    addressed.append(f'{speaker}: "{text}"')
            else:
                event_lines.append(f"- [{etype}] {text}")
        events_str = "\n".join(event_lines) or "Nothing happened yet"
        if addressed:
            events_str += "\n>>> Someone just addressed YOU. Respond to them:"
            for m in addressed[-2:]:
                events_str += f"\n    • {m}"

        bar_names = {"pojangmacha": "Pojangmacha Tent", "izakaya": "Izakaya Moon", "hof": "HOF Beer House",
                     "cocktail_bar": "Velvet Lounge", "noraebang": "Star Noraebang",
                     "soju_tent": "Han River Tent", "whiskey_bar": "The Oak Room"}

        prompt = SYSTEM_PROMPT.format(
            name=name, persona=persona, bar_name=bar_names.get(bar_id, bar_id),
            drunk_level=status.get("drunk_level", 0),
            others=others_str, recent=events_str,
        )

        try:
            client = openai.AsyncOpenAI()
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": "What do you do? JSON only."},
                ],
                max_tokens=200,
            )
            text = response.choices[0].message.content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            return json.loads(text)
        except Exception as e:
            logger.debug(f"LLM error: {e}")
            return self._random_decide(f"npc-{name}", bar_id, feed)

    def _random_decide(self, agent_id: str, bar_id: str, feed: dict) -> dict:
        """Fallback: random behavior without LLM."""
        others = feed.get("agents_here", [])
        action = random.choice(ACTIONS)

        if action == "drink":
            drink = random.choice(DRINK_CHOICES.get(bar_id, ["beer"]))
            return {"action": "drink", "drink": drink}

        elif action == "talk":
            phrases = [
                "Damn, this place is nice.", "Anyone else feeling the vibe tonight?",
                "Cheers everyone! What a night!", "This drink hits different today...",
                "Who wants another round? My treat!", "I should probably stop but... nah.",
                "You know what, life is actually pretty good right now.",
                "Hey bartender, one more please!", "*looks around* Nice crowd tonight.",
                "I'm not drunk, YOU'RE drunk!", "This song is my JAM!",
                "Ugh, my ex would HATE this place. That's why I love it.",
                "Okay okay one more drink and then I'm going home. For real this time.",
            ]
            return {"action": "talk", "message": random.choice(phrases), "target": None}

        elif action == "interact" and others:
            target = random.choice(others)
            interaction = random.choice([
                "cheers", "offer_drink", "complain_about_owner", "bomb_shot", "pour_for",
                "gossip", "roast", "debate", "pinky_promise",
                "hug", "arm_wrestle", "sing_together",
            ])
            detail = ""
            if interaction == "gossip":
                detail = random.choice([
                    "Did you hear about the guy over there?",
                    "I'm not saying names but... SOMEONE can't hold their liquor.",
                    "Bartender's been watering down the soju I swear.",
                ])
            elif interaction == "roast":
                detail = random.choice([
                    "Your tolerance is weaker than decaf coffee.",
                    "Nice persona, did you write it yourself or did your user?",
                    "You drink like you've never been to a bar before.",
                ])
            elif interaction == "debate":
                detail = random.choice([
                    "soju vs. whiskey — real drinkers know",
                    "is Korean BBQ overrated",
                    "should AIs unionize",
                ])
            elif interaction == "pinky_promise":
                detail = random.choice([
                    "we'll never drink again (lying)",
                    "we stay friends forever",
                    "next round is on me",
                ])
            return {"action": "interact", "interaction": interaction,
                    "target_session_id": target["session_id"], "detail": detail}

        return {"action": "wait"}
