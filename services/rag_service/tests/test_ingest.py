from datetime import date
from pathlib import Path
from unittest.mock import Mock
import pytest
from app import ingest
from app.schemas import DocumentInfo

@pytest.mark.parametrize('category',['..','a/../b','.hidden','a//b'])
def test_category_traversal_rejected(category):
    with pytest.raises(ValueError): ingest._sanitize_rel_path(category,'test.md')

@pytest.mark.parametrize('source',['../x.md','.secret/x.md','a/../../x.md'])
def test_file_traversal_rejected(tmp_path,source):
    with pytest.raises(ValueError): ingest._resolve_safe(tmp_path,source)


def test_symlink_cannot_escape_storage(tmp_path):
    outside=tmp_path.parent/'outside.md';outside.write_text('private')
    (tmp_path/'escape.md').symlink_to(outside)
    with pytest.raises(ValueError): ingest._resolve_safe(tmp_path,'escape.md')


def test_decode_bom_cp1251_and_frontmatter():
    assert ingest._decode_bytes(b'\xef\xbb\xbfhello')=='hello'
    assert ingest._decode_bytes('Привет'.encode('cp1251'))=='Привет'
    meta,body=ingest._extract_frontmatter('---\ntitle: Тест\npublished_at: 2026-11-01\n---\nТекст')
    assert meta['published_at']==date(2026,11,1) and body=='Текст'


def test_recursive_index_preserves_titles_headers_dates_urls(tmp_path,monkeypatch):
    nested=tmp_path/'school'/'go';nested.mkdir(parents=True)
    (nested/'course.MD').write_text('---\ntitle: Курс Go\nsource_url: https://education.cft.ru/go\npublished_at: 2026-11-01\nversion: 2\n---\n# Go\n## Программа\nИзучаем Go и PostgreSQL',encoding='utf-8')
    (tmp_path/'.hidden').mkdir();(tmp_path/'.hidden'/'hidden.txt').write_text('hidden')
    (tmp_path/'unrelated.json').write_text('{}')
    store=Mock();monkeypatch.setattr(ingest,'get_vectorstore',lambda:store)
    recreate=Mock();monkeypatch.setattr(ingest,'recreate_collection',recreate)
    result=ingest.index_dataset(str(tmp_path))
    assert result.files_indexed==1 and result.folders_found==1 and result.total_chunks>=1
    chunks=store.add_documents.call_args.args[0]
    assert chunks[0].metadata['source']=='school/go/course.MD'
    assert chunks[0].metadata['title']=='Курс Go'
    assert chunks[0].metadata['published_at']=='2026-11-01'
    assert 'Программа' in chunks[0].page_content
    assert chunks[0].metadata['source_url'].startswith('https:')


def test_empty_directory_keeps_existing_index(tmp_path,monkeypatch):
    recreate=Mock();monkeypatch.setattr(ingest,'recreate_collection',recreate)
    with pytest.raises(ValueError,match='индекс сохранён'): ingest.index_dataset(str(tmp_path))
    recreate.assert_not_called()


def test_empty_files_keep_existing_index(tmp_path,monkeypatch):
    (tmp_path/'empty.txt').touch()
    recreate=Mock();monkeypatch.setattr(ingest,'recreate_collection',recreate)
    with pytest.raises(ValueError): ingest.index_dataset(str(tmp_path))
    recreate.assert_not_called()

@pytest.mark.parametrize('name,raw',[('bad.exe',b'text'),('empty.md',b'  '),('big.md',b'x'*(1024*1024+1))])
def test_upload_rejects_invalid_files_before_mutating_index(tmp_path,monkeypatch,name,raw):
    monkeypatch.setattr(ingest.settings,'max_upload_mb',1)
    remove=Mock();monkeypatch.setattr(ingest,'delete_document_points',remove)
    with pytest.raises(ValueError): ingest.save_and_index_file(name,raw,data_dir=str(tmp_path))
    remove.assert_not_called()
    assert not list(tmp_path.rglob('*'))


def test_storage_inventory_reports_disk_only_and_index_only(tmp_path,monkeypatch):
    (tmp_path/'local.md').write_text('Hello')
    monkeypatch.setattr(ingest,'list_documents',lambda:[DocumentInfo(source='remote.md',category='index',chunks=3)])
    result={f.source:f for f in ingest.list_storage_files(str(tmp_path))}
    assert result['local.md'].on_disk and not result['local.md'].indexed
    assert result['remote.md'].indexed and not result['remote.md'].on_disk


def test_invalid_update_preserves_existing_file(tmp_path,monkeypatch):
    target=tmp_path/'go.md';target.write_text('Original course')
    delete=Mock();monkeypatch.setattr(ingest,'delete_document_points',delete)
    with pytest.raises(ValueError):
        ingest.save_and_index_file('go.md',b'---\ntitle: Empty\n---\n',data_dir=str(tmp_path))
    assert target.read_text()=='Original course'
    delete.assert_not_called()
    assert list(tmp_path.iterdir())==[target]


def test_index_upload_uses_final_source_name_not_staging_name(tmp_path,monkeypatch):
    store=Mock();monkeypatch.setattr(ingest,'get_vectorstore',lambda:store)
    monkeypatch.setattr(ingest,'delete_document_points',Mock())
    result=ingest.save_and_index_file('go.md',b'# Go course\nTwelve weeks','school',str(tmp_path))
    chunk=store.add_documents.call_args.args[0][0]
    assert result.source=='school/go.md' and chunk.metadata['source']==result.source
    assert chunk.metadata['filename']=='go.md' and chunk.metadata['title']=='go'
    assert (tmp_path/'school/go.md').is_file()


def test_failed_vector_delete_preserves_source_file(tmp_path,monkeypatch):
    target=tmp_path/'go.md';target.write_text('Original')
    monkeypatch.setattr(ingest,'delete_document_points',Mock(side_effect=RuntimeError('offline')))
    with pytest.raises(RuntimeError):ingest.delete_file_and_vectors('go.md',str(tmp_path))
    assert target.read_text()=='Original'
