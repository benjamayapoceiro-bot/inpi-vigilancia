-- Cartera de marcas a vigilar (las tuyas + las de tus clientes/estudios)
create table marcas_vigiladas (
    id uuid primary key default gen_random_uuid(),
    nombre text not null,
    clase int not null,
    cliente text,
    propietario_user_id uuid references auth.users(id),
    created_at timestamptz default now()
);

-- Registro de boletines ya procesados (evita reprocesar)
create table boletines_procesados (
    numero_boletin text primary key,
    fecha_boletin date,
    tipo text,  -- 'MARCAS NUEVAS'
    actas_encontradas int,
    procesado_at timestamptz default now()
);

-- Alertas generadas por el matcher
create table alertas (
    id uuid primary key default gen_random_uuid(),
    marca_vigilada_id uuid references marcas_vigiladas(id),
    acta_nueva text not null,
    denominacion_nueva text,
    clase int,
    titular_nuevo jsonb,
    boletin_numero text references boletines_procesados(numero_boletin),
    similitud_ortografica numeric,
    similitud_fonetica numeric,
    similitud_score numeric,
    revisada boolean default false,
    created_at timestamptz default now()
);

create index idx_alertas_marca on alertas(marca_vigilada_id);
create index idx_alertas_revisada on alertas(revisada);

-- RLS: cada usuario ve solo su cartera y sus alertas
alter table marcas_vigiladas enable row level security;
alter table alertas enable row level security;

create policy "usuarios ven su propia cartera"
    on marcas_vigiladas for all
    using (propietario_user_id = auth.uid());

create policy "usuarios ven alertas de su cartera"
    on alertas for select
    using (
        marca_vigilada_id in (
            select id from marcas_vigiladas where propietario_user_id = auth.uid()
        )
    );
