#!/usr/bin/env python3
"""
Corre el scraper localmente y sube los resultados a la API.
Uso: python3 scrape_local.py <url_zonaprop>
"""
import sys
import json
import math
import requests
import pandas as pd
from app.scraper.browser import Browser
from app.scraper.scraper import Scraper

API_URL = "https://zonaprop-api.onrender.com"


def main(url: str):
    print(f"Scrapeando: {url}")
    base_url = url.replace(".html", "")
    browser = Browser()
    scraper = Scraper(browser, base_url)
    estates = scraper.scrap_website()

    if not estates:
        print("No se encontraron propiedades.")
        return

    df = pd.DataFrame(estates)
    for col in ["m2_totales", "m2_cubiertos", "m2_descubiertos", "ambientes", "dormitorios", "banos", "cocheras"]:
        if col not in df.columns:
            df[col] = None

    m2_cub  = pd.to_numeric(df["m2_cubiertos"],   errors="coerce").fillna(0)
    m2_desc = pd.to_numeric(df["m2_descubiertos"], errors="coerce").fillna(0)
    price   = pd.to_numeric(df.get("price_value"), errors="coerce")
    df["m2_ponderados"] = (m2_cub + m2_desc * 0.30).round(2)
    df["valor_x_m2"]    = (price / df["m2_ponderados"].replace(0, float("nan"))).round(0)

    col_map = {
        "url": "url", "price_value": "price_value", "price_type": "price_type",
        "m2_cubiertos": "m2_cubiertos", "m2_descubiertos": "m2_descubiertos",
        "m2_totales": "m2_totales", "m2_ponderados": "m2_ponderados",
        "valor_x_m2": "valor_x_m2", "ambientes": "ambientes",
        "dormitorios": "dormitorios", "banos": "banos", "cocheras": "cocheras",
        "location": "location", "description": "description",
        "expenses_value": "expenses_value", "expenses_type": "expenses_type",
        "POSTING_CARD_GALLERY": "estado",
    }
    float_cols   = {"price_value", "m2_cubiertos", "m2_descubiertos", "m2_totales",
                    "m2_ponderados", "valor_x_m2", "expenses_value"}
    integer_cols = {"ambientes", "dormitorios", "banos", "cocheras"}

    records = []
    for _, row in df.iterrows():
        record = {}
        for src, dest in col_map.items():
            if src not in df.columns:
                record[dest] = None
                continue
            val = row[src]
            if val is None or (isinstance(val, float) and math.isnan(val)):
                val = None
            elif isinstance(val, str) and val.strip() == "":
                val = None
            elif dest in float_cols and val is not None:
                try: val = float(val)
                except: val = None
            elif dest in integer_cols and val is not None:
                try: val = int(float(val))
                except: val = None
            record[dest] = val
        records.append(record)

    print(f"Subiendo {len(records)} propiedades a la API...")
    res = requests.post(f"{API_URL}/upload", json={"url": url, "properties": records})
    res.raise_for_status()
    data = res.json()
    job_id = data["job_id"]

    print(f"\n✓ Listo. {len(records)} propiedades subidas.")
    print(f"Descargá el Excel en:\n  {API_URL}/jobs/{job_id}/excel\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 scrape_local.py <url_zonaprop>")
        sys.exit(1)
    main(sys.argv[1])
