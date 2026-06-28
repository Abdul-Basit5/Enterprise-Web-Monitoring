# 🛡️ Enterprise Web Monitor

A powerful, enterprise-grade web page monitoring system built with **Python**, **Streamlit**, and **Playwright**. It automatically detects content changes on target web pages and sends instant **email alerts** — all through an elegant real-time dashboard.

---

## 📋 Table of Contents

1. [Project Overview](#-project-overview)
2. [Features](#-features)
3. [Architecture & File Structure](#-architecture--file-structure)
4. [Technology Stack](#-technology-stack)
5. [Core Concepts Explained](#-core-concepts-explained)
   - [Headless Browser Automation (Playwright)](#1-headless-browser-automation--playwright)
   - [Anti-Bot Evasion Techniques](#2-anti-bot-evasion-techniques)
   - [HTML Sanitization (BeautifulSoup)](#3-html-sanitization--beautifulsoup)
   - [Content Fingerprinting (MD5 Hashing)](#4-content-fingerprinting--md5-hashing)
   - [Change Detection (Difflib)](#5-change-detection--difflib)
   - [Email Alerting (SMTP / Gmail)](#6-email-alerting--smtp--gmail)
   - [Concurrency & Thread Safety](#7-concurrency--thread-safety)
   - [Windows Async Loop Compatibility](#8-windows-async-loop-compatibility)
   - [Streamlit Dashboard](#9-streamlit-dashboard)
   - [Auto-Refresh (streamlit-autorefresh)](#10-auto-refresh--streamlit-autorefresh)
   - [Session State Management](#11-session-state-management)
   - [Environment Variables (.env)](#12-environment-variables--env)
   - [JSON Persistence](#13-json-persistence)
6. [How the Monitoring Pipeline Works](#-how-the-monitoring-pipeline-works)
7. [Setup & Installation](#-setup--installation)
8. [Configuration](#-configuration)
9. [Running the Application](#-running-the-application)
10. [Security Best Practices](#-security-best-practices)
11. [Troubleshooting](#-troubleshooting)

---

## 🎯 Project Overview

Enterprise Web Monitor was purpose-built to watch dynamic, JavaScript-rendered web pages (such as job boards, e-commerce listings, and live portals) for changes. Unlike simple `requests`-based scrapers that only see raw HTML, this system launches a real Chromium browser behind the scenes to wait for fully rendered page content before comparing it.

**Primary use case in this project:** Monitoring [Amazon Jobs UK](https://www.jobsatamazon.co.uk/app#/jobSearch) for new warehouse and operative listings, sending an instant email alert when jobs appear or disappear.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🌐 **JavaScript-aware Fetching** | Uses Playwright to render fully dynamic pages just like a real browser |
| 🤖 **Anti-Bot Evasion** | Randomised User-Agents, hidden `webdriver` flag, blocked telemetry assets |
| 🧹 **Intelligent HTML Sanitisation** | Extracts only meaningful job data — not timestamps or ads — to avoid false alerts |
| 🔑 **MD5 Content Fingerprinting** | Hashes sanitised text and compares fingerprints to detect real changes |
| 📧 **Instant Email Alerts** | Sends a structured Gmail alert listing all live jobs the moment a change is found |
| 🔄 **Configurable Auto-Refresh** | Poll interval slider (30–300 s) drives automatic dashboard refresh |
| 🔒 **Thread-Safe Monitoring** | A global threading lock prevents duplicate concurrent monitoring cycles |
| 🗂️ **JSON State Persistence** | Baseline hashes and last sanitised text survive app restarts |
| 🎛️ **Live Dashboard** | Real-time 3-column status grid with colour-coded health indicators |
| ➕ **Dynamic Target Management** | Add/remove monitoring URLs on the fly through the sidebar |

---

## 🏗️ Architecture & File Structure

```
Enterprise_Web_Monitor/
│
├── app.py                  # Streamlit UI layer — dashboard, sidebar controls, engine trigger
├── generic_monitor.py      # Core monitoring engine — fetch, sanitise, hash, diff, alert
├── monitored_pages.json    # Persistent state — URLs, statuses, baseline hashes
├── config.json             # App configuration (e.g. proxy tier settings)
├── requirements.txt        # Python dependency list
├── .env                    # Secret credentials (NOT committed to version control)
└── README.md               # This file
```

### Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        app.py (UI)                          │
│  Sidebar → Add URL → monitored_pages.json                   │
│  Start Engine → calls run_monitoring_cycle() each refresh   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                 generic_monitor.py (Engine)                  │
│                                                             │
│  1. fetch_with_playwright()  ── Playwright (headless Chrome)│
│  2. sanitize_html()          ── BeautifulSoup / Regex       │
│  3. generate_md5_hash()      ── hashlib                     │
│  4. Compare hash vs baseline                                │
│  5. generate_delta_diff()    ── difflib (if changed)        │
│  6. send_email_alert()       ── smtplib / Gmail SMTP        │
│  7. Save updated state       ── monitored_pages.json        │
└─────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Technology Stack

| Library | Version (latest) | Role |
|---|---|---|
| `streamlit` | ≥1.35 | Web dashboard / UI framework |
| `playwright` | ≥1.44 | Headless Chromium browser for JS-rendered pages |
| `beautifulsoup4` | ≥4.12 | HTML parsing and structured data extraction |
| `lxml` | ≥5.0 | High-performance HTML parser backend for BeautifulSoup |
| `streamlit-autorefresh` | ≥1.0 | Automatic page refresh on a configurable interval |
| `python-dotenv` | ≥1.0 | Load secrets from `.env` file into environment variables |
| **stdlib: `hashlib`** | built-in | MD5 content fingerprinting |
| **stdlib: `difflib`** | built-in | Unified diff generation between old and new content |
| **stdlib: `smtplib`** | built-in | Sending email over Gmail's SMTP SSL server |
| **stdlib: `threading`** | built-in | Thread lock to prevent duplicate monitoring cycles |
| **stdlib: `asyncio`** | built-in | Async event loop for Playwright coroutines |
| **stdlib: `json`** | built-in | Reading and writing persistent state files |

---

## 🧠 Core Concepts Explained

### 1. Headless Browser Automation — Playwright

**File:** `generic_monitor.py` → `_async_fetch()` / `fetch_with_playwright()`

**Why it's needed:**  
Modern websites (like Amazon Jobs) are Single-Page Applications (SPAs). They load an empty HTML shell and then use JavaScript to fetch and render job listings. A plain `requests.get()` call returns *before* that JavaScript runs, so you'd receive an empty page.

**How Playwright solves it:**  
Playwright launches a real Chromium browser (invisible, "headless" mode), navigates to the URL, and waits for the DOM to fully load plus an extra 4 seconds for React/JS rendering. Only then does it capture the full HTML.

```python
browser = await p.chromium.launch(headless=True, args=["--no-sandbox", ...])
page = await context.new_page()
await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
await page.wait_for_timeout(4000)   # Wait for React/SPA to populate the DOM
html = await page.content()         # Retrieve the fully rendered HTML
```

**Key arguments:**
- `headless=True` — runs the browser with no visible window, suitable for servers
- `wait_until="domcontentloaded"` — starts the 4s wait as soon as the base HTML is parsed
- `timeout=45_000` — maximum 45 seconds before giving up
- `--no-sandbox` — required in many server/container environments

---

### 2. Anti-Bot Evasion Techniques

**File:** `generic_monitor.py` → `_async_fetch()`

Websites detect and block automated scrapers using several signals. This project counters them:

| Technique | Code | What it defeats |
|---|---|---|
| **Random User-Agent** | `random.choice(USER_AGENTS)` | Browser fingerprint detection |
| **Hidden `webdriver` flag** | `add_init_script(...)` | `navigator.webdriver === true` bot check |
| **Realistic viewport** | `viewport={"width": 1366, "height": 768}` | Headless browser size detection |
| **Locale & Timezone** | `locale="en-GB"`, `timezone_id="Europe/London"` | Geographic anomaly detection |
| **Disabled automation flag** | `--disable-blink-features=AutomationControlled` | Blink-level bot flag |
| **Blocked assets** | `context.route(...)` to abort images/fonts | Faster load; also reduces telemetry |
| **Polite delay** | `time.sleep(random.uniform(3, 7))` | Rate-limit triggers |

The `webdriver` patch is especially important:
```python
await page.add_init_script(
    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
)
```
This runs *before* any page JavaScript, making the browser indistinguishable from a human's.

---

### 3. HTML Sanitisation — BeautifulSoup

**File:** `generic_monitor.py` → `sanitize_html()`

**Why it's needed:**  
Raw HTML contains: timestamps, session tokens, ad banners, CSRF tokens, and other elements that change on *every single page load* — even when no real content has changed. Comparing raw HTML directly causes thousands of false alerts.

**The sanitisation strategy:**

1. **Parse HTML** with `BeautifulSoup(html, "lxml")` — `lxml` is used as the parser for speed and robustness.
2. **Find job count** — searches the page for text matching `\d+ jobs? found` using a regex.
3. **Find job cards** — looks for elements whose CSS class matches `job-card|JobCard|job-tile|result-card`.
4. **Fallback heuristic** — if no class-based cards are found, scans every `<div>` and `<li>` for element text containing job-related keywords (e.g., "warehouse", "operative") plus field markers ("Pay rate:", "£").
5. **Standardise format** — represents each job as a pipe-delimited string: `Title | Type | Duration | Pay rate | Location`
6. **Deduplicate & sort** — ensures the output is always in the same order, preventing false positives from reordering.
7. **Exclude noise** — strips lines containing known junk words ("scam", "menu", "faq", etc.).
8. **Validation** — if the result is too short (< 10 chars), it reverts to the previous known text to avoid wiping a valid baseline from a temporary page error.

---

### 4. Content Fingerprinting — MD5 Hashing

**File:** `generic_monitor.py` → `generate_md5_hash()`

```python
def generate_md5_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()
```

**Concept:** Instead of comparing full text strings on every cycle (expensive), we compute a 32-character MD5 hash of the sanitised text. Two identical texts will always produce the same hash. If hashes differ, the content has changed.

- The first cycle's hash becomes the **baseline fingerprint**.
- Each subsequent cycle computes a **current hash** and compares it to the baseline.
- Only an MD5 mismatch triggers the diff and email alert.
- The baseline hash is displayed (first 8 chars) on each monitoring card in the UI.

---

### 5. Change Detection — Difflib

**File:** `generic_monitor.py` → `generate_delta_diff()`

```python
def generate_delta_diff(old_text: str, new_text: str) -> str:
    diff = difflib.unified_diff(
        old_text.splitlines(), new_text.splitlines(),
        fromfile="previous", tofile="current", lineterm=""
    )
    return "\n".join(list(diff))
```

Python's built-in `difflib` generates a **unified diff** — the same format used by `git diff`. Lines prefixed with `+` are additions, lines with `-` are deletions, and unchanged lines have a space prefix. This diff is computed when a change is detected, ready for inclusion in alert emails or future logging.

---

### 6. Email Alerting — SMTP / Gmail

**File:** `generic_monitor.py` → `send_email_alert()`

When a change is detected, an email is sent via **Gmail's SMTP SSL** server on port 465.

```python
with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
    server.login(sender_email, app_password)
    server.sendmail(sender_email, [receiver_email], msg.as_string())
```

**Key concepts:**
- **`smtplib.SMTP_SSL`** — establishes a direct SSL-encrypted connection (no STARTTLS needed)
- **Gmail App Password** — Google no longer allows your regular account password for third-party apps. You must generate a 16-character App Password from your Google Account security settings
- **`MIMEText`** — constructs a structured email message body with UTF-8 encoding so special characters (£, ⚡, etc.) display correctly
- **`email.header.Header`** — properly encodes the email subject line with UTF-8

The email body includes:
- Previous vs. current job count
- A bullet-point list of all currently live jobs
- A direct link to the monitored page
- The timestamp of detection

---

### 7. Concurrency & Thread Safety

**File:** `generic_monitor.py` → `run_monitoring_cycle()` and `fetch_with_playwright()`

**Problem:** Streamlit reruns the entire Python script on every interaction and on every auto-refresh. Without protection, this could trigger multiple simultaneous monitoring cycles, causing corrupted state files and duplicate emails.

**Solution — Threading Lock:**
```python
_monitor_lock = threading.Lock()

if not _monitor_lock.acquire(blocking=False):
    print("[Monitor] Already running, skipping duplicate cycle.")
    return
```

- `blocking=False` — tries to acquire the lock without waiting. If it's already held, the new cycle exits immediately.
- A **timeout safety** mechanism force-releases the lock if it has been held for more than 120 seconds (handles crash scenarios).

**Playwright runs in a dedicated thread:**
```python
t = threading.Thread(target=run_in_thread)
t.start()
t.join(timeout=60)
```
This isolates the async event loop from Streamlit's main thread and sets a hard 60-second deadline on each page fetch.

---

### 8. Windows Async Loop Compatibility

**File:** `generic_monitor.py` → `fetch_with_playwright()` → `run_in_thread()`

```python
if os.name == 'nt':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
```

**Why this is critical:** On Windows, the default event loop policy (`SelectorEventLoop`) does not support subprocess-based operations — and Playwright's Chromium subprocess is exactly that. The `WindowsProactorEventLoopPolicy` uses an IOCP (I/O Completion Port) based loop that supports this. Without it, you get a `NotImplementedError`. This line is a mandatory Windows fix placed inside the monitoring thread.

---

### 9. Streamlit Dashboard

**File:** `app.py`

Streamlit converts plain Python scripts into interactive web applications with zero HTML/CSS/JS knowledge required. Key Streamlit APIs used:

| API | Purpose |
|---|---|
| `st.set_page_config()` | Sets browser tab title and page layout to "wide" |
| `st.sidebar.*` | Renders controls in the collapsible left panel |
| `st.slider()` | Creates an interactive slider for the poll interval |
| `st.text_input()` + `st.button()` | URL input field and "Add Target" button |
| `st.columns(3)` | Creates a responsive 3-column grid for monitor cards |
| `st.markdown(..., unsafe_allow_html=True)` | Renders custom HTML/CSS cards with colour-coded statuses |
| `st.toast()` | Shows a temporary notification message |
| `st.rerun()` | Forces the full script to re-execute, refreshing the UI |
| `st.expander()` | Collapsible section for notification settings |
| `st.session_state` | Persists the engine running state across reruns |

**Custom CSS** is injected directly via `st.markdown()` to style the status indicators:
```css
.status-healthy { color: #28a745; font-weight: bold; }
.status-changes { color: #fd7e14; font-weight: bold; }
.status-error   { color: #dc3545; font-weight: bold; }
```

---

### 10. Auto-Refresh — streamlit-autorefresh

**File:** `app.py`

```python
from streamlit_autorefresh import st_autorefresh
st_autorefresh(interval=poll_frequency * 1000, key="data_refresh")
```

`streamlit-autorefresh` is a Streamlit component that injects a JavaScript timer into the browser page. After the specified `interval` (in milliseconds), it triggers a Streamlit rerun — causing the monitoring cycle to execute again without any user interaction. The `key` parameter ensures only one timer is active. The interval is directly controlled by the sidebar slider (30–300 seconds → 30,000–300,000 ms).

---

### 11. Session State Management

**File:** `app.py`

```python
if 'monitor_running' not in st.session_state:
    st.session_state.monitor_running = False
```

Streamlit reruns the entire script from top to bottom on every interaction. Normally, all variables would be reset to their defaults. `st.session_state` is a dictionary-like object that **persists values across reruns** within the same browser session. Here it stores whether the monitoring engine is running or stopped, so clicking "Stop" actually stops future cycles even as the page refreshes.

---

### 12. Environment Variables — .env

**File:** `.env` loaded by `python-dotenv`

```
SENDER_EMAIL=you@gmail.com
APP_PASSWORD=xxxx xxxx xxxx xxxx
RECEIVER_EMAIL=recipient@gmail.com
```

```python
from dotenv import load_dotenv
load_dotenv()
sender_email = os.getenv("SENDER_EMAIL")
```

**Why `.env` files?**  
Hard-coding credentials in source code is a critical security risk — anyone who reads your code (or its Git history) gains access to your email account. The `.env` pattern separates secrets from code:
- `python-dotenv` reads the `.env` file and loads each `KEY=VALUE` pair into the OS environment.
- `os.getenv()` reads them at runtime.
- The `.env` file should **always** be listed in `.gitignore`.

> ⚠️ **Gmail App Password:** You must enable 2-Factor Authentication on your Google account and generate an App Password at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords). Your regular Gmail password will not work.

---

### 13. JSON Persistence

**Files:** `monitored_pages.json`, `config.json`

The application has no database. State is stored in two plain JSON files:

**`monitored_pages.json`** — the live operational state store:
```json
{
    "https://www.jobsatamazon.co.uk/app#/jobSearch": {
        "status": "Healthy / Monitoring",
        "baseline_hash": "fb670e32b9a19fc719d7bf7e932f713d",
        "last_sanitized_text": "1 job found\nWarehouse Operative | ..."
    }
}
```

**`config.json`** — application-level configuration (e.g., proxy settings):
```json
{"proxy_tier2": ""}
```

`load_json()` in `app.py` handles missing files and empty/corrupt JSON gracefully, returning `{}` instead of crashing. `save_json()` always writes with `indent=4` for human-readable formatting.

---

## 🔄 How the Monitoring Pipeline Works

Here is the complete lifecycle of one monitoring cycle, step by step:

```
START: st_autorefresh triggers a Streamlit rerun
  │
  ├─ [app.py] Is st.session_state.monitor_running == True?
  │     └─ No  → Skip. Nothing happens.
  │     └─ Yes → Call run_monitoring_cycle()
  │
  ├─ [generic_monitor.py] Acquire _monitor_lock
  │     └─ Lock already held → Exit immediately (duplicate protection)
  │
  ├─ For each URL in monitored_pages.json:
  │
  │   ├─ 1. WAIT: random.uniform(3, 7) seconds (polite delay)
  │   │
  │   ├─ 2. FETCH: fetch_with_playwright(url)
  │   │      └─ Launch headless Chromium in a new thread
  │   │      └─ Navigate, wait 4s for JS rendering
  │   │      └─ Return full rendered HTML
  │   │      └─ On failure → set status = "Connection Error" and skip
  │   │
  │   ├─ 3. SANITISE: sanitize_html(html, previous_text)
  │   │      └─ BeautifulSoup parses HTML
  │   │      └─ Extract job count + job cards
  │   │      └─ Deduplicate, sort, return clean text
  │   │
  │   ├─ 4. HASH: generate_md5_hash(sanitised_text)
  │   │
  │   ├─ 5. COMPARE:
  │   │      ├─ No baseline yet → Save hash as baseline. Status = "Healthy / Monitoring"
  │   │      ├─ Hash == baseline → No change. Status = "Healthy / Monitoring"
  │   │      └─ Hash != baseline → CHANGE DETECTED ⚡
  │   │             ├─ generate_delta_diff(old, new)
  │   │             ├─ send_email_alert(...)
  │   │             ├─ Update baseline_hash & last_sanitized_text
  │   │             └─ Status = "Changes Detected ⚡"
  │   │
  │   └─ Save updated state to monitored_pages.json
  │
  ├─ Release _monitor_lock
  │
  └─ [app.py] st.rerun() → Dashboard refreshes with new statuses
```

---

## ⚙️ Setup & Installation

### Prerequisites

- Python 3.10 or higher
- Windows, macOS, or Linux
- A Gmail account with 2FA enabled

### Step 1 — Clone / Download the Project

```bash
git clone https://github.com/your-username/Enterprise_Web_Monitor.git
cd Enterprise_Web_Monitor
```

### Step 2 — Create a Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### Step 3 — Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — Install Playwright Browsers

This is a one-time step that downloads the Chromium browser binary:

```bash
playwright install chromium
```

### Step 5 — Configure Credentials

Create (or edit) the `.env` file in the project root:

```
SENDER_EMAIL=your-gmail@gmail.com
APP_PASSWORD=xxxx xxxx xxxx xxxx
RECEIVER_EMAIL=recipient@gmail.com
```

> **Getting a Gmail App Password:**
> 1. Go to [myaccount.google.com](https://myaccount.google.com)
> 2. Security → 2-Step Verification (must be ON)
> 3. Security → App passwords
> 4. Select "Mail" and your device → Generate
> 5. Copy the 16-character password into `.env`

---

## 🔧 Configuration

| File | Key | Description |
|---|---|---|
| `.env` | `SENDER_EMAIL` | Gmail address that sends the alert emails |
| `.env` | `APP_PASSWORD` | 16-character Gmail App Password (NOT your login password) |
| `.env` | `RECEIVER_EMAIL` | Email address that receives alerts |
| `config.json` | `proxy_tier2` | Optional proxy URL for Tier-2 scraping (leave blank if unused) |
| Sidebar Slider | Poll Frequency | How often the dashboard auto-refreshes and runs a monitoring cycle (30–300 seconds) |

---

## 🚀 Running the Application

```bash
streamlit run app.py
```

The dashboard opens automatically at **http://localhost:8501**.

**First-time steps in the UI:**
1. In the sidebar, paste a URL into "Add Monitoring Target URL" and click **Add Target**
2. Click **▶️ Start Engine** to begin monitoring
3. The first cycle sets the baseline. Subsequent cycles compare against it.
4. When a change is detected, your inbox receives an alert within seconds.

---

## 🔒 Security Best Practices

- ✅ **Never commit `.env`** — add it to `.gitignore` immediately
- ✅ **Use Gmail App Passwords** — never store your actual Gmail password
- ✅ **Restrict receiver email** — only send alerts to addresses you control
- ✅ **Rate-limit fetches** — the built-in 3–7 second polite delay respects target servers
- ✅ **Review monitored_pages.json** — it stores sanitised page text; avoid monitoring pages with personal data

---

## 🛠️ Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `NotImplementedError` on Windows | Missing `WindowsProactorEventLoopPolicy` | Ensure `generic_monitor.py` lines 104–108 are present |
| `Connection Error / Timeout` in dashboard | Target site blocked the request or timed out | Check your network; the site may require a proxy |
| False alerts on first few runs | Baseline not yet stable | Stop and restart the engine to reset the baseline |
| Emails not sending | Wrong App Password or 2FA not enabled | Regenerate App Password at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) |
| Dashboard not auto-refreshing | `streamlit-autorefresh` not installed | Run `pip install streamlit-autorefresh` |
| Extracted content always empty | CSS selectors changed on target site | Update class patterns in `sanitize_html()` in `generic_monitor.py` |
| `playwright install` not found | Playwright not installed | Run `pip install playwright` then `playwright install chromium` |

---

## 📄 License

This project is open-source and free to use for personal and educational purposes.

---

*Built with ❤️ using Python, Streamlit, and Playwright.*
