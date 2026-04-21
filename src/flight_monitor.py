import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup


REQUEST_TIMEOUT = 30
SAO_PAULO_TZ = timezone(timedelta(hours=-3))
MAX_TELEGRAM_MESSAGE_LENGTH = 3800
SOURCE_PAGES = (
    "https://www.melhoresdestinos.com.br/passagens-aereas",
    "https://www.melhoresdestinos.com.br/passagens-aereas/promocoes-passagens",
    "https://passageirodeprimeira.com/categorias/passagens-aereas/",
)
KEYWORD_GROUPS = (
    ("goiania", "gyn"),
    ("sao paulo", "gru", "cgh"),
    ("campinas", "vcp", "viracopos"),
)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36"
)


@dataclass(frozen=True)
class OfferItem:
    title: str
    url: str
    source: str
    published_at: str
    summary: str


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_text.lower()


def get_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"Environment variable {name} is required.")
    return value.strip()


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def fetch_html(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.text


def extract_links_from_listing(html: str, base_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[tuple[str, str]] = []
    seen = set()
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "").strip()
        title = " ".join(anchor.get_text(" ", strip=True).split())
        if not href.startswith("http"):
            continue
        if href == base_url or len(title) < 12:
            continue
        item = (href, title)
        if item in seen:
            continue
        seen.add(item)
        links.append(item)
    return links


def matches_route(text: str) -> bool:
    normalized = normalize_text(text)
    has_destination = any(keyword in normalized for keyword in KEYWORD_GROUPS[0])
    has_origin = any(keyword in normalized for keyword in KEYWORD_GROUPS[1] + KEYWORD_GROUPS[2])
    return has_destination and has_origin


def extract_summary(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    snippets: list[str] = []
    for tag in soup.find_all(["p", "li"]):
        text = " ".join(tag.get_text(" ", strip=True).split())
        if len(text) < 50:
            continue
        snippets.append(text)
        if len(snippets) == 2:
            break
    return " ".join(snippets)


def extract_published_at(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for attr in ("article:published_time", "og:updated_time"):
        tag = soup.find("meta", attrs={"property": attr})
        if tag and tag.get("content"):
            return format_datetime(tag["content"])
    for attr in ("datePublished", "dateModified"):
        tag = soup.find("meta", attrs={"itemprop": attr})
        if tag and tag.get("content"):
            return format_datetime(tag["content"])
    time_tag = soup.find("time")
    if time_tag and time_tag.get("datetime"):
        return format_datetime(time_tag["datetime"])
    text = normalize_text(soup.get_text(" ", strip=True))
    match = re.search(r"(\d{2}/\d{2}/\d{4}\s+as\s+\d{1,2}:\d{2})", text)
    if match:
        return match.group(1)
    return "Data nao identificada"


def format_datetime(value: str) -> str:
    try:
        iso_value = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(iso_value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=SAO_PAULO_TZ)
        return parsed.astimezone(SAO_PAULO_TZ).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return value


def collect_offers() -> list[OfferItem]:
    session = build_session()
    results: list[OfferItem] = []
    seen_urls = set()

    for page_url in SOURCE_PAGES:
        listing_html = fetch_html(session, page_url)
        for article_url, title in extract_links_from_listing(listing_html, page_url):
            if article_url in seen_urls:
                continue
            if not matches_route(title):
                continue

            article_html = fetch_html(session, article_url)
            summary = extract_summary(article_html)
            combined_text = f"{title} {summary}"
            if not matches_route(combined_text):
                continue

            results.append(
                OfferItem(
                    title=title,
                    url=article_url,
                    source=page_url,
                    published_at=extract_published_at(article_html),
                    summary=summary,
                )
            )
            seen_urls.add(article_url)

    return results


def build_report(items: list[OfferItem]) -> str:
    run_time = datetime.now(SAO_PAULO_TZ).strftime("%d/%m/%Y %H:%M")
    lines = [
        f"Monitor Goiania executado em {run_time}",
        "Escopo: ofertas e conteudos publicos sobre voos para Goiania saindo de Sao Paulo ou Campinas",
        "",
    ]

    if not items:
        lines.append("Nenhum conteudo relevante foi encontrado nas fontes monitoradas nesta execucao.")
        lines.append("Fontes verificadas: Melhores Destinos e Passageiro de Primeira.")
        return "\n".join(lines)

    lines.append(f"Itens encontrados: {len(items)}")
    for item in items:
        lines.extend(
            [
                "",
                f"Titulo: {item.title}",
                f"Publicado em: {item.published_at}",
                f"Resumo: {item.summary or 'Resumo nao encontrado'}",
                f"Link: {item.url}",
            ]
        )
    return "\n".join(lines)


def split_text(text: str, max_length: int = MAX_TELEGRAM_MESSAGE_LENGTH) -> list[str]:
    if len(text) <= max_length:
        return [text]

    chunks: list[str] = []
    current_lines: list[str] = []
    current_length = 0
    for line in text.splitlines():
        line_length = len(line) + 1
        if current_lines and current_length + line_length > max_length:
            chunks.append("\n".join(current_lines))
            current_lines = [line]
            current_length = line_length
        else:
            current_lines.append(line)
            current_length += line_length
    if current_lines:
        chunks.append("\n".join(current_lines))
    return chunks


def send_telegram_message(session: requests.Session, text: str) -> None:
    token = get_env("TELEGRAM_BOT_TOKEN")
    chat_id = get_env("TELEGRAM_CHAT_ID")
    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    for chunk in split_text(text):
        response = session.post(
            api_url,
            json={"chat_id": chat_id, "text": chunk, "disable_web_page_preview": True},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()


def main() -> int:
    session = build_session()
    items = collect_offers()
    report = build_report(items)
    send_telegram_message(session, report)
    print(f"Sent report with {len(items)} matched item(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
