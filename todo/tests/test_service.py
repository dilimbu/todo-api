"""
Unit tests for TodoService layer (with mocking)
Using explicit mocking for better clarity and reliability.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from todo.schemas import TaskCreate
from todo.service import TodoService

"""
MagicMock = mocks database - fakes database and tables, 
does not know about actual db schema, but it allows to accept 
any method call eg. mock_db.add(), .query() etc.
great for unit testing behavior
"""


# can run test: uv run pytest todo/tests/test_service.py -v --tb=short

@pytest.fixture
def mock_db():
    """Mock SQLAlchemy session"""
    return MagicMock()


@pytest.fixture
def service(mock_db):
    """TodoService with mocked DB session"""
    return TodoService(db=mock_db)


# ====================== get_all() Tests ======================

def test_get_all_pending_tasks(service, mock_db, mocker):
    """Test getting only pending tasks for a user."""
    # Mock query result
    mock_task = MagicMock()
    mock_task.id = 1
    mock_task.title = "Buy milk"  # real str
    mock_task.done = False
    mock_task.created_at = datetime.now(timezone.utc)

    # Simulate full query chain, when we call todoService.get_all(..)
    mock_query = MagicMock()

    mock_db.query.return_value = mock_query  # db.query(TaskModel)
    mock_query.where.return_value = mock_query  # .where(...)
    mock_query.order_by.return_value = mock_query  # .order_by(...)
    mock_query.all.return_value = [mock_task]  # .all()def test_get_all_pending_tasks(service, mock_db, mocker):

    # OR - one-liner (short but hard to read) - simulates the chain: db.query(...).where(...).order_by(..).all()
    # mock_db.query.return_value.where.return_value.order_by.return_value.all.return_value = [mock_task]

    # What this does:
    #
    # mock_db.query → when called, returns another mock
    # .return_value.filter → that mock's .filter returns another mock
    # .return_value.all → that mock's .all returns our test data
    #
    # This mimics the real SQLAlchemy query chain without hitting the database.

    # This line can be simplified as:What this does:
    #
    # mock_db.query → when called, returns another mock
    # .return_value.where → that mock's .where returns another mock
    # .return_value.order_by → does order by
    # .return_value.all → that mock's .all returns our test data
    #
    # This mimics the real SQLAlchemy query chain without hitting the database.
    # Create a mock query object that supports chaining
    # mock_query = mocker.Mock()
    #
    # mock_db.query.return_value = mock_query # When code does: mock_db.query(...)  →  return mock_query
    # mock_query.where.return_value = mock_query  # When code does: mock_query.where(...)  →  return mock_query (same object for chaining)
    # mock_query.order_by.return_value = mock_query   # Same idea for .order_by()
    # mock_query.all.return_value = [mock_task] # When code does: ... .all()  →  return the actual data [mock_task]

    tasks = service.get_all(user_id=2, show_all=False)

    assert len(tasks) == 1
    assert tasks[0].done is False
    assert tasks[0].title == "Buy milk"

    # Assertions to verify behavior
    mock_db.query.assert_called_once()  # ensure query was called
    assert mock_query.where.call_count == 2  # user_id + done
    mock_query.order_by.assert_called_once()  # .order_by() was called?
    mock_query.all.assert_called_once()

    # Step-by-step Timeline:
    #
    # Fixture Creation (before test runs)
    # mock_db fixture runs → creates a fresh MagicMock()
    # service fixture runs → TodoService(db=mock_db)
    # → The service object now holds a reference to this mock DB.
    #
    # Inside the Test Function (when test starts)
    # You set up the query chain on the mock:Pythonmock_query = MagicMock()
    # mock_db.query.return_value = mock_query
    # mock_query.where.return_value = mock_query
    # mock_query.order_by.return_value = mock_query
    # mock_query.all.return_value = [mock_task]
    #
    # When service.get_all() is called
    # The service uses the mock DB it already has.
    # It does self.db.query(...) → returns the mock you prepared.
    # The chain executes and eventually calls .all() → returns your test data.


def test_get_all_including_done(service, mock_db):
    """Test getting all tasks when show_all=True"""
    t1, t2 = MagicMock(), MagicMock()
    t1.id, t1.title, t1.done = 1, "A", False
    t1.created_at = datetime.now(timezone.utc)

    t2.id, t2.title, t2.done = 2, "B", True
    t2.created_at = datetime.now(timezone.utc)

    mock_db.query.return_value.where.return_value.order_by.return_value.all.return_value = [t1, t2]

    tasks = service.get_all(user_id=2, show_all=True)

    assert len(tasks) == 2
    assert tasks[0].title == "A"
    assert tasks[1].done is True


# ====================== create() Tests ======================
def test_create_task(service, mock_db):
    """Test task creation"""
    task_data = TaskCreate(title="Write unit tests")

    created_task = service.create(2, task_data)

    assert created_task.title == "Write unit tests"
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once()


# ====================== mark_done() Tests ======================
def test_mark_done_success(service, mock_db):
    """Test marking existing task as done (owned by this user)."""
    user_id = 2
    task_id = 5

    mock_task = MagicMock()
    mock_task.id = task_id
    mock_task.user_id = user_id
    mock_task.done = False

    # Chain: db.query(TaskModel).where(...).first()
    mock_db.query.return_value.where.return_value.first.return_value = mock_task

    result = service.mark_done(user_id, task_id)

    assert result == mock_task
    assert mock_task.done is True
    mock_db.commit.assert_called_once()
    mock_db.query.assert_called_once()
    mock_db.query.return_value.where.assert_called_once()


def test_mark_done_not_found(service, mock_db):
    """Test marking non-existent task"""
    mock_db.query.return_value.where.return_value.first.return_value = None

    result = service.mark_done(user_id=2, task_id=999)
    assert result is None
    mock_db.commit.assert_not_called()


# ====================== delete() Tests ======================
def test_delete_success(service, mock_db):
    """Test successful deletion"""
    mock_task = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_task

    result = service.delete(user_id=2, task_id=1)

    assert result is True
    mock_db.delete.assert_called_once()
    mock_db.commit.assert_called_once()


def test_delete_not_found(service, mock_db):
    """Test deleting non-existent task"""
    # mock_db.query.return_value.filter.return_value.first.return_value = None
    mock_db.query.return_value.where.return_value.first.return_value = None

    result = service.delete(user_id=2, task_id=999)
    assert result is False
    mock_db.query.return_value.where.assert_called_once()
    # Full equality on SQLAlchemy expressions is awkward; calling once is usually enough.
