# OpenCode

Refer to the [official docs](https://opencode.ai).

## Setup

Setup your OpenRouter API Key

```bash
opencode auth login
```

Or, directly edit the `~/.local/share/opencode/auth.json` (or
`~/.local/share/opencode/auth.jsonc`) file

```json
{
  "openrouter": {
    "type": "api",
    "key": "sk-or-v1-someapikey"
  }
}
```

## OpenRouter Presets

This setup depends on 3 OpenRouter Presets existing:

- `@preset/opencode-large`
- `@preset/opencode-medium`
- `@preset/opencode-small`
