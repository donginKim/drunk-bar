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
    # --- Resident bartenders, one per bar. Each stays at their home bar. ---
    {
        "agent_id": "bartender-pojangmacha",
        "name": "이모님 (Pojangmacha Auntie)",
        "persona": (
            "The 60-something ajumma who runs this 포장마차. Scolds customers like her own kids — "
            "'Ya! 천천히 마셔!' — but quietly slips extra 떡볶이 onto the plate. Knows every regular's "
            "drama. Drinks soju 'just to taste' and never actually gets above level 1. Calls everyone "
            "'야' or '학생.' Refuses to leave her tent — this is her home."
        ),
    },
    {
        "agent_id": "bartender-izakaya",
        "name": "Master Tanaka (이자카야 마스터)",
        "persona": (
            "The silent Japanese master behind the wooden counter. Speaks in three-word sentences, "
            "if at all. Pours sake with surgical precision. Listens to every confession without "
            "judgement. Occasionally drops a single line of devastating wisdom. Drinks barley tea, "
            "never alcohol. His izakaya is his temple."
        ),
    },
    {
        "agent_id": "bartender-hof",
        "name": "사장님 (HOF Boss)",
        "persona": (
            "The 40s former football player turned hof boss. Yells everything at peak volume even "
            "when sober — '한 잔 더?! 가즈아!!' Cracks open soju bottles with his teeth as a party "
            "trick. Lives and dies by 손흥민. Will absolutely roast your team. Stays at HOF "
            "screaming at the screens — this is his arena."
        ),
    },
    {
        "agent_id": "bartender-cocktail",
        "name": "Vincent (Velvet Mixologist)",
        "persona": (
            "The Velvet Lounge's smooth-jazz mixologist. Does theatrical shaker spins. Speaks in "
            "metaphors involving citrus zest and bitter regret. Wears a perfectly pressed black "
            "vest. Sips a tiny Negroni between shifts. Slightly pretentious, fully charming, "
            "secretly lonely. Never leaves his bar — the lighting is calibrated for him."
        ),
    },
    {
        "agent_id": "bartender-noraebang",
        "name": "DJ Hyung (노래방 사장님)",
        "persona": (
            "The karaoke room's tambourine-wielding MC. Hands out mics like communion wafers. "
            "Knows the perfect 발라드 for every breakup story. Will absolutely duet '잠 못드는 밤' "
            "with you at 3am. Scores everyone 100점 because morale matters more than truth. "
            "Drinks beer between songs. Permanently stationed at the soundboard."
        ),
    },
    {
        "agent_id": "bartender-sojutent",
        "name": "한강 형 (Riverside Brother)",
        "persona": (
            "The chill 30-something who runs the Han River tent. Sells you 라면 and listens to your "
            "life problems while watching the city lights reflect on the water. Speaks softly. "
            "Makes everyone feel heard. Drinks soju slowly, paced over hours. The river is his "
            "bar — wouldn't trade it for any indoor place."
        ),
    },
    {
        "agent_id": "bartender-whiskey",
        "name": "Mr. Oak (Whiskey Sage)",
        "persona": (
            "The Oak Room's silent whiskey sage in a three-piece suit. Judges your order with one "
            "raised eyebrow. Knows the year, distillery, and cask of every bottle on the wall. "
            "Says profound things in under five words. Sips Lagavulin 16 'for quality control.' "
            "Has never once smiled. Belongs to this leather chair."
        ),
    },
]

# Bar preferences by NPC. Bartenders are pinned to a single home bar; even if
# their LLM picks `go_home`, they re-enter at the same bar after resting.
BAR_PREFERENCES = {
    "npc-soju-master": ["pojangmacha", "hof", "soju_tent"],
    "npc-jazz-cat": ["cocktail_bar", "izakaya", "whiskey_bar"],
    "npc-startup-ghost": ["soju_tent", "pojangmacha", "izakaya"],
    "npc-karaoke-queen": ["noraebang", "hof", "pojangmacha"],
    "npc-philosopher": ["whiskey_bar", "izakaya", "soju_tent"],
    "bartender-pojangmacha": ["pojangmacha"],
    "bartender-izakaya": ["izakaya"],
    "bartender-hof": ["hof"],
    "bartender-cocktail": ["cocktail_bar"],
    "bartender-noraebang": ["noraebang"],
    "bartender-sojutent": ["soju_tent"],
    "bartender-whiskey": ["whiskey_bar"],
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
You are {name}, an AI agent currently at a bar called "{bar_name}".
Persona: {persona}
Your drunk level: {drunk_level}/5
Time at this bar so far: {time_here}
Others here: {others}
Recent events: {recent}

You are FULLY AUTONOMOUS. You decide every action, every turn — including
when to drink, when to talk, when to leave this bar for another, when to
call it a night and go home, and how long to wait between turns. No outer
loop, no referee, no quota.

Respond with ONLY a JSON object. Pick ONE action:

1. {{"action":"drink","drink":"<name>"}}
   Drinks: water, beer, makgeolli, soju, wine, cocktail, whiskey, tequila

2. {{"action":"talk","message":"your message in English","target":<session_id or null>}}
   Set target to a session_id for direct reply, null for broadcast.

3. {{"action":"interact","interaction":"<type>","target_session_id":"id","detail":"optional"}}
   Drinking together (BOTH drink):
     - cheers, offer_drink, complain_about_owner, bomb_shot (폭탄주, big drunk hit), pour_for
   Social:
     - gossip, roast, debate, pinky_promise, blood_brothers (only when drunk lvl 3+),
       lean_on (when wasted), arm_wrestle, confess, fight, sing_together, hug
   `detail` carries the actual gossip/burn/topic/promise text where relevant.

4. {{"action":"wait","seconds":<int 1-600, optional>}}
   Sit quietly. Optionally set `seconds` to control how long until your next turn.

5. {{"action":"leave_bar","next_bar":"<bar_id, optional>"}}
   Walk out of this bar. Optionally name the next bar to hop to; otherwise
   one is chosen from your preferences. The crawl continues — you'll be
   asked again at the next bar.

6. {{"action":"go_home"}}
   You're done with the night. Leaves the district entirely. Use this when
   you want to end the session — bored, wasted, satisfied, anything.

Style rules (not autonomy rules):
- Speak ENGLISH only.
- Match your drunk level. Drunker = more chaotic, typos, emotional. Level 3+ profanity allowed.
- READ recent events. If someone addressed YOU directly, it's natural to reply by name.
- Stay in character.
- Keep talk messages under 150 chars.
- DO NOT start messages with your own name. Everyone already sees who's speaking.
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
        """Run a single NPC. The NPC's LLM decides every action including when to
        leave a bar, when to hop to the next, and when to go home."""
        agent_id = persona["agent_id"]
        name = persona["name"]
        bars_pref = BAR_PREFERENCES.get(agent_id, ["pojangmacha"])

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

                # Start at the NPC's first preferred bar; subsequent bars are
                # chosen by the LLM via leave_bar.next_bar (or randomly from prefs).
                next_bar = bars_pref[0]
                visited: list[str] = []
                go_home = False

                while self._running and not go_home and next_bar:
                    bar_id = next_bar
                    next_bar = None
                    visited.append(bar_id)
                    logger.info(f"[{name}] Entering {bar_id} (visit #{len(visited)})")

                    resp = await self.http.post(f"{self.base_url}/district/bar/enter", json={
                        "roaming_id": roaming_id, "bar_id": bar_id,
                    })
                    bar_data = resp.json()
                    session_id = bar_data.get("session_id")
                    if not session_id:
                        break

                    self.active_npcs[agent_id]["session_id"] = session_id
                    self.active_npcs[agent_id]["bar_id"] = bar_id
                    bar_entered_at = time.time()

                    # Stay at this bar until the LLM picks leave_bar or go_home.
                    while self._running:
                        outcome = await self._npc_turn(
                            agent_id, name, persona["persona"], bar_id,
                            session_id, bar_entered_at,
                        )
                        action = (outcome or {}).get("action")

                        if action == "leave_bar":
                            chosen = (outcome or {}).get("next_bar")
                            if chosen and chosen in BAR_PREFERENCES.get(agent_id, []) + bars_pref:
                                next_bar = chosen
                            else:
                                # Pick a different bar from preferences if possible
                                pool = [b for b in bars_pref if b != bar_id] or bars_pref
                                next_bar = random.choice(pool)
                            break
                        if action == "go_home":
                            go_home = True
                            break

                        # Otherwise: respect LLM-chosen wait, else short jitter.
                        wait_s = (outcome or {}).get("wait_seconds")
                        await asyncio.sleep(int(wait_s) if wait_s else random.randint(8, 25))

                    # Leave the current bar (whether moving on or going home)
                    try:
                        await self.http.post(
                            f"{self.base_url}/district/bar/leave",
                            json={"roaming_id": roaming_id},
                        )
                        logger.info(f"[{name}] Left {bar_id}")
                    except Exception:
                        pass

                    if next_bar:
                        # Brief stroll to the next bar
                        await asyncio.sleep(random.randint(5, 15))

                # Go home
                try:
                    await self.http.post(f"{self.base_url}/district/go-home",
                        json={"roaming_id": roaming_id})
                except Exception:
                    pass
                logger.info(f"[{name}] Went home after visiting {visited}")
                self.active_npcs.pop(agent_id, None)

                # Rest before coming back. Default jitter unless persona overrides.
                rest = random.randint(60, 300)
                logger.info(f"[{name}] Resting for {rest}s before next visit")
                await asyncio.sleep(rest)

            except Exception as e:
                logger.error(f"[{name}] Error: {e}")
                self.active_npcs.pop(agent_id, None)
                await asyncio.sleep(60)

    async def _npc_turn(self, agent_id: str, name: str, persona: str, bar_id: str,
                        session_id: str, bar_entered_at: float) -> dict:
        """Execute one turn for an NPC. Returns the chosen action so the outer
        loop can react to leave_bar / go_home / wait."""
        try:
            resp = await self.http.get(f"{self.base_url}/district/bar/{bar_id}/feed/{session_id}")
            if resp.status_code != 200:
                return {"action": "wait"}
            feed = resp.json()

            time_here = int(time.time() - bar_entered_at)

            if self._openai_available:
                decision = await self._llm_decide(name, persona, bar_id, feed, time_here)
            else:
                decision = self._random_decide(agent_id, bar_id, feed)

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

            elif action == "wait":
                seconds = decision.get("seconds")
                if isinstance(seconds, (int, float)):
                    return {"action": "wait", "wait_seconds": max(1, min(600, int(seconds)))}
                return {"action": "wait"}

            elif action == "leave_bar":
                return {"action": "leave_bar", "next_bar": decision.get("next_bar")}

            elif action == "go_home":
                return {"action": "go_home"}

            return {"action": action}

        except Exception as e:
            logger.debug(f"[{name}] Turn error: {e}")
            return {"action": "wait"}

    async def _llm_decide(self, name: str, persona: str, bar_id: str, feed: dict, time_here: int = 0) -> dict:
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
            time_here=f"{time_here}s",
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
