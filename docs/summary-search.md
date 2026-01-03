# Summary Search

PowerSearch now exposes a background-task tool, `summarize_search`, that runs a search and uses MCP sampling to produce a concise, citation-preserving summary.

- Inputs: `query` (required), `intent` (required guidance for tone/focus), optional `time_range` (`day`, `month`, `year`), `max_results` (caps context), and `map_reduce` (sequentially summarizes chunks for larger corpora).
- Execution: the tool is decorated with `task=True`, so clients get a task ID, progress events, and a final result without blocking.
- Context safety: results are trimmed to `POWERSEARCH_FILTER_TOP_K` (default 10) and `POWERSEARCH_SUMMARY_CONTENT_LIMIT` (if set) before sampling. General `POWERSEARCH_CONTENT_LIMIT` still applies to non-summary fetches. Chunking uses `POWERSEARCH_SUMMARY_CHUNK_SIZE` (default 4).
- Latency caveat: MCP sampling allows only one request at a time; map-reduce runs chunk summaries sequentially, so expect longer runtimes on large sets.

Example task-based invocation (client-side pseudo-code):

```python
task = await client.call_tool(
    "summarize_search",
    {"query": "kubernetes cluster autoscaling", "intent": "prepare a brief with citations"},
    task=True,
)
result = await task.result()
print(result.structured_content["result"]["summary"])
```
