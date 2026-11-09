"""Public release metadata must work without launching the GUI or a game."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import renpy_walkthrough_studio as studio


class ReleaseMetadataTests(unittest.TestCase):
    def test_version_has_an_explicit_beta_identifier(self):
        self.assertRegex(studio.__version__, r'^\d+\.\d+\.\d+(?:b\d+|rc\d+)?$')

    def test_version_exits_without_gui_or_game_processing(self):
        output = io.StringIO()
        with patch.object(sys, 'argv', ['studio', '--version']), redirect_stdout(output), \
                patch.object(studio, 'RenpyWalkthroughApp') as gui, \
                patch.object(studio, 'run_cli_mode') as process:
            with self.assertRaises(SystemExit) as status:
                studio.main()
        self.assertEqual(status.exception.code, 0)
        self.assertIn(studio.__version__, output.getvalue())
        self.assertIn("Ren'Py Walkthrough Studio", output.getvalue())
        gui.assert_not_called()
        process.assert_not_called()

    def test_cli_help_includes_version_switch(self):
        output = io.StringIO()
        with patch.object(sys, 'argv', ['studio', '--help']), redirect_stdout(output):
            with self.assertRaises(SystemExit) as status:
                studio.main()
        self.assertEqual(status.exception.code, 0)
        self.assertIn('--version', output.getvalue())


if __name__ == '__main__':
    unittest.main()
