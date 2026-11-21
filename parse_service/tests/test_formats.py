import gzip
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from app.pipeline import run
from app.detection import detect

class FormatTests(unittest.TestCase):
    def test_other_signatures_collisions_and_reporting(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw=Path(tmp)/'raw/other';raw.mkdir(parents=True);out=Path(tmp)/'parsed'
            (raw/'a.txt').write_text('Обычный текст для проверки')
            (raw/'a.md').write_text('# Другой документ')
            (raw/'unknown.xyz').write_text('Читаемый документ с неизвестным расширением')
            (raw/'data.json').write_text('{"продукт":"ЦФТ","параметры":[1,2]}')
            (raw/'binary.dat').write_bytes(b'\x00\x01\x02\xff')
            (raw/'hidden.txt').write_text('не индексировать')
            (raw/'hidden.txt.meta.json').write_text('{"include_in_rag":false}')
            (raw/'image.fake').write_bytes(b'%PDF-1.4\ninvalid')
            self.assertEqual(detect(raw/'image.fake'),'.pdf')
            (raw/'image.fake').unlink()
            self.assertEqual(run(raw.parent,out,verbose=False),(4,0))
            self.assertTrue((out/'other/a.txt.md').exists())
            self.assertTrue((out/'other/a.md.md').exists())
            stats=json.loads((Path(tmp)/'registry/parsing_summary.json').read_text())
            self.assertEqual(stats['unsupported'],1)
            self.assertEqual(stats['excluded'],1)
            self.assertEqual(stats['ignored_metadata_and_hidden'],1)
            self.assertEqual(run(raw.parent,out,verbose=False),(0,0))

    def test_structured_office_archives(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw=Path(tmp)/'raw';raw.mkdir();out=Path(tmp)/'parsed'
            (raw/'a.csv').write_text('Имя;Число\nЦФТ;42')
            (raw/'a.yaml').write_text('продукт: ЦФТ\nверсия: 2')
            (raw/'a.xml').write_text('<root><product>ЦФТ</product></root>')
            (raw/'a.jsonl').write_text('{"id":1}\n{"id":2}\n')
            (raw/'a.css').write_text('body { color: black; }')
            (raw/'a.rtf').write_bytes(b'{\\rtf1\\ansi Hello RTF}')
            from openpyxl import Workbook
            b=Workbook();b.active.append(['Продукт','Версия']);b.active.append(['ЦФТ',2]);b.save(raw/'book.bin')
            from pptx import Presentation
            p=Presentation();slide=p.slides.add_slide(p.slide_layouts[1]);slide.shapes.title.text='ЦФТ презентация';p.save(raw/'slides.bin')
            with zipfile.ZipFile(raw/'archive.zip','w') as z:
                z.writestr('document.txt','Документ внутри архива')
                z.writestr('../escape.txt','не должен извлекаться')
                z.writestr('binary.dat',b'\x00\x01')
            (raw/'compressed.gz').write_bytes(gzip.compress('Сжатый текст'.encode()))
            self.assertEqual(run(raw,out,verbose=False),(10,0))
            text=(out/'archive.zip.md').read_text()
            self.assertIn('Документ внутри архива',text)
            self.assertIn('небезопасный путь',text)
            self.assertIn('ЦФТ',(out/'book.bin.md').read_text())
            self.assertIn('ЦФТ презентация',(out/'slides.bin.md').read_text())

    def test_odt_and_epub_with_unknown_extensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw=Path(tmp)/'raw';raw.mkdir();out=Path(tmp)/'parsed'
            with zipfile.ZipFile(raw/'text.unknown','w') as z:
                z.writestr('mimetype','application/vnd.oasis.opendocument.text')
                z.writestr('content.xml','<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"><text:p>ODT документ</text:p></office:document>')
            with zipfile.ZipFile(raw/'book.unknown','w') as z:
                z.writestr('mimetype','application/epub+zip')
                z.writestr('META-INF/container.xml','<container><rootfiles><rootfile full-path="book.opf"/></rootfiles></container>')
                z.writestr('book.opf','<package><manifest><item id="a" href="a.html"/></manifest><spine><itemref idref="a"/></spine></package>')
                z.writestr('a.html','<html><body><h1>EPUB</h1><p>Текст книги</p></body></html>')
            self.assertEqual(run(raw,out,verbose=False),(2,0))
            self.assertIn('ODT документ',(out/'text.unknown.md').read_text())
            self.assertIn('Текст книги',(out/'book.unknown.md').read_text())

    @unittest.skipUnless(__import__('shutil').which('tesseract'),'Tesseract is not installed')
    def test_image_and_scanned_pdf_ocr(self):
        from PIL import Image,ImageDraw,ImageFont
        import fitz
        with tempfile.TemporaryDirectory() as tmp:
            raw=Path(tmp)/'raw';raw.mkdir();out=Path(tmp)/'parsed'
            image=Image.new('RGB',(1000,200),'white')
            font=ImageFont.truetype('DejaVuSans.ttf',60)
            ImageDraw.Draw(image).text((30,40),'HELLO CFT 123',font=font,fill='black')
            image.save(raw/'image.png')
            pdf=fitz.open();page=pdf.new_page(width=500,height=100);page.insert_image(page.rect,filename=str(raw/'image.png'));pdf.save(raw/'scan.pdf');pdf.close()
            self.assertEqual(run(raw,out,verbose=False),(2,0))
            self.assertIn('CFT',(out/'image.png.md').read_text())
            self.assertIn('CFT',(out/'scan.pdf.md').read_text())

if __name__=='__main__':unittest.main()

