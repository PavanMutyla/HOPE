"""SubAgentSpec — everything a dynamically spawned sub-agent is told.

Shaped by the main lesson from Anthropic's multi-agent research write-up:
vague one-line delegations made sub-agents duplicate each other's searches
or leave gaps, and what fixed it was giving every sub-agent an objective, an
output format, which tools to use, and explicit task boundaries. So those
are required fields here rather than something a prompt has to remember.
"""

from pydantic import BaseModel, Field, model_validator

# What each template may ever be given, enforced when the spec is built — a
# spec asking a researcher to also get write_file is rejected in code, no
# matter what the planner LLM (or a web page it read) asked for.
TEMPLATE_TOOLS: dict[str, frozenset[str]] = {
    "researcher": frozenset({"web_search", "read_url"}),
}


class SubAgentSpec(BaseModel):
    template: str
    objective: str = Field(description="What this agent must find out or do.")
    output_format: str = Field(description="What the agent hands back, and in what shape.")
    boundaries: str = Field(description="What's out of scope, so parallel agents don't overlap.")
    tools: list[str]
    max_tool_calls: int = Field(gt=0)

    @model_validator(mode="after")
    def _tools_within_template(self) -> "SubAgentSpec":
        allowed = TEMPLATE_TOOLS.get(self.template)
        if allowed is None:
            raise ValueError(f"Unknown sub-agent template '{self.template}'.")
        extra = set(self.tools) - allowed
        if extra:
            raise ValueError(
                f"Template '{self.template}' may not use {sorted(extra)} — allowed: {sorted(allowed)}."
            )
        return self
