# OpenHands and LangGraph Integration Notes

This project integrates the strongest architectural patterns from OpenHands and LangGraph without copying their source code.

## OpenHands-inspired strengths

OpenHands emphasizes a composable agent SDK with explicit tools, workspaces, events, security policies, and sandboxed execution. The platform now adopts those strengths through:

- `agi_platform.agent_events.Event`, `ActionEvent`, `ObservationEvent`, and `EventLog` for append-only event streams.
- `SandboxLab.execute_action()` for action-to-observation execution.
- `GET /sandbox/events` for API visibility into the sandbox event stream.
- command allowlisting and temporary workspace cleanup in `SandboxLab`.

## LangGraph-inspired strengths

LangGraph emphasizes durable execution, typed graph state, checkpointing, streaming, and human-in-the-loop interruption/resume. The platform now adopts those strengths through:

- `WorkflowCheckpoint` as persisted graph state.
- `WorkflowEngine.plan()` for stateful workflow creation.
- `require_human_review` to pause workflows with an interrupt event.
- `WorkflowEngine.resume()` to continue execution with human input.
- `GET /workflows/{checkpoint}/events` to stream workflow history.

## Source references

- OpenHands SDK architecture: https://docs.openhands.dev/sdk/arch/overview
- OpenHands runtime architecture: https://docs.openhands.dev/openhands/usage/architecture/runtime
- LangGraph overview: https://docs.langchain.com/oss/python/langgraph/overview
- LangGraph persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- LangGraph interrupts: https://docs.langchain.com/oss/python/langgraph/interrupts
