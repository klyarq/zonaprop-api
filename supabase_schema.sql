-- Ejecutar esto en el SQL Editor de Supabase

create table scrape_jobs (
  id            uuid primary key default gen_random_uuid(),
  url           text not null,
  status        text not null default 'pending',  -- pending | running | done | error
  total_properties int,
  error_msg     text,
  created_at    timestamptz not null default now(),
  finished_at   timestamptz
);

create table properties (
  id              uuid primary key default gen_random_uuid(),
  job_id          uuid not null references scrape_jobs(id) on delete cascade,
  url             text,
  price_value     numeric,
  price_type      text,
  m2_cubiertos    numeric,
  m2_descubiertos numeric,
  m2_totales      numeric,
  m2_ponderados   numeric,
  valor_x_m2      numeric,
  ambientes       integer,
  dormitorios     integer,
  banos           integer,
  cocheras        integer,
  location        text,
  description     text,
  expenses_value  numeric,
  expenses_type   text,
  estado          text,
  created_at      timestamptz not null default now()
);

-- Índices útiles para filtrar y ordenar
create index on properties (job_id);
create index on properties (valor_x_m2);

-- Row Level Security: solo usuarios autenticados de tu proyecto ven los datos
alter table scrape_jobs enable row level security;
alter table properties   enable row level security;

create policy "Authenticated users can read jobs"
  on scrape_jobs for select
  using (auth.role() = 'authenticated');

create policy "Authenticated users can read properties"
  on properties for select
  using (auth.role() = 'authenticated');

-- El service_key de Railway puede escribir sin restricciones (bypasses RLS)
