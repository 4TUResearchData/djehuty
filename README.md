djehuty
=========

This Python package provides the repository system for 4TU.ResearchData.

## Develop

To create a development environment, use the following snippet:
```bash
python -m venv djehuty-env
. djehuty-env/bin/activate
cd /path/to/the/repository/checkout/root
pip install -r requirements.txt
```

Note: On Windows Powershell, replace `. djehuty-env/bin/activate` with
`djehuty-env\Scripts\Activate.ps1`.

### Interactive development

To get an interactive development environment, use:
```python
sed -e 's/@VERSION@/0.0.1/g' pyproject.toml.in > pyproject.toml
pip install --editable .
cp etc/djehuty/djehuty-example-config.xml djehuty.xml
djehuty web --config-file djehuty.xml
```

Note: On Windows, instead of the `sed` command, copy `pyproject.toml.in`
to `pyproject.toml` and change the version from `@VERSION@` to `0.0.1`.

#### Keeping your development environment up-to-date

To update packages in the virtual environment, use the following command
inside an activated virtual environment:
```bash
pip freeze | grep -v "djehuty.git" | cut -d= -f1 | xargs -n1 pip install -U
```

### Setting up the database

Djehuty needs a SPARQL 1.1 endpoint such as
[Virtuoso OSE](https://github.com/openlink/virtuoso-opensource) or
[Jena Fuseki](https://jena.apache.org/documentation/fuseki2/) to
store its state.

### First run

Upon first run, `djehuty` needs to initialize the database with categories,
licences and accounts.  To do so, pass the `--initialize` option to the
`djehuty web` command:

```bash
djehuty web --initialize --config djehuty.xml
```

## Deploy

### PyInstaller

Create a portable executable with:

```bash
pip install pyinstaller
pyinstaller --onefile \
            --hidden-import=_cffi_backend \
            --add-data "src/djehuty/web/resources:djehuty/web/resources" \
            --name djehuty \
            main.py
```

On Windows, use:

```bash
pip install pyinstaller
pyinstaller --onefile \
            --hidden-import=_cffi_backend \
            --add-data="src/djehuty/web/resources;djehuty/web/resources" \
            --icon="src/djehuty/web/resources/static/images/favicon.ico" \
            --name=djehuty \
            main.py
```

#### Tricks when building using WINE

While no support can be provided for this, the following notes may help.
Allegedly, using Python 3.8.6 works well.  Activating the virtual
environment works best from a `cmd.exe`, which can be started using:
```bash
wine cmd
```

### Build an AppImage with Nuitka

```bash
pip install nuitka
nuitka3 --standalone \
        --include-module=rdflib.plugins \
        --include-module=_cffi_backend \
        --include-package-data=djehuty \
        --onefile \
        --linux-onefile-icon="src/djehuty/web/resources/static/images/favicon.png" \
        main.py \
        -o djehuty.appimage
```

### Build RPMs

Building RPMs can be done via the Autotools scripts:

```bash
autoreconf -vif
./configure
make dist-rpm
```

The RPMs will be available under `rpmbuild/RPMS/noarch`.

## Run

### Using the built-in web server

```bash
djehuty web --config-file=djehuty.xml
```

An example of a configuration file can be found in [etc/djehuty/djehuty-example-config.xml](./etc/djehuty/djehuty-example-config.xml).

Use the `maximum-workers` configuration option to use forking rather than threading.

### Using `uwsgi`:

On EL7, install `uwsgi` and `uwsgi-plugin-python36`.

```bash
uwsgi --plugins-dir /usr/lib64/uwsgi --need-plugin python36,http --http :8080 --wsgi-file src/djehuty/web/ui.py -H <path-to-your-virtualenv-root> --env DJEHUTY_CONFIG_FILE=djehuty.xml --master --processes 4 --threads 2
```
