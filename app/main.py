from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
import io

from app.db import supabase
from app.excel import build_excel

app = FastAPI(title="ZonaProp API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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
      --paper: #F0ECE4; --paper-2: #E8E4DC; --ink: #18150F;
      --ink-2: #4A4740; --ink-3: #8C8880; --ink-4: #BCB9B2;
      --rule: rgba(24,21,15,.12); --r: 4px;
    }
    body { font-family: "Inter Tight", system-ui, sans-serif; background: var(--paper); color: var(--ink); line-height: 1.5; -webkit-font-smoothing: antialiased; min-height: 100vh; }
    nav { position: sticky; top: 0; z-index: 100; height: 64px; background: var(--paper); border-bottom: 1px solid var(--rule); display: flex; align-items: center; justify-content: space-between; padding: 0 32px; }
    .nav-left { display: flex; align-items: center; gap: 14px; }
    .nav-logo { font-size: 18px; font-weight: 700; letter-spacing: -0.02em; color: var(--ink); text-decoration: none; }
    .nav-sep { color: var(--ink-4); font-size: 18px; }
    .nav-sub { font-size: 13px; color: var(--ink-3); }
    .nav-tag { font-size: 11px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-2); background: var(--paper-2); border: 1px solid var(--rule); border-radius: 999px; padding: 3px 10px; }
    main { max-width: 720px; margin: 0 auto; padding: 64px 24px 80px; }
    .page-label { font-size: 11px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--ink-3); margin-bottom: 16px; }
    h1 { font-size: clamp(28px, 4vw, 40px); font-weight: 700; letter-spacing: -0.03em; line-height: 1.15; margin-bottom: 12px; }
    .hero-desc { font-size: 15px; color: var(--ink-2); max-width: 520px; margin-bottom: 48px; }
    .divider { border: none; border-top: 1px solid var(--rule); margin: 0 0 32px; }
    .section-label { font-size: 11px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--ink-3); margin-bottom: 16px; }
    .job-row { display: flex; align-items: center; justify-content: space-between; padding: 14px 0; border-bottom: 1px solid var(--rule); gap: 16px; }
    .job-row:last-child { border-bottom: none; }
    .job-url { font-size: 13px; color: var(--ink-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
    .job-meta { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
    .job-count { font-size: 12px; color: var(--ink-3); }
    .badge { font-size: 11px; font-weight: 600; letter-spacing: 0.05em; padding: 3px 8px; border-radius: 999px; }
    .badge-done { background: #E6F5EC; color: #1a5c32; }
    .dl-link { font-size: 12px; font-weight: 600; color: var(--ink); text-decoration: underline; text-underline-offset: 3px; }
    .empty { font-size: 13px; color: var(--ink-4); padding: 20px 0; }
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
    <p class="hero-desc">Resultados de análisis de ZonaProp. Cada búsqueda está ordenada por valor de m² ponderado (cubierto 100% · descubierto 30%).</p>
    <hr class="divider">
    <p class="section-label">Búsquedas recientes</p>
    <div id="jobsList"><p class="empty">Sin búsquedas todavía.</p></div>
  </main>
  <script>
    async function loadJobs() {
      const res = await fetch('/jobs');
      const jobs = await res.json();
      const el = document.getElementById('jobsList');
      const done = jobs.filter(j => j.status === 'done');
      if (!done.length) { el.innerHTML = '<p class="empty">Sin búsquedas todavía.</p>'; return; }
      el.innerHTML = done.slice(0, 20).map(j => {
        const count = j.total_properties ? '<span class="job-count">' + j.total_properties + ' prop.</span>' : '';
        const date = new Date(j.created_at).toLocaleDateString('es-AR', {day:'2-digit',month:'2-digit',year:'numeric'});
        const shortUrl = j.url.replace('https://www.zonaprop.com.ar/', '').replace('.html','');
        return '<div class="job-row"><span class="job-url" title="' + j.url + '">' + shortUrl + '</span><span class="job-meta"><span class="job-count">' + date + '</span>' + count + '<span class="badge badge-done">listo</span><a class="dl-link" href="/jobs/' + j.id + '/excel" download>Descargar</a></span></div>';
      }).join('');
    }
    loadJobs();
  </script>
</body>
</html>
"""


@app.post("/upload", status_code=201)
def upload_results(body: dict):
    from datetime import datetime, timezone
    import uuid
    url = body.get("url", "")
    records = body.get("properties", [])
    if not records:
        raise HTTPException(400, "No hay propiedades para guardar")

    job_id = str(uuid.uuid4())
    supabase.table("scrape_jobs").insert({
        "id": job_id,
        "url": url,
        "status": "done",
        "total_properties": len(records),
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }).execute()

    for r in records:
        r["job_id"] = job_id
    supabase.table("properties").insert(records).execute()

    return {"job_id": job_id, "total_properties": len(records)}


@app.get("/jobs")
def list_jobs():
    result = supabase.table("scrape_jobs") \
        .select("id, url, status, total_properties, created_at") \
        .order("created_at", desc=True) \
        .limit(50) \
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
        raise HTTPException(400, "Job todavía no terminó")

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
