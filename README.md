djehuty
=========

This Python package provides the repository system for 4TU.ResearchData and Nikhef.

## Reporting (potential) security issues

For security-related matters, please e-mail
[security@djehuty.4tu.nl](mailto:security@djehuty.4tu.nl).  This will only
reach the security teams at 4TU.ResearchData and Nikhef.

## Creating a development environment

This project uses the GNU autotools build system.

### GNU/Linux

For development on GNU/Linux we recommend installing `git`, `autoconf`,
`automake` and `make` through your system's package manager, followed by
creating a Python virtual environment for `djehuty`:

```bash
git clone https://github.com/4TUResearchData/djehuty.git && cd djehuty/
autoreconf -if && ./configure
python -m venv ../djehuty-env
. ../djehuty-env/bin/activate
pip install --upgrade pip
pip install --requirement requirements.txt
pip install --editable .
```

#### Keeping your development environment up-to-date

Because the virtual environment isn't updated by your system's package
manager, you can use the following snippet to update packages inside your
virtual environment:
```bash
pip freeze | grep -v "djehuty.git" | cut -d= -f1 | xargs -n1 pip install -U
```

### macOS X

For development on Apple's macOS X, we recommend installing `python3`, `git`,
`autoconf`, `automake`, and `make` through [homebrew](https://brew.sh/),
followed by creating a Python virtual environment for `djehuty`:

```bash
brew install python3 git autoconf automake make
git clone https://github.com/4TUResearchData/djehuty.git && cd djehuty/
autoreconf -if && ./configure
python3 -m venv ../djehuty-env
. ../djehuty-env/bin/activate
pip install --upgrade pip
pip install --requirement requirements.txt
pip install --editable .
```

#### Keeping your development environment up-to-date

Because the virtual environment isn't updated by homebrew, you can use the
following snippet to update packages inside your virtual environment:
```bash
pip freeze | grep -v "djehuty.git" | cut -d= -f1 | xargs -n1 pip install -U
```

### Microsoft Windows

For development on Windows we recommend [MSYS2](https://www.msys2.org/)
and the following approach to installing packages:
```bash
PREFIX="mingw-w64-x86_64-" # See https://www.msys2.org/docs/package-naming
pacman -Suy git autoconf automake make ${PREFIX}python \
            ${PREFIX}python-pygit2 ${PREFIX}python-rdflib \
            ${PREFIX}python-jinja ${PREFIX}python-requests \
            ${PREFIX}python-werkzeug ${PREFIX}python-defusedxml \
            ${PREFIX}python-pillow ${PREFIX}python-build \
            ${PREFIX}python-setuptools
git clone https://github.com/4TUResearchData/djehuty.git && cd djehuty/
autoreconf -if && ./configure
# If you chose a different PREFIX above, change /mingw64 accordingly below.
# See: https://www.msys2.org/docs/environments
/mingw64/bin/python -m venv --system-site-packages ../djehuty-env
. ../djehuty-env/bin/activate
pip install --editable .
```

#### Keeping your development environment up-to-date

The dependencies for `djehuty` are installed via `pacman`, so to update those
packages use the following snippet:
```bash
pacman -Suy
```

See [Updating MSYS2](https://www.msys2.org/docs/updating/) for more details.

### Verify that the installation works
Upon completing the installation, you should be able to run:
```bash
djehuty --help
```

## Setting up the database

Djehuty needs a SPARQL 1.1 endpoint such as
[Virtuoso OSE](https://github.com/openlink/virtuoso-opensource) or
[Jena Fuseki](https://jena.apache.org/documentation/fuseki2/) to
store its state.

## Run the web service

To start the web service, we recommend copying the
[example configuration](./etc/djehuty/djehuty-example-config.xml)
and go from there:

```python
cp etc/djehuty/djehuty-example-config.xml djehuty.xml
```

### First run

Upon first run, `djehuty` needs to initialize the database with categories,
licences and accounts.  To do so, pass the `--initialize` option to the
`djehuty web` command:

```bash
djehuty web --initialize --config-file djehuty.xml
```

### Subsequent runs

After the database has been initialized, you can remove the `--initialize`
option:
```bash
djehuty web --config-file=djehuty.xml
```
