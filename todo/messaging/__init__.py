# __init__.py inside todo/messaging/ lets Python treat
#  this folder as a package and not just a random directory
# so imports like these don't fail or behave inconsistently:
# from todo.messaging.outbox import enqueue_outbox
# from todo.messaging import outbox