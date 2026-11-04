# Providers and models

Models are addressed as `provider:model`. Run `openfix providers` to see what's installed and which credentials
are set.

| Provider | Example | Credentials | Install |
|---|---|---|---|
| `anthropic` | `anthropic:claude-opus-5-5` | `ANTHROPIC_API_KEY` | `openfix[anthropic]` |
| `openai` | `openai:gpt-5` | `OPENAI_API_KEY` | `openfix[openai]` |
| `gemini` | `gemini:gemini-2.5-pro` | `GEMINI_API_KEY` (or Vertex AI via `GOOGLE_GENAI_USE_VERTEXAI`) | `openfix[gemini]` |
| `xai` | `xai:grok-4` | `XAI_API_KEY` | `openfix[openai]` |
| `openrouter` | `openrouter:qwen/qwen3-coder` | `OPENROUTER_API_KEY` | `openfix[openai]` |
| `groq`, `deepseek`, `mistral`, `together`, `fireworks` | `mistral:devstral-medium-latest` | `<NAME>_API_KEY` | `openfix[openai]` |
| `ollama` | `ollama:qwen2.5-coder:32b` | none (local) | `openfix[openai]` |
| `vllm`, `lmstudio` | `vllm:<served-name>` | none (local) | `openfix[openai]` |
| `compat` | `compat:<model>` | `OPENFIX_COMPAT_BASE_URL`, optional `OPENFIX_COMPAT_API_KEY` | `openfix[openai]` |
| `scripted` | `scripted:path/to/script.yaml` | none; replays recorded tool calls for tests and demos | built in |

Model names in the examples are illustrative. Use any model your account can access that supports tool or function
calling. Override any endpoint's URL with `OPENFIX_<PROVIDER>_BASE_URL` (for example `OPENFIX_OLLAMA_BASE_URL`).

## Notes per provider

- **Anthropic** uses the official SDK with adaptive thinking, the configured effort, prompt caching on the stable
  prefix, and assistant turns replayed unchanged. On models that support it, server-side refusal fallback is enabled
  (set `OPENFIX_ANTHROPIC_FALLBACKS=0` to turn it off).
- **OpenAI-compatible** endpoints use Chat Completions with function calling, the most widely implemented
  interface. `reasoning_effort` is sent to OpenAI only, and is dropped automatically when a model rejects it.
- **Gemini** uses the official `google-genai` SDK with automatic function calling disabled, so OpenFix keeps control
  of every tool call.

## Choosing models

- Use a **different provider for the reviewer** than for the author, so the review isn't checking a model's work
  with the same model's blind spots.
- Use `local_only_paths` to keep sensitive code on infrastructure you control, without giving up cloud models for
  everything else.
- Token counts are always recorded in the receipt. Dollar costs are computed for Claude out of the box, and for
  other models when you add `pricing` to the policy.

## Adding a provider

Implement `start(system, tools) -> Conversation` and `Conversation.send(user=..., tool_results=...) -> Turn` (see
`src/openfix/providers/base.py`), then register it in `providers/__init__.py`. Keep provider-native history inside
the conversation object, so that provider-specific content (such as reasoning blocks) is replayed unchanged.
