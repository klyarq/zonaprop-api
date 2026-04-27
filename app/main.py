from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid

from app.db import supabase
from app.scraper.runner import run_scrape_job

app = FastAPI(title="ZonaProp API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ScrapeRequest(BaseModel):
    url: str


@app.get("/")
def root():
    return {"status": "ok", "service": "zonaprop-api"}


@app.post("/scrape", status_code=202)
def start_scrape(body: ScrapeRequest, background_tasks: BackgroundTasks):
    if "zonaprop.com.ar" not in body.url:
        raise HTTPException(400, "URL debe ser de zonaprop.com.ar")

    job_id = str(uuid.uuid4())

    supabase.table("scrape_jobs").insert({
        "id": job_id,
        "url": body.url,
        "status": "pending",
    }).execute()

    background_tasks.add_task(run_scrape_job, job_id, body.url)

    return {"job_id": job_id, "status": "pending"}


@app.get("/jobs")
def list_jobs():
    result = supabase.table("scrape_jobs") \
        .select("id, url, status, total_properties, error_msg, created_at, finished_at") \
        .order("created_at", desc=True) \
        .limit(50) \
        .execute()
    return result.data


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    result = supabase.table("scrape_jobs") \
        .select("*") \
        .eq("id", job_id) \
        .single() \
        .execute()
    if not result.data:
        raise HTTPException(404, "Job no encontrado")
    return result.data


@app.get("/jobs/{job_id}/results")
def get_results(job_id: str):
    job = supabase.table("scrape_jobs") \
        .select("status") \
        .eq("id", job_id) \
        .single() \
        .execute()
    if not job.data:
        raise HTTPException(404, "Job no encontrado")
    if job.data["status"] != "done":
        raise HTTPException(400, f"Job todavía en estado: {job.data['status']}")

    result = supabase.table("properties") \
        .select("*") \
        .eq("job_id", job_id) \
        .order("valor_x_m2", desc=False) \
        .execute()
    return result.data
