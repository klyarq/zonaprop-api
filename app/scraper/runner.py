import pandas as pd
from datetime import datetime, timezone

from app.db import supabase
from app.scraper.browser import Browser
from app.scraper.scraper import Scraper


def run_scrape_job(job_id: str, url: str):
    try:
        supabase.table("scrape_jobs").update({"status": "running"}).eq("id", job_id).execute()

        base_url = url.replace(".html", "")
        browser = Browser()
        scraper = Scraper(browser, base_url)
        estates = scraper.scrap_website()

        df = pd.DataFrame(estates)

        important = ["m2_totales", "m2_cubiertos", "m2_descubiertos",
                     "ambientes", "dormitorios", "banos", "cocheras"]
        for col in important:
            if col not in df.columns:
                df[col] = None

        # Calcular valor/m²
        m2_cub  = pd.to_numeric(df["m2_cubiertos"],   errors="coerce").fillna(0)
        m2_desc = pd.to_numeric(df["m2_descubiertos"], errors="coerce").fillna(0)
        price   = pd.to_numeric(df.get("price_value"), errors="coerce")

        df["m2_ponderados"] = (m2_cub + m2_desc * 0.30).round(2)
        df["valor_x_m2"]    = (price / df["m2_ponderados"].replace(0, float("nan"))).round(0)

        # Mapeo de columnas a guardar en Supabase
        col_map = {
            "url":                  "url",
            "price_value":          "price_value",
            "price_type":           "price_type",
            "m2_cubiertos":         "m2_cubiertos",
            "m2_descubiertos":      "m2_descubiertos",
            "m2_totales":           "m2_totales",
            "m2_ponderados":        "m2_ponderados",
            "valor_x_m2":           "valor_x_m2",
            "ambientes":            "ambientes",
            "dormitorios":          "dormitorios",
            "banos":                "banos",
            "cocheras":             "cocheras",
            "location":             "location",
            "description":          "description",
            "expenses_value":       "expenses_value",
            "expenses_type":        "expenses_type",
            "POSTING_CARD_GALLERY": "estado",
        }

        records = []
        for _, row in df.iterrows():
            record = {"job_id": job_id}
            for src_col, dest_col in col_map.items():
                if src_col in df.columns:
                    val = row[src_col]
                    # Convertir NaN/None a None para JSON
                    record[dest_col] = None if pd.isna(val) else val
                else:
                    record[dest_col] = None
            records.append(record)

        if records:
            supabase.table("properties").insert(records).execute()

        supabase.table("scrape_jobs").update({
            "status": "done",
            "total_properties": len(records),
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", job_id).execute()

    except Exception as e:
        supabase.table("scrape_jobs").update({
            "status": "error",
            "error_msg": str(e),
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", job_id).execute()
        raise
