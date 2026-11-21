import json
import tempfile
import unittest
from pathlib import Path
import yaml
from app.pipeline import run
from app.registry import discover

class ParserTests(unittest.TestCase):
    def test_registry(self):
        for ext in ('.txt','.html','.docx','.pdf','.json'):
            self.assertIn(ext,discover())

    def test_html_content_and_changed_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw=Path(tmp)/'raw';raw.mkdir();out=Path(tmp)/'parsed'
            src=raw/'page.html'
            src.write_text('<html><title>ЦФТ</title><header>Меню</header><div class="content"><h1>Платформа</h1><p>Поддержка Linux</p><a href="/support">Сопровождение</a><table><tr><th>ОС</th><th>Тип</th></tr><tr><td>Linux</td><td>Сервер</td></tr></table></div><footer>Мусор</footer></html>')
            side=src.with_name(src.name+'.meta.json')
            side.write_text(json.dumps({'source_url':'https://www.cft.ru/platforms','fetched_at':'2026-11-21T06:00:00Z'}))
            self.assertEqual(run(raw,out,verbose=False),(1,0))
            result=(out/'page.html.md').read_text()
            self.assertIn('https://www.cft.ru/support',result)
            self.assertIn('| ОС | Тип |',result)
            self.assertNotIn('Мусор',result)
            self.assertNotIn('Меню',result)
            self.assertEqual(run(raw,out,verbose=False),(0,0))
            side.write_text(json.dumps({'source_url':'https://www.cft.ru/platforms','category':'updated'}))
            self.assertEqual(run(raw,out,verbose=False),(1,0))
            metadata=yaml.safe_load((out/'page.html.md').read_text().split('---',2)[1])
            self.assertEqual(metadata['category'],'updated')

    def test_catalog_application_title_archived_and_excluded_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw=Path(tmp)/'raw';raw.mkdir();out=Path(tmp)/'parsed'
            src=raw/'application.json'
            src.write_text(json.dumps([{'Title':'Раздел','appTitle':'Приложение','HTMLContent':'<p>Описание</p>',
                                       'HTMLFunction':'<ul><li>Функция</li></ul>','dateendsale1':'Архив','CodeAsvul':'123'}]))
            src.with_name(src.name+'.meta.json').write_text(json.dumps({'catalog_kind':'application','title':'Раздел'}))
            asset=raw/'menu.json';asset.write_text('{}')
            asset.with_name(asset.name+'.meta.json').write_text('{"include_in_rag": false}')
            self.assertEqual(run(raw,out,verbose=False),(1,0))
            text=(out/'application.json.md').read_text()
            self.assertIn('title: Приложение',text)
            self.assertIn('Архив',text)
            self.assertIn('- Функция',text)
            self.assertFalse((out/'menu.json.md').exists())

if __name__=='__main__':unittest.main()
