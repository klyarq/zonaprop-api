"""Corre el scraper y sube resultados a la API. Usado por GitHub Actions."""
import os
import math
import requests
import pandas as pd
from app.scraper.browser import Browser
from app.scraper.scraper import Scraper

API_URL = os.environ["API_URL"]
url     = os.environ["ZONAPROP_URL"]
job_id  = os.environ["JOB_ID"]


def to_float(val):
    if val is None or (isinstance(val, float) and math.isnan(val)): return None
    if isinstance(val, str) and val.strip() == "": return None
    try: return float(val)
    except: return None

def to_int(val):
    f = to_float(val)
    return None if f is None else int(f)


def main():
    print(f"Scrapeando: {url}")
    base_url = url.replace(".html", "")
    browser  = Browser()
    scraper  = Scraper(browser, base_url)
    estates  = scraper.scrap_website()
    print(f"Propiedades encontradas: {len(estates)}")

    if not estates:
        requests.post(f"{API_URL}/jobs/{job_id}/fail",
                      json={"error": "No se encontraron propiedades"})
        return

    df = pd.DataFrame(estates)
    for col in ["m2_totales","m2_cubiertos","m2_descubiertos","ambientes","dormitorios","banos","cocheras"]:
        if col not in df.columns: df[col] = None

    m2_cub  = pd.to_numeric(df["m2_cubiertos"],   errors="coerce").fillna(0)
    m2_desc = pd.to_numeric(df["m2_descubiertos"], errors="coerce").fillna(0)
    price   = pd.to_numeric(df.get("price_value"), errors="coerce")
    df["m2_ponderados"] = (m2_cub + m2_desc * 0.30).round(2)
    df["valor_x_m2"]    = (price / df["m2_ponderados"].replace(0, float("nan"))).round(0)

    col_map = {
        "url":"url","price_value":"price_value","price_type":"price_type",
        "m2_cubiertos":"m2_cubiertos","m2_descubiertos":"m2_descubiertos",
        "m2_totales":"m2_totales","m2_ponderados":"m2_ponderados",
        "valor_x_m2":"valor_x_m2","ambientes":"ambientes",
        "dormitorios":"dormitorios","banos":"banos","cocheras":"cocheras",
        "location":"location","description":"description",
        "expenses_value":"expenses_value","expenses_type":"expenses_type",
        "POSTING_CARD_GALLERY":"estado",
    }
    float_cols   = {"price_value","m2_cubiertos","m2_descubiertos","m2_totales","m2_ponderados","valor_x_m2","expenses_value"}
    integer_cols = {"ambientes","dormitorios","banos","cocheras"}

    records = []
    for _, row in df.iterrows():
        record = {"job_id": job_id}
        for src, dest in col_map.items():
            val = row[src] if src in df.columns else None
            if dest in float_cols:   val = to_float(val)
            elif dest in integer_cols: val = to_int(val)
            elif val is not None and isinstance(val, float) and math.isnan(val): val = None
            elif isinstance(val, str) and val.strip() == "": val = None
            record[dest] = val
        records.append(record)

    print(f"Subiendo {len(records)} propiedades...")
    res = requests.post(f"{API_URL}/jobs/{job_id}/complete",
                        json={"properties": records})
    res.raise_for_status()
    print(f"✓ Listo. Excel disponible en: {API_URL}/jobs/{job_id}/excel")


if __name__ == "__main__":
    main()
