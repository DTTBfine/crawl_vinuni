# Crawl VinUni Sources

## Install

```bash
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium
```

## Auto crawl linked pages

Crawler reads `data/crawl_sources_tracker.json`, keeps HTML sources in domains `C4` and `C6`, opens each seed URL, discovers internal links, and crawls linked pages until `--max-depth` or `--max-pages` is reached.

```bash
python3 src/crawl_vinuni_web.py --discover-mode auto --max-depth 2 --max-pages 30
```

Crawl one source:

```bash
python3 src/crawl_vinuni_web.py --source-id vinuni_about --discover-mode auto --max-depth 2 --max-pages 30
```

Force browser-rendered discovery and click visible links:

```bash
python3 src/crawl_vinuni_web.py --discover-mode browser --click-links --max-depth 2 --max-pages 50
```

Outputs are saved under `data/landing/html_src/{domain}/{priority}/{source_id}.json`.

## Convert outputs to Markdown

```bash
python3 src/convert_to_md.py
```
