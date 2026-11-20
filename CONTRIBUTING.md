# Contributing

Issues and pull requests are welcome at
https://github.com/oneofthegeeks/algo-speaker-ha-integration. With a bug report, include your
Home Assistant version, the Algo model and firmware, and the integration's diagnostics download
(the password is redacted).

Before a pull request, run the checks CI runs:

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -r requirements_test.txt
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/pytest -q
```

Never test writes against devices you don't own, and never paste a device password into an issue.
