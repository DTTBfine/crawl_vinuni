"""
Convert toàn bộ file trong data/landing/ thành Markdown.

Sử dụng MarkItDown của Microsoft:
    https://github.com/microsoft/markitdown

Cài đặt:
    pip install markitdown
    python -m pip install "markitdown[all]"

Hướng dẫn:
    1. Scan toàn bộ file trong data/landing/ (PDF, DOCX, JSON)
    2. Convert sang Markdown
    3. Lưu vào data/standardized/ giữ nguyên cấu trúc thư mục
"""

import json
import re
from pathlib import Path

from markitdown import MarkItDown

LANDING_DIR = Path(__file__).parent.parent / "data" / "landing"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "standardized"


def write_markdown(output_path: Path, content: str):
    """Write markdown content with UTF-8 encoding."""
    output_path.write_text(content.strip() + "\n", encoding="utf-8")


def build_web_markdown(data: dict) -> str:
    """Tạo markdown chỉ gồm title và content từ JSON đã crawl."""
    pages = data.get("pages") or []
    if pages:
        return build_pages_markdown(data, pages)

    return build_single_page_markdown(
        title=data.get("source_name", ""),
        content=data["content_markdown"],
    )


def build_pages_markdown(data: dict, pages: list[dict]) -> str:
    """Tạo markdown từ danh sách page đã crawl, bỏ metadata/debug links."""
    source_name = data.get("source_name", "")
    sections = []

    for page in pages:
        content = page.get("content_markdown")
        if not content or not should_include_page(page, len(pages)):
            continue

        title = extract_markdown_title(content) or source_name or page.get("url", "")
        section = build_single_page_markdown(title=title, content=content)
        if section:
            sections.append(section)

    return "\n\n".join(sections)


def build_single_page_markdown(title: str, content: str) -> str:
    """Render một trang theo dạng title + content."""
    clean_content = clean_markdown_noise(clean_web_content(content, title))
    clean_title = extract_markdown_title(clean_content) or title or "Untitled"
    body = remove_leading_title(clean_content, clean_title)

    if not body.strip():
        return ""

    return f"## {clean_title}\n\n{body.strip()}"


def should_include_page(page: dict, total_pages: int) -> bool:
    """Bỏ page rỗng, page lỗi 404, và page hub chỉ dùng để phát hiện links."""
    content = page.get("content_markdown") or ""
    normalized = content.lower()

    if "## 404" in content or "sorry, this page either moved or no longer exists" in normalized:
        return False

    discovered_links = page.get("discovered_links") or []
    if total_pages > 1 and page.get("depth") == 0 and len(discovered_links) >= 8:
        return False

    return True


def extract_markdown_title(content: str) -> str:
    """Lấy heading đầu tiên trong markdown."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") and not stripped.startswith("#1"):
            return re.sub(r"^#+\s*", "", stripped).strip()
    return ""


def remove_leading_title(content: str, title: str) -> str:
    """Bỏ heading đầu nếu đã được dùng làm title section."""
    lines = content.splitlines()
    title_normalized = title.strip().lower()
    start_index = 0

    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        line_title = re.sub(r"^#+\s*", "", stripped).strip().lower()
        if stripped.startswith("#") and line_title == title_normalized:
            start_index = index + 1
            continue
        start_index = index
        break

    return "\n".join(lines[start_index:]).strip()


def clean_markdown_noise(content: str) -> str:
    """Bỏ các dòng icon/banner/control text còn sót lại sau crawl."""
    noise_lines = {
        "view more",
        "view less",
        "no search results found.",
        "top of page",
    }
    cleaned_lines = []

    for line in content.splitlines():
        stripped = line.strip()
        normalized = stripped.lower()

        if normalized in noise_lines:
            continue
        if re.fullmatch(r"!\[[^\]]*\]\([^)]+\)", stripped):
            continue
        if "external-link-icon.svg" in stripped or "lock-link-icon.svg" in stripped:
            continue
        if "vinuni_banner" in stripped.lower() or "banner footer" in stripped.lower():
            continue

        cleaned_lines.append(line)

    content = "\n".join(cleaned_lines)
    content = re.sub(r"\[Top of page\]\(javascript:[^)]+\)", "", content)
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content.strip()


def build_web_markdown_with_metadata(data: dict) -> str:
    """Deprecated: tạo markdown có metadata từ JSON đã crawl."""
    url = data.get("url", "")
    source_name = data.get("source_name", "")
    date_crawled = data.get("date_crawled", "")
    content = clean_web_content(data["content_markdown"], source_name)

    return f"""---
url: {url}
source_name: {source_name}
date_crawled: {date_crawled}
---

# {source_name}

Source: {url}

{content}
"""


def clean_web_content(content: str, source_name: str) -> str:
    """Bóc tách phần nội dung chính, bỏ menu/header/footer phổ biến của website."""
    lines = content.splitlines()
    title_candidates = [
        source_name,
        source_name.replace("VinUni ", ""),
        source_name.replace("Experience VinUni ", ""),
    ]
    title_candidates = [title.strip().lower() for title in title_candidates if title.strip()]

    start_index = 0
    for index, line in enumerate(lines):
        stripped = line.strip()
        normalized = re.sub(r"^#+\s*", "", stripped).strip().lower()
        if stripped.startswith("#") and not stripped.startswith("#1"):
            start_index = index
            break
        if normalized in title_candidates:
            start_index = index
            break

    end_index = len(lines)
    for index, line in enumerate(lines[start_index:], start=start_index):
        if "![Banner footer]" in line or line.strip().startswith("Copyright ©"):
            end_index = index
            break

    return "\n".join(lines[start_index:end_index]).strip()


def convert_docs():
    """Convert PDF/DOCX files và giữ nguyên cấu trúc thư mục từ data/landing."""
    md = MarkItDown()
    converted_count = 0

    for filepath in LANDING_DIR.rglob("*"):
        if filepath.suffix.lower() not in (".pdf", ".docx", ".doc"):
            continue

        relative_path = filepath.relative_to(LANDING_DIR).with_suffix(".md")
        output_path = OUTPUT_DIR / relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"Converting: {filepath}")
        result = md.convert(str(filepath))
        write_markdown(output_path, result.text_content)
        converted_count += 1
        print(f"  ✓ Saved: {output_path}")

    print(f"  ✓ Converted document files: {converted_count}")


def convert_crawled_json_files():
    """Convert crawled JSON files có content_markdown khác null sang markdown."""
    converted_count = 0
    skipped_count = 0

    for filepath in LANDING_DIR.rglob("*.json"):
        data = json.loads(filepath.read_text(encoding="utf-8"))
        content_markdown = data.get("content_markdown")

        if content_markdown is None:
            skipped_count += 1
            print(f"  - Skip null content_markdown: {filepath}")
            continue

        relative_path = filepath.relative_to(LANDING_DIR).with_suffix(".md")
        output_path = OUTPUT_DIR / relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"Converting: {filepath}")
        content = build_web_markdown(data)
        write_markdown(output_path, content)
        converted_count += 1
        print(f"  ✓ Saved: {output_path}")

    print(f"  ✓ Converted JSON files: {converted_count}")
    print(f"  - Skipped null content_markdown: {skipped_count}")


def convert_all():
    """Convert toàn bộ files."""
    print("=" * 50)
    print("Task 3: Convert to Markdown (MarkItDown)")
    print("=" * 50)

    print("\n--- File Documents ---")
    convert_docs()

    print("\n--- Crawled JSON Websites ---")
    convert_crawled_json_files()

    print("\n✓ Done! Output tại:", OUTPUT_DIR)


if __name__ == "__main__":
    convert_all()
