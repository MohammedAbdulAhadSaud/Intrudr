# Intrudr — HTTP request variation sender (VERSION2 BETA)

> **Quick:** an interactive tool to paste a raw HTTP request, auto-detect parameters/placeholders, generate value combos (sniper/clusterbomb/pitchfork/battering-ram), send requests concurrently, and save responses to disk for analysis.

---

## Table of contents
- [What it is](#what-it-is)
- [Features](#features)
- [Warning / Ethics](#warning--ethics)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick start](#quick-start)
- [How it works (interactive flow)](#how-it-works-interactive-flow)
- [Attack modes explained](#attack-modes-explained)
- [Configuration / tuning](#configuration--tuning)
- [Output files](#output-files)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License & Author](#license--author)

---

## What it is
`Intrudr` is a small command-line Python tool to take a raw HTTP request (paste as plaintext), detect query/form parameters and `^^...^^` placeholders, let you provide values (manually or from files), generate attack/test combinations, send those requests concurrently, and save responses and a CSV summary.

It’s meant for testing APIs, debugging and defensive/security testing workflows where generating many variants of a request is useful.

---

## Features
- Paste raw HTTP request (request line + headers + optional body)
- Auto-detect URL/query/form parameters and wrapped placeholders `^^...^^`
- Replace placeholders with values from files or manual input
- Multiple attack modes: Sniper, Clusterbomb (Cartesian), Pitchfork, Battering-ram
- Concurrent sending with `ThreadPoolExecutor` and ordered result printing
- Saves full responses to files and a `summary.csv`
- Randomized `User-Agent` selection and optional proxy support
- Saves "prepared raw" sent requests (binary) for forensic analysis

---

## Warning / Ethics
**Use only on systems you own or where you have explicit permission to test.**  
This tool can generate many requests quickly; misusing it can be illegal, disruptive, or cause service outages. The author and contributors are not responsible for misuse.

Also note: writing full responses into CSV can create very large files. The script prints a warning at the top.

---

## Requirements
- Python 3.8+ (script uses modern `concurrent.futures` features)
- pip:
  - `requests`
  - `colorama`

Install dependencies:
```bash

pip install -r requirements.txt
# or
pip install requests colorama

```
---

# Installation

## Clone the repo and make the script executable:
```bash
git clone https://github.com/MohammedAbdulAhadSaud/Intrudr.git
cd Intrudr
chmod +x intrudr.py    # or run with python3 intrudr.py
```
