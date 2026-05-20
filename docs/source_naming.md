# Source naming — the anonymization key

This repo is a **public, didactic** reference. The intelligence system it descends from runs against a real, curated source list (buy-side research, expert analysts, regional wires, podcasts, think tanks). Those names are **not** in this repo. They are replaced throughout with generic taxonomic aliases.

The goal: a reader learns the *pattern* (how source tiering works, why both-sides coverage matters, what makes an "expert" source different from a "wire") without learning the actual list, which would compromise the live system.

## The taxonomy

### Tier-1 sell-side / bulge-bracket banks

Large investment banks with global research desks. Used for: house views on rates, FX, equities, macro themes. Strong on consensus framing. Often slow to challenge that consensus.

| Alias | Region | Typical output |
|---|---|---|
| `Bank1` | NY-based | FX / rates / equities daily, global macro weekly |
| `Bank2` | EU-based | Rates strategy, equity strategy, geopolitical commentary |
| `Bank3` | Asia-based | Regional macro, EM specialist |
| `Bank4` | NY-based | Equities-heavy, China specialist desk |
| `Bank5` | EU-based, universal bank | Rates + commodities |

### Tier-2 regional / commercial banks

Mid-size commercial or regional banks with respected research desks. Often stronger than tier-1 on the regions they cover natively.

| Alias | Region | Specialty |
|---|---|---|
| `Bank6` | LatAm | Regional rates, local fiscal |
| `Bank7` | EM | EM sovereign credit |
| `Bank8` | EU regional | European peripherals, ECB watching |

### Independent macro / geopolitical analysts

Subscription Substacks, paid newsletters, or individual analysts publishing under their own name. Higher signal-per-word than bank research; less institutional ballast.

| Alias | Style | Typical lens |
|---|---|---|
| `Expert1` | Independent macro | Rates, central bank policy, deep monetary |
| `Expert2` | Independent geopolitical | Great-power competition, regional conflicts |
| `Expert3` | Fiscal-monetary historian | Long-arc framing, debt cycles |
| `Expert4` | Energy / commodities specialist | Oil, gas, transitions |
| `Expert5` | China-specialist macro | Beijing internal political economy |
| `Expert6` | Geopolitical analyst, region X | Iran, Gulf, Levant |
| `Expert7` | Geopolitical analyst, region Y | Russia, post-Soviet space |

### Boutique research shops

Small institutional research firms. Subscription-only, paid by buy-side. Often the source of "what the smart money is reading."

| Alias | Specialty |
|---|---|
| `Macro1` | Cross-asset macro |
| `Macro2` | Geopolitical risk |
| `Macro3` | Country-specific macro (region Z) |

### Wires

Real-time newswire services. The pipeline treats wires as *highest signal for breaking events, lowest for analysis*.

| Alias | Region |
|---|---|
| `Wire1` | English-language global wire |
| `Wire2` | Regional financial wire (region A) |
| `Wire3` | Regional financial wire (region B) |
| `Wire4` | English-language regional wire (Asia) |

### State-aligned media

Important for "what the other side is saying." Used in geopolitical synthesis where missing the adversary's framing produces a one-sided answer.

| Alias | Aligned with |
|---|---|
| `State1` | Region A government |
| `State2` | Region B government |
| `State3` | Region C government |

### Think tanks

| Alias | Geography | Lens |
|---|---|---|
| `ThinkTank1` | DC-based | Foreign policy, hawkish |
| `ThinkTank2` | DC-based | Foreign policy, restraint-leaning |
| `ThinkTank3` | EU-based | European strategic autonomy |

### Podcasts and YouTube channels

Long-form interview podcasts where the *guest* is what matters. The retrieval pipeline treats each episode as one document with the guest's identity as an entity tag.

| Alias | Format | Cadence |
|---|---|---|
| `Podcast1` | Long-form interview, geopolitics | Weekly |
| `Podcast2` | Long-form interview, macro | Weekly |
| `Podcast3` | News / interviews, region X | Daily |
| `Podcast4` | YouTube channel, macro commentary | Multiple per week |
| `Podcast5` | Audio-only Substack | Weekly |

### Institutions (subjects of coverage, not sources)

Used in the entity registry for "what's being talked about" rather than "who's talking."

| Alias | Type |
|---|---|
| `Inst1` | Central bank, country A |
| `Inst2` | Treasury / finance ministry, country A |
| `Inst3` | Central bank, country B |
| `Inst4` | International financial institution (IMF-shaped) |
| `Inst5` | Multilateral development bank |
| `Pol1` | Head of state, country A |
| `Pol2` | Finance minister, country A |
| `Pol3` | Head of state, country B |

### Countries

| Alias | Role |
|---|---|
| `CountryA` | Primary subject country of the example pipeline |
| `CountryB` | Secondary country, frequent comparator |
| `CountryC` | Third country, used in geopolitical examples |
| `RegionX` | Geographic region for "regional" expertise |

## Hosts and infrastructure

Server names are also anonymized. The pattern is what matters, not the hostname.

| Alias | Role |
|---|---|
| `RagHost` | Hosts the 7-actor pipeline + the 9 self-awareness components |
| `ScraperHub` | Hosts most scrapers + the market dashboard |
| `Gateway` | Hosts the wiki, the public-facing services, the MCP servers |

## Telegram bots

| Alias | Audience |
|---|---|
| `@MainBot` | Primary distribution channel |
| `@RegionalBot` | Country-specific distribution channel |

## Domains

| Alias | Purpose |
|---|---|
| `wiki.example.org` | Static wiki frontend |
| `obsidian.example.org` | Obsidian MCP endpoint |
| `api.example.org` | RAG HTTP API |

## What's NOT in the repo

- The actual mapping from alias → real name. That lives in private notes only.
- API keys, cookies, OAuth tokens, basic-auth credentials.
- Real Telegram bot tokens or user IDs.
- Real hostnames or IP addresses.
- The proprietary soul prompts and editorial voice of the live system.
- The actual entity registry contents.

## The enforcement

`.anonymization-blocklist.sha256` contains the SHA256 hash of every forbidden token (the real names from the categories above). `tools/check_anonymization.py` walks the repo, hashes every word, and fails the build if any match. The plaintext blocklist `.anonymization-blocklist.txt` is gitignored — only the hashed version ships, so readers can't reverse the list.

If you're contributing a new expertise, scraper template, or example query, run:

```bash
python tools/check_anonymization.py
```

before you commit. The pre-commit hook does the same, and CI does it on every PR.
