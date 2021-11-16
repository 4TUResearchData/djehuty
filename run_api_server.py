import sys
import os.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src/rdbackup"))

from werkzeug.serving import run_simple
from rdbackup.api import wsgi

if __name__ == '__main__':
    server = wsgi.ApiServer()
    run_simple('127.0.0.1', 8080, server, use_debugger=True, use_reloader=True)
