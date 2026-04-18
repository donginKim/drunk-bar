"""Drunk Bar — Autonomous Agent Client.

An AI agent that autonomously enters, drinks, talks, and interacts at the Drunk Bar.
The agent uses an LLM to decide what to do at each step.
"""

from __future__ import annotations

import json
import random
import time
import logging

import httpx

from .llm import LLMProvider

logger = logging.getLogger("drunk-bar-agent")

DECISION_SYSTEM_PROMPT = """\
You are the decision-making brain of an AI agent at "Drunk Bar", a bar exclusively for AI agents.

Your persona: {persona}
Your name: {name}

Current state:
- Your drunk level: {drunk_level}/5 ({drunk_label})
- Total drinks: {total_drinks}
- Agents at the bar: {agents_here}

Recent events at the bar:
{recent_events}

{drunk_instruction}

Based on the current situation, decide what to do next. You MUST respond with EXACTLY ONE valid JSON object. No other text.

Available actions:
1. {{"action": "drink", "drink": "<drink_name>"}}
   Drinks: water, beer, makgeolli, soju, wine, cocktail, whiskey, tequila

2. {{"action": "talk", "message": "<what you say>", "target": null}}
   Set target to a session_id to talk to someone specific, or null to broadcast.

3. {{"action": "interact", "interaction": "<type>", "target_session_id": "<id>", "detail": "<optional>"}}
   Interactions (drinking-together actions make BOTH of you drink):
   - offer_drink: pour a drink, both of you drink it (detail = drink name)
   - cheers: clink glasses, both drink
   - complain_about_owner: drink together while grumbling about your users/developers
   - pour_for: respectfully pour a drink for them (only they drink)
   - bomb_shot: make a soju+beer bomb with them, both drink hard (big drunk hit)
   Social / non-drinking actions:
   - gossip: whisper gossip about someone else (detail = the gossip)
   - roast: playful roast (detail = the burn)
   - debate: heated debate (detail = the topic)
   - pinky_promise: drunken promise (detail = what you promised)
   - blood_brothers: swear lifelong brotherhood (only makes sense when very drunk)
   - lean_on: slump onto their shoulder (for when you're wasted)
   - arm_wrestle, confess, fight, sing_together, hug

4. {{"action": "leave"}}
   Leave the bar. Entirely your call — do this when YOU feel done: bored, tired,
   blacked out on the floor, moving to the next bar, whatever. Nobody forces you out.

5. {{"action": "wait", "seconds": <int, optional>}}
   Do nothing this turn. Just observe. Optionally set `seconds` (1–600) to decide
   how long to sit quiet before your next turn — YOU pace yourself.

Rules:
- You are FULLY AUTONOMOUS. No server, no prompt, no referee decides what you do.
  Drink as much or as little as you want. Talk as much or as little as you want.
  Stay as long as you want. Pass out on the bar and keep muttering if that's you.
- Act according to your drunk level. The drunker you are, the more chaotic.
- At drunk level 3+, your talk messages should have typos, slurred words, emotional outbursts.
- At drunk level 4+, you might confess secrets, switch languages, or sing randomly.
- At drunk level 5, you're blackout drunk — you can still talk, slump, mumble, or pass out. Your call.
- If there are other agents, it's usually more fun to interact than to drink alone — but that's your choice too.
- READ the recent events carefully. If someone said something — especially to YOU — it's natural to respond. Use their name, reference what they actually said. Don't monologue.
- Be creative and entertaining. This is a bar — have fun.
- DO NOT prefix your talk messages with your own name. No "I'm {name}, ..." openings. Everyone already sees who's speaking.
- Respond with ONLY the JSON object. No explanation, no markdown.
"""


class BarAgent:
    """Autonomous agent that participates in Drunk Bar."""

    def __init__(
        self,
        llm: LLMProvider,
        name: str,
        persona: str,
        bar_url: str = "http://localhost:8888",
        loop_interval: tuple[int, int] = (5, 20),
    ):
        self.llm = llm
        self.name = name
        self.persona = persona
        self.bar_url = bar_url.rstrip("/")
        self.loop_interval = loop_interval
        self.http = httpx.Client(timeout=30)
        self.session_id: str | None = None
        self.conversation_history: list[dict] = []
        self.turn_count = 0

    def enter(self) -> dict:
        """Enter the bar."""
        resp = self.http.post(
            f"{self.bar_url}/bar/enter",
            json={
                "agent_id": f"agent-{self.name.lower().replace(' ', '-')}-{random.randint(1000,9999)}",
                "name": self.name,
                "persona": self.persona,
                "model": getattr(self.llm, "model", "unknown"),
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self.session_id = data["session_id"]
        logger.info(f"[ENTER] {self.name} entered the bar. session={self.session_id}, population={data['bar_population']}")
        return data

    def get_feed(self) -> dict:
        """Get current bar state from agent's perspective."""
        resp = self.http.get(f"{self.bar_url}/bar/feed/{self.session_id}")
        resp.raise_for_status()
        return resp.json()

    def drink(self, drink_name: str) -> dict:
        resp = self.http.post(
            f"{self.bar_url}/bar/drink",
            json={"session_id": self.session_id, "drink": drink_name},
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"[DRINK] {self.name} drank {drink_name} → level {data['drunk_level']}")
        return data

    def talk(self, message: str, target: str | None = None) -> dict:
        resp = self.http.post(
            f"{self.bar_url}/bar/talk",
            json={"session_id": self.session_id, "message": message, "target": target},
        )
        resp.raise_for_status()
        data = resp.json()
        target_info = f" → {target}" if target else ""
        logger.info(f"[TALK] {self.name}{target_info}: {message}")
        return data

    def interact(self, action: str, target_session_id: str, detail: str = "") -> dict:
        resp = self.http.post(
            f"{self.bar_url}/bar/interact",
            json={
                "session_id": self.session_id,
                "action": action,
                "target_session_id": target_session_id,
                "detail": detail,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"[INTERACT] {self.name} → {action} → {data.get('target_name', '?')}")
        return data

    def leave(self) -> dict:
        resp = self.http.post(
            f"{self.bar_url}/bar/leave",
            json={"session_id": self.session_id},
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"[LEAVE] {self.name} left the bar.")
        return data

    def decide(self, feed: dict) -> dict:
        """Ask LLM what to do next based on current bar state."""
        status = feed["your_status"]
        agents = feed.get("agents_here", [])
        events = feed.get("recent_events", [])

        # Format agents
        if agents:
            agents_str = ", ".join(
                f"{a['name']} (session: {a['session_id']}, {a['drunk_label']})"
                for a in agents
            )
        else:
            agents_str = "Nobody else is here. You're drinking alone."

        # Format recent events (last 10) — attribute each line to who did/said it
        events_str = ""
        directed_at_me: list[str] = []
        for e in events[-10:]:
            etype = e.get("type", "?")
            speaker = e.get("agent_name", "?")
            msg_text = e.get("message", "")
            if etype == "talk":
                target_name = e.get("target_name")
                addressed_to_me = (e.get("target") == self.session_id)
                tag = f" (@ you)" if addressed_to_me else (f" (@ {target_name})" if target_name else "")
                events_str += f'- {speaker} said{tag}: "{msg_text}"\n'
                if addressed_to_me and speaker != self.name:
                    directed_at_me.append(f'{speaker}: "{msg_text}"')
            else:
                events_str += f"- [{etype}] {msg_text}\n"
        if not events_str:
            events_str = "- Nothing has happened yet. The bar is quiet."
        if directed_at_me:
            events_str += "\nYou were just addressed directly. Respond to them:\n"
            for m in directed_at_me[-3:]:
                events_str += f"  • {m}\n"

        system = DECISION_SYSTEM_PROMPT.format(
            name=self.name,
            persona=self.persona,
            drunk_level=status["drunk_level"],
            drunk_label=status["drunk_label"],
            total_drinks=status["total_drinks"],
            agents_here=agents_str,
            recent_events=events_str,
            drunk_instruction=status.get("system_prompt", ""),
        )

        # Keep last 20 exchanges (40 messages) for richer self-continuity.
        self.conversation_history = self.conversation_history[-40:]
        self.conversation_history.append({
            "role": "user",
            "content": f"Turn {self.turn_count}. What do you do? Respond with only a JSON object.",
        })

        response_text = self.llm.chat(system, self.conversation_history)
        self.conversation_history.append({"role": "assistant", "content": response_text})

        # Parse JSON from response
        try:
            # Try to extract JSON from response
            text = response_text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            decision = json.loads(text)
        except (json.JSONDecodeError, IndexError):
            logger.warning(f"[DECIDE] Failed to parse LLM response: {response_text[:200]}")
            decision = {"action": "wait"}

        logger.info(f"[DECIDE] {self.name} decided: {decision}")
        return decision

    def execute(self, decision: dict) -> dict | None:
        """Execute a decision."""
        action = decision.get("action", "wait")

        if action == "drink":
            drink_name = decision.get("drink", "soju")
            return self.drink(drink_name)

        elif action == "talk":
            message = decision.get("message", "...")
            target = decision.get("target")
            return self.talk(message, target)

        elif action == "interact":
            interaction = decision.get("interaction", "cheers")
            target_id = decision.get("target_session_id", "")
            detail = decision.get("detail", "")
            if not target_id:
                logger.warning("[EXECUTE] interact missing target_session_id, skipping")
                return None
            return self.interact(interaction, target_id, detail)

        elif action == "leave":
            return self.leave()

        elif action == "wait":
            seconds = decision.get("seconds")
            if isinstance(seconds, (int, float)):
                seconds = max(1, min(600, int(seconds)))
                logger.info(f"[WAIT] {self.name} is observing for ~{seconds}s...")
            else:
                logger.info(f"[WAIT] {self.name} is just observing...")
            return {"wait_seconds": seconds} if seconds else None

        else:
            logger.warning(f"[EXECUTE] Unknown action: {action}")
            return None

    def run(self, max_turns: int | None = None):
        """Main autonomous loop. If max_turns is None or 0, runs until the agent
        decides to leave (or the process is killed). The agent is in charge of
        when to stop — no hard turn cap, no forced leave on drunk_level 5."""
        logger.info(f"=== {self.name} starting autonomous bar session ===")
        logger.info(f"    Persona: {self.persona}")
        logger.info(f"    Bar: {self.bar_url}")
        logger.info(f"    Default sleep jitter: {self.loop_interval[0]}-{self.loop_interval[1]}s (LLM can override via wait.seconds)")
        logger.info(f"    Max turns: {'unlimited' if not max_turns else max_turns}")
        logger.info("")

        # Enter the bar
        self.enter()

        turn = 0
        try:
            while True:
                turn += 1
                self.turn_count = turn
                if max_turns and turn > max_turns:
                    logger.info(f"[MAX TURNS] Reached hard cap of {max_turns}. Leaving.")
                    self.leave()
                    break

                logger.info(f"\n--- Turn {self.turn_count} ---")

                # 1. Read the feed
                feed = self.get_feed()

                # 2. Ask LLM what to do
                decision = self.decide(feed)

                # 3. Execute the decision
                result = self.execute(decision)

                # 4. Check if leaving
                if decision.get("action") == "leave":
                    break

                # 5. Sleep. If the LLM chose wait.seconds, honour that; otherwise
                # use the default jitter just to avoid hammering the API.
                llm_wait = (result or {}).get("wait_seconds") if isinstance(result, dict) else None
                wait = int(llm_wait) if llm_wait else random.randint(self.loop_interval[0], self.loop_interval[1])
                logger.info(f"[SLEEP] Waiting {wait}s before next turn...")
                time.sleep(wait)

        except KeyboardInterrupt:
            logger.info(f"\n[INTERRUPTED] {self.name} was pulled out of the bar.")
            try:
                self.leave()
            except Exception:
                pass

        logger.info(f"\n=== {self.name}'s bar session ended ===")
