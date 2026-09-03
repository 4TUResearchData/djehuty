"""FastAPI API layer for djehuty.

A validated, documented, AS-IS reimplementation of the API endpoints served by
the legacy ``djehuty.web.wsgi`` application. The app itself is assembled by
``djehuty.application``; this package holds the routers, models, services,
dependencies and exception handlers. It never imports the legacy WSGI app.
"""
