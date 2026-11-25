"""Dimension tables for the multimodal RAG / hybrid vector-lakehouse warehouse.

These describe *what* the fact tables measure: the content (``source_dim``,
``document_dim``, ``modality_dim``), the models and configurations involved
(``model_dim``, ``chunking_strategy_dim``, ``retrieval_strategy_dim``,
``prompt_template_dim``), where data physically lives (``vector_index_dim``,
``lakehouse_table_dim``), who ran what (``pipeline_dim``) and how quality is
judged (``metric_dim``, ``eval_dataset_dim``).

Together with the existing ``datetime_dim``, ``localisation_dim`` and ``user``
tables they form the dimensions of the star schemas in ``facts.py``. Only
metadata lives here: raw files, chunk text and vectors stay in the lakehouse and
in the vector store, and are linked through ``uri`` / ``*_uid`` columns.
"""

from sqlalchemy import (
  JSON,
  Boolean,
  Column,
  DateTime,
  Float,
  ForeignKey,
  Integer,
  Numeric,
  String,
  UniqueConstraint,
  func,
  text,
)
from sqlalchemy.sql.expression import false, true

from src.models.base import Base
from src.models.datawarehouse.common import BigInt, CreatedAtMixin, enum_type
from src.models.datawarehouse.enums import (
  ChunkingMethod,
  ChunkUnit,
  DistanceMetric,
  FusionMethod,
  IndexType,
  MedallionLayer,
  MetricCategory,
  ModelKind,
  PipelineStage,
  PromptPurpose,
  Quantization,
  RetrievalMode,
  Sensitivity,
  SourceKind,
  TableFormat,
)


class ModalityDim(Base):
  """Content modality (table ``modality_dim``).

  Small, stable lookup of the kinds of content that are ingested and retrieved.
  Seeded by a migration with TEXT, IMAGE, AUDIO, VIDEO, TABLE, CODE and
  DOCUMENT (a composite such as a PDF or slide deck).

  Attributes:
    id (int): Surrogate primary key.
    code (str): Unique upper-case business key, e.g. ``"IMAGE"``.
    name (str): Human-readable name.
    is_time_based (bool): ``True`` for audio and video, whose chunks are
      located by time range instead of text offsets.
    description (str | None): Free-text notes.
  """

  __tablename__ = "modality_dim"

  id = Column(Integer, primary_key=True, autoincrement=True)
  code = Column(String(32), nullable=False, unique=True)
  name = Column(String(64), nullable=False)
  is_time_based = Column(Boolean, nullable=False, server_default=false())
  description = Column(String(255), nullable=True)


class SourceDim(CreatedAtMixin, Base):
  """System that documents are ingested from (table ``source_dim``).

  Attributes:
    id (int): Surrogate primary key.
    name (str): Unique source name, e.g. ``"s3://corp-docs"`` or
      ``"confluence-engineering"``.
    kind (SourceKind): Type of source system.
    uri (str | None): Base location of the source. Never put credentials here.
    owner (str | None): Team or person responsible for the source.
    sensitivity (Sensitivity): Default data classification for documents from
      this source.
    is_active (bool): ``False`` once the source is no longer crawled.
    created_at (datetime): Insertion time (from ``CreatedAtMixin``).
  """

  __tablename__ = "source_dim"

  id = Column(Integer, primary_key=True, autoincrement=True)
  name = Column(String(128), nullable=False, unique=True)
  kind = Column(enum_type(SourceKind), nullable=False)
  uri = Column(String(512), nullable=True)
  owner = Column(String(128), nullable=True)
  sensitivity = Column(
    enum_type(Sensitivity),
    nullable=False,
    default=Sensitivity.INTERNAL,
    server_default=Sensitivity.INTERNAL.name,
  )
  is_active = Column(Boolean, nullable=False, server_default=true())


class DocumentDim(CreatedAtMixin, Base):
  """Logical document or media asset (table ``document_dim``), SCD type 2.

  A new row is written whenever the content of a document changes, so history
  is kept: all versions share ``document_uid`` while ``version`` increases, the
  previous row gets ``valid_to`` and ``is_current = False``, and the new row is
  the current one. Facts reference the exact version they processed.

  This is a large dimension (one row per document version). Keep it narrow and
  put the heavy content (raw bytes, parsed text) in the lakehouse, reachable
  through ``uri``.

  Attributes:
    id (int): Surrogate primary key (the version-specific key facts point to).
    document_uid (str): Stable business key shared by all versions, e.g. a hash
      of source and path.
    version (int): Version number, starting at 1.
    content_hash (str): SHA-256 (hex) of the raw bytes; used to detect
      unchanged and duplicate content.
    source_id (int): Source the document came from.
    modality_id (int): Primary modality (``DOCUMENT`` for mixed content).
    title (str | None): Document title.
    uri (str | None): Location of the raw asset (lakehouse bronze path, bucket
      key, URL).
    mime_type (str | None): Media type, e.g. ``"application/pdf"``.
    language (str | None): BCP-47 / ISO 639-1 language tag, e.g. ``"fr"``.
    size_bytes (int | None): Size of the raw asset.
    page_count (int | None): Number of pages, for paged documents.
    duration_seconds (float | None): Duration, for audio and video.
    sensitivity (Sensitivity): Data classification of this document.
    valid_from (datetime): When this version became current.
    valid_to (datetime | None): When it was superseded; ``None`` while current.
    is_current (bool): ``True`` for the latest version of the document.
    created_at (datetime): Insertion time (from ``CreatedAtMixin``).
  """

  __tablename__ = "document_dim"
  __table_args__ = (UniqueConstraint("document_uid", "version"),)

  id = Column(BigInt, primary_key=True, autoincrement=True)
  document_uid = Column(String(64), nullable=False)
  version = Column(Integer, nullable=False, server_default=text("1"))
  content_hash = Column(String(64), nullable=False, index=True)
  source_id = Column(Integer, ForeignKey("source_dim.id"), nullable=False, index=True)
  modality_id = Column(Integer, ForeignKey("modality_dim.id"), nullable=False, index=True)
  title = Column(String(512), nullable=True)
  uri = Column(String(1024), nullable=True)
  mime_type = Column(String(128), nullable=True)
  language = Column(String(16), nullable=True)
  size_bytes = Column(BigInt, nullable=True)
  page_count = Column(Integer, nullable=True)
  duration_seconds = Column(Float, nullable=True)
  sensitivity = Column(
    enum_type(Sensitivity),
    nullable=False,
    default=Sensitivity.INTERNAL,
    server_default=Sensitivity.INTERNAL.name,
  )
  valid_from = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
  valid_to = Column(DateTime(timezone=True), nullable=True)
  is_current = Column(Boolean, nullable=False, server_default=true())


class ModelDim(Base):
  """AI model used anywhere in the pipeline (table ``model_dim``).

  One table for every kind of model (embedding, LLM, vision-language, reranker,
  OCR, speech-to-text). Fact tables reference it several times in different
  roles (embedding model, generator, judge, reranker), the classic
  "role-playing dimension". A new row is added for every model *version*.

  Attributes:
    id (int): Surrogate primary key.
    kind (ModelKind): Role of the model.
    provider (str): Vendor or hosting, e.g. ``"openai"``, ``"huggingface"``,
      ``"self-hosted"``.
    name (str): Model name or repository id.
    version (str): Version, revision or snapshot tag (``"latest"`` if unknown).
    modalities (list | None): Input modalities handled, e.g.
      ``["text", "image"]``.
    vector_dim (int | None): Output vector size, for embedding models.
    max_input_tokens (int | None): Context window.
    max_output_tokens (int | None): Maximum generated tokens.
    input_price_per_mtok (Decimal | None): USD per million input tokens.
    output_price_per_mtok (Decimal | None): USD per million output tokens.
    is_open_weights (bool): Whether the weights are publicly available.
    params (dict | None): Anything else worth recording (quantization,
      revision hash, serving options).
  """

  __tablename__ = "model_dim"
  __table_args__ = (UniqueConstraint("kind", "provider", "name", "version"),)

  id = Column(Integer, primary_key=True, autoincrement=True)
  kind = Column(enum_type(ModelKind), nullable=False)
  provider = Column(String(64), nullable=False)
  name = Column(String(128), nullable=False)
  version = Column(String(64), nullable=False, server_default="latest")
  modalities = Column(JSON, nullable=True)
  vector_dim = Column(Integer, nullable=True)
  max_input_tokens = Column(Integer, nullable=True)
  max_output_tokens = Column(Integer, nullable=True)
  input_price_per_mtok = Column(Numeric(12, 6), nullable=True)
  output_price_per_mtok = Column(Numeric(12, 6), nullable=True)
  is_open_weights = Column(Boolean, nullable=False, server_default=false())
  params = Column(JSON, nullable=True)


class ChunkingStrategyDim(Base):
  """How content is split into chunks (table ``chunking_strategy_dim``).

  Lets you compare retrieval quality and cost across chunk sizes, overlaps and
  methods, per modality.

  Attributes:
    id (int): Surrogate primary key.
    name (str): Unique descriptive name, e.g. ``"recursive-512-64"``.
    method (ChunkingMethod): Splitting algorithm.
    unit (ChunkUnit): Unit of ``chunk_size`` and ``chunk_overlap``.
    chunk_size (int | None): Target chunk size, in ``unit``.
    chunk_overlap (int | None): Overlap between consecutive chunks, in ``unit``.
    modality_id (int | None): Modality the strategy applies to; ``None`` if it
      is modality-agnostic.
    params (dict | None): Extra settings (separators, similarity threshold,
      layout model, ...).
  """

  __tablename__ = "chunking_strategy_dim"

  id = Column(Integer, primary_key=True, autoincrement=True)
  name = Column(String(128), nullable=False, unique=True)
  method = Column(enum_type(ChunkingMethod), nullable=False)
  unit = Column(enum_type(ChunkUnit), nullable=False)
  chunk_size = Column(Integer, nullable=True)
  chunk_overlap = Column(Integer, nullable=True)
  modality_id = Column(Integer, ForeignKey("modality_dim.id"), nullable=True)
  params = Column(JSON, nullable=True)


class RetrievalStrategyDim(Base):
  """Retrieval configuration (table ``retrieval_strategy_dim``).

  The knob set behind a query: dense, sparse or hybrid search, how results are
  fused, how many are kept and whether a reranker runs. Essential for A/B
  comparing hybrid-search setups.

  Attributes:
    id (int): Surrogate primary key.
    name (str): Unique descriptive name, e.g. ``"hybrid-rrf-k20-rerank"``.
    mode (RetrievalMode): Retrieval approach.
    fusion (FusionMethod): How dense and sparse scores are combined.
    top_k (int): Number of candidates returned to the next stage.
    reranker_model_id (int | None): Reranker used, if any.
    dense_weight (float | None): Weight of the dense score in a weighted-sum
      fusion (the sparse weight is ``1 - dense_weight``).
    min_score (float | None): Minimum score for a hit to be kept.
    params (dict | None): Extra settings (metadata filters, MMR lambda, query
      expansion, ...).
  """

  __tablename__ = "retrieval_strategy_dim"

  id = Column(Integer, primary_key=True, autoincrement=True)
  name = Column(String(128), nullable=False, unique=True)
  mode = Column(enum_type(RetrievalMode), nullable=False)
  fusion = Column(enum_type(FusionMethod), nullable=False, server_default=FusionMethod.NONE.name)
  top_k = Column(Integer, nullable=False)
  reranker_model_id = Column(Integer, ForeignKey("model_dim.id"), nullable=True)
  dense_weight = Column(Float, nullable=True)
  min_score = Column(Float, nullable=True)
  params = Column(JSON, nullable=True)


class VectorIndexDim(CreatedAtMixin, Base):
  """Vector index / collection in the vector store (table ``vector_index_dim``).

  Describes the "vector half" of the hybrid vector-lakehouse: which engine
  holds the vectors and how the index is tuned.

  Attributes:
    id (int): Surrogate primary key.
    vector_engine (str): Vector database, e.g. ``"qdrant"``, ``"milvus"``,
      ``"pgvector"``, ``"lancedb"``.
    collection (str): Collection, table or index name inside the engine.
    embedding_model_id (int): Model that produced the vectors.
    modality_id (int | None): Modality stored; ``None`` for mixed collections.
    dimensions (int): Vector size.
    metric (DistanceMetric): Similarity function.
    index_type (IndexType): ANN structure.
    quantization (Quantization): Vector compression.
    index_params (dict | None): Tuning parameters (``M``, ``efConstruction``,
      ``nlist``, ``nprobe``, ...).
    created_at (datetime): Insertion time (from ``CreatedAtMixin``).
  """

  __tablename__ = "vector_index_dim"
  __table_args__ = (UniqueConstraint("vector_engine", "collection"),)

  id = Column(Integer, primary_key=True, autoincrement=True)
  vector_engine = Column(String(64), nullable=False)
  collection = Column(String(128), nullable=False)
  embedding_model_id = Column(Integer, ForeignKey("model_dim.id"), nullable=False)
  modality_id = Column(Integer, ForeignKey("modality_dim.id"), nullable=True)
  dimensions = Column(Integer, nullable=False)
  metric = Column(enum_type(DistanceMetric), nullable=False)
  index_type = Column(enum_type(IndexType), nullable=False)
  quantization = Column(
    enum_type(Quantization), nullable=False, server_default=Quantization.NONE.name
  )
  index_params = Column(JSON, nullable=True)


class LakehouseTableDim(Base):
  """Table in the lakehouse (table ``lakehouse_table_dim``).

  Describes the "lakehouse half" of the hybrid architecture: the open-format
  tables (Delta, Iceberg, Hudi) that hold raw assets, parsed content, chunk text
  and features.

  Attributes:
    id (int): Surrogate primary key.
    catalog (str): Catalog name (``"default"`` if there is only one).
    schema_name (str): Database / namespace inside the catalog.
    table_name (str): Table name.
    layer (MedallionLayer): Bronze, silver or gold.
    table_format (TableFormat): Open table format.
    location (str | None): Storage location, e.g. ``"s3://lake/silver/chunks"``.
    partition_spec (str | None): Partitioning, e.g. ``"days(event_at)"``.
    description (str | None): What the table holds.
  """

  __tablename__ = "lakehouse_table_dim"
  __table_args__ = (UniqueConstraint("catalog", "schema_name", "table_name"),)

  id = Column(Integer, primary_key=True, autoincrement=True)
  catalog = Column(String(128), nullable=False, server_default="default")
  schema_name = Column(String(128), nullable=False)
  table_name = Column(String(128), nullable=False)
  layer = Column(enum_type(MedallionLayer), nullable=False)
  table_format = Column(enum_type(TableFormat), nullable=False)
  location = Column(String(1024), nullable=True)
  partition_spec = Column(String(255), nullable=True)
  description = Column(String(255), nullable=True)


class PipelineDim(Base):
  """Data or ML pipeline definition (table ``pipeline_dim``).

  One row per pipeline *version*, so runs can be attributed to the exact code
  that produced them.

  Attributes:
    id (int): Surrogate primary key.
    name (str): Pipeline name, e.g. ``"pdf_ingest"`` or ``"embed_chunks"``.
    version (str): Release tag, semantic version or git SHA.
    stage (PipelineStage): What the pipeline does.
    orchestrator (str | None): Scheduler or engine, e.g. ``"airflow"``,
      ``"dagster"``, ``"spark"``.
    owner (str | None): Team or person responsible.
    description (str | None): What the pipeline does.
  """

  __tablename__ = "pipeline_dim"
  __table_args__ = (UniqueConstraint("name", "version"),)

  id = Column(Integer, primary_key=True, autoincrement=True)
  name = Column(String(128), nullable=False)
  version = Column(String(64), nullable=False)
  stage = Column(enum_type(PipelineStage), nullable=False)
  orchestrator = Column(String(64), nullable=True)
  owner = Column(String(128), nullable=True)
  description = Column(String(255), nullable=True)


class PromptTemplateDim(CreatedAtMixin, Base):
  """Versioned prompt template (table ``prompt_template_dim``).

  Prompts are code that changes answer quality; tracking them as a dimension
  makes "did prompt v3 beat v2?" a plain group-by. The template text itself
  stays in git or a prompt registry; only its hash is stored here.

  Attributes:
    id (int): Surrogate primary key.
    name (str): Template name, e.g. ``"rag-answer"``.
    version (str): Template version.
    purpose (PromptPurpose): What the prompt is used for.
    template_hash (str): SHA-256 (hex) of the template text, to detect silent
      edits.
    description (str | None): Notes on the change.
    created_at (datetime): Insertion time (from ``CreatedAtMixin``).
  """

  __tablename__ = "prompt_template_dim"
  __table_args__ = (UniqueConstraint("name", "version"),)

  id = Column(Integer, primary_key=True, autoincrement=True)
  name = Column(String(128), nullable=False)
  version = Column(String(64), nullable=False)
  purpose = Column(enum_type(PromptPurpose), nullable=False)
  template_hash = Column(String(64), nullable=False)
  description = Column(String(255), nullable=True)


class MetricDim(Base):
  """Evaluation or quality metric (table ``metric_dim``).

  Lookup of the metrics stored in ``evaluation_result_fact``. Seeded by a
  migration with the usual retrieval, generation and system metrics.

  Attributes:
    id (int): Surrogate primary key.
    code (str): Unique machine name, e.g. ``"recall_at_k"``, ``"faithfulness"``.
    name (str): Human-readable name.
    category (MetricCategory): Retrieval, generation or system metric.
    higher_is_better (bool): Direction of improvement (``False`` for latency,
      cost, hallucination rate, ...).
    unit (str | None): Unit, e.g. ``"ratio"``, ``"ms"``, ``"usd"``.
    min_value (float | None): Lowest possible value, if bounded.
    max_value (float | None): Highest possible value, if bounded.
    description (str | None): How the metric is computed.
  """

  __tablename__ = "metric_dim"

  id = Column(Integer, primary_key=True, autoincrement=True)
  code = Column(String(64), nullable=False, unique=True)
  name = Column(String(128), nullable=False)
  category = Column(enum_type(MetricCategory), nullable=False)
  higher_is_better = Column(Boolean, nullable=False, server_default=true())
  unit = Column(String(32), nullable=True)
  min_value = Column(Float, nullable=True)
  max_value = Column(Float, nullable=True)
  description = Column(String(255), nullable=True)


class EvalDatasetDim(CreatedAtMixin, Base):
  """Evaluation ("golden") dataset (table ``eval_dataset_dim``).

  Attributes:
    id (int): Surrogate primary key.
    name (str): Dataset name, e.g. ``"support-faq-golden"``.
    version (str): Dataset version; results are only comparable within one.
    description (str | None): What the dataset covers.
    num_samples (int | None): Number of question/answer samples.
    location (str | None): Where the dataset lives (lakehouse path, URL).
    created_at (datetime): Insertion time (from ``CreatedAtMixin``).
  """

  __tablename__ = "eval_dataset_dim"
  __table_args__ = (UniqueConstraint("name", "version"),)

  id = Column(Integer, primary_key=True, autoincrement=True)
  name = Column(String(128), nullable=False)
  version = Column(String(64), nullable=False)
  description = Column(String(255), nullable=True)
  num_samples = Column(Integer, nullable=True)
  location = Column(String(1024), nullable=True)
