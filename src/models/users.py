from sqlalchemy import Column, Integer, String, Table
from src.models.base import Base
from src.session import provide_session
from src.engine import engine

class User(Base):
  """An application user (table ``user``).

  The classmethods below manage their own database session through
  ``provide_session``: pass ``session=...`` (by keyword) to run inside an
  existing session, otherwise one is opened, committed and closed for you.

  Attributes:
    id (int): Integer primary key.
    name (str | None): Name of the user. The column is nullable.
  """

  __tablename__ = 'user'
  __table_args__ = {}
  # __table__ = Table(
  #   'user',
  #   Base.metadata,
  #   autoload=True,
  #   autoload_with=engine
  # )

  id = Column(Integer, primary_key=True)
  name = Column(String)

  @classmethod
  @provide_session
  def create(cls, name, session=None):
    """Insert a new user.

    Args:
      name (str): Name for the new user.
      session (Session, optional): Session to add the user to, passed by
        keyword. When omitted, a session is opened and committed automatically.

    Returns:
      None: ``Session.add`` returns nothing, so the new user (and its generated
      ``id``) is not handed back.

    Note:
      With a caller-supplied session the user is only added to it. Sessions
      here use ``autoflush=False``, so nothing is written until you flush or
      commit.
    """
    user = User(name=name)
    return session.add(user)

  @classmethod
  @provide_session
  def get(cls, user_id, session=None):
    """Look up a user's name by id.

    Args:
      user_id (int): Primary key of the user to look up.
      session (Session, optional): Session to query with, passed by keyword.
        When omitted, a session is opened and closed automatically.

    Returns:
      sqlalchemy.engine.Row | None: A one-column row ``(name,)`` for the
      matching user, or ``None`` if no user has that id. This is the name only,
      not a ``User`` instance.
    """
    return session.query(User.name).filter(User.id == user_id).first()

  @classmethod
  @provide_session
  def all(cls, session=None):
    """Return every user.

    Args:
      session (Session, optional): Session to query with, passed by keyword.
        When omitted, a session is opened and closed automatically.

    Returns:
      list[User]: All rows of the ``user`` table, in no guaranteed order. The
      instances stay readable after the session is closed because sessions are
      created with ``expire_on_commit=False``.
    """
    print(dir(cls))
    return session.query(cls).all()
