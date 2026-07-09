{%
  include-markdown "../../CONTRIBUTING.md"
  heading-offset=0
%}

## Development environment

{%
  include-markdown "../../README.md"
  start="## Development environment"
  end="## Running in production"
  heading-offset=0
%}

## Navigating the source code

This section traces the path from invoking `djehuty` to responding to an HTTP
request.

### Starting point

Because `djehuty` is installable as a Python package, the starting point can be
found in `pyproject.toml`:

```toml
[project.scripts]
djehuty = "djehuty.ui:main"
```

The tour starts at [src/djehuty/ui.py](https://github.com/4TUResearchData/djehuty/blob/main/src/djehuty/ui.py) in the
procedure called `main`.

### How `djehuty` initializes

The `main` procedure calls `main_inner`, which handles the command-line
arguments. When invoking `djehuty web`, the following snippet handles it:

```python
import djehuty.web.ui as web_ui
...
if args.command == "web":
    web_ui.main (args.config_file, True, 
                 args.initialize, args,
                 extract_transactions_from_log,
                 args.apply_transactions)
```

The entry-point for the `web` subcommand is found in
[src/djehuty/web/ui.py](https://github.com/4TUResearchData/djehuty/blob/main/src/djehuty/web/ui.py) at the `main` procedure.

This procedure sets up an instance of `WebServer` (found in
[src/djehuty/web/wsgi.py](https://github.com/4TUResearchData/djehuty/blob/main/src/djehuty/web/wsgi.py)) and uses
`werkzeug`'s `run_simple` to start the web server.

### Translating URI paths to internal procedures

An instance of `WebServer` is passed along in werkzeug's `run_simple`
procedure. Werkzeug calls the instance directly, which is handled by the
`__call__` procedure of the `WebServer` class. The `__call__` procedure
invokes its `wsgi` instance, configured as follows:

```python
self.wsgi = SharedDataMiddleware(self.__respond, self.static_roots)
```

The `__respond` procedure calls `__dispatch_request`, where the requested URI
is translated into a procedure name using the `url_map`. Except for static
resources in `src/djehuty/web/resources` and pre-configured static pages, URIs
are handled by a procedure in the `WebServer` instance.

The mapping between URIs and their handler procedures can be found in the
`url_map` defined in the `WebServer` class in
[src/djehuty/web/wsgi.py](https://github.com/4TUResearchData/djehuty/blob/main/src/djehuty/web/wsgi.py).

### Diving into the code that displays the homepage

As an example, the `url_map` contains:

```python
R("/", self.ui_home),
```

`self` is a reference to a `WebServer` instance, so we look for a procedure
called `ui_home` inside that class. Most code editors have a "go to definition"
feature to help navigate.

`ui_home` gathers summary numbers from the SPARQL endpoint:

```python
summary_data = self.db.repository_statistics()
```

And a list of the latest datasets:

```python
records = self.db.latest_datasets_portal(30)
```

It then passes that information to `__render_template`, which renders
`portal.html` from
[src/djehuty/web/resources/html_templates](https://github.com/4TUResearchData/djehuty/tree/main/src/djehuty/web/resources/html_templates)
using [Jinja](https://jinja.palletsprojects.com/en/3.1.x/):

```python
return self.__render_template (request, "portal.html",
                               summary_data = summary_data,
                               latest = records, ...)
```

### Database communication

In `ui_home`, we found a call to `self.db.repository_statistics`. To find
where `self.db` is assigned:

```python
self.db = database.SparqlInterface()
```

And where `database` comes from:

```python
from djehuty.web import database
```

This leads to
[src/djehuty/web/database.py](https://github.com/4TUResearchData/djehuty/blob/main/src/djehuty/web/database.py).

In `repository_statistics`, a call to `self.__query_from_template` is followed
by a call to `__run_query`, which sends the query to the SPARQL endpoint and
returns results as a list of Python dictionaries.

`self.__query_from_template` takes the name of a template file (without extension)
containing a SPARQL query. These templates can be found in
[src/djehuty/web/resources/sparql_templates](https://github.com/4TUResearchData/djehuty/tree/main/src/djehuty/web/resources/sparql_templates).
