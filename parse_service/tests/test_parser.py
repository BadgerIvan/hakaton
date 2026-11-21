import tempfile
import unittest
from pathlib import Path
import yaml
from app.pipeline import ROOT, run
from app.registry import discover


class ParserTests(unittest.TestCase):
    def test_registry(self):
        registry = discover()
        for ext in ('.txt', '.html', '.docx', '.pdf'):
            self.assertIn(ext, registry)

    def test_demo_parsing(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary)
            written, errors = run(ROOT / 'raw', destination, verbose=False)
            self.assertEqual(errors, 0)
            self.assertEqual(written, 4)
            for ext, filename in [('txt','demo_note'),('html','demo_page'),('docx','demo_document'),('pdf','demo_pages')]:
                output = destination / ext / (filename + '.md')
                self.assertTrue(output.exists(), output)
                text = output.read_text(encoding='utf-8')
                self.assertTrue(text.startswith('---\n'))
                header = yaml.safe_load(text.split('---', 2)[1])
                self.assertEqual(header['source_format'], ext)
                self.assertEqual(header['chunk_strategy'], 'hierarchical')
            self.assertIn('| Тип | Формат |', (destination/'docx/demo_document.md').read_text())
            self.assertIn('## Страница 2', (destination/'pdf/demo_pages.md').read_text())
            self.assertIn('| Формат | Парсер |', (destination/'html/demo_page.md').read_text())
            self.assertNotIn('Повторяющийся футер', (destination/'html/demo_page.md').read_text())
            written2, errors2 = run(ROOT / 'raw', destination, verbose=False)
            self.assertEqual((written2,errors2),(0,0))


if __name__ == '__main__':
    unittest.main()
