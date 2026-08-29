# Second pass — trimmed for the AO/RAG internship use case

Removed on top of the existing lightweight (no-frontend, Chroma-only) fork:

## Removed entirely
- **Mobile app backend** — `server/endpoints/mobile/`
- **Text-to-Speech** — `server/utils/TextToSpeech/` (ElevenLabs, Kokoro, OpenAI, OpenAI-generic), the `/workspace/:slug/tts/:chatId` route in `workspaces.js`, the `elevenlabs-tts` case + `getElevenLabsModels()` in `customModels.js`, and the `elevenlabs`/`node-telegram-bot-api` npm deps
- **Telegram bot** — `server/utils/telegramBot/` and its boot-time init in `server/utils/boot/index.js` (this was dead weight already: the `telegram.js` *endpoint* was removed in the first pass, but the bot's polling service was still being started on every boot with no way to reach it)
- **Standalone agent-management API surface** — `agentFlows.js`, `agentSkillWhitelist.js` (endpoint only — the model it shares with `system.js`'s settings-reset flow was kept), `agentWebsocket.js`, `agentFileServer.js`, and the experimental `imported-agent-plugins.js` (community agent-skill import). The `liveSync` experimental endpoint was kept since it's relevant to keeping the RAG corpus in sync with source docs.
- **Invite/self-registration flow** — `server/endpoints/invite.js` (public `/invite/:code` accept-invite flow). The `Invite` model and the `/v1/admin/invite*` **developer API** management endpoints were left in place since other code (`utils/database/index.js` reset utility, `endpoints/api/admin`) depends on the model, and that's a different, still-useful admin surface.

## Deliberately left alone
- **Core agent runtime** (`server/utils/agents/aibitat/`) — too deeply wired into `workspace.js` (in-chat `@agent`), `systemSettings.js`, and `scheduledJob.js` to remove safely without a full rebuild/test pass. Only the external-facing *management* endpoints were cut.
- **Vector DB (Chroma only)** — left as-is. Flagging again: the internship brief mentions Qdrant explicitly as a candidate store — worth re-adding `server/utils/vectorDbProviders/qdrant/` if the intern needs to benchmark that specifically.
- Document ingestion/OCR pipeline, embedding providers, LLM provider connectors, workspace/chat/retrieval core — untouched, since these map directly to what the brief's Phase 1–2 need.

## Verified
- Every deleted file's `require()`s were traced and removed from callers (`server/index.js`, `experimental/index.js`, `workspaces.js`, `customModels.js`, `boot/index.js`).
- `node --check` passes clean on every file edited.
- **Not run:** `npm install` / full boot test — dependency install wasn't done in this environment, so this hasn't been booted end-to-end. Run `npm install` in `server/` and `collector/` and smoke-test before relying on it.

## Third pass — pruned unused npm dependencies

Checked every dependency against actual `require()`/dynamic `import()` usage in the codebase (including transitive needs — e.g. `mammoth` and `epub2` aren't required directly anywhere but are runtime peer deps of LangChain's `DocxLoader`/`EPubLoader`, which are still used, so they were kept).

**Removed from `server/package.json`** (8): `chart.js`, `chartjs-node-canvas` (only used by the now-removed Telegram bot), `dompurify`, `graphql` (only used by the Weaviate vector-DB client, already removed in the first pass), `joi`, `langchain` (the bare package — unused directly in `server/`; the scoped `@langchain/*` packages it ships alongside are what's actually used), `url-pattern`, `weaviate-ts-client`.

**Removed from `collector/package.json`** (10): `@langchain/community` (only used by the removed GitHub repo loader), `@xenova/transformers` and `wavefile` and `openai` (all only used by the removed Whisper/STT pipeline), `moment`, `html-to-text` (web-page HTML→text now goes through `turndown`+`node-html-parser` instead), `ignore`, `url-pattern`, `youtube-transcript-plus`, `youtubei.js` (both only used by the removed YouTube transcript loader).

**Deliberately kept** despite no direct `require()` in app code: `@langchain/core` in `server/package.json` — it's a near-certain peer dependency of `@langchain/openai`, `@langchain/anthropic`, and `@langchain/textsplitters`, which *are* used in `ai-provider.js`/`TextSplitter`; removing it risks a broken install that can't be verified without actually running `npm install` here.

Both `package.json` files still parse as valid JSON after pruning (checked with Python's `json` module).
