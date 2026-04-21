import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Iterable

import requests


REQUEST_TIMEOUT = 30
SAO_PAULO_TZ = timezone(timedelta(hours=-3))
ORIGINS = {
    "GRU": "Sao Paulo / Guarulhos",
    "CGH": "Sao Paulo / Congonhas",
    "VCP": "Campinas / Viracopos",
}
DESTINATION = "GYN"
DESTINATION_LABEL = "Goiania"
DEFAULT_MAX_RESULTS_PER_ORIGIN = 3
DEFAULT_DEAL_THRESHOLD_BRL = Decimal("550")
MAX_TELEGRAM_MESSAGE_LENGTH = 3800


@dataclass(frozen=True)
class FareOption:
    origin_code: str
    origin_label: str
    destination_code: str
    departure_date: str
    return_date: str | None
    total_brl: Decimal
    one_way: bool
    deep_link: str | None

    @property
    def trip_type_label(self) -> str:
        return "Ida" if self.one_way else "Ida e volta"


def get_env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or not str(value).strip():
        raise RuntimeError(f"Environment variable {name} is required.")
    return str(value).strip()


def get_api_base() -> str:
    env = os.getenv("AMADEUS_ENV", "test").strip().lower()
    if env == "production":
        return "https://api.amadeus.com"
    return "https://test.api.amadeus.com"


def get_access_token(session: requests.Session) -> str:
    client_id = get_env("AMADEUS_CLIENT_ID")
    client_secret = get_env("AMADEUS_CLIENT_SECRET")
    response = session.post(
        f"{get_api_base()}/v1/security/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    return payload["access_token"]


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": "goiania-flight-monitor/1.0"})
    return session


def parse_decimal(value: str) -> Decimal:
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError) as exc:
        raise RuntimeError(f"Invalid decimal value: {value}") from exc


def search_round_trip_fares(session: requests.Session, token: str, origin_code: str) -> list[FareOption]:
    start_date = date.today() + timedelta(days=1)
    end_date = start_date + timedelta(days=89)
    response = session.get(
        f"{get_api_base()}/v1/shopping/flight-dates",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "origin": origin_code,
            "destination": DESTINATION,
            "departureDate": f"{start_date.isoformat()},{end_date.isoformat()}",
            "oneWay": "false",
            "duration": "2,7",
            "currencyCode": "BRL",
            "nonStop": "false",
            "viewBy": "DATE",
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()

    options: list[FareOption] = []
    for item in payload.get("data", []):
        price = item.get("price", {}).get("total")
        departure_date = item.get("departureDate")
        return_date = item.get("returnDate")
        if not price or not departure_date:
            continue
        options.append(
            FareOption(
                origin_code=origin_code,
                origin_label=ORIGINS[origin_code],
                destination_code=DESTINATION,
                departure_date=departure_date,
                return_date=return_date,
                total_brl=parse_decimal(price),
                one_way=False,
                deep_link=item.get("links", {}).get("flightOffers"),
            )
        )

    options.sort(key=lambda item: item.total_brl)
    max_results = int(os.getenv("MAX_RESULTS_PER_ORIGIN", str(DEFAULT_MAX_RESULTS_PER_ORIGIN)))
    return options[:max_results]


def format_money(value: Decimal) -> str:
    normalized = f"{value:.2f}"
    integer_part, decimal_part = normalized.split(".")
    integer_with_separator = ""
    for index, char in enumerate(reversed(integer_part)):
        if index and index % 3 == 0:
            integer_with_separator = "." + integer_with_separator
        integer_with_separator = char + integer_with_separator
    return f"R$ {integer_with_separator},{decimal_part}"


def format_date(value: str) -> str:
    parsed = datetime.strptime(value, "%Y-%m-%d")
    return parsed.strftime("%d/%m/%Y")


def build_report(options_by_origin: dict[str, list[FareOption]]) -> str:
    run_time = datetime.now(SAO_PAULO_TZ).strftime("%d/%m/%Y %H:%M")
    deal_threshold = parse_decimal(os.getenv("DEAL_THRESHOLD_BRL", str(DEFAULT_DEAL_THRESHOLD_BRL)))
    all_options = [option for options in options_by_origin.values() for option in options]

    lines = [
        f"Monitor de passagens para {DESTINATION_LABEL} executado em {run_time}",
        "Janela pesquisada: proximos 90 dias",
        "",
    ]

    if not all_options:
        lines.append("Nenhuma tarifa foi encontrada nesta execucao.")
        return "\n".join(lines)

    best_option = min(all_options, key=lambda item: item.total_brl)
    lines.extend(
        [
            "Melhor tarifa do momento:",
            f"{best_option.origin_code} -> {best_option.destination_code} | {best_option.trip_type_label} | {format_money(best_option.total_brl)}",
            f"Datas: {format_date(best_option.departure_date)} a {format_date(best_option.return_date)}",
        ]
    )
    if best_option.total_brl <= deal_threshold:
        lines.append(f"Alerta: abaixo do limite configurado de {format_money(deal_threshold)}")
    if best_option.deep_link:
        lines.append(f"Link: {best_option.deep_link}")

    for origin_code, options in options_by_origin.items():
        lines.extend(["", f"Top tarifas saindo de {ORIGINS[origin_code]}:"])
        if not options:
            lines.append("Nenhuma tarifa encontrada.")
            continue
        for option in options:
            lines.append(
                f"- {format_money(option.total_brl)} | {format_date(option.departure_date)} a {format_date(option.return_date)}"
            )
            if option.deep_link:
                lines.append(f"  {option.deep_link}")

    return "\n".join(lines)


def split_text(text: str, max_length: int = MAX_TELEGRAM_MESSAGE_LENGTH) -> list[str]:
    if len(text) <= max_length:
        return [text]

    chunks: list[str] = []
    current = []
    current_length = 0
    for line in text.splitlines():
        line_length = len(line) + 1
        if current and current_length + line_length > max_length:
            chunks.append("\n".join(current))
            current = [line]
            current_length = line_length
            continue
        current.append(line)
        current_length += line_length
    if current:
        chunks.append("\n".join(current))
    return chunks


def send_telegram_message(session: requests.Session, text: str) -> None:
    token = get_env("TELEGRAM_BOT_TOKEN")
    chat_id = get_env("TELEGRAM_CHAT_ID")
    api_url = f"https://api.telegram.org/bot{token}/sendMessage"

    for chunk in split_text(text):
        response = session.post(
            api_url,
            json={
                "chat_id": chat_id,
                "text": chunk,
                "disable_web_page_preview": True,
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()


def monitor() -> dict[str, list[FareOption]]:
    session = build_session()
    token = get_access_token(session)
    options_by_origin: dict[str, list[FareOption]] = {}
    for origin_code in ORIGINS:
        options_by_origin[origin_code] = search_round_trip_fares(session, token, origin_code)
    return options_by_origin


def main() -> int:
    options_by_origin = monitor()
    session = build_session()
    report = build_report(options_by_origin)
    send_telegram_message(session, report)
    total_options = sum(len(options) for options in options_by_origin.values())
    print(f"Sent report with {total_options} fare options.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

