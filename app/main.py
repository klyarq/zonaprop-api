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
  <title>KLY — Análisis de Mercado</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --paper:   #F0ECE4;
      --paper-2: #E8E4DC;
      --ink:     #18150F;
      --ink-2:   #4A4740;
      --ink-3:   #8C8880;
      --ink-4:   #BCB9B2;
      --yellow:  #EFE10F;
      --rule:    rgba(24,21,15,.12);
      --r:       4px;
    }

    body {
      font-family: "Inter Tight", system-ui, sans-serif;
      background: var(--paper);
      color: var(--ink);
      line-height: 1.5;
      -webkit-font-smoothing: antialiased;
      min-height: 100vh;
    }

    /* NAV */
    nav {
      position: sticky;
      top: 0;
      z-index: 100;
      height: 64px;
      background: var(--paper);
      border-bottom: 1px solid var(--rule);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 32px;
    }
    .nav-left { display: flex; align-items: center; gap: 14px; }
    .nav-logo {
      font-size: 18px;
      font-weight: 700;
      letter-spacing: -0.02em;
      color: var(--ink);
      text-decoration: none;
    }
    .nav-sep { color: var(--ink-4); font-size: 18px; }
    .nav-sub { font-size: 13px; color: var(--ink-3); letter-spacing: 0.01em; }
    .nav-tag {
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--ink-2);
      background: var(--paper-2);
      border: 1px solid var(--rule);
      border-radius: 999px;
      padding: 3px 10px;
    }

    /* LAYOUT */
    main {
      max-width: 720px;
      margin: 0 auto;
      padding: 64px 24px 80px;
    }

    .page-label {
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--ink-3);
      margin-bottom: 16px;
    }
    h1 {
      font-size: clamp(28px, 4vw, 40px);
      font-weight: 700;
      letter-spacing: -0.03em;
      line-height: 1.15;
      color: var(--ink);
      margin-bottom: 12px;
    }
    .hero-desc {
      font-size: 15px;
      color: var(--ink-2);
      max-width: 520px;
      margin-bottom: 48px;
    }

    /* FORM CARD */
    .card {
      background: #fff;
      border: 1px solid var(--rule);
      border-radius: 8px;
      padding: 32px;
      margin-bottom: 48px;
    }
    .field-label {
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: var(--ink-3);
      margin-bottom: 8px;
      display: block;
    }
    input[type=text] {
      width: 100%;
      padding: 11px 14px;
      background: var(--paper);
      border: 1px solid var(--rule);
      border-radius: var(--r);
      color: var(--ink);
      font-family: inherit;
      font-size: 14px;
      outline: none;
      transition: border-color .15s;
    }
    input[type=text]::placeholder { color: var(--ink-4); }
    input[type=text]:focus { border-color: var(--ink); }
    .hint {
      font-size: 12px;
      color: var(--ink-4);
      margin-top: 6px;
      margin-bottom: 20px;
    }
    .btn-primary {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      background: var(--ink);
      color: var(--paper);
      padding: 12px 24px;
      font-family: inherit;
      font-size: 14px;
      font-weight: 600;
      letter-spacing: 0.02em;
      border-radius: var(--r);
      border: none;
      cursor: pointer;
      transition: opacity .15s;
      width: 100%;
      justify-content: center;
    }
    .btn-primary:hover:not(:disabled) { opacity: 0.85; }
    .btn-primary:disabled { opacity: 0.45; cursor: not-allowed; }

    /* STATUS */
    #status {
      display: none;
      margin-top: 20px;
      padding: 14px 16px;
      border-radius: var(--r);
      font-size: 13px;
      line-height: 1.5;
    }
    .status-running {
      background: #FFFDE6;
      border: 1px solid #EFE10F;
      color: var(--ink-2);
    }
    .status-done {
      background: #F0FAF4;
      border: 1px solid #A8D5B5;
      color: #1a4a2a;
    }
    .status-error {
      background: #FFF0F0;
      border: 1px solid #F5BABA;
      color: #7a1a1a;
    }
    .download-link {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      margin-top: 12px;
      background: var(--ink);
      color: var(--paper);
      padding: 10px 20px;
      border-radius: var(--r);
      font-size: 13px;
      font-weight: 600;
      text-decoration: none;
      transition: opacity .15s;
    }
    .download-link:hover { opacity: 0.85; }

    /* DIVIDER */
    .divider {
      border: none;
      border-top: 1px solid var(--rule);
      margin: 0 0 32px;
    }

    /* JOBS TABLE */
    .section-label {
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--ink-3);
      margin-bottom: 16px;
    }
    .job-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 14px 0;
      border-bottom: 1px solid var(--rule);
      gap: 16px;
    }
    .job-row:last-child { border-bottom: none; }
    .job-url {
      font-size: 13px;
      color: var(--ink-2);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      flex: 1;
    }
    .job-meta { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
    .job-count { font-size: 12px; color: var(--ink-3); }
    .badge {
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.05em;
      padding: 3px 8px;
      border-radius: 999px;
    }
    .badge-done    { background: #E6F5EC; color: #1a5c32; }
    .badge-running { background: #FFFDE6; color: #7a6a00; }
    .badge-error   { background: #FFF0F0; color: #7a1a1a; }
    .badge-pending { background: var(--paper-2); color: var(--ink-3); }
    .dl-link {
      font-size: 12px;
      font-weight: 600;
      color: var(--ink);
      text-decoration: underline;
      text-underline-offset: 3px;
    }
    .empty { font-size: 13px; color: var(--ink-4); padding: 20px 0; }

    /* SPINNER */
    @keyframes spin { to { transform: rotate(360deg); } }
    .spinner {
      width: 14px; height: 14px;
      border: 2px solid var(--paper);
      border-top-color: transparent;
      border-radius: 50%;
      animation: spin .7s linear infinite;
      display: inline-block;
    }
  </style>
</head>
<body>

  <nav>
    <div class="nav-left">
      <a href="https://kly-project.vercel.app" class="nav-logo">KLY</a>
      <span class="nav-sep">|</span>
      <span class="nav-sub">Buenos Aires · AR</span>
    </div>
    <span class="nav-tag">Análisis de Mercado</span>
  </nav>

  <main>
    <p class="page-label">Herramienta interna</p>
    <h1>Búsqueda de mercado</h1>
    <p class="hero-desc">Pegá el link de búsqueda de ZonaProp para analizar las propiedades disponibles y obtener el ranking por valor de m² ponderado.</p>

    <div class="card">
      <label class="field-label">Link de búsqueda ZonaProp</label>
      <input type="text" id="urlInput"
        placeholder="https://www.zonaprop.com.ar/departamentos-venta-palermo.html">
      <p class="hint">El scraper va a recorrer todas las páginas del resultado — puede tardar 3–5 minutos.</p>
      <button class="btn-primary" id="scrapeBtn" onclick="startScrape()">
        Generar análisis →
      </button>
      <div id="status"></div>
    </div>

    <hr class="divider">

    <p class="section-label">Búsquedas recientes</p>
    <div id="jobsList"><p class="empty">Sin búsquedas todavía.</p></div>
  </main>

  <script>
    let pollInterval = null;

    async function startScrape() {
      const url = document.getElementById('urlInput').value.trim();
      if (!url) return;
      const btn = document.getElementById('scrapeBtn');
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner"></span> Iniciando...';
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
        btn.innerHTML = 'Generar análisis →';
        return;
      }
      const { job_id } = await res.json();
      btn.innerHTML = '<span class="spinner"></span> Analizando mercado...';
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
            '<strong>' + job.total_properties + ' propiedades analizadas.</strong> El Excel está ordenado por valor de m² ponderado (cubierto 100% · descubierto 30%).' +
            '<br><a class="download-link" href="/jobs/' + job_id + '/excel" download>⬇ Descargar Excel</a>'
          );
          document.getElementById('scrapeBtn').disabled = false;
          document.getElementById('scrapeBtn').innerHTML = 'Generar análisis →';
          loadJobs();
        } else if (job.status === 'error') {
          clearInterval(pollInterval);
          showStatus('error', 'Error al scrapear: ' + job.error_msg);
          document.getElementById('scrapeBtn').disabled = false;
          document.getElementById('scrapeBtn').innerHTML = 'Generar análisis →';
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
      if (!jobs.length) { el.innerHTML = '<p class="empty">Sin búsquedas todavía.</p>'; return; }
      el.innerHTML = jobs.slice(0, 10).map(j => {
        const badge = '<span class="badge badge-' + j.status + '">' + j.status + '</span>';
        const dl = j.status === 'done' ? '<a class="dl-link" href="/jobs/' + j.id + '/excel" download>Descargar</a>' : '';
        const count = j.total_properties ? '<span class="job-count">' + j.total_properties + ' prop.</span>' : '';
        const shortUrl = j.url.replace('https://www.zonaprop.com.ar/', '').replace('.html','');
        return '<div class="job-row"><span class="job-url">' + shortUrl + '</span><span class="job-meta">' + count + badge + dl + '</span></div>';
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
