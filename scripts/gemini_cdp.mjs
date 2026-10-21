// Visible Chrome with Gemini on port 9335 (profile ~/.local/share/pinterest-video-tools/gemini-visible):
//   node gemini_cdp.mjs shot <file.png>          screenshot of the visible page
//   node gemini_cdp.mjs eval '<js expression>'   run in the page, print the result
//   node gemini_cdp.mjs click x,y | type '<text>' | key Enter
import { writeFileSync } from 'node:fs';

const [cmd, arg] = process.argv.slice(2);
const list = await (await fetch('http://127.0.0.1:9335/json/list')).json();
const page = list.find((t) => t.type === 'page' && t.url.includes('google.com'));
if (!page) throw new Error('no gemini page');
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener('open', r, { once: true }));
let id = 0;
const pending = new Map();
ws.addEventListener('message', (e) => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
});
ws.addEventListener('close', () => { for (const r of pending.values()) r({ error: 'ws closed' }); pending.clear(); });
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });

await send('Page.bringToFront');
if (cmd === 'newchat') {
  await send('Page.navigate', { url: 'https://gemini.google.com/app' });
  await new Promise((r) => setTimeout(r, 6000));
}
if (cmd === 'shot') {
  const m = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync(arg, Buffer.from(m.result.data, 'base64'));
}
if (cmd === 'eval') {
  const m = await send('Runtime.evaluate', { expression: arg, awaitPromise: true, returnByValue: true, userGesture: true });
  console.log(JSON.stringify(m.result?.result?.value ?? m.result?.exceptionDetails?.text ?? m));
}
if (cmd === 'click') {
  const [x, y] = arg.split(',').map(Number);
  await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y });
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', clickCount: 1 });
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', clickCount: 1 });
}
if (cmd === 'type') await send('Input.insertText', { text: arg });
if (cmd === 'download') {
  // download <dir>: press "Download full size image" on the last generated image, save into <dir>
  await send('Browser.setDownloadBehavior', { behavior: 'allow', downloadPath: arg, eventsEnabled: true });
  const done = new Promise((r) => ws.addEventListener('message', (e) => {
    const m = JSON.parse(e.data); if (m.method === 'Browser.downloadProgress' && m.params.state === 'completed') r(m.params);
  }));
  // a real mouse click: the Russian UI ignores element.click() on this button
  const r = await send('Runtime.evaluate', { returnByValue: true, expression:
    `(()=>{const b=[...document.querySelectorAll('button')].filter(b=>/Download full size|полном размере|Скачать изображение/i.test(b.getAttribute('aria-label')||'')).pop();
      b.scrollIntoView({block:'center'});const q=b.getBoundingClientRect();return [q.x+q.width/2,q.y+q.height/2]})()` });
  const [x, y] = r.result.result.value;
  await new Promise((res) => setTimeout(res, 500));
  await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y });
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', clickCount: 1 });
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', clickCount: 1 });
  const p = await Promise.race([done, new Promise((r) => setTimeout(() => r(null), 15000))]);
  console.log(p ? 'downloaded' : 'download timeout');
}
if (cmd === 'upload') {
  // upload <menu-item-text> <file> [file...]: open "Upload & tools", pick the item, feed the file chooser
  const files = process.argv.slice(4);
  await send('Page.enable');
  await send('Page.setInterceptFileChooserDialog', { enabled: true });
  const opened = new Promise((r) => ws.addEventListener('message', (e) => {
    const m = JSON.parse(e.data); if (m.method === 'Page.fileChooserOpened') r(m.params);
  }));
  const js = (s) => send('Runtime.evaluate', { expression: s, userGesture: true, awaitPromise: true, returnByValue: true });
  const UP = `'button[aria-label="Upload & tools"],button[aria-label="Загрузка и инструменты"]'`;
  const where = (sel) => `(async()=>{let e=null;for(let i=0;i<40&&!e;i++){e=(${sel})();if(!e)await new Promise(r=>setTimeout(r,300))}
    if(!e)return null;e.scrollIntoView({block:'center'});const q=e.getBoundingClientRect();return [q.x+q.width/2,q.y+q.height/2]})()`;
  const tap = async (expr) => {
    const r = await js(where(expr)); const xy = r.result?.result?.value; if (!xy) return false;
    const [x, y] = xy;
    await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y });
    await send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', clickCount: 1 });
    await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', clickCount: 1 });
    return true;
  };
  const item = `()=>document.querySelector('button[aria-label^="Upload files"],button[aria-label^="Загрузить файлы"]')||[...document.querySelectorAll('[role=menu] *')].filter(e=>e.children.length==0&&[${JSON.stringify(arg)},'Файлы'].includes((e.innerText||'').trim())).map(e=>e.closest('button,[role=menuitem]')||e)[0]`;
  let p = null;
  for (let attempt = 0; attempt < 3 && !p; attempt++) {
    await tap(`()=>document.querySelector(${UP})`);
    await new Promise((r) => setTimeout(r, 800));
    await tap(item);
    p = await Promise.race([opened, new Promise((r) => setTimeout(() => r(null), 8000))]);
    if (!p) { await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
              await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
              await new Promise((r) => setTimeout(r, 1000)); }
  }
  if (!p) throw new Error('file chooser did not open');
  await send('DOM.setFileInputFiles', { files, backendNodeId: p.backendNodeId });
  await new Promise((r) => setTimeout(r, 4000));
  console.log('uploaded', files.length);
}
if (cmd === 'key') {
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: arg, code: arg, windowsVirtualKeyCode: arg === 'Enter' ? 13 : 0 });
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: arg, code: arg, windowsVirtualKeyCode: arg === 'Enter' ? 13 : 0 });
}
ws.close();
