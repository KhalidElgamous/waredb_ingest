"""Shared SQLAlchemy engine for the warehouse database.

Reads the connection URL from the ``SQL_ALCHEMY_CONN`` environment variable
(a ``.env`` file in this directory or any parent directory is loaded first;
variables already set in the environment take precedence) and exposes a single
module-level ``engine`` that the rest of the package shares.

Importing this module raises ``KeyError`` if ``SQL_ALCHEMY_CONN`` is not set.
"""

from dotenv import load_dotenv
from sqlalchemy import create_engine

import os

load_dotenv()

SQL_ALCHEMY_CONN = os.environ['SQL_ALCHEMY_CONN']

engine = create_engine(SQL_ALCHEMY_CONN, echo=False)
