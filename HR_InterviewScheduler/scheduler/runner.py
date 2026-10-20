"""Run one scheduling cycle through the ADK runner.

Usage:
    python -m scheduler.runner                 # one cycle against the seeded demo data
    python -m scheduler.runner "reply: C-001 option 2"   # pass a candidate reply as the run input
"""

from __future__ import annotations

import asyncio
import sys
import uuid

from google.adk.runners import InMemoryRunner
from google.genai import types

from scheduler import config  # noqa: F401
from scheduler.agent import root_agent
from scheduler import demo_data
from scheduler.tools import configure_from_env

APP_NAME = "interview_scheduler"
USER_ID = "scheduler-service"
DEFAULT_INPUT = "Run a scheduling cycle: process pending candidates, then chase anyone awaiting a reply for more than 48 hours."


async def run_cycle(message: str = DEFAULT_INPUT) -> list[str]:
    runner = InMemoryRunner(agent=root_agent, app_name=APP_NAME)
    session_id = uuid.uuid4().hex
    await runner.session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)

    content = types.Content(role="user", parts=[types.Part(text=message)])
    replies: list[str] = []
    async for event in runner.run_async(user_id=USER_ID, session_id=session_id, new_message=content):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text and event.is_final_response():
                    replies.append(part.text)
    return replies


def main() -> None:
    configure_from_env()
    demo_data.seed()
    message = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_INPUT
    for text in asyncio.run(run_cycle(message)):
        print(text)


if __name__ == "__main__":
    main()
