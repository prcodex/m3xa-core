#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent Central Hub — Context Orchestration Layer for M3xA RAG

Single entry point that detects query topics, fetches context from relevant
agents in parallel, manages context budget, and returns a unified block
ready for system prompt injection.

Agents:
  - markets:     Live FX, rates, indices, commodities (always-on, compact)
  - polymarket:  Prediction market probabilities + trend evolution
  - calendar:    Economic calendar events
  - polls:       Brazil election polls
  - boost:       Priority source deep-context (prompt boost)
"""

import os
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------------------------------------------------------------------------
# Agent registry — each agent has a fetch function and topic triggers
# ---------------------------------------------------------------------------

_AGENTS = {}
_AVAILABLE = {}


def _safe_import():
    """Import all available agent modules. Called once at startup."""
    global _AVAILABLE

    # Markets Agent (8564 dashboard)
    try:
        from markets_agent import get_live_market_context as _ma_fetch
        _AGENTS['markets'] = {
            'fetch': lambda query, budget, **kw: _ma_fetch() or "",
            'always': True,
            'priority': 10,
            'default_budget': 2000,
            'label': 'Markets',
        }
        _AVAILABLE['markets'] = True
        print("[AgentHub] Markets agent registered")
    except ImportError as e:
        _AVAILABLE['markets'] = False
        print(f"[AgentHub] Markets agent not available: {e}")

    # Polymarket Agent (8565 dashboard via HTTP)
    try:
        import sys
        sys.path.insert(0, '/home/ubuntu/argus/scripts')
        from polymarket_agent import (
            detect_topics as pm_detect,
            get_context_for_query as pm_get_ctx,
            TOPICS as PM_TOPICS,
        )
        _AGENTS['polymarket'] = {
            'fetch': lambda query, budget, **kw: _pm_fetch_wrapper(query, pm_get_ctx),
            'detect': lambda query: bool(pm_detect(query)),
            'priority': 9,
            'default_budget': 4000,
            'label': 'Polymarket',
            '_detect_fn': pm_detect,
            '_topics': PM_TOPICS,
        }
        _AVAILABLE['polymarket'] = True
        print("[AgentHub] Polymarket agent registered")
    except ImportError as e:
        _AVAILABLE['polymarket'] = False
        print(f"[AgentHub] Polymarket agent not available: {e}")

    # Calendar Agent
    try:
        from economic_calendar_context import (
            should_include_calendar as cal_should,
            get_economic_context as cal_fetch,
        )
        _AGENTS['calendar'] = {
            'fetch': lambda query, budget, **kw: cal_fetch() or "",
            'detect': cal_should,
            'priority': 7,
            'default_budget': 6000,
            'label': 'Calendar',
        }
        _AVAILABLE['calendar'] = True
        print("[AgentHub] Calendar agent registered")
    except ImportError as e:
        _AVAILABLE['calendar'] = False
        print(f"[AgentHub] Calendar agent not available: {e}")

    # Polls Agent
    try:
        from poll_context import (
            should_include_polls as poll_should,
            get_poll_context as poll_fetch,
        )
        _AGENTS['polls'] = {
            'fetch': lambda query, budget, **kw: poll_fetch() or "",
            'detect': poll_should,
            'priority': 8,
            'default_budget': 2500,
            'label': 'Polls',
        }
        _AVAILABLE['polls'] = True
        print("[AgentHub] Polls agent registered")
    except ImportError as e:
        _AVAILABLE['polls'] = False
        print(f"[AgentHub] Polls agent not available: {e}")

    # Prompt Boost Agent
    try:
        from prompt_boost import build_boost_prompt as boost_build
        _AGENTS['boost'] = {
            'fetch': lambda query, budget, **kw: _boost_wrapper(
                query, boost_build, kw.get('time_hours'), kw.get('boost_enabled', True)),
            'detect': lambda query: True,
            'priority': 5,
            'default_budget': 8000,
            'label': 'Boost',
            '_build_fn': boost_build,
        }
        _AVAILABLE['boost'] = True
        print("[AgentHub] Boost agent registered")
    except ImportError as e:
        _AVAILABLE['boost'] = False
        print(f"[AgentHub] Boost agent not available: {e}")


def _pm_fetch_wrapper(query, pm_get_ctx):
    """Wrapper for Polymarket that returns just the context string."""
    try:
        ctx, topics = pm_get_ctx(query)
        return ctx or ""
    except Exception as e:
        print(f"[AgentHub] Polymarket fetch error: {e}")
        return ""


def _boost_wrapper(query, boost_build, time_hours, boost_enabled):
    """Wrapper for Prompt Boost that handles the (content, instruction) tuple."""
    if not boost_enabled:
        return ""
    try:
        days = max(1, int(time_hours / 24)) if time_hours and time_hours > 0 else 7
        content, instruction = boost_build(
            '/home/ubuntu/m3xa/lancedb_clean', query, days=days)
        if content:
            return content
    except Exception as e:
        print(f"[AgentHub] Boost error: {e}")
    return ""


# ---------------------------------------------------------------------------
# Mode presets — which agents to activate and budget allocation
# ---------------------------------------------------------------------------

MODES = {
    'general': {
        'agents': ['markets', 'polymarket', 'calendar', 'polls', 'boost'],
        'total_budget': 25000,
    },
    'macro_telegram': {
        'agents': ['markets', 'polymarket', 'calendar', 'boost'],
        'total_budget': 20000,
        'force_agents': ['markets', 'polymarket', 'calendar'],
    },
    'brazil_brief': {
        'agents': ['markets', 'polymarket', 'polls', 'boost'],
        'total_budget': 20000,
        'force_agents': ['markets', 'polymarket', 'polls'],
    },
}


# ---------------------------------------------------------------------------
# Core orchestration
# ---------------------------------------------------------------------------

def get_context(query, mode='general', budget=None, time_hours=None,
                boost_enabled=True, filters=None):
    """
    Main entry point. Detects relevant agents, fetches in parallel,
    manages budget, returns a single formatted context block.

    Args:
        query:         The user query or synthetic trigger query
        mode:          One of 'general', 'macro_telegram', 'brazil_brief'
        budget:        Override total char budget (default from mode)
        time_hours:    Time window for boost agent
        boost_enabled: Whether to include prompt boost
        filters:       RAG filters list (e.g. ['macro'])

    Returns:
        dict with keys:
            'context':  str  — formatted context block for system prompt
            'agents':   list — names of agents that contributed
            'chars':    int  — total chars
            'details':  dict — per-agent char counts
    """
    if not _AGENTS:
        _safe_import()

    mode_cfg = MODES.get(mode, MODES['general'])
    total_budget = budget or mode_cfg['total_budget']
    allowed_agents = mode_cfg['agents']
    force_agents = mode_cfg.get('force_agents', [])

    # For general mode, only include boost if macro filter is active
    if mode == 'general' and filters and 'macro' not in filters:
        boost_enabled = False

    # Determine which agents to activate
    active = []
    for agent_id in allowed_agents:
        if agent_id not in _AGENTS:
            continue
        agent = _AGENTS[agent_id]

        if agent_id in force_agents or agent.get('always'):
            active.append(agent_id)
        elif 'detect' in agent:
            try:
                if agent['detect'](query):
                    active.append(agent_id)
            except Exception:
                pass

    # For macro_telegram, force polymarket with a broad detection query
    if mode == 'macro_telegram' and 'polymarket' in _AGENTS and 'polymarket' not in active:
        active.append('polymarket')

    if not active:
        return {'context': '', 'agents': [], 'chars': 0, 'details': {}}

    _start = time.time()
    print(f"[AgentHub] Mode={mode}, Budget={total_budget}, Active={active}")

    # Fetch all agents in parallel
    results = {}
    with ThreadPoolExecutor(max_workers=len(active)) as pool:
        futures = {}
        for agent_id in active:
            agent = _AGENTS[agent_id]
            # For polymarket in macro_telegram, use broad query
            fetch_query = query
            if agent_id == 'polymarket' and mode == 'macro_telegram':
                fetch_query = "iran conflict brazil election fed macro russia ukraine"

            f = pool.submit(
                agent['fetch'],
                fetch_query,
                agent.get('default_budget', 5000),
                time_hours=time_hours,
                boost_enabled=boost_enabled,
            )
            futures[f] = agent_id

        for f in as_completed(futures):
            agent_id = futures[f]
            try:
                text = f.result()
                if text and len(text.strip()) > 10:
                    results[agent_id] = text
            except Exception as e:
                print(f"[AgentHub] {agent_id} failed: {e}")

    if not results:
        return {'context': '', 'agents': [], 'chars': 0, 'details': {}}

    # Budget allocation: priority-sorted, truncate to fit
    ordered = sorted(results.keys(),
                     key=lambda a: _AGENTS[a]['priority'], reverse=True)

    allocated = {}
    remaining = total_budget
    for agent_id in ordered:
        text = results[agent_id]
        default = _AGENTS[agent_id].get('default_budget', 5000)
        alloc = min(len(text), default, remaining)
        if alloc > 100:
            allocated[agent_id] = text[:alloc]
            remaining -= alloc
        if remaining <= 0:
            break

    # If there's remaining budget, distribute to agents that were truncated
    if remaining > 0:
        for agent_id in ordered:
            if agent_id in allocated and agent_id in results:
                full_text = results[agent_id]
                current = len(allocated[agent_id])
                if current < len(full_text):
                    extra = min(len(full_text) - current, remaining)
                    allocated[agent_id] = full_text[:current + extra]
                    remaining -= extra
                if remaining <= 0:
                    break

    # Format the unified output
    sections = []

    if 'markets' in allocated:
        sections.append(allocated['markets'])

    if 'polymarket' in allocated:
        sections.append(
            "╔══════════════════════════════════════════════════════════════╗\n"
            "║  POLYMARKET PREDICTION MARKETS — REAL MONEY BETS             ║\n"
            "║  Changes show the EVOLUTION of risk sentiment over time.     ║\n"
            "║  YOU MUST USE THIS DATA for Iran, Brazil, election, Fed.     ║\n"
            "╚══════════════════════════════════════════════════════════════╝\n"
            + allocated['polymarket']
        )

    if 'calendar' in allocated:
        sections.append(allocated['calendar'])

    if 'polls' in allocated:
        sections.append(allocated['polls'])

    if 'boost' in allocated:
        sections.append(
            "PRIORITY SOURCES (deep context):\n" + allocated['boost']
        )

    context_block = "\n\n".join(sections)
    details = {a: len(t) for a, t in allocated.items()}
    elapsed = round(time.time() - _start, 2)

    print(f"[AgentHub] Done in {elapsed}s: {details} = {len(context_block)} chars total")

    return {
        'context': context_block,
        'agents': list(allocated.keys()),
        'chars': len(context_block),
        'details': details,
    }


# ---------------------------------------------------------------------------
# Convenience: check availability
# ---------------------------------------------------------------------------

def is_available(agent_id):
    if not _AGENTS:
        _safe_import()
    return agent_id in _AGENTS


def list_agents():
    if not _AGENTS:
        _safe_import()
    return {
        aid: {
            'label': a['label'],
            'priority': a['priority'],
            'always': a.get('always', False),
        }
        for aid, a in _AGENTS.items()
    }
