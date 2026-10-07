"""HTML UI views served by the new FastAPI stack.

The first template-rendering route group to move off the legacy Werkzeug app.
The shared page renderer in ``rendering`` reproduces the legacy
``layout.html`` context so migrated pages stay byte-identical; later UI groups
reuse it. Nothing here imports ``djehuty.web.wsgi``.
"""
