"""Small, dependency-free Markdown subset used for resume exports."""
from html import escape
import re


def inline(value: str) -> str:
    value = escape(value, quote=False)
    return re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', value)


def to_html(text: str) -> str:
    parts, bullets = [], []
    def flush():
        nonlocal bullets
        if bullets:
            parts.append('<ul>' + ''.join(f'<li>{inline(x)}</li>' for x in bullets) + '</ul>')
            bullets = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            flush(); continue
        heading = re.match(r'^(#{1,3})\s+(.+)$', line)
        bullet = re.match(r'^[-*]\s+(.+)$', line)
        if heading:
            flush(); level = len(heading[1]); parts.append(f'<h{level}>{inline(heading[2])}</h{level}>')
        elif bullet:
            bullets.append(bullet[1])
        else:
            flush(); parts.append(f'<p>{inline(line)}</p>')
    flush()
    return '\n'.join(parts)
