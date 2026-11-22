import io
import json
import zipfile
from pathlib import Path
import pytest
from app.parsers.archive_parser import ArchiveParser
from app.parsers.structured_parser import CodeParser, StructuredParser
from app.pipeline import run


def test_archive_drops_traversal_and_nested_archive(tmp_path):
    inner=io.BytesIO()
    with zipfile.ZipFile(inner,'w') as z:z.writestr('nested.txt','nested')
    path=tmp_path/'data.zip'
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('../secret.txt','secret')
        z.writestr('/absolute.txt','secret')
        z.writestr('safe.txt','Текст курса Go')
        z.writestr('nested.zip',inner.getvalue())
    result=ArchiveParser().parse(path)
    assert 'Текст курса Go' in result.markdown
    assert 'secret' not in result.markdown
    assert any('небезопасный путь' in w for w in result.warnings)
    assert any('Вложенный архив' in w for w in result.warnings)
    assert not (tmp_path.parent/'secret.txt').exists()


def test_archive_entry_limit(tmp_path):
    path=tmp_path/'huge.zip'
    with zipfile.ZipFile(path,'w') as z:
        for i in range(501):z.writestr(str(i)+'.txt','text')
    with pytest.raises(ValueError,match='500'):ArchiveParser().parse(path)


def test_xml_external_entity_is_not_read(tmp_path):
    secret=tmp_path/'private.txt';secret.write_text('DO-NOT-EXPOSE')
    xml=tmp_path/'test.xml'
    xml.write_text(f'<!DOCTYPE a [<!ENTITY leak SYSTEM "{secret.as_uri()}">]><a><value>&leak;</value><ok>Go</ok></a>')
    result=StructuredParser().parse(xml)
    assert 'DO-NOT-EXPOSE' not in result.markdown and 'Go' in result.markdown


def test_code_is_rendered_as_text_and_never_executed(tmp_path):
    sentinel=tmp_path/'executed'
    code=tmp_path/'script.py';code.write_text(f'from pathlib import Path\nPath({str(sentinel)!r}).touch()\n# ```')
    result=CodeParser().parse(code)
    assert not sentinel.exists()
    assert result.markdown.startswith('````py')


def test_output_inside_input_and_missing_input_rejected(tmp_path):
    with pytest.raises(ValueError):run(tmp_path/'missing',tmp_path/'out',verbose=False)
    with pytest.raises(ValueError):run(tmp_path,tmp_path/'out',verbose=False)


def test_invalid_sidecar_is_reported_and_other_files_continue(tmp_path):
    raw=tmp_path/'raw';raw.mkdir();out=tmp_path/'parsed'
    (raw/'bad.txt').write_text('Bad text');(raw/'bad.txt.meta.json').write_text('[]')
    (raw/'ok.txt').write_text('Хороший документ Go')
    assert run(raw,out,verbose=False)==(1,1)
    report=json.loads((tmp_path/'registry/parsing_summary.json').read_text())
    assert report['error']==1 and report['written']==1
