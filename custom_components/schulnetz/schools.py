"""Schulnetz school directory."""

from __future__ import annotations

SCHOOL_BASE_URL = "https://schulnetz.lu.ch"

CUSTOM = "custom"

# Ordered list of (code, official name). The code is the path under
# https://schulnetz.lu.ch/<code>.
SCHOOLS: list[tuple[str, str]] = [
    # Kantonsschulen
    ("ksalp", "Kantonsschule Alpenquai Luzern"),
    ("ksber", "Kantonsschule Beromünster"),
    ("ksmus", "Kantonsschule Musegg Luzern"),
    ("ksreu", "Kantonsschule Reussbühl Luzern"),
    ("kssch", "Kantonsschule Schüpfheim"),
    ("kssee", "Kantonsschule Seetal"),
    ("kssur", "Kantonsschule Sursee"),
    ("kswil", "Kantonsschule Willisau"),
    # Schulen und Berufsbildungszentren
    ("bbzb", "Berufsbildungszentrum Bau und Gewerbe"),
    ("bbzg", "Berufsbildungszentrum Gesundheit und Soziales"),
    ("bbzn", "Berufsbildungszentrum Natur und Ernährung"),
    ("bbzw", "Berufsbildungszentrum Wirtschaft, Informatik und Technik"),
    ("fmz", "Fach- und Wirtschaftsmittelschulzentrum Luzern"),
    ("wbzlu", "Weiterbildungszentrum Luzern"),
    ("zba", "Zentrum für Brückenangebote Luzern"),
    # Andere
    ("zentrale", "Zentraler Mandant"),
]

SCHOOL_CODES: list[str] = [code for code, _ in SCHOOLS]
