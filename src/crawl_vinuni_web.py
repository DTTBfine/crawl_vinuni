"""
Crawl các nguồn HTML từ file data/crawl_sources_tracker.json.

Hướng dẫn:
    1. Đọc danh sách nguồn từ data/crawl_sources_tracker.json.
    2. Chỉ crawl nguồn có domain là C4 hoặc C6 và source_type là "html".
    3. Lưu output vào data/landing/html_src/{domain}/{priority}/.
    4. Tên file JSON lấy từ source_id.

Cài đặt:
    pip install crawl4ai
    python -m playwright install chromium

Ví dụ:
    python3 src/crawl_vinuni_web.py --source-id vinuni_about --max-depth 2 --max-pages 30
    python3 src/crawl_vinuni_web.py --discover-mode browser --click-links --max-pages 50
"""

import asyncio
import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

PROJECT_DIR = Path(__file__).parent.parent
TRACKER_FILE = PROJECT_DIR / "data" / "crawl_sources_tracker.json"
DATA_DIR = PROJECT_DIR / "data" / "landing" / "html_src"
CRAWL4AI_BASE_DIR = PROJECT_DIR / "data" / "crawl4ai"
ALLOWED_DOMAINS = {"C4", "C6"}
ALLOWED_SOURCE_TYPE = "html"
MAX_CRAWL_DEPTH = 2
MAX_PAGES_PER_SOURCE = 30
SKIP_URL_PATTERNS = (
    "javascript:",
    "mailto:",
    "tel:",
    "login",
    "sharepoint.com",
    "forms.office.com",
    "outlook.office365.com",
    "sis.vinuni.edu.vn",
)
SKIP_EXTENSIONS = (
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".zip",
    ".rar",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".webp",
    ".mp4",
    ".mp3",
)


def setup_directory():
    """Tạo các thư mục output/cache nếu chưa có."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CRAWL4AI_BASE_DIR.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("CRAWL4_AI_BASE_DIRECTORY", str(CRAWL4AI_BASE_DIR))


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Crawl HTML sources from crawl_sources_tracker.json.")
    parser.add_argument("--source-id", help="Only crawl one source_id.")
    parser.add_argument("--limit", type=int, help="Only crawl the first N matching sources.")
    parser.add_argument("--max-depth", type=int, default=MAX_CRAWL_DEPTH, help="Recursive crawl depth.")
    parser.add_argument("--max-pages", type=int, default=MAX_PAGES_PER_SOURCE, help="Max pages per source.")
    parser.add_argument(
        "--discover-mode",
        choices=("auto", "static", "browser"),
        default="auto",
        help="How to discover child links: static HTML, rendered browser DOM, or auto fallback.",
    )
    parser.add_argument(
        "--click-links",
        action="store_true",
        help="In browser discovery mode, click visible links to catch links opened by JavaScript.",
    )
    parser.add_argument(
        "--browser-wait-ms",
        type=int,
        default=1000,
        help="Extra wait after opening each page in browser discovery mode.",
    )
    return parser.parse_args()


def load_crawl_sources(source_id: str | None = None, limit: int | None = None) -> list[dict]:
    """Load và lọc các nguồn cần crawl từ tracker JSON."""
    if not TRACKER_FILE.exists():
        raise FileNotFoundError(f"Không tìm thấy tracker file: {TRACKER_FILE}")

    sources = json.loads(TRACKER_FILE.read_text(encoding="utf-8"))
    filtered_sources = [
        source
        for source in sources
        if source.get("domain") in ALLOWED_DOMAINS
        and source.get("source_type") == ALLOWED_SOURCE_TYPE
        and source.get("url")
        and source.get("source_id")
    ]

    if source_id:
        filtered_sources = [source for source in filtered_sources if source.get("source_id") == source_id]
    if limit:
        filtered_sources = filtered_sources[:limit]

    return filtered_sources


def build_output_path(source: dict) -> Path:
    """Tạo đường dẫn output theo domain/priority/source_id."""
    domain = source["domain"]
    priority = source.get("priority", "unknown").strip().lower()
    source_id = source["source_id"].strip()
    return DATA_DIR / domain / priority / f"{source_id}.json"


def normalize_url(url: str) -> str:
    """Normalize URL for deduplication."""
    url, _fragment = urldefrag(url)
    return url.rstrip("/")


def get_host(url: str) -> str:
    """Return normalized hostname."""
    return (urlparse(url).hostname or "").lower()


def is_vinuni_host(host: str) -> bool:
    """Check whether a host belongs to VinUni."""
    return host == "vinuni.edu.vn" or host.endswith(".vinuni.edu.vn")


def is_crawlable_link(url: str, seed_url: str) -> bool:
    """Allow relevant HTML pages and skip assets, auth pages, forms, and portals."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False

    lower_url = url.lower()
    if any(pattern in lower_url for pattern in SKIP_URL_PATTERNS):
        return False
    if parsed.path.lower().endswith(SKIP_EXTENSIONS):
        return False

    seed_host = get_host(seed_url)
    target_host = get_host(url)
    return target_host == seed_host or (is_vinuni_host(seed_host) and is_vinuni_host(target_host))


def extract_main_content_html(html: str) -> str:
    """Extract likely main content and remove nav/header/footer/sidebar noise."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html or "", "html.parser")

    noisy_selectors = [
        "script",
        "style",
        "noscript",
        "header",
        "footer",
        "nav",
        "aside",
        "form",
        "[role='navigation']",
        "[role='banner']",
        "[role='contentinfo']",
        ".menu",
        ".navbar",
        ".nav",
        ".header",
        ".footer",
        ".sidebar",
        ".side-bar",
        ".tabbar",
        ".tab-bar",
        ".breadcrumb",
        ".breadcrumbs",
        ".search",
        ".login",
    ]
    for selector in noisy_selectors:
        for node in soup.select(selector):
            node.decompose()

    main_candidates = soup.select(
        ".page_body_resource, #sectionPortal, .portal, .page_body_xx, "
        "main, article, [role='main'], .main-content, .entry-content, "
        ".post-content, .page-content, .resource-content, .list-resource, #content, .content"
    )
    if main_candidates:
        main_node = max(main_candidates, key=lambda node: len(node.get_text(" ", strip=True)))
        return str(main_node)

    body = soup.body or soup
    return str(body)


def html_to_markdown(html: str) -> str:
    """Convert cleaned main-content HTML to markdown."""
    from markdownify import markdownify as md

    markdown = md(html or "", heading_style="ATX")
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    return markdown.strip()


def extract_content_links(html: str, base_url: str, seed_url: str) -> list[str]:
    """Extract crawlable links from main content only."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html or "", "html.parser")
    links = []
    seen = set()

    for anchor in soup.find_all("a", href=True):
        url = normalize_url(urljoin(base_url, anchor["href"]))
        if url in seen or not is_crawlable_link(url, seed_url):
            continue
        seen.add(url)
        links.append(url)

    return links


def unique_links(urls: list[str], seed_url: str) -> list[str]:
    """Normalize, filter, and deduplicate discovered links while preserving order."""
    links = []
    seen = set()

    for raw_url in urls:
        if not raw_url:
            continue
        url = normalize_url(raw_url)
        if url in seen or not is_crawlable_link(url, seed_url):
            continue
        seen.add(url)
        links.append(url)

    return links


def get_result_markdown(result) -> str:
    """Read crawl4ai markdown safely across versions."""
    markdown = getattr(result, "markdown", None)
    if markdown is None:
        return ""
    return getattr(markdown, "raw_markdown", str(markdown)) or ""


async def discover_browser_links(page, url: str, seed_url: str, wait_ms: int, click_links: bool) -> list[str]:
    """Open a page in Playwright and discover links from the rendered DOM."""
    discovered = []

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        if wait_ms > 0:
            await page.wait_for_timeout(wait_ms)

        hrefs = await page.eval_on_selector_all(
            "a[href]",
            """(anchors) => anchors.map((anchor) => anchor.href).filter(Boolean)""",
        )
        discovered.extend(hrefs)

        if click_links:
            candidate_hrefs = await page.eval_on_selector_all(
                "a[href]",
                """(anchors) => anchors
                    .filter((anchor) => {
                        const style = window.getComputedStyle(anchor);
                        const rect = anchor.getBoundingClientRect();
                        return style.visibility !== "hidden"
                            && style.display !== "none"
                            && rect.width > 0
                            && rect.height > 0;
                    })
                    .map((anchor) => anchor.href)
                    .filter(Boolean)
                """,
            )

            for href in candidate_hrefs[:25]:
                try:
                    absolute_url = normalize_url(href)
                    if not is_crawlable_link(absolute_url, seed_url):
                        continue

                    click_page = await page.context.new_page()
                    try:
                        await click_page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        selector = f"a[href='{href}']"
                        link = click_page.locator(selector).first()
                        if await link.count() == 0:
                            discovered.append(absolute_url)
                            continue

                        await link.click(timeout=2000)
                        await click_page.wait_for_load_state("domcontentloaded", timeout=5000)
                        discovered.append(click_page.url)
                    finally:
                        await click_page.close()
                except Exception:
                    continue
    except Exception as exc:
        print(f"      ! Browser link discovery failed for {url}: {exc}", flush=True)

    return unique_links(discovered, seed_url)


async def crawl_article(
    source: dict,
    max_depth: int,
    max_pages: int,
    discover_mode: str = "auto",
    click_links: bool = False,
    browser_wait_ms: int = 1000,
) -> dict:
    """
    Crawl một nguồn và trả về dict chứa metadata + content.

    Returns:
        {
            "source_id": str,
            "url": str,
            "source_name": str,
            "domain": str,
            "subdomain": str,
            "priority": str,
            "source_type": str,
            "date_crawled": str (ISO format),
            "content_markdown": str
        }
    """
    try:
        from crawl4ai import AsyncWebCrawler
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "Chưa cài crawl4ai. Hãy chạy: python3 -m pip install -r requirements.txt"
        ) from exc

    seed_url = normalize_url(source["url"])

    browser_context = None
    browser = None
    browser_page = None
    actual_discover_mode = discover_mode

    if discover_mode in {"auto", "browser"}:
        try:
            from playwright.async_api import async_playwright

            browser_context = await async_playwright().start()
            browser = await browser_context.chromium.launch(headless=True)
            browser_page = await browser.new_page()
            actual_discover_mode = "browser"
        except ModuleNotFoundError as exc:
            if discover_mode == "browser":
                raise ModuleNotFoundError(
                    "Chưa cài Playwright. Hãy chạy: python3 -m pip install -r requirements.txt "
                    "và python3 -m playwright install chromium"
                ) from exc
            actual_discover_mode = "static"
        except Exception as exc:
            if discover_mode == "browser":
                raise
            print(f"    ! Browser discovery unavailable, falling back to static links: {exc}", flush=True)
            actual_discover_mode = "static"

    async with AsyncWebCrawler(base_directory=str(CRAWL4AI_BASE_DIR)) as crawler:
        pages = []
        visited = set()
        queue = [(seed_url, 0, "seed")]

        try:
            while queue and len(visited) < max_pages:
                url, depth, parent_url = queue.pop(0)
                if url in visited:
                    continue

                visited.add(url)
                print(f"    - depth={depth} page={len(visited)} {url}", flush=True)
                result = await crawler.arun(url=url)

                cleaned_html = extract_main_content_html(getattr(result, "cleaned_html", "") or getattr(result, "html", ""))
                content_markdown = html_to_markdown(cleaned_html) or get_result_markdown(result)
                static_links = extract_content_links(cleaned_html, url, seed_url)
                browser_links = []

                if browser_page is not None:
                    browser_links = await discover_browser_links(
                        browser_page,
                        url,
                        seed_url,
                        wait_ms=browser_wait_ms,
                        click_links=click_links,
                    )

                child_links = unique_links(static_links + browser_links, seed_url)

                pages.append(
                    {
                        "url": url,
                        "parent_url": parent_url,
                        "depth": depth,
                        "success": getattr(result, "success", None),
                        "content_markdown": content_markdown,
                        "discovered_links": child_links,
                        "discovery_mode": actual_discover_mode,
                    }
                )

                if depth >= max_depth:
                    continue

                for link in child_links:
                    if link not in visited and len(visited) + len(queue) < max_pages:
                        queue.append((link, depth + 1, url))
        finally:
            if browser is not None:
                await browser.close()
            if browser_context is not None:
                await browser_context.stop()

        combined_content = "\n\n".join(
            f"## Page: {page['url']}\n\n{page['content_markdown']}"
            for page in pages
            if page.get("content_markdown")
        )

        return {
            "source_id": source.get("source_id", ""),
            "url": seed_url,
            "source_name": source.get("source_name", ""),
            "domain": source.get("domain", ""),
            "subdomain": source.get("subdomain", ""),
            "priority": source.get("priority", ""),
            "source_type": source.get("source_type", ""),
            "authority_level": source.get("authority_level"),
            "crawl_frequency": source.get("crawl_frequency", ""),
            "status": source.get("status", ""),
            "output_format": source.get("output_format", ""),
            "note": source.get("note", ""),
            "date_crawled": datetime.now().isoformat(),
            "crawl_depth": max_depth,
            "discover_mode": actual_discover_mode,
            "click_links": click_links,
            "page_count": len(pages),
            "content_markdown": combined_content,
            "pages": pages,
        }


async def crawl_all(
    source_id: str | None = None,
    limit: int | None = None,
    max_depth: int = MAX_CRAWL_DEPTH,
    max_pages: int = MAX_PAGES_PER_SOURCE,
    discover_mode: str = "auto",
    click_links: bool = False,
    browser_wait_ms: int = 1000,
):
    """Crawl toàn bộ nguồn phù hợp trong tracker JSON."""
    setup_directory()
    sources = load_crawl_sources(source_id=source_id, limit=limit)

    if not sources:
        print("Không có nguồn nào phù hợp để crawl.", flush=True)
        return

    for i, source in enumerate(sources, 1):
        url = source["url"]
        source_id = source["source_id"]
        domain = source["domain"]
        priority = source.get("priority", "unknown")
        print(
            f"[{i}/{len(sources)}] Crawling {domain}/{priority}: {source_id} - {url}",
            flush=True,
        )
        article = await crawl_article(
            source,
            max_depth=max_depth,
            max_pages=max_pages,
            discover_mode=discover_mode,
            click_links=click_links,
            browser_wait_ms=browser_wait_ms,
        )

        # Lưu file JSON
        filepath = build_output_path(source)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(json.dumps(article, ensure_ascii=False, indent=2))
        print(f"  ✓ Saved: {filepath}", flush=True)


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(
        crawl_all(
            source_id=args.source_id,
            limit=args.limit,
            max_depth=args.max_depth,
            max_pages=args.max_pages,
            discover_mode=args.discover_mode,
            click_links=args.click_links,
            browser_wait_ms=args.browser_wait_ms,
        )
    )
