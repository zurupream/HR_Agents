"""Pytest suite for T013: Fix ADK web crash on first message and use gemini-4-argon."""

from __future__ import annotations

import asyncio
from pathlib import Path
import re
import sys

from google.adk.agents import BaseAgent, LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.flows.llm_flows.instructions import _process_agent_instruction
from google.adk.flows.llm_flows.prompt import inject_session_state
from google.adk.runners import InMemoryRunner
from google.genai import types
import pytest

# Ensure ~/candidates_screening is on sys.path when running pytest from screening_agent/
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import screening_agent.agent as agent_module
from screening_agent.tests.fixtures.create_dummy_data import build_dummy_dataset
import screening_agent.tools as tools_module
from screening_agent.tools import read_job_advert


@pytest.fixture(autouse=True)
def _sales_test_dataset(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Create temporary Sales Executive fixture dataset in tmp_path for every test."""
    data_dir = tmp_path / "sales_fixture"
    out_dir = tmp_path / "sales_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    build_dummy_dataset(data_dir)
    monkeypatch.setattr(tools_module, "DEFAULT_ADVERT_PATH", data_dir / "job_advert.docx")
    monkeypatch.setattr(tools_module, "DEFAULT_APPLICATIONS_DIR", data_dir / "applications")
    monkeypatch.setattr(tools_module, "DEFAULT_RUBRIC_PATH", out_dir / "rubric.json")
    monkeypatch.setattr(tools_module, "DEFAULT_EXCEL_PATH", out_dir / "screening_results.xlsx")
    monkeypatch.setattr(tools_module, "DEFAULT_EVALUATIONS_PATH", out_dir / "evaluations.json")
    monkeypatch.setattr(tools_module, "DEFAULT_HR_DECISIONS_PATH", out_dir / "hr_decisions.json")
    return data_dir


def _iter_all_agents(agent: BaseAgent) -> list[BaseAgent]:
    """Recursively collect an agent and all its sub_agents."""
    collected: list[BaseAgent] = [agent]
    for sub in getattr(agent, "sub_agents", []) or []:
        collected.extend(_iter_all_agents(sub))
    return collected


def test_root_agent_exists() -> None:
    """(a) Import screening_agent.agent and verify root_agent exists and has expected sub-agents."""
    assert hasattr(agent_module, "root_agent")
    assert agent_module.root_agent is not None
    assert isinstance(agent_module.root_agent, BaseAgent)
    sub_names = [a.name for a in agent_module.root_agent.sub_agents]
    assert "rubric_agent" in sub_names
    assert "screening_pipeline" in sub_names


def test_resolve_instructions_with_empty_session_state() -> None:
    """(b) Build a session with EMPTY state and verify resolving every agent's instruction
    does not raise KeyError and returns the job advert text.
    """

    async def _run_check() -> None:
        runner = InMemoryRunner(
            agent=agent_module.root_agent,
            app_name="adk_web_empty_state_test",
        )
        empty_session = await runner.session_service.create_session(
            app_name="adk_web_empty_state_test",
            user_id="adk_web_user",
            state={},
        )
        assert empty_session.state == {}

        expected_advert_text = read_job_advert()
        assert len(expected_advert_text) > 50

        # Check all agents in root_agent hierarchy plus dynamically created screening_agent
        agents_to_check = _iter_all_agents(agent_module.root_agent) + [
            agent_module.build_screening_agent("C001")
        ]

        placeholder_pattern = re.compile(r"\{+[a-zA-Z_][a-zA-Z0-9_]*\}+")

        for ag in agents_to_check:
            if not isinstance(ag, LlmAgent):
                continue

            inv_ctx = InvocationContext(
                session_service=runner.session_service,
                invocation_id=f"test-inv-{ag.name}",
                agent=ag,
                session=empty_session,
            )
            readonly_ctx = ReadonlyContext(inv_ctx)

            # 1. Resolve via ADK's _process_agent_instruction (exact path used by adk web)
            resolved_instruction = await _process_agent_instruction(ag, inv_ctx)
            assert isinstance(resolved_instruction, str)
            assert len(resolved_instruction) > 0

            # 2. Verify canonical_instruction and inject_session_state do not raise KeyError
            raw_inst, bypass_injection = await ag.canonical_instruction(readonly_ctx)
            assert bypass_injection is True
            injected = await inject_session_state(raw_inst, readonly_ctx)
            assert isinstance(injected, str)

            # 3. Verify no unresolved {placeholder} remains
            assert not placeholder_pattern.search(resolved_instruction), (
                f"Unresolved placeholder found in {ag.name}: "
                f"{placeholder_pattern.findall(resolved_instruction)}"
            )

            # 4. Verify rubric_agent instruction includes the job advert text from read_job_advert()
            if ag.name == "rubric_agent":
                assert expected_advert_text in resolved_instruction

    asyncio.run(_run_check())


def test_adk_web_first_message_hi_with_empty_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify sending 'hi' on a fresh empty-state session (as adk web does) completes without KeyError."""
    # Ensure offline deterministic mode is used on this server (no live API calls)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)
    monkeypatch.setattr(
        "screening_agent.tools.DEFAULT_RUBRIC_PATH", tmp_path / "rubric.json"
    )
    monkeypatch.setattr(
        "screening_agent.tools.DEFAULT_EXCEL_PATH",
        tmp_path / "screening_results.xlsx",
    )

    async def _run_hi() -> None:
        runner = InMemoryRunner(
            agent=agent_module.root_agent,
            app_name="adk_web_hi_test",
        )
        session = await runner.session_service.create_session(
            app_name="adk_web_hi_test",
            user_id="web_user",
            state={},
        )
        assert session.state == {}

        user_msg = types.Content(
            role="user",
            parts=[types.Part.from_text(text="hi")],
        )
        events = []
        async for ev in runner.run_async(
            user_id="web_user",
            session_id=session.id,
            new_message=user_msg,
        ):
            events.append(ev)

        assert len(events) >= 2
        updated = await runner.session_service.get_session(
            app_name="adk_web_hi_test",
            user_id="web_user",
            session_id=session.id,
        )
        assert "rubric" in updated.state
        assert "evaluations" in updated.state
        assert len(updated.state["evaluations"]) == 4

    asyncio.run(_run_hi())


def test_get_model_name_defaults_to_gemini_2_5_pro(monkeypatch: pytest.MonkeyPatch) -> None:
    """(c) Check get_model_name() returns 'gemini-4-argon' when MODEL_NAME is unset."""
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert agent_module.get_model_name() == "gemini-4-argon"

    # Also verify .env configures MODEL_NAME=gemini-4-argon
    env_path = Path(agent_module.__file__).resolve().parent / ".env"
    assert env_path.exists()
    env_text = env_path.read_text(encoding="utf-8")
    assert "MODEL_NAME=gemini-4-argon" in env_text
