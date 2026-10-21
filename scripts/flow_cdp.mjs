// Google Flow project tab in the visible Chrome on port 9335 (image generation is free there):
//   node flow_cdp.mjs attach <file-name-in-library>   add a library item to the prompt
//   node flow_cdp.mjs upload <file> [file...]         put files into the project library
//   node flow_cdp.mjs prompt '<text>'                 type the prompt and send it
//   node flow_cdp.mjs images                          JSON list of generated image urls (newest first)
//   node flow_cdp.mjs fetch <url> <out-file>          save an image at full size
//   node flow_cdp.mjs state                           JSON {busy, text}
import { writeFileSync } from 'node:fs';

const [cmd, a1, a2] = process.argv.slice(2);
const page = (await (await fetch('http://127.0.0.1:9335/json/list')).json()).find((t) => t.type === 'page' && t.url.includes('flow.google.com/project/'));
if (!page) throw new Error('no Flow project tab');
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener('open', r, { once: true }));
let id = 0;
const pending = new Map();
ws.addEventListener('message', (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } });
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const js = async (expr) => (await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true, userGesture: true })).result?.result?.value;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const click = async (x, y) => { for (const type of ['mouseMoved', 'mousePressed', 'mouseReleased']) await send('Input.dispatchMouseEvent', { type, x, y, button: 'left', clickCount: 1 }); };
// centre of the first visible element matched by a JS finder; waits up to 10 s
const where = async (finder, tries = 20) => {
  for (let i = 0; i < tries; i++) {
    const xy = await js(`(()=>{const e=(${finder})();if(!e)return null;const q=e.getBoundingClientRect();return q.width?[q.x+q.width/2,q.y+q.height/2]:null})()`);
    if (xy) return xy;
    await sleep(500);
  }
  throw new Error('not found: ' + finder.slice(0, 80));
};
const icon = (name, pick = 'last') => `()=>{const b=[...document.querySelectorAll('button')].filter(b=>b.innerText.trim()==='${name}'&&b.offsetParent);return b.sort((p,q)=>p.getBoundingClientRect().y-q.getBoundingClientRect().y)[${pick === 'last' ? 'b.length-1' : 0}]}`;
const text = (t) => `()=>[...document.querySelectorAll('*')].find(e=>e.children.length==0&&e.offsetParent&&(e.innerText||'').trim()===${JSON.stringify(t)})`;

await send('Page.bringToFront');
const esc = async () => { for (const type of ['keyDown', 'keyUp']) await send('Input.dispatchKeyEvent', { type, key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 }); await sleep(600); };
if (cmd === 'clear') {               // close popups and drop the prompt's attachments
  await esc();
  const x = await js(`(()=>{const b=[...document.querySelectorAll('button')].filter(b=>b.offsetParent&&b.innerText.trim()==='close'&&b.getBoundingClientRect().y>window.innerHeight*0.6);if(!b.length)return null;const q=b[0].getBoundingClientRect();return [q.x+q.width/2,q.y+q.height/2]})()`);
  if (x) { await click(...x); await sleep(800); }
}
if (cmd === 'attach') {
  await esc();
  await click(...(await where(icon('add'))));            // the prompt's "+" is the lowest "add" button
  const box = await where(`()=>[...document.querySelectorAll('input')].find(i=>i.offsetParent&&/Поиск|Search/i.test(i.placeholder||''))`);
  await click(...box);
  await js(`(()=>{const i=[...document.querySelectorAll('input')].find(i=>i.offsetParent&&/Поиск|Search/i.test(i.placeholder||''));i.select()})()`);
  const stem = a1.replace(/\.[^.]+$/, '');
  await send('Input.insertText', { text: stem });          // the search matches names without extension
  await sleep(1500);
  let item = null;
  try { item = await where(`()=>[...document.querySelectorAll('*')].find(e=>e.children.length==0&&e.offsetParent&&(e.innerText||'').trim().startsWith(${JSON.stringify(stem)}))`, 8); } catch {}
  if (!item) { await esc(); console.log('already attached'); }        // the library hides items already in the prompt
  else {
    await click(...item);
    await sleep(800);
    try { await click(...(await where(text('Добавить в подсказку'), 6))); } catch {}   // sometimes the click alone adds it
    await sleep(1200);
    await esc();
  }
}
if (cmd === 'upload') {
  const files = process.argv.slice(3);
  await send('Page.enable'); await send('Page.setInterceptFileChooserDialog', { enabled: true });
  const opened = new Promise((r) => ws.addEventListener('message', (e) => { const m = JSON.parse(e.data); if (m.method === 'Page.fileChooserOpened') r(m.params); }));
  await click(...(await where(icon('add'))));
  await sleep(1500);
  await click(...(await where(`()=>[...document.querySelectorAll('button,div')].find(e=>e.offsetParent&&/^\\s*(upload\\s*)?Загрузить м/.test(e.innerText||''))`)));
  const p = await Promise.race([opened, sleep(8000).then(() => null)]);
  if (!p) throw new Error('file chooser did not open');
  await send('DOM.setFileInputFiles', { files, backendNodeId: p.backendNodeId });
  await sleep(8000);
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
}
if (cmd === 'prompt') {
  // a previous generation may still be running: wait for the send arrow (up to 3 min)
  await where(icon('arrow_forward'), 360);
  await click(...(await where(`()=>document.querySelector('[contenteditable=true],textarea')`)));
  await send('Input.insertText', { text: a1 });
  await sleep(800);
  await click(...(await where(icon('arrow_forward'))));
}
if (cmd === 'aspect') {   // default image aspect in the agent settings: 16:9 | 4:3 | 1:1 | 3:4 | 9:16
  const open = await js(`!![...document.querySelectorAll('*')].find(e=>e.children.length==0&&e.offsetParent&&e.innerText.trim()==='Сохранять')`);
  if (!open) { await esc(); await click(...(await where(icon('tune')))); await sleep(1200); }
  await click(...(await where(`()=>[...document.querySelectorAll('mat-button-toggle')].filter(e=>e.offsetParent&&e.innerText.trim().split('\\n').pop()===${JSON.stringify(a1)}).sort((p,q)=>p.getBoundingClientRect().y-q.getBoundingClientRect().y)[0]`)));
  await sleep(500);
  await click(...(await where(text('Сохранять'))));
  await sleep(1200);
}
if (cmd === 'images') {   // the grid is virtualised: scroll every scroller to the top so the newest tiles exist in the DOM
  await js(`[...document.querySelectorAll('*')].forEach(e=>{if(e.scrollTop>0)e.scrollTop=0});window.scrollTo(0,0)`);
  await sleep(1500);
  console.log(JSON.stringify(await js(`[...new Map([...document.querySelectorAll('img')].filter(i=>i.src.includes('/asb/')&&i.naturalWidth>200).map(i=>[i.src.split('=')[0]+'=s0',i.naturalWidth>i.naturalHeight?'w':'t'])).entries()]`)));   // [url (=s0: full size), orientation]
}
if (cmd === 'state') console.log(JSON.stringify(await js(`({busy:!![...document.querySelectorAll('button')].find(b=>b.innerText.trim()==='stop'&&b.offsetParent), text:document.body.innerText.slice(-400)})`)));
if (cmd === 'fetch') {
  const d = await js(`(async()=>{const b=await (await fetch(${JSON.stringify(a1)})).blob();return await new Promise(r=>{const f=new FileReader();f.onload=()=>r(f.result);f.readAsDataURL(b)})})()`);
  writeFileSync(a2, Buffer.from(d.split(',')[1], 'base64'));
}
ws.close();
