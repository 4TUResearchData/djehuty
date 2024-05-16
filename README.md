# djehuty

This Python package provides the repository system for 4TU.ResearchData.

## Develop

First, create the virtual environment (here we name it `djehuty-env`)

```bash
python -m venv djehuty-env
```

Then, activate the environment created above.

On Linux/Mac:

```bash
. djehuty-env/bin/activate
```

<details>
<summary>On Windows PowerShell</summary>

On Windows PowerShell:

```bash
djehuty-env\Scripts\Activate.ps1
```

</details>

Then, go to the repository directory, and install the required Python packages.

```bash
cd /path/to/the/repository/checkout/root
pip install -r requirements.txt
```

### Interactive development

To get an interactive development environment, make the repository as a Python project and install it in the editable mode.

First, create the `pyproject.toml` file by copying the example in the root folder:

```bash
sed -e 's/@VERSION@/0.0.1/g' pyproject.toml.in > pyproject.toml
```

<details>
<summary>On Windows</summary>

On Windows, copy the `pyproject.toml.in` file as `pyproject.toml` and change the version from `@VERSION@` to `0.0.1`

</details>

Install the current package `djehuty` in the editable mode

```bash
pip install --editable .
```

Copy the example config file to the root folder as `djehuty.xml`. This file is ignored by default.

```bash
cp etc/djehuty/djehuty-example-config.xml djehuty.xml
```

Run the app with the config file

```bash
djehuty web --config-file djehuty.xml
```

### Editing the config file

For developing, it's best to set yourself as an admin and get all rights. To do so, you can edit the `<authentication>` and `<privileges>` tags in the config file as below:

```xml
<!-- ... -->
  <authentication>
    <automatic-login-email>YOUR_EMAIL@example.com</automatic-login-email>
  </authentication>

  <privileges>
    <account email="YOUR_EMAIL@example.com" orcid="xxxx-xxxx-xxxx-xxxx">
      <may-administer>1</may-administer>
      <may-impersonate>1</may-impersonate>
      <may-review>1</may-review>
      <may-run-sparql-queries>1</may-run-sparql-queries>
    </account>
  </privileges>
  <!-- ... -->
```

### Setting up the database

Djehuty needs SPARQL-compatible database to run, such as Virtuoso or Jena Fuseki.

You can run a docker container such as
openlink/virtuoso-opensource-7
secoresearch/fuseki

Forward the port to 8890.

Login to the database Admin panel to create a dataset for djehuty named `sparql`. (new dataset -> create dataset named `sparql`)

To use the app, we need to initialize / seed the database. To do so, run:

```bash
djehuty web --initialize --config djehuty.xml
```

Doing so will create `.djehuty-initialized` file on root to signal that the database was seeded.

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
Alledgedly, using Python 3.8.6 works well. Activating the virtual
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
