"""ORM models for the warehouse database.

Importing this package registers every model on the shared ``Base`` metadata,
which is what Alembic's autogenerate inspects (see ``env.py``). A new model must
therefore be imported here, otherwise its table is not detected.

Exports:
    Base: Declarative base class that holds the shared metadata.
    User: Application user (table ``user``).
    DatetimeDim: Date/time dimension (table ``datetime_dim``).
    LocalisationDim: Location dimension (table ``localisation_dim``).
"""

from src.models.base import Base
from src.models.users import User
from src.models.datawarehouse.dimensions import (
  DatetimeDim,
  LocalisationDim,
)
from src.models.datawarehouse.rag_dimensions import (
  ChunkingStrategyDim,
  DocumentDim,
  EvalDatasetDim,
  LakehouseTableDim,
  MetricDim,
  ModalityDim,
  ModelDim,
  PipelineDim,
  PromptTemplateDim,
  RetrievalStrategyDim,
  SourceDim,
  VectorIndexDim,
)
from src.models.datawarehouse.facts import (
  ChunkFact,
  EmbeddingFact,
  EvaluationResultFact,
  FeedbackFact,
  IngestionFact,
  LakehouseSnapshotFact,
  PipelineRunFact,
  QueryFact,
  RetrievalHitFact,
  VectorIndexSnapshotFact,
)

__all__ = [
  'Base',
  'User',
  'DatetimeDim',
  'LocalisationDim',
  'ModalityDim',
  'SourceDim',
  'DocumentDim',
  'ModelDim',
  'ChunkingStrategyDim',
  'RetrievalStrategyDim',
  'VectorIndexDim',
  'LakehouseTableDim',
  'PipelineDim',
  'PromptTemplateDim',
  'MetricDim',
  'EvalDatasetDim',
  'PipelineRunFact',
  'IngestionFact',
  'ChunkFact',
  'EmbeddingFact',
  'QueryFact',
  'RetrievalHitFact',
  'FeedbackFact',
  'EvaluationResultFact',
  'LakehouseSnapshotFact',
  'VectorIndexSnapshotFact',
]
