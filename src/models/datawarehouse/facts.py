"""Fact tables for the multimodal RAG / hybrid vector-lakehouse warehouse.

Four star schemas share the dimensions in ``dimensions.py`` and
``rag_dimensions.py`` (plus the ``user`` table):

* **Ingestion**: ``pipeline_run_fact`` -> ``ingestion_fact`` -> ``chunk_fact`` ->
  ``embedding_fact``. How content flows from sources, through parsing and
  chunking, to vectors in an index.
* **Serving**: ``query_fact`` -> ``retrieval_hit_fact`` and ``feedback_fact``.
  What users ask, what is retrieved, what it costs and how users react.
* **Evaluation**: ``evaluation_result_fact``. Offline quality scores per
  dataset, metric and system configuration.
* **Storage health**: ``lakehouse_snapshot_fact`` and
  ``vector_index_snapshot_fact``. Periodic size and performance snapshots of
  the two halves of the hybrid store.

Conventions:

* Every fact has a ``BigInt`` surrogate key, a ``datetime_id`` pointing to
  ``datetime_dim`` (for slicing by calendar) and an exact timestamp
  (``event_at`` / ``snapshot_at`` / ``started_at``) for partitioning and
  ordering.
* Measures are nullable when not every modality or stage can provide them.
* Only measures and keys are stored. Chunk text, raw files and vectors stay in
  the lakehouse and the vector store; ``chunk_uid``, ``vector_id`` and
  ``document_dim.uri`` link to them.
* Foreign keys document the star joins. For the very largest tables you may
  drop the constraints (keep the indexes) to speed up bulk loads.
"""

from sqlalchemy import (
  JSON,
  Boolean,
  Column,
  DateTime,
  Float,
  ForeignKey,
  Index,
  Integer,
  Numeric,
  SmallInteger,
  String,
  Text,
  UniqueConstraint,
  text,
)
from sqlalchemy.sql.expression import false

from src.models.base import Base
from src.models.datawarehouse.common import BigInt, enum_type
from src.models.datawarehouse.enums import (
  Channel,
  FeedbackLabel,
  RequestStatus,
  RunStatus,
  Sentiment,
  TriggerType,
)


class PipelineRunFact(Base):
  """One execution of a pipeline (table ``pipeline_run_fact``).

  Grain: one row per pipeline run. It is an *accumulating snapshot*: the row is
  inserted when the run starts and updated as it progresses (``status``,
  ``finished_at``, counters).

  Attributes:
    id (int): Surrogate primary key.
    run_uid (str): Unique run id from the orchestrator (e.g. an Airflow
      ``run_id``).
    pipeline_id (int): Pipeline version that ran (``pipeline_dim``).
    datetime_id (int): Start time in ``datetime_dim``.
    started_at (datetime): Exact start time.
    finished_at (datetime | None): Exact end time; ``None`` while running.
    status (RunStatus): Current or final status.
    trigger_type (TriggerType): What started the run.
    records_read (int): Input records processed.
    records_written (int): Output records produced.
    records_failed (int): Records that errored.
    bytes_processed (int): Input volume in bytes.
    duration_seconds (float | None): Wall-clock duration.
    cpu_seconds (float | None): CPU time consumed.
    gpu_seconds (float | None): GPU time consumed (embedding, OCR, ASR, ...).
    cost_usd (Decimal | None): Estimated compute cost.
    error_message (str | None): Failure reason, if any.
  """

  __tablename__ = "pipeline_run_fact"

  id = Column(BigInt, primary_key=True, autoincrement=True)
  run_uid = Column(String(64), nullable=False, unique=True)
  pipeline_id = Column(Integer, ForeignKey("pipeline_dim.id"), nullable=False, index=True)
  datetime_id = Column(Integer, ForeignKey("datetime_dim.id"), nullable=False, index=True)
  started_at = Column(DateTime(timezone=True), nullable=False)
  finished_at = Column(DateTime(timezone=True), nullable=True)
  status = Column(enum_type(RunStatus), nullable=False)
  trigger_type = Column(
    enum_type(TriggerType), nullable=False, server_default=TriggerType.SCHEDULE.name
  )
  records_read = Column(BigInt, nullable=False, server_default=text("0"))
  records_written = Column(BigInt, nullable=False, server_default=text("0"))
  records_failed = Column(BigInt, nullable=False, server_default=text("0"))
  bytes_processed = Column(BigInt, nullable=False, server_default=text("0"))
  duration_seconds = Column(Float, nullable=True)
  cpu_seconds = Column(Float, nullable=True)
  gpu_seconds = Column(Float, nullable=True)
  cost_usd = Column(Numeric(14, 6), nullable=True)
  error_message = Column(Text, nullable=True)


class IngestionFact(Base):
  """A document version processed by a run (table ``ingestion_fact``).

  Grain: one row per document version per pipeline run. Answers "how many
  documents and bytes came in, from which source and modality, how many failed
  and why, how many were duplicates".

  Attributes:
    id (int): Surrogate primary key.
    datetime_id (int): Processing time in ``datetime_dim``.
    event_at (datetime): Exact processing time.
    pipeline_run_id (int): Run that processed the document.
    document_id (int): Document version processed (``document_dim``).
    source_id (int): Source of the document (denormalized for star joins).
    modality_id (int): Modality of the document.
    target_table_id (int | None): Lakehouse table the raw content was landed in.
    status (RunStatus): Outcome for this document.
    is_duplicate (bool): ``True`` if identical content was already ingested.
    bytes_in (int | None): Raw size read.
    bytes_out (int | None): Size written after parsing.
    page_count (int | None): Pages processed, for paged documents.
    duration_seconds (float | None): Media duration, for audio and video.
    chunk_count (int): Chunks produced.
    parse_ms (int | None): Time spent parsing / OCR / transcription.
    total_ms (int | None): Total processing time.
    retry_count (int): Number of retries before the final outcome.
    error_code (str | None): Short machine-readable failure code.
    error_message (str | None): Failure details.
  """

  __tablename__ = "ingestion_fact"

  id = Column(BigInt, primary_key=True, autoincrement=True)
  datetime_id = Column(Integer, ForeignKey("datetime_dim.id"), nullable=False, index=True)
  event_at = Column(DateTime(timezone=True), nullable=False)
  pipeline_run_id = Column(BigInt, ForeignKey("pipeline_run_fact.id"), nullable=False, index=True)
  document_id = Column(BigInt, ForeignKey("document_dim.id"), nullable=False, index=True)
  source_id = Column(Integer, ForeignKey("source_dim.id"), nullable=False)
  modality_id = Column(Integer, ForeignKey("modality_dim.id"), nullable=False)
  target_table_id = Column(Integer, ForeignKey("lakehouse_table_dim.id"), nullable=True)
  status = Column(enum_type(RunStatus), nullable=False)
  is_duplicate = Column(Boolean, nullable=False, server_default=false())
  bytes_in = Column(BigInt, nullable=True)
  bytes_out = Column(BigInt, nullable=True)
  page_count = Column(Integer, nullable=True)
  duration_seconds = Column(Float, nullable=True)
  chunk_count = Column(Integer, nullable=False, server_default=text("0"))
  parse_ms = Column(Integer, nullable=True)
  total_ms = Column(Integer, nullable=True)
  retry_count = Column(Integer, nullable=False, server_default=text("0"))
  error_code = Column(String(64), nullable=True)
  error_message = Column(Text, nullable=True)


class ChunkFact(Base):
  """A retrievable chunk of a document (table ``chunk_fact``).

  Grain: one row per chunk. Holds the chunk's *metadata and measures* only; the
  text (or image / audio / video segment) lives in the lakehouse and the vector
  in the vector store, both addressed by ``chunk_uid``. This is typically the
  largest table of the warehouse.

  Attributes:
    id (int): Surrogate primary key.
    chunk_uid (str): Unique business key shared with the lakehouse row and the
      vector-store point.
    datetime_id (int): Creation time in ``datetime_dim``.
    event_at (datetime): Exact creation time.
    document_id (int): Document version the chunk belongs to.
    modality_id (int): Modality of the chunk (a PDF yields TEXT, TABLE and IMAGE
      chunks).
    chunking_strategy_id (int): Strategy that produced the chunk.
    ingestion_id (int | None): Ingestion event that created it.
    lakehouse_table_id (int | None): Lakehouse table holding the chunk content.
    chunk_index (int): Position of the chunk within the document.
    page_number (int | None): Source page, for paged documents.
    start_offset (int | None): Start character offset in the parsed text.
    end_offset (int | None): End character offset in the parsed text.
    start_ms (int | None): Start time, for audio and video chunks.
    end_ms (int | None): End time, for audio and video chunks.
    token_count (int | None): Size in tokens.
    char_count (int | None): Size in characters.
    language (str | None): Detected language tag.
    content_hash (str): SHA-256 (hex) of the chunk content, to find duplicates.
    quality_score (float | None): Parsing / OCR / transcription confidence.
    extra (dict | None): Modality-specific details (image bounding box, table
      shape, speaker label, ...).
  """

  __tablename__ = "chunk_fact"
  __table_args__ = (UniqueConstraint("document_id", "chunking_strategy_id", "chunk_index"),)

  id = Column(BigInt, primary_key=True, autoincrement=True)
  chunk_uid = Column(String(64), nullable=False, unique=True)
  datetime_id = Column(Integer, ForeignKey("datetime_dim.id"), nullable=False, index=True)
  event_at = Column(DateTime(timezone=True), nullable=False)
  document_id = Column(BigInt, ForeignKey("document_dim.id"), nullable=False)
  modality_id = Column(Integer, ForeignKey("modality_dim.id"), nullable=False)
  chunking_strategy_id = Column(Integer, ForeignKey("chunking_strategy_dim.id"), nullable=False)
  ingestion_id = Column(BigInt, ForeignKey("ingestion_fact.id"), nullable=True, index=True)
  lakehouse_table_id = Column(Integer, ForeignKey("lakehouse_table_dim.id"), nullable=True)
  chunk_index = Column(Integer, nullable=False)
  page_number = Column(Integer, nullable=True)
  start_offset = Column(Integer, nullable=True)
  end_offset = Column(Integer, nullable=True)
  start_ms = Column(Integer, nullable=True)
  end_ms = Column(Integer, nullable=True)
  token_count = Column(Integer, nullable=True)
  char_count = Column(Integer, nullable=True)
  language = Column(String(16), nullable=True)
  content_hash = Column(String(64), nullable=False, index=True)
  quality_score = Column(Float, nullable=True)
  extra = Column(JSON, nullable=True)


class EmbeddingFact(Base):
  """A chunk embedded and indexed (table ``embedding_fact``).

  Grain: one row per chunk, embedding model and vector index. Re-embedding with
  another model or into another index adds a row, so index migrations and
  model comparisons stay traceable.

  Attributes:
    id (int): Surrogate primary key.
    datetime_id (int): Embedding time in ``datetime_dim``.
    event_at (datetime): Exact embedding time.
    chunk_id (int): Chunk that was embedded.
    model_id (int): Embedding model used (``model_dim``).
    vector_index_id (int): Index the vector was written to.
    pipeline_run_id (int | None): Run that produced the embedding.
    vector_id (str | None): Id of the point in the vector store.
    status (RunStatus): Outcome of embedding and indexing.
    tokens_embedded (int | None): Tokens (or patches / frames) sent to the model.
    embed_ms (int | None): Model inference time.
    index_ms (int | None): Time to write the vector into the index.
    vector_norm (float | None): L2 norm of the vector, handy to spot degenerate
      embeddings.
    cost_usd (Decimal | None): Embedding cost.
    error_code (str | None): Short machine-readable failure code.
  """

  __tablename__ = "embedding_fact"
  __table_args__ = (UniqueConstraint("chunk_id", "model_id", "vector_index_id"),)

  id = Column(BigInt, primary_key=True, autoincrement=True)
  datetime_id = Column(Integer, ForeignKey("datetime_dim.id"), nullable=False, index=True)
  event_at = Column(DateTime(timezone=True), nullable=False)
  chunk_id = Column(BigInt, ForeignKey("chunk_fact.id"), nullable=False)
  model_id = Column(Integer, ForeignKey("model_dim.id"), nullable=False)
  vector_index_id = Column(Integer, ForeignKey("vector_index_dim.id"), nullable=False)
  pipeline_run_id = Column(BigInt, ForeignKey("pipeline_run_fact.id"), nullable=True, index=True)
  vector_id = Column(String(128), nullable=True)
  status = Column(enum_type(RunStatus), nullable=False)
  tokens_embedded = Column(Integer, nullable=True)
  embed_ms = Column(Integer, nullable=True)
  index_ms = Column(Integer, nullable=True)
  vector_norm = Column(Float, nullable=True)
  cost_usd = Column(Numeric(14, 6), nullable=True)
  error_code = Column(String(64), nullable=True)


class QueryFact(Base):
  """A request to the RAG system (table ``query_fact``).

  Grain: one row per user request. The central table for usage, latency, cost
  and quality analytics of the serving side. Raw query text is optional so
  deployments with privacy constraints can store only ``query_hash``.

  Attributes:
    id (int): Surrogate primary key.
    request_uid (str): Unique request / trace id, also used in application logs.
    datetime_id (int): Request time in ``datetime_dim``.
    event_at (datetime): Exact request time.
    user_id (int | None): Requesting user (``user``); ``None`` if anonymous.
    localisation_id (int | None): Location the request came from.
    retrieval_strategy_id (int | None): Retrieval configuration used.
    generator_model_id (int | None): LLM / VLM that wrote the answer; ``None``
      for retrieval-only requests.
    prompt_template_id (int | None): Prompt template used.
    channel (Channel): Entry point of the request.
    status (RequestStatus): Outcome.
    language (str | None): Language of the query.
    query_hash (str): SHA-256 (hex) of the normalized query, for grouping
      repeated questions without storing the text.
    query_text (str | None): The query itself, if retention is allowed.
    input_modalities (list | None): Modalities in the query, e.g.
      ``["text", "image"]``.
    is_multimodal (bool): ``True`` if the query contained more than text.
    cache_hit (bool): ``True`` if answered from a semantic cache.
    guardrail_triggered (bool): ``True`` if a safety guardrail intervened.
    retrieved_count (int): Chunks retrieved.
    cited_count (int): Chunks cited in the answer.
    prompt_tokens (int | None): Tokens sent to the generator.
    completion_tokens (int | None): Tokens generated.
    retrieval_ms (int | None): Search time.
    rerank_ms (int | None): Reranking time.
    generation_ms (int | None): Generation time.
    total_ms (int | None): End-to-end latency.
    ttft_ms (int | None): Time to first streamed token.
    cost_usd (Decimal | None): Total cost of the request.
    error_code (str | None): Short machine-readable failure code.
  """

  __tablename__ = "query_fact"

  id = Column(BigInt, primary_key=True, autoincrement=True)
  request_uid = Column(String(64), nullable=False, unique=True)
  datetime_id = Column(Integer, ForeignKey("datetime_dim.id"), nullable=False, index=True)
  event_at = Column(DateTime(timezone=True), nullable=False)
  user_id = Column(Integer, ForeignKey("user.id"), nullable=True, index=True)
  localisation_id = Column(Integer, ForeignKey("localisation_dim.id"), nullable=True)
  retrieval_strategy_id = Column(Integer, ForeignKey("retrieval_strategy_dim.id"), nullable=True)
  generator_model_id = Column(Integer, ForeignKey("model_dim.id"), nullable=True)
  prompt_template_id = Column(Integer, ForeignKey("prompt_template_dim.id"), nullable=True)
  channel = Column(enum_type(Channel), nullable=False)
  status = Column(enum_type(RequestStatus), nullable=False)
  language = Column(String(16), nullable=True)
  query_hash = Column(String(64), nullable=False, index=True)
  query_text = Column(Text, nullable=True)
  input_modalities = Column(JSON, nullable=True)
  is_multimodal = Column(Boolean, nullable=False, server_default=false())
  cache_hit = Column(Boolean, nullable=False, server_default=false())
  guardrail_triggered = Column(Boolean, nullable=False, server_default=false())
  retrieved_count = Column(Integer, nullable=False, server_default=text("0"))
  cited_count = Column(Integer, nullable=False, server_default=text("0"))
  prompt_tokens = Column(Integer, nullable=True)
  completion_tokens = Column(Integer, nullable=True)
  retrieval_ms = Column(Integer, nullable=True)
  rerank_ms = Column(Integer, nullable=True)
  generation_ms = Column(Integer, nullable=True)
  total_ms = Column(Integer, nullable=True)
  ttft_ms = Column(Integer, nullable=True)
  cost_usd = Column(Numeric(14, 6), nullable=True)
  error_code = Column(String(64), nullable=True)


class RetrievalHitFact(Base):
  """A chunk returned for a query (table ``retrieval_hit_fact``).

  Grain: one row per query and retrieved chunk (the final candidate list). It
  is the bridge between ``query_fact`` and ``chunk_fact`` and carries the score
  of every retrieval stage, which makes hybrid-search tuning (dense vs sparse
  vs fused vs reranked) a SQL question. Volume is ``top_k`` rows per query.

  Attributes:
    id (int): Surrogate primary key.
    datetime_id (int): Query time in ``datetime_dim``.
    event_at (datetime): Exact query time.
    query_id (int): Query this hit belongs to.
    chunk_id (int): Chunk that was retrieved.
    vector_index_id (int | None): Index the dense hit came from.
    final_rank (int): Position after fusion and reranking (1 = best).
    dense_score (float | None): Vector-similarity score.
    sparse_score (float | None): Lexical (BM25 / SPLADE) score.
    fused_score (float | None): Score after fusion.
    rerank_score (float | None): Score from the reranker.
    dense_rank (int | None): Position in the dense result list.
    sparse_rank (int | None): Position in the sparse result list.
    was_used_in_context (bool): ``True`` if the chunk went into the prompt.
    was_cited (bool): ``True`` if the answer cited the chunk.
    relevance_label (int | None): Human or LLM relevance judgement (e.g. 0-3),
      for offline evaluation.
  """

  __tablename__ = "retrieval_hit_fact"
  __table_args__ = (UniqueConstraint("query_id", "chunk_id"),)

  id = Column(BigInt, primary_key=True, autoincrement=True)
  datetime_id = Column(Integer, ForeignKey("datetime_dim.id"), nullable=False, index=True)
  event_at = Column(DateTime(timezone=True), nullable=False)
  query_id = Column(BigInt, ForeignKey("query_fact.id"), nullable=False)
  chunk_id = Column(BigInt, ForeignKey("chunk_fact.id"), nullable=False, index=True)
  vector_index_id = Column(Integer, ForeignKey("vector_index_dim.id"), nullable=True)
  final_rank = Column(Integer, nullable=False)
  dense_score = Column(Float, nullable=True)
  sparse_score = Column(Float, nullable=True)
  fused_score = Column(Float, nullable=True)
  rerank_score = Column(Float, nullable=True)
  dense_rank = Column(Integer, nullable=True)
  sparse_rank = Column(Integer, nullable=True)
  was_used_in_context = Column(Boolean, nullable=False, server_default=false())
  was_cited = Column(Boolean, nullable=False, server_default=false())
  relevance_label = Column(SmallInteger, nullable=True)


class FeedbackFact(Base):
  """User feedback on an answer (table ``feedback_fact``).

  Grain: one row per feedback event (a query can receive several).

  Attributes:
    id (int): Surrogate primary key.
    datetime_id (int): Feedback time in ``datetime_dim``.
    event_at (datetime): Exact feedback time.
    query_id (int): Query the feedback is about.
    user_id (int | None): User who gave it.
    sentiment (Sentiment | None): Thumbs up / down.
    rating (int | None): Numeric rating (e.g. 1-5).
    label (FeedbackLabel | None): Reason chosen by the user.
    comment_text (str | None): Free-text comment.
  """

  __tablename__ = "feedback_fact"

  id = Column(BigInt, primary_key=True, autoincrement=True)
  datetime_id = Column(Integer, ForeignKey("datetime_dim.id"), nullable=False, index=True)
  event_at = Column(DateTime(timezone=True), nullable=False)
  query_id = Column(BigInt, ForeignKey("query_fact.id"), nullable=False, index=True)
  user_id = Column(Integer, ForeignKey("user.id"), nullable=True)
  sentiment = Column(enum_type(Sentiment), nullable=True)
  rating = Column(SmallInteger, nullable=True)
  label = Column(enum_type(FeedbackLabel), nullable=True)
  comment_text = Column(Text, nullable=True)


class EvaluationResultFact(Base):
  """One metric value from an evaluation run (table ``evaluation_result_fact``).

  Grain: one row per evaluation run, sample and metric. Storing one metric per
  row (instead of one column per metric) means new metrics need no schema
  change. The system under test is described by the strategy, model and prompt
  keys, so any two configurations can be compared on the same dataset.

  Attributes:
    id (int): Surrogate primary key.
    datetime_id (int): Evaluation time in ``datetime_dim``.
    event_at (datetime): Exact evaluation time.
    eval_run_uid (str): Id of the evaluation run (groups all rows of one run).
    eval_dataset_id (int): Dataset evaluated.
    sample_id (str): Id of the sample inside the dataset.
    metric_id (int): Metric measured.
    metric_value (float): Measured value.
    passed (bool | None): Whether the value met the metric's threshold.
    retrieval_strategy_id (int | None): Retrieval configuration under test.
    embedding_model_id (int | None): Embedding model under test.
    generator_model_id (int | None): Generator model under test.
    judge_model_id (int | None): LLM used as judge, for model-graded metrics.
    prompt_template_id (int | None): Prompt template under test.
    query_id (int | None): Matching ``query_fact`` row if the sample was
      replayed through the live system.
  """

  __tablename__ = "evaluation_result_fact"
  __table_args__ = (
    UniqueConstraint("eval_run_uid", "sample_id", "metric_id"),
    Index("ix_evaluation_result_fact_eval_dataset_id_metric_id", "eval_dataset_id", "metric_id"),
  )

  id = Column(BigInt, primary_key=True, autoincrement=True)
  datetime_id = Column(Integer, ForeignKey("datetime_dim.id"), nullable=False, index=True)
  event_at = Column(DateTime(timezone=True), nullable=False)
  eval_run_uid = Column(String(64), nullable=False)
  eval_dataset_id = Column(Integer, ForeignKey("eval_dataset_dim.id"), nullable=False)
  sample_id = Column(String(64), nullable=False)
  metric_id = Column(Integer, ForeignKey("metric_dim.id"), nullable=False)
  metric_value = Column(Float, nullable=False)
  passed = Column(Boolean, nullable=True)
  retrieval_strategy_id = Column(Integer, ForeignKey("retrieval_strategy_dim.id"), nullable=True)
  embedding_model_id = Column(Integer, ForeignKey("model_dim.id"), nullable=True)
  generator_model_id = Column(Integer, ForeignKey("model_dim.id"), nullable=True)
  judge_model_id = Column(Integer, ForeignKey("model_dim.id"), nullable=True)
  prompt_template_id = Column(Integer, ForeignKey("prompt_template_dim.id"), nullable=True)
  query_id = Column(BigInt, ForeignKey("query_fact.id"), nullable=True)


class LakehouseSnapshotFact(Base):
  """Periodic size snapshot of a lakehouse table (table ``lakehouse_snapshot_fact``).

  Grain: one row per lakehouse table per snapshot time (a *periodic snapshot*,
  e.g. daily). Tracks growth and file-layout health, such as the small-file
  problem that calls for compaction.

  Attributes:
    id (int): Surrogate primary key.
    datetime_id (int): Snapshot time in ``datetime_dim``.
    snapshot_at (datetime): Exact snapshot time.
    lakehouse_table_id (int): Table measured.
    table_version (str | None): Delta version or Iceberg snapshot id at that
      moment.
    row_count (int): Rows in the table.
    file_count (int): Data files.
    total_bytes (int): Total size of the data files.
    small_file_count (int | None): Files below the target size.
    partition_count (int | None): Number of partitions.
    last_optimized_at (datetime | None): Last compaction / OPTIMIZE run.
  """

  __tablename__ = "lakehouse_snapshot_fact"
  __table_args__ = (UniqueConstraint("lakehouse_table_id", "snapshot_at"),)

  id = Column(BigInt, primary_key=True, autoincrement=True)
  datetime_id = Column(Integer, ForeignKey("datetime_dim.id"), nullable=False, index=True)
  snapshot_at = Column(DateTime(timezone=True), nullable=False)
  lakehouse_table_id = Column(Integer, ForeignKey("lakehouse_table_dim.id"), nullable=False)
  table_version = Column(String(64), nullable=True)
  row_count = Column(BigInt, nullable=False)
  file_count = Column(Integer, nullable=False)
  total_bytes = Column(BigInt, nullable=False)
  small_file_count = Column(Integer, nullable=True)
  partition_count = Column(Integer, nullable=True)
  last_optimized_at = Column(DateTime(timezone=True), nullable=True)


class VectorIndexSnapshotFact(Base):
  """Periodic health snapshot of a vector index (table ``vector_index_snapshot_fact``).

  Grain: one row per vector index per snapshot time (a *periodic snapshot*).
  Tracks index growth, memory footprint, search latency and measured recall, the
  signals that tell you when to re-tune or rebuild an index.

  Attributes:
    id (int): Surrogate primary key.
    datetime_id (int): Snapshot time in ``datetime_dim``.
    snapshot_at (datetime): Exact snapshot time.
    vector_index_id (int): Index measured.
    vector_count (int): Live vectors in the index.
    deleted_count (int | None): Tombstoned vectors not yet compacted.
    index_bytes (int | None): On-disk size.
    memory_bytes (int | None): Resident memory.
    qps (float | None): Average queries per second in the period.
    latency_p50_ms (float | None): Median search latency.
    latency_p95_ms (float | None): 95th-percentile search latency.
    latency_p99_ms (float | None): 99th-percentile search latency.
    recall_estimate (float | None): Sampled recall against exact (brute-force)
      search, between 0 and 1.
    recall_k (int | None): ``k`` used for ``recall_estimate``.
  """

  __tablename__ = "vector_index_snapshot_fact"
  __table_args__ = (UniqueConstraint("vector_index_id", "snapshot_at"),)

  id = Column(BigInt, primary_key=True, autoincrement=True)
  datetime_id = Column(Integer, ForeignKey("datetime_dim.id"), nullable=False, index=True)
  snapshot_at = Column(DateTime(timezone=True), nullable=False)
  vector_index_id = Column(Integer, ForeignKey("vector_index_dim.id"), nullable=False)
  vector_count = Column(BigInt, nullable=False)
  deleted_count = Column(BigInt, nullable=True)
  index_bytes = Column(BigInt, nullable=True)
  memory_bytes = Column(BigInt, nullable=True)
  qps = Column(Float, nullable=True)
  latency_p50_ms = Column(Float, nullable=True)
  latency_p95_ms = Column(Float, nullable=True)
  latency_p99_ms = Column(Float, nullable=True)
  recall_estimate = Column(Float, nullable=True)
  recall_k = Column(Integer, nullable=True)
