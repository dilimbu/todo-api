from todo.routers import auth, tasks, admin, reports, health, dashboard

__all__ = ["auth", "tasks", "admin", "reports", "health", "dashboard"]

# __init__.py marks folder as Python package so can be imported from,
# With todo/routers/__init__.py, Python treats routers/ as a package:
# without it (on older / strict layouts), imports could fail:
# from todo.routers import auth
# from todo.routers.tasks import router