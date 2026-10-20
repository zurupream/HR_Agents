# T013 - Fix ADK web crash on first message and use the strongest Gemini model

## Problem (reproduced by the user in `adk web`)
Typing "hi" in the ADK web UI shows an error:
  KeyError: 'Context variable not found: `job_advert_text`.'
Cause: adk web creates a new session with EMPTY state. The agent's instruction templates in
~/candidates_screening/screening_agent/agent.py reference {job_advert_text}, which only the
command-line entry point (run_screening_pipeline_async) puts into session state. ADK fills
{...} placeholders from session state, so the first message crashes before any model call.

## Fix required
1. Make the agent self-sufficient when state is empty. Preferred approach: replace the
   string instruction that contains {job_advert_text} with an instruction provider (a function
   taking the ReadonlyContext) that uses ctx.state["job_advert_text"] if present, otherwise
   calls read_job_advert() from tools.py. Do the same for any other {placeholder} in the
   instructions that is not guaranteed to be in state. Keep the prompt text unchanged.
   Alternatively set the state in a before_agent_callback on root_agent. Pick one, keep it simple.
2. Make the model the strongest Gemini model available: set the default in get_model_name()
   to "gemini-2.5-pro" and set MODEL_NAME=gemini-2.5-pro in the server's .env. Keep all
   GOOGLE_GENAI_USE_VERTEXAI / project / location settings as they are. Do not write any key or
   credential into any file.
3. Keep the same structure: __init__.py, agent.py, tools.py, schemas.py, prompts/, data/, output/.
   Keep relative imports (from .schemas / from .tools).

## Testing you must do on this server
- Add tests/test_adk_web_entry.py (pytest) that:
  a. imports screening_agent.agent and checks root_agent exists;
  b. builds a session with EMPTY state and checks that resolving every agent's instruction does
     not raise KeyError (use the ADK instruction-resolution helpers, or the same code path adk web
     uses; if this is not feasible, check that no instruction string contains an unresolved
     {placeholder} that is missing from state, and that the provider returns the advert text);
  c. checks get_model_name() returns "gemini-2.5-pro" when MODEL_NAME is unset.
- Run pytest from ~/candidates_screening/screening_agent with .venv/bin/python -m pytest.
- This server has NO Google/Vertex credentials. Do NOT try to make live model calls and do NOT
  claim a live test passed. In your final summary, state exactly which checks ran and which could
  not run here.

## Rules
- Work only inside ~/candidates_screening. Do not touch other folders.
- No secrets, keys or client secrets in any file.
- Do not change the output format of screening_results.xlsx or rubric.json.

## Done means
- The KeyError path is fixed in code (show the diff summary in your final message).
- Default model is gemini-2.5-pro in code and in the server .env.
- tests/test_adk_web_entry.py passes (show pytest output summary).
- Final summary lists what was changed, the test results, and what still needs a live test on the laptop.
