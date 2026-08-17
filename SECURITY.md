# Security

## Reporting

Email **shunvel@gmail.com** with a description of the issue. Do not open a public GitHub issue for secrets or exploitable bugs.

## Secrets

- Never commit `.env`, API keys, or `.agent_diff/` run logs.
- `GEMINI_API_KEY` belongs in environment variables or CI secrets.
- If a key leaks, rotate it immediately at [Google AI Studio](https://aistudio.google.com/apikey).

## Scope

skilldiff executes user-supplied Python tool scripts. Treat `--baseline-tools` / `--variant-tools` as you would any local code you run: only point them at files you trust.
