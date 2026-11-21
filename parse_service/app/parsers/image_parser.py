import shutil
import subprocess
import tempfile
from pathlib import Path
from .base import BaseParser,ParseResult

def ocr(image):
    if not shutil.which('tesseract'):raise RuntimeError('Для OCR установите tesseract-ocr и языки rus/eng')
    languages=subprocess.run(['tesseract','--list-langs'],capture_output=True,text=True,timeout=20,check=True).stdout.splitlines()
    selected=[x for x in ('rus','eng') if x in languages]
    if not selected:raise RuntimeError('Нет языков OCR rus/eng')
    with tempfile.TemporaryDirectory() as tmp:
        file=Path(tmp)/'page.png';image.convert('RGB').save(file)
        result=subprocess.run(['tesseract',str(file),'stdout','-l','+'.join(selected)],capture_output=True,text=True,timeout=120,check=True)
    return result.stdout.strip()

class ImageParser(BaseParser):
    extensions=('.image','.png','.jpg','.jpeg','.tif','.tiff','.bmp','.gif','.webp')
    def parse(self,path):
        from PIL import Image,ImageSequence
        pages=[]
        with Image.open(path) as image:
            for n,frame in enumerate(ImageSequence.Iterator(image),1):
                if n>100:raise ValueError('Изображение содержит больше 100 кадров')
                if frame.width*frame.height>40000000:raise ValueError('OCR: изображение больше 40 мегапикселей')
                text=ocr(frame)
                if text:pages.append(f'## Изображение {n}\n\n{text}')
        if not pages:raise ValueError('OCR не обнаружил текст')
        return ParseResult('\n\n'.join(pages),title=path.stem,pages=len(pages),warnings=['Текст получен OCR; возможны ошибки распознавания'])
