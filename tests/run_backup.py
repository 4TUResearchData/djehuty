"""
This module contains a test that runs the back-up tool to retrieve data
from a running instance.
"""

import os
import unittest
import djehuty.backup.ui as backup_ui

ACCOUNT_ID = os.getenv("DJEHUTY_ACCOUNT_ID")
TOKEN      = os.getenv("DJEHUTY_TEST_TOKEN")
BASE_URL   = "http://127.0.0.1:8080/v2"

class TestRunBackup(unittest.TestCase):
    """Class to run the backup tool in itself."""

    def __init__(self, *args, **kwargs):
        super(TestRunBackup, self).__init__(*args, **kwargs)

    ## Create and destroy
    ## ------------------------------------------------------------------------
    def test_run_backup (self):
        """Runs the back-up tool and tests whether it reaches the end."""
        result = backup_ui.main (TOKEN, "-", ACCOUNT_ID, BASE_URL)
        self.assertTrue (result)
