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

### Interactive development

To get an interactive development environment, use:
```python
sed -e 's/@VERSION@/0.0.1/g' pyproject.toml.in > pyproject.toml
pip install --editable .
cp etc/djehuty/djehuty-example-config.xml djehuty.xml
djehuty web --config-file djehuty.xml
```

#### Keeping your development environment up-to-date

To update packages in the virtual environment, use the following command
inside an activated virtual environment:
```bash
pip freeze | grep -v "djehuty.git" | cut -d= -f1 | xargs -n1 pip install -U
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
Alledgedly, using Python 3.8.6 works well.  Activating the virtual
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
djehuty web --config-file=config.xml
```

An example of a configuration file can be found in [etc/djehuty/djehuty-example-config.xml](./etc/djehuty/djehuty-example-config.xml).

Use the `maximum-workers` configuration option to use forking rather than threading.

### Using `uwsgi`:

On EL7, install `uwsgi` and `uwsgi-plugin-python36`.

```bash
uwsgi --plugins-dir /usr/lib64/uwsgi --need-plugin python36,http --http :8080 --wsgi-file src/djehuty/web/ui.py -H <path-to-your-virtualenv-root> --env DJEHUTY_CONFIG_FILE=config.xml --master --processes 4 --threads 2
```
