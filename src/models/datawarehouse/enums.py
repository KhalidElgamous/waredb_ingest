"""Enumerations used by the RAG dimension and fact tables.

Each member's value equals its name, and the name is what ends up in the
database (see ``common.enum_type``). Only categories that are structural enough
to group or filter by are enums; vendor-like attributes (model provider, vector
engine, orchestrator) are free-text columns so new ones need no code change.
"""

import enum


class ModelKind(enum.Enum):
  """Role a model plays in the pipeline."""

  EMBEDDING = "EMBEDDING"
  LLM = "LLM"
  VLM = "VLM"  # vision-language model (image/video understanding)
  RERANKER = "RERANKER"
  OCR = "OCR"
  ASR = "ASR"  # speech-to-text
  OTHER = "OTHER"


class SourceKind(enum.Enum):
  """Kind of system documents are ingested from."""

  OBJECT_STORE = "OBJECT_STORE"
  FILE_SHARE = "FILE_SHARE"
  WEB_CRAWL = "WEB_CRAWL"
  DATABASE = "DATABASE"
  API = "API"
  STREAM = "STREAM"
  SAAS_CONNECTOR = "SAAS_CONNECTOR"
  MANUAL_UPLOAD = "MANUAL_UPLOAD"


class Sensitivity(enum.Enum):
  """Data classification, used to enforce access control at retrieval time."""

  PUBLIC = "PUBLIC"
  INTERNAL = "INTERNAL"
  CONFIDENTIAL = "CONFIDENTIAL"
  RESTRICTED = "RESTRICTED"


class ChunkUnit(enum.Enum):
  """Unit in which a chunking strategy measures chunk size and overlap."""

  TOKENS = "TOKENS"
  CHARACTERS = "CHARACTERS"
  SENTENCES = "SENTENCES"
  PARAGRAPHS = "PARAGRAPHS"
  PAGES = "PAGES"
  SECONDS = "SECONDS"
  FRAMES = "FRAMES"


class ChunkingMethod(enum.Enum):
  """Algorithm used to split content into chunks."""

  FIXED_SIZE = "FIXED_SIZE"
  RECURSIVE = "RECURSIVE"
  SEMANTIC = "SEMANTIC"
  SLIDING_WINDOW = "SLIDING_WINDOW"
  LAYOUT_AWARE = "LAYOUT_AWARE"  # headings, tables, figures
  PAGE = "PAGE"
  SCENE = "SCENE"  # video shot / scene detection
  SPEAKER_TURN = "SPEAKER_TURN"  # audio diarization


class RetrievalMode(enum.Enum):
  """Retrieval approach of a retrieval strategy."""

  DENSE = "DENSE"
  SPARSE = "SPARSE"  # BM25 / SPLADE style lexical search
  HYBRID = "HYBRID"  # dense + sparse
  MULTI_VECTOR = "MULTI_VECTOR"  # late interaction (ColBERT / ColPali style)
  GRAPH = "GRAPH"


class FusionMethod(enum.Enum):
  """How scores from several retrievers are combined."""

  NONE = "NONE"
  RRF = "RRF"  # reciprocal rank fusion
  WEIGHTED_SUM = "WEIGHTED_SUM"
  LEARNED = "LEARNED"


class IndexType(enum.Enum):
  """Approximate-nearest-neighbour index structure."""

  FLAT = "FLAT"
  HNSW = "HNSW"
  IVF_FLAT = "IVF_FLAT"
  IVF_PQ = "IVF_PQ"
  DISKANN = "DISKANN"
  SCANN = "SCANN"


class DistanceMetric(enum.Enum):
  """Similarity / distance function of a vector index."""

  COSINE = "COSINE"
  DOT_PRODUCT = "DOT_PRODUCT"
  EUCLIDEAN = "EUCLIDEAN"
  HAMMING = "HAMMING"


class Quantization(enum.Enum):
  """Vector compression applied inside an index."""

  NONE = "NONE"
  SCALAR_INT8 = "SCALAR_INT8"
  PRODUCT = "PRODUCT"
  BINARY = "BINARY"


class TableFormat(enum.Enum):
  """Open table format of a lakehouse table."""

  DELTA = "DELTA"
  ICEBERG = "ICEBERG"
  HUDI = "HUDI"
  PARQUET = "PARQUET"


class MedallionLayer(enum.Enum):
  """Medallion-architecture layer of a lakehouse table."""

  BRONZE = "BRONZE"  # raw, as ingested
  SILVER = "SILVER"  # cleaned, parsed, chunked
  GOLD = "GOLD"  # curated, serving-ready


class PipelineStage(enum.Enum):
  """What a pipeline does in the RAG data lifecycle."""

  INGEST = "INGEST"
  PARSE = "PARSE"
  CHUNK = "CHUNK"
  EMBED = "EMBED"
  INDEX = "INDEX"
  EVALUATE = "EVALUATE"
  MAINTENANCE = "MAINTENANCE"  # compaction, vacuum, re-index


class PromptPurpose(enum.Enum):
  """What a prompt template is used for."""

  ANSWER = "ANSWER"
  QUERY_REWRITE = "QUERY_REWRITE"
  SUMMARIZE = "SUMMARIZE"
  CAPTION = "CAPTION"
  CLASSIFY = "CLASSIFY"
  JUDGE = "JUDGE"
  OTHER = "OTHER"


class MetricCategory(enum.Enum):
  """Family of an evaluation metric."""

  RETRIEVAL = "RETRIEVAL"
  GENERATION = "GENERATION"
  SYSTEM = "SYSTEM"


class RunStatus(enum.Enum):
  """Outcome of a pipeline run or of one item processed by a run."""

  PENDING = "PENDING"
  RUNNING = "RUNNING"
  SUCCESS = "SUCCESS"
  PARTIAL = "PARTIAL"
  FAILED = "FAILED"
  SKIPPED = "SKIPPED"
  CANCELLED = "CANCELLED"


class TriggerType(enum.Enum):
  """What started a pipeline run."""

  SCHEDULE = "SCHEDULE"
  MANUAL = "MANUAL"
  EVENT = "EVENT"
  BACKFILL = "BACKFILL"


class Channel(enum.Enum):
  """Entry point a RAG request came through."""

  WEB = "WEB"
  API = "API"
  CHAT = "CHAT"
  BATCH = "BATCH"
  EVALUATION = "EVALUATION"


class RequestStatus(enum.Enum):
  """Outcome of a RAG request."""

  SUCCESS = "SUCCESS"
  NO_CONTEXT = "NO_CONTEXT"  # nothing relevant retrieved
  BLOCKED = "BLOCKED"  # stopped by a guardrail
  TIMEOUT = "TIMEOUT"
  ERROR = "ERROR"


class Sentiment(enum.Enum):
  """Thumbs-up / thumbs-down feedback."""

  UP = "UP"
  DOWN = "DOWN"


class FeedbackLabel(enum.Enum):
  """Reason attached to user feedback on an answer."""

  HELPFUL = "HELPFUL"
  INCORRECT = "INCORRECT"
  INCOMPLETE = "INCOMPLETE"
  IRRELEVANT_SOURCES = "IRRELEVANT_SOURCES"
  HALLUCINATION = "HALLUCINATION"
  UNSAFE = "UNSAFE"
  OTHER = "OTHER"
