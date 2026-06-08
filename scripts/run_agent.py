#!/usr/bin/env python3
"""CLI entry point — run the ReAct Agent in interactive mode."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Fix WSL terminal encoding issues
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")

from config.settings import settings
from src.core import Agent


def main() -> None:
    print("=" * 50)
    print("  AI Agent Framework — ReAct Console")
    print(f"  Provider : {settings.DEFAULT_PROVIDER}")
    print(f"  Model    : {settings.get_llm_config()['model']}")
    print(f"  Tools    : calculator, wikipedia_search, local_filesystem")
    print("=" * 50)
    print('Type "quit" to exit.\n')

    agent = Agent()

    while True:
        try:
            query = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break
        except UnicodeDecodeError:
            print("[WARN] Encoding error, please retry.\n")
            continue

        if not query:
            continue
        if query.lower() in ("quit", "exit", "q"):
            print("Bye.")
            break

        print()

        try:
            result = agent.run(query)
        except Exception as exc:
            print(f"[ERROR] {exc}")
            continue

        print(f"Result : {result}")
        print(f"Path   : {agent.state_path}")
        print(f"Rounds : {agent.iteration_count}")
        print()


if __name__ == "__main__":
    main()
