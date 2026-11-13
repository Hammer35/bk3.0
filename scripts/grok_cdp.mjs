// Grok Imagine tab (grok.com/imagine) in the visible Chrome on port 9335:
//   node grok_cdp.mjs new                       fresh canvas
//   node grok_cdp.mjs upload <file> [file...]   attach reference images
//   node grok_cdp.mjs aspect 16:9|9:16|2:3|3:4  pick the aspect ratio
//   node grok_cdp.mjs prompt '<text>'           type and send
//   node grok_cdp.mjs images                    JSON list of generated image urls on the page
//   node grok_cdp.mjs fetch <url> <out-file>
//   node grok_cdp.mjs text                      tail of the page text (limits, errors)
import { writeFileSync } from 'node:fs';

const [cmd, a1, a2] = process.argv.slice(2);
const page = (await (await fetch('http://127.0.0.1:9335/json/list')).json()).find((t) => t.type === 'page' && t.url.includes('grok.com'));
if (!page) throw new Error('no Grok tab');
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener('open', r, { once: true }));
let id = 0;
const pending = new Map();
ws.addEventListener('message', (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } });
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const js = async (expr) => (await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true, userGesture: true })).result?.result?.value;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const click = async ([x, y]) => { for (const type of ['mouseMoved', 'mousePressed', 'mouseReleased']) await send('Input.dispatchMouseEvent', { type, x, y, button: 'left', clickCount: 1 }); };
const where = async (finder, tries = 20) => {
  for (let i = 0; i < tries; i++) {
    const xy = await js(`(()=>{const e=(${finder})();if(!e)return null;e.scrollIntoView({block:'center'});const q=e.getBoundingClientRect();return q.width?[q.x+q.width/2,q.y+q.height/2]:null})()`);
    if (xy) return xy;
    await sleep(500);
  }
  throw new Error('not found: ' + finder.slice(0, 80));
};
const btn = (label) => `()=>[...document.querySelectorAll('button')].find(b=>b.offsetParent&&((b.getAttribute('aria-label')||'')===${JSON.stringify(label)}||b.innerText.trim()===${JSON.stringify(label)}))`;

await send('Page.bringToFront');
if (cmd === 'new') { await send('Page.navigate', { url: 'https://grok.com/imagine' }); await sleep(7000); }
if (cmd === 'upload') {   // "+" (Загрузить) opens the native chooser; intercept it and feed the files
  const files = process.argv.slice(3);
  await js(`window.scrollTo(0,0);[...document.querySelectorAll('*')].forEach(e=>{if(e.scrollTop>0)e.scrollTop=0})`); await sleep(800);
  await send('Page.enable'); await send('Page.setInterceptFileChooserDialog', { enabled: true });
  const opened = new Promise((r) => ws.addEventListener('message', (e) => { const m = JSON.parse(e.data); if (m.method === 'Page.fileChooserOpened') r(m.params); }));
  await click(await where(btn('Загрузить')));
  let p = await Promise.race([opened, sleep(3000).then(() => null)]);
  if (!p) {                                  // "+" may open a small menu first
    await click(await where(`()=>[...document.querySelectorAll('[role=menuitem],button,div')].filter(e=>e.offsetParent&&/Загрузить|Upload/.test(e.innerText)&&e.innerText.length<40).pop()`));
    p = await Promise.race([opened, sleep(5000).then(() => null)]);
  }
  if (!p) throw new Error('file chooser did not open');
  await send('DOM.setFileInputFiles', { files, backendNodeId: p.backendNodeId });
  await sleep(8000);
}
if (cmd === 'aspect') {
  await click(await where(btn('Соотношение сторон')));
  await sleep(800);
  await click(await where(`()=>[...document.querySelectorAll('[role=menuitem],[role=option],button,div')].filter(e=>e.offsetParent&&e.innerText.trim().startsWith(${JSON.stringify(a1)})&&e.innerText.trim().length<30).pop()`));
  await sleep(600);
}
if (cmd === 'prompt') {
  await click(await where(`()=>document.querySelector('textarea,[contenteditable=true]')`));
  await send('Input.insertText', { text: a1 });
  await sleep(800);
  await click(await where(btn('Отправить')));
}
if (cmd === 'images') console.log(JSON.stringify(await js(`[...new Set([...document.querySelectorAll('img')].filter(i=>i.src.includes('/generated/')&&i.naturalWidth>=400).map(i=>i.src))]`)));
if (cmd === 'text') console.log(JSON.stringify(await js(`document.body.innerText.slice(-600)`)));
if (cmd === 'download') {   // download <dir>: the post page's "Скачать" button, saved straight into <dir>
  await send('Browser.setDownloadBehavior', { behavior: 'allow', downloadPath: a1, eventsEnabled: true });
  const done = new Promise((r) => ws.addEventListener('message', (e) => { const m = JSON.parse(e.data); if (m.method === 'Browser.downloadProgress' && m.params.state === 'completed') r(1); }));
  await click(await where(btn('Скачать')));
  await Promise.race([done, sleep(30000)]);
}
if (cmd === 'fetch') {   // assets.grok.com needs its own origin + cookies: open the image in a tab and read it there
  const t = await (await fetch('http://127.0.0.1:9335/json/new?' + encodeURIComponent(a1), { method: 'PUT' })).json();
  await sleep(4000);
  const w2 = new WebSocket(t.webSocketDebuggerUrl);
  await new Promise((r) => w2.addEventListener('open', r, { once: true }));
  const d = await new Promise((r) => { w2.addEventListener('message', (e) => { const m = JSON.parse(e.data); if (m.id === 1) r(m.result?.result?.value); });
    w2.send(JSON.stringify({ id: 1, method: 'Runtime.evaluate', params: { awaitPromise: true, returnByValue: true,
      expression: `(async()=>{const b=await (await fetch(location.href,{credentials:'include'})).blob();return await new Promise(r=>{const f=new FileReader();f.onload=()=>r(f.result);f.readAsDataURL(b)})})()` } })); });
  w2.close(); await fetch('http://127.0.0.1:9335/json/close/' + t.id);
  if (typeof d !== 'string' || d.length < 1000) throw new Error('fetch failed');
  writeFileSync(a2, Buffer.from(d.split(',')[1], 'base64'));
}
ws.close();
