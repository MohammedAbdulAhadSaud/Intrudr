# Intrudr -   Advanced HTTP Request Fuzzer

---

## ⚠️ Warning
-   Writing full HTTP responses into CSV can create very large files.
-   Use responsibly and only on systems you are authorized to test.

---

## 📝 Description
Intrudr is a Python-  based HTTP request fuzzer that allows you to:

### To send request Faster than the Burpsuite-  Community-  Edition
-   Send raw HTTP requests with customizable parameters.
-   Detect and handle placeholders in requests (`^^PLACEHOLDER^^` syntax).
-   Generate parameter combinations using multiple **attack modes**.
-   Save full responses and raw sent requests for later analysis.
- It supports concurrency, user- defined values from files, default values, and flexible attack strategies.

- - - 

## 🛠 Features

-  **Raw HTTP Request Input**: Paste raw HTTP requests interactively.
-  **Parameter Detection**: Automatically detects URL and body parameters.
-  **Placeholders**: Supports custom placeholders with the `^^PLACEHOLDER^^` syntax.
-  **Attack Modes**:
  -  **Sniper**: Varies one parameter at a time.
  -  **Clusterbomb**: Cartesian product of all parameter values.
  -  **Pitchfork**: Pairwise combination of multi- value lists; single/default values are repeated.
  -  **Battering- ram**: All parameters take the same value from the first multi- value list; single/default values are repeated.
-  **Concurrency**: Uses ThreadPoolExecutor for fast requests.
-  **User- Agent Randomization**: Rotates through a list of realistic User- Agent headers.
-  **Proxy Support**: Optional HTTP/HTTPS proxy.
-  **Response Management**:
  -  Save full responses as `.txt` files.
  -  Save raw prepared requests as `.bin` files.
  -  Generate summary CSV with request/response metadata.

- - - 

## ⚙️ Installation

1. Clone the repository:

```bash
git clone https://github.com/MohammedAbdulAhadSaud/Intrudr.git
cd Intrudr
python3 intrudr-v2beta.py
```

# Usage

- Run the script:

- python3 intrudr.py

- Step- by- step:

-  Paste raw HTTP request:

```Request Ex

POST /login HTTP/1.1
Host: example.com
Content- Type: application/x- www- form- urlencoded

username=^^USER^^&password=^^PASS^^
END

```
-  Use ^^PLACEHOLDER^^ for variables you want to fuzz.

-  End input with "END"  or "..."

-  Detect parameters and placeholders:

-  Intrudr will automatically list detected parameters and placeholders.

-  Example:

Detected Parameters:
1. username = default
2. password = default

Detected Placeholders:
PH1 - > ^^USER^^
PH2 - > ^^PASS^^

-  Provide values:

-  You can provide:

- -   Single value (manual input)

- -   File input (list of values)

- -   Default/detected value

-  Select attack mode:

-  Options:

- -   Sniper

- -   Clusterbomb

- -   Pitchfork

- -   Battering- ram

-  Logic ensures:

- -   Multi- value lists in Pitchfork or Battering- ram must have the same length.

- -   Single/default parameters are automatically repeated.

-  Specify output folder:

-  Example: responses

-  Intrudr saves:

- -   Full responses (response_XXXX_*.txt)

- -   Raw sent requests (sent_raw_XXXX.bin)

- -   Summary CSV (summary.csv)

-    View summary:

-   Colored console output shows request number, status, length, time, and errors.

-   Full response can be previewed or just saved to files.

⚡ Attack Mode Details
Mode	Description
Sniper	Varies one parameter at a time, others fixed
Clusterbomb	Cartesian product of all parameter values
Pitchfork	Pairwise combination of multi-  value lists; single/default values are repeated
Battering-  ram	All parameters take the same value from the first multi-  value list; single/default repeated


# Output Structure


-   response_XXXX_*.txt: Full response text.

-   sent_raw_XXXX.bin: Prepared raw request bytes.

-   summary.csv: Summary of all requests, statuses, lengths, errors, and response previews.

# Configuration Options

-  MAX_WORKERS: Number of concurrent requests (default: 12)

-  REQUEST_TIMEOUT: Timeout per request in seconds (default: 60)

-  REQUEST_RETRIES: Number of retries for failed requests (default: 1)

-  SHOW_FULL_RESPONSE: Whether to print full response to console (capped by MAX_RESPONSE_PRINT)

-  USE_PROXY: Enable/disable proxy usage

-  PROXY_ADDR: Proxy address if enabled

-  RECORD_PREPARED_RAW: Save raw prepared requests as .bin files
