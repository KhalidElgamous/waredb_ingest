"""Building blocks shared by the data-warehouse models.

* ``BigInt``: 64-bit integer type for surrogate keys of high-volume tables.
* ``enum_type``: portable, evolvable enum column type.
* ``CreatedAtMixin``: adds a server-populated ``created_at`` audit column.
"""

from sqlalchemy import BigInteger, Column, DateTime, Enum, Integer, func

# SQLite only auto-numbers a column declared exactly as ``INTEGER PRIMARY KEY``,
# so on SQLite the 64-bit type degrades to a plain INTEGER (which is 64-bit
# there anyway). Every other database gets a real BIGINT.
BigInt = BigInteger().with_variant(Integer, "sqlite")


def enum_type(enum_cls, length=32):
  """Build a portable column type for a Python ``enum.Enum``.

  The values are stored by member name in a plain ``VARCHAR(length)`` instead of
  a native database ENUM, and no CHECK constraint is created. Adding a member
  therefore needs no schema change (no ``ALTER TYPE`` on PostgreSQL), downgrades
  leave no orphaned enum types behind, and every database behaves the same.
  Unknown values are still rejected on the Python side (``validate_strings``).

  Args:
    enum_cls (type[enum.Enum]): Enum class whose member names are stored.
    length (int, optional): Width of the ``VARCHAR`` column. Defaults to 32.

  Returns:
    sqlalchemy.Enum: Column type to pass to ``Column(...)``.
  """
  return Enum(enum_cls, native_enum=False, length=length, validate_strings=True)


class CreatedAtMixin:
  """Mixin that adds a ``created_at`` audit timestamp.

  Attributes:
    created_at (datetime): Timezone-aware insertion time, filled in by the
      database (``now()``) so that bulk and raw-SQL loads get it too.
  """

  created_at = Column(
    DateTime(timezone=True), nullable=False, server_default=func.now()
  )
