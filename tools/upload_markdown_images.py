#!/usr/bin/env python3
"""Upload local Markdown images to PicGo Cloud and rewrite source files."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

SOURCE = Path('source').resolve()
ROOT = Path('.').resolve()
EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.avif', '.bmp', '.ico', '.apng', '.tif', '.tiff'}
IMAGE_START = re.compile(r'!\[[^\]\n]*\]\(')
HTML_IMAGE = re.compile(r'<img\b[^>]*?\bsrc\s*=\s*([\'\"])(.*?)\1[^>]*>', re.IGNORECASE)
HTML_SRC = re.compile(r'\bsrc\s*=\s*([\'\"])(.*?)\1', re.IGNORECASE)
FENCE = re.compile(r'^ {0,3}(`{3,}|~{3,})')
CODE_SPAN = re.compile(r'(`+)(.*?)\1')


def local_image(url: str, markdown: Path) -> tuple[Path, str] | None:
    """Resolve a local image path, disallowing reads outside the repository."""
    url = url.strip().replace('\\ ', '%20')
    parts = urlsplit(url)
    if parts.scheme or parts.netloc or not parts.path or parts.path.startswith('\\'):
        return None
    relative = unquote(parts.path)
    if re.match(r'^[A-Za-z]:', relative):
        return None
    target = (SOURCE / relative.lstrip('/') if relative.startswith('/') else markdown.parent / relative).resolve()
    if not target.is_relative_to(ROOT):
        raise ValueError(f'Image escapes repository: {markdown}: {url}')
    if target.suffix.lower() not in EXTENSIONS:
        return None
    if not target.is_file():
        raise FileNotFoundError(f'Local image not found: {markdown}: {url} (resolved: {target})')
    suffix = ('?' + parts.query if parts.query else '') + ('#' + parts.fragment if parts.fragment else '')
    return target, suffix


def matching_parenthesis(text: str, start: int) -> int:
    depth, quote_char, angled = 1, '', False
    for pos in range(start + 1, len(text)):
        ch = text[pos]
        if ch == '\\':
            # Escape handling is completed by the iterator below via a skip marker.
            continue
        if pos > start + 1 and text[pos - 1] == '\\':
            continue
        if quote_char:
            if ch == quote_char:
                quote_char = ''
        elif ch in "\"'" and (pos == start + 1 or text[pos - 1].isspace()):
            quote_char = ch
        elif ch == '<':
            angled = True
        elif ch == '>':
            angled = False
        elif not angled and ch == '(':
            depth += 1
        elif not angled and ch == ')':
            depth -= 1
            if depth == 0:
                return pos
    return -1


def url_range(text: str, begin: int, end: int) -> tuple[int, int] | None:
    cursor = begin
    while cursor < end and text[cursor].isspace():
        cursor += 1
    if cursor >= end:
        return None
    if text[cursor] == '<':
        closing = text.find('>', cursor + 1, end)
        return (cursor + 1, closing) if closing >= 0 else None
    start, nesting = cursor, 0
    while cursor < end:
        char = text[cursor]
        if char == '\\' and cursor + 1 < end:
            cursor += 2
            continue
        if char.isspace() and nesting == 0:
            break
        if char == '(':
            nesting += 1
        elif char == ')':
            nesting -= 1
        cursor += 1
    return (start, cursor) if cursor > start else None


def rewrite_line(line: str, markdown: Path, image_url) -> str:
    protected = [(m.start(), m.end()) for m in CODE_SPAN.finditer(line)]
    def in_code(pos: int) -> bool:
        return any(a <= pos < b for a, b in protected)

    edits: list[tuple[int, int, str]] = []
    last_end = 0
    for m in IMAGE_START.finditer(line):
        if m.start() < last_end or in_code(m.start()):
            continue
        opening = m.end() - 1
        closing = matching_parenthesis(line, opening)
        if closing == -1:
            continue
        last_end = closing + 1
        bounds = url_range(line, opening + 1, closing)
        if not bounds:
            continue
        a, b = bounds
        result = local_image(line[a:b], markdown)
        if result:
            path, suffix = result
            edits.append((a, b, image_url(path) + suffix))

    for m in HTML_IMAGE.finditer(line):
        if in_code(m.start()) or any(m.start() < b and m.end() > a for a, b, _ in edits):
            continue
        source = HTML_SRC.search(m.group())
        if not source:
            continue
        start, end = m.start() + source.start(2), m.start() + source.end(2)
        result = local_image(line[start:end], markdown)
        if result:
            path, suffix = result
            edits.append((start, end, image_url(path) + suffix))

    for a, b, replacement in sorted(edits, reverse=True):
        line = line[:a] + replacement + line[b:]
    return line


def rewrite(text: str, markdown: Path, image_url) -> str:
    lines, fence_type, fence_size = [], '', 0
    for line in text.splitlines(keepends=True):
        marker = FENCE.match(line)
        if marker:
            sequence = marker.group(1)
            if not fence_type:
                fence_type, fence_size = sequence[0], len(sequence)
                lines.append(line)
                continue
            if sequence[0] == fence_type and len(sequence) >= fence_size:
                fence_type = ''
                fence_size = 0
                lines.append(line)
                continue
        lines.append(line if fence_type else rewrite_line(line, markdown, image_url))
    return ''.join(lines)


def upload_images(images: list[Path]) -> list[str]:
    """Use the official PicGo SDK without exposing the Cloud token in arguments."""
    if not os.environ.get('PICGO_CLOUD_TOKEN', '').strip():
        raise RuntimeError('Configure GitHub Actions Secret PICGO_CLOUD_TOKEN before uploading images')
    helper = Path(__file__).with_name('upload_picgo_images.cjs')
    result = subprocess.run(
        ['node', str(helper)],
        input=json.dumps([str(image) for image in images]),
        capture_output=True,
        text=True,
        encoding='utf-8',
        timeout=max(180, 180 * len(images)),
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'PicGo Cloud upload failed')
    try:
        urls = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError('PicGo Cloud uploader returned invalid JSON') from exc
    if not isinstance(urls, list) or len(urls) != len(images):
        raise RuntimeError('PicGo Cloud uploader returned an unexpected number of URLs')
    for url in urls:
        if not isinstance(url, str):
            raise RuntimeError('PicGo Cloud uploader returned an invalid image URL')
        parts = urlsplit(url)
        if parts.scheme != 'https' or not parts.netloc or any(c.isspace() for c in url):
            raise RuntimeError('PicGo Cloud uploader must return public HTTPS image URLs')
    return urls


def run() -> int:
    if not SOURCE.is_dir():
        raise RuntimeError('Expected Hexo source/ directory')
    markdown_files = sorted(SOURCE.rglob('*.md'))
    pending: dict[Path, str] = {}
    unique_images: dict[Path, str] = {}
    # Stage replacements in memory before any write.
    for markdown in markdown_files:
        original = markdown.read_text(encoding='utf-8')
        def collect(image: Path) -> str:
            unique_images.setdefault(image, '')
            return f'__LOCAL_IMAGE_{list(unique_images).index(image)}__'
        result = rewrite(original, markdown, collect)
        if result != original:
            pending[markdown] = result
    if not pending:
        print(f'No local image references found in {len(markdown_files)} Markdown files.')
        return 0

    uploads: dict[str, Path] = {}
    image_keys: list[str] = []
    for image in unique_images:
        key = hashlib.sha256(image.read_bytes()).hexdigest() + image.suffix.lower()
        uploads.setdefault(key, image)
        image_keys.append(key)
    print(f'Uploading {len(uploads)} unique images to PicGo Cloud')
    uploaded_urls = dict(zip(uploads, upload_images(list(uploads.values())), strict=True))
    urls = [uploaded_urls[key] for key in image_keys]

    for markdown, text in pending.items():
        for i, url in enumerate(urls):
            text = text.replace(f'__LOCAL_IMAGE_{i}__', url)
        markdown.write_text(text, encoding='utf-8')
        print(f'Updated {markdown.relative_to(ROOT)}')
    print(f'Done: {len(unique_images)} images, {len(pending)} Markdown files')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(run())
    except Exception as exc:
        print(f'Image upload failed: {exc}', file=sys.stderr)
        sys.exit(1)
