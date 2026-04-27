from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
import io
import uuid

from app.db import supabase
from app.excel import build_excel
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


@app.get("/", response_class=HTMLResponse)
def root():
    return """
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>KLY – ZonaProp Scraper</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #0f1117;
      color: #e0e0e0;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 60px 20px;
    }
    .card {
      background: #1a1d27;
      border: 1px solid #2a2d3a;
      border-radius: 16px;
      padding: 48px;
      width: 100%;
      max-width: 640px;
    }
    h1 { font-size: 24px; font-weight: 700; margin-bottom: 6px; color: #fff; }
    .subtitle { font-size: 14px; color: #6b7280; margin-bottom: 36px; }
    label { font-size: 13px; color: #9ca3af; display: block; margin-bottom: 8px; }
    input[type=text] {
      width: 100%;
      padding: 12px 16px;
      background: #0f1117;
      border: 1px solid #2a2d3a;
      border-radius: 8px;
      color: #fff;
      font-size: 14px;
      outline: none;
      transition: border-color 0.2s;
    }
    input[type=text]:focus { border-color: #FFC000; }
    button {
      margin-top: 16px;
      width: 100%;
      padding: 14px;
      background: #FFC000;
      color: #000;
      font-weight: 700;
      font-size: 15px;
      border: none;
      border-radius: 8px;
      cursor: pointer;
      transition: opacity 0.2s;
    }
    button:hover { opacity: 0.9; }
    button:disabled { opacity: 0.5; cursor: not-allowed; }
    #status {
      margin-top: 28px;
      padding: 16px;
      border-radius: 8px;
      font-size: 14px;
      display: none;
    }
    .status-running { background: #1e2a1e; border: 1px solid #2d5a2d; color: #6fcf97; }
    .status-error   { background: #2a1e1e; border: 1px solid #5a2d2d; color: #eb5757; }
    .status-done    { background: #1e2420; border: 1px solid #2d5a40; color: #6fcf97; }
    .download-btn {
      display: inline-block;
      margin-top: 12px;
      padding: 10px 24px;
      background: #FFC000;
      color: #000;
      font-weight: 700;
      border-radius: 8px;
      text-decoration: none;
      font-size: 14px;
    }
    .jobs-section { margin-top: 48px; width: 100%; max-width: 640px; }
    .jobs-title { font-size: 14px; color: #6b7280; margin-bottom: 12px; }
    .job-row {
      background: #1a1d27;
      border: 1px solid #2a2d3a;
      border-radius: 8px;
      padding: 14px 16px;
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 13px;
    }
    .job-url { color: #9ca3af; max-width: 380px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .badge {
      padding: 3px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 600;
    }
    .badge-done    { background: #1e3a2a; color: #6fcf97; }
    .badge-running { background: #1e2a3a; color: #56b6f7; }
    .badge-error   { background: #3a1e1e; color: #eb5757; }
    .badge-pending { background: #2a2a1e; color: #f2c94c; }
    .dl-link { color: #FFC000; text-decoration: none; font-weight: 600; margin-left: 12px; }
  </style>
</head>
<body>
  <div class="card">
    <h1>KLY · ZonaProp Scraper</h1>
    <p class="subtitle">Pegá el link de búsqueda de ZonaProp y descargá el Excel con el valor por m²</p>

    <label>Link de búsqueda ZonaProp</label>
    <input type="text" id="urlInput" placeholder="https://www.zonaprop.com.ar/departamentos-venta-palermo.html">
    <button id="scrapeBtn" onclick="startScrape()">Buscar y descargar Excel</button>

    <div id="status"></div>
  </div>

  <div class="jobs-section">
    <p class="jobs-title">Búsquedas recientes</p>
    <div id="jobsList"></div>
  </div>

  <script>
    let pollInterval = null;

    async function startScrape() {
      const url = document.getElementById('urlInput').value.trim();
      if (!url) return;

      const btn = document.getElementById('scrapeBtn');
      btn.disabled = true;
      btn.textContent = 'Iniciando...';
      showStatus('running', 'Scrapeando ZonaProp, esto puede tardar unos minutos...');

      const res = await fetch('/scrape', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
      });

      if (!res.ok) {
        const err = await res.json();
        showStatus('error', 'Error: ' + (err.detail || 'algo salió mal'));
        btn.disabled = false;
        btn.textContent = 'Buscar y descargar Excel';
        return;
      }

      const { job_id } = await res.json();
      btn.textContent = 'Scrapeando...';
      pollJob(job_id);
    }

    function pollJob(job_id) {
      if (pollInterval) clearInterval(pollInterval);
      pollInterval = setInterval(async () => {
        const res = await fetch('/jobs/' + job_id);
        const job = await res.json();

        if (job.status === 'done') {
          clearInterval(pollInterval);
          showStatus('done',
            `✓ ${job.total_properties} propiedades encontradas.
            <br><a class="download-btn" href="/jobs/${job_id}/excel" download>
              ⬇ Descargar Excel
            </a>`
          );
          document.getElementById('scrapeBtn').disabled = false;
          document.getElementById('scrapeBtn').textContent = 'Buscar y descargar Excel';
          loadJobs();
        } else if (job.status === 'error') {
          clearInterval(pollInterval);
          showStatus('error', 'Error: ' + job.error_msg);
          document.getElementById('scrapeBtn').disabled = false;
          document.getElementById('scrapeBtn').textContent = 'Buscar y descargar Excel';
        }
      }, 10000);
    }

    function showStatus(type, msg) {
      const el = document.getElementById('status');
      el.className = 'status-' + type;
      el.innerHTML = msg;
      el.style.display = 'block';
    }

    async function loadJobs() {
      const res = await fetch('/jobs');
      const jobs = await res.json();
      const el = document.getElementById('jobsList');
      if (!jobs.length) { el.innerHTML = '<p style="color:#6b7280;font-size:13px">Sin búsquedas todavía</p>'; return; }
      el.innerHTML = jobs.slice(0, 10).map(j => {
        const badge = `<span class="badge badge-${j.status}">${j.status}</span>`;
        const dl = j.status === 'done' ? `<a class="dl-link" href="/jobs/${j.id}/excel" download>Excel</a>` : '';
        const props = j.total_properties ? `<span style="color:#6b7280;font-size:12px;margin-left:8px">${j.total_properties} prop.</span>` : '';
        return `<div class="job-row">
          <span class="job-url">${j.url}</span>
          <span style="display:flex;align-items:center">${badge}${props}${dl}</span>
        </div>`;
      }).join('');
    }

    loadJobs();
  </script>
</body>
</html>
"""


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


@app.get("/jobs/{job_id}/excel")
def download_excel(job_id: str):
    job = supabase.table("scrape_jobs") \
        .select("status, url") \
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

    excel_bytes = build_excel(result.data)

    filename = f"zonaprop_{job_id[:8]}.xlsx"
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
