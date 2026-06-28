# generic_monitor.py - COMPLETE FIXED VERSION (ROBUST)
# Adds threading lock, deterministic text extraction, and improved fetch stability.

import json
import hashlib
import difflib
import smtplib
import os
import random
import time
import threading
import asyncio
from datetime import datetime
from email.mime.text import MIMEText
from email.header import Header
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

load_dotenv()

# Global lock to prevent duplicate concurrent monitoring cycles
_monitor_lock = threading.Lock()
_cycle_start_time = 0.0  # Track when the last cycle started

# ─── Realistic browser User-Agent pool ───────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) "
    "Gecko/20100101 Firefox/124.0",
]


# =============================================================================
# STEP 1 — FETCH: isolated in a Thread for Windows compatibility
# =============================================================================

async def _async_fetch(url: str) -> str | None:
    """Internal async logic for Playwright with improved stability."""
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                ],
            )

            context = await browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1366, "height": 768},
                locale="en-GB",
                timezone_id="Europe/London",
                java_script_enabled=True,
            )

            # Speed up: block images, fonts
            await context.route(
                "**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,otf}",
                lambda route: route.abort(),
            )

            page = await context.new_page()

            # Hide automation fingerprint
            await page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            print(f"[Playwright] Opening: {url}")
            # Faster load: wait only for DOM, then fixed 4s for React
            await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            await page.wait_for_timeout(4000)

            html = await page.content()
            
            # ISSUE 3 Fix: If content is empty/too short, wait and retry once
            if not html or len(html) < 200:
                print(f"[Playwright] ⚠️ Content empty or too short ({len(html) if html else 0} chars). Retrying in 6s...")
                await page.wait_for_timeout(6000)
                html = await page.content()

            await browser.close()
            return html

        except Exception as e:
            print(f"[Playwright] ❌ Error during fetch: {e}")
            return None


def fetch_with_playwright(url: str) -> str | None:
    """
    Sync wrapper that runs Playwright in a separate Thread.
    Critical for Streamlit on Windows to avoid NotImplementedError.
    """
    result = {"html": None}

    def run_in_thread():
        if os.name == 'nt':
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result["html"] = loop.run_until_complete(_async_fetch(url))
        except Exception as e:
            print(f"[Thread] ❌ Error: {e}")
        finally:
            loop.close()

    t = threading.Thread(target=run_in_thread)
    t.start()
    t.join(timeout=60)
    
    return result["html"]


# =============================================================================
# STEP 2 — SANITIZE: Deterministic text extraction (Fixes false alerts)
# =============================================================================

def sanitize_html(html_content: str, previous_text: str = "") -> str:
    """
    V3: Extracts job counts and job cards from BOTH main and secondary sections.
    Strategy: 
    1. Search for elements with class-based selectors.
    2. Fallback heuristic for generic div/li elements.
    3. Standardize format: Title | Type | Duration | Pay rate | Location.
    """
    import re
    soup = BeautifulSoup(html_content, "lxml")

    extracted_lines = []

    # 1. Extract Job Count Line (e.g. "3 jobs found")
    count_texts = []
    # Search for count patterns in the whole page
    for el in soup.find_all(string=re.compile(r'\d+\s+jobs?\s+found', re.I)):
        parent = el.parent
        if parent:
            count_texts.append(parent.get_text(strip=True))
    
    # 2. Extract Job Cards using Broader Selectors
    job_cards = soup.find_all(class_=re.compile(r'job-card|JobCard|job-tile|result-card', re.I))

    # 3. Fallback Heuristic
    if not job_cards:
        # Find every <div> or <li> that contains a job title word + "Type:" or "Duration:" or "Pay rate:" or "£"
        job_title_keywords = ["warehouse", "operative", "associate", "driver", "packer", "seasonal", "support"]
        for el in soup.find_all(['div', 'li']):
            text = el.get_text(" ", strip=True)
            text_lower = text.lower()
            
            # Check if it has a title word AND markers
            has_title = any(word in text_lower for word in job_title_keywords)
            has_markers = any(m in text for m in ["Type:", "Duration:", "Pay rate:", "£"])
            
            if has_title and has_markers:
                if 40 < len(text) < 500:
                    job_cards.append(el)

    # 4. Standardize Job Card Content
    # Format: "Title | Type | Duration | Pay rate | Location"
    for card in job_cards:
        # If this card contains another element that is also a 'card', 
        # we check if this one is a better container or if we should use the child.
        # Strategy: Use the one that has markers like '£' or 'Pay rate' if possible.
        has_child_card = any(child in job_cards for child in card.descendants)
        if has_child_card:
            # If the current card has the pay info but children don't, keep this one.
            # Otherwise, skip this one and let the children be processed.
            if '£' in card.get_text() and not any('£' in child.get_text() for child in card.descendants if child in job_cards):
                pass # Keep this one
            else:
                continue

        raw_text = card.get_text(" | ", strip=True)
        # Clean up
        clean_text = re.sub(r'\s*\|\s*', ' | ', raw_text)
        clean_text = re.sub(r'\s+', ' ', clean_text)
        
        parts = [p.strip() for p in clean_text.split('|') if p.strip()]
        
        # Deduplicate parts in the line
        seen_parts = []
        for p in parts:
            if p.lower() not in [sp.lower() for sp in seen_parts]:
                seen_parts.append(p)
        
        final_line = " | ".join(seen_parts)
        # Lower threshold: a valid job line should at least have a title and something else
        if len(final_line) > 15:
            extracted_lines.append(final_line)

    # Add count lines to the list
    for c in count_texts:
        if 5 < len(c) < 100: # Practical limit for a count line
            extracted_lines.append(c)

    # 5. Post-processing: Deduplicate, Sort, Join
    # Filter out known junk
    EXCLUDE_KEYWORDS = ["scam", "fraud", "unofficial", "social media", "menu", "search", "faq"]
    extracted_lines = [
        line for line in extracted_lines 
        if not any(word in line.lower() for word in EXCLUDE_KEYWORDS)
    ]
    
    # Deduplicate while preserving order, then Sort
    extracted_lines = list(dict.fromkeys(extracted_lines))
    extracted_lines.sort()
    
    result_text = "\n".join(extracted_lines)

    # 6. Validation
    if not result_text or len(result_text) < 10:
        print(f"[Sanitize] ⚠️ Extracted content too short ({len(result_text)} chars). Reverting.")
        return previous_text

    print(f"[Sanitize] Extracted {len(extracted_lines)} lines (including counts and jobs).")
    return result_text


# =============================================================================
# STEP 3 — HELPERS & EMAIL
# =============================================================================

def generate_md5_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def generate_delta_diff(old_text: str, new_text: str) -> str:
    diff = difflib.unified_diff(
        old_text.splitlines(), new_text.splitlines(),
        fromfile="previous", tofile="current", lineterm=""
    )
    return "\n".join(list(diff))


def send_email_alert(sender_email, app_password, receiver_email, url, old_text, new_text):
    """
    V3: Detailed email alerts showing job count changes and live job lists.
    """
    def get_job_count(text):
        for line in text.splitlines():
            if "job found" in line.lower() or "jobs found" in line.lower():
                return line.strip()
        return "0 jobs found"

    prev_count = get_job_count(old_text)
    curr_count = get_job_count(new_text)

    # Bullet points for live jobs (exclude the count line itself)
    live_jobs = []
    for line in new_text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Skip the count line
        if "job found" in line.lower() or "jobs found" in line.lower():
            continue
        live_jobs.append(f"• {line}")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    divider = "─────────────────────"
    msg_content = (
        f"⚡ CHANGE DETECTED on Amazon Jobs UK\n\n"
        f"Previous: {prev_count}\n"
        f"Current: {curr_count}\n\n"
        f"📋 CURRENT LIVE JOBS:\n"
        f"{divider}\n"
        f"{chr(10).join(live_jobs) if live_jobs else 'No specific job details found.'}\n"
        f"{divider}\n\n"
        f"🔗 View jobs: {url}\n"
        f"Time: {timestamp}"
    )

    msg = MIMEText(msg_content, "plain", "utf-8")
    msg["Subject"] = Header(f"🔔 Amazon Jobs Changed ({curr_count})", "utf-8")
    msg["From"]    = f"WebMonitorBot <{sender_email}>"
    msg["To"]      = receiver_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(sender_email, app_password)
            server.sendmail(sender_email, [receiver_email], msg.as_string())
        print(f"[Email] ✅ Detailed alert sent to {receiver_email}")
        return True
    except Exception as e:
        print(f"[Email] ❌ Error: {e}")
        return False


# =============================================================================
# STEP 4 — MAIN CYCLE (With Lock & Robust Error Handling)
# =============================================================================

def run_monitoring_cycle():
    """Sync function called by Streamlit. Prevents concurrent duplicate runs."""
    global _cycle_start_time
    
    # ISSUE 2 Fix: Lock Timeout Safety
    # If lock is held but it's been more than 120s, force release it.
    if _monitor_lock.locked():
        elapsed = time.time() - _cycle_start_time
        if elapsed > 120:
            print(f"[Monitor] ⚠️ Lock held for {elapsed:.1f}s (>120s). Force-releasing.")
            try:
                _monitor_lock.release()
            except RuntimeError:
                pass # Already released

    if not _monitor_lock.acquire(blocking=False):
        print("[Monitor] Already running, skipping duplicate cycle.")
        return

    _cycle_start_time = time.time()

    try:
        try:
            with open("monitored_pages.json", "r") as f:
                monitored_pages = json.load(f)
        except Exception as e:
            print(f"[Config] ❌ Load error: {e}")
            return

        sender_email   = os.getenv("SENDER_EMAIL")
        app_password   = os.getenv("APP_PASSWORD")
        receiver_email = os.getenv("RECEIVER_EMAIL")

        for url, data in monitored_pages.items():
            print(f"\n[Monitor] Checking: {url}")
            
            # Polite delay
            time.sleep(random.uniform(3, 7))

            html_content = fetch_with_playwright(url)

            # CRITICAL: If fetch fails, skip this URL to avoid wiping baseline or false alerts
            if not html_content:
                data["status"] = "Connection Error / Timeout"
                print(f"[Monitor] ⚠️ Skipping {url} due to fetch error.")
                continue

            sanitized_text = sanitize_html(html_content, data.get("last_sanitized_text", ""))
            current_hash   = generate_md5_hash(sanitized_text)

            if not data.get("baseline_hash"):
                data["baseline_hash"] = current_hash
                data["last_sanitized_text"] = sanitized_text
                data["status"] = "Healthy / Monitoring"
                print("[Monitor] ✅ Baseline set.")
            elif current_hash != data["baseline_hash"]:
                print("[Monitor] ⚡ CHANGE DETECTED!")
                diff_text = generate_delta_diff(data.get("last_sanitized_text", ""), sanitized_text)
                
                if sender_email and app_password and receiver_email:
                    send_email_alert(sender_email, app_password, receiver_email, url, data.get("last_sanitized_text", ""), sanitized_text)

                data["baseline_hash"] = current_hash
                data["last_sanitized_text"] = sanitized_text
                data["status"] = "Changes Detected ⚡"
            else:
                data["status"] = "Healthy / Monitoring"
                print("[Monitor] ✅ No changes detected.")

        # Save updated state
        try:
            with open("monitored_pages.json", "w") as f:
                json.dump(monitored_pages, f, indent=4)
            print("[Monitor] State saved successfully.")
        except Exception as e:
            print(f"[Monitor] ❌ Save error: {e}")

    finally:
        _monitor_lock.release()
