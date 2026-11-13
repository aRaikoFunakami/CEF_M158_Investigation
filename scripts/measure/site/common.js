function done(name, obj){ window.__result = obj; document.title = name + (obj.pass ? ' PASS' : ' FAIL');
  const p = document.getElementById('out'); p.textContent = JSON.stringify(obj, null, 1);
  const h = document.getElementById('h'); h.className = obj.pass ? 'ok' : 'ng'; h.textContent = name + ': ' + (obj.pass ? 'PASS' : 'FAIL'); }
function sleep(ms){ return new Promise(r => setTimeout(r, ms)); }
async function waitPlay(v, sec, timeoutMs){ const t0 = performance.now();
  while (performance.now() - t0 < timeoutMs) { if (v.currentTime >= sec) return true; await sleep(500); } return false; }
