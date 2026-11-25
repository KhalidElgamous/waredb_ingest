"""Database session helpers.

Defines ``Session``, a thread-local (``scoped_session``) factory bound to
``engine.engine``, and two helpers built on it:

* ``create_session``: context manager that commits on success and rolls back on
  error.
* ``provide_session``: decorator that injects a ``session`` keyword argument
  into the decorated function.

``Session`` is configured with ``autocommit=False``, ``autoflush=False`` and
``expire_on_commit=False``: nothing is written until a flush or commit, and
loaded objects stay readable after the session is committed or closed.
"""

from contextlib import contextmanager
from functools import wraps
from sqlalchemy.orm import scoped_session, sessionmaker

from src.engine import engine

Session = scoped_session(sessionmaker(
  autocommit=False,
  autoflush=False,
  bind=engine,
  expire_on_commit=False
))


@contextmanager
def create_session():
	"""Provide a transactional scope around a block of work.

	Takes a session from the thread-local ``Session`` registry and yields it.
	The session is committed when the block exits normally, rolled back (and the
	exception re-raised) if the block raises, and always closed afterwards.

	Because ``Session`` is a ``scoped_session``, nested calls in the same thread
	receive the *same* underlying session, so an inner block's commit and close
	also affect the outer block's work.

	Yields:
		sqlalchemy.orm.Session: Session bound to the shared engine.

	Raises:
		Exception: Whatever the wrapped block raised, after the rollback.

	Example::

		with create_session() as session:
			session.add(User(name="alice"))
	"""
	session = Session()
	try:
		yield session
		session.commit()
	except Exception:
		session.rollback()
		raise
	finally:
		session.close()

def provide_session(f):
	"""Decorator that supplies ``f`` with a ``session`` keyword argument.

	If the caller passes ``session=...`` it is used as is, and the caller stays
	responsible for committing, rolling back and closing it. Otherwise a session
	is opened with ``create_session`` for the duration of the call: committed
	when ``f`` returns, rolled back if it raises.

	``f``'s return value is produced inside the transaction. Because sessions are
	created with ``expire_on_commit=False``, ORM objects it returns stay readable
	after the session is closed.

	Note:
		``session`` must be passed by keyword. Passing it positionally makes the
		wrapper inject a second one, which raises ``TypeError`` ("got multiple
		values for argument 'session'").

	Args:
		f (Callable): Function that accepts a ``session`` keyword argument.

	Returns:
		Callable: The wrapped function. ``functools.wraps`` preserves ``f``'s name
		and docstring.

	Example::

		@provide_session
		def count_users(session=None):
			return session.query(User).count()

		count_users()                 # opens and commits its own session
		count_users(session=my_sess)  # uses the caller's session
	"""
	@wraps(f)
	def wrapper(*args, **kwargs):
		if "session" in kwargs:
			return f(*args, **kwargs)
		else:
			with create_session() as s:
				return f(*args, session=s, **kwargs)
	return wrapper
