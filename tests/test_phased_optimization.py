"""Content-only caches must not cache approval, context or mutable results."""
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import renpy_walkthrough_studio as studio


class BothLexicalCacheTests(unittest.TestCase):
    def setUp(self):
        studio._both_logical_lines_cached.cache_clear()

    def test_same_content_matches_original_lexer_and_is_reused(self):
        lines = ['    $ points += (\n', '        2 # comment\n', '    )\n',
                 '    "Text # not a comment"\n']
        self.assertEqual(studio._both_logical_lines(lines), studio.cs_logical_lines(lines))
        self.assertEqual(studio._both_logical_lines(list(lines)), studio.cs_logical_lines(lines))
        self.assertEqual(studio._both_logical_lines_cached.cache_info().hits, 1)

    def test_mutating_returned_list_cannot_change_next_result(self):
        lines = ['    $ points += 2\n']
        result = studio._both_logical_lines(lines)
        result.clear()
        self.assertEqual(studio._both_logical_lines(lines), studio.cs_logical_lines(lines))

    def test_changed_source_content_does_not_reuse_previous_result(self):
        lines = ['    $ points += 2\n']
        first = studio._both_logical_lines(lines)
        lines[0] = '    $ points -= 2\n'
        second = studio._both_logical_lines(lines)
        self.assertNotEqual(first, second)
        self.assertEqual(second, studio.cs_logical_lines(lines))

    def test_line_partition_is_part_of_cache_key(self):
        first = ['    pass\n', '    return\n']
        second = ['    pass\n    return\n']
        self.assertEqual(''.join(first), ''.join(second))
        self.assertEqual(studio._both_logical_lines(first), studio.cs_logical_lines(first))
        self.assertEqual(studio._both_logical_lines(second), studio.cs_logical_lines(second))
        self.assertEqual(studio._both_logical_lines_cached.cache_info().misses, 2)

    def test_large_input_bypasses_bounded_cache(self):
        lines = ['    pass\n'] * 20001
        self.assertEqual(studio._both_logical_lines(lines), studio.cs_logical_lines(lines))
        self.assertEqual(studio._both_logical_lines_cached.cache_info().currsize, 0)
        self.assertEqual(studio._both_logical_lines_cached.cache_info().maxsize, 32)

    def test_warm_flow_validation_still_stats_every_source(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / 'script.rpy')
            Path(path).write_text('label start:\n    menu:\n        "A":\n            return\n', encoding='utf-8')
            analyzer = SimpleNamespace(rpy_files=[path], labels={'start': (path, 0)})
            menu = SimpleNamespace(file_path=path, line_num=1)
            studio.BothScenePlanner(analyzer)._verify_return_context(menu)
            real_stat = studio.os.stat
            with patch.object(studio.os, 'stat', wraps=real_stat) as stat:
                studio.BothScenePlanner(analyzer)._verify_return_context(menu)
            self.assertEqual(stat.call_count, 1)


class CharacterDiscoveryPrefilterTests(unittest.TestCase):
    def analyze(self, sources):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        paths = []
        for name, source in sources.items():
            path = root / name
            path.write_text(source, encoding='utf-8')
            paths.append(str(path))
        analyzer = studio.RenpyWalkthroughAnalyzer(str(root), options={'read_only': True})
        analyzer.rpy_files = paths
        return analyzer

    def test_explicit_definitions_in_later_files_still_win(self):
        analyzer = self.analyze({
            'a.rpy': '$ nova_love += 1\n$ iris_Trust += 2\n',
            'b.rpy': 'define nova = Character("Explicit Nova")\n',
        })
        with patch.dict(studio.DYNAMIC_CHARACTERS, {}, clear=True):
            real_read = analyzer.get_file_lines
            with patch.object(analyzer, 'get_file_lines', wraps=real_read) as read:
                analyzer.discover_game_characters()
            self.assertEqual(studio.DYNAMIC_CHARACTERS, {'nova': 'Explicit Nova', 'iris': 'Iris'})
            self.assertEqual(read.call_count, 6)  # Preserve pass order, not a merged heuristic.

    def test_object_stat_case_whitespace_and_builtin_filters_unchanged(self):
        analyzer = self.analyze({'script.rpy':
            '$ chloe \t. \tMCAffection += 2\n'
            '$ mira.Love += 1\n'
            '$ ember.affection += 2\n'
            '$ min.Love += 1\n'
            '$ len_points += 1\n'
            '$ Faye_Trust += 1\n'
            '"Quoted rhea_points += 1"\n'
            '$ sylvia.Points\n'
            '$ unknown_points = 1\n'})
        with patch.dict(studio.DYNAMIC_CHARACTERS, {}, clear=True):
            analyzer.discover_game_characters()
            self.assertEqual(studio.DYNAMIC_CHARACTERS,
                             {'chloe': 'Chloe', 'mira': 'Mira', 'faye': 'Faye',
                              'rhea': 'Rhea', 'sylvia': 'Sylvia'})

    def test_gain_variants_keep_original_regex_matches(self):
        source = []
        expected = {}
        for index, suffix in enumerate(('love', 'AFF', 'points', 'Romance', 'like', 'Trust')):
            name = 'unit' + str(index)
            source.append(f'$ {name}_{suffix}\t += 1\n')
            expected[name] = name.capitalize()
        source.extend(['"Ordinary dialogue with punctuation."\n', '$ wrong_love + = 1\n'])
        analyzer = self.analyze({'script.rpy': ''.join(source)})
        with patch.dict(studio.DYNAMIC_CHARACTERS, {}, clear=True):
            analyzer.discover_game_characters()
            self.assertEqual(studio.DYNAMIC_CHARACTERS, expected)


if __name__ == '__main__':
    unittest.main()
