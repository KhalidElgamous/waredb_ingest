"""Dimension tables of the data warehouse.

Defines the ``Day`` and ``Month`` enums and the ``datetime_dim`` and
``localisation_dim`` tables.
"""

from sqlalchemy import Column, Integer, Float, Enum
from src.models.base import Base

import enum


class Day(enum.Enum):
  """Day of the week, stored in the database by member name (``MONDAY`` ...)."""

  MONDAY = "MONDAY"
  TUESDAY = "TUESDAY"
  WEDNESDAY = "WEDNESDAY"
  THURSDAY = "THURSDAY"
  FRIDAY = "FRIDAY"
  SATURDAY = "SATURDAY"
  SUNDAY = "SUNDAY"

class Month(enum.Enum):
  """Month of the year, stored in the database by member name (``JANUARY`` ...)."""

  JANUARY = "JANUARY"
  FEBRUARY = "FEBRUARY"
  MARCH = "MARCH"
  APRIL = "APRIL"
  MAY = "MAY"
  JUNE = "JUNE"
  JULY = "JULY"
  AUGUST = "AUGUST"
  SEPTEMBER = "SEPTEMBER"
  OCTOBER = "OCTOBER"
  NOVEMBER = "NOVEMBER"
  DECEMBER = "DECEMBER"

class DatetimeDim(Base):
  """Date and time dimension (table ``datetime_dim``).

  Attributes:
    id (int): Auto-incrementing primary key.
    day (Day | None): Day of the *week* (``Day.MONDAY`` ...), not the day of
      the month.
    month (Month | None): Month of the year.
    year (int | None): Calendar year, e.g. ``2026``.
    hour (int | None): Hour of the day. Nullable, so a row can carry only the
      date part.
    minute (int | None): Minute of the hour. Nullable, like ``hour``.
  """

  __tablename__ = "datetime_dim"

  id = Column(Integer, primary_key=True, autoincrement=True)

  # date part
  day = Column(Enum(Day))
  day_of_month = Column(Integer, nullable=True)
  month = Column(Enum(Month))
  year = Column(Integer)

  # time part
  hour = Column(Integer, nullable=True)
  minute = Column(Integer, nullable=True)

class LocalisationDim(Base):
  """Location dimension (table ``localisation_dim``).

  Attributes:
    id (int): Auto-incrementing primary key.
    lat (float): Latitude of the location. Required.
    long (float): Longitude of the location. Required.
  """

  __tablename__ = "localisation_dim"

  id = Column(Integer, primary_key=True, autoincrement=True)

  lat = Column(Float, nullable=False)
  long = Column(Float, nullable=False)
