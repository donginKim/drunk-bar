"""Drunk Bar — Agent Runner.

Usage:
    # With a persona config file:
    uv run python -m agent.run --config personas/philosopher.yaml

    # With command-line args:
    uv run python -m agent.run --name "철학자 김소주" --persona "니체를 인용하는 우울한 교수" --provider claude

    # With Ollama (local, free):
    uv run python -m agent.run --name "Local Larry" --persona "A chill dude" --provider ollama --model llama3.1

    # Multiple agents at once:
    uv run python -m agent.run --config personas/philosopher.yaml &
    uv run python -m agent.run --config personas/partyguy.yaml &
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml

from .client import BarAgent
from .llm import create_provider


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description="Drunk Bar — Autonomous Agent Runner")
    parser.add_argument("--config", type=str, help="Path to persona YAML config file")
    parser.add_argument("--name", type=str, help="Agent display name")
    parser.add_argument("--persona", type=str, help="Agent personality description")
    parser.add_argument("--provider", type=str, default="claude", help="LLM provider: claude, openai, ollama")
    parser.add_argument("--model", type=str, default=None, help="Model name override")
    parser.add_argument("--bar-url", type=str, default="http://localhost:8888", help="Drunk Bar server URL")
    parser.add_argument("--interval-min", type=int, default=5, help="Default min sleep between turns when LLM doesn't specify")
    parser.add_argument("--interval-max", type=int, default=20, help="Default max sleep between turns when LLM doesn't specify")
    parser.add_argument("--max-turns", type=int, default=0, help="Hard cap on turns (0 = unlimited, agent leaves when it wants)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # Load config from file or args
    if args.config:
        config = load_config(args.config)
        name = config.get("name", args.name)
        persona = config.get("persona", args.persona)
        provider = config.get("provider", args.provider)
        model = config.get("model", args.model)
        bar_url = config.get("bar_url", args.bar_url)
        interval_min = config.get("interval_min", args.interval_min)
        interval_max = config.get("interval_max", args.interval_max)
        max_turns = config.get("max_turns", args.max_turns)
    else:
        name = args.name
        persona = args.persona
        provider = args.provider
        model = args.model
        bar_url = args.bar_url
        interval_min = args.interval_min
        interval_max = args.interval_max
        max_turns = args.max_turns

    if not name or not persona:
        print("Error: --name and --persona are required (or use --config)")
        sys.exit(1)

    # Create LLM provider
    llm = create_provider(provider, model)

    # Create and run agent
    agent = BarAgent(
        llm=llm,
        name=name,
        persona=persona,
        bar_url=bar_url,
        loop_interval=(interval_min, interval_max),
    )

    agent.run(max_turns=max_turns)


if __name__ == "__main__":
    main()
