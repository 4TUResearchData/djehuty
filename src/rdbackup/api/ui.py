from werkzeug.serving import run_simple
from rdbackup.api import wsgi

def main (address, port, use_debugger=False, use_reloader=False):
    server = wsgi.ApiServer ()
    run_simple (address, port, server,
                use_debugger=use_debugger,
                use_reloader=use_reloader)
