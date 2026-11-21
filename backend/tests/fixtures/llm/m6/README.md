# Recorded LLM answers for Shino's prompts (M6 quiz)

One `<name>.json` per recording: `{"name": ..., "calls": [{"prompt_sha256": ..., "raw": ...}]}`,
the provider's raw replies in call order.

- Normal tests replay them through the `shino_llm` fixture (`tests/shino_helpers.py`):
  `shino_llm.use("<name>")`, then call the service as usual. No network.
- Live tests (`@pytest.mark.live`, synthetic test course only) call the real LLM through the same
  fixture; `pytest -m live --record-llm` writes the file, and only when the test passed.
- A replay warns when the prompt changed since recording; re-record then.

Only synthetic course content goes here (no course materials).
