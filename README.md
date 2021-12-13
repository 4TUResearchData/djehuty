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

### Working on the API server

To get an interactive development environment, use:
```python
pip install --editable .
djehuty api -d -r
```

## Deploy

Create a portable executable with:

```bash
pip install pyinstaller
pyinstaller -s -F --onefile --add-data "src/djehuty/api/resources:djehuty/api/resources" main.py -n djehuty
```

On Windows, use:

```bash
pip install pyinstaller
pyinstaller -F --onefile --add-data "src/djehuty/api/resources;djehuty/api/resources" main.py -n djehuty
```
