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
