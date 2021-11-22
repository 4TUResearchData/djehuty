rdbackup
=========

This Python package provides functionality to extract metadata from Figshare
to gather statistical insights.  Its further goal is to function as a
local API testing endpoint.

## Development setup



### Working on the API server

To get an interactive development environment, use:
```python
pip install --editable .
rdbackup api -d -r
```

## Deploy

Create a portable executable with:

```
pip install pyinstaller
pyinstaller -s -F --onefile --add-data "src/rdbackup/api/resources:rdbackup/api/resources" main.py -n rdbackup
```

On Windows, use:

```
pip install pyinstaller
pyinstaller -F --onefile --add-data "src/rdbackup/api/resources;rdbackup/api/resources" main.py -n rdbackup
```
