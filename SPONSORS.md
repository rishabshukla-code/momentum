# Partner prizes and how Momentum uses each one

## Official links (from tokensand.com/personalagenthack)

- Submit: https://tokensand.com/personalagenthack/submit (deadline 4:30 PM PT: repo, demo video link, what you built + tools, team names/emails)
- tokens& app checks: https://tokensand.com/docs/api#observe-workflow
- Arcee: https://docs.arcee.ai/
- Guild: https://docs.guild.ai/ · Smith bot: https://app.guild.ai/chat
- Superlinked SIE Serverless: https://superlinked.com/serverless · https://superlinked.com/docs · https://github.com/superlinked/cookbook
- Cognee: https://docs.cognee.ai/ · https://platform.cognee.ai/sign-up · https://github.com/topoteretes/cognee
- Firedrill: https://firedrill.run/hacker-docs · https://docs.firedrill.run/
- SingleStore: https://docs.singlestore.com/cloud/getting-started-with-singlestore-helios/ · Python: https://docs.singlestore.com/cloud/developer-resources/connect-with-application-development-tools/connect-with-python/
- Amplitude: https://amplitude.com/get-started · Statsig: https://console.statsig.com/sign_up
- Airbyte context layer: https://docs.airbyte.com/platform/context-layer
- Senso.ai (shopping context): https://docs.senso.ai/docs/overview
- Persona: https://help.withpersona.com/


Based on the partner talks this morning. Status: ✅ built in, 🔌 slot ready (add the key), 📝 to do at the booth.

| Partner | Prize | What they asked for | How Momentum uses it | Status |
|---|---|---|---|---|
| **Guild.ai** | 100M / 50M / 25M tokens | Acts first (event trigger, not chat), least access that works, shows what it did without you, runs in a sandbox, human in the loop. Their own example: a Telegram message when something changes. | Event trigger via `POST /trigger` (point a Guild cron at it). Only needs one Telegram chat. Every decision logged with its reason. You always decide with the buttons. | ✅ endpoint · 📝 deploy on Guild + set cron |
| **SingleStore** | $1000 / $750 / $500 gift card, $600 credits | Live data loop: state → reason → act → write back → approval → update state. Store session state and telemetry. | `nudges` table is the loop: state, the decision and reason, the outcome. Runs on a SingleStore Helios Starter cluster over TLS (BIGINT ids for its large auto-increment values); `python -m momentum.migrate` copies local history across. | ✅ live |
| **Arcee** | $500 inference credits, "best use of the Pareto frontier" | Cheap, fast open models instead of frontier models. | A small open model writes every nudge. One short call per nudge: the cheap, frequent task they described. | 🔌 add base URL, key, model |
| **Cognee** | $500 cash + $500 credits | Memory graph that improves from agent traces and feedback. | Every outcome is written as a fact ("tiny step nudge worked Tuesday morning"); recalled when writing the next nudge. | 🔌 `pip install cognee`, set `COGNEE_ENABLED=true` |
| **Superlinked** | (ask at booth) | Wrap small task-specific models as tools instead of paying an LLM. | When you tap "Not now", your one-line excuse is classified (tired / overwhelmed / busy / bored / unclear) and boosts the nudge types that help with it. | 🔌 add endpoint; 📝 pick a classifier from their cookbook and fix the request shape in `classify_excuse()` |
| **Amplitude** | (ask at booth) | Agent analytics, trace view, custom evals on every session. | `nudge_sent` (type, reason, scores, fatigue) and `nudge_outcome` (success, latency) events. 📝 Build a custom eval: "did the nudge lead to a start within 15 min". | 🔌 add API key |
| **Firedrill** | (ask at booth) | Run thousands of simulations against synthetic users with personas, find failures before users do. | `personas.json` holds the synthetic users. 📝 Install the Firedrill CLI/skill and ask it to drill the bot against these personas. Local simulator is the fallback. | 📝 |
| **Persona** | Keychron gift cards + swag | Agent verification, humanness/age claims. | Weak fit. Skip unless you add "someone's counting" with a real accountability buddy. | skip |

## Booth questions (morning)

1. **Arcee:** exact base URL for the OpenAI-compatible endpoint, and which small model they'd pick for short message writing.
2. **Superlinked:** a text classifier from the cookbook, and the request/response shape.
3. **Firedrill:** can it drive a Telegram bot, or should we expose `/trigger` + a callback endpoint for its synthetic users?
4. **Amplitude:** is there an agent-specific SDK for the trace view, or is the HTTP API enough?
5. **Guild:** fastest way to run `python -m momentum.bot` in their sandbox with a cron hitting `/trigger`.
