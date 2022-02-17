djehuty
=========

This Python package provides functionality to extract metadata from Figshare
to gather statistical insights.  Its further goal is to function as a
local API testing endpoint.

## Development setup

To create a development environment, use the following snippet:
```bash
virtualenv --python python3.6 djehuty-env
. djehuty-env/bin/activate
cd /path/to/the/repository/checkout/root
pip install -r requirements.txt
```

### Interactive development

To get an interactive development environment, use:
```python
cp setup.cfg.in setup.cfg
sed -i 's/@VERSION@/0.0.1/g' setup.cfg
pip install --editable .
djehuty web -d -r
```

## Deploy

### PyInstaller

Create a portable executable with:

```bash
pip install pyinstaller
pyinstaller -s -F --onefile --add-data "src/djehuty/web/resources:djehuty/web/resources" main.py -n djehuty
```

On Windows, use:

```bash
pip install pyinstaller
pyinstaller -F --onefile --add-data "src/djehuty/web/resources;djehuty/web/resources" main.py -n djehuty
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

Use the `maximum-workers` configuration option to use forking rather than threading.

### Using `uwsgi`:

On EL7, install `uwsgi` and `uwsgi-plugin-python36`.

```bash
uwsgi --plugins-dir /usr/lib64/uwsgi --need-plugin python36,http --http :8080 --wsgi-file src/djehuty/web/ui.py -H <path-to-your-virtualenv-root> --env DJEHUTY_CONFIG_FILE=config.xml --master --processes 4 --threads 2
```
