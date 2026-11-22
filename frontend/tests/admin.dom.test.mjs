import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM, VirtualConsole } from 'jsdom';

const html = readFileSync(new URL('../../services/rag_service/app/static/admin.html', import.meta.url), 'utf8');
const sourceFiles = [
  {source:'shift/go.md',category:'shift',size_bytes:2048,chunks:12,indexed:true,on_disk:true},
  {source:'cft/products.txt',category:'cft',size_bytes:1024,chunks:0,indexed:false,on_disk:true},
];
const sourceLogs = [
  {timestamp:'2026-11-22T10:01:02.000+00:00',service:'backend',level:'ERROR',event:'generation.failed',request_id:'trace-42'},
  {timestamp:'2026-11-22T10:01:00.000+00:00',service:'auth',level:'INFO',event:'http.request'},
];
function boot({savedToken='', logs=sourceLogs}={}) {
  const calls=[], errors=[], intervals=[];
  let files=structuredClone(sourceFiles), failLogs=false;
  const vc=new VirtualConsole();vc.on('jsdomError', error => errors.push(error.message));
  const dom=new JSDOM(html,{url:'http://admin.local/admin',runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,
    beforeParse(window){
      if(savedToken)window.sessionStorage.setItem('rag_admin_token',savedToken);
      window.setInterval=callback=>{intervals.push(callback);return intervals.length;};
      window.HTMLElement.prototype.scrollIntoView=function(){};
      window.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
      window.HTMLDialogElement.prototype.close=function(value){this.returnValue=value;this.open=false;this.dispatchEvent(new window.Event('close'));};
      window.fetch=async (path,options={})=>{
        const url=new URL(path,'http://admin.local');calls.push({url,options});
        const response=(body,status=200)=>({ok:status<400,status,json:async()=>structuredClone(body)});
        if(options.headers['X-Admin-Token']!=='test-token')return response({detail:'Неверный токен'},401);
        if(url.pathname.endsWith('/logs')){
          if(failLogs)return response({detail:'Журнал недоступен'},503);
          let rows=logs;
          if(url.searchParams.get('service'))rows=rows.filter(row=>row.service===url.searchParams.get('service'));
          if(url.searchParams.get('level')==='ERROR')rows=rows.filter(row=>row.level==='ERROR');
          if(url.searchParams.get('search'))rows=rows.filter(row=>JSON.stringify(row).toLowerCase().includes(url.searchParams.get('search').toLowerCase()));
          return response({configured:true,truncated:false,updated_at:new Date().toISOString(),entries:rows});
        }
        if(url.pathname.endsWith('/reindex'))return response({files_indexed:files.length,total_chunks:15});
        if(options.method==='DELETE'){files=files.filter(file=>file.source!==url.searchParams.get('source'));return response({deleted:true});}
        if(options.method==='POST')return response({uploaded:[{}],total_chunks_added:3});
        return response(files);
      };
    }});
  const {window}=dom; const $=id=>window.document.getElementById(id);
  const change=(id,value,type='change')=>{$(id).value=value;$(id).dispatchEvent(new window.Event(type,{bubbles:true}));};
  const submit=()=>{$('authForm').dispatchEvent(new window.Event('submit',{bubbles:true,cancelable:true}));};
  return {dom,window,$,change,submit,calls,errors,intervals,failLogs:()=>{failLogs=true;}};
}
const until=async predicate=>{for(let n=0;n<100;n++){if(predicate())return;await new Promise(resolve=>setTimeout(resolve,10));}assert.fail('UI did not reach expected state');};
async function login(ui){ui.$('tokenInput').value='test-token';ui.submit();await until(()=>!ui.$('adminContent').hidden);}

test('sign-in, inventory, search, category and logout',async()=>{
  const ui=boot();try{
    assert.equal(ui.$('headingActions').hidden,true);
    await login(ui);assert.equal(ui.$('statFiles').textContent,'2');assert.equal(ui.$('statIndexed').textContent,'1');
    ui.change('fileSearch','products','input');assert.equal(ui.$('filesBody').querySelectorAll('tr').length,1);
    assert.match(ui.$('filesBody').textContent,/products.txt/);
    ui.change('fileSearch','','input');ui.change('categoryFilter','shift');assert.match(ui.$('filesBody').textContent,/go.md/);
    assert.equal(ui.window.sessionStorage.getItem('rag_admin_token'),'test-token');
    ui.$('logoutBtn').click();assert.equal(ui.$('adminContent').hidden,true);assert.equal(ui.window.sessionStorage.getItem('rag_admin_token'),null);
    assert.deepEqual(ui.errors,[]);
  }finally{ui.dom.window.close();}
});

test('invalid token cannot reveal documents; stored token restores the session',async()=>{
  const bad=boot();try{bad.$('tokenInput').value='bad';bad.submit();await until(()=>!bad.$('statusBox').hidden);assert.equal(bad.$('adminContent').hidden,true);assert.match(bad.$('statusBox').textContent,/Токен не принят/);}finally{bad.dom.window.close();}
  const good=boot({savedToken:'test-token'});try{await until(()=>!good.$('adminContent').hidden);assert.deepEqual(good.errors,[]);}finally{good.dom.window.close();}
});

test('logs filter by service, level and search; empty/error states and tab keyboard',async()=>{
  const ui=boot();try{
    await login(ui);ui.$('tab-logs').click();await until(()=>ui.$('logsBody').querySelectorAll('details').length===2);
    ui.change('logService','backend');ui.change('logLevel','ERROR');await until(()=>ui.$('logsBody').querySelectorAll('details').length===1);
    assert.match(ui.$('logsBody').textContent,/trace-42/);assert.equal(ui.$('exportLogs').disabled,false);
    ui.change('logSearch','missing','input');await until(()=>ui.$('logsBody').textContent.includes('Событий пока нет'));assert.equal(ui.$('exportLogs').disabled,true);
    ui.failLogs();ui.$('refreshBtn').click();await until(()=>!ui.$('logsError').hidden);assert.match(ui.$('logsError').textContent,/Журнал недоступен/);
    ui.$('tab-logs').dispatchEvent(new ui.window.KeyboardEvent('keydown',{key:'Home',bubbles:true}));assert.equal(ui.$('knowledge').hidden,false);
    assert.deepEqual(ui.errors,[]);
  }finally{ui.dom.window.close();}
});

test('delete and reindex wait for confirmation; upload sends the chosen category',async()=>{
  const ui=boot();try{
    await login(ui);ui.$('filesBody').querySelector('button').click();assert.equal(ui.calls.some(call=>call.options.method==='DELETE'),false);
    ui.$('confirmDialog').close('cancel');await new Promise(resolve=>setTimeout(resolve,0));assert.equal(ui.$('statFiles').textContent,'2');
    ui.$('filesBody').querySelector('button').click();ui.$('confirmDialog').close('confirm');await until(()=>ui.$('statFiles').textContent==='1');
    ui.$('reindexBtn').click();ui.$('confirmDialog').close('confirm');await until(()=>ui.$('statusBox').textContent.includes('Индекс обновлён'));
    ui.change('categoryInput','shift');Object.defineProperty(ui.$('fileInput'),'files',{configurable:true,value:[new ui.window.File(['# Doc'],'new.md',{type:'text/markdown'})]});
    ui.$('fileInput').dispatchEvent(new ui.window.Event('change'));await until(()=>ui.$('statusBox').textContent.includes('Загружено документов: 1'));
    const upload=ui.calls.find(call=>call.options.body);assert.equal(upload.options.body.get('category'),'shift');assert.equal(upload.options.body.getAll('files').length,1);
    assert.deepEqual(ui.errors,[]);
  }finally{ui.dom.window.close();}
});

test('untrusted filenames and log messages stay inert',async()=>{
  const ui=boot({logs:[{...sourceLogs[0],event:'<img src=x onerror="window.injected=true">'}]});try{
    await login(ui);ui.$('tab-logs').click();await until(()=>ui.$('logsBody').querySelector('details'));
    assert.match(ui.$('logsBody').textContent,/<img src=x/);assert.equal(ui.$('logsBody').querySelectorAll('img').length,0);assert.equal(ui.window.injected,undefined);assert.deepEqual(ui.errors,[]);
  }finally{ui.dom.window.close();}
});

test('auto-refresh runs only on the active logs tab when enabled',async()=>{
  const ui=boot();try{
    await login(ui);let count=ui.calls.length;ui.intervals[0]();assert.equal(ui.calls.length,count);
    ui.$('tab-logs').click();await until(()=>ui.$('logsBody').querySelector('details'));
    count=ui.calls.length;ui.intervals[0]();await until(()=>ui.calls.length>count);
    ui.$('autoRefresh').checked=false;count=ui.calls.length;ui.intervals[0]();assert.equal(ui.calls.length,count);assert.deepEqual(ui.errors,[]);
  }finally{ui.dom.window.close();}
});
