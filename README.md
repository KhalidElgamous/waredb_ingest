# waredb_ingest

Data-warehouse layer for a **multimodal RAG platform on a hybrid
vector-lakehouse**: SQLAlchemy models, Alembic migrations and small session
helpers.

The warehouse stores the *metadata and measures* of the platform as star
schemas: what was ingested, how it was chunked and embedded, what users asked,
what was retrieved, how good the answers were and what it all cost. The heavy
payload stays where it belongs: raw files and chunk text in the lakehouse
(Delta / Iceberg / Hudi), vectors in the vector store. Rows here link to them
through `uri`, `chunk_uid` and `vector_id`.

Connection settings come from a single environment variable, so the same code
runs against SQLite, PostgreSQL, MySQL or anything else SQLAlchemy supports.

## Requirements

- Python 3.10+
- A database reachable through a SQLAlchemy URL (SQLite works with no extra
  driver; MySQL needs 8.0.13+)

## Project layout

```
waredb_ingest/
├── engine.py              # SQLAlchemy engine built from SQL_ALCHEMY_CONN
├── session.py             # thread-local Session, create_session(), @provide_session
├── env.py                 # Alembic environment (offline and online runners)
├── script.py.mako         # Alembic template for new revisions
├── models/
│   ├── __init__.py        # re-exports Base and every model (Alembic imports from here)
│   ├── base.py            # declarative Base, shared MetaData and naming convention
│   ├── users.py           # User model and query helpers
│   └── datawarehouse/
│       ├── common.py          # BigInt, enum_type(), CreatedAtMixin
│       ├── enums.py           # enumerations used by the RAG tables
│       ├── dimensions.py      # Day, Month; DatetimeDim, LocalisationDim
│       ├── rag_dimensions.py  # 12 RAG dimensions
│       └── facts.py           # 10 fact tables
├── versions/              # Alembic revisions (schema + seed data)
├── requirements.txt
└── README.md
```

## Getting started

### 1. Install

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.txt` ends with commented-out database drivers. Uncomment the one
that matches your database (for example `psycopg2-binary` for PostgreSQL).

### 2. Configure the database

Create a `.env` file (it is git-ignored) with your connection URL:

```bash
# SQLite, no driver needed
SQL_ALCHEMY_CONN=sqlite:///waredb.db

# PostgreSQL
# SQL_ALCHEMY_CONN=postgresql+psycopg2://user:password@localhost:5432/waredb
```

Always spell the driver in the URL (`postgresql+psycopg2://`): SQLAlchemy 2.1
maps a bare `postgresql://` to psycopg 3, which is a different package.

`SQL_ALCHEMY_CONN` is required: importing the package without it raises a
`KeyError`, and importing the models creates the engine, so the database driver
must be installed even for `alembic ... --sql`. A variable that is already set
in the environment takes precedence over `.env`.

A relative SQLite path such as `waredb.db` is resolved from the current working
directory, so run `alembic` and your own code from the same place (or use an
absolute path: `sqlite:////absolute/path/to/waredb.db`).

### 3. Apply the migrations

```bash
alembic upgrade head
```

This creates every table and seeds the stable lookups (`modality_dim` with 7
modalities, `metric_dim` with 14 evaluation metrics).

Alembic needs an `alembic.ini` that points at this directory. If you don't have
one yet, `alembic init` generates it; then make sure these two settings are
present (the logging sections that `alembic init` writes must stay, because
`env.py` calls `fileConfig`):

```ini
[alembic]
script_location = %(here)s
prepend_sys_path = %(here)s/..
```

This assumes `alembic.ini` sits next to `env.py` and the project folder is named
`waredb_ingest`. `env.py` reads the URL from `SQL_ALCHEMY_CONN`, so no
`sqlalchemy.url` is needed in the ini file.

Handy commands:

```bash
alembic current                      # revision the database is at
alembic history                      # all revisions
alembic upgrade head --sql           # print the SQL instead of running it
alembic downgrade -1                 # undo the latest revision
alembic check                        # fail if the models and the DB have drifted apart
```

Downgrading past the seed revision fails while facts still reference the seeded
rows. That is intentional.

## Schema

Four star schemas share the dimensions. Every fact also points to `datetime_dim`
(not drawn below), and `model_dim` plays several roles (embedding model,
generator, reranker, judge).

```mermaid
erDiagram
    source_dim ||--o{ document_dim : "has"
    modality_dim ||--o{ document_dim : "typed as"
    pipeline_dim ||--o{ pipeline_run_fact : "runs"
    pipeline_run_fact ||--o{ ingestion_fact : "processes"
    document_dim ||--o{ ingestion_fact : "ingested"
    ingestion_fact ||--o{ chunk_fact : "produces"
    document_dim ||--o{ chunk_fact : "split into"
    chunking_strategy_dim ||--o{ chunk_fact : "by"
    lakehouse_table_dim ||--o{ chunk_fact : "stored in"
    chunk_fact ||--o{ embedding_fact : "embedded as"
    model_dim ||--o{ embedding_fact : "using"
    vector_index_dim ||--o{ embedding_fact : "indexed in"
    user ||--o{ query_fact : "asks"
    localisation_dim ||--o{ query_fact : "from"
    retrieval_strategy_dim ||--o{ query_fact : "retrieved by"
    prompt_template_dim ||--o{ query_fact : "prompted with"
    model_dim ||--o{ query_fact : "answered by"
    query_fact ||--o{ retrieval_hit_fact : "returns"
    chunk_fact ||--o{ retrieval_hit_fact : "hit"
    query_fact ||--o{ feedback_fact : "rated by"
    eval_dataset_dim ||--o{ evaluation_result_fact : "evaluated on"
    metric_dim ||--o{ evaluation_result_fact : "measured by"
    lakehouse_table_dim ||--o{ lakehouse_snapshot_fact : "snapshot of"
    vector_index_dim ||--o{ vector_index_snapshot_fact : "snapshot of"
```

### Dimensions

| Table                    | What it describes                                                               |
|--------------------------|---------------------------------------------------------------------------------|
| `datetime_dim`           | Calendar and clock slice (weekday, day of month, month, year, hour, minute)     |
| `localisation_dim`       | Latitude / longitude of a location                                              |
| `user`                   | Application user (also the user dimension of the facts)                         |
| `modality_dim`           | Content modality: TEXT, IMAGE, AUDIO, VIDEO, TABLE, CODE, DOCUMENT (seeded)     |
| `source_dim`             | System documents come from (object store, web crawl, SaaS connector, ...)       |
| `document_dim`           | Document or media asset, versioned as SCD type 2                                |
| `model_dim`              | Any model: embedding, LLM, vision-language, reranker, OCR, speech-to-text       |
| `chunking_strategy_dim`  | Chunking method, unit, size and overlap, per modality                           |
| `retrieval_strategy_dim` | Dense / sparse / hybrid retrieval, fusion method, top-k, reranker               |
| `vector_index_dim`       | Vector-store collection: engine, ANN index type, metric, quantization           |
| `lakehouse_table_dim`    | Lakehouse table: format (Delta / Iceberg / Hudi), medallion layer, location     |
| `pipeline_dim`           | Pipeline name and version, orchestrator, stage                                  |
| `prompt_template_dim`    | Versioned prompt template (the text stays in git; its hash is stored)           |
| `metric_dim`             | Evaluation metric: recall@k, nDCG, faithfulness, latency, cost, ... (seeded)    |
| `eval_dataset_dim`       | Versioned evaluation ("golden") dataset                                         |

### Facts

| Table                        | Grain                                           | Type                 |
|------------------------------|-------------------------------------------------|----------------------|
| `pipeline_run_fact`          | one pipeline run                                | accumulating snapshot|
| `ingestion_fact`             | one document version per run                    | transaction          |
| `chunk_fact`                 | one chunk (metadata only)                       | transaction          |
| `embedding_fact`             | one chunk x embedding model x vector index      | transaction          |
| `query_fact`                 | one RAG request                                 | transaction          |
| `retrieval_hit_fact`         | one query x retrieved chunk, with all scores    | transaction          |
| `feedback_fact`              | one feedback event on an answer                 | transaction          |
| `evaluation_result_fact`     | one run x sample x metric                       | transaction          |
| `lakehouse_snapshot_fact`    | one lakehouse table per snapshot time           | periodic snapshot    |
| `vector_index_snapshot_fact` | one vector index per snapshot time              | periodic snapshot    |

Every column of every table is documented in the docstring of its model class
(`models/datawarehouse/`).

### Design notes

- **Keys and time.** Facts use 64-bit surrogate keys (`BigInt`, degraded to
  `INTEGER` on SQLite, which only auto-numbers that type). Each fact has a
  `datetime_id` for calendar slicing and an exact timestamp (`event_at`,
  `snapshot_at` or `started_at`) for ordering and partitioning.
- **Enums are `VARCHAR`.** The RAG enums are stored as plain strings with no
  CHECK constraint, so adding a modality, engine or status needs no schema
  change and no `ALTER TYPE`. Python still rejects unknown values.
- **Named constraints.** A naming convention on `Base` gives every key, unique
  constraint and index a stable name (`fk_chunk_fact_document_id`, ...), so they
  can be altered or dropped by name on any database.
- **Linking to the lakehouse and vector store.** `chunk_fact.chunk_uid` is meant
  to be the same id as the chunk row in the lakehouse and the point id in the
  vector store; `embedding_fact.vector_id` and `document_dim.uri` complete the
  links.
- **Privacy.** `query_fact.query_text` is optional. Store only `query_hash` if
  queries must not be retained.
- **At scale.** The largest tables are `chunk_fact`, `embedding_fact`,
  `retrieval_hit_fact` and `query_fact`. Partition them by their timestamp column
  (database-specific, so not done in the migrations), add composite indexes for
  your own query patterns, and consider dropping the foreign-key constraints
  (keeping the indexes) on bulk-loaded tables. The same schema also works as the
  DDL contract for the equivalent Delta / Iceberg tables.

## Usage

Imports are package-relative, so the project folder must be importable as
`waredb_ingest`: run from its parent directory, or put that directory on
`PYTHONPATH`.

```python
from waredb_ingest.models import User, DatetimeDim, LocalisationDim
from waredb_ingest.models.datawarehouse.dimensions import Day, Month
from waredb_ingest.session import create_session, provide_session

# Built-in helpers manage their own session (commit on success, rollback on error)
User.create("alice")
User.get(1)          # -> ('alice',)   a one-column row, or None if not found
User.all()           # -> [<User>, ...]

# Several writes in one transaction
with create_session() as session:
    session.add(LocalisationDim(lat=33.5731, long=-7.5898))
    session.add(DatetimeDim(day=Day.WEDNESDAY, day_of_month=25, month=Month.NOVEMBER,
                            year=2026, hour=12, minute=22))

# Your own functions can receive a session the same way
@provide_session
def count_users(session=None):
    return session.query(User).count()

count_users()                      # opens and commits its own session
count_users(session=my_session)    # uses yours; you commit and close it
```

Recording a RAG request:

```python
import hashlib
from datetime import datetime, timezone
from decimal import Decimal

from waredb_ingest.models import DatetimeDim, QueryFact
from waredb_ingest.models.datawarehouse.dimensions import Day, Month
from waredb_ingest.models.datawarehouse.enums import Channel, RequestStatus
from waredb_ingest.session import create_session

question = "What changed in the 2026 annual report?"

with create_session() as session:
    when = DatetimeDim(day=Day.WEDNESDAY, day_of_month=25, month=Month.NOVEMBER,
                       year=2026, hour=19, minute=0)
    session.add(when)
    session.flush()                              # assigns when.id

    session.add(QueryFact(
        request_uid="req-0001",                  # trace id from your application
        datetime_id=when.id,
        event_at=datetime.now(timezone.utc),
        channel=Channel.WEB,
        status=RequestStatus.SUCCESS,
        query_hash=hashlib.sha256(question.encode()).hexdigest(),
        total_ms=1500,
        cost_usd=Decimal("0.0123"),
    ))
```

Analytics are plain SQL over the stars:

```sql
-- Ingestion health per source in a month
SELECT s.name AS source, i.status, COUNT(*) AS documents, SUM(i.bytes_in) AS bytes_in
FROM ingestion_fact i
JOIN source_dim s   ON s.id = i.source_id
JOIN datetime_dim d ON d.id = i.datetime_id
WHERE d.year = 2026 AND d.month = 'NOVEMBER'
GROUP BY s.name, i.status;

-- Compare retrieval strategies on latency, cost and user satisfaction
SELECT rs.name AS strategy, COUNT(DISTINCT q.id) AS queries,
       AVG(q.total_ms) AS avg_latency_ms,
       AVG(CASE WHEN f.sentiment = 'UP' THEN 1.0 WHEN f.sentiment = 'DOWN' THEN 0.0 END) AS thumbs_up_rate
FROM query_fact q
JOIN retrieval_strategy_dim rs ON rs.id = q.retrieval_strategy_id
LEFT JOIN feedback_fact f      ON f.query_id = q.id
GROUP BY rs.name;

-- Offline quality per generator model on a golden dataset
SELECT m.code AS metric, g.name AS generator, AVG(e.metric_value) AS avg_value
FROM evaluation_result_fact e
JOIN metric_dim m        ON m.id = e.metric_id
JOIN model_dim g         ON g.id = e.generator_model_id
JOIN eval_dataset_dim ds ON ds.id = e.eval_dataset_id
WHERE ds.name = 'golden' AND ds.version = '1'
GROUP BY m.code, g.name;
```

Things worth knowing:

- Pass `session` **by keyword**. `User.get(1, my_session)` raises a
  `TypeError`; use `User.get(1, session=my_session)`.
- `Session` is thread-local, so nested `create_session()` blocks in one thread
  share the same underlying session.
- Sessions use `autoflush=False` and `expire_on_commit=False`: nothing is
  written until a flush or commit, and returned objects stay readable after the
  session is closed.
- `User.create` returns `None`; query the user again if you need its `id`.
- `DatetimeDim.day` is the day of the **week**; use `day_of_month` for the
  calendar day.

## Adding a model

1. Define it under `models/` on top of `Base` (from `models/base.py`).
2. Import and export it in `models/__init__.py`. Alembic autogenerate only sees
   models that are imported there.
3. Generate and review the migration, then apply it:

   ```bash
   alembic revision --autogenerate -m "create something"
   alembic upgrade head
   ```

   Autogenerate renders defaults using the dialect it runs on, so check
   boolean and timestamp defaults before committing: write `sa.true()`,
   `sa.false()` and `sa.func.now()` instead of `sa.text('1')`, `sa.text('0')` or
   `sa.text('(CURRENT_TIMESTAMP)')`. The latter break on PostgreSQL and older
   MySQL.
