"""Read the actual public CFT JSON responses, not the SPA's empty HTML shell."""
import json
from pathlib import Path
from .base import BaseParser, ParseResult
from .html_parser import extract_markdown


class CatalogJSONParser(BaseParser):
    extensions = ('.json',)

    def parse(self, path: Path) -> ParseResult:
        sidecar = path.with_name(path.name + '.meta.json')
        meta = json.loads(sidecar.read_text(encoding='utf-8')) if sidecar.exists() else {}
        if meta.get('catalog_kind') not in ('overview','application','product'):
            from .structured_parser import render, read_text
            return ParseResult(markdown=render(json.loads(read_text(path))),title=path.stem)
        records = json.loads(path.read_bytes())
        if not isinstance(records,list) or not records:
            raise ValueError('Пустой ответ каталога')
        sections=[]
        first_title=''
        def plain(label, value):
            if value is not None and str(value).strip():
                sections.append(f'**{label}:** {value}\n')
        def rich(label, value):
            if value and str(value).strip():
                from bs4 import BeautifulSoup
                if not BeautifulSoup(str(value),'html.parser').get_text(' ',strip=True):
                    return
                body,_ = extract_markdown(str(value), meta.get('source_url',''))
                sections.append(f'## {label}\n\n{body}\n')
        for record in records:
            if not isinstance(record,dict):
                raise ValueError('Некорректная запись каталога')
            title=record.get('appTitle') or record.get('Title') or meta.get('title') or path.stem
            first_title=first_title or title
            sections.append(f'# {title}\n')
            for label,key in [('Каталог','catalog_title'),('Каталог','title_catalog'),
                              ('Код приложения','CodeAsvul'),('Код продукта','AsvulCode'),
                              ('Бизнес-направление','TitleBN'),('Раздел','Title'),
                              ('Направление продукта','DirectionTitle'),('Группа','GroupTitle'),
                              ('Подгруппа','SubGroupTitle'),('Версия','Version'),
                              ('Совместимость','Requirement'),('Архитектура','Architecture'),
                              ('Дополнительная архитектура','ArchitectureAdditional'),
                              ('Интерфейс','Interface'),('Дополнительный интерфейс','InterfaceAdditional'),
                              ('Тип','Type'),('Разработчик','developer'),
                              ('Дата начала продаж по источнику','DateStartSale'),
                              ('Статус по источнику','dateendsale1'),('Дата окончания продаж','DateEndSale')]:
                if key=='Title' and record.get(key)==title:continue
                plain(label,record.get(key))
            if record.get('isArchive'):
                plain('Статус','Архивный материал')
            rich('Краткое описание',record.get('BriefDescription'))
            rich('Описание',record.get('HTMLContent'))
            rich('Функциональные возможности',record.get('HTMLFunction'))
            for label,key in [('Необходимые приложения (коды)','AppsCodeNeeded'),
                              ('Рекомендуемые приложения (коды)','AppsCodeRecommended')]:
                plain(label,record.get(key))
            if record.get('Setting'):
                settings=json.loads(record['Setting']) if isinstance(record['Setting'],str) else record['Setting']
                sections.append('## Примеры настройки продукта из каталога\n\nЭто параметры примера настройки, а не условия конкретного банка.\n')
                for n,item in enumerate(settings,1):
                    rich(f'Настройка {n}',item.get('Tuning_Ru'))
                    rich(f'Пример {n}',item.get('Example_Ru'))
            if record.get('Versions'):
                versions=json.loads(record['Versions'])
                sections.append('## График версий по источнику\n\n| Версия | Дата по графику | Дата актуализации по источнику |\n| --- | --- | --- |')
                for v in versions:
                    sections.append(f'| {v.get("vers","")} | {v.get("dateVers","")} | {v.get("actualDateVers","")} |')
                sections.append('\nДаты графика могут относиться к будущим выпускам.\n')
            rich('Информация о версиях',record.get('VersionInfo'))
        return ParseResult(markdown='\n'.join(sections).strip()+'\n',title=first_title)
