---
alwaysApply: true
---

# CursorTravel - Seamless Multi-Environment Navigation System

> **Note:** This is the production environments map for the live M3xA system. It documents real hostnames, IPs, ports, and service paths. API keys / bot tokens are NOT included — they live in env vars on each host (`~/.bashrc`, systemd `Environment=`, or the `.api_key_*` files referenced inline).

## Current Location Detector

```yaml
QUESTION: "Where am I?"
ANSWER: Check these indicators:
  - Terminal prompt: $(echo $PS1)
  - Current user: $(whoami)
  - Current directory: $(pwd)
  - Hostname: $(hostname)
  - Can SSH?: $(ssh -o ConnectTimeout=2 ubuntu@44.225.226.126 echo "yes" 2>/dev/null || echo "no")
```

## Available Environments

### 1. LOCAL_MAC

```yaml
name: "Pedro's Local Mac"
identifier:
  prompt: "(base) basics-MacBook-Pro"
  user: "Pedro_Ribeiro"
  home: "/Users/Pedro_Ribeiro"

navigation_commands:
  to_project: "cd /Users/Pedro_Ribeiro/k"
  to_home: "cd ~"
  check_location: "pwd && whoami"

capabilities:
  - File editing
  - Git operations
  - AWS CLI
  - Browser access
  - SSH (when network allows)

limitations:
  - Direct AWS file access
  - Server process management

quick_travel:
  aws_ssh: "ssh -i ~/.ssh/aws-ec2-key ubuntu@44.225.226.126"
  aws_console: "open 'https://us-west-2.console.aws.amazon.com/ec2'"

  check_sage: "curl -I http://44.225.226.126:8540"
  check_xscraper: "curl -I http://44.225.226.126:8509"

  push_code: "git add . && git commit -m 'update' && git push"
  check_status: "git status"

  list_buckets: "aws s3 ls"
  sage_bucket: "aws s3 ls s3://sage-unified-feed-lance/"
```

### 2. AWS_SERVER (ARGUS / RAG host — internally "R6G")

```yaml
name: "AWS EC2 - ARGUS Server (the RAG host)"
identifier:
  prompt: "ubuntu@ip-172-31-44-26"
  user: "ubuntu"
  hostname: "ip-172-31-44-26"
  elastic_ip: "44.225.226.126"
  instance_id: "i-06360d2516ecd4a35"
  domain: "argus.data-codex.com"

navigation_commands:
  connect_ssh: "ssh -i ~/.ssh/aws-ec2-key ubuntu@44.225.226.126"
  connect_ec2: "open 'https://us-west-2.console.aws.amazon.com/ec2/v2/home?region=us-west-2#ConnectToInstance:instanceId=i-06360d2516ecd4a35'"

  to_sage: "cd /home/ubuntu/newspaper_project"
  to_spyder: "cd /home/ubuntu/curator1_real"
  to_logs: "cd /home/ubuntu/logs"

capabilities:
  - Service management
  - Database access
  - Log viewing
  - Process control

services:
  m3xa_rag:
    path: "/home/ubuntu/newspaper_project/m3xa_rag_8550.py"
    port: 8550
    notes: "The main RAG service. Souls live at /home/ubuntu/argus/config/soul_{global,brazil}.md, hot-reloaded every 5 min via _load_soul()."
  sage:
    path: "/home/ubuntu/newspaper_project"
    start: "nohup python3 sage4_interface_fixed.py > ../SAGE4/sage.log 2>&1 &"
    check: "ps aux | grep sage4"
    port: 8540
    url: "http://44.225.226.126:8540"
    domain_url: "http://argus.data-codex.com/sage"

  xscraper:
    path: "/home/ubuntu/newspaper_project"
    start: "nohup python3 xscraper_twitter.py > ../logs/xscraper_twitter.log 2>&1 &"
    check: "ps aux | grep xscraper"
    port: 8509
    url: "http://44.225.226.126:8509"
    domain_url: "http://argus.data-codex.com/xscraper"
    notes: "October 14, 2025 - Beautiful interface with smart refresh, user rating persistence, dual scores"

  spyder:
    path: "/home/ubuntu/agenticspyder4_curator1_aws/src"
    start: "nohup python3 /home/ubuntu/start_spyder_fixed.py > /home/ubuntu/spyder_fixed.log 2>&1 &"
    check: "ps aux | grep spyder"
    port: 8046
    url: "http://44.225.226.126:8046/curator1"
    domain_url: "http://argus.data-codex.com/spyder"
    notes: "October 13 AWS version with fixes"

  catalog:
    path: "/home/ubuntu/spyder_main"
    start: "nohup python3 spyder_book_catalog_enhanced_fixed.py > book_catalog.log 2>&1 &"
    check: "ps aux | grep catalog"
    port: 8057
    url: "http://44.225.226.126:8057"

  codex:
    path: "/home/ubuntu/codex_standalone"
    start: "nohup python3 codex_app.py > codex.log 2>&1 &"
    check: "ps aux | grep codex"
    port: 8055
    url: "http://44.225.226.126:8055"
    domain_url: "http://argus.data-codex.com/codex-v1"
    notes: "Standalone AI - no database required"

  codex_v2:
    path: "/home/ubuntu/codex_v2_orchestrator"
    start: "./start_codex_v2.sh"
    check: "ps aux | grep 'python3 app.py'"
    port: 8056
    url: "http://44.225.226.126:8056"
    domain_url: "http://argus.data-codex.com/codex"
    notes: "Universal Orchestrator - Multi-Agent System"

quick_travel:
  exit: "exit"
  start_all: "cd /home/ubuntu && ./start_all_services.sh"
  check_all: "netstat -tlnp | grep -E '(8540|8509|8046|8057|8550)'"
  sage_log: "tail -f /home/ubuntu/SAGE4/sage.log"
  xscraper_log: "tail -f /home/ubuntu/logs/xscraper_twitter.log"
```

### 3. GITHUB

```yaml
name: "GitHub Repository"
identifier:
  remote: "git@github.com:prcodex/Argus.git"
  branch: "main"
  local_path: "/Users/Pedro_Ribeiro/k/argus_github"

repositories:
  argus:
    url: "https://github.com/prcodex/Argus"
    local: "/Users/Pedro_Ribeiro/k/argus_github"
    description: "SAGE + XSCRAPER system"

  codex:
    url: "https://github.com/prcodex/Codex"
    description: "SPYDER curator1 - Advanced AI Research System"

  sage_4_3:
    url: "https://github.com/prcodex/sage-4.3"
    description: "SAGE AI 4.3 standalone"

  m3xa_core:
    url: "https://github.com/prcodex/m3xa-core"
    description: "This repo — the M3xA core (souls + RAG + scrapers + self-awareness loop)"
```

### 4. EC_Gateway — Orchestration

```yaml
name: "EC_Gateway - Orchestration"
identifier:
  prompt: "ubuntu@ip-172-31-35-124"
  user: "ubuntu"
  hostname: "ip-172-31-35-124"
  elastic_ip: "44.227.226.179"
  instance_id: "i-092e3c61ef5cdfa63"
  instance_type: "t3.medium"

navigation_commands:
  connect_ssh: "ssh -i ~/.ssh/aws-ec2-key ubuntu@44.227.226.179"
  to_scrapers: "cd /home/ubuntu/scrapers"
  to_logs: "cd /home/ubuntu/scrapers/logs"

capabilities:
  - Orchestration (RSS, email, tweet collection)
  - Nginx proxy to R6G services
  - Monitoring (dashboards, watchdogs)
  - Scraper EC2 health monitoring

role: "Orchestration — collects URLs, scrapes emails, enriches tweets, monitors. Article extraction migrated to Scraper EC2 on Feb 25, 2026."

services:
  gateway_dashboard:
    port: 8554
    url: "http://44.227.226.179:8554"
  gold_ops_dashboard:
    port: 8563
    url: "http://44.227.226.179:8563"
  gold_twitter_monitor:
    port: 8562
    url: "http://44.227.226.179:8562"

quick_travel:
  check_health: "curl -s http://44.227.226.179/health"
  check_scraper: "curl -s http://44.238.184.219:8580/health"
  view_logs: "tail -f ~/scrapers/logs/sync_cron.log"

cost: "$30/month"
upgraded: "February 25, 2026 (t3.small → t3.medium)"
```

### 4b. SCRAPER EC2 — Dedicated Article Extraction

```yaml
name: "Scraper EC2 - Dedicated Article Extraction"
identifier:
  prompt: "ubuntu@ip-172-31-44-59"
  user: "ubuntu"
  hostname: "ip-172-31-44-59"
  elastic_ip: "44.238.184.219"
  instance_id: "i-048b867050b70bf9f"
  instance_type: "t3.medium"

navigation_commands:
  connect_ssh: "ssh -i ~/.ssh/aws-ec2-key ubuntu@44.238.184.219"
  to_scraper: "cd /home/ubuntu/scraper"
  to_logs: "cd /home/ubuntu/scraper/logs"

capabilities:
  - 3 parallel macro extraction workers
  - 1 brazil extraction daemon
  - Direct sync to R6G LanceDB
  - Independent RSS collection
  - Health endpoint (port 8580)

services:
  health:
    port: 8580
    url: "http://44.238.184.219:8580/health"
    description: "JSON health status of all daemons"
  worker_1:
    sources: "BBG, MW"
    method: "ZenRows primary"
  worker_2:
    sources: "WSJ, BARN"
    method: "Cookies (human-like)"
  worker_3:
    sources: "RTRS, FT"
    method: "ScraperAPI + ZenRows"
  brazil:
    sources: "VALOR, FOLHA, ANTAG, METRO, OESTE, CNNBR"

cost: "$30/month"
created: "February 25, 2026"
```

### 5. S3_STORAGE

```yaml
name: "AWS S3 Buckets"
identifier:
  region: "us-west-2"
  main_bucket: "sage-unified-feed-lance"

buckets:
  sage_unified_feed:
    name: "sage-unified-feed-lance"
    paths:
      sage4: "SAGE AI email/news data"
      tweetss3: "XSCRAPER Twitter data"
      lancedb: "Legacy LanceDB data"

  spyder_data:
    name: "sage-intelligence-data"
    paths:
      fx-ohlc: "Foreign exchange data"
```

## Domain Access

### ARGUS Intelligence System

**Main Domain**: http://argus.data-codex.com

| Service | Domain URL | Direct IP | Description |
|---------|------------|-----------|-------------|
| **M3xA RAG** | (Telegram only) | http://44.225.226.126:8550 | Macro intelligence agent |
| **XSCRAPER** | http://argus.data-codex.com/xscraper | http://44.225.226.126:8509 | Financial Intelligence Feed |
| **SAGE AI** | http://argus.data-codex.com/sage | http://44.225.226.126:8540 | Email/News System |
| **SPYDER** | http://argus.data-codex.com/spyder | http://44.225.226.126:8046/curator1 | Research Curator (278 books) |
| **CODEX V2** | http://argus.data-codex.com/codex | http://44.225.226.126:8056 | Universal Orchestrator |
| **CODEX V1** | http://argus.data-codex.com/codex-v1 | http://44.225.226.126:8055 | Standalone AI |

### Wiki frontend (May 10, 2026) — added to Gateway services

```yaml
wiki:
  url: https://wiki.m3xa.org
  auth: HTTP basic auth (HTTPS only)
  users: pjr, guest
  add_user: ssh gateway → sudo htpasswd -B /etc/nginx/.htpasswd-wiki <user>
  source: /home/ubuntu/obsidian-vault (symlinked into /home/ubuntu/quartz/content)
  build_cadence: every 5 min via systemd timer (quartz-build.timer); rebuild only when vault HEAD changes
  manager: systemd (quartz-serve.service on 127.0.0.1:8572 + quartz-build.timer)
  vhost: /etc/nginx/sites-enabled/wiki-m3xa
  cert: /etc/letsencrypt/live/wiki.m3xa.org/ (renews 2026-08-08)
  generator: Quartz 4.5.2 + Node 22.22.2 (via nvm)
  static_handler: /home/ubuntu/quartz/serve_quartz.py
```

DNS for wiki.m3xa.org is grey-cloud (44.227.226.179 directly); the gate is basic auth at nginx, not Cloudflare Access.

## Key Principles

1. **Always Know Your Location** - Use `whereami` function
2. **State Awareness** - Track what's running where
3. **Quick Travel** - Use aliases for common moves
4. **Service Health** - Regular status checks
5. **Backup First** - Always backup before changes
6. **No credentials in this file** — bot tokens, API keys, and passwords live in env vars on each host, never in this map
