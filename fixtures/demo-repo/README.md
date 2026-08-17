# Demo eval suite

Self-contained fixture (same idea as fatcheck's `fixtures/messy-repo`). Reviewers can inspect tasks and tools without running an LLM.

```
fixtures/demo-repo/
├── tasks.json           # 2 sanity + 2 eval tasks
├── notes.txt
├── baseline_tools.py    # fetch_url, read_text_file, extract_title_from_html
├── variant_tools.py     # fetch_and_extract_title, summarize_text
└── http_utils.py        # certifi HTTPS helper
```

## Tags

| Tag | Use |
|-----|-----|
| `sanity` | Inner loop: `skilldiff run --quick` |
| `eval` | Offline-friendly extra tasks (no live HTTP required if the agent uses local tools) |

## Run

From the repo root:

```bash
skilldiff run --quick \
  --tasks fixtures/demo-repo/tasks.json \
  --baseline-tools fixtures/demo-repo/baseline_tools.py \
  --variant-tools fixtures/demo-repo/variant_tools.py

# Full suite (omit --quick)
skilldiff run \
  --tasks fixtures/demo-repo/tasks.json \
  --baseline-tools fixtures/demo-repo/baseline_tools.py \
  --variant-tools fixtures/demo-repo/variant_tools.py
```

Root `examples/` and `tasks.json` stay as a shorter day-one copy of the sanity pair.
