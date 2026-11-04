"""Provider adapters: request shape and tool-call round trips, against fake SDK clients (no network)."""

from types import SimpleNamespace as NS

import pytest

from openfix.providers import ProviderError, ToolResult, ToolSpec, create, parse_ref

TOOLS = [
    ToolSpec("read_file", "read", {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]})
]


class FakeAnthropicStream:
    def __init__(self, msg):
        self.msg = msg

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self.msg


def test_anthropic_round_trip(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    p = create("anthropic:claude-opus-5-5", effort="high")
    calls = []
    replies = [
        NS(
            content=[
                NS(type="thinking", thinking=""),
                NS(type="tool_use", id="tu1", name="read_file", input={"path": "a.py"}),
            ],
            stop_reason="tool_use",
            model="claude-opus-5-5",
            usage=NS(input_tokens=100, output_tokens=20, cache_read_input_tokens=0, cache_creation_input_tokens=50),
        ),
        NS(
            content=[NS(type="text", text="done")],
            stop_reason="end_turn",
            model="claude-opus-5-5",
            usage=NS(input_tokens=10, output_tokens=5, cache_read_input_tokens=150, cache_creation_input_tokens=0),
        ),
    ]

    def stream(**params):
        calls.append({k: v for k, v in params.items()})
        return FakeAnthropicStream(replies[len(calls) - 1])

    p._client = NS(messages=NS(stream=stream))
    convo = p.start("system prompt", TOOLS)
    t1 = convo.send(user="fix it")
    assert t1.stop == "tool_use" and t1.tool_calls[0].arguments == {"path": "a.py"}
    assert t1.usage.input_tokens == 150
    first = calls[0]
    assert first["thinking"] == {"type": "adaptive"}
    assert first["output_config"] == {"effort": "high"}
    assert first["tools"][0]["input_schema"]["required"] == ["path"]
    assert first["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert first["extra_body"] == {"fallbacks": "default"}
    t2 = convo.send(tool_results=[ToolResult("tu1", "read_file", "contents")])
    assert t2.stop == "end" and t2.text == "done"
    # The assistant turn (including its thinking block) is replayed unchanged, then the tool result.
    msgs = calls[1]["messages"]
    assert msgs[1]["role"] == "assistant" and msgs[1]["content"][0].type == "thinking"
    assert msgs[2]["content"][0] == {
        "type": "tool_result",
        "tool_use_id": "tu1",
        "content": "contents",
        "is_error": False,
    }


def test_openai_compatible_round_trip(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "test")
    p = create("xai:grok-4")
    assert p.endpoint.base_url == "https://api.x.ai/v1" and not p.local
    calls = []
    replies = [
        NS(
            model="grok-4",
            usage=NS(prompt_tokens=50, completion_tokens=10, prompt_tokens_details=None),
            choices=[
                NS(
                    finish_reason="tool_calls",
                    message=NS(
                        content=None,
                        tool_calls=[NS(id="c1", function=NS(name="read_file", arguments='{"path": "b.js"}'))],
                    ),
                )
            ],
        ),
        NS(model="grok-4", usage=None, choices=[NS(finish_reason="stop", message=NS(content="ok", tool_calls=None))]),
    ]

    def create_(**params):
        calls.append(params)
        return replies[len(calls) - 1]

    p._client = NS(chat=NS(completions=NS(create=create_)))
    convo = p.start("sys", TOOLS)
    t1 = convo.send(user="go")
    assert t1.tool_calls[0].name == "read_file" and t1.tool_calls[0].arguments == {"path": "b.js"}
    assert "reasoning_effort" not in calls[0]  # only sent to OpenAI itself
    convo.send(tool_results=[ToolResult("c1", "read_file", "x", is_error=True)])
    msgs = calls[1]["messages"]
    assert msgs[0]["role"] == "system"
    assert msgs[2]["tool_calls"][0]["function"]["arguments"] == '{"path": "b.js"}'
    assert msgs[3] == {"role": "tool", "tool_call_id": "c1", "content": "ERROR: x"}


def test_local_providers_need_no_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    p = create("ollama:qwen2.5-coder:32b")
    assert p.local and p.model == "qwen2.5-coder:32b"


def test_missing_key_is_a_clear_error(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ProviderError, match="OPENAI_API_KEY"):
        create("openai:gpt-5")


def test_parse_ref():
    assert parse_ref("anthropic:claude-opus-5-5") == ("anthropic", "claude-opus-5-5")
    with pytest.raises(ProviderError):
        parse_ref("gpt-5")
    with pytest.raises(ProviderError, match="Unknown provider"):
        create("nope:model")


def test_gemini_round_trip(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    p = create("gemini:gemini-2.5-pro")
    sent = []

    class Chat:
        def send_message(self, parts):
            sent.append(parts)
            if len(sent) == 1:
                return NS(
                    function_calls=[NS(id=None, name="read_file", args={"path": "c.go"})],
                    usage_metadata=NS(
                        prompt_token_count=30,
                        candidates_token_count=5,
                        thoughts_token_count=2,
                        cached_content_token_count=0,
                    ),
                    candidates=[NS(finish_reason="STOP")],
                    text=None,
                )
            return NS(function_calls=None, usage_metadata=None, candidates=[NS(finish_reason="STOP")], text="fine")

    p._client = NS(chats=NS(create=lambda model, config: Chat()))
    convo = p.start("sys", TOOLS)
    t1 = convo.send(user="go")
    assert t1.tool_calls[0].arguments == {"path": "c.go"} and t1.usage.output_tokens == 7
    t2 = convo.send(tool_results=[ToolResult(t1.tool_calls[0].id, "read_file", "pkg main")])
    assert t2.text == "fine"
    assert sent[1][0].function_response.name == "read_file"
