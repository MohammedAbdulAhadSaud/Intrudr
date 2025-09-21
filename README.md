````markdown
## Intrudr — Concurrent HTTP Requester / Parameter Fuzzer (VERSION4 BETA)

> **WARNING:** This tool can generate a large number of HTTP requests and write full responses to disk. Only use it on systems and targets you own or where you have explicit, documented permission to test.

---

## What is this

`Intrudr` is a small command-line Python utility designed to take a raw HTTP request, discover parameters and placeholders, and send many variations of that request concurrently. It supports several attack modes (Sniper, Clusterbomb, Pitchfork, Battering-ram) and saves full responses to a user-specified output folder. It is intended for **authorized security testing and research**.

> **Not a hacking tool for unauthorized use.** Always have written permission before testing any target.

---

## Features

- Parse raw HTTP requests (request line, headers, body).
- Auto-detect query/form parameters and `^^placeholder^^` tokens.
- Interactive prompt to provide parameter values or load from files.
- Several combination ("attack") modes: Sniper, Clusterbomb (Cartesian), Pitchfork, Battering-ram.
- Concurrent request sending with ordered result collection and optional per-worker sessions.
- Save full responses to disk and write a CSV `summary.csv` with metadata.
- Optional recording of the prepared raw HTTP bytes for each sent request.
- Configurable timeouts, retry count, worker count, throttling, and user agents.

---

## Requirements

- Python 3.8+
- The following Python packages (installable via `pip`):
  - `requests`
  - `colorama`

### Example install

```bash
python3 -m pip install -r requirements.txt
# Or individually
python3 -m pip install requests colorama
````

A `requirements.txt` entry for this repository could contain:

```text
requests
colorama
```

---

## Quick start

1. Save the script (for example `intrudr.py`) and ensure it is executable:

```bash
chmod +x intrudr.py
```

2. Run it:

```bash
./intrudr.py
# or
python3 intrudr.py
```

3. When prompted, paste a raw HTTP request (request line, headers, blank line, body). Use `^^...^^` wrappers inside the request to mark placeholders you want replaced programmatically.

4. Follow the interactive prompts to provide parameter values (manual or file) and choose an output folder.

---

## Example raw request (user input)

```http
POST /path/resource?foo=1&bar=2 HTTP/1.1
Host: example.com
Content-Type: application/x-www-form-urlencoded
User-Agent: unittest

username=admin&password=^^PASSWORD^^&mode=normal
```

In the example above `^^PASSWORD^^` becomes a placeholder (mapped to `PH1`) and will be replaced by values you supply.

---

## Important configuration options (top of script)

These constants live near the top of the script and can be adjusted to change runtime behavior:

```python
REQUEST_TIMEOUT = 60
REQUEST_RETRIES = 1
MAX_WORKERS = 12
THROTTLE_SECONDS = 0.0
SUMMARY_FILENAME = "summary.csv"
RESPONSE_PREVIEW_LEN = 2000
SHOW_FULL_RESPONSE = True
MAX_RESPONSE_PRINT = 100_000
USE_PROXY = False
PROXY_ADDR = "http://127.0.0.1:8080"
RECORD_PREPARED_RAW = True
```

* `USER_AGENTS` – a list of UA strings randomly selected per request.
* Adjust these values carefully depending on your environment and target.

---

## Output

By default responses and CSV summaries are written to the folder you specify when running. Expect to see:

```text
responses/response_0001_...txt   # saved full response bodies
responses/sent_raw_0001.bin     # (optional) raw prepared bytes recorded
responses/summary.csv           # CSV summary (index, params, status, length, filename, error, req_time_s, request, full_response, sent_raw_file)
```

**Note:** Writing full responses to disk can consume a lot of space. Use `SHOW_FULL_RESPONSE` and `MAX_RESPONSE_PRINT` settings to limit console output, and monitor disk usage when saving many responses.

---

## Safety, Ethics & Legal

This tool is capable of generating a large volume of requests and could be used to disrupt services. You must follow these rules:

```text
- Only run against systems you own or where you have explicit, written permission to test.
- Use conservative MAX_WORKERS, THROTTLE_SECONDS, and REQUEST_RETRIES when testing production systems.
- Do not use this tool to perform denial-of-service attacks, credential stuffing, or other unauthorized activities.
- Keep logs and communicate with the responsible parties when performing tests.
```

The author(s) are not responsible for misuse. Use at your own risk.

---

## Tips & Troubleshooting

```text
- If you see "No Host header" errors, make sure the input raw request contains a Host: header.
- If parameters are not detected automatically, ensure query string or form-encoded body is present, or provide placeholder tokens (^^...^^).
- For complex cookies/headers that should not be altered, avoid placing parameter-looking patterns inside them, or sanitize via the interactive prompts.
- Use proxying (USE_PROXY) with tools like mitmproxy for debugging prepared requests.
```

---

## Contributing

Contributions are welcome. Please open issues and pull requests on the repository. When contributing:

```text
- Add tests for parsing and combo generation when possible.
- Keep the interactive UX clear — the script is intentionally conservative with prompting.
```

---

## License

```text
This repository does not include a license by default. Add a LICENSE file (for example, MIT) if you want to permit reuse.
Without a license, the default is: All rights reserved.
```

---

## Acknowledgements

```text
- Script author: MohammedAbdulAhadSaud (ASCII signature in the script)
- Uses requests and colorama for HTTP operations and colored console outpu
```
