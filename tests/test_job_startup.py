"""A blocked working folder must not crash the desktop window on its first probe."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4
import shutil

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'src'))
try:
    import JuicyCensorApp as ui
except ModuleNotFoundError as error:
    if not error.name.startswith(('PySide6','shiboken6')): raise
    ui=None


@unittest.skipIf(ui is None,'GUI dependencies required')
class JobStartupTests(unittest.TestCase):
    def test_denied_job_file_reports_error_without_starting_worker(self):
        parent=Path(tempfile.gettempdir()).resolve()
        root=parent/('juicy-startup-test-'+uuid4().hex)
        root.mkdir()
        try:
            (root/'runtime.local.json').write_text(json.dumps({'python':sys.executable}),encoding='utf-8')
            messages=[]; badges=[]
            window=SimpleNamespace(process=None,hardware=SimpleNamespace(setText=badges.append),set_status=messages.append)
            with patch.object(ui,'ROOT',root),patch.object(ui,'write_json',side_effect=PermissionError('blocked')):
                ui.MainWindow.start_job(window,{'action':'probe'})
            self.assertIsNone(window.process)
            self.assertEqual(badges,['Needs attention'])
            self.assertIn('Cannot write working files',window.worker_error)
            self.assertEqual(messages,[window.worker_error])
        finally:
            assert root.resolve().parent==parent
            shutil.rmtree(root)
