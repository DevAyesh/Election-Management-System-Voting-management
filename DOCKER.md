# Docker Deployment Guide

## Quick Start Commands

```bash
docker compose up --build            # normal start (data kept)
$env:DEMO_RESET="true"; docker compose up --build   # demo: fresh start (PowerShell)
docker compose down                  # stop
docker compose logs -f watcher       # live integrity watcher
docker compose exec web python manage.py audit_chain --anchor-file data/anchors.txt
```

> [!NOTE]
> `audit_chain` accepts `--anchor <COUNT:TIPHASH>` and `--save-anchor <FILE>` rather than `--anchor-file`.
> 
> To audit the chain against the latest anchor recorded by `watcher` in `data/anchors.txt`, use either:
> 
> **Standard audit (checks chain integrity, block contents, and ledger reconciliation):**
> ```bash
> docker compose exec web python manage.py audit_chain
> ```
> 
> **Audit with the latest anchor from `data/anchors.txt`:**
> * In Linux / Container Shell:
>   ```bash
>   docker compose exec web sh -c 'python manage.py audit_chain --anchor "$(tail -n 1 data/anchors.txt)"'
>   ```
> * In PowerShell:
>   ```powershell
>   docker compose exec web python manage.py audit_chain --anchor (Get-Content data/anchors.txt -Tail 1)
>   ```
