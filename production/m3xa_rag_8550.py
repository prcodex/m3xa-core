# ═══════════════════════════════════════════════════════════════════════════════
# METHODOLOGY 1 - Original M3xA Search Algorithm (Backup Jan 7, 2026)
# ═══════════════════════════════════════════════════════════════════════════════
# 
# SEARCH STRATEGY:
#   - STRICT 24h window (no exceptions)
#   - Hybrid scoring: 40% time-weighted + 60% semantic
#   - Time decay: exponential with 48h half-life
#   - Single-pass search (no tiered expansion)
# 
# FORMULA:
#   hybrid_score = (time_weighted_score * 0.4) + (semantic_score * 10 * 0.6)
#   time_weighted_score = ai_score * time_decay
#   time_decay = exp(-0.693/48 * age_hours)  # min 0.1
# 
# TO RESTORE: cp argus_rag_8550_METHODOLOGY_1.py argus_rag_8550.py
# ═══════════════════════════════════════════════════════════════════════════════

import sys
from flask import Flask, jsonify, render_template_string, request, Response, stream_with_context
import sqlite3
import lancedb
# ─── Singleton LanceDB connection (RAG) ─────────────────────────────────────
# Each lancedb.connect() creates a fresh Rust-level fragment cache → memory
# balloon over time. One shared connection = one bounded fragment cache.
import threading as _rag_threading
_rag_db_singleton = None
_rag_db_lock = _rag_threading.Lock()

def _get_rag_db():
    """Return shared LanceDB connection for the RAG. Bounded memory footprint."""
    global _rag_db_singleton
    if _rag_db_singleton is None:
        with _rag_db_lock:
            if _rag_db_singleton is None:
                _rag_db_singleton = lancedb.connect('/home/ubuntu/m3xa/lancedb_clean')
    return _rag_db_singleton
# ─────────────────────────────────────────────────────────────────────────────
import json
import anthropic
import re
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
import math
import os
from overnight_weighting import is_overnight_query, get_overnight_weight, get_overnight_windows
from time_range_agent import detect_time_range
from query_understanding_agent import understand_query, calculate_boost, should_exclude
from author_detection import detect_author_in_query, filter_by_author, IMPORTANT_AUTHORS
from economic_calendar_context import should_include_calendar, get_economic_context, format_us_calendar_tables_utc3
from poll_context import should_include_polls, get_poll_context
from prompt_boost import build_boost_prompt
from response_evaluator import ResponseEvaluator, CONFIG as EVAL_CONFIG

# ═══════════════════════════════════════════════════════════════════════════
# SOUL FILE — M3xA self-knowledge (hot-reloadable, 5-min cache)
# ═══════════════════════════════════════════════════════════════════════════
_SOUL_PATHS = {
    'global': '/home/ubuntu/argus/config/soul_global.md',
    'brazil': '/home/ubuntu/argus/config/soul_brazil.md',
}
_soul_caches = {
    'global': {'text': '', 'mtime': 0, 'loaded_at': 0},
    'brazil': {'text': '', 'mtime': 0, 'loaded_at': 0},
}

def _load_soul(variant='global'):
    """Load soul file with 5-minute cache. variant = 'global' or 'brazil'."""
    import time as _st, os as _so
    path = _SOUL_PATHS.get(variant, _SOUL_PATHS['global'])
    cache = _soul_caches.setdefault(variant, {'text': '', 'mtime': 0, 'loaded_at': 0})
    now = _st.time()
    try:
        mtime = _so.path.getmtime(path)
    except OSError:
        return cache['text']
    if cache['text'] and (now - cache['loaded_at']) < 300 and mtime == cache['mtime']:
        return cache['text']
    try:
        with open(path, 'r') as f:
            txt = f.read().strip()
        cache['text'] = txt
        cache['mtime'] = mtime
        cache['loaded_at'] = now
        print(f"[Soul] Loaded {variant} soul ({len(txt)} chars, mtime={mtime})")
        return txt
    except Exception as e:
        print(f"[Soul] Failed to load {variant}: {e}")
        return cache['text']


# Polymarket Universal Agent (Feb 2026) - Iran, Brazil, Fed, Russia-Ukraine
sys.path.insert(0, '/home/ubuntu/argus/scripts')
try:
    from polymarket_agent import (
        detect_topics as pm_detect_topics,
        get_context_for_query as pm_get_context_for_query,
        get_live_context as pm_get_live_context,
        get_topic_history as pm_get_topic_history,
        run_all_snapshots as pm_run_all_snapshots,
        get_latest_snapshot as pm_get_latest_snapshot,
        TOPICS as PM_TOPICS,
        DB_PATH as PM_DB_PATH,
    )
    POLYMARKET_AVAILABLE = True
    print("Polymarket Universal Agent enabled (Iran, Brazil, Fed, Russia-Ukraine)")
except ImportError as e:
    POLYMARKET_AVAILABLE = False

# Markets Agent (Feb 2026) - real-time price context for every query
try:
    from markets_agent import get_live_market_context as ma_get_live_market_context
    MARKETS_AGENT_AVAILABLE = True
    print("Markets Agent enabled - live price context for all queries")
except ImportError as e:
    MARKETS_AGENT_AVAILABLE = False
    print(f"Markets Agent not available: {e}")
    print(f"Polymarket Agent not available: {e}")

# Agent Central Hub (Feb 2026) - orchestrates all context agents
try:
    import agent_hub
    AGENT_HUB_AVAILABLE = True
    print("Agent Hub enabled - centralized context orchestration")
except ImportError as e:
    AGENT_HUB_AVAILABLE = False
    print(f"Agent Hub not available: {e}")

import numpy as np


# ═══════════════════════════════════════════════════════════════════
# INSTITUTION BOOST — keyword fallback when top results miss a named source
# ═══════════════════════════════════════════════════════════════════
_INSTITUTION_KEYWORDS = {
    'jpmorgan':   ['JPMorgan', 'JP Morgan', 'Jamie Dimon', 'Gaiani'],
    'bradesco':   ['Bradesco', 'Honorato', 'Bradesco BBI'],
    'goldman':    ['Goldman Sachs', 'Goldman', 'GS Research'],
    'itau':       ['Itaú', 'Itau', 'Mario Mesquita', 'Mesquita'],
    'xp':         ['XP Investimentos', 'XP Macro', 'XP Análise', 'XP '],
    'btg':        ['BTG Pactual', 'BTG'],
    'ubs':        ['UBS'],
    'santander':  ['Santander'],
    'citi':       ['Citibank', 'Citi ', 'Citigroup'],
    'barclays':   ['Barclays'],
    'bofa':       ['Bank of America', 'BofA', 'Merrill'],
    'hsbc':       ['HSBC'],
    'apollo':     ['Apollo', 'Torsten Slok'],
    'gavekal':    ['Gavekal'],
    'rosenberg':  ['Rosenberg'],
    'vital':      ['Vital Knowledge'],
    'donnelly':   ['Brent Donnelly', 'Spectra', 'Donnelly'],
    'tonyp':      ['Tony Pasquariello', 'Tony P', 'Pasquariello', 'Topline', 'Tactical Flow'],
    'professor_jiang': ['Professor Jiang', 'Prof Jiang', 'Predictive History', 'professorjiang'],
    'glenn_diesen': ['Glenn Diesen', 'Diesen'],
    'triggernometry': ['Triggernometry', 'Triggeronometry'],
    'conflicted': ['Conflicted podcast', 'Aimen Dean'],
    'foreign_policy_live': ['Foreign Policy Live', 'Foreign Policy podcast'],
    'ian_bremmer': ['Ian Bremmer', 'Bremmer', 'GZERO', 'GZero World'],
}

# Direct source usernames — articles FROM the institution itself
_INSTITUTION_USERNAMES = {
    'jpmorgan':   ['jpmorgan'],
    'bradesco':   ['bradesco'],
    'goldman':    ['gs_research', 'gs_markets', 'goldman_drv', 'codex_goldman', 'codex_goldman_research',
                   'codex_gs_macro_economics_research', 'codex_gs_macro_markets_research',
                   'codex_goldman_sachs', 'codex_gs_rates_research', 'codex_gs_rates',
                   'codex_gs_top_of_mind_nathan', 'codex_gs_top_of_mind_natha'],
    'itau':       ['itau_us', 'itau_mexico', 'itau_china', 'codex_itau_politico', 'itau_macro'],
    'xp':         ['codex_xp_macro_strategy', 'xp_newsclipping', 'xp_analise_politica'],
    'btg':        ['btg_pactual'],
    'ubs':        ['codex_ubs'],
    'apollo':     ['codex_torsten'],
    'gavekal':    ['codex_gavekal', 'Gavekal_drv', 'gavekal_drv', 'Gavekalresearch_drv',
                   'codex_gavekal_research_joe_studwell', 'codex_gavekal_research_lou',
                   'codex_gavekal_research_louis_vincent'],
    'rosenberg':  ['codex_rosenberg'],
    'vital':      ['vital_knowledge'],
    'donnelly':   ['donnelly_brent', 'brentdonnelly', 'codex_brent_donnelly',
                   'codex_spectra_markets_brent_donnelly'],
    'tonyp':      ['@tonyp', 'tonyp'],
    'professor_jiang': ['podcast_youtube_UCWOnz7XxWPScqfF1ejt'],
    'glenn_diesen': ['podcast_youtube_UCZFCDIHTe9HGxtIuVDp'],
    'triggernometry': ['podcast_triggernometry'],
    'conflicted': ['podcast_conflicted'],
    'foreign_policy_live': ['podcast_foreign_policy_live'],
    'ian_bremmer': ['podcast_gzero_world_with_ian_bremmer', 'ianbremmer'],
}

def _detect_institution(query):
    """Detect if user asks about a specific institution. Returns (key, [variants]) or (None, None)."""
    q = query.lower()
    for key, variants in _INSTITUTION_KEYWORDS.items():
        for v in variants:
            if v.lower() in q:
                return key, variants
    return None, None

def _institution_boost(df, results_tweets, inst_key, inst_variants, limit=5):
    """
    Two-layer institution search:
      Layer 1 (DIRECT): articles FROM the institution (username match) — primary voice
      Layer 2 (CITED):  articles that MENTION the institution (content_text match) — secondary
    Direct source articles are prioritized in the results.
    Returns list of extra tweet dicts to prepend (may be empty).
    """
    import re as _re
    pattern = '|'.join(_re.escape(v) for v in inst_variants)
    existing_ids = {str(t.get('id', '')) for t in results_tweets}

    # Check if top results already have enough mentions
    top_n = results_tweets[:20]
    top_mentions = sum(1 for tweet in top_n 
                       if any(v.lower() in str(tweet.get('text', '')).lower() for v in inst_variants))

    # Also check if direct source articles are already in results
    direct_usernames = set(u.lower() for u in _INSTITUTION_USERNAMES.get(inst_key, []))
    top_direct = sum(1 for tweet in top_n
                     if str(tweet.get('username', '')).lower() in direct_usernames)

    if top_mentions >= 3 and top_direct >= 1:
        print(f"[InstitutionBoost] {inst_key} well-represented: {top_mentions} mentions + {top_direct} direct — no boost needed")
        return []

    extras = []

    # LAYER 1: Direct source (FROM the institution)
    if direct_usernames:
        direct_mask = df['username'].str.lower().isin(direct_usernames)
        direct_df = df[direct_mask].copy()
        if len(direct_df) > 0:
            direct_df = direct_df.nlargest(min(limit, len(direct_df)), 'time_weighted_score')
            for _, row in direct_df.iterrows():
                rid = str(row.get('id', ''))
                if rid in existing_ids:
                    continue
                existing_ids.add(rid)
                username = row.get('username', '')
                tweet_id = row.get('id', '')
                tweet_url = ''
                if tweet_id and username and not str(tweet_id).startswith('codex_'):
                    tweet_url = f"https://x.com/{username}/status/{tweet_id}"
                urls_field = row.get('urls', '') or ''
                text_urls = _re.findall(r'https?://[^\s<>)]+', str(row.get('text', '')))
                article_url = urls_field if urls_field else (text_urls[0] if text_urls else '')
                ct = str(row.get('content_text', ''))
                is_podcast = str(row.get('source_type', '')) == 'podcast' or username.startswith('podcast_')
                max_chars = 8000 if is_podcast else 2000
                text_val = ct[:max_chars] if len(ct) > 100 else str(row.get('text', ''))[:max_chars]
                extras.append({
                    'text': text_val,
                    'username': username,
                    'keywords': row.get('keywords', ''),
                    'ai_score': row.get('ai_score', 0),
                    'track': 'institution_direct',
                    'tweet_url': tweet_url,
                    'article_url': article_url,
                })
            print(f"[InstitutionBoost] {inst_key} DIRECT: +{len(extras)} from source usernames {direct_usernames & set(df['username'].str.lower().unique())}")

    # LAYER 2: Cited by others (MENTIONS the institution in content)
    remaining = limit - len(extras)
    if remaining > 0:
        cited_mask = df['content_text'].str.contains(pattern, case=False, na=False)
        cited_df = df[cited_mask].copy()
        if len(cited_df) > 0:
            cited_df = cited_df.nlargest(min(remaining * 2, len(cited_df)), 'time_weighted_score')
            cited_count = 0
            for _, row in cited_df.iterrows():
                if cited_count >= remaining:
                    break
                rid = str(row.get('id', ''))
                if rid in existing_ids:
                    continue
                existing_ids.add(rid)
                username = row.get('username', '')
                tweet_id = row.get('id', '')
                tweet_url = ''
                if tweet_id and username and not str(tweet_id).startswith('codex_'):
                    tweet_url = f"https://x.com/{username}/status/{tweet_id}"
                urls_field = row.get('urls', '') or ''
                text_urls = _re.findall(r'https?://[^\s<>)]+', str(row.get('text', '')))
                article_url = urls_field if urls_field else (text_urls[0] if text_urls else '')
                ct = str(row.get('content_text', ''))
                is_podcast = str(row.get('source_type', '')) == 'podcast' or username.startswith('podcast_')
                max_chars = 8000 if is_podcast else 2000
                text_val = ct[:max_chars] if len(ct) > 100 else str(row.get('text', ''))[:max_chars]
                extras.append({
                    'text': text_val,
                    'username': username,
                    'keywords': row.get('keywords', ''),
                    'ai_score': row.get('ai_score', 0),
                    'track': 'institution_cited',
                    'tweet_url': tweet_url,
                    'article_url': article_url,
                })
                cited_count += 1
            print(f"[InstitutionBoost] {inst_key} CITED: +{cited_count} from content mentions")

    if not extras:
        print(f"[InstitutionBoost] {inst_key} not found in feed — no results")

    total = len(extras)
    direct_n = sum(1 for e in extras if e.get('track') == 'institution_direct')
    cited_n = total - direct_n
    if total > 0:
        print(f"[InstitutionBoost] {inst_key}: +{total} total ({direct_n} direct, {cited_n} cited)")
    return extras

# Voyage AI for semantic search (Dec 2025 upgrade)
try:
    import voyageai
    with open('/home/ubuntu/argus/newspaper_project/.voyage_api_key', 'r') as f:
        VOYAGE_API_KEY = f.read().strip()
    voyage_client = voyageai.Client(api_key=VOYAGE_API_KEY)
    VOYAGE_ENABLED = True
    print("✅ Voyage AI semantic search enabled (2048-dim)")
except Exception as e:
    print(f"⚠️ Voyage AI not available: {e}")
    voyage_client = None
    VOYAGE_ENABLED = False


# ══════════════════════════════════════════════════════════════
# QUERY LOG - 24h rolling structured log for diagnostics
# ══════════════════════════════════════════════════════════════
import threading as _log_threading

QUERY_LOG_FILE = '/home/ubuntu/argus/logs/rag_query_log.jsonl'
_query_log_lock = _log_threading.Lock()

def log_query(entry):
    """Append a structured query log entry (JSONL format, 24h rolling)."""
    import json as _j
    from datetime import datetime as _dt, timedelta as _td
    entry['logged_at'] = _dt.utcnow().isoformat()
    try:
        with _query_log_lock:
            with open(QUERY_LOG_FILE, 'a') as f:
                f.write(_j.dumps(entry, default=str) + '\n')
            # Trim to 24h occasionally
            import random
            if random.random() < 0.05:
                cutoff = (_dt.utcnow() - _td(hours=24)).isoformat()
                lines = open(QUERY_LOG_FILE).readlines()
                recent = [l for l in lines if _j.loads(l).get('logged_at', '') >= cutoff]
                with open(QUERY_LOG_FILE, 'w') as f:
                    f.writelines(recent)
    except Exception as e:
        print(f'[QueryLog] Error: {e}')

# Entity Registry (Apr 2026)
import entity_registry as _entity_reg
ENTITY_REGISTRY_LIVE = _entity_reg.is_live()
_ENTITY_SOURCE_NAMES = _entity_reg.get_source_display_names()
_LOADED_PROMPTS = _entity_reg.load_premade_queries()
if _LOADED_PROMPTS:
    print(f"[EntityRegistry] Loaded {len(_LOADED_PROMPTS)} prompt templates from MDs", flush=True)
_SCORING = _entity_reg.load_scoring_config()
print(f"[EntityRegistry] Scoring config: hybrid={_SCORING.get('hybrid_time_weight')}/{_SCORING.get('hybrid_semantic_weight')}, priority_high={_SCORING.get('priority_high')}", flush=True)
print(f"[EntityRegistry] LIVE={ENTITY_REGISTRY_LIVE}, source_names={len(_ENTITY_SOURCE_NAMES)}", flush=True)

app = Flask(__name__)

# API Key
try:
    with open('/home/ubuntu/argus/.api_key_8550', 'r') as f:
        API_KEY = f.read().strip()
except:
    API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

# ═══════════════════════════════════════════════════════════════════════════════
# RESPONSE SELF-EVALUATION SYSTEM (Dec 2025)
# Evaluates response quality before sending, regenerates if needed
# ═══════════════════════════════════════════════════════════════════════════════
try:
    response_evaluator = ResponseEvaluator()
    EVALUATION_ENABLED = True
    print("✅ Response Self-Evaluation enabled (score_accept=7.0)")
except Exception as e:
    print(f"⚠️ Response Evaluator not available: {e}")
    response_evaluator = None
    EVALUATION_ENABLED = False

# Email configuration for sending analysis
EMAIL_USER_8550 = os.environ.get('EMAIL_USER_8550', '')
EMAIL_PASS_8550 = os.environ.get('EMAIL_PASS_8550', '')  # stripped for public repo
RECIPIENT_8550 = os.environ.get('RECIPIENT_8550', '')

# ═══════════════════════════════════════════════════════════════
# TELEGRAM BOT CONFIG
# ═══════════════════════════════════════════════════════════════
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')  # stripped for public repo
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
LODO_CHAT_ID = os.environ.get('LODO_CHAT_ID', '')

def _close_open_tags(chunk):
    """Ensure all HTML tags are properly closed in a chunk."""
    for tag in ['b', 'i', 'code', 'pre']:
        open_count = chunk.count(f'<{tag}>')
        close_count = chunk.count(f'</{tag}>')
        if open_count > close_count:
            chunk += f'</{tag}>' * (open_count - close_count)
    return chunk


def _sanitize_tg_html(text):
    """Escape < and > that aren't part of valid Telegram HTML tags.
    Prevents Telegram parse errors from LLM output like '<15%' or '<6,000'."""
    import re as _san_re
    # Valid Telegram tags: b, i, u, s, code, pre, a, tg-spoiler (opening and closing)
    safe_tag = _san_re.compile(r'<(/?)(?:b|i|u|s|code|pre|a|tg-spoiler)(?:\s[^>]*)?>',  _san_re.IGNORECASE)
    result = []
    i = 0
    while i < len(text):
        if text[i] == '<':
            m = safe_tag.match(text, i)
            if m:
                result.append(m.group(0))
                i = m.end()
            else:
                result.append('&lt;')
                i += 1
        elif text[i] == '&' and not text[i:i+4].startswith('&lt;') and not text[i:i+4].startswith('&gt;') and not text[i:i+5].startswith('&amp;'):
            result.append('&amp;')
            i += 1
        else:
            result.append(text[i])
            i += 1
    return ''.join(result)


def send_telegram_message(text, parse_mode="HTML", chat_id=None):
    """Send message to Telegram bot, splitting if > 4096 chars.
    Ensures HTML tags are properly closed in each chunk to avoid parse failures."""
    import requests as _tg_req
    _target_chat = chat_id or TELEGRAM_CHAT_ID
    MAX_LEN = 4000
    chunks = []
    while len(text) > MAX_LEN:
        # Find a good split point (newline before limit)
        sp = text.rfind('\n', 0, MAX_LEN)
        if sp == -1:
            sp = MAX_LEN
        chunk = text[:sp]
        # Close any open HTML tags in this chunk
        chunk = _close_open_tags(chunk)
        chunk = _sanitize_tg_html(chunk)
        chunks.append(chunk)
        text = text[sp:].lstrip('\n')
    chunks.append(_sanitize_tg_html(text))
    sent = 0
    for chunk in chunks:
        try:
            r = _tg_req.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": _target_chat, "text": chunk, "parse_mode": parse_mode},
                timeout=30
            )
            resp_data = r.json()
            if not resp_data.get('ok'):
                err_code = resp_data.get('error_code', 0)
                err_desc = resp_data.get('description', 'unknown')
                print(f"[TELEGRAM] Send failed ({err_code}): {err_desc}", flush=True)
                # HTTP 429 Too Many Requests — respect retry_after then retry
                if err_code == 429:
                    import time as _rate_time
                    retry_after = resp_data.get('parameters', {}).get('retry_after', 30)
                    print(f"[TELEGRAM] Rate limited, sleeping {retry_after + 2}s", flush=True)
                    _rate_time.sleep(retry_after + 2)
                    r = _tg_req.post(
                        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                        json={"chat_id": _target_chat, "text": chunk, "parse_mode": parse_mode},
                        timeout=30
                    )
                    resp_retry = r.json()
                    if not resp_retry.get('ok'):
                        print(f"[TELEGRAM] Retry after 429 also failed: {resp_retry.get('description', '?')}", flush=True)
                else:
                    # Strip HTML and retry as plain text
                    import re as _strip_re
                    plain = _strip_re.sub(r'<[^>]+>', '', chunk)
                    _tg_req.post(
                        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                        json={"chat_id": _target_chat, "text": plain},
                        timeout=30
                    )
            sent += 1
            import time; time.sleep(0.3)
        except Exception as e:
            print(f"[TELEGRAM] Send error: {e}")
    return sent

def _tg_send_and_get_id(text, chat_id, parse_mode="HTML"):
    """Send a single Telegram message and return (message_id, ok)."""
    import requests as _tg_req
    try:
        text = text[:4000]
        r = _tg_req.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
            timeout=15
        )
        data = r.json()
        if data.get('ok'):
            return data['result']['message_id'], True
        # Retry as plain text
        import re as _rp
        plain = _rp.sub(r'<[^>]+>', '', text)
        r2 = _tg_req.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": plain},
            timeout=15
        )
        d2 = r2.json()
        return (d2.get('result',{}).get('message_id'), d2.get('ok', False))
    except Exception as e:
        print(f"[TG-SEND] Error: {e}", flush=True)
        return None, False


def _tg_edit(msg_id, text, chat_id, parse_mode="HTML"):
    """Edit an existing Telegram message (for streaming updates)."""
    if not msg_id:
        return
    import requests as _tg_req
    import re as _rp
    import time as _tg_time
    # Sanitize HTML before truncating
    text = _sanitize_tg_html(text)
    # Truncate AFTER sanitizing (entity escapes may have grown the text)
    text = text[:4000]
    try:
        r = _tg_req.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText",
            json={"chat_id": chat_id, "message_id": msg_id,
                  "text": text, "parse_mode": parse_mode},
            timeout=10
        )
        resp = r.json()
        if resp.get('ok'):
            return
        err_code = resp.get('error_code', 0)
        err_desc = resp.get('description', 'unknown')
        print(f"[TG-EDIT] Failed ({err_code}): {err_desc}", flush=True)
        # HTTP 429 Too Many Requests — respect retry_after, retry once
        if err_code == 429:
            retry_after = resp.get('parameters', {}).get('retry_after', 30)
            print(f"[TG-EDIT] Rate limited, sleeping {retry_after + 2}s", flush=True)
            _tg_time.sleep(retry_after + 2)
            r2 = _tg_req.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText",
                json={"chat_id": chat_id, "message_id": msg_id,
                      "text": text, "parse_mode": parse_mode},
                timeout=10
            )
            if not r2.json().get('ok'):
                print(f"[TG-EDIT] Retry after 429 also failed: {r2.json().get('description', '?')}", flush=True)
            return
        # HTTP 400 HTML parse error — retry as plain text
        if err_code == 400:
            plain = _rp.sub(r'<[^>]+>', '', text)
            r3 = _tg_req.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText",
                json={"chat_id": chat_id, "message_id": msg_id, "text": plain},
                timeout=10
            )
            if not r3.json().get('ok'):
                print(f"[TG-EDIT] Plain-text fallback also failed: {r3.json().get('description', '?')}", flush=True)
            return
    except Exception as e:
        print(f"[TG-EDIT] Exception: {e}", flush=True)


# ─── Per-session streaming queue for live Telegram updates ───────────────────
import queue as _queue_mod
_TG_STREAM_QUEUES = {}  # session_id -> Queue of str tokens (None = done)
_TG_STREAM_LOCK = __import__('threading').Lock()

def _tg_stream_register(session_id):
    q = _queue_mod.Queue()
    with _TG_STREAM_LOCK:
        _TG_STREAM_QUEUES[session_id] = q
    return q

def _tg_stream_unregister(session_id):
    with _TG_STREAM_LOCK:
        _TG_STREAM_QUEUES.pop(session_id, None)

def _tg_stream_put(session_id, token):
    with _TG_STREAM_LOCK:
        q = _TG_STREAM_QUEUES.get(session_id)
    if q:
        q.put(token)


def send_telegram_photo(photo_bytes, chat_id=None, caption=None):
    """Send a photo (BytesIO PNG) to Telegram."""
    import requests as _tg_req
    _target = chat_id or TELEGRAM_CHAT_ID
    try:
        files = {"photo": ("chart.png", photo_bytes, "image/png")}
        data = {"chat_id": _target}
        if caption:
            data["caption"] = caption[:1024]
        r = _tg_req.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
            files=files, data=data, timeout=30
        )
        return r.json().get('ok', False)
    except Exception as e:
        print(f"[TELEGRAM] Photo send error: {e}")
        return False

def format_for_telegram(markdown_text):
    """Convert markdown response to Telegram HTML, preserving <pre> blocks"""
    t = markdown_text
    # Extract <pre>...</pre> blocks before HTML-escaping
    pre_blocks = []
    def _save_pre(m):
        pre_blocks.append(m.group(0))
        return f"__PRE_BLOCK_{len(pre_blocks)-1}__"
    t = re.sub(r'<pre>(.*?)</pre>', _save_pre, t, flags=re.DOTALL)
    # HTML-escape the rest (& must come first)
    t = t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    # Horizontal rules -> thin line
    t = re.sub(r'^---+$', '────────────────────', t, flags=re.MULTILINE)
    # Headers (# ## ###) -> bold (with or without space after #)
    t = re.sub(r'^###\s*(.+)', r'<b>\1</b>', t, flags=re.MULTILINE)
    t = re.sub(r'^##\s*(.+)', r'<b>\1</b>', t, flags=re.MULTILINE)
    t = re.sub(r'^#\s*(.+)', r'<b>\1</b>', t, flags=re.MULTILINE)
    # Bold (**text**) - must come before italic
    t = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', t)
    # Italic (*text*) - but NOT bullet points (lines starting with * )
    t = re.sub(r'(?<=\s)\*(?!\s)(.+?)(?<!\s)\*(?!\*)', r'<i>\1</i>', t)
    # Inline code backticks
    t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
    # Blockquotes -> italic with bar
    t = re.sub(r'^&gt;\s*(.+)', '│ <i>' + r'\1' + '</i>', t, flags=re.MULTILINE)
    # Clean up any leftover ## that didn't match (no space)
    t = re.sub(r'^#{1,3}(?=\S)', '', t, flags=re.MULTILINE)
    # Re-insert preserved <pre> blocks
    for i, block in enumerate(pre_blocks):
        t = t.replace(f"__PRE_BLOCK_{i}__", block)
    return t

# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE CLASSIFICATIONS - Read from central database (Dec 2025)
# Single source of truth: http://argus.data-codex.com/sources
# ═══════════════════════════════════════════════════════════════════════════════
SOURCE_DB_PATH = '/home/ubuntu/argus/newspaper_project/source_classifications.db'


# ═══════════════════════════════════════════════════════════════════════════════
# QUALITY ENHANCEMENT: Use full article content when available (Dec 2025)
# ═══════════════════════════════════════════════════════════════════════════════
def get_best_text(row, max_length=2000):
    """
    Get the best available text content for RAG response.
    Priority: content_text (full article) > text (tweet)
    """
    # Try content_text first (full article from scraping)
    content_text = row.get('content_text', '')
    if content_text and len(str(content_text)) > 100:
        return str(content_text)[:max_length]
    
    # Fall back to text (tweet/headline)
    text = row.get('text', '')
    return str(text)[:max_length] if text else ''


def get_sources_by_classification(classification):
    """
    Get sources from central database by classification.
    classification: 'brazil', 'macro', or 'both'
    Returns: set of source_ids (lowercase usernames)
    """
    try:
        conn = sqlite3.connect(SOURCE_DB_PATH)
        cursor = conn.cursor()
        
        if classification == 'brazil':
            cursor.execute("SELECT source_id FROM source_classifications WHERE classification IN ('brazil', 'both')")
        elif classification == 'macro':
            cursor.execute("SELECT source_id FROM source_classifications WHERE classification IN ('macro', 'both')")
        else:
            cursor.execute("SELECT source_id FROM source_classifications WHERE classification = ?", (classification,))
        
        sources = set(row[0].lower() for row in cursor.fetchall())
        conn.close()
        return sources
    except Exception as e:
        print(f"Error reading source classifications: {e}")
        # Fallback to hardcoded if DB fails
        return {'infomoney', 'estadao', 'folha', 'metropoles', 'cnnbrasil', 'poder360', 'blogdonoblat'}

def get_brazilian_sources():
    """Get all Brazil-classified sources"""
    return get_sources_by_classification('brazil')

def get_macro_sources():
    """Get all Macro-classified sources"""
    return get_sources_by_classification('macro')

def get_source_priority(source_id):
    """Get priority level for a source from classifications DB"""
    try:
        conn = sqlite3.connect(SOURCE_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT priority FROM source_classifications WHERE source_id = ?", (source_id.lower(),))
        row = cursor.fetchone()
        conn.close()
        if row:
            return row[0] or 'normal'
        return 'normal'
    except:
        return 'normal'

def get_source_class(source_id):
    """Get class level (1-5) for a source from classifications DB"""
    try:
        conn = sqlite3.connect('/home/ubuntu/argus/newspaper_project/source_classifications.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COALESCE(source_class, 3) FROM source_classifications WHERE source_id = ?", (source_id.lower(),))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 3
    except:
        return 3

def get_high_priority_sources():
    """Get all high-priority sources"""
    try:
        conn = sqlite3.connect(SOURCE_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT source_id FROM source_classifications WHERE priority = 'high'")
        sources = set(row[0].lower() for row in cursor.fetchall())
        conn.close()
        return sources
    except:
        return set()

def detect_query_type(query):
    """Detect if query is political/institutional to enable connection analysis"""
    query_lower = query.lower()
    political_keywords = [
        'stf', 'supremo', 'senado', 'câmara', 'congresso', 'governo', 'lula',
        'bolsonaro', 'ministro', 'presidente', 'deputado', 'senador', 'gilmar',
        'alcolumbre', 'messias', 'impeachment', 'indicação', 'nomeação', 'política',
        'político', 'poderes', 'executivo', 'legislativo', 'judiciário', 'pl',
        'pt', 'psdb', 'união brasil', 'pp', 'psd', 'mdb', 'republicanos'
    ]
    return any(kw in query_lower for kw in political_keywords)



# Legacy compatibility - will be replaced by dynamic lookup
BRAZILIAN_SOURCES = {
    'infomoney': 3, 'valoreconomico': 3, 'estadao': 3, 'folha': 3,
    'jotainfo': 3, 'poder360': 3, 'monicabergamo': 3, 'blogdonoblat': 3,
    'laurojardim': 3, 'pfnery': 3, 'cnnbrasil': 2, 'metropoles': 2,
    'danleich': 3, 'rconstantino': 3, 'andreazzaeditor': 3, 'acikielmogois': 3
}

# Pre-made queries
PREMADE_QUERIES = {
    'macro': """What are the major MACRO themes in the selected time window?

RESPONSE FORMAT: Use rich markdown with ## headers, **bold**, bullet points, and tables. Do NOT return JSON or structured data objects. Write a narrative analysis.

Provide a comprehensive analysis:
1. Top 10 themes ranked by importance and source volume
2. For each theme: a ## header, detailed analysis (5-7 sentences), key market levels with timestamps, sentiment (bullish/bearish/neutral)
3. Key sources (@usernames who discussed each theme)
4. Include direct quotes from notable analysts when available
5. When citing market prices, always specify the time they were observed
6. Polymarket/prediction market data should be woven into relevant themes as supporting evidence, NOT listed as separate themes

Focus on global macro, US economy, Europe, Asia, commodities, currencies, and geopolitics.""",

    'brazil': """Quais são os principais temas discutidos no Brasil nas últimas 24 horas?

Forneça uma análise abrangente EM PORTUGUÊS:
1. Top 10 temas ranqueados por importância
2. Para cada tema: análise detalhada (5-7 frases), implicações, sentimento
3. Principais fontes (@usernames)
4. Citações diretas quando disponíveis
5. Links para tweets importantes usando formato markdown [texto](url)

Foco em política brasileira, economia, mercados, Banco Central, e relações internacionais.""",

    'codex': """Summarize all CODEX email intelligence from the last 24 hours.

Provide:
1. Executive Summary (3-4 sentences overview)
2. Key Numbers: All important data points, percentages, and figures
3. Source-by-Source breakdown:
   - Goldman Sachs: Main insights
   - Rosenberg Research: Key views
   - Other sources: Notable points
4. Preserve the author's voice and perspective
5. Include any actionable insights or trade ideas mentioned""",

    'compare': """Compare today's major themes with the previous day's themes.

Provide:
1. What's NEW today that wasn't discussed yesterday?
2. What's INTENSIFYING (more tweets, more urgency)?
3. What's FADING (less attention than yesterday)?
4. Key shifts in sentiment
5. Notable new sources weighing in
6. Include links to support your analysis""",

    'risks': """What are the key MARKET RISKS being discussed right now?

Focus on:
1. Bearish signals and concerns
2. Geopolitical risks
3. Economic warning signs
4. Sector-specific risks
5. What analysts are worried about
6. Include quotes from pessimistic voices
7. Sentiment analysis: How fearful vs complacent is the market?""",

    'breaking': """What are the MOST IMPORTANT breaking stories from the last 24 hours?

Provide:
1. Top 5 most significant news items
2. Why each matters for markets
3. Who broke the story first
4. Market reaction (if any)
5. Links to original sources
6. Rank by urgency/importance""",

    'numbers': """Extract all KEY NUMBERS and statistics from today's data.

Provide:
1. Economic data releases (GDP, unemployment, inflation, etc.)
2. Market moves (indices, commodities, currencies)
3. Company-specific numbers
4. Central bank related figures
5. Any notable records or milestones
6. Format as a clear, scannable list""",

    'evolution': """How have the major themes EVOLVED over the past 7 days?

Analyze:
1. Which themes are consistently discussed all week?
2. Which themes emerged mid-week?
3. Which themes peaked and faded?
4. Any cyclical patterns?
5. What's the "story of the week"?
6. Predictions for next week based on trajectory"""
}



# Time decay configuration
TIME_DECAY_HALFLIFE_HOURS = 48  # Half-life for exponential decay
BRAZIL_TZ = ZoneInfo('America/Sao_Paulo')

def get_brazil_time():
    """Get current time in Brazil timezone"""
    return datetime.now(BRAZIL_TZ)

def calculate_time_decay(created_at, query_time=None):
    """Time decay disabled - Time Agent already filters by period"""
    # Jan 2026: Since Time Agent defines the time window,
    # all items within that window get equal weight (1.0)
    # No need to penalize older items within the selected period
    return 1.0

def get_data_time_range(df):
    """Get the time range of data in the dataframe"""
    try:
        # Handle date formats with Z suffix and nanoseconds
        # created_at_dt already parsed above
        valid = df[df['created_at_dt'].notna()]
        if len(valid) == 0:
            return None, None, 0
        
        oldest = valid['created_at_dt'].min()
        newest = valid['created_at_dt'].max()
        return oldest, newest, len(valid)
    except:
        return None, None, 0


def semantic_search(query: str, df, limit: int = 50, min_similarity: float = 0.3, query_understanding: dict = None):
    """
    Native LanceDB vector search using Voyage AI embeddings.
    Re-enabled Mar 2026: Uses LanceDB ANN instead of brute-force numpy.
    Returns list of (df_index, similarity_score) tuples, or None on failure.
    """
    if not VOYAGE_ENABLED or voyage_client is None:
        print('[8550] Semantic search: Voyage not available')
        return None

    try:
        import time as _vs_time
        _vs_t0 = _vs_time.time()

        result = voyage_client.embed(
            texts=[query],
            model="voyage-3-large",
            input_type="query",
            output_dimension=2048
        )
        query_vector = np.array(result.embeddings[0], dtype='float32')
        _vs_t1 = _vs_time.time()

        _lance_db = _get_rag_db()
        _lance_table = _lance_db.open_table('unified_feed')

        lance_results = (
            _lance_table
            .search(query_vector, vector_column_name='content_vector')
            .where('has_vector > 0', prefilter=True)
            .limit(limit * 3)
            .to_pandas()
        )
        _vs_t2 = _vs_time.time()

        if lance_results.empty:
            print(f'[8550] Semantic search: no results from LanceDB')
            return None

        lance_ids = set(str(r) for r in lance_results['id'].values)
        max_dist = lance_results['_distance'].max() if '_distance' in lance_results.columns else 2.0
        if max_dist == 0:
            max_dist = 1.0

        # FAST MERGE: filter df to matched rows first, then iterate only ~150 rows
        _lance_dist_map = dict(zip(lance_results['id'].astype(str), lance_results['_distance']))
        _df_matched = df[df['id'].astype(str).isin(lance_ids)].copy()
        matched = []
        for df_idx, row in _df_matched.iterrows():
            _row_id = str(row['id'])
            _dist = _lance_dist_map.get(_row_id, max_dist)
            matched.append((df_idx, max(0, 1.0 - (_dist / max_dist))))
        matched.sort(key=lambda x: x[1], reverse=True)
        matched = matched[:limit]

        _vs_t3 = _vs_time.time()
        print(f'[8550] Semantic search: embed={_vs_t1-_vs_t0:.2f}s lance={_vs_t2-_vs_t1:.2f}s merge={_vs_t3-_vs_t2:.2f}s total={_vs_t3-_vs_t0:.2f}s matched={len(matched)}', flush=True)
        # 2026-04-22: threshold > 5 -> >= 1. Was dropping 1-5-match results (17% of
        # queries) and forcing them into the slow score_tweet fallback. See
        # docs/QUERY_PIPELINE.md.
        return matched if len(matched) >= 1 else None

    except Exception as e:
        print(f'[8550] Semantic search error: {e}', flush=True)
        return None
    """ORIGINAL BELOW:
    Perform semantic search using Voyage AI embeddings.
    Returns indices of most relevant rows sorted by similarity.
    
    Uses vlm_enhanced_vector when available (contains chart/table data from VLM processing),
    otherwise falls back to content_vector (text-only embedding).
    Both are voyage-3-large, 2048 dim.
    """
    if not VOYAGE_ENABLED or voyage_client is None:
        return None  # Fall back to text-based search
    
    try:
        # Generate query embedding with input_type="query"
        result = voyage_client.embed(
            texts=[query],
            model="voyage-3-large",
            input_type="query",
            output_dimension=2048
        )
        query_vector = np.array(result.embeddings[0])
        
        # If we have query understanding with boosts, lower threshold
        effective_min_sim = min_similarity
        if query_understanding and query_understanding.get('boost_keywords'):
            effective_min_sim = 0.20  # Lower to allow boosted docs
        
        # Calculate cosine similarity with all documents
        # Use VLM-enhanced vector when available (has chart data), else use content_vector
        similarities = []
        vlm_used = 0
        boosts_applied = 0
        
        # PERF: Load vectors only for the time-filtered subset
        import time as _time
        _tv0 = _time.time()
        _fids = set(str(x) for x in df['id'].tolist())
        try:
            _vdb = _get_rag_db()
            _vt = _vdb.open_table('unified_feed')
            _va = _vt.to_arrow()
            import pyarrow as pa
            _vcols = ['id']
            if 'content_vector' in _va.column_names: _vcols.append('content_vector')
            if 'vlm_enhanced_vector' in _va.column_names: _vcols.append('vlm_enhanced_vector')
            _vsel = _va.select(_vcols)
            _vpd = _vsel.to_pandas()
            _vpd = _vpd[_vpd['id'].astype(str).isin(_fids)]
            _vmap = {}
            for _, _vr in _vpd.iterrows():
                _vmap[str(_vr['id'])] = {'cv': _vr.get('content_vector'), 'vv': _vr.get('vlm_enhanced_vector')}
            del _va, _vsel, _vpd
            print(f'[8550] Vector load: {_time.time()-_tv0:.1f}s for {len(_vmap)} rows')
        except Exception as _ve:
            print(f'[8550] Vector load failed: {_ve}')
            _vmap = {}

        for idx, row in df.iterrows():
            _rid = str(row.get('id', ''))
            if _rid in _vec_map:
                row['content_vector'] = _vec_map[_rid].get('content_vector')
                row['vlm_enhanced_vector'] = _vec_map[_rid].get('vlm_enhanced_vector')
            # Inject vectors from lazy map
            _rid = str(row.get('id', ''))
            if _rid in _vmap:
                row = row.copy()
                row['content_vector'] = _vmap[_rid].get('cv')
                row['vlm_enhanced_vector'] = _vmap[_rid].get('vv')
            # Check exclusions first (Jan 2026)
            if query_understanding and should_exclude(query_understanding, row):
                continue
            
            # Prefer vlm_enhanced_vector (contains chart data from VLM processing)
            doc_vector = row.get('vlm_enhanced_vector')
            if doc_vector is not None and hasattr(doc_vector, '__len__') and len(doc_vector) == 2048:
                vlm_used += 1
            else:
                doc_vector = row.get('content_vector')
            
            if doc_vector is not None and hasattr(doc_vector, '__len__') and len(doc_vector) == 2048:
                doc_vector = np.array(doc_vector)
                # Cosine similarity
                similarity = np.dot(query_vector, doc_vector) / (
                    np.linalg.norm(query_vector) * np.linalg.norm(doc_vector) + 1e-8
                )
                
                # Apply keyword boost from query understanding (Jan 2026)
                boost = 0.0
                if query_understanding:
                    doc_content = str(row.get('content_text', '')) + ' ' + str(row.get('text', ''))
                    boost = calculate_boost(query_understanding, doc_content)
                    if boost > 0:
                        boosts_applied += 1
                
                final_similarity = similarity + boost
                
                if final_similarity >= effective_min_sim:
                    similarities.append((idx, final_similarity))
        
        if boosts_applied > 0:
            print(f"Query Understanding: applied {boosts_applied} boosts")
        
        # Sort by similarity (highest first)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Return top results
        return similarities[:limit]
    
    except Exception as e:
        print(f"⚠️ Semantic search error: {e}")
        return None


def hybrid_search(query: str, df, filters: list, limit: int = 50, query_understanding: dict = None):
    """
    Hybrid search combining semantic similarity + text matching + time decay.
    Returns filtered and scored DataFrame.
    """
    # Try semantic search first
    semantic_results = semantic_search(query, df, limit=limit*2, query_understanding=query_understanding)
    
    # 2026-04-22: threshold lowered from >10 to >=1. Rationale: when semantic has few
    # matches, those rows get boosted; others fall back to time_weighted_score via the
    # hybrid formula (semantic_score=0). This avoids the slow Python-fallback path in
    # Step 6 (df.apply(score_tweet, axis=1) over ~3,400 rows = ~50s). See docs/QUERY_PIPELINE.md.
    if semantic_results and len(semantic_results) >= 1:
        # Get semantic scores as a dict
        semantic_scores = {idx: score for idx, score in semantic_results}
        
        # Add semantic score to dataframe
        df['semantic_score'] = df.index.map(lambda x: semantic_scores.get(x, 0))
        
        # 2026-04-22: priority boost applied in fast path for parity with slow
        # score_tweet path. High-priority sources get 1.5x multiplier so
        # First Squawk / DeItaone / VIP accounts dont get drowned out by volume.
        # One DB query (get_high_priority_sources), vectorised .apply — near-zero
        # cost. See docs/QUERY_PIPELINE.md.
        _high_priority = get_high_priority_sources()
        _priority_mult = df['username'].fillna('').str.lower().apply(
            lambda u: 1.5 if u in _high_priority else 1.0
        )
        
        # Boost rows with high semantic similarity + source priority
        df['hybrid_score'] = (
            df['time_weighted_score'] * _SCORING.get('hybrid_time_weight', 0.4) +
            df['semantic_score'] * _SCORING.get('hybrid_semantic_multiplier', 10) * _SCORING.get('hybrid_semantic_weight', 0.6)
        ) * _priority_mult                      # × source priority
        
        return df.nlargest(limit, 'hybrid_score')
    else:
        # Fall back to text-based scoring
        return None


def parse_temporal_query(query):
    """Parse temporal references in query and return time window"""
    query_lower = query.lower()
    now = datetime.now()
    
    # Check for temporal keywords
    if 'today' in query_lower or 'hoje' in query_lower:
        return now - timedelta(hours=24), now, 'last 24 hours'
    elif 'yesterday' in query_lower or 'ontem' in query_lower:
        return now - timedelta(hours=48), now - timedelta(hours=24), 'yesterday'
    elif 'this week' in query_lower or 'esta semana' in query_lower:
        return now - timedelta(days=7), now, 'last 7 days'
    elif 'last 24' in query_lower or 'últimas 24' in query_lower:
        return now - timedelta(hours=24), now, 'last 24 hours'
    elif 'last 48' in query_lower or 'últimas 48' in query_lower:
        return now - timedelta(hours=48), now, 'last 48 hours'
    elif 'this month' in query_lower or 'este mês' in query_lower:
        return now - timedelta(days=30), now, 'last 30 days'
    else:
        return None, None, None  # No temporal constraint


# Chat sessions storage
chat_sessions = {}
# Stores last full query+response per chat_id for #continue command
_pending_continuation: dict = {}  # chat_id -> {query, response_so_far, session_id}



# ════════════════════════════════════════════════════════════════
# PERFORMANCE: Global Feed Cache - load data once, refresh every 5 min
# Avoids reloading 200K rows from LanceDB on every query
# ════════════════════════════════════════════════════════════════
import time as _cache_time
import threading

class _FeedCache:
    def __init__(self):
        self._df = None
        self._loaded_at = 0
        self._lock = threading.Lock()
        self._refreshing = False
        self.TTL = 900  # 15 minutes (loads take 3-12 min, 5-min TTL caused memory bloat)

    def _do_load(self, table):
        """Internal: load data from LanceDB + pre-parse dates"""
        t0 = _cache_time.time()
        _heavy = {'content_vector', 'vlm_enhanced_vector', 'content_html', 'raw_data'}
        _light = [c for c in table.schema.names if c not in _heavy]
        new_df = table.search().select(_light).limit(300000).to_pandas()
        _before = len(new_df)
        new_df = new_df[
            ((new_df['status'].isin(['enriched', 'active', 'vlm_enriched', 'vip_scored'])) | (new_df['status'].isna()))
            & ((new_df['is_junk'] != True) | (new_df['is_junk'].isna()))
        ].reset_index(drop=True)
        # Pre-parse dates in cache so queries skip the 38s apply step
        import pandas as _pd
        def _parse_dt_fast(val):
            if _pd.isna(val):
                return _pd.NaT
            try:
                s = str(val).replace('000000000Z', '').replace('Z', '').replace('+00:00', '').strip()
                dt = _pd.to_datetime(s)
                if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
                    dt = dt.replace(tzinfo=None)
                return dt
            except:
                return _pd.NaT
        new_df['created_at_dt'] = _pd.to_datetime(new_df['created_at'].apply(_parse_dt_fast), errors='coerce')
        t1 = _cache_time.time()
        valid = new_df['created_at_dt'].notna().sum()
        with self._lock:
            self._df = new_df
            self._loaded_at = _cache_time.time()
            self._refreshing = False
        print(f'[FeedCache] Loaded {len(new_df)} rows ({valid} valid dates) in {self._loaded_at - t0:.1f}s', flush=True)
        import gc; gc.collect()

    def get_df(self, table):
        now = _cache_time.time()
        expired = self._df is not None and (now - self._loaded_at) >= self.TTL

        # First load ever: must block
        if self._df is None:
            print('[FeedCache] First load (blocking)...', flush=True)
            self._do_load(table)
            return self._df.copy()

        # Expired but have stale data: serve stale, refresh in background
        if expired and not self._refreshing:
            self._refreshing = True
            t = threading.Thread(target=self._do_load, args=(table,), daemon=True)
            t.start()
            print('[FeedCache] Stale data served, background refresh started', flush=True)

        return self._df.copy()

    def preload(self):
        """Preload cache at startup"""
        try:
            import lancedb as _lb
            db = _get_rag_db()  # reuse singleton
            table = db.open_table('unified_feed')
            self._do_load(table)
            print('[FeedCache] Preload complete!', flush=True)
        except Exception as e:
            print(f'[FeedCache] Preload failed: {e}', flush=True)

_feed_cache = _FeedCache()
# Preload cache at startup so first query is instant
threading.Thread(target=_feed_cache.preload, daemon=True).start()

def get_rag_context(query, filters, limit=200, query_understanding=None, boost2_enabled=False, time_hours=None):
    """Retrieve relevant data for RAG - NO JUNK - TIME AWARE"""
    db = _get_rag_db()
    table = db.open_table('unified_feed')
    # PERF: Use cached DataFrame (refreshes every 5 min)
    import time as _t; _s = _t.time()
    df = _feed_cache.get_df(table)
    print(f'[8550] Step1 cache: {_t.time()-_s:.1f}s, {len(df)} rows', flush=True)
    
    # CRITICAL: Exclude junk items
    # Check external junk file - items IN file are junked, items NOT in file are allowed
    from junk_manager import load_flags, JUNK_FILE
    junk_flags = load_flags(JUNK_FILE)
    junked_ids = set(str(k) for k in junk_flags.keys())
    
    # Exclude items that are in external junk file
    df = df[~df['id'].astype(str).isin(junked_ids)]
    print(f'[8550] Step2 junk: {_t.time()-_s:.1f}s, {len(df)} rows left', flush=True)
    
    
    # Parse datetime column - Fixed Jan 2026: Use apply() for robust mixed-type parsing
    def parse_date_robust(val):
        if pd.isna(val):
            return pd.NaT
        try:
            s = str(val).replace('000000000Z', '').replace('Z', '').replace('+00:00', '').strip()
            dt = pd.to_datetime(s)
            if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            return dt
        except:
            return pd.NaT
    
    print(f'[8550] Step3 parsing dates...', flush=True)
    if 'created_at_dt' not in df.columns or df['created_at_dt'].isna().all():
        df['created_at_dt'] = df['created_at'].apply(parse_date_robust)
        print(f'[8550] Step3 dates (parsed): {_t.time()-_s:.1f}s', flush=True)
    else:
        print(f'[8550] Step3 dates (cached): {_t.time()-_s:.1f}s', flush=True)
    
    
    # Get data time range for context
    oldest, newest, valid_count = get_data_time_range(df)
    
    # ═══════════════════════════════════════════════════════════════════
    # FLEXIBLE TIME FILTER - Uses Time Agent to detect time range
    # Jan 2026: Removed hardcoded 24h, now respects user intent
    # Default: 7 days when no time specified
    # ═══════════════════════════════════════════════════════════════════
    
    # Time range: use explicit time_hours from frontend or fall back to Time Agent
    if time_hours is not None and time_hours >= 0:
        now_filter = datetime.now()
        time_end = now_filter
        if time_hours == 0:
            time_start = datetime(2020, 1, 1)
            time_desc = "All database"
        elif time_hours <= 72:
            time_start = now_filter - timedelta(hours=time_hours)
            time_desc = f"Last {time_hours}h"
        elif time_hours <= 168:
            time_start = now_filter - timedelta(hours=time_hours)
            time_desc = f"Last {time_hours // 24} days"
        elif time_hours <= 744:
            time_start = now_filter - timedelta(hours=time_hours)
            time_desc = f"Last ~{round(time_hours / 168)} week(s)"
        else:
            time_start = now_filter - timedelta(hours=time_hours)
            time_desc = f"Last ~{round(time_hours / 720)} month(s)"
        time_metadata = {"reason": f"Frontend selection: {time_desc}", "display": time_desc}
        print(f"[8550] Time override from UI: {time_desc} ({time_hours}h)", flush=True)
    else:
        # Fall back to Time Agent
        time_start, time_end, time_desc, time_metadata = detect_time_range(query)
        # If Time Agent returns default (no time detected), use 7 days
        if "default" in time_metadata.get("reason", "").lower() or "no time" in time_metadata.get("reason", "").lower() or "no explicit" in time_metadata.get("reason", "").lower():
            now_filter = datetime.now()
            time_start = now_filter - timedelta(days=14)
            time_end = now_filter
            time_desc = "Last 14 days (default)"
            time_metadata["reason"] = "No time specified, using 14 days default"
            time_metadata["display"] = time_desc
    
    # Apply time filter based on Time Agent result
    # Ensure time_start/time_end are tz-naive to match parsed dates
    if hasattr(time_start, 'tzinfo') and time_start.tzinfo is not None:
        time_start = time_start.replace(tzinfo=None)
    if hasattr(time_end, 'tzinfo') and time_end.tzinfo is not None:
        time_end = time_end.replace(tzinfo=None)
    df = df[(df["created_at_dt"] >= time_start) & (df["created_at_dt"] <= time_end)]
    print(f'[8550] Step4 time filter: {_t.time()-_s:.1f}s, {len(df)} rows in window', flush=True)
    
    if len(df) == 0:
        print(f"WARNING: No data in time range {time_start} to {time_end}!")
    
    # Recompute data age from the FILTERED window (not the whole DB)
    filtered_valid = df[df['created_at_dt'].notna()]
    if len(filtered_valid) > 0:
        oldest = filtered_valid['created_at_dt'].min()
        newest = filtered_valid['created_at_dt'].max()
        valid_count = len(filtered_valid)
    
    # Calculate time decay for each row
    now = datetime.now()
    # Time decay disabled (Time Agent handles filtering), all items = 1.0
    df['time_decay'] = 1.0
    
    # Time-weighted score = ai_score * time_decay (effectively just ai_score)
    df['ai_score'] = pd.to_numeric(df['ai_score'], errors='coerce').fillna(5)
    df['time_weighted_score'] = df['ai_score'] * df['time_decay']
    
    results = {'tweets': [], 'codex': [], 'stats': {}, 'time_context': {}}
    
    # Add time context — data_age reflects the filtered window
    rows_in_window = len(df)
    age_hours = round((now - newest).total_seconds() / 3600, 1) if newest else None
    results['time_context'] = {
        'query_time': now.strftime('%Y-%m-%d %H:%M'),
        'query_time_brazil': get_brazil_time().strftime('%Y-%m-%d %H:%M BRT'),
        'data_oldest': oldest.strftime('%Y-%m-%d %H:%M') if oldest else 'Unknown',
        'data_newest': newest.strftime('%Y-%m-%d %H:%M') if newest else 'Unknown',
        'data_age_hours': age_hours,
        'data_freshness': 'LIVE' if age_hours is not None and age_hours < 1 else ('RECENT' if age_hours is not None and age_hours < 6 else 'STALE'),
        'temporal_filter': time_desc,
        'valid_timestamps': valid_count,
        'rows_in_time_window': rows_in_window,
        'time_start': time_start.strftime('%Y-%m-%d %H:%M') if time_start else None,
        'time_end': time_end.strftime('%Y-%m-%d %H:%M') if time_end else None,
    }
    query_lower = query.lower()
    raw_query_terms = set(query_lower.split())
    
    # AUTHOR DETECTION (Dec 16, 2025)
    # Check if query asks about a specific author/columnist
    detected_author = detect_author_in_query(query)
    if detected_author:
        author_key = detected_author.get("author_key", "unknown")
        print(f"🔍 Author detected in query: {author_key}")
        
        # Filter to get author-specific content
        author_df = filter_by_author(df, detected_author)
        author_count = len(author_df)
        print(f"   Found {author_count} items from this author")
        
        # If we have author-specific content, prioritize it
        if author_count > 0:
            # Sort by time and limit
            author_df = author_df.sort_values("created_at_dt", ascending=False).head(50)
            
            # Add author results to context
            for _, row in author_df.iterrows():
                tweet_id = str(row.get("id", ""))
                username = row.get("username", "")
                text = str(row.get("text", ""))
                content_text = str(row.get("content_text", ""))
                display_text = content_text[:1500] if len(content_text) > len(text) else text[:1500]
                
                results["tweets"].append({
                    "id": tweet_id,
                    "username": username,
                    "text": display_text,
                    "created_at": str(row.get("created_at", "")),
                    "ai_score": row.get("ai_score", 5),
                    "source_type": row.get("source_type", "tweet"),
                    "urls": str(row.get("urls", "")),
                    "author": row.get("author", ""),
                    "track": "author"
                })
            
            # Return early with author-specific results
            if author_count >= 3:
                results["stats"] = {
                    "total": author_count,
                    "author_query": True,
                    "author_name": author_key,
                    "source": detected_author.get("source", "")
                }
                return results
    
    # Synonym expansion for better semantic matching (Dec 2025)
    SYNONYMS = {
        'stf': ['stf', 'supremo', 'supremo tribunal federal', 'gilmar', 'moraes', 'dino', 'ministros'],
        'impeachment': ['impeachment', 'liminar', 'blindar', 'blindagem', 'destituição', 'afastamento'],
        'gilmar': ['gilmar', 'gilmar mendes', 'ministro decano', 'stf', 'supremo'],
        'nomeacao': ['nomeação', 'indicação', 'indicado', 'sabatina', 'messias', 'vaga', 'ccj'],
        'nomecao': ['nomeação', 'indicação', 'indicado', 'sabatina', 'messias', 'vaga', 'ccj'],
        'indicacao': ['indicação', 'indicado', 'nomeação', 'sabatina', 'messias'],
        'ministro': ['ministro', 'min.', 'ministros', 'stf'],
        'decisao': ['decisão', 'liminar', 'determinação', 'ordem'],
        'economia': ['economia', 'econômico', 'econômica', 'pib', 'inflação'],
        'dolar': ['dólar', 'dolar', 'usd', 'dollar'],
        'juros': ['juros', 'selic', 'taxa de juros', 'copom'],
    }
    
    # Expand query terms with synonyms
    query_terms = set()
    for term in raw_query_terms:
        query_terms.add(term)
        if term in SYNONYMS:
            query_terms.update(SYNONYMS[term])
    
    brazilian_usernames = get_brazilian_sources()  # Dynamic from source_classifications.db
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # ESCOPO DEFINIDO PELO FILTRO (Dec 2025 - Arquitetura Limpa)
    # Filtro = ONDE buscar | Manager Agent = COMO buscar dentro do escopo
    # ═══════════════════════════════════════════════════════════════════════════════
    # ═══════════════════════════════════════════════════════════════════════════════
    # SCOPE DETECTION: Determine if query is about BRAZIL or GLOBAL
    # ═══════════════════════════════════════════════════════════════════════════════
    primary_scope = None
    
    # Global/International keywords → macro scope
    global_keywords = ['fed', 'federal reserve', 'ecb', 'bce', 'boj', 'pboc', 
                      'powell', 'lagarde', 'us economy', 'china', 'europe',
                      'dollar', 'treasury', 'wall street', 's&p', 'nasdaq',
                      'oil', 'crude', 'brent', 'wti', 'gold', 'silver', 'copper',
                      'bonds', 'yields', 'rates', 'equities', 'stocks',
                      'commodities', 'futures', 'forex', 'fx',
                      'iran', 'russia', 'ukraine', 'tariff', 'trump', 'trade war',
                      'cpi', 'nfp', 'payroll', 'inflation', 'gdp',
                      'goldman', 'ubs', 'gavekal', 'rosenberg', 'apollo',
                      'donnelly', 'spectra', 'tony p', 'pasquariello',
                      'deltaone', 'zerohedge', 'macro', 'geopolit',
                      'market', 'markets', 'rally', 'selloff', 'sell-off',
                      'opec', 'hormuz', 'energy', 'lng', 'natural gas']
    
    # Brazilian keywords → brazil scope  
    brazil_keywords = ['copom', 'selic', 'bcb', 'banco central brasil', 'galípolo',
                      'campos neto', 'haddad', 'lula', 'stf', 'congresso',
                      'ibovespa', 'b3', 'real', 'ptax', 'ipca', 'igpm']
    
    query_lower = query.lower()
    
    if 'brazil' in filters and 'macro' in filters:
        # Both selected - detect based on keywords first
        has_global = any(kw in query_lower for kw in global_keywords)
        has_brazil = any(kw in query_lower for kw in brazil_keywords)
        
        if has_global and not has_brazil:
            primary_scope = 'macro'
        elif has_brazil and not has_global:
            primary_scope = 'brazil'
        else:
            # Ambiguous - use Manager Agent, but respect which bot is asking
            _macro_bot = 'macro' in filters  # Macro bot sends macro+brazil+codex
            try:
                from manager_agent import get_query_classification
                classification = get_query_classification(query)
                route = classification['route']
                if _macro_bot:
                    # Macro bot: default to macro unless Manager explicitly says POLITICAL (pure BR politics)
                    if route == 'POLITICAL':
                        primary_scope = 'brazil'
                    else:
                        primary_scope = 'macro'
                else:
                    # Brazil-only bot: default to brazil for economic/political
                    if route in ['ECONOMIC', 'POLITICAL', 'BOTH']:
                        primary_scope = 'brazil'
                    else:
                        primary_scope = 'macro'
            except:
                primary_scope = 'macro' if _macro_bot else 'brazil'
    elif 'brazil' in filters:
        primary_scope = 'brazil'
    elif 'macro' in filters:
        primary_scope = 'macro'
    
    print(f'[8550] Step5 scope: {_t.time()-_s:.1f}s, scope={primary_scope}', flush=True)
    if 'macro' in filters and (primary_scope == 'macro' or primary_scope is None):
        macro_df = df[~df['username'].str.lower().isin(brazilian_usernames)]
        # REMOVED: codex_* exclusion - now included in macro searches
        # Filter out junk items
        macro_df = macro_df[macro_df["is_junk"] != True]
        
        # Try hybrid search with Voyage AI semantic embeddings
        hybrid_result = hybrid_search(query, macro_df, filters, limit, query_understanding=query_understanding)
        
        if hybrid_result is not None and len(hybrid_result) > 0:
            macro_df = hybrid_result
            print(f"🔍 Using Voyage AI semantic search for macro ({len(macro_df)} results)")
        else:
            # Fall back to text-based scoring
            # Get high priority sources for boosting
            high_priority_sources = get_high_priority_sources()
            
            def score_tweet(row):
                text = str(row.get('text', '')).lower()
                keywords = str(row.get('keywords', '')).lower()
                username = str(row.get('username', '')).lower()
                
                # Semantic relevance (text-based)
                semantic_score = sum(1 for term in query_terms if term in text or term in keywords)
                semantic_score += row.get('ai_score', 0) / 10
                
                # Time decay factor
                time_decay = row.get('time_decay', 0.5)
                
                # PRIORITY BOOST - high priority sources get 2.5x weight
                priority = get_source_priority(username)
                priority_mult = _SCORING.get('priority_high', 1.5) if priority == 'high' else (_SCORING.get('priority_low', 0.5) if priority == 'low' else _SCORING.get('priority_normal', 1.0))
                
                # CLASS BOOST (Prompt Boost 2) - source_class 1-5 for Brazil queries
                class_mult = 1.0
                if boost2_enabled and 'brazil' in str(filters).lower():
                    source_class = get_source_class(username)
                    # Class 5 = 1.5x, Class 4 = 1.25x, Class 3 = 1.0x, Class 2 = 0.75x, Class 1 = 0.5x
                    class_mult = {5: 1.5, 4: 1.25, 3: 1.0, 2: 0.75, 1: 0.5}.get(source_class, 1.0)
                
                # Combined score with priority
                base_score = (_SCORING.get('fallback_semantic_weight', 0.75) * semantic_score) + (_SCORING.get('fallback_time_weight', 0.15) * time_decay * 10) + (row.get('ai_score', 5) * _SCORING.get('fallback_ai_score_weight', 0.10))
                
                # OVERNIGHT WEIGHTING - apply special time-based weights if overnight query
                if is_overnight_query(query):
                    doc_dt = row.get('created_at_dt')
                    if doc_dt is not None:
                        overnight_weight, overnight_window = get_overnight_weight(doc_dt)
                        base_score = base_score * overnight_weight
                        # Note: overnight_weight already includes the time-based multiplier
                        # morning (2am-now): 45%, night (17pm-2am): 35%, previous_day: 25%
                
                return base_score * priority_mult * class_mult

            macro_df['relevance'] = macro_df.apply(score_tweet, axis=1)
            macro_df = macro_df.nlargest(limit, 'relevance')
        
        for _, row in macro_df.iterrows():
            tweet_id = row.get('id', '')
            username = row.get('username', '')
            tweet_url = f"https://x.com/{username}/status/{tweet_id}" if tweet_id and username and not str(tweet_id).startswith('codex_') else ''
            urls_field = row.get('urls', '') or ''
            text_urls = re.findall(r'https?://[^\s<>\)]+', str(row.get('text', '')))
            article_url = urls_field if urls_field else (text_urls[0] if text_urls else '')
            
            results['tweets'].append({
                'text': get_best_text(row, 2000),
                'username': username,
                'keywords': row.get('keywords', ''),
                'ai_score': row.get('ai_score', 0),
                'track': 'macro',
                'tweet_url': tweet_url,
                'article_url': article_url
            })
        results['stats']['macro_count'] = len(macro_df)
        print(f'[8550] Step6 macro done: {_t.time()-_s:.1f}s, {len(macro_df)} results', flush=True)
    

    # ═══ INSTITUTION BOOST for MACRO (Feb 2026) + Entity Resolver (Apr 2026) ═══
    _entity_resolved = None
    _entity_boost_limit = 5
    _entity_si = 0.0
    if 'macro' in filters and (primary_scope == 'macro' or primary_scope is None):
        _ib_key_m = None
        _ib_variants_m = None
        _entity_si = (query_understanding or {}).get('source_importance', 0.0)
        _entity_detected = (query_understanding or {}).get('detected_entity')

        if _entity_detected and ENTITY_REGISTRY_LIVE:
            _entity_resolved = _entity_reg.resolve(_entity_detected)
            if _entity_resolved and any(s in _entity_resolved.scope for s in ('macro', 'iran', 'geopolitics')):
                _ib_key_m = f'entity:{_entity_resolved.slug}'
                _ib_variants_m = [_entity_resolved.name] + _entity_resolved.aliases
                _INSTITUTION_USERNAMES[_ib_key_m] = _entity_resolved.all_source_ids
                _entity_boost_limit = _entity_resolved.max_boost_rows if _entity_si >= _entity_resolved.importance_threshold else 5
                print(f"[EntityBoost] Resolved '{_entity_detected}' -> {_entity_resolved.slug} handles={_entity_resolved.all_handles[:5]} mode={_entity_resolved.boost_mode} si={_entity_si:.2f} limit={_entity_boost_limit}", flush=True)
            else:
                _entity_resolved = None
        elif _entity_detected and not ENTITY_REGISTRY_LIVE:
            _shadow = _entity_reg.resolve(_entity_detected)
            if _shadow:
                print(f"[EntityBoost:SHADOW] Would resolve '{_entity_detected}' -> {_shadow.slug} handles={_shadow.all_handles[:5]} mode={_shadow.boost_mode}", flush=True)

        if not _entity_resolved:
            _ib_key_m, _ib_variants_m = _detect_institution(query)

        if _ib_key_m:
            _macro_base = df[~df['username'].str.lower().isin(brazilian_usernames)].copy()
            _ib_extras_m = _institution_boost(_macro_base, results['tweets'], _ib_key_m, _ib_variants_m, limit=_entity_boost_limit)
            if _ib_extras_m:
                results['tweets'] = _ib_extras_m + results['tweets']
                results['stats']['institution_boost'] = len(_ib_extras_m)
                results['stats']['institution_name'] = _ib_key_m
                if _entity_resolved:
                    results['stats']['entity_resolved'] = _entity_resolved.slug
                    results['stats']['entity_boost_mode'] = _entity_resolved.boost_mode
                    results['stats']['entity_handles'] = _entity_resolved.all_handles[:5]
                    _entity_reg._last_resolved = (_entity_resolved, _entity_si)

    if 'brazil' in filters and (primary_scope == 'brazil' or primary_scope is None):
        # ═══════════════════════════════════════════════════════════════════
        # BRAZIL SCOPE - Filtro define ONDE, Manager Agent define COMO
        # Dec 2025: Escopo limpo - só fontes brasileiras
        # ═══════════════════════════════════════════════════════════════════
        
        brazil_df = df[df['username'].str.lower().isin(brazilian_usernames)].copy()
        
        # Manager Agent decide COMO buscar dentro do Brasil
        try:
            from manager_agent import get_query_classification
            from economic_agent import search_economic_content
            import re as regex_module
            
            classification = get_query_classification(query)
            route = classification['route']
            
            if route in ['ECONOMIC', 'BOTH']:
                # ═══ BUSCA ECONÔMICA (Copom, Selic, Juros, PIB) ═══
                econ_results = search_economic_content(query, limit=limit)
                
                for r in econ_results:
                    tweet_id = r.get('id', '')
                    username = r.get('source', '')
                    tweet_url = ''
                    if tweet_id and username and not str(tweet_id).startswith('codex_'):
                        tweet_url = f"https://x.com/{username}/status/{tweet_id}"
                    text = r.get('text', '')
                    text_urls = regex_module.findall(r'https?://[^\s<>)]+', text)
                    article_url = text_urls[0] if text_urls else ''
                    
                    results['tweets'].append({
                        'text': text[:2000] if text else '',
                        'username': username,
                        'keywords': '',
                        'ai_score': int(r.get('score', 0.5) * 10),
                        'track': 'brazil',
                        'tweet_url': tweet_url,
                        'article_url': article_url
                    })
                
                results['stats']['brazil_count'] = len(econ_results)
                print(f"🇧🇷 Brazil ECONOMIC: {len(econ_results)} results")
                # Retorna aqui - não precisa continuar processamento
                
            elif route == 'POLITICAL':
                # ═══ BUSCA POLÍTICA (STF, Lula, Congresso) ═══
                political_vip = ['lula', 'bolsonaro', 'haddad', 'stf', 'supremo', 
                               'congresso', 'senado', 'câmara', 'barroso', 'moraes']
                
                def political_score(row):
                    text = str(row.get('text', '')).lower()
                    score = sum(2 for vip in political_vip if vip in text)
                    # Query term matching
                    for term in query.lower().split():
                        if len(term) > 3 and term in text:
                            score += 1
                    return score
                
                brazil_df['pol_score'] = brazil_df.apply(political_score, axis=1)
                brazil_df = brazil_df[brazil_df['pol_score'] > 0]
                brazil_df = brazil_df.nlargest(limit, 'pol_score')
                
                for _, row in brazil_df.iterrows():
                    tweet_id = row.get('id', '')
                    username = row.get('username', '')
                    tweet_url = f"https://x.com/{username}/status/{tweet_id}" if tweet_id and username and not str(tweet_id).startswith('codex_') else ''
                    urls_field = row.get('urls', '') or ''
                    text_urls = regex_module.findall(r'https?://[^\s<>)]+', str(row.get('text', '')))
                    article_url = urls_field if urls_field else (text_urls[0] if text_urls else '')
                    
                    results['tweets'].append({
                        'text': get_best_text(row, 2000),
                        'username': username,
                        'keywords': row.get('keywords', ''),
                        'ai_score': row.get('ai_score', 0),
                        'track': 'brazil',
                        'tweet_url': tweet_url,
                        'article_url': article_url
                    })
                
                results['stats']['brazil_count'] = len(brazil_df)
                print(f"🇧🇷 Brazil POLITICAL: {len(brazil_df)} results")
                
            else:
                # ═══ BUSCA GERAL (Semântica normal) ═══
                raise Exception("Use general search")
                
        except Exception as e:
            print(f"Agent routing: {e}, using semantic search")
            # Fallback para busca semântica normal
            # Fallback: Semantic search for GENERAL queries
            semantic_results = semantic_search(query, brazil_df, limit=limit*3, query_understanding=query_understanding)
            
            if semantic_results and len(semantic_results) > 5:
                semantic_scores = {idx: score for idx, score in semantic_results}
                brazil_df['semantic_score'] = brazil_df.index.map(lambda x: semantic_scores.get(x, 0))
            else:
                def keyword_score(row):
                    text = str(row.get('text', '')).lower()
                    return sum(1 for term in query.lower().split() if len(term) > 3 and term in text) / 10
                brazil_df['semantic_score'] = brazil_df.apply(keyword_score, axis=1)
            
            brazil_df['relevance'] = brazil_df['semantic_score'] * 10 + brazil_df['ai_score'].fillna(5) * 0.2
            brazil_df = brazil_df.nlargest(limit, 'relevance')
            
            import re as regex_module
            for _, row in brazil_df.iterrows():
                tweet_id = row.get('id', '')
                username = row.get('username', '')
                tweet_url = f"https://x.com/{username}/status/{tweet_id}" if tweet_id and username and not str(tweet_id).startswith('codex_') else ''
                urls_field = row.get('urls', '') or ''
                text_urls = regex_module.findall(r'https?://[^\s<>)]+', str(row.get('text', '')))
                article_url = urls_field if urls_field else (text_urls[0] if text_urls else '')
                
                results['tweets'].append({
                    'text': get_best_text(row, 2000),
                    'username': username,
                    'keywords': row.get('keywords', ''),
                    'ai_score': row.get('ai_score', 0),
                    'track': 'brazil',
                    'tweet_url': tweet_url,
                    'article_url': article_url
                })
            results['stats']['brazil_count'] = len(brazil_df)
            print(f"🇧🇷 Brazil GENERAL: {len(brazil_df)} results")
    
    

    # ═══ INSTITUTION BOOST (Feb 2026) ═══
    # If user asked about a specific institution and brazil results don't mention it,
    # inject keyword-matched articles as fallback
    if 'brazil' in filters and (primary_scope == 'brazil' or primary_scope is None):
        _ib_key, _ib_variants = _detect_institution(query)
        if _ib_key:
            _ib_extras = _institution_boost(
                df[df['username'].str.lower().isin(brazilian_usernames)].copy() if 'brazil_df' not in dir() else brazil_df,
                results['tweets'],
                _ib_key,
                _ib_variants,
                limit=5
            )
            if _ib_extras:
                results['tweets'] = _ib_extras + results['tweets']
                results['stats']['institution_boost'] = len(_ib_extras)
                results['stats']['institution_name'] = _ib_key

    if 'codex' in filters:
        codex_df = df[df['username'].str.startswith('codex_', na=False)]
        codex_df = codex_df[codex_df['is_junk'] != True]
        codex_df = codex_df.nlargest(15, 'ai_score')
        
        for _, row in codex_df.iterrows():
            results['codex'].append({
                'text': get_best_text(row, 3000),
                'source': row.get('username', '').replace('codex_', '').replace('_', ' ').title(),
                'ai_score': row.get('ai_score', 0)
            })
        results['stats']['codex_count'] = len(codex_df)
    
    results['primary_scope'] = primary_scope
    return results


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/query-log')
def api_query_log():
    """Return recent query log entries (last 24h)."""
    import json as _j
    try:
        lines = open(QUERY_LOG_FILE).readlines()
        entries = [_j.loads(l) for l in lines[-200:]]
        return jsonify({'entries': entries, 'count': len(entries)})
    except FileNotFoundError:
        return jsonify({'entries': [], 'count': 0, 'note': 'No queries yet'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/rag', methods=['POST'])
def rag_query():
    """Main RAG endpoint"""
    import time as _t
    _rq_start = _t.time()
    print(f"[8550-RAG] === NEW QUERY at {_t.strftime('%H:%M:%S', _t.localtime())} ===")
    data = request.json
    query = data.get('query', '')
    raw_filters = data.get('filters', ['macro', 'brazil', 'codex'])
    
    # Normalize filters - handle both list ['brazil'] and dict {'source': 'brazil'} formats
    if isinstance(raw_filters, dict):
        # Extract source value from dict format
        source = raw_filters.get('source', '')
        filters = [source] if source else ['macro', 'brazil', 'codex']
    elif isinstance(raw_filters, list):
        filters = raw_filters
    else:
        filters = ['macro', 'brazil', 'codex']
    session_id = data.get('session_id', 'default')
    premade_key = data.get('premade_key', None)
    boost_enabled = data.get('boost_enabled', True)  # ON by default
    boost2_enabled = data.get('boost2_enabled', False)  # Brazil Class prioritization
    
    # Time range from frontend (hours, 0 = all database)
    time_hours = data.get('time_hours', None)
    if time_hours is not None:
        try:
            time_hours = int(time_hours)
        except:
            time_hours = None
    
    # Use premade query if specified
    if premade_key:
        _pq = _LOADED_PROMPTS.get(premade_key) or PREMADE_QUERIES.get(premade_key)
        if _pq:
            query = _pq
        # Set appropriate filters based on premade
        if premade_key == 'macro':
            filters = ['macro']
        elif premade_key == 'brazil':
            filters = ['brazil']
        elif premade_key == 'codex':
            filters = ['codex']
        else:
            filters = ['macro', 'brazil', 'codex']
    
    if not query:
        return jsonify({'error': 'No query provided'}), 400
    
    start_time = datetime.now()
    
    # Query Understanding Agent (Jan 2026)
    # Extracts authors, sources, topics, boosts, and exclusions
    try:
        query_understanding = understand_query(query)
        if query_understanding.get('boost_keywords'):
            print(f"Query Understanding: {len(query_understanding['boost_keywords'])} boost keywords")
        if query_understanding.get('exclusions', {}).get('source_types'):
            print(f"Query Understanding: excluding {query_understanding['exclusions']['source_types']}")
    except Exception as e:
        print(f"Query Understanding error: {e}")
        query_understanding = None
    
    # Get or create session
    if session_id not in chat_sessions:
        chat_sessions[session_id] = []
    
    # For MACRO queries, automatically enhance to include WSJ/Bloomberg/FT insights
    enhanced_query = query
    if 'macro' in filters and 'brazil' not in filters:
        # Add instruction to include major news sources (only if not already mentioned)
        wsj_mentioned = any(x in query.lower() for x in ['wsj', 'wall street', 'bloomberg', 'ft', 'financial times'])
        if not wsj_mentioned:
            enhanced_query = f"{query} (Include relevant insights from WSJ, Bloomberg, and Financial Times)"
    
    # Retrieve context
    print(f'[8550-RAG] Step-A: calling get_rag_context...', flush=True)
    context = get_rag_context(enhanced_query, filters, limit=200, query_understanding=query_understanding, boost2_enabled=boost2_enabled, time_hours=time_hours)
    rows_found = context.get('time_context', {}).get('rows_in_time_window', len(context.get('tweets', [])))
    print(f'[8550-RAG] Step-B: got context, {len(context.get("tweets",[]))} tweets, {rows_found} rows in window', flush=True)

    # If 0 rows in time window and we have a specific time_hours, force cache refresh and retry once
    if rows_found == 0 and time_hours and time_hours > 0:
        print(f'[8550-RAG] 0 rows with {time_hours}h window — forcing cache refresh and retrying...', flush=True)
        try:
            import lancedb as _lb_retry
            _retry_db = _get_rag_db()  # reuse singleton
            _retry_table = _retry_db.open_table('unified_feed')
            _feed_cache._do_load(_retry_table)
            print(f'[8550-RAG] Cache refreshed, retrying query...', flush=True)
            context = get_rag_context(enhanced_query, filters, limit=200, query_understanding=query_understanding, boost2_enabled=boost2_enabled, time_hours=time_hours)
            rows_found = context.get('time_context', {}).get('rows_in_time_window', len(context.get('tweets', [])))
            print(f'[8550-RAG] Retry result: {rows_found} rows in window', flush=True)
        except Exception as e:
            print(f'[8550-RAG] Cache refresh retry failed: {e}', flush=True)
    
    # Structured query log
    try:
        _tc = context.get('time_context', {})
        log_query({
            'query_type': premade_key or 'freetext',
            'query_preview': query[:150],
            'filters': filters,
            'time_hours_requested': time_hours,
            'time_desc': _tc.get('temporal_filter', '?'),
            'data_newest': _tc.get('data_newest', '?'),
            'data_age_hours': _tc.get('data_age_hours', '?'),
            'rows_in_window': len(context.get('tweets', [])),
            'total_cached_rows': _tc.get('total_rows', '?'),
            'valid_date_rows': _tc.get('valid_dates', '?'),
            'after_junk_filter': _tc.get('after_junk', '?'),
            'elapsed_sec': round((datetime.now() - start_time).total_seconds(), 1),
        })
    except Exception as _le:
        print(f'[QueryLog] Failed: {_le}')
    
    # Build context string
    context_parts = []
    
    # Source name mapping for clearer identification
    SOURCE_NAMES = {
        'gs_research': '📊 GOLDMAN SACHS RESEARCH',
        'codex_goldman': '📊 GOLDMAN SACHS',
        'codex_gavekal': '📈 GAVEKAL RESEARCH',
        'codex_ubs': '📈 UBS RESEARCH',
        'codex_rosenberg': '📈 ROSENBERG RESEARCH',
        'codex_apollo': '📈 APOLLO (Torsten Slok)',
        'codex_torsten': '📈 TORSTEN SLOK',
        'codex_barrons': "📰 BARRON'S",
        'codex_bloomberg': '📰 BLOOMBERG',
        'codex_itau': '📈 ITAU RESEARCH',
        'codex_itau_politico': '📈 ITAU RESEARCH',
        'codex_spectra': '📈 SPECTRA MARKETS',
        # Podcast / YouTube transcripts
        'podcast_youtube_UCWOnz7XxWPScqfF1ejt': '🎙️ PROFESSOR JIANG',
        'podcast_youtube_UCNye-wNBqNL5ZzHSJj3': '🎙️ AL JAZEERA ENGLISH (YouTube)',
        'podcast_youtube_UCZFCDIHTe9HGxtIuVDp': '🎙️ GLENN DIESEN (YouTube)',
        'podcast_youtube_UCK0z0_5uL7mb9IjntOK': '🎙️ THE ATLANTIC (YouTube)',
        'podcast_youtube_UC11aHtNnc5bEPLI4jf6': '🎙️ PREDICTIVE HISTORY (YouTube)',
        'podcast_youtube_UCIALMKvObZNtJ6AmdCL': '🎙️ BLOOMBERG TELEVISION (YouTube)',
        'podcast_triggernometry': '🎙️ TRIGGERNOMETRY',
        'podcast_conflicted': '🎙️ CONFLICTED',
        'podcast_foreign_policy_live': '🎙️ FOREIGN POLICY LIVE',
        'podcast_gzero_world_with_ian_bremmer': '🎙️ GZERO WORLD (Ian Bremmer)',
        'podcast_bloomberg_surveillance': '🎙️ BLOOMBERG SURVEILLANCE',
        'podcast_bloomberg_odd_lots': '🎙️ BLOOMBERG ODD LOTS',
        'podcast_bloomberg_trumponomics': '🎙️ BLOOMBERG TRUMPONOMICS',
        'podcast_bloomberg_daybreak_us_edition': '🎙️ BLOOMBERG DAYBREAK',
        'podcast_goldman_exchanges': '🎙️ GOLDMAN SACHS EXCHANGES',
        'podcast_jpmorgan_at_any_rate': '🎙️ JPMORGAN AT ANY RATE',
        'podcast_jpmorgan_making_sense': '🎙️ JPMORGAN MAKING SENSE',
        'podcast_jpmorgan_global_data_pod': '🎙️ JPMORGAN GLOBAL DATA POD',
        'podcast_ubs_on_air_market_moves': '🎙️ UBS ON-AIR MARKET MOVES',
    }
    
    def get_source_display(username):
        """Get friendly display name for source — checks entity registry first"""
        _uname = username.lower()
        if _uname in _ENTITY_SOURCE_NAMES:
            return f"{_ENTITY_SOURCE_NAMES[_uname]} (@{username})"
        elif username in SOURCE_NAMES:
            return f"{SOURCE_NAMES[username]} (@{username})"
        elif username.startswith('codex_'):
            clean = username.replace('codex_', '').replace('_', ' ').title()
            return f"{clean} (@{username})"
        elif username.startswith('gs_'):
            return f"Goldman Sachs (@{username})"
        return f"@{username}"
    
    if context['tweets']:
        # Check if institution boost items are present — tell the LLM to use them
        boost_items = [t for t in context['tweets'][:10] if 'institution' in t.get('track', '')]
        if boost_items:
            boost_source = get_source_display(boost_items[0]['username'])
            is_podcast_boost = any(t.get('username', '').startswith('podcast_') for t in boost_items)
            podcast_note = " These are podcast/YouTube transcript excerpts — summarize the key topics, guests, and arguments discussed." if is_podcast_boost else ""
            context_parts.append(
                f"=== CRITICAL: The first {len(boost_items)} items below are DIRECTLY FROM {boost_source} — "
                f"the source the user asked about. You MUST analyze and cite these items. "
                f"Do NOT say 'no content found' or 'not in my feed' — the data IS here.{podcast_note} ==="
            )
        _entity_resolved, _entity_si = getattr(_entity_reg, '_last_resolved', (None, 0.0))
        _entity_reg._last_resolved = (None, 0.0)
        if _entity_resolved and _entity_si >= _entity_resolved.importance_threshold and _entity_resolved.notes:
            _enotes = _entity_resolved.notes.split(chr(10) + chr(10))[0][:500]
            context_parts.append(
                f"=== ENTITY CONTEXT: {_entity_resolved.name} ({_entity_resolved.type}) ==="
                f"\n{_enotes}\n"
                f"=== END ENTITY CONTEXT ==="
            )
            print(f"[EntityBoost] Injected notes for {_entity_resolved.name} ({len(_enotes)} chars)", flush=True)
        context_parts.append("=== FINANCIAL INTELLIGENCE (Quality Vetted) ===")
        for t in context["tweets"][:200]:
            url_info = ""
            if t.get('tweet_url'):
                url_info = f" [Tweet: {t['tweet_url']}]"
            if t.get('article_url'):
                url_info += f" [Article: {t['article_url']}]"
            source_display = get_source_display(t['username'])
            kw_info = f" Keywords: {t['keywords'][:200]}" if t.get('keywords') else ""
            context_parts.append(f"{source_display} [{t['track'].upper()}] (AI:{t['ai_score']}/10):{kw_info}\n{t['text'][:5000]}{url_info}")
    
    if context['codex']:
        context_parts.append("\n=== CODEX EMAIL INTELLIGENCE ===")
        for c in context["codex"][:80]:
            context_parts.append(f"FROM {c['source']}: {c['text'][:5000]}")
    
    context_str = "\n".join(context_parts)
    
    # Get time context
    time_ctx = context.get('time_context', {})
    
    # Detect if this is a political/institutional query
    is_political = detect_query_type(query)
    
    # Build connection analysis instructions for political queries
    connection_instructions = """
=== POLITICAL/INSTITUTIONAL ANALYSIS MODE ===
This query involves political/institutional topics. You MUST:

1. **IDENTIFY THE KEY ACTORS** and their roles:
   - Government (Executivo): President Lula, ministers, AGU
   - Legislature (Legislativo): Senate (Alcolumbre), Chamber, party leaders
   - Judiciary (Judiciário): STF ministers (Gilmar, Moraes, Toffoli, etc.)
   
2. **MAP THE CONNECTIONS** between events:
   - What decision/action triggered reactions?
   - Who is responding to whom?
   - What are the underlying power dynamics?
   - Are there ongoing disputes or negotiations?
   
3. **EXPLAIN THE INSTITUTIONAL LINKS**:
   - How does STF decision X affect Senate action Y?
   - What projects/nominations are in dispute?
   - What constitutional mechanisms are being used?
   
4. **PROVIDE DEEP CONTEXT**:
   - Historical precedents
   - Ongoing institutional tensions
   - Strategic motivations of each actor
   
5. **STRUCTURE YOUR ANALYSIS** as:
   - Executive Summary (2-3 sentences)
   - Key Actors & Their Positions
   - The Main Conflict/Issue
   - How Events Are Connected
   - Implications & What to Watch

DO NOT give superficial summaries. Provide DEEP INSTITUTIONAL ANALYSIS with connections between events.
""" if is_political else ""
    
    # SOUL VARIANT SELECTION (Mar 2026)
    # Brazil bot sends filters=["brazil"] only → brazil soul (Portuguese)
    # Macro bot sends filters=["macro","brazil","codex"] → global soul (English) by default
    # Only use brazil soul for macro bot if query is EXPLICITLY about Brazil
    _query_scope = context.get('primary_scope', None)
    _brazil_only = 'brazil' in filters and 'macro' not in filters
    if _brazil_only:
        soul_variant = 'brazil'
    elif _query_scope == 'brazil' and _brazil_only:
        soul_variant = 'brazil'
    else:
        soul_variant = 'global'
    
    # Calendar context: always inject for Macro so Ask M3xA has full day-by-day data (same as when user asks in chat)
    calendar_context = ""
    calendar_instruction = ""
    mandatory_table_block = ""
    force_table_response = ""
    if "macro" in filters:
        calendar_context = get_economic_context()
        if calendar_context:
            print(f"📅 Calendar context activated ({len(calendar_context)} chars)")
            calendar_instruction = (
                "\nIMPORTANT (US/Brazil economic calendar):\n"
                "0. SCOPE: If the user asks about the US calendar, this week US, or US releases only—show and discuss ONLY the US ECONOMIC CALENDAR. Do NOT show or mention Brazil. Only include the BRAZIL ECONOMIC CALENDAR when the user explicitly asks about Brazil, Brazil calendar, or the full/both calendars.\n"
                "1. Use ONLY the calendar sections above (US and/or Brazil as per scope). Do not invent events or dates from memory.\n"
                "2. When answering about the US calendar: give the COMPLETE US day-by-day list—every event for each date, using the exact names. Do not summarize or omit events; include the full list. Do not add Brazil events.\n"
                "3. FOMC: NEVER say there is an 'FOMC meeting' or 'FOMC rate decision' on a date unless the calendar explicitly shows an event with 'Interest Rate Decision' or 'rate decision' for that date. Minutes/documentation releases are not meetings.\n"
                "4. After the calendar list, qualify with: what actually happened (actuals vs forecast), relevant views from the context (analysts, WSJ, Bloomberg, FT), and what is most important for markets.\n"
                "5. When publishing release tables (e.g. Morning/Afternoon Releases): (a) Use the 'US CALENDAR — TABLE FORMAT (times UTC-3)' section from context if present—copy or adapt it. (b) NEVER use EST or Eastern Time. ALL times in release tables MUST be in UTC-3 (Brazil). Conversion: EST + 2h = UTC-3 (e.g. 08:30 EST = 10:30 UTC-3, 14:00 EST = 16:00 UTC-3). (c) Structure: per day, group into 'Morning (UTC-3)' (00:00–11:59 UTC-3) and 'Afternoon (UTC-3)' (12:00–23:59 UTC-3). Table columns: Time (UTC-3) | Release | Actual | Expected | Previous | Status | Importance. Label the time column 'Time (UTC-3)'.\n"
            )
        # When user asks for a TABLE or for the US/economic CALENDAR, generate the real UTC-3 table and require output verbatim
        _q = query.lower()
        _want_table = (
            ("calendar" in _q and "table" in _q)
            or ("show" in _q and "calendar" in _q and "table" in _q)
            or ("us" in _q and "calendar" in _q and ("table" in _q or "show" in _q))
            or ("economic calendar" in _q and ("table" in _q or "show" in _q or "this week" in _q))
        )
        if _want_table:
            try:
                from datetime import datetime as _dt, timedelta as _td
                _today = _dt.now().date()
                _week_ago = (_today - _td(days=3)).isoformat()
                _two_weeks = (_today + _td(days=60)).isoformat()
                _table = format_us_calendar_tables_utc3(_week_ago, _two_weeks)
                if _table and len(_table.strip()) > 0:
                    force_table_response = (
                        "## US Economic Calendar — This Week (UTC-3)\n\n"
                        + _table.strip()
                    )
                    mandatory_table_block = (
                        "\n\n=== MANDATORY: US CALENDAR TABLE (UTC-3) — OUTPUT THIS TABLE FIRST, EXACTLY AS SHOWN ===\n"
                        "The user asked for a table. You MUST start your response with the following table. Do NOT use EST. Do NOT change column order. Do NOT replace with a different table. Copy it exactly, then add your summary or watchlist after.\n\n"
                        + _table.strip() + "\n\n"
                        "After the table above, you may add a short 'Summary' or 'Watchlist' section. All times in the table are already in UTC-3 (Brazil).\n"
                    )
                    print(f"📅 Mandatory calendar table injected ({len(_table)} chars) — user asked for table")
            except Exception as _e:
                print(f"Mandatory calendar table failed: {_e}")

    # Agent Central Hub — orchestrates markets, polymarket, polls, boost
    agent_context = ""
    polymarket_injected = False
    polymarket_topics = []
    boost_content = ""
    boost_instruction = ""
    if AGENT_HUB_AVAILABLE:
        try:
            hub_result = agent_hub.get_context(
                query=query,
                mode='general',
                time_hours=time_hours,
                boost_enabled=(boost_enabled and 'macro' in filters),
                filters=filters,
                df=_feed_cache._df,
            )
            agent_context = hub_result.get('context', '')
            if 'polymarket' in hub_result.get('agents', []):
                polymarket_injected = True
            if agent_context:
                print(f"[AgentHub] Injected: {hub_result.get('details', {})} = {hub_result.get('chars', 0)} chars")
        except Exception as e:
            print(f"[AgentHub] Error, falling back to direct agents: {e}")
            # Fallback to direct calls if hub fails
            AGENT_HUB_AVAILABLE_LOCAL = False
    else:
        # Legacy fallback: direct agent calls
        poll_context_text = ""
        if should_include_polls(query):
            poll_context_text = get_poll_context() or ""
        market_live = ""
        if MARKETS_AGENT_AVAILABLE:
            try:
                market_live = ma_get_live_market_context() or ""
            except:
                pass
        pm_text = ""
        if POLYMARKET_AVAILABLE:
            try:
                pm_ctx, pm_topics = pm_get_context_for_query(query)
                if pm_ctx:
                    pm_text = pm_ctx
                    polymarket_injected = True
                    polymarket_topics = pm_topics
            except:
                pass
        if boost_enabled and 'macro' in filters:
            try:
                boost_days = max(1, time_hours / 24) if time_hours and time_hours > 0 else 7
                boost_content, boost_instruction = build_boost_prompt('/home/ubuntu/m3xa/lancedb_clean', query, days=int(boost_days))
            except:
                pass
        agent_context = "\n\n".join(x for x in [market_live, pm_text, poll_context_text, boost_content] if x)
    
    # ═══════════════════════════════════════════════════════════════════════
    # SYSTEM PROMPT — Soul file + dynamic context (Phase 1: Feb 2026)
    # ═══════════════════════════════════════════════════════════════════════
    soul_text = _load_soul(variant=soul_variant)

    system_prompt = f"""{soul_text}

=== CURRENT TIME ===
Query Time: {time_ctx.get('query_time_brazil', 'Unknown')}
Server Time (UTC): {time_ctx.get('query_time', 'Unknown')}

=== DATA FRESHNESS ===
Data Range: {time_ctx.get('data_oldest', 'Unknown')} to {time_ctx.get('data_newest', 'Unknown')}
Data Age: {time_ctx.get('data_age_hours', 'Unknown')} hours since newest data
Freshness Status: {time_ctx.get('data_freshness', 'Unknown')}
Temporal Filter Applied: {time_ctx.get('temporal_filter', 'None')}

{calendar_context}
{calendar_instruction}
{mandatory_table_block}



=== AGENT CONTEXT (markets, prediction markets, polls, priority sources) ===
{agent_context}

=== CURRENT DATA CONTEXT ===
{context_str}

=== DATA STATISTICS ===
{json.dumps(context.get('stats', {}))}

When describing any country's monetary policy (e.g. Brazil BCB/COPOM/Selic), strictly reflect what the RETRIEVED SOURCES say. Do not infer hiking vs cutting from general knowledge. If sources are ambiguous or conflict, say so and cite the disagreement."""

    # Build messages
    messages = []
    # Initialize session if not exists
    if session_id not in chat_sessions:
        chat_sessions[session_id] = []
    for msg in chat_sessions[session_id][-6:]:
        messages.append(msg)
    messages.append({"role": "user", "content": query})
    
    try:
        # Deterministic table mode: for explicit US/economic calendar table requests,
        # return the server-generated UTC-3 table directly (no LLM rewrite).
        if force_table_response:
            assistant_response = force_table_response
            print("📅 Deterministic calendar table response returned (LLM bypass)")
        else:
            client = anthropic.Anthropic(api_key=API_KEY)
            
            # Streaming with extended thinking for deeper reasoning
            assistant_response = ""
            with client.messages.stream(
                model="claude-sonnet-4-6",
                max_tokens=8000,
                thinking={"type": "enabled", "budget_tokens": 5000},
                system=system_prompt,
                messages=messages,
                timeout=120.0,
            ) as stream:
                for text in stream.text_stream:
                    assistant_response += text
                    _tg_stream_put(session_id, text)
                # Capture stop reason to detect max_tokens truncation
                try:
                    _final_msg = stream.get_final_message()
                    _stop_reason = _final_msg.stop_reason
                except Exception:
                    _stop_reason = "end_turn"
            # Auto-continuation: if Anthropic hit token limit, keep going until end_turn
            _continuation_count = 0
            _MAX_CONTINUATIONS = 3
            while _stop_reason == "max_tokens" and _continuation_count < _MAX_CONTINUATIONS:
                _continuation_count += 1
                print(f"[RAG] Auto-continuation {_continuation_count}/{_MAX_CONTINUATIONS} (stop_reason=max_tokens)", flush=True)
                _tg_stream_put(session_id, chr(10)+chr(10))
                # Append what we have so far as assistant turn, then ask to continue
                _cont_messages = messages + [
                    {"role": "assistant", "content": assistant_response},
                    {"role": "user", "content": "Continue from exactly where you left off. Do not repeat anything already written."},
                ]
                _cont_response = ""
                with client.messages.stream(
                    model="claude-sonnet-4-6",
                    max_tokens=8000,
                    system=system_prompt,
                    messages=_cont_messages,
                    timeout=120.0,
                ) as _cont_stream:
                    for _ct in _cont_stream.text_stream:
                        _cont_response += _ct
                        _tg_stream_put(session_id, _ct)
                    try:
                        _stop_reason = _cont_stream.get_final_message().stop_reason
                    except Exception:
                        _stop_reason = "end_turn"
                assistant_response += chr(10)+chr(10) + _cont_response
                print(f"[RAG] Continuation {_continuation_count} done: {len(_cont_response)} chars, stop={_stop_reason}", flush=True)
            if _continuation_count > 0:
                print(f"[RAG] Auto-continuation complete: {_continuation_count} extra call(s), total {len(assistant_response)} chars", flush=True)
            _tg_stream_put(session_id, None)  # signal done after all continuations
        
        # ═══════════════════════════════════════════════════════════════════════════
        # SELF-EVALUATION SYSTEM (Dec 2025)
        # Evaluate response quality, regenerate if needed
        # ═══════════════════════════════════════════════════════════════════════════
        evaluation_data = None
        warning_note = ""
        
        if EVALUATION_ENABLED and response_evaluator:
            should_eval, query_type = response_evaluator.should_evaluate(query)
            
            if should_eval:
                print(f"🔍 Evaluating response for query type: {query_type}")
                evaluation = response_evaluator.evaluate(query, assistant_response)
                evaluation_data = {
                    'scores': evaluation.get('scores', {}),
                    'total_score': evaluation.get('total_score', 0),
                    'passed': evaluation.get('passed', True),
                    'issues': evaluation.get('issues', [])[:3]
                }
                
                # Check if regeneration needed
                if False:  # DISABLED - self-evaluation removed
                    print(f"⚠️ Score {evaluation.get('total_score'):.1f} < 7.0, regenerating...")
                    
                    # Add improvement hint to system prompt
                    improvement_hint = f"""

IMPORTANT IMPROVEMENT NEEDED:
The previous response had these issues: {', '.join(evaluation.get('issues', [])[:3])}
Suggestions: {evaluation.get('suggestions', '')}

Please generate an improved response that:
- Clearly explains what each percentage/number represents
- Does not mix different metrics without context
- Only states facts that can be verified from the data
"""
                    enhanced_prompt = system_prompt + improvement_hint
                    
                    # Try regeneration
                    try:
                        # Streaming for regen
                        new_response = ""
                        with client.messages.stream(
                            model="claude-sonnet-4-6",
                            max_tokens=8000,
                            thinking={"type": "enabled", "budget_tokens": 5000},
                            system=enhanced_prompt,
                            messages=messages,
                            timeout=120.0,
                        ) as regen_stream:
                            for text in regen_stream.text_stream:
                                new_response += text
                        
                        # Re-evaluate
                        regen_eval = response_evaluator.evaluate(query, new_response)
                        
                        if regen_eval.get('total_score', 0) > evaluation.get('total_score', 0):
                            print(f"✅ Regeneration improved score: {evaluation.get('total_score'):.1f} → {regen_eval.get('total_score'):.1f}")
                            assistant_response = new_response
                            evaluation = regen_eval
                            evaluation_data = {
                                'scores': regen_eval.get('scores', {}),
                                'total_score': regen_eval.get('total_score', 0),
                                'passed': regen_eval.get('passed', True),
                                'issues': regen_eval.get('issues', [])[:3],
                                'was_regenerated': True
                            }
                        else:
                            print(f"❌ Regeneration didn't improve, keeping original")
                    except Exception as regen_err:
                        print(f"⚠️ Regeneration failed: {regen_err}")
                
                # Add warning note if score between 6 and 7
                if evaluation.get('needs_warning', False):
                    warning_note = response_evaluator.generate_warning_note(evaluation.get('issues', []))
                    assistant_response = assistant_response + warning_note
                    print(f"📝 Added quality warning note (score: {evaluation.get('total_score'):.1f})")
                
                print(f"✅ Evaluation complete: score={evaluation.get('total_score'):.1f}, passed={evaluation.get('passed')}")
            else:
                print(f"⏭️ Skipping evaluation for query type: {query_type}")
        
        # Save to session
        chat_sessions[session_id].append({"role": "user", "content": query})
        chat_sessions[session_id].append({"role": "assistant", "content": assistant_response})
        
        if len(chat_sessions[session_id]) > 20:
            chat_sessions[session_id] = chat_sessions[session_id][-20:]
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        # Save conversation for learning
        sources_used = [{'username': t.get('username'), 'text': t.get('text', '')[:100]} for t in context.get('tweets', [])[:5]]
        conversation_id = save_conversation(
            session_id=session_id,
            query=query,
            response=assistant_response,
            filters=filters,
            sources_used=sources_used,
            response_time=elapsed
        )
        
        # Save evaluation if performed
        if evaluation_data and response_evaluator:
            try:
                response_evaluator.save_evaluation(
                    conversation_id=conversation_id,
                    query_type=query_type if 'query_type' in dir() else 'general',
                    evaluation=evaluation if 'evaluation' in dir() else {},
                    was_regenerated=evaluation_data.get('was_regenerated', False)
                )
            except Exception as eval_save_err:
                print(f"⚠️ Could not save evaluation: {eval_save_err}")
        
        # Store for #continue: last response per session (keyed by session_id for bot lookup)
        _pending_continuation[session_id] = {
            'query': query,
            'response_so_far': assistant_response,
            'stop_reason': _stop_reason if "_stop_reason" in dir() else "end_turn",
        }
        return jsonify({
            'response': assistant_response,
            'conversation_id': conversation_id,
            'evaluation': evaluation_data,
            'sources': {
                'tweets': len(context['tweets']),
                'codex': len(context['codex']),
                'macro': context['stats'].get('macro_count', 0),
                'brazil': context['stats'].get('brazil_count', 0)
            },
            'time_context': context.get('time_context', {}),
            'elapsed_seconds': round(elapsed, 1),
            'session_id': session_id
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/clear', methods=['POST'])
def clear_session():
    data = request.json
    session_id = data.get('session_id', 'default')
    if session_id in chat_sessions:
        del chat_sessions[session_id]
    return jsonify({'status': 'cleared'})


# Import pandas for the context function
import pandas as pd
from brazil_vip_config import BRAZIL_SYNONYMS, get_vip_priority, BRAZIL_VIP



# ═══════════════════════════════════════════════════════════════════════════
# RAG LEARNING SYSTEM (Dec 2025)
# Archive conversations, collect feedback, build learning rules
# ═══════════════════════════════════════════════════════════════════════════

RAG_LEARNING_DB = '/home/ubuntu/argus/newspaper_project/rag_learning.db'

def _init_learning_db():
    try:
        conn = sqlite3.connect(RAG_LEARNING_DB)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            query TEXT,
            response TEXT,
            filters TEXT,
            sources_used TEXT,
            response_time_seconds REAL,
            timestamp TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS response_evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER,
            scores TEXT,
            total_score REAL,
            passed INTEGER,
            issues TEXT,
            timestamp TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS learning_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_type TEXT,
            pattern TEXT,
            action TEXT,
            priority INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1
        )''')
        conn.commit()
        conn.close()
        print("[LEARNING-DB] rag_learning.db initialized", flush=True)
    except Exception as e:
        print(f"[LEARNING-DB] Init error: {e}", flush=True)

_init_learning_db()

def save_conversation(session_id, query, response, filters, sources_used, response_time):
    """Archive a conversation to the database"""
    try:
        conn = sqlite3.connect(RAG_LEARNING_DB)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO conversations (session_id, query, response, filters, sources_used, response_time_seconds)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (session_id, query, response, json.dumps(filters), json.dumps(sources_used), response_time))
        conversation_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return conversation_id
    except Exception as e:
        print(f"Error saving conversation: {e}")
        return None

def get_learning_rules():
    """Get active learning rules to inject into prompts"""
    try:
        conn = sqlite3.connect(RAG_LEARNING_DB)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT rule_type, pattern, action FROM learning_rules 
            WHERE active = 1 ORDER BY priority DESC
        ''')
        rules = cursor.fetchall()
        conn.close()
        return rules
    except:
        return []

def get_good_examples(query_type=None, limit=3):
    """Get good response examples for few-shot learning"""
    try:
        conn = sqlite3.connect(RAG_LEARNING_DB)
        cursor = conn.cursor()
        if query_type:
            cursor.execute('''
                SELECT example_query, example_response FROM good_examples 
                WHERE query_type = ? ORDER BY created_at DESC LIMIT ?
            ''', (query_type, limit))
        else:
            cursor.execute('''
                SELECT example_query, example_response FROM good_examples 
                ORDER BY created_at DESC LIMIT ?
            ''', (limit,))
        examples = cursor.fetchall()
        conn.close()
        return examples
    except:
        return []

@app.route('/api/cache-invalidate', methods=['POST'])
def cache_invalidate():
    """Mark FeedCache as dirty so next query triggers a background refresh.
    Called by gateway-insert, iran_intel_scraper, and other inserters.
    DEBOUNCED: Does NOT force an immediate reload (which takes 3-12 min and causes
    memory bloat when called 50+ times/hour). Instead, sets loaded_at to 0 so the
    next get_df() call triggers a background refresh within TTL."""
    try:
        _feed_cache._loaded_at = 0  # Mark stale — next get_df() will refresh in background
        return jsonify({'status': 'ok', 'message': 'Cache marked dirty (will refresh on next query)',
                       'rows': len(_feed_cache._df) if _feed_cache._df is not None else 0})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)[:200]}), 500


@app.route('/api/feedback', methods=['POST'])
def submit_feedback():
    """Submit feedback on a RAG response"""
    try:
        data = request.json
        conversation_id = data.get('conversation_id')
        rating = data.get('rating')  # 'good', 'bad', 'partial'
        correction = data.get('correction', '')
        what_was_wrong = data.get('what_was_wrong', '')
        
        conn = sqlite3.connect(RAG_LEARNING_DB)
        cursor = conn.cursor()
        
        # Save feedback
        cursor.execute('''
            INSERT INTO feedback (conversation_id, rating, correction, what_was_wrong)
            VALUES (?, ?, ?, ?)
        ''', (conversation_id, rating, correction, what_was_wrong))
        feedback_id = cursor.lastrowid
        
        # If marked as good, save as example
        if rating == 'good' and conversation_id:
            cursor.execute('SELECT query, response FROM conversations WHERE id = ?', (conversation_id,))
            row = cursor.fetchone()
            if row:
                cursor.execute('''
                    INSERT INTO good_examples (query_type, example_query, example_response, why_good, conversation_id)
                    VALUES (?, ?, ?, ?, ?)
                ''', ('user_approved', row[0], row[1], 'User marked as good', conversation_id))
        
        # If correction provided, consider creating a learning rule
        if what_was_wrong and rating == 'bad':
            # Extract potential patterns
            if 'missed' in what_was_wrong.lower():
                cursor.execute('''
                    INSERT INTO learning_rules (rule_type, pattern, action, created_from_feedback_id)
                    VALUES (?, ?, ?, ?)
                ''', ('search_deeper', what_was_wrong, 'Read more thoroughly when user mentions this topic', feedback_id))
            elif 'wrong' in what_was_wrong.lower() or 'incorrect' in what_was_wrong.lower():
                cursor.execute('''
                    INSERT INTO learning_rules (rule_type, pattern, action, created_from_feedback_id)
                    VALUES (?, ?, ?, ?)
                ''', ('verify_facts', what_was_wrong, 'Double-check facts about this topic', feedback_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'feedback_id': feedback_id, 'message': 'Feedback recorded. Thank you!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/learning-stats', methods=['GET'])
def get_learning_stats():
    """Get learning system statistics"""
    try:
        conn = sqlite3.connect(RAG_LEARNING_DB)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM conversations')
        total_conversations = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM feedback')
        total_feedback = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM feedback WHERE rating = 'good'")
        good_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM feedback WHERE rating = 'bad'")
        bad_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM learning_rules WHERE active = 1')
        active_rules = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM good_examples')
        good_examples = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'total_conversations': total_conversations,
            'total_feedback': total_feedback,
            'good_ratings': good_count,
            'bad_ratings': bad_count,
            'satisfaction_rate': round(good_count / total_feedback * 100, 1) if total_feedback > 0 else 0,
            'active_rules': active_rules,
            'good_examples': good_examples
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    """Get archived conversations"""
    try:
        limit = request.args.get('limit', 50, type=int)
        conn = sqlite3.connect(RAG_LEARNING_DB)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.id, c.session_id, c.query, c.response, c.timestamp, 
                   f.rating, f.correction
            FROM conversations c
            LEFT JOIN feedback f ON c.id = f.conversation_id
            ORDER BY c.timestamp DESC LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        conn.close()
        
        conversations = []
        for row in rows:
            conversations.append({
                'id': row[0],
                'session_id': row[1],
                'query': row[2],
                'response': row[3][:500] + '...' if len(row[3]) > 500 else row[3],
                'timestamp': row[4],
                'rating': row[5],
                'correction': row[6]
            })
        
        return jsonify({'conversations': conversations})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>🧠 M3xA - Market Augmented Awareness Agent</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, sans-serif;
            background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
            min-height: 100vh;
            color: #e0e0e0;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        header {
            text-align: center;
            padding: 30px 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            margin-bottom: 30px;
        }
        
        h1 {
            font-size: 2.5em;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 10px;
        }
        
        .subtitle {
            color: #888;
            font-size: 1.1em;
        }
        
        .quick-buttons {
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            justify-content: center;
            margin-bottom: 30px;
        }
        
        .quick-btn {
            padding: 14px 24px;
            border-radius: 12px;
            border: 1px solid rgba(102, 126, 234, 0.3);
            background: rgba(102, 126, 234, 0.1);
            color: #a0a0ff;
            cursor: pointer;
            font-size: 15px;
            font-weight: 500;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .quick-btn:hover {
            background: rgba(102, 126, 234, 0.25);
            border-color: rgba(102, 126, 234, 0.6);
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(102, 126, 234, 0.2);
        }
        
        .quick-btn.active {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-color: transparent;
        }
        
        .input-section {
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            padding: 20px;
            margin-bottom: 30px;
        }
        
        .input-section label {
            display: block;
            margin-bottom: 12px;
            color: #888;
            font-size: 14px;
        }
        
        .input-row {
            display: flex;
            gap: 12px;
        }
        
        .input-row input {
            flex: 1;
            padding: 16px 20px;
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.15);
            background: rgba(255,255,255,0.08);
            color: white;
            font-size: 16px;
            outline: none;
            transition: all 0.3s;
        }
        
        .input-row input:focus {
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.2);
        }
        
        .input-row input::placeholder {
            color: #666;
        }
        
        .input-row button {
            padding: 16px 32px;
            border-radius: 12px;
            border: none;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .input-row button:hover {
            transform: scale(1.02);
            box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4);
        }
        
        .input-row button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        
        .response-section {
            background: rgba(255,255,255,0.03);
            border-radius: 16px;
            border: 1px solid rgba(255,255,255,0.08);
            min-height: 400px;
        }
        
        .response-header {
            padding: 16px 24px;
            border-bottom: 1px solid rgba(255,255,255,0.08);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .response-header h3 {
            color: #888;
            font-weight: 500;
        }
        
        .response-meta {
            display: flex;
            gap: 20px;
            font-size: 13px;
            color: #666;
        }
        
        .response-body {
            padding: 24px;
            line-height: 1.8;
            font-size: 15px;
        }
        
        .response-body.empty {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 350px;
            color: #555;
        }
        
        .response-body.empty .icon {
            font-size: 4em;
            margin-bottom: 20px;
            opacity: 0.3;
        }
        
        .response-body h2 {
            color: #667eea;
            margin: 24px 0 16px 0;
            font-size: 1.4em;
            border-bottom: 2px solid rgba(102, 126, 234, 0.3);
            padding-bottom: 8px;
        }
        
        .response-body h3 {
            color: #a0a0ff;
            margin: 20px 0 12px 0;
            font-size: 1.2em;
        }
        
        .response-body p {
            margin-bottom: 16px;
        }
        
        .response-body strong {
            color: #667eea;
        }
        
        .response-body em {
            color: #a0a0ff;
            font-style: italic;
        }
        
        .response-body a {
            color: #4da6ff;
            text-decoration: none;
        }
        
        .response-body a:hover {
            text-decoration: underline;
        }
        
        .response-body ul, .response-body ol {
            margin: 12px 0 12px 24px;
        }
        
        .response-body li {
            margin-bottom: 8px;
        }
        
        .response-body blockquote {
            border-left: 3px solid #667eea;
            padding-left: 16px;
            margin: 16px 0;
            color: #aaa;
            font-style: italic;
        }
        
        .response-body table {
            width: 100%;
            border-collapse: collapse;
            margin: 16px 0;
            font-size: 13px;
            background: rgba(255,255,255,0.02);
            border: 1px solid rgba(255,255,255,0.15);
            border-radius: 8px;
            overflow: hidden;
        }
        
        .response-body table thead tr {
            background: rgba(102,126,234,0.15);
        }
        
        .response-body table th {
            padding: 10px 12px;
            text-align: left;
            color: #667eea;
            font-weight: 600;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 2px solid rgba(102,126,234,0.3);
            border-right: 1px solid rgba(255,255,255,0.08);
            white-space: nowrap;
        }
        
        .response-body table th:last-child {
            border-right: none;
        }
        
        .response-body table td {
            padding: 8px 12px;
            border-bottom: 1px solid rgba(255,255,255,0.06);
            border-right: 1px solid rgba(255,255,255,0.06);
            color: #ccc;
        }
        
        .response-body table td:last-child {
            border-right: none;
        }
        
        .response-body table tbody tr:hover {
            background: rgba(102,126,234,0.08);
        }
        
        .response-body table tbody tr:nth-child(even) {
            background: rgba(255,255,255,0.02);
        }
        
        .loading {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 350px;
        }
        
        .spinner {
            width: 50px;
            height: 50px;
            border: 4px solid rgba(102, 126, 234, 0.2);
            border-top-color: #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-bottom: 20px;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .timer {
            color: #667eea;
            font-size: 24px;
            font-weight: 600;
        }
        
        .sources-footer {
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid rgba(255,255,255,0.1);
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            font-size: 13px;
            color: #666;
        }
        
        .sources-footer span {
            background: rgba(102, 126, 234, 0.1);
            padding: 6px 12px;
            border-radius: 20px;
        }
        
        .clear-btn {
            position: fixed;
            bottom: 20px;
            right: 20px;
            padding: 12px 20px;
            background: rgba(255,100,100,0.2);
            border: 1px solid rgba(255,100,100,0.3);
            color: #ff6b6b;
            border-radius: 8px;
            cursor: pointer;
            font-size: 13px;
        }
        
        .clear-btn:hover {
            background: rgba(255,100,100,0.3);
        }
        
        /* Clickable link buttons */
        .tweet-link {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 4px 12px;
            background: linear-gradient(135deg, #1da1f2 0%, #0d8ecf 100%);
            color: white !important;
            border-radius: 20px;
            text-decoration: none !important;
            font-size: 13px;
            font-weight: 500;
            margin: 2px 4px;
            transition: all 0.2s ease;
        }
        .tweet-link:hover {
            transform: scale(1.05);
            box-shadow: 0 4px 12px rgba(29, 161, 242, 0.4);
        }
        
        .article-link {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 4px 12px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white !important;
            border-radius: 20px;
            text-decoration: none !important;
            font-size: 13px;
            font-weight: 500;
            margin: 2px 4px;
            transition: all 0.2s ease;
        }
        .article-link:hover {
            transform: scale(1.05);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }
        
        .mention-link {
            color: #1da1f2 !important;
            font-weight: 600;
            text-decoration: none;
        }
        .mention-link:hover {
            text-decoration: underline;
        }
    
        .feedback-section {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid rgba(255,255,255,0.1);
        }
        
        .feedback-label { color: #888; font-size: 0.9em; }
        
        .feedback-btn {
            padding: 8px 16px;
            border-radius: 8px;
            border: 1px solid rgba(255,255,255,0.2);
            background: rgba(255,255,255,0.05);
            color: #e0e0e0;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        .feedback-btn:hover { background: rgba(255,255,255,0.1); }
        .feedback-btn.good:hover { border-color: #4ade80; color: #4ade80; }
        .feedback-btn.bad:hover { border-color: #f87171; color: #f87171; }
        .feedback-btn.correct:hover { border-color: #60a5fa; color: #60a5fa; }
        .feedback-btn.submitted { background: rgba(102, 126, 234, 0.3); border-color: #667eea; color: #667eea; }
        
        .correction-box {
            margin-top: 15px;
            padding: 15px;
            background: rgba(0,0,0,0.2);
            border-radius: 10px;
        }
        
        .correction-box textarea {
            width: 100%;
            height: 80px;
            padding: 12px;
            border-radius: 8px;
            border: 1px solid rgba(255,255,255,0.2);
            background: rgba(0,0,0,0.3);
            color: #e0e0e0;
            font-family: inherit;
        }
        
        .submit-correction {
            margin-top: 10px;
            padding: 10px 20px;
            border-radius: 8px;
            border: none;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            cursor: pointer;
        }


        /* Database Toggle Switch */
        .db-toggle-container {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 15px;
            margin: 20px 0;
            padding: 15px;
            background: rgba(255,255,255,0.03);
            border-radius: 12px;
        }
        
        .db-toggle-label {
            font-size: 16px;
            font-weight: 500;
            color: #888;
            transition: color 0.3s ease;
        }
        
        .db-toggle-label.active {
            color: #fff;
        }
        
        .db-toggle {
            position: relative;
            width: 80px;
            height: 40px;
            background: rgba(102, 126, 234, 0.2);
            border-radius: 20px;
            cursor: pointer;
            transition: background 0.3s ease;
            border: 2px solid rgba(102, 126, 234, 0.3);
        }
        
        .db-toggle.brazil {
            background: linear-gradient(135deg, #009c3b 0%, #ffdf00 100%);
            border-color: #009c3b;
        }
        
        .db-toggle.macro {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-color: #667eea;
        }
        
        .db-toggle-slider {
            position: absolute;
            top: 4px;
            left: 4px;
            width: 28px;
            height: 28px;
            background: white;
            border-radius: 50%;
            transition: transform 0.3s ease;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3);
        }
        
        .db-toggle.macro .db-toggle-slider {
            transform: translateX(40px);
        }
        
        .db-indicator {
            font-size: 12px;
            color: #667eea;
            margin-top: 5px;
            text-align: center;
        }

    
        /* Prompt Boost Toggle */
        .boost-toggle {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-top: 12px;
            padding: 10px 15px;
            background: rgba(102, 126, 234, 0.1);
            border-radius: 8px;
            border: 1px solid rgba(102, 126, 234, 0.2);
        }
        
        .boost-toggle input[type="checkbox"] {
            width: 18px;
            height: 18px;
            cursor: pointer;
            accent-color: #667eea;
        }
        
        .boost-toggle label {
            color: #a0a0ff;
            font-size: 14px;
            cursor: pointer;
            margin: 0;
        }
        
        .boost-toggle .boost-info {
            color: #666;
            font-size: 12px;
            margin-left: auto;
        }

        </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🧠 M3xA - Market Augmented Awareness Agent</h1><span style="font-size:10px;color:#4ade80;margin-left:10px;">[v2.1]</span><button onclick="sendEmail()" style="margin-left:15px;padding:6px 14px;background:#667eea;color:white;border:none;border-radius:6px;cursor:pointer;font-size:12px;">📧 Send Email</button>
        </header>
        
        <!-- Time range selector + action buttons -->
        <div style="display:flex;align-items:center;justify-content:center;gap:14px;margin:12px 0 18px;flex-wrap:wrap;">
            <label style="color:#94a3b8;font-size:13px;font-weight:500;">⏰ Time Window:</label>
            <select id="timeRange" onchange="updateTimeLabel()" style="padding:9px 16px;border-radius:10px;border:1px solid rgba(102,126,234,0.5);background:linear-gradient(135deg,#0f172a,#1e293b);color:#e2e8f0;font-size:14px;font-weight:500;cursor:pointer;outline:none;min-width:140px;transition:border-color 0.2s;">
                <option value="6">6 hours</option>
                <option value="12">12 hours</option>
                <option value="24" selected>24 hours</option>
                <option value="48">48 hours</option>
                <option value="72">72 hours</option>
                <option value="168">1 week</option>
                <option value="720">1 month</option>
                <option value="2160">3 months</option>
                <option value="0">All database</option>
            </select>
            <span id="timeLabel" style="color:#667eea;font-size:12px;opacity:0.8;">(last 24h)</span>
        </div>
        
        <div class="quick-buttons">
            <button class="quick-btn" onclick="runPremade('macro')" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-color: #667eea; font-size: 15px; padding: 14px 24px;">
                🌍 Macro Themes
            </button>
            <button class="quick-btn" onclick="runBrazilBrief()" style="background: linear-gradient(135deg, #1a5f2a 0%, #0d3d1a 100%); border-color: #4ade80; font-size: 15px; padding: 14px 24px;">
                🇧🇷 Brazil Brief
            </button>
            <button class="quick-btn" onclick="window.open('/iran-dashboard','_blank')" style="background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%); border-color: #e74c3c; font-size: 15px; padding: 14px 24px;">
                &#127919; Iran Risk
            </button>
            <button class="quick-btn" onclick="window.open('/brazil-dashboard','_blank')" style="background: linear-gradient(135deg, #009c3b 0%, #006400 100%); border-color: #009c3b; font-size: 15px; padding: 14px 24px;">
                &#127463;&#127479; Brazil 2026
            </button>
            <button class="quick-btn" onclick="runMacroTelegram(6)" id="telegramMacroBtn6" style="background: linear-gradient(135deg, #0088cc 0%, #005580 100%); border-color: #0088cc; font-size: 15px; padding: 14px 24px;">
                📱 Macro 6h → TG
            </button>
            <button class="quick-btn" onclick="runMacroTelegram(12)" id="telegramMacroBtn12" style="background: linear-gradient(135deg, #6633cc 0%, #442288 100%); border-color: #6633cc; font-size: 15px; padding: 14px 24px;">
                📱 Macro 12h → TG
            </button>
        </div>
        
        <div class="input-section">
            <label>💬 Or ask anything:</label>
            <div class="input-row">
                <input type="text" id="queryInput" placeholder="What did Goldman Sachs say about China? Include links..." onkeypress="if(event.key==='Enter')runQuery()">
                <button onclick="runQuery()" id="askBtn">Ask M3xA</button>
            </div>
        
            <div class="boost-toggle">
                <input type="checkbox" id="boostToggle" checked>
                <label for="boostToggle">🚀 Prompt Boost 1 (Multi-Source)</label>
                <span class="boost-info">Queries 12 priority sources (7-day window)</span>
            </div>
            <div class="boost-toggle" style="margin-top:8px">
                <input type="checkbox" id="boostToggle2">
                <label for="boostToggle2">🇧🇷 Prompt Boost 2 (Brazil Brief)</label>
                <span class="boost-info">Class-based Brazil sources (⭐ priority)</span>
                <button onclick="runBrazilBrief()" style="margin-left:10px;padding:4px 12px;background:#047857;color:white;border:none;border-radius:4px;cursor:pointer">▶️ Run</button>
            </div>
        </div>
        
            <!-- SAVED PROMPTS ROW -->
            <div style="margin-top:10px;display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
                <button onclick="saveCurrentPrompt()" style="background:transparent;border:1px solid #f59e0b;color:#f59e0b;padding:5px 14px;border-radius:6px;cursor:pointer;font-size:12px;font-weight:600;">&#x1F4BE; Save Prompt</button>
                <select id="savedPromptsDropdown" onchange="loadSavedPrompt(this.value)" style="background:#161b22;color:#e2e8f0;border:1px solid rgba(102,126,234,0.4);padding:5px 10px;border-radius:6px;font-size:12px;max-width:400px;flex:1;cursor:pointer;">
                    <option value="">&#x1F4C2; Saved Prompts...</option>
                </select>
                <button onclick="deleteSavedPrompt()" style="background:transparent;border:1px solid #f8717180;color:#f87171;padding:5px 10px;border-radius:6px;cursor:pointer;font-size:11px;" title="Delete selected prompt">&#x1F5D1;</button>
            </div>
        </div>

        <div class="response-section">
            <div class="response-header">
                <h3>📋 Response</h3>
                <div class="response-meta" id="responseMeta"></div>
            </div>
            <div class="response-body" id="responseBody">
                <div class="empty">
                    <div class="icon">🤖</div>
                    <p>Click a quick analysis button or ask a question to get started</p>
                </div>
            </div>
        </div>
    </div>
    
    <button class="clear-btn" onclick="clearSession()">🗑️ Clear Session</button>
    <button class="clear-btn" onclick="showCronsModal()" style="background: linear-gradient(135deg, #2d5016 0%, #1a3d0c 100%); margin-left: 10px;">📋 Crons</button>
    
    <script>
        // Database toggle state
        let currentDatabase = 'macro';  // Default to Macro
        
        
        async function runBrazilBrief() {
            const responseBody = document.getElementById("responseBody");
            responseBody.innerHTML = "<div class=loading>🇧🇷 Generating Brazil Brief (streaming)...</div>";
            
            try {
                const response = await fetch("/api/brazil_brief?llm=true&min_class=1");
                if (!response.ok) throw new Error("HTTP " + response.status);
                
                const contentType = response.headers.get("content-type");
                if (contentType && contentType.includes("text/event-stream")) {
                    responseBody.innerHTML = "<div class=response></div>";
                    const outputDiv = responseBody.querySelector(".response");
                    const reader = response.body.getReader();
                    const decoder = new TextDecoder();
                    let buffer = "";
                    let fullText = "";
                    
                    while (true) {
                        const {done, value} = await reader.read();
                        if (done) break;
                        buffer += decoder.decode(value, {stream: true});
                        const lines = buffer.split("\\n");
                        buffer = lines.pop();
                        for (const line of lines) {
                            if (line.startsWith("data: ")) {
                                try {
                                    const data = JSON.parse(line.slice(6));
                                    if (data.text) {
                                        fullText += data.text;
                                        outputDiv.innerHTML = fullText.replace(/\\n/g, "<br>").replace(/⭐/g, "<span style=color:gold>⭐</span>");
                                    }
                                    if (data.error) outputDiv.innerHTML = "<div class=error>" + data.error + "</div>";
                                } catch(e) {}
                            }
                        }
                    }
                    // Add email button after streaming completes
                    window.lastResponse = fullText;
                    window.lastQuery = "Brazil Brief";
                    responseBody.innerHTML += '<div class="feedback-section" style="margin-top:15px;padding-top:15px;border-top:1px solid rgba(255,255,255,0.1);display:flex;gap:10px;"><span style="color:#888;">Actions:</span><button class="feedback-btn" style="background:#667eea;border-color:#667eea;padding:6px 12px;border-radius:4px;color:white;cursor:pointer;" onclick="sendEmail()">📧 Email</button></div>';
                } else {
                    const data = await response.json();
                    if (data.error) responseBody.innerHTML = "<div class=error>" + data.error + "</div>";
                    else responseBody.innerHTML = "<div class=response>" + data.brief.replace(/\\n/g, "<br>").replace(/⭐/g, "<span style=color:gold>⭐</span>") + "</div>";
                }
            } catch(e) {
                responseBody.innerHTML = "<div class=error>Error: " + e.message + "</div>";
            }
        }

        function showCronsModal() {
            document.getElementById("cronsModal").style.display = "block";
            fetch("/api/crons").then(r => r.json()).then(data => {
                let h = "";
                const cats = {"macro_scrapers": "🌍 MACRO", "brazil_scrapers": "🇧🇷 BRAZIL", "email_pipeline": "📧 EMAIL", "twitter": "🐦 TWITTER", "other": "📰 OTHER"};
                for (const [k, t] of Object.entries(cats)) {
                    if (data.crons[k]) {
                        h += "<div style=margin-bottom:15px><h3 style=color:#fbbf24;margin:5px>" + t + "</h3><table style=width:100%;border-collapse:collapse>";
                        h += "<tr style=background:#2a2a2a><th style=padding:6px;border:1px_solid_#444>Name</th><th style=padding:6px;border:1px_solid_#444>Cron</th><th style=padding:6px;border:1px_solid_#444>Last</th><th style=padding:6px;border:1px_solid_#444>Desc</th></tr>";
                        data.crons[k].forEach(c => {
                            const st = c.status === "ok" ? "✅" : "⚠️";
                            h += "<tr><td style=padding:6px;border:1px_solid_#333>" + st + " " + c.name + "</td>";
                            h += "<td style=padding:6px;border:1px_solid_#333;color:#60a5fa>" + c.cron + "</td>";
                            h += "<td style=padding:6px;border:1px_solid_#333;color:#4ade80>" + c.last_run + "</td>";
                            h += "<td style=padding:6px;border:1px_solid_#333;color:#9ca3af>" + c.desc + "</td></tr>";
                        });
                        h += "</table></div>";
                    }
                }
                h += "<div style=margin-top:15px;padding:10px;background:#2a2a2a;border-radius:6px><strong style=color:#fbbf24>💰 Est. Cost:</strong> ~.30/day</div>";
                document.getElementById("cronsContent").innerHTML = h.replace(/_/g, " ");
            });
        }
        function closeCronsModal() { document.getElementById("cronsModal").style.display = "none"; }

        function toggleDatabase() {
            const toggle = document.getElementById('dbToggle');
            const brazilLabel = document.getElementById('brazilLabel');
            const macroLabel = document.getElementById('macroLabel');
            const indicator = document.getElementById('dbIndicator');
            
            if (currentDatabase === 'brazil') {
                currentDatabase = 'macro';
                toggle.classList.remove('brazil');
                toggle.classList.add('macro');
                brazilLabel.classList.remove('active');
                macroLabel.classList.add('active');
                indicator.textContent = '📊 Currently: Macro sources (98 sources)';
                indicator.style.color = '#667eea';
            } else {
                currentDatabase = 'brazil';
                toggle.classList.remove('macro');
                toggle.classList.add('brazil');
                macroLabel.classList.remove('active');
                brazilLabel.classList.add('active');
                indicator.textContent = '📊 Currently: Brazil sources (38 sources)';
                indicator.style.color = '#009c3b';
            }
        }
        
        // Initialize toggle state on load
        document.addEventListener('DOMContentLoaded', function() {
            document.getElementById('brazilLabel').classList.add('active');
        });
        
        let sessionId = 'session_' + Date.now();
        
        function updateTimeLabel() {
            const sel = document.getElementById('timeRange');
            const label = document.getElementById('timeLabel');
            if (!sel || !label) return;
            const v = parseInt(sel.value);
            const labels = {0:'all data',6:'last 6h',12:'last 12h',24:'last 24h',48:'last 48h',72:'last 72h',168:'last week',720:'last month',2160:'last 3 months'};
            label.textContent = '(' + (labels[v] || v+'h') + ')';
        }
        let timerInterval = null;
        let startTime = null;
        
        function formatMarkdown(text) {
            // Parse markdown tables FIRST (before other transforms break pipe chars)
            text = text.replace(/((?:^\\|.+\\|$\\n?)+)/gm, function(tableBlock) {
                const rows = tableBlock.trim().split('\\n').filter(r => r.trim());
                if (rows.length < 2) return tableBlock;
                
                // Check if second row is separator (|---|---|)
                const sepRow = rows[1];
                if (!/^\\|[\\s:\\-]+\\|/.test(sepRow)) {
                    if (!/^[\\s|:\\-]+$/.test(sepRow)) return tableBlock;
                }
                
                function parseCells(row) {
                    return row.split('|').slice(1, -1).map(c => c.trim());
                }
                
                const headerCells = parseCells(rows[0]);
                let html = '<table><thead><tr>';
                headerCells.forEach(c => { html += '<th>' + c + '</th>'; });
                html += '</tr></thead><tbody>';
                
                for (let i = 2; i < rows.length; i++) {
                    if (!rows[i].trim() || !/\\|/.test(rows[i])) continue;
                    const cells = parseCells(rows[i]);
                    html += '<tr>';
                    cells.forEach(c => { html += '<td>' + c + '</td>'; });
                    html += '</tr>';
                }
                html += '</tbody></table>';
                return html;
            });
            
            // Headers
            text = text.replace(/^### (.+)$/gm, '<h3>$1</h3>');
            text = text.replace(/^## (.+)$/gm, '<h2>$1</h2>');
            
            // Bold and italic
            text = text.replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>');
            text = text.replace(/\\*(.+?)\\*/g, '<em>$1</em>');
            
            // Links
            text = text.replace(/\\[([^\\]]+)\\]\\(([^)]+)\\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
            
            // @mentions
            text = text.replace(/@(\\w+)/g, '<strong style="color:#667eea">@$1</strong>');
            
            // Bullet points
            text = text.replace(/^- (.+)$/gm, '<li>$1</li>');
            text = text.replace(/(<li>.*<\\/li>)/s, '<ul>$1</ul>');
            
            // Numbered lists
            text = text.replace(/^\\d+\\. (.+)$/gm, '<li>$1</li>');
            
            // Paragraphs
            text = text.replace(/\\n\\n/g, '</p><p>');
            text = text.replace(/\\n/g, '<br>');
            
            return '<p>' + text + '</p>';
        }
        
        function showLoading() {
            startTime = Date.now();
            document.getElementById('responseBody').innerHTML = `
                <div class="loading">
                    <div class="spinner"></div>
                    <div class="timer" id="loadTimer">0.0s</div>
                    <p style="color:#666;margin-top:10px;">Analyzing with Claude Opus 4...</p>
                </div>
            `;
            document.getElementById('responseMeta').innerHTML = '';
            document.getElementById('askBtn').disabled = true;
            
            timerInterval = setInterval(() => {
                const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
                document.getElementById('loadTimer').textContent = elapsed + 's';
            }, 100);
        }
        
        function hideLoading() {
            if (timerInterval) {
                clearInterval(timerInterval);
                timerInterval = null;
            }
            document.getElementById('askBtn').disabled = false;
        }
        
        
        async function sendEmail() {
            if (!window.lastResponse) {
                alert('No analysis to send. Run a query first.');
                return;
            }
            
            const btn = event.target;
            const originalText = btn.innerHTML;
            btn.innerHTML = '📧 Sending...';
            btn.disabled = true;
            
            try {
                const response = await fetch('/api/send_email', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        response: window.lastResponse,
                        query: window.lastQuery
                    })
                });
                
                const data = await response.json();
                if (data.status === 'sent') {
                    btn.innerHTML = '✅ Sent!';
                    setTimeout(() => { btn.innerHTML = originalText; btn.disabled = false; }, 3000);
                } else {
                    btn.innerHTML = '❌ Failed';
                    setTimeout(() => { btn.innerHTML = originalText; btn.disabled = false; }, 3000);
                }
            } catch(e) {
                btn.innerHTML = '❌ Error';
                setTimeout(() => { btn.innerHTML = originalText; btn.disabled = false; }, 3000);
            }
        }
        
async function runPremade(key) {
            // Highlight active button
            document.querySelectorAll('.quick-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            
            showLoading();
            
            // Get selected time range from dropdown
            const selTime = document.getElementById('timeRange');
            const timeHours = selTime ? parseInt(selTime.value) : 24;
            
            try {
                const response = await fetch('/api/rag', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        premade_key: key,
                        session_id: sessionId,
                        time_hours: timeHours
                    })
                });
                
                const data = await response.json();
                hideLoading();
                
                if (data.error) {
                    document.getElementById('responseBody').innerHTML = '<p style="color:#ff6b6b;">Error: ' + data.error + '</p>';
                } else {
                    displayResponse(data);
                }

            } catch (error) {
                hideLoading();
                document.getElementById('responseBody').innerHTML = '<p style="color:#ff6b6b;">Connection error. Please try again.</p>';
            }
        }
        
        
        async function runMacroTelegram(hours = 6) {
            const btn = document.getElementById('telegramMacroBtn' + hours);
            const originalText = btn.innerHTML;
            btn.innerHTML = '⏳ Sending to Telegram...';
            btn.disabled = true;
            btn.style.opacity = '0.7';
            
            try {
                const response = await fetch('/api/telegram-macro', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ hours: hours })
                });
                
                const data = await response.json();
                btn.innerHTML = '✅ Sent! Check Telegram';
                btn.style.background = 'linear-gradient(135deg, #22c55e 0%, #16a34a 100%)';
                
                setTimeout(() => {
                    btn.innerHTML = originalText;
                    btn.disabled = false;
                    btn.style.opacity = '1';
                    btn.style.background = '';
                }, 5000);
            } catch(e) {
                btn.innerHTML = '❌ Error';
                setTimeout(() => {
                    btn.innerHTML = originalText;
                    btn.disabled = false;
                    btn.style.opacity = '1';
                    btn.style.background = '';
                }, 3000);
            }
        }

        async function runQuery() {
            const query = document.getElementById('queryInput').value.trim();
            if (!query) return;
            
            document.querySelectorAll('.quick-btn').forEach(btn => btn.classList.remove('active'));
            showLoading();
            
            try {
                const timeHoursQ = document.getElementById('timeRange') ? parseInt(document.getElementById('timeRange').value) : null;
                const response = await fetch('/api/rag', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        query: query,
                        filters: { source: currentDatabase },
                        session_id: sessionId,
                        boost_enabled: document.getElementById('boostToggle').checked,
                        boost2_enabled: document.getElementById('boostToggle2').checked,
                        time_hours: timeHoursQ
                    })
                });
                
                const data = await response.json();
                hideLoading();
                
                if (data.error) {
                    document.getElementById('responseBody').innerHTML = '<p style="color:#ff6b6b;">Error: ' + data.error + '</p>';
                } else {
                    displayResponse(data);
                }
            } catch (error) {
                hideLoading();
                document.getElementById('responseBody').innerHTML = '<p style="color:#ff6b6b;">Connection error. Please try again.</p>';
            }
        }
        
        function displayResponse(data) {
            let formatted = formatMarkdown(data.response);
            
            // Post-process: Add tweet-link class to all x.com links
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = formatted;
            tempDiv.querySelectorAll('a[href*="x.com"]').forEach(link => {
                if (!link.classList.contains('mention-link')) {
                    link.classList.add('tweet-link');
                    if (!link.innerHTML.includes('🐦')) {
                        link.innerHTML = '🐦 ' + link.innerHTML;
                    }
                }
            });
            tempDiv.querySelectorAll('a[href*="substack"]').forEach(link => {
                link.classList.add('article-link');
                if (!link.innerHTML.includes('📄')) {
                    link.innerHTML = '📄 ' + link.innerHTML;
                }
            });
            formatted = tempDiv.innerHTML;
            
            let sourcesHtml = '<div class="sources-footer">';
            sourcesHtml += '<span>📊 ' + data.sources.tweets + ' tweets</span>';
            sourcesHtml += '<span>📧 ' + data.sources.codex + ' emails</span>';
            if (data.time_context && data.time_context.data_newest) {
                sourcesHtml += '<span>📅 Data: ' + data.time_context.data_newest + '</span>';
            }
            if (data.time_context && data.time_context.data_age_hours) {
                const ageHours = data.time_context.data_age_hours;
                let ageText = '';
                let ageColor = '';
                if (ageHours < 24) {
                    ageText = '🟢 Fresh (' + Math.round(ageHours) + 'h ago)';
                    ageColor = '#4ade80';
                } else if (ageHours < 72) {
                    ageText = '🟡 ' + Math.round(ageHours/24) + ' days ago';
                    ageColor = '#facc15';
                } else {
                    ageText = '🔴 ' + Math.round(ageHours/24) + ' days old';
                    ageColor = '#f87171';
                }
                sourcesHtml += '<span style="color:' + ageColor + '">' + ageText + '</span>';
            }
            sourcesHtml += '<span>⏱️ ' + data.elapsed_seconds + 's</span>';
            sourcesHtml += '</div>';
            
            // Add feedback buttons - using data attributes to avoid escaping issues
            let convId = data.conversation_id || 0;
            let feedbackHtml = '<div class="feedback-section">';
            feedbackHtml += '<span class="feedback-label">Was this helpful?</span>';
            feedbackHtml += '<button class="feedback-btn good" data-convid="' + convId + '" data-rating="good" onclick="handleFeedback(this)">👍 Good</button>';
            feedbackHtml += '<button class="feedback-btn bad" data-convid="' + convId + '" data-rating="bad" onclick="handleFeedback(this)">👎 Bad</button>';
            feedbackHtml += '<button class="feedback-btn correct" data-convid="' + convId + '" onclick="handleCorrection(this)">✏️ Correct</button>';
            feedbackHtml += '<button class="feedback-btn" style="margin-left:auto;background:#667eea;border-color:#667eea;" onclick="sendEmail()">📧 Email</button>';
            feedbackHtml += '</div>';
            feedbackHtml += '<div id="correctionBox" class="correction-box" style="display:none;">';
            feedbackHtml += '<textarea id="correctionText" placeholder="What was wrong or missing? Your feedback helps me learn..."></textarea>';
            feedbackHtml += '<button class="submit-correction" onclick="submitCorrection()">Submit Correction</button>';
            feedbackHtml += '</div>';
            
            // Store conversation_id for later
            window.currentConversationId = data.conversation_id;
        
        // Store last response for email sending
        window.lastResponse = data.response;
        window.lastQuery = data.query || document.getElementById('queryInput').value;
            
            document.getElementById('responseBody').innerHTML = formatted + sourcesHtml + feedbackHtml;
            document.getElementById('responseMeta').innerHTML = '⏱️ ' + data.elapsed_seconds + 's';
        }
        
        async function clearSession() {
            try {
                await fetch('/api/clear', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ session_id: sessionId })
                });
            } catch(e) {}
            
            sessionId = 'session_' + Date.now();
            document.getElementById('responseBody').innerHTML = `
                <div class="empty">
                    <div class="icon">🤖</div>
                    <p>Session cleared. Click a button or ask a question.</p>
                </div>
            `;
            document.getElementById('responseMeta').innerHTML = '';
            document.querySelectorAll('.quick-btn').forEach(btn => btn.classList.remove('active'));
        }

        // Feedback functions
        // Wrapper functions that read from data attributes
        function handleFeedback(btn) {
            const convId = btn.dataset.convid;
            const rating = btn.dataset.rating;
            submitFeedback(convId, rating);
        }
        
        function handleCorrection(btn) {
            const convId = btn.dataset.convid;
            showCorrection(convId);
        }
        
        async function submitFeedback(conversationId, rating) {
            try {
                const response = await fetch('/api/feedback', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        conversation_id: conversationId,
                        rating: rating
                    })
                });
                const data = await response.json();
                if (data.success) {
                    // Show confirmation
                    document.querySelectorAll('.feedback-btn').forEach(btn => {
                        btn.classList.remove('submitted');
                    });
                    event.target.classList.add('submitted');
                    event.target.textContent = rating === 'good' ? '👍 Thanks!' : '👎 Noted';
                }
            } catch(e) {
                console.error('Feedback error:', e);
            }
        }
        
        function showCorrection(conversationId) {
            window.currentConversationId = conversationId;
            document.getElementById('correctionBox').style.display = 'block';
            document.getElementById('correctionText').focus();
        }
        
        async function submitCorrection() {
            const correction = document.getElementById('correctionText').value.trim();
            if (!correction) return;
            
            try {
                const response = await fetch('/api/feedback', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        conversation_id: window.currentConversationId,
                        rating: 'bad',
                        correction: correction,
                        what_was_wrong: correction
                    })
                });
                const data = await response.json();
                if (data.success) {
                    document.getElementById('correctionBox').innerHTML = '<p style="color:#4ade80;">✅ Thank you! Your correction helps me learn.</p>';
                }
            } catch(e) {
                console.error('Correction error:', e);
            }
        }
        // === SAVED PROMPTS ===
        function refreshSavedPrompts() {
            fetch('/api/saved_prompts').then(r => r.json()).then(data => {
                const dd = document.getElementById('savedPromptsDropdown');
                const count = data.prompts ? data.prompts.length : 0;
                dd.innerHTML = '<option value="">📂 Saved Prompts (' + count + ')...</option>';
                if (data.prompts) {
                    data.prompts.forEach((p, i) => {
                        const ctx = p.context === 'brazil' ? '🇧🇷' : '🌎';
                        const t = p.time_hours ? p.time_hours + 'h' : '24h';
                        const nm = p.name || (p.query || '').substring(0, 50);
                        dd.innerHTML += '<option value="' + i + '">' + ctx + ' ' + t + ' | ' + nm + '</option>';
                    });
                }
            }).catch(e => console.error('Load prompts error:', e));
        }

        function saveCurrentPrompt() {
            const query = document.getElementById('queryInput').value.trim();
            if (!query) { alert('Type a query first'); return; }
            const name = window.prompt('Name for this prompt:', query.substring(0, 50));
            if (name === null) return;
            const selTime = document.getElementById('timeRange');
            const th = selTime ? parseInt(selTime.value) : 24;
            const payload = {
                query: query,
                name: name || query.substring(0, 50),
                context: 'macro',
                time_hours: th,
                boost1: document.getElementById('boostToggle').checked,
                boost2: document.getElementById('boostToggle2').checked
            };
            fetch('/api/saved_prompts', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({action: 'save', prompt: payload})
            }).then(r => r.json()).then(d => {
                if (d.success) refreshSavedPrompts();
                else alert('Error: ' + (d.error || 'unknown'));
            }).catch(e => alert('Save error: ' + e.message));
        }

        function loadSavedPrompt(idx) {
            if (idx === '') return;
            fetch('/api/saved_prompts').then(r => r.json()).then(data => {
                const p = data.prompts[parseInt(idx)];
                if (!p) return;
                document.getElementById('queryInput').value = p.query || '';
                if (p.time_hours) {
                    const sel = document.getElementById('timeRange');
                    if (sel) sel.value = String(p.time_hours);
                }
                document.getElementById('boostToggle').checked = p.boost1 !== false;
                document.getElementById('boostToggle2').checked = !!p.boost2;
            });
        }

        function deleteSavedPrompt() {
            const dd = document.getElementById('savedPromptsDropdown');
            const idx = dd.value;
            if (idx === '') { alert('Select a prompt first'); return; }
            if (!confirm('Delete this saved prompt?')) return;
            fetch('/api/saved_prompts', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({action: 'delete', index: parseInt(idx)})
            }).then(r => r.json()).then(d => {
                if (d.success) refreshSavedPrompts();
            });
        }

        setTimeout(refreshSavedPrompts, 800);

        async function runBrazil24hStructured() {
            const resultDiv = document.getElementById('responseBody');
            const askBtn = document.getElementById('askBtn');
            askBtn.disabled = true;
            resultDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>🇧🇷 Gerando análise estruturada Brazil 24h...</p></div>';
            try {
                const response = await fetch('/api/brazil_24h_structured');
                const data = await response.json();
                if (data.status === 'success') {
                    resultDiv.innerHTML = data.response;
                } else {
                    resultDiv.innerHTML = '<p style="color: #f87171;">Erro: ' + data.error + '</p>';
                }
            } catch (error) {
                resultDiv.innerHTML = '<p style="color: #f87171;">Erro: ' + error.message + '</p>';
            }
            askBtn.disabled = false;
        }

    </script>

    <div id="cronsModal" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); z-index: 1000; overflow-y: auto;">
        <div style="background: #1a1a1a; margin: 30px auto; max-width: 800px; border-radius: 12px; border: 1px solid #4ade80; padding: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                <h2 style="color: #4ade80; margin: 0;">📋 CRON JOBS STATUS</h2>
                <button onclick="closeCronsModal()" style="background: #ef4444; border: none; color: white; padding: 8px 16px; border-radius: 6px; cursor: pointer;">✕</button>
            </div>
            <div id="cronsContent" style="color: #e0e0e0; font-family: monospace; font-size: 12px;">Loading...</div>
        </div>
    </div>
</body>
</html>
'''



THEMES_BRAZIL = {
    'politica_monetaria': ['copom', 'selic', 'juros', 'bc', 'banco central', 'inflação', 'ipca', 'galípolo'],
    'politica_institucional': ['stf', 'supremo', 'gilmar', 'moraes', 'congresso', 'senado', 'câmara', 'impeachment'],
    'eleicoes_2026': ['eleição', 'eleições', 'candidato', 'candidatura', 'pesquisa', 'quaest', 'datafolha', '2026'],
    'governo_lula': ['lula', 'haddad', 'governo federal', 'planalto', 'ministro', 'ministério'],
    'fiscal': ['ldo', 'orçamento', 'meta fiscal', 'déficit', 'superávit', 'emendas', 'contingenciamento']
}

def classify_theme_brazil(text, keywords):
    text_lower = (str(text) + ' ' + str(keywords)).lower()
    scores = {}
    for theme, theme_keywords in THEMES_BRAZIL.items():
        score = sum(1 for kw in theme_keywords if kw in text_lower)
        if score > 0:
            scores[theme] = score
    if scores:
        return max(scores, key=scores.get)
    return 'outros'

@app.route('/api/saved_prompts', methods=['GET', 'POST'])
def saved_prompts_api():
    import json as _j
    PROMPTS_FILE = '/home/ubuntu/argus/newspaper_project/data/saved_prompts.json'

    def _load():
        try:
            with open(PROMPTS_FILE) as f:
                return _j.load(f)
        except:
            return []

    def _save(prompts):
        import os
        os.makedirs(os.path.dirname(PROMPTS_FILE), exist_ok=True)
        with open(PROMPTS_FILE, 'w') as f:
            _j.dump(prompts, f, indent=2)

    if request.method == 'GET':
        return jsonify({'prompts': _load()})

    data = request.get_json()
    action = data.get('action', '')

    if action == 'save':
        prompts = _load()
        new_prompt = data.get('prompt', {})
        from datetime import datetime as _dt
        new_prompt['saved_at'] = _dt.now().strftime('%Y-%m-%d %H:%M')
        prompts.insert(0, new_prompt)
        if len(prompts) > 50:
            prompts = prompts[:50]
        _save(prompts)
        return jsonify({'success': True, 'count': len(prompts)})

    elif action == 'delete':
        prompts = _load()
        idx = data.get('index', -1)
        if 0 <= idx < len(prompts):
            prompts.pop(idx)
            _save(prompts)
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Invalid index'})

    return jsonify({'success': False, 'error': 'Unknown action'})


@app.route('/api/brazil_24h_structured')
def brazil_24h_structured():
    """
    RAG ESTRUTURADO - Brazil 24h
    Fontes verificadas automaticamente, sem alucinações
    """
    import pandas as pd
    # Anthropic already imported at top
    
    try:
        # 1. Get Brazil data from last 24h
        db = _get_rag_db()
        table = db.open_table('unified_feed')
        # PERF: Load only light columns (avoids reading vectors from disk)
        _heavy = {'content_vector', 'vlm_enhanced_vector', 'content_html', 'raw_data'}
        _light = [c for c in table.schema.names if c not in _heavy]
        df = table.search().select(_light).limit(300000).to_pandas()
        
        # Timestamp normalization - parse dates for this fresh DataFrame
        def _parse_dt(val):
            if pd.isna(val):
                return pd.NaT
            try:
                s = str(val).replace('000000000Z', '').replace('Z', '').replace('+00:00', '').strip()
                dt = pd.to_datetime(s)
                if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
                    dt = dt.replace(tzinfo=None)
                return dt
            except:
                return pd.NaT
        df['created_at_dt'] = df['created_at'].apply(_parse_dt)
        
        now = datetime.now()
        cutoff = now - timedelta(hours=24)
        df = df[df['created_at_dt'] > cutoff]
        
        # Brazil sources filter
        brazil_sources = get_brazilian_sources()
        df = df[df['username'].str.lower().isin(brazil_sources)]
        
        total_items = len(df)
        unique_sources = df['username'].nunique()
        time_range = f"{cutoff.strftime('%d/%m %H:%M')} - {now.strftime('%d/%m %H:%M')}"
        
        # 2. Extract and classify facts
        facts = []
        for _, row in df.iterrows():
            text = str(row.get('text', ''))
            keywords = str(row.get('keywords', ''))
            fact = {
                'id': row['id'],
                'source': row['username'],
                'timestamp': row['created_at_dt'].strftime('%Y-%m-%d %H:%M') if pd.notna(row['created_at_dt']) else 'Unknown',
                'text': text[:500],
                'keywords': keywords,
                'ai_score': row.get('ai_score', 5),
                'theme': classify_theme_brazil(text, keywords)
            }
            facts.append(fact)
        
        # 3. Group by theme
        themes = {theme: [] for theme in THEMES_BRAZIL.keys()}
        themes['outros'] = []
        for fact in facts:
            themes[fact['theme']].append(fact)
        
        # Sort by ai_score
        for theme in themes:
            themes[theme] = sorted(themes[theme], key=lambda x: x['ai_score'], reverse=True)
        
        # 4. Synthesize each theme
        client = anthropic.Anthropic(api_key=API_KEY)
        results = {}
        
        for theme, theme_facts in themes.items():
            if len(theme_facts) >= 3:
                top_facts = theme_facts[:15]
                facts_text = "\n".join([
                    f"[{f['timestamp']}] @{f['source']} (score:{f['ai_score']}): {f['text'][:300]}"
                    for f in top_facts
                ])
                
                prompt = f"""Você é um analista que APENAS resume os fatos fornecidos.

TEMA: {theme.replace('_', ' ').upper()}

FATOS DISPONÍVEIS (total: {len(top_facts)}):
{facts_text}

INSTRUÇÕES RIGOROSAS:
1. Resuma os fatos acima em 2-3 parágrafos em português
2. NÃO adicione nenhuma informação que não está nos fatos
3. NÃO cite fontes no texto - as fontes serão adicionadas automaticamente
4. Se algo não está nos fatos, NÃO mencione
5. Foque no que é NOVO e IMPORTANTE

Responda APENAS com o resumo, sem introdução ou conclusão."""
                

                response = client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=1000,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                summary = response.content[0].text
                sources = list(set(f['source'] for f in top_facts))
                
                results[theme] = {
                    'summary': summary,
                    'sources': sources,
                    'fact_count': len(top_facts)
                }
        
        # 5. Format HTML response
        html_parts = []
        html_parts.append(f'''
<div style="background: linear-gradient(135deg, #1a5f2a 0%, #0d3d1a 100%); color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
    <h2 style="margin: 0 0 10px 0; color: white;">🇧🇷 Brazil 24h - RAG Estruturado</h2>
    <p style="margin: 5px 0; opacity: 0.9;">📊 {total_items} itens | 📰 {unique_sources} fontes | ⏰ {time_range}</p>
    <p style="margin: 5px 0; opacity: 0.8; font-size: 12px;">✅ Fontes verificadas automaticamente - Sem alucinações</p>
</div>
''')
        
        theme_titles = {
            'politica_monetaria': '💰 Política Monetária',
            'politica_institucional': '⚖️ Política Institucional',
            'eleicoes_2026': '🗳️ Eleições 2026',
            'governo_lula': '🏛️ Governo Lula',
            'fiscal': '📊 Fiscal',
            'outros': '📰 Outros Temas'
        }
        
        for theme, data in results.items():
            theme_title = theme_titles.get(theme, theme.replace('_', ' ').title())
            sources_str = ', '.join([f'@{s}' for s in data['sources'][:5]])
            
            html_parts.append(f'''
<div style="background: rgba(255,255,255,0.05); border-radius: 8px; padding: 15px; margin-bottom: 15px; border-left: 4px solid #4ade80;">
    <h3 style="color: #4ade80; margin: 0 0 10px 0;">{theme_title}</h3>
    <p style="line-height: 1.6;">{data['summary']}</p>
    <p style="font-size: 12px; color: #888; margin-top: 10px;">
        <strong>Fontes ({len(data['sources'])}):</strong> {sources_str}
        | <strong>Fatos:</strong> {data['fact_count']}
    </p>
</div>
''')
        
        final_html = ''.join(html_parts)
        
        return jsonify({
            'status': 'success',
            'response': final_html,
            'metadata': {
                'total_items': total_items,
                'unique_sources': unique_sources,
                'time_range': time_range,
                'themes_processed': list(results.keys())
            }
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            'status': 'error',
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500



@app.route('/api/crons')
def get_crons_status():
    import subprocess
    import os
    from datetime import datetime
    
    crons_info = {
        'macro_scrapers': [
            {'name': 'Bloomberg', 'cron': '0 */4h', 'log': 'bloomberg.log', 'desc': 'Matt Levine, John Authers'},
            {'name': 'WSJ/Barrons', 'cron': '30 */4h', 'log': 'wsj_barrons.log', 'desc': 'Markets AM/PM, Politics'},
            {'name': 'ZeroHedge', 'cron': '0 */2h', 'log': 'zerohedge.log', 'desc': 'Premium articles'},
            {'name': 'Apricitas', 'cron': '0 */4h', 'log': 'aprecitas.log', 'desc': 'Economic + VLM'},
            {'name': 'Daily Shot', 'cron': '0 9h', 'log': 'dailyshot.log', 'desc': 'Global macro'},
        ],
        'brazil_scrapers': [
            {'name': 'BDM', 'cron': '0 5h', 'log': 'bdm_premium.log', 'desc': 'Morning Call'},
            {'name': 'Meio Politico', 'cron': '0 */3h', 'log': 'meio_politico.log', 'desc': 'Politics premium'},
            {'name': 'Pesquisas', 'cron': '0 */6h', 'log': 'pesquisas.log', 'desc': 'Election polls'},
            {'name': 'Columnists', 'cron': '30 11h', 'log': 'columnist_crawler.log', 'desc': 'Folha/Globo'},
            {'name': 'Daniela Lima', 'cron': '0 11,21h', 'log': 'daniela_lima.log', 'desc': 'UOL'},
        ],
        'email_pipeline': [
            {'name': 'Email Fetch', 'cron': ':15', 'log': 'email_processor.log', 'desc': 'Gmail fetch'},
            {'name': 'Tag Processor', 'cron': ':25', 'log': 'codex_tag.log', 'desc': 'Classify'},
            {'name': 'Vectorize', 'cron': ':35', 'log': 'vectorize_emails.log', 'desc': 'Voyage AI'},
            {'name': 'VLM', 'cron': ':45 /2h', 'log': 'codex_vlm.log', 'desc': 'PDF analysis'},
        ],
        'twitter': [
            {'name': 'Fetch', 'cron': ':00,:20,:40', 'log': 'twitter_master.log', 'desc': '3x/hour'},
            {'name': 'Vectorize', 'cron': ':05,:25,:45', 'log': 'vectorize.log', 'desc': 'Vectors'},
            {'name': 'Enrichment', 'cron': ':10,:30,:50', 'log': 'safe_enricher.log', 'desc': 'AI score'},
        ],
        'other': [
            {'name': 'Google Drive', 'cron': ':30', 'log': 'drive_to_goldman.log', 'desc': 'PDFs'},
        ]
    }
    
    for cat in crons_info.values():
        for c in cat:
            try:
                import os
                mtime = os.path.getmtime('/home/ubuntu/argus/logs/' + c.get('log', ''))
                c['last_run'] = datetime.fromtimestamp(mtime).strftime('%m-%d %H:%M')
                c['status'] = 'ok'
            except:
                c['last_run'] = 'N/A'
                c['status'] = 'unk'
    
    return jsonify({'crons': crons_info})


@app.route('/api/brazil_brief')
def brazil_brief_endpoint():
    """
    Brazil Brief - EXACT same pipeline as the email version.
    Runs: Bastidores (Sonnet) + Main Brief (Haiku) + Polymarket + Polls
    Module: brazil_brief_for_8550.py -> generate_full_brief()
    """
    from brazil_brief_for_8550 import generate_full_brief
    import json

    try:
        def generate():
            try:
                full_text = generate_full_brief()
                if not full_text:
                    err = json.dumps({"error": "No Brazil content available"})
                    yield f"data: {err}\n\n"
                    return

                chunk_size = 120
                for i in range(0, len(full_text), chunk_size):
                    chunk = json.dumps({"text": full_text[i:i+chunk_size]})
                    yield f"data: {chunk}\n\n"

                done = json.dumps({"done": True, "full_text": full_text})
                yield f"data: {done}\n\n"
            except Exception as e:
                err = json.dumps({"error": str(e)})
                yield f"data: {err}\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        )

    except Exception as e:
        return jsonify({"error": str(e), "brief": f"❌ Erro: {str(e)}"})




# Polymarket Universal Agent Endpoints (Feb 2026)
@app.route('/api/polymarket/<topic>')
def api_polymarket_topic(topic):
    if not POLYMARKET_AVAILABLE:
        return jsonify({"error": "Polymarket Agent not available"}), 503
    if topic not in PM_TOPICS:
        return jsonify({"error": f"Unknown topic. Available: {list(PM_TOPICS.keys())}"}), 404
    try:
        ctx, details = pm_get_live_context(topic)
        return jsonify({"status": "ok", "topic": topic, "label": PM_TOPICS[topic]['label'], "context": ctx, "details": details})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/polymarket/refresh', methods=['POST'])
def api_polymarket_refresh():
    if not POLYMARKET_AVAILABLE:
        return jsonify({"error": "Polymarket Agent not available"}), 503
    try:
        pm_run_all_snapshots()
        return jsonify({"status": "ok", "message": "All topics refreshed"})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/polymarket/history/<topic>')
def api_polymarket_history(topic):
    if not POLYMARKET_AVAILABLE:
        return jsonify({"error": "Polymarket Agent not available"}), 503
    hours = request.args.get('hours', 168, type=int)
    history = pm_get_topic_history(topic, hours)
    return jsonify({"status": "ok", "topic": topic, "history": history, "count": len(history)})

@app.route('/iran-dashboard')
def iran_dashboard():
    if not POLYMARKET_AVAILABLE:
        return "Polymarket Agent not available", 503
    try:
        ctx, details = pm_get_live_context('iran_conflict')
        if not details:
            return "No Iran data available", 404
        history = pm_get_topic_history('iran_conflict', 168)
        us30 = details.get('us30') or 0
        us90 = details.get('us90') or 0
        us365 = details.get('us365') or 0
        composite = (us90 * 0.35 + (details.get('isr90') or 0) * 0.15 + (details.get('cf90') or 0) * 0.15 + (details.get('regime') or 0) * 0.10 + (details.get('hormuz') or 0) * 0.10 + (details.get('nuke') or 0) * 0.05) / 0.9 * 100
        if us30 and us30 > 0.15: composite += us30 * 20
        composite = max(0, min(100, composite))
        def _pct(v): return round(v * 100, 1) if v else 0
        if composite < 25: rc, rl = 'risk-low', 'LOW RISK'
        elif composite < 50: rc, rl = 'risk-elevated', 'ELEVATED'
        elif composite < 75: rc, rl = 'risk-high', 'HIGH RISK'
        else: rc, rl = 'risk-critical', 'CRITICAL'
        term_filtered = {k: v for k, v in sorted(details.get('term_structure', {}).items(), key=lambda x: int(x[0])) if int(k) <= 200}
        with open('/home/ubuntu/argus/newspaper_project/iran_dashboard.html', 'r') as _f:
            tmpl = _f.read()
        return render_template_string(tmpl,
            composite=composite, risk_class=rc, risk_label=rl, trend='',
            volume=details.get('total_volume', 0), markets_tracked=details.get('markets_tracked', 0),
            updated=datetime.now(ZoneInfo('America/Sao_Paulo')).strftime('%Y-%m-%d %H:%M'),
            us30_pct=_pct(us30), us90_pct=_pct(us90), us365_pct=_pct(us365),
            isr_pct=_pct(details.get('isr90')), cf_pct=_pct(details.get('cf90')),
            regime_pct=_pct(details.get('regime')), hormuz_pct=_pct(details.get('hormuz')),
            nuke_pct=_pct(details.get('nuke')), deal_pct=_pct(details.get('deal')),
            term_structure=term_filtered, history=history)
    except Exception as e:
        return f"Error: {e}", 500

@app.route('/brazil-dashboard')
def brazil_dashboard():
    if not POLYMARKET_AVAILABLE:
        return "Polymarket Agent not available", 503
    try:
        ctx, details = pm_get_live_context('brazil_elections')
        if not details:
            return "No Brazil election data", 404
        with open('/home/ubuntu/argus/newspaper_project/brazil_dashboard.html', 'r') as _f:
            tmpl = _f.read()
        return render_template_string(tmpl,
            candidates=details.get('candidates', []),
            runoff=details.get('runoff', []),
            first_round=details.get('first_round'),
            total_volume=details.get('total_volume', 0),
            markets_tracked=details.get('markets_tracked', 0),
            updated=datetime.now(ZoneInfo('America/Sao_Paulo')).strftime('%Y-%m-%d %H:%M'),
            history=pm_get_topic_history('brazil_elections', 168))
    except Exception as e:
        return f"Error: {e}", 500

@app.route('/api/issues', methods=['GET'])
def api_issues():
    """Review #issue complaints. Filters: ?status=open&bot=m3xa"""
    status_filter = request.args.get('status', None)
    bot_filter = request.args.get('bot', None)
    try:
        conn = sqlite3.connect(CONVO_DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        sql = "SELECT * FROM issues WHERE 1=1"
        params = []
        if status_filter:
            sql += " AND status=?"
            params.append(status_filter)
        if bot_filter:
            sql += " AND bot=?"
            params.append(bot_filter)
        sql += " ORDER BY id DESC LIMIT 100"
        c.execute(sql, params)
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify({'issues': rows, 'count': len(rows)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/issues/<int:issue_id>/resolve', methods=['POST'])
def api_resolve_issue(issue_id):
    """Mark an issue as reviewed/resolved. Body: {"status": "reviewed"|"resolved"}"""
    data = request.json or {}
    new_status = data.get('status', 'reviewed')
    try:
        conn = sqlite3.connect(CONVO_DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE issues SET status=? WHERE id=?", (new_status, issue_id))
        conn.commit()
        affected = c.rowcount
        conn.close()
        return jsonify({'updated': affected, 'issue_id': issue_id, 'status': new_status})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/telegram-log', methods=['GET'])
def api_telegram_log():
    """Review Telegram conversation log. Filters: ?bot=m3xa&user=name&limit=50"""
    bot_filter = request.args.get('bot', None)
    user_filter = request.args.get('user', None)
    limit = int(request.args.get('limit', 50))
    try:
        conn = sqlite3.connect(CONVO_DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        sql = "SELECT id, timestamp, bot, chat_id, user_name, query, elapsed_seconds, sources, response_chars FROM conversations WHERE 1=1"
        params = []
        if bot_filter:
            sql += " AND bot=?"
            params.append(bot_filter)
        if user_filter:
            sql += " AND user_name LIKE ?"
            params.append(f"%{user_filter}%")
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        c.execute(sql, params)
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify({'conversations': rows, 'count': len(rows)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/telegram-log/<int:convo_id>', methods=['GET'])
def api_telegram_log_detail(convo_id):
    """Get full Telegram conversation detail including response text."""
    try:
        conn = sqlite3.connect(CONVO_DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM conversations WHERE id=?", (convo_id,))
        row = c.fetchone()
        conn.close()
        if row:
            return jsonify(dict(row))
        return jsonify({'error': 'Not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/telegram-macro', methods=['POST'])
def telegram_macro_6h():
    """Run Macro Themes with configurable window — structured per-theme Telegram messages"""
    import threading
    
    data = request.json or {}
    hours = int(data.get('hours', 6))
    if hours not in (6, 12, 24):
        hours = 6
    
    def _run_structured(hours=hours):
        import time as _t
        import json as _json
        _start = _t.time()
        print(f"[TG-MACRO] Starting structured {hours}h Macro Themes...", flush=True)
        
        send_telegram_message(
            f"🧠 <b>M3xA Macro Themes ({hours}h)</b>\n"
            "⏳ Running full RAG pipeline...\n"
            f"📡 Querying 110K+ items, filtering {hours}h window\n"
            "🤖 Haiku deep analysis in progress (~2 min)"
        )
        
        try:
            # ── Step 1: Get RAG context (same as the Macro Themes button) ──
            macro_query = PREMADE_QUERIES.get('macro', 'What are the major macro themes?')
            
            query_understanding = None
            try:
                query_understanding = understand_query(macro_query)
            except:
                pass
            
            context = get_rag_context(
                macro_query + " (Include relevant insights from WSJ, Bloomberg, and Financial Times)",
                ['macro'], limit=200,
                query_understanding=query_understanding,
                boost2_enabled=False,
                time_hours=hours
            )
            
            tweets = context.get('tweets', [])
            codex = context.get('codex', [])
            stats = context.get('stats', {})
            time_ctx = context.get('time_context', {})
            rows_in_window = time_ctx.get('rows_in_time_window', len(tweets))
            
            print(f"[TG-MACRO] Context: {len(tweets)} tweets, {rows_in_window} rows in 6h", flush=True)
            
            # ── Step 2: Build context string (same as main RAG) ──
            SOURCE_NAMES = {
                'gs_research': 'GOLDMAN SACHS', 'codex_goldman': 'GOLDMAN SACHS',
                'codex_gavekal': 'GAVEKAL', 'codex_ubs': 'UBS',
                'codex_rosenberg': 'ROSENBERG', 'codex_apollo': 'APOLLO',
                'codex_barrons': "BARRON\'S", 'codex_bloomberg': 'BLOOMBERG',
                'codex_spectra': 'SPECTRA MARKETS',
                'podcast_youtube_UCWOnz7XxWPScqfF1ejt': 'PROFESSOR JIANG',
                'podcast_youtube_UCNye-wNBqNL5ZzHSJj3': 'AL JAZEERA (YouTube)',
                'podcast_youtube_UCZFCDIHTe9HGxtIuVDp': 'GLENN DIESEN',
                'podcast_youtube_UCK0z0_5uL7mb9IjntOK': 'THE ATLANTIC (YouTube)',
                'podcast_youtube_UC11aHtNnc5bEPLI4jf6': 'PREDICTIVE HISTORY',
                'podcast_youtube_UCIALMKvObZNtJ6AmdCL': 'BLOOMBERG TV (YouTube)',
                'podcast_triggernometry': 'TRIGGERNOMETRY',
                'podcast_conflicted': 'CONFLICTED',
                'podcast_foreign_policy_live': 'FOREIGN POLICY LIVE',
                'podcast_gzero_world_with_ian_bremmer': 'GZERO WORLD',
                'podcast_bloomberg_surveillance': 'BLOOMBERG SURVEILLANCE',
                'podcast_bloomberg_odd_lots': 'BLOOMBERG ODD LOTS',
                'podcast_bloomberg_trumponomics': 'BLOOMBERG TRUMPONOMICS',
                'podcast_bloomberg_daybreak_us_edition': 'BLOOMBERG DAYBREAK',
                'podcast_goldman_exchanges': 'GOLDMAN EXCHANGES',
                'podcast_jpmorgan_at_any_rate': 'JPMORGAN AT ANY RATE',
                'podcast_jpmorgan_making_sense': 'JPMORGAN MAKING SENSE',
                'podcast_jpmorgan_global_data_pod': 'JPMORGAN DATA POD',
                'podcast_ubs_on_air_market_moves': 'UBS MARKET MOVES',
            }
            
            context_parts = []
            for t in tweets[:200]:
                src = SOURCE_NAMES.get(t['username'], f"@{t['username']}")
                context_parts.append(f"{src} (AI:{t['ai_score']}/10): {t['text'][:3000]}")
            for c in codex[:40]:
                context_parts.append(f"EMAIL {c['source']}: {c['text'][:3000]}")
            
            context_str = "\n---\n".join(context_parts)
            
            # ── Step 3: Agent Hub (markets, polymarket, calendar, boost) ──
            tg_agent_context = ""
            if AGENT_HUB_AVAILABLE:
                try:
                    hub_result = agent_hub.get_context(
                        query="iran conflict brazil election fed macro rates geopolitics",
                        mode='macro_telegram',
                        time_hours=hours,
                        boost_enabled=True,
                    )
                    tg_agent_context = hub_result.get('context', '')
                    print(f"[TG-MACRO] AgentHub: {hub_result.get('details', {})} = {hub_result.get('chars', 0)} chars", flush=True)
                except Exception as e:
                    print(f"[TG-MACRO] AgentHub error: {e}", flush=True)

            # ── Step 5: Structured JSON prompt for Telegram ──
            system_prompt = f"""You are M3xA Macro Agent — an experienced macro trader and economic analyst.

CURRENT TIME: {time_ctx.get('query_time_brazil', 'Unknown')} (Brazil)
DATA WINDOW: Last {hours} hours ({rows_in_window} items analyzed)

=== AGENT CONTEXT (markets, prediction markets, calendar, priority sources) ===
{tg_agent_context}

=== INTELLIGENCE DATA ===
{context_str}

=== YOUR TASK ===
Analyze the data and identify the TOP 8 MACRO THEMES from the last {hours} hours.

RESPOND IN VALID JSON ONLY. No markdown, no text outside the JSON.
The response must be a JSON object with this exact structure:

{{
  "executive_summary": "2-3 sentence overview of the macro landscape right now. If prediction market probabilities are surging or plunging on ANY topic, lead with that.",
  "themes": [
    {{
      "rank": 1,
      "emoji": "📉",
      "name": "Theme Title",
      "analysis": "4-6 sentence deep analysis. MUST weave in Polymarket prediction market probability evolution when the theme relates to Iran, geopolitics, Brazil, elections, or Fed policy. State the current probability AND how it changed (daily, weekly, month-to-date). Example: 'US strike probability surged to 67.5% from 54% yesterday (+13.5pp daily), with the entire term structure shifting up +18pp, reflecting the most aggressive single-day repricing since the contracts launched.'",
      "prediction_markets": "Required for Iran/Brazil/election/Fed themes. Format: 'US strike 30d: 67% (+13pp D, +5pp W) | Lula: 46% (-2pp D, -6pp W)'. Set to null if theme has no relevant prediction market data.",
      "sentiment": "Bullish/Bearish/Neutral/Mixed",
      "key_numbers": ["10Y at 4.32%", "Polymarket US strike 67.5% (+13pp daily)"],
      "sources": ["@source1", "Polymarket", "@source3"]
    }}
  ]
}}

RULES:
- Exactly 8 themes, ranked by importance
- Each analysis must have SPECIFIC numbers and data points from the sources
- Compare perspectives: what does Goldman say vs Bloomberg vs FT?
- Include contrarian or minority views when present
- CRITICAL — PREDICTION MARKET EVOLUTION IS MANDATORY:
  * For ANY theme touching Iran, geopolitics, Middle East, military, Brazil, elections, Fed policy, or rate cuts:
    you MUST include the "prediction_markets" field with current probabilities AND their daily/weekly/MTD changes.
  * In the "analysis" text, describe the TREND: "surging", "plunging", "accelerating", "stable" — show how the crowd's money moved over time.
  * The daily change shows the latest shock. The weekly change shows the trend. The MTD shows the bigger picture.
  * This is REAL MONEY — $100M+ wagered — making it the most honest signal of crowd expectations.
  * If Polymarket data is available above but you fail to reference it for a relevant theme, the output is INCOMPLETE.
- key_numbers: 2-4 specific figures per theme (Polymarket probabilities count as key numbers)
- sources: 2-4 per theme (include "Polymarket" when prediction market data is used)
- sentiment must be exactly one of: Bullish, Bearish, Neutral, Mixed
- VALID JSON ONLY — no trailing commas, no comments"""

            # ── Step 6: Call Haiku ──
            print("[TG-MACRO] Calling Haiku for structured analysis...", flush=True)
            client = anthropic.Anthropic(api_key=API_KEY)
            
            response = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=8000,
                messages=[{"role": "user", "content": "Generate the structured macro themes analysis as JSON."}],
                system=system_prompt
            )
            
            raw = response.content[0].text.strip()
            elapsed = round(_t.time() - _start, 1)
            print(f"[TG-MACRO] Haiku returned {len(raw)} chars in {elapsed}s", flush=True)
            
            # ── Step 7: Parse JSON ──
            # Clean potential markdown code fences
            if raw.startswith('```'):
                raw = raw.split('\n', 1)[1] if '\n' in raw else raw[3:]
                if raw.endswith('```'):
                    raw = raw[:-3]
            raw = raw.strip()
            
            try:
                result = _json.loads(raw)
            except _json.JSONDecodeError as je:
                print(f"[TG-MACRO] JSON parse error: {je}", flush=True)
                # Fallback: send raw as single message
                send_telegram_message(
                    f"🧠 <b>M3xA Macro Themes ({hours}h)</b>\n"
                    f"📊 {len(tweets)} sources | ⏱ {elapsed}s\n"
                    f"{'─' * 30}\n\n" + raw[:4000]
                )
                return
            
            # ── Step 8: Send structured Telegram messages ──
            themes = result.get('themes', [])
            summary = result.get('executive_summary', '')
            
            # Message 1: Header + Executive Summary
            header = (
                f"🧠 <b>M3xA Macro Themes ({hours}h)</b>\n"
                f"📊 {len(tweets)} sources | {rows_in_window} in window | ⏱ {elapsed}s\n"
                f"🕐 {time_ctx.get('temporal_filter', 'Last 6h')}\n"
                f"{'━' * 28}\n\n"
                f"<b>Executive Summary</b>\n"
                f"{summary}"
            )
            send_telegram_message(header)
            _t.sleep(0.5)
            
            # Messages 2-9: One per theme
            for theme in themes:
                rank = theme.get('rank', '?')
                emoji = theme.get('emoji', '📌')
                name = theme.get('name', 'Unknown')
                analysis = theme.get('analysis', '')
                sentiment = theme.get('sentiment', '?')
                key_nums = theme.get('key_numbers', [])
                sources = theme.get('sources', [])
                
                # Sentiment emoji
                sent_emoji = {'Bullish': '🟢', 'Bearish': '🔴', 'Neutral': '⚪', 'Mixed': '🟡'}.get(sentiment, '⚪')
                
                # Format key numbers
                nums_str = " | ".join(key_nums) if key_nums else ""
                sources_str = ", ".join(sources) if sources else ""
                
                # Prediction markets line
                pm_line = theme.get('prediction_markets') or ""
                
                msg = (
                    f"{emoji} <b>{rank}. {name}</b>\n"
                    f"{sent_emoji} {sentiment}\n\n"
                    f"{analysis}\n"
                )
                if pm_line and pm_line != "null":
                    msg += f"\n🎰 <b>Markets:</b> {pm_line}"
                if nums_str:
                    msg += f"\n📊 <b>Key:</b> {nums_str}"
                if sources_str:
                    msg += f"\n📡 {sources_str}"
                
                send_telegram_message(msg)
                _t.sleep(0.3)
            
            # Message 10: Footer
            footer = (
                f"{'━' * 28}\n"
                f"✅ <b>M3xA Analysis Complete</b>\n"
                f"📊 {len(themes)} themes | {len(tweets)} sources analyzed\n"
                f"⏱ Generated in {elapsed}s\n"
                f"🕐 {time_ctx.get('query_time_brazil', '')}"
            )
            send_telegram_message(footer)
            
            print(f"[TG-MACRO] Done! Sent {2 + len(themes)} structured messages in {_t.time()-_start:.1f}s", flush=True)
            
        except Exception as e:
            import traceback
            print(f"[TG-MACRO] Error: {e}\n{traceback.format_exc()}", flush=True)
            send_telegram_message(f"❌ Error: {str(e)[:300]}")
    
    t = threading.Thread(target=_run_structured, daemon=True)
    t.start()
    
    return jsonify({"status": "processing", "message": "Macro 6h sent to Telegram. Check your phone."})


@app.route('/api/send_email', methods=['POST'])
def send_analysis_email():
    """Send the latest analysis to pedro.ribeiro@jpmorgan.com with beautiful styling"""
    try:
        data = request.json
        response_text = data.get("response", "")
        query = data.get("query", "Analysis")
        
        print(f"[EMAIL] Received send_email request. query={query!r}, response_len={len(response_text)}, first_100={response_text[:100]!r}", flush=True)
        
        if not response_text or len(response_text.strip()) < 10:
            print(f"[EMAIL] WARNING: response_text is empty or too short!", flush=True)
        
        import re
        
        # Clean the response - remove full sources attribution
        if "SOURCES CITED" in response_text:
            response_text = response_text.split("SOURCES CITED")[0].strip()
        
        patterns = [r"Research Institutions:.*", r"News Outlets:.*", r"Analyst Commentary:.*"]
        for p in patterns:
            response_text = re.sub(p, "", response_text, flags=re.DOTALL)
        response_text = response_text.strip()
        
        # Format content with styling
        html_body = response_text
        
        # Bold text
        html_body = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html_body)
        
        # Section headers with colored boxes
        sections = [
            ("## ", "#667eea", "#f0f4ff"),
            ("### ", "#059669", "#ecfdf5"),
            ("🌍", "#2563eb", "#eff6ff"),
            ("🇧🇷", "#059669", "#ecfdf5"),
            ("📊", "#7c3aed", "#faf5ff"),
            ("💰", "#d97706", "#fffbeb"),
            ("🏦", "#dc2626", "#fef2f2"),
        ]
        
        for marker, color, bg in sections:
            if marker in html_body:
                lines = html_body.split("\n")
                new_lines = []
                for line in lines:
                    if line.strip().startswith(marker):
                        header_text = line.strip().replace("## ", "").replace("### ", "")
                        styled = f'<div style="background:{bg};border-left:4px solid {color};padding:12px 16px;margin:16px 0;border-radius:0 8px 8px 0;"><strong style="color:{color};font-size:15px;">{header_text}</strong></div>'
                        new_lines.append(styled)
                    else:
                        new_lines.append(line)
                html_body = "\n".join(new_lines)
        
        # Bullet points
        html_body = re.sub(r"^- (.+)$", r'<div style="margin:6px 0;padding-left:16px;border-left:3px solid #e5e7eb;">▸ \1</div>', html_body, flags=re.MULTILINE)
        html_body = re.sub(r"• (.+?)(<br>|\n|$)", r'<div style="margin:6px 0;padding-left:16px;border-left:3px solid #e5e7eb;">▸ \1</div>\2', html_body)
        
        # @mentions
        html_body = re.sub(r"@(\w+)", r'<strong style="color:#667eea;">@\1</strong>', html_body)
        
        # Line breaks
        html_body = html_body.replace("\n\n", '</p><p style="margin:12px 0;line-height:1.7;color:#374151;">')
        html_body = html_body.replace("\n", "<br>")
        
        from datetime import datetime
        now = datetime.now()
        date_str = now.strftime("%d/%m/%Y %H:%M")
        subject = f"M3xA Intelligence - {query[:40]} - {date_str}"
        
        html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background-color:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
    <div style="max-width:750px;margin:20px auto;background:#fff;border-radius:16px;box-shadow:0 4px 20px rgba(0,0,0,0.1);">
        <div style="background:linear-gradient(135deg,#667eea,#764ba2);padding:30px;text-align:center;border-radius:16px 16px 0 0;">
            <div style="font-size:42px;margin-bottom:10px;">🧠</div>
            <h1 style="color:#fff;margin:0;font-size:28px;font-weight:700;">M3xA Intelligence</h1>
            <p style="color:#e0e7ff;margin:8px 0 0 0;font-size:14px;">Market Augmented Awareness Agent</p>
        </div>
        <div style="background:#f8fafc;padding:15px 30px;border-bottom:1px solid #e5e7eb;">
            <p style="margin:0;color:#64748b;font-size:13px;">📋 <strong>Query:</strong> {query}</p>
            <p style="margin:5px 0 0 0;color:#64748b;font-size:13px;">📅 <strong>Generated:</strong> {date_str}</p>
        </div>
        <div style="padding:30px;color:#1f2937;">
            <p style="margin:12px 0;line-height:1.7;color:#374151;">{html_body}</p>
        </div>
        <div style="background:linear-gradient(135deg,#f8fafc,#e2e8f0);padding:20px;text-align:center;border-top:1px solid #e5e7eb;border-radius:0 0 16px 16px;">
            <p style="color:#64748b;font-size:12px;margin:0;">
                🤖 <strong>M3xA</strong> - Powered by M3xA<br>
                📊 Sources: Twitter, Bloomberg, Reuters, WSJ, Substack
            </p>
        </div>
    </div>
</body>
</html>"""
        
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = formataddr(("M3xA Intelligence", EMAIL_USER_8550))
        msg["To"] = RECIPIENT_8550
        
        text_part = MIMEText(response_text, "plain", "utf-8")
        html_part = MIMEText(html_content, "html", "utf-8")
        
        msg.attach(text_part)
        msg.attach(html_part)
        
        print(f"[EMAIL] Connecting to Gmail SMTP...", flush=True)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_USER_8550, EMAIL_PASS_8550)
            server.send_message(msg)
        
        print(f"[EMAIL] SENT OK to {RECIPIENT_8550} | subject={subject!r} | body_len={len(response_text)}", flush=True)
        return jsonify({"status": "sent", "recipient": RECIPIENT_8550})
        
    except Exception as e:
        import traceback
        print(f"[EMAIL] ERROR: {type(e).__name__}: {e}", flush=True)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════════════
# WHATSAPP BUSINESS CLOUD API — Interactive M3xA queries via WhatsApp
# ═══════════════════════════════════════════════════════════════════════════════
WHATSAPP_VERIFY_TOKEN = os.environ.get('WHATSAPP_VERIFY_TOKEN', '')  # stripped for public repo
WHATSAPP_ACCESS_TOKEN = os.environ.get('WHATSAPP_ACCESS_TOKEN', '')
WHATSAPP_PHONE_ID = os.environ.get('WHATSAPP_PHONE_ID', '')
WHATSAPP_ALLOWED_NUMBER = os.environ.get('WHATSAPP_ALLOWED_NUMBER', '')

def send_whatsapp_message(to, text):
    """Send a WhatsApp message via Cloud API, splitting if > 4096 chars."""
    import requests as _wa_req
    if not WHATSAPP_ACCESS_TOKEN or not WHATSAPP_PHONE_ID:
        print("[WA] WhatsApp not configured (missing token or phone_id)", flush=True)
        return 0
    API_URL = f"https://graph.facebook.com/v21.0/{WHATSAPP_PHONE_ID}/messages"
    HEADERS = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    MAX_LEN = 4000
    chunks = []
    while len(text) > MAX_LEN:
        sp = text.rfind('\n', 0, MAX_LEN)
        if sp == -1:
            sp = MAX_LEN
        chunks.append(text[:sp])
        text = text[sp:].lstrip('\n')
    chunks.append(_sanitize_tg_html(text))
    sent = 0
    for chunk in chunks:
        try:
            payload = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": chunk}
            }
            r = _wa_req.post(API_URL, headers=HEADERS, json=payload, timeout=30)
            if r.status_code in (200, 201):
                sent += 1
            else:
                print(f"[WA] Send error: {r.status_code} {r.text[:200]}", flush=True)
            import time
            time.sleep(0.3)
        except Exception as e:
            print(f"[WA] Send exception: {e}", flush=True)
    return sent


def format_for_whatsapp(markdown_text):
    """Convert markdown to WhatsApp-friendly plain text with bold/italic."""
    t = markdown_text
    t = re.sub(r'###\s*(.+)', r'*\1*', t)
    t = re.sub(r'##\s*(.+)', r'*\1*', t)
    t = re.sub(r'\*\*(.+?)\*\*', r'*\1*', t)
    t = re.sub(r'<b>(.+?)</b>', r'*\1*', t)
    t = re.sub(r'<i>(.+?)</i>', r'_\1_', t)
    t = re.sub(r'<[^>]+>', '', t)
    return t


@app.route('/webhook/whatsapp', methods=['GET'])
def whatsapp_verify():
    """Meta webhook verification challenge."""
    mode = request.args.get('hub.mode', '')
    token = request.args.get('hub.verify_token', '')
    challenge = request.args.get('hub.challenge', '')
    if mode == 'subscribe' and token == WHATSAPP_VERIFY_TOKEN:
        print(f"[WA] Webhook verified OK", flush=True)
        return challenge, 200
    print(f"[WA] Webhook verification FAILED (token mismatch)", flush=True)
    return 'Forbidden', 403


@app.route('/webhook/whatsapp', methods=['POST'])
def whatsapp_webhook():
    """Receive WhatsApp messages, query /api/rag, reply."""
    import threading
    body = request.json or {}

    entries = body.get('entry', [])
    for entry in entries:
        for change in entry.get('changes', []):
            value = change.get('value', {})
            messages = value.get('messages', [])
            for msg in messages:
                msg_type = msg.get('type', '')
                sender = msg.get('from', '')
                text = msg.get('text', {}).get('body', '').strip() if msg_type == 'text' else ''

                if not text:
                    continue

                if WHATSAPP_ALLOWED_NUMBER and sender != WHATSAPP_ALLOWED_NUMBER:
                    print(f"[WA] Blocked message from unauthorized number: {sender}", flush=True)
                    continue

                print(f"[WA] Message from {sender}: {text[:100]}", flush=True)

                def _handle_wa_query(sender=sender, text=text):
                    import requests as _rq
                    RAG_URL = "http://127.0.0.1:8550/api/rag"

                    send_whatsapp_message(sender, f"\U0001f50d *Querying M3xA...*\n_{text[:200]}_\n\u23f3 ~2-3 min for full analysis")

                    try:
                        rag_resp = _rq.post(RAG_URL, json={
                            "query": text,
                            "filters": ["macro", "brazil", "codex"],
                            "session_id": f"whatsapp_{sender}"
                        }, timeout=180)

                        if rag_resp.status_code == 200:
                            result = rag_resp.json()
                            answer = result.get("response", "No response generated.")
                            elapsed = result.get("elapsed_seconds", "?")
                            sources = result.get("sources", {})

                            wa_answer = format_for_whatsapp(answer)
                            src_tweets = sources.get("tweets", 0)
                            src_macro = sources.get("macro", 0)
                            src_brazil = sources.get("brazil", 0)
                            footer = (
                                f"\n\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
                                f"\u23f1 {elapsed}s | "
                                f"\U0001f4ca {src_tweets} tweets, "
                                f"{src_macro} macro, {src_brazil} brazil"
                            )
                            send_whatsapp_message(sender, wa_answer + footer)
                            print(f"[WA] Reply sent to {sender} ({elapsed}s)", flush=True)
                        else:
                            send_whatsapp_message(sender, f"\u274c RAG error: HTTP {rag_resp.status_code}")
                    except Exception as e:
                        send_whatsapp_message(sender, f"\u274c Error: {str(e)[:200]}")
                        print(f"[WA] Error: {e}", flush=True)

                threading.Thread(target=_handle_wa_query, daemon=True).start()

    return 'OK', 200


# ═══════════════════════════════════════════════════════════════════════════════
# TWILIO WHATSAPP WEBHOOK — Interactive M3xA queries via WhatsApp (Twilio)
# ═══════════════════════════════════════════════════════════════════════════════
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')  # stripped for public repo
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')  # stripped for public repo
TWILIO_WHATSAPP_FROM = os.environ.get('TWILIO_WHATSAPP_FROM', '')

def send_twilio_whatsapp(to, text):
    """Send a WhatsApp message via Twilio API, splitting if > 1600 chars."""
    import requests as _tw_req
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_WHATSAPP_FROM:
        print("[TW-WA] Twilio not configured", flush=True)
        return 0
    URL = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    MAX_LEN = 1500
    chunks = []
    while len(text) > MAX_LEN:
        sp = text.rfind('\n', 0, MAX_LEN)
        if sp == -1:
            sp = MAX_LEN
        chunks.append(text[:sp])
        text = text[sp:].lstrip('\n')
    chunks.append(_sanitize_tg_html(text))
    sent = 0
    for chunk in chunks:
        try:
            r = _tw_req.post(URL, data={
                "From": TWILIO_WHATSAPP_FROM,
                "To": to,
                "Body": chunk
            }, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN), timeout=30)
            if r.status_code in (200, 201):
                sent += 1
            else:
                print(f"[TW-WA] Send error: {r.status_code} {r.text[:200]}", flush=True)
            import time
            time.sleep(0.3)
        except Exception as e:
            print(f"[TW-WA] Send exception: {e}", flush=True)
    return sent


@app.route('/webhook/twilio-whatsapp', methods=['POST'])
def twilio_whatsapp_webhook():
    """Receive WhatsApp messages via Twilio, query /api/rag, reply."""
    import threading

    sender = request.form.get('From', '')
    text = request.form.get('Body', '').strip()
    num_media = int(request.form.get('NumMedia', 0))

    if not text:
        return '<Response></Response>', 200, {'Content-Type': 'text/xml'}

    print(f"[TW-WA] Message from {sender}: {text[:100]}", flush=True)

    def _handle_twilio_query(sender=sender, text=text):
        import requests as _rq
        RAG_URL = "http://127.0.0.1:8550/api/rag"

        send_twilio_whatsapp(sender, f"\U0001f1e7\U0001f1f7 *M3xA_Brazil querying...*\n_{text[:200]}_\n\u23f3 ~2-3 min for full analysis")

        try:
            rag_resp = _rq.post(RAG_URL, json={
                "query": text,
                "filters": ["brazil"],
                "session_id": f"twilio_wa_{sender}"
            }, timeout=180)

            if rag_resp.status_code == 200:
                result = rag_resp.json()
                answer = result.get("response", "No response generated.")
                elapsed = result.get("elapsed_seconds", "?")
                sources = result.get("sources", {})

                wa_answer = format_for_whatsapp(answer)
                src_tweets = sources.get("tweets", 0)
                src_macro = sources.get("macro", 0)
                src_brazil = sources.get("brazil", 0)
                footer = (
                    f"\n\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
                    f"\u23f1 {elapsed}s | "
                    f"\U0001f4ca {src_tweets} tweets, "
                    f"{src_macro} macro, {src_brazil} brazil"
                )
                send_twilio_whatsapp(sender, wa_answer + footer)
                print(f"[TW-WA] Reply sent to {sender} ({elapsed}s)", flush=True)
            else:
                send_twilio_whatsapp(sender, f"\u274c RAG error: HTTP {rag_resp.status_code}")
        except Exception as e:
            send_twilio_whatsapp(sender, f"\u274c Error: {str(e)[:200]}")
            print(f"[TW-WA] Error: {e}", flush=True)

    threading.Thread(target=_handle_twilio_query, daemon=True).start()

    return '<Response></Response>', 200, {'Content-Type': 'text/xml'}


# ═══════════════════════════════════════════════════════════════════════════════
# TELEGRAM INTERACTIVE POLLING — queries /api/rag and replies in Telegram
# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
# M3xA_BRAZIL TELEGRAM BOT — Brazil-focused queries + receives Brazil Brief
# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
# TELEGRAM BOT ACCESS CONTROL — "turma" join system
# ═══════════════════════════════════════════════════════════════════════════════
APPROVED_USERS_FILE = '/home/ubuntu/argus/newspaper_project/telegram_approved_users.json'

def _load_approved_users():
    """Load approved Telegram chat IDs from file."""
    import json
    try:
        with open(APPROVED_USERS_FILE, 'r') as f:
            return set(str(x) for x in json.load(f))
    except:
        return set()

def _save_approved_users(users):
    """Save approved Telegram chat IDs to file."""
    import json
    with open(APPROVED_USERS_FILE, 'w') as f:
        json.dump(list(users), f)

def _is_approved(chat_id):
    """Check if a chat ID is approved (owner always approved)."""
    if str(chat_id) == str(TELEGRAM_CHAT_ID):
        return True
    return str(chat_id) in _load_approved_users()

def _approve_user(chat_id, user_name):
    """Add a user to the approved list."""
    users = _load_approved_users()
    users.add(str(chat_id))
    _save_approved_users(users)
    print(f"[TG-ACCESS] Approved new user: {user_name} (chat_id={chat_id})", flush=True)


# ═══════════════════════════════════════════════════════════════════════════════
# CONVERSATION LOGGING + #issue COMPLAINT SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

CONVO_DB_PATH = '/home/ubuntu/argus/newspaper_project/telegram_conversations.db'

def _init_conversation_db():
    """Create conversations and issues tables if they don't exist."""
    conn = sqlite3.connect(CONVO_DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
        bot TEXT,
        chat_id TEXT,
        user_name TEXT,
        query TEXT,
        response TEXT,
        elapsed_seconds REAL,
        sources TEXT,
        response_chars INTEGER
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS issues (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
        bot TEXT,
        chat_id TEXT,
        user_name TEXT,
        complaint TEXT,
        last_query TEXT,
        last_response TEXT,
        status TEXT DEFAULT 'open'
    )""")
    conn.commit()
    conn.close()

_init_conversation_db()
print("[CONVO-LOG] Conversation logging DB initialized", flush=True)


def _log_conversation(bot, chat_id, user_name, query, response, elapsed, sources):
    """Log a Q&A pair to the conversations table."""
    try:
        conn = sqlite3.connect(CONVO_DB_PATH)
        c = conn.cursor()
        c.execute(
            "INSERT INTO conversations (bot, chat_id, user_name, query, response, elapsed_seconds, sources, response_chars) VALUES (?,?,?,?,?,?,?,?)",
            (bot, str(chat_id), user_name, query, response,
             float(elapsed) if elapsed else 0,
             json.dumps(sources) if isinstance(sources, dict) else str(sources),
             len(response) if response else 0)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[CONVO-LOG] Error logging conversation: {e}", flush=True)


def _get_last_conversation(bot, chat_id):
    """Get the most recent Q&A for a user on a given bot."""
    try:
        conn = sqlite3.connect(CONVO_DB_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT query, response FROM conversations WHERE bot=? AND chat_id=? ORDER BY id DESC LIMIT 1",
            (bot, str(chat_id))
        )
        row = c.fetchone()
        conn.close()
        if row:
            return {'query': row[0], 'response': row[1]}
    except Exception as e:
        print(f"[CONVO-LOG] Error fetching last conversation: {e}", flush=True)
    return None


def _hydrate_session_from_db(session_id, bot, chat_id, max_exchanges=2, max_age_min=30):
    """Load recent conversation history from DB into chat_sessions if empty.
    Called on first Telegram query after a restart to restore continuity."""
    if session_id in chat_sessions and len(chat_sessions[session_id]) > 0:
        return  # Already has in-memory history
    try:
        conn = sqlite3.connect(CONVO_DB_PATH)
        c = conn.cursor()
        c.execute(
            """SELECT query, response FROM conversations 
               WHERE bot=? AND chat_id=? 
               AND timestamp > datetime('now', ?)
               ORDER BY id DESC LIMIT ?""",
            (bot, str(chat_id), f'-{max_age_min} minutes', max_exchanges)
        )
        rows = c.fetchall()
        conn.close()
        if rows:
            chat_sessions[session_id] = []
            for query, response in reversed(rows):
                truncated_resp = response[:2000] if response else ""
                chat_sessions[session_id].append({"role": "user", "content": query})
                chat_sessions[session_id].append({"role": "assistant", "content": truncated_resp})
            print(f"[SESSION] Hydrated {len(rows)} exchanges for {session_id} from DB", flush=True)
    except Exception as e:
        print(f"[SESSION] Hydration error: {e}", flush=True)


def _log_issue(bot, chat_id, user_name, complaint):
    """Log a #issue complaint with the last Q&A as context."""
    last = _get_last_conversation(bot, chat_id)
    try:
        conn = sqlite3.connect(CONVO_DB_PATH)
        c = conn.cursor()
        c.execute(
            "INSERT INTO issues (bot, chat_id, user_name, complaint, last_query, last_response) VALUES (?,?,?,?,?,?)",
            (bot, str(chat_id), user_name, complaint,
             last['query'] if last else None,
             last['response'] if last else None)
        )
        conn.commit()
        conn.close()
        print(f"[ISSUE] New issue from {user_name} on {bot}: {complaint[:100]}", flush=True)
    except Exception as e:
        print(f"[ISSUE] Error logging issue: {e}", flush=True)


# ═══════════════════════════════════════════════════════════════════════════════
# #code INVESTIGATION SYSTEM — Phase 1: read-only autonomous agent
# ═══════════════════════════════════════════════════════════════════════════════

def _run_code_investigation(request, chat_id, user_name, bot_name, send_fn):
    """Run #code investigation in background thread via maintenance_agent."""
    try:
        import sys as _sys
        import importlib as _imp
        if '/home/ubuntu/argus/scripts' not in _sys.path:
            _sys.path.insert(0, '/home/ubuntu/argus/scripts')
        import maintenance_agent
        _imp.reload(maintenance_agent)
        from maintenance_agent import investigate
        inv_id, finding, tools_used = investigate(
            request, bot=bot_name, chat_id=chat_id, user_name=user_name)
        header = f"\U0001f50d <b>Investigation #{inv_id}</b> ({tools_used} lookups)\n\n"
        result = format_for_telegram(finding)
        send_fn(header + result, chat_id=chat_id)
    except Exception as e:
        send_fn(f"\u274c <b>Agent error:</b> {str(e)[:300]}", chat_id=chat_id)
        print(f"[CODE] Investigation error: {e}", flush=True)


TELEGRAM_BR_BOT_TOKEN = os.environ.get('TELEGRAM_BR_BOT_TOKEN', '')  # stripped for public repo
TELEGRAM_BR_CHAT_ID = TELEGRAM_CHAT_ID  # same user

_tg_br_last_update_id = 0

def send_telegram_brazil(text, parse_mode="HTML", chat_id=None):
    """Send message via M3xA_Brazil bot."""
    import requests as _tg_br_req
    target = chat_id or TELEGRAM_BR_CHAT_ID
    MAX_LEN = 4000
    chunks = []
    while len(text) > MAX_LEN:
        sp = text.rfind('\n', 0, MAX_LEN)
        if sp == -1:
            sp = MAX_LEN
        chunk = text[:sp]
        chunk = _close_open_tags(chunk)
        chunk = _sanitize_tg_html(chunk)
        chunks.append(chunk)
        text = text[sp:].lstrip('\n')
    chunks.append(_sanitize_tg_html(text))
    sent = 0
    for chunk in chunks:
        try:
            r = _tg_br_req.post(
                f"https://api.telegram.org/bot{TELEGRAM_BR_BOT_TOKEN}/sendMessage",
                json={"chat_id": target, "text": chunk, "parse_mode": parse_mode},
                timeout=30
            )
            if not r.json().get('ok'):
                import re as _strip_re
                plain = _strip_re.sub(r'<[^>]+>', '', chunk)
                _tg_br_req.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BR_BOT_TOKEN}/sendMessage",
                    json={"chat_id": target, "text": plain},
                    timeout=30
                )
            sent += 1
            import time; time.sleep(0.3)
        except Exception as e:
            print(f"[TG-BR] Send error: {e}", flush=True)
    return sent


def send_telegram_brazil_photo(photo_bytes, chat_id=None, caption=None):
    """Send a photo (BytesIO PNG) via M3xA_Brazil bot."""
    import requests as _tg_br_req
    target = chat_id or TELEGRAM_BR_CHAT_ID
    try:
        files = {"photo": ("chart.png", photo_bytes, "image/png")}
        data = {"chat_id": target}
        if caption:
            data["caption"] = caption[:1024]
        r = _tg_br_req.post(
            f"https://api.telegram.org/bot{TELEGRAM_BR_BOT_TOKEN}/sendPhoto",
            files=files, data=data, timeout=30
        )
        return r.json().get('ok', False)
    except Exception as e:
        print(f"[TG-BR] Photo send error: {e}", flush=True)
        return False


def _run_brazil_brief_telegram(hours, chat_id, user_name):
    """Background thread: generate and send Brazil Brief via Telegram."""
    import traceback
    try:
        import sys, importlib
        sys.path.insert(0, '/home/ubuntu/argus/newspaper_project')
        import brazil_brief_for_8550
        importlib.reload(brazil_brief_for_8550)
        generate_full_brief = brazil_brief_for_8550.generate_full_brief

        result = generate_full_brief(hours=hours)

        if not result or len(result) < 100:
            send_telegram_brazil("\u274c Erro ao gerar Brief. Sem conteudo suficiente.", chat_id=chat_id)
            return

        # Split into chunks for Telegram (max ~4000 chars per message)
        MAX_CHUNK = 3800
        chunks = []
        lines = result.split('\n')
        current_chunk = ""
        for line in lines:
            if len(current_chunk) + len(line) + 1 > MAX_CHUNK:
                chunks.append(current_chunk)
                current_chunk = line
            else:
                current_chunk += ("\n" + line) if current_chunk else line
        if current_chunk:
            chunks.append(current_chunk)

        for i, chunk in enumerate(chunks):
            tg_chunk = format_for_telegram(chunk)
            if i == len(chunks) - 1:
                tg_chunk += f"\n\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\U0001f1e7\U0001f1f7 Brazil Brief ({hours}h) | {len(result)} chars"
            send_telegram_brazil(tg_chunk, chat_id=chat_id)
            import time; time.sleep(1)

        print(f"[TG-BR] Brief ({hours}h) sent to {user_name}: {len(result)} chars, {len(chunks)} msgs", flush=True)

    except Exception as e:
        print(f"[TG-BR] Brief error: {e}\n{traceback.format_exc()}", flush=True)
        send_telegram_brazil(f"\u274c Erro ao gerar Brief: {str(e)[:200]}", chat_id=chat_id)



def _wait_for_telegram_dns(tag="TG", max_wait=120):
    """Block until api.telegram.org resolves. Prevents stale DNS cache in requests."""
    import socket, time
    start = time.time()
    while time.time() - start < max_wait:
        try:
            socket.getaddrinfo('api.telegram.org', 443)
            print(f"[{tag}] DNS ready for api.telegram.org", flush=True)
            return True
        except socket.gaierror:
            print(f"[{tag}] Waiting for DNS... ({int(time.time()-start)}s)", flush=True)
            time.sleep(5)
    print(f"[{tag}] DNS not ready after {max_wait}s, proceeding anyway", flush=True)
    return False

def _telegram_brazil_poll_loop():
    """Background thread: poll M3xA_Brazil bot, forward to /api/rag with Brazil filter."""
    import requests as _rq
    import time as _t
    global _tg_br_last_update_id

    API = f"https://api.telegram.org/bot{TELEGRAM_BR_BOT_TOKEN}"
    RAG_URL = "http://127.0.0.1:8550/api/rag"
    ALLOWED_CHAT = str(TELEGRAM_BR_CHAT_ID)

    print("[TG-BR] M3xA_Brazil Telegram polling started", flush=True)

    _wait_for_telegram_dns("TG-BR")

    try:
        r = _rq.get(f"{API}/getUpdates", params={"limit": 1, "offset": -1}, timeout=10)
        updates = r.json().get("result", [])
        if updates:
            _tg_br_last_update_id = updates[-1]["update_id"] + 1
            print(f"[TG-BR] Skipping old messages, starting from update_id {_tg_br_last_update_id}", flush=True)
    except Exception as e:
        print(f"[TG-BR] Init error: {e}", flush=True)

    while True:
        try:
            r = _rq.get(
                f"{API}/getUpdates",
                params={"offset": _tg_br_last_update_id, "timeout": 30, "allowed_updates": '["message"]'},
                timeout=40
            )
            updates = r.json().get("result", [])

            for upd in updates:
                _tg_br_last_update_id = upd["update_id"] + 1
                msg_data = upd.get("message", {})
                chat_obj = msg_data.get("chat", {})
                chat_id = str(chat_obj.get("id", ""))
                text = msg_data.get("text", "").strip()

                if not text:
                    continue

                # "turma" join system
                if text.lower().strip() == 'turma':
                    _approve_user(chat_id, msg_data.get("from", {}).get("first_name", "Unknown"))
                    send_telegram_brazil("\u2705 <b>Bem-vindo ao M3xA_Brazil!</b>\nVoce esta aprovado. Pergunte sobre Brasil, eleicoes, economia.\n\n\U0001f30d Para macro global, use @M3xabot", chat_id=chat_id)
                    continue

                if not _is_approved(chat_id):
                    user_name = msg_data.get("from", {}).get("first_name", "Unknown")
                    print(f"[TG-BR] Unauthorized: {user_name} (chat_id={chat_id}) msg: {text[:200]}", flush=True)
                    send_telegram_brazil("\U0001f44b Ola! Nao reconheco este chat.\n\n""Por favor, apresente-se para o operador revisar o acesso:\n""• Seu nome\n""• Como conhece o operador\n""• Para que quer usar este bot", chat_id=chat_id)
                    continue

                # #issue complaint system
                if text.lower().startswith('#issue'):
                    complaint = text[6:].strip() or "(no details provided)"
                    user_name = msg_data.get("from", {}).get("first_name", "Unknown")
                    _log_issue("m3xa_brazil", chat_id, user_name, complaint)
                    send_telegram_brazil(
                        "\U0001f4dd <b>Feedback registrado.</b>\n"
                        f"Issue: <i>{complaint[:200]}</i>\n\n"
                        "Pedro vai revisar junto com sua ultima pergunta. Obrigado!",
                        chat_id=chat_id)
                    continue

                # #code investigation (admin only — Phase 1: read-only)
                if text.lower().startswith('#code'):
                    if str(chat_id) != str(TELEGRAM_CHAT_ID):
                        send_telegram_brazil("\U0001f512 <b>#code somente admin.</b>", chat_id=chat_id)
                        continue
                    code_request = text[5:].strip() or "(no details)"
                    user_name = msg_data.get("from", {}).get("first_name", "Unknown")
                    send_telegram_brazil(
                        "\U0001f527 <b>M3xA Code Agent \u2014 Investigacao iniciada</b>\n"
                        f"Request: <i>{code_request[:200]}</i>\n\n"
                        "\u23f3 Agent lendo codigo & logs... ~30-60s",
                        chat_id=chat_id)
                    import threading
                    threading.Thread(
                        target=_run_code_investigation,
                        args=(code_request, chat_id, user_name, "m3xa_brazil", send_telegram_brazil),
                        daemon=True).start()
                    continue

                # #brazilbrief{N} — generate Brazil Brief over last N hours
                import re as _re_cmd
                brief_match = _re_cmd.match(r'^#brazilbrief(\d+)$', text.lower().strip())
                if brief_match:
                    hours = int(brief_match.group(1))
                    if hours < 1 or hours > 72:
                        send_telegram_brazil("\u274c Horas deve ser entre 1 e 72. Ex: <b>#brazilbrief18</b>", chat_id=chat_id)
                        continue
                    user_name = msg_data.get("from", {}).get("first_name", "User")
                    print(f"[TG-BR] Brazil Brief ({hours}h) requested by {user_name}", flush=True)
                    send_telegram_brazil(
                        f"\U0001f4cb <b>Gerando Brazil Brief ({hours}h)...</b>\n"
                        f"\u23f3 Aguarde ~2-3 minutos.",
                        chat_id=chat_id)
                    import threading
                    threading.Thread(
                        target=_run_brazil_brief_telegram,
                        args=(hours, chat_id, user_name),
                        daemon=True).start()
                    continue

                # #chart command — generate chart image directly
                if text.lower().startswith('#chart'):
                    try:
                        import sys
                        sys.path.insert(0, '/home/ubuntu/argus/newspaper_project')
                        from chart_generator import parse_chart_command, generate_chart
                        chart_spec, hint = parse_chart_command(text)
                        if chart_spec:
                            send_telegram_brazil("\U0001f4c8 <b>Gerando grafico...</b>", chat_id=chat_id)
                            buf, caption = generate_chart(chart_spec)
                            if buf:
                                send_telegram_brazil_photo(buf, chat_id=chat_id, caption=caption)
                                print(f"[TG-BR] Chart sent: {chart_spec}", flush=True)
                            else:
                                send_telegram_brazil(f"\u274c Erro no grafico: {caption}", chat_id=chat_id)
                        else:
                            send_telegram_brazil(
                                "\U0001f4c8 <b>#chart uso:</b>\n"
                                "\u2022 <code>#chart USDBRL 1M</code> — candlestick\n"
                                "\u2022 <code>#chart IBOVESPA vs SP500 3mo</code> — comparacao\n"
                                "\u2022 <code>#chart fx</code> — FX snapshot\n"
                                "\u2022 <code>#chart indices</code> — indices",
                                chat_id=chat_id)
                    except Exception as e:
                        send_telegram_brazil(f"\u274c Erro no grafico: {str(e)[:200]}", chat_id=chat_id)
                        print(f"[TG-BR] Chart error: {e}", flush=True)
                    continue

                # #mail command — email last Q&A to pedro.ribeiro@jpmorgan.com
                if text.lower().strip() in ('#mail', '@mail'):
                    try:
                        last = _get_last_conversation("m3xa_brazil", chat_id)
                        if not last or not last.get('response'):
                            send_telegram_brazil("\u274c Nenhuma conversa anterior para enviar. Faca uma pergunta primeiro!", chat_id=chat_id)
                            continue
                        send_telegram_brazil("\U0001f4e7 <b>Enviando para inbox JPM...</b>", chat_id=chat_id)
                        import requests as _mail_req
                        r = _mail_req.post("http://127.0.0.1:8550/api/send_email", json={
                            "query": last['query'][:200],
                            "response": last['response']
                        }, timeout=30)
                        if r.status_code == 200 and r.json().get('status') == 'sent':
                            send_telegram_brazil("\u2705 <b>Email enviado!</b>\n\U0001f4e8 Para: pedro.ribeiro@jpmorgan.com\n\U0001f4e4 De: pr@codex-net.com", chat_id=chat_id)
                            print(f"[TG-BR] #mail sent for query: {last['query'][:80]}", flush=True)
                        else:
                            send_telegram_brazil(f"\u274c Erro no email: {r.text[:200]}", chat_id=chat_id)
                    except Exception as e:
                        send_telegram_brazil(f"\u274c Erro no email: {str(e)[:200]}", chat_id=chat_id)
                        print(f"[TG-BR] #mail error: {e}", flush=True)
                    continue

                # #forwardlodo — admin forwards a message to Lodo
                if text.lower().startswith('#forwardlodo'):
                    if str(chat_id) != str(TELEGRAM_CHAT_ID):
                        send_telegram_brazil("\U0001f512 <b>#forwardlodo somente admin.</b>", chat_id=chat_id)
                        continue
                    fwd_msg = text[12:].strip()
                    if not fwd_msg:
                        send_telegram_brazil("\u274c Uso: <code>#forwardlodo sua mensagem aqui</code>", chat_id=chat_id)
                        continue
                    send_telegram_brazil(
                        f"\U0001f4e8 <b>Mensagem do Pedro:</b>\n\n{fwd_msg}\n\n"
                        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
                        f"<i>Responda com</i> <code>#response sua resposta</code>",
                        chat_id=LODO_CHAT_ID)
                    send_telegram_brazil("\u2705 <b>Mensagem enviada para Lodo.</b>", chat_id=chat_id)
                    print(f"[TG-BR] #forwardlodo sent: {fwd_msg[:100]}", flush=True)
                    continue

                # #response — Lodo replies back to admin
                if text.lower().startswith('#response'):
                    if str(chat_id) != str(LODO_CHAT_ID):
                        send_telegram_brazil("\U0001f512 <b>#response somente para Lodo.</b>", chat_id=chat_id)
                        continue
                    reply_msg = text[9:].strip()
                    if not reply_msg:
                        send_telegram_brazil("\u274c Uso: <code>#response sua resposta aqui</code>", chat_id=chat_id)
                        continue
                    send_telegram_brazil(
                        f"\U0001f4ec <b>Resposta do Lodo:</b>\n\n{reply_msg}",
                        chat_id=TELEGRAM_CHAT_ID)
                    send_telegram_brazil("\u2705 <b>Resposta enviada para Pedro.</b>", chat_id=chat_id)
                    print(f"[TG-BR] #response from Lodo: {reply_msg[:100]}", flush=True)
                    continue

                if text.startswith("/"):
                    help_msg = (
                        "\U0001f1e7\U0001f1f7 <b>M3xA_Brazil</b>\n"
                        "Agent focado em Brasil \u2014 eleicoes, politica, economia.\n\n"
                        "Exemplos:\n"
                        "\u2022 <i>Quais as chances do Lula?</i>\n"
                        "\u2022 <i>Brazil election polls</i>\n"
                        "\u2022 <i>Selic outlook</i>\n"
                        "\u2022 <i>What is happening in Brazil?</i>\n"
                        "\u2022 <b>#brazilbrief18</b> — Brief ultimas 18h\n"
                        "\u2022 <b>#brazilbrief6</b> — Brief ultimas 6h"
                    )
                    send_telegram_brazil(help_msg, chat_id=chat_id)
                    continue

                user_name = msg_data.get("from", {}).get("first_name", "User")
                print(f"[TG-BR] Query from {user_name}: {text[:100]}", flush=True)

                ack = f"\U0001f1e7\U0001f1f7 <b>M3xA_Brazil querying...</b>\n<i>{text[:200]}</i>\n\u23f3 ~2-3 min"
                send_telegram_brazil(ack, chat_id=chat_id)

                # Hydrate session from DB if empty (e.g. after restart)
                _hydrate_session_from_db(f"telegram_br_{chat_id}", "m3xa_brazil", chat_id)

                try:
                    rag_resp = _rq.post(RAG_URL, json={
                        "query": text,
                        "filters": ["brazil"],
                        "session_id": f"telegram_br_{chat_id}"
                    }, timeout=300)

                    if rag_resp.status_code == 200:
                        result = rag_resp.json()
                        answer = result.get("response", "No response generated.")
                        elapsed = result.get("elapsed_seconds", "?")
                        sources = result.get("sources", {})

                        # Parse and strip chart tags before formatting
                        import re as _re_chart
                        _chart_tags = _re_chart.findall(r'<!--CHART:(.+?)-->', answer)
                        answer = _re_chart.sub(r'<!--CHART:.+?-->', '', answer).rstrip()

                        tg_answer = format_for_telegram(answer)
                        conv_id = result.get("conversation_id", "")
                        src_brazil = sources.get("brazil", 0)
                        src_tweets = sources.get("tweets", 0)
                        time_ctx = result.get("time_context", {})
                        time_window = time_ctx.get("temporal_filter", "")
                        data_fresh = time_ctx.get("data_freshness", "")
                        rows_in = time_ctx.get("rows_in_time_window", "?")
                        inst_name = sources.get("institution_name", "")
                        inst_n = sources.get("institution_boost", 0)
                        conv_label = f"#{conv_id} | " if conv_id else ""
                        # Header with conversation number (shows on first chunk)
                        header = f"<b>{conv_label}M3xA_Brazil</b>\n\n" if conv_id else ""
                        footer = (
                            f"\n\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
                            f"\U0001f1e7\U0001f1f7 M3xA_Brazil | {conv_label}\u23f1 {elapsed}s | "
                            f"\U0001f4ca {src_brazil} artigos, {src_tweets} tweets"
                        )
                        if time_window:
                            footer += f"\n\U0001f4c5 {time_window} ({rows_in} itens) | {data_fresh}"
                        if inst_name:
                            footer += f"\n\U0001f3e6 {inst_name}: +{inst_n} via busca institucional"
                        send_telegram_brazil(header + tg_answer + footer, chat_id=chat_id)
                        print(f"[TG-BR] Reply sent ({elapsed}s, {len(tg_answer)} chars)", flush=True)
                        _log_conversation("m3xa_brazil", chat_id, user_name, text, answer, elapsed, sources)

                        # Generate and send chart if RAG suggested one
                        if _chart_tags:
                            try:
                                import sys
                                sys.path.insert(0, '/home/ubuntu/argus/newspaper_project')
                                from chart_generator import generate_chart
                                for _ct in _chart_tags[:1]:
                                    _buf, _cap = generate_chart(_ct)
                                    if _buf:
                                        send_telegram_brazil_photo(_buf, chat_id=chat_id, caption=_cap)
                                        print(f"[TG-BR] Auto-chart sent: {_ct}", flush=True)
                            except Exception as _ce:
                                print(f"[TG-BR] Auto-chart error: {_ce}", flush=True)
                    else:
                        send_telegram_brazil(f"\u274c RAG error: HTTP {rag_resp.status_code}", chat_id=chat_id)

                except _rq.exceptions.Timeout:
                    send_telegram_brazil("\u23f0 Query timed out (>300s).", chat_id=chat_id)
                except Exception as e:
                    send_telegram_brazil(f"\u274c Error: {str(e)[:200]}", chat_id=chat_id)
                    print(f"[TG-BR] Error: {e}", flush=True)

        except _rq.exceptions.ReadTimeout:
            pass
        except Exception as e:
            print(f"[TG-BR] Poll error: {e}", flush=True)
            _t.sleep(5)


def start_telegram_brazil_polling():
    """Start M3xA_Brazil polling thread."""
    import threading
    t = threading.Thread(target=_telegram_brazil_poll_loop, daemon=True, name="TelegramBrazilPoll")
    t.start()
    print("[TG-BR] M3xA_Brazil polling thread launched", flush=True)


_tg_last_update_id = 0

def _telegram_poll_loop():
    """Background thread: poll Telegram for new messages, forward to /api/rag, reply."""
    import requests as _rq
    import time as _t
    global _tg_last_update_id

    API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    RAG_URL = "http://127.0.0.1:8550/api/rag"
    ALLOWED_CHAT = str(TELEGRAM_CHAT_ID)

    print("[TG-POLL] Interactive Telegram polling started", flush=True)

    _wait_for_telegram_dns("TG-POLL")

    # Skip old messages on startup
    try:
        r = _rq.get(f"{API}/getUpdates", params={"limit": 1, "offset": -1}, timeout=10)
        updates = r.json().get("result", [])
        if updates:
            _tg_last_update_id = updates[-1]["update_id"] + 1
            print(f"[TG-POLL] Skipping old messages, starting from update_id {_tg_last_update_id}", flush=True)
    except Exception as e:
        print(f"[TG-POLL] Init error: {e}", flush=True)

    while True:
        try:
            r = _rq.get(
                f"{API}/getUpdates",
                params={"offset": _tg_last_update_id, "timeout": 30, "allowed_updates": '["message"]'},
                timeout=40
            )
            updates = r.json().get("result", [])

            for upd in updates:
                _tg_last_update_id = upd["update_id"] + 1
                msg_data = upd.get("message", {})
                chat_obj = msg_data.get("chat", {})
                chat_id = str(chat_obj.get("id", ""))
                text = msg_data.get("text", "").strip()

                if not text:
                    continue

                # "turma" join system
                if text.lower().strip() == 'turma':
                    _approve_user(chat_id, msg_data.get("from", {}).get("first_name", "Unknown"))
                    send_telegram_message("\u2705 <b>Welcome to M3xA!</b>\nYou are now approved. Ask any macro/markets question.\n\n\U0001f1e7\U0001f1f7 Para Brasil, use @M3xabr_bot", chat_id=chat_id)
                    continue

                if not _is_approved(chat_id):
                    user_name = msg_data.get("from", {}).get("first_name", "Unknown")
                    print(f"[TG-POLL] Unauthorized: {user_name} (chat_id={chat_id}) msg: {text[:200]}", flush=True)
                    send_telegram_message("\U0001f44b Hi! I don't recognise this chat.\n\n""Please introduce yourself so the operator can review access:\n""• Your name\n""• How you know the operator\n""• What you want to use this bot for", chat_id=chat_id)
                    continue

                # #issue complaint system
                if text.lower().startswith('#issue'):
                    complaint = text[6:].strip() or "(no details provided)"
                    user_name = msg_data.get("from", {}).get("first_name", "Unknown")
                    _log_issue("m3xa", chat_id, user_name, complaint)
                    send_telegram_message(
                        "\U0001f4dd <b>Feedback recorded.</b>\n"
                        f"Issue: <i>{complaint[:200]}</i>\n\n"
                        "Pedro will review this along with your last Q&A for context. Thank you!",
                        chat_id=chat_id)
                    continue

                # #code investigation (admin only — Phase 1: read-only)
                if text.lower().startswith('#code'):
                    if str(chat_id) != str(TELEGRAM_CHAT_ID):
                        send_telegram_message("\U0001f512 <b>#code is admin-only.</b>", chat_id=chat_id)
                        continue
                    code_request = text[5:].strip() or "(no details)"
                    user_name = msg_data.get("from", {}).get("first_name", "Unknown")
                    send_telegram_message(
                        "\U0001f527 <b>M3xA Code Agent \u2014 Investigation started</b>\n"
                        f"Request: <i>{code_request[:200]}</i>\n\n"
                        "\u23f3 Agent reading code & logs... ~30-60s",
                        chat_id=chat_id)
                    import threading
                    threading.Thread(
                        target=_run_code_investigation,
                        args=(code_request, chat_id, user_name, "m3xa", send_telegram_message),
                        daemon=True).start()
                    continue

                # #chart command — generate chart image directly
                if text.lower().startswith('#chart'):
                    try:
                        import sys
                        sys.path.insert(0, '/home/ubuntu/argus/newspaper_project')
                        from chart_generator import parse_chart_command, generate_chart
                        chart_spec, hint = parse_chart_command(text)
                        if chart_spec:
                            send_telegram_message("\U0001f4c8 <b>Generating chart...</b>", chat_id=chat_id)
                            buf, caption = generate_chart(chart_spec)
                            if buf:
                                send_telegram_photo(buf, chat_id=chat_id, caption=caption)
                                print(f"[TG-POLL] Chart sent: {chart_spec}", flush=True)
                            else:
                                send_telegram_message(f"\u274c Chart failed: {caption}", chat_id=chat_id)
                        else:
                            send_telegram_message(
                                "\U0001f4c8 <b>#chart usage:</b>\n"
                                "\u2022 <code>#chart EURUSD 1M</code> — candlestick\n"
                                "\u2022 <code>#chart SP500 vs NASDAQ 1M</code> — comparison\n"
                                "\u2022 <code>#chart fx</code> — FX snapshot\n"
                                "\u2022 <code>#chart rates</code> — rates\n"
                                "\u2022 <code>#chart commodities</code> — commodities",
                                chat_id=chat_id)
                    except Exception as e:
                        send_telegram_message(f"\u274c Chart error: {str(e)[:200]}", chat_id=chat_id)
                        print(f"[TG-POLL] Chart error: {e}", flush=True)
                    continue

                # #mail command — email last Q&A to pedro.ribeiro@jpmorgan.com
                if text.lower().strip() in ('#mail', '@mail'):
                    try:
                        last = _get_last_conversation("m3xa", chat_id)
                        if not last or not last.get('response'):
                            send_telegram_message("\u274c No previous conversation to email. Ask a question first!", chat_id=chat_id)
                            continue
                        send_telegram_message("\U0001f4e7 <b>Sending to JPM inbox...</b>", chat_id=chat_id)
                        import requests as _mail_req
                        r = _mail_req.post("http://127.0.0.1:8550/api/send_email", json={
                            "query": last['query'][:200],
                            "response": last['response']
                        }, timeout=30)
                        if r.status_code == 200 and r.json().get('status') == 'sent':
                            send_telegram_message("\u2705 <b>Email sent!</b>\n\U0001f4e8 To: pedro.ribeiro@jpmorgan.com\n\U0001f4e4 From: pr@codex-net.com", chat_id=chat_id)
                            print(f"[TG-POLL] #mail sent for query: {last['query'][:80]}", flush=True)
                        else:
                            send_telegram_message(f"\u274c Email failed: {r.text[:200]}", chat_id=chat_id)
                    except Exception as e:
                        send_telegram_message(f"\u274c Email error: {str(e)[:200]}", chat_id=chat_id)
                        print(f"[TG-POLL] #mail error: {e}", flush=True)
                    continue

                # #forwardlodo — admin forwards a message to Lodo
                if text.lower().startswith('#forwardlodo'):
                    if str(chat_id) != str(TELEGRAM_CHAT_ID):
                        send_telegram_message("\U0001f512 <b>#forwardlodo is admin-only.</b>", chat_id=chat_id)
                        continue
                    fwd_msg = text[12:].strip()
                    if not fwd_msg:
                        send_telegram_message("\u274c Usage: <code>#forwardlodo your message here</code>", chat_id=chat_id)
                        continue
                    send_telegram_message(
                        f"\U0001f4e8 <b>Message from Pedro:</b>\n\n{fwd_msg}\n\n"
                        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
                        f"<i>Reply with</i> <code>#response your reply</code>",
                        chat_id=LODO_CHAT_ID)
                    send_telegram_message("\u2705 <b>Message forwarded to Lodo.</b>", chat_id=chat_id)
                    print(f"[TG-POLL] #forwardlodo sent: {fwd_msg[:100]}", flush=True)
                    continue

                # #response — Lodo replies back to admin
                if text.lower().startswith('#response'):
                    if str(chat_id) != str(LODO_CHAT_ID):
                        send_telegram_message("\U0001f512 <b>#response is for Lodo only.</b>", chat_id=chat_id)
                        continue
                    reply_msg = text[9:].strip()
                    if not reply_msg:
                        send_telegram_message("\u274c Usage: <code>#response your reply here</code>", chat_id=chat_id)
                        continue
                    send_telegram_message(
                        f"\U0001f4ec <b>Reply from Lodo:</b>\n\n{reply_msg}",
                        chat_id=TELEGRAM_CHAT_ID)
                    send_telegram_message("\u2705 <b>Reply sent to Pedro.</b>", chat_id=chat_id)
                    print(f"[TG-POLL] #response from Lodo: {reply_msg[:100]}", flush=True)
                    continue

                # Bot commands
                if text.startswith("/"):
                    help_msg = (
                        "\U0001f9e0 <b>M3xA Interactive</b>\n"
                        "Just type your question \u2014 I query the full RAG database and reply.\n\n"
                        "Examples:\n"
                        "\u2022 <i>What is happening with Iran?</i>\n"
                        "\u2022 <i>Brazil election latest polls</i>\n"
                        "\u2022 <i>Fed rate outlook</i>\n"
                        "\u2022 <i>Oil and geopolitics</i>"
                    )
                    send_telegram_message(help_msg, chat_id=chat_id)
                    continue

                # #continue — deliver more from last response (or continue if max_tokens hit)
                if text.lower().strip() in ("#continue", "continue", "#more", "more"):
                    _sess_id = f"telegram_{chat_id}"
                    _pending = _pending_continuation.get(_sess_id)
                    if not _pending:
                        send_telegram_message(
                            "ℹ️ No previous response to continue. Ask a question first!",
                            chat_id=chat_id)
                    else:
                        send_telegram_message(
                            "🔄 <b>Continuing previous response...</b>",
                            chat_id=chat_id)
                        try:
                            r = _rq.post(RAG_URL, json={
                                "query": "Please continue your previous response from exactly where you left off, without repeating what you already said.",
                                "filters": ["macro", "brazil", "codex"],
                                "session_id": _sess_id,
                            }, timeout=300)
                            if r.status_code == 200:
                                cont_answer = r.json().get("response", "")
                                send_telegram_message(cont_answer, chat_id=chat_id)
                                _pending_continuation.pop(_sess_id, None)
                            else:
                                send_telegram_message(f"❌ Continue failed: HTTP {r.status_code}", chat_id=chat_id)
                        except Exception as _ce:
                            send_telegram_message(f"❌ Continue error: {str(_ce)[:200]}", chat_id=chat_id)
                    continue

                user_name = msg_data.get("from", {}).get("first_name", "User")
                print(f"[TG-POLL] Query from {user_name}: {text[:100]}", flush=True)

                # Send ack and capture message_id for live streaming edits
                ack = f"\U0001f50d <b>Querying M3xA...</b>\n<i>{text[:200]}</i>\n\u23f3 Processing..."
                _ack_msg_id, _ = _tg_send_and_get_id(ack, chat_id)

                # Hydrate session from DB if empty (e.g. after restart)
                _hydrate_session_from_db(f"telegram_{chat_id}", "m3xa", chat_id)

                # Register streaming queue BEFORE starting the RAG call
                _sess_id = f"telegram_{chat_id}"
                _stream_q = _tg_stream_register(_sess_id)

                # Start RAG call in background thread
                import threading as _thr
                _rag_result = [None]
                def _do_rag():
                    try:
                        r = _rq.post(RAG_URL, json={
                            "query": text,
                            "filters": ["macro", "brazil", "codex"],
                            "session_id": _sess_id,
                        }, timeout=300)
                        _rag_result[0] = r
                    except Exception as _e:
                        _rag_result[0] = _e
                _rag_thread = _thr.Thread(target=_do_rag, daemon=True)
                _rag_thread.start()

                # Stream tokens to Telegram while RAG runs
                _partial = ""
                _last_edit = _t.time()
                _start_stream = _t.time()
                _EDIT_INTERVAL = 0.8  # edit at most every 0.8s
                _streaming_started = False
                while True:
                    try:
                        token = _stream_q.get(timeout=2.0)
                        if token is None:  # stream done signal
                            break
                        _partial += token
                        now = _t.time()
                        if now - _last_edit >= _EDIT_INTERVAL and len(_partial) > 50:
                            # Show live partial — strip HTML for safety during streaming
                            import re as _prev_re
                            preview_clean = _prev_re.sub(r'<[^>]+>', '', _partial[:3500])
                            preview = preview_clean + ("..." if len(_partial) > 3500 else "")
                            elapsed_so_far = int(now - _start_stream)
                            _tg_edit(_ack_msg_id, f"\u26a1 <b>M3xA</b> ({elapsed_so_far}s)\n\n{preview}", chat_id)
                            _last_edit = now
                            _streaming_started = True
                    except _queue_mod.Empty:
                        if not _rag_thread.is_alive():
                            break
                        # Show heartbeat so user knows it's alive
                        elapsed_so_far = int(_t.time() - _start_stream)
                        if elapsed_so_far % 10 == 0 and elapsed_so_far > 0:
                            _tg_edit(_ack_msg_id, f"\U0001f50d <b>Querying M3xA...</b>\n<i>{text[:150]}</i>\n\u23f3 {elapsed_so_far}s...", chat_id)

                _tg_stream_unregister(_sess_id)
                # Anthropic stream ends before Flask finishes self-eval + JSON.
                # Wait up to 90s for the HTTP response after stream signals done.
                _wait_deadline = _t.time() + 600  # 600s: 300s stream + up to 3 auto-continuations + self-eval
                while _rag_result[0] is None and _t.time() < _wait_deadline:
                    _t.sleep(0.3)
                _rag_thread.join(timeout=3)

                # Now process the full response
                try:
                    rag_resp = _rag_result[0]
                    if isinstance(rag_resp, Exception):
                        raise rag_resp
                    if rag_resp is None:
                        raise Exception("RAG timed out after stream — self-eval exceeded 90s. Try again.")

                    if rag_resp.status_code == 200:
                        result = rag_resp.json()
                        answer = result.get("response", "No response generated.")
                        elapsed = result.get("elapsed_seconds", "?")
                        sources = result.get("sources", {})

                        # Parse and strip chart tags before formatting
                        import re as _re_chart
                        _chart_tags = _re_chart.findall(r'<!--CHART:(.+?)-->', answer)
                        answer = _re_chart.sub(r'<!--CHART:.+?-->', '', answer).rstrip()

                        tg_answer = format_for_telegram(answer)
                        conv_id = result.get("conversation_id", "")
                        src_tweets = sources.get("tweets", 0)
                        src_macro = sources.get("macro", 0)
                        src_brazil = sources.get("brazil", 0)
                        conv_label = f"#{conv_id} | " if conv_id else ""
                        header = f"<b>{conv_label}M3xA</b>\n\n" if conv_id else ""
                        footer = (
                            f"\n\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
                            f"{conv_label}\u23f1 {elapsed}s | "
                            f"\U0001f4ca {src_tweets} tweets, "
                            f"{src_macro} macro, "
                            f"{src_brazil} brazil"
                        )
                        full_answer = header + tg_answer + footer
                        # Edit the ack message with final formatted answer, or send new if too long
                        if len(full_answer) <= 4000:
                            _tg_edit(_ack_msg_id, full_answer, chat_id)
                        else:
                            # Final answer is long — delete placeholder, send as properly split multi-part
                            try:
                                import requests as _del_req
                                _del_req.post(
                                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteMessage",
                                    json={"chat_id": chat_id, "message_id": _ack_msg_id},
                                    timeout=5
                                )
                            except Exception:
                                pass
                            send_telegram_message(full_answer, chat_id=chat_id)
                        print(f"[TG-POLL] Reply sent ({elapsed}s, {len(tg_answer)} chars)", flush=True)
                        _log_conversation("m3xa", chat_id, user_name, text, answer, elapsed, sources)

                        # Generate and send chart if RAG suggested one
                        if _chart_tags:
                            try:
                                import sys
                                sys.path.insert(0, '/home/ubuntu/argus/newspaper_project')
                                from chart_generator import generate_chart
                                for _ct in _chart_tags[:1]:
                                    _buf, _cap = generate_chart(_ct)
                                    if _buf:
                                        send_telegram_photo(_buf, chat_id=chat_id, caption=_cap)
                                        print(f"[TG-POLL] Auto-chart sent: {_ct}", flush=True)
                            except Exception as _ce:
                                print(f"[TG-POLL] Auto-chart error: {_ce}", flush=True)
                    else:
                        send_telegram_message(f"\u274c RAG error: HTTP {rag_resp.status_code}", chat_id=chat_id)
                        print(f"[TG-POLL] RAG HTTP error: {rag_resp.status_code}", flush=True)

                except _rq.exceptions.Timeout:
                    send_telegram_message("\u23f0 Query timed out (>300s). Try a more specific question.", chat_id=chat_id)
                    print("[TG-POLL] RAG timeout", flush=True)
                except Exception as e:
                    send_telegram_message(f"\u274c Error: {str(e)[:200]}", chat_id=chat_id)
                    print(f"[TG-POLL] RAG call error: {e}", flush=True)

        except _rq.exceptions.ReadTimeout:
            pass  # Normal for long polling
        except Exception as e:
            print(f"[TG-POLL] Poll error: {e}", flush=True)
            _t.sleep(5)


def start_telegram_polling():
    """Start the Telegram polling thread (called once at startup)."""
    import threading
    t = threading.Thread(target=_telegram_poll_loop, daemon=True, name="TelegramPoll")
    t.start()
    print("[TG-POLL] Background polling thread launched", flush=True)



# ═══════════════════════════════════════════════════════════════════════════════
# WEB CHAT INTERFACE — Telegram-replica for M3xA and M3xA Brazil
# ═══════════════════════════════════════════════════════════════════════════════
@app.route('/chat')
def chat_interface():
    import os
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'm3xa_chat.html')
    with open(html_path, 'r') as f:
        return f.read()


if __name__ == '__main__':
    start_telegram_polling()
    start_telegram_brazil_polling()
    app.run(host='0.0.0.0', port=8550, debug=False, threaded=True)

