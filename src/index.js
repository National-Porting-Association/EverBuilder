// EverBuilder frontend (single clean script)
(function(){
  function $id(n){ return document.getElementById(n); }
  const dirInput = $id('dirInput');
    const fileList = $id('fileList');
    const buildBtn = $id('buildBtn');
    const clearBtn = $id('clearBtn');
    const logArea = $id('logArea');
    const downloadLog = $id('downloadLog');
    const downloadBuild = $id('downloadBuild');
    const copyLogBtn = $id('copyLog');
    const spinnerSmall = $id('spinnerSmall');
    const artifactNameEl = $id('artifactName');
    const artifactSizeEl = $id('artifactSize');
    const progressBar = $id('progressBar');
    const progressPct = $id('progressPct');
    const etaLabel = $id('eta');
    const optClean = $id('opt_clean_temp');
    const optAutoOpen = $id('opt_auto_open');
    const optVerbose = $id('opt_verbose');
    const optCompress = $id('opt_compress');
  const loaderSelect = $id('loaderSelect');
  const loaderPreview = $id('loaderPreview');

    function humanSize(n){ if(!n) return '0 B'; if(n<1024) return n+' B'; if(n<1024*1024) return (n/1024).toFixed(1)+' KB'; return (n/(1024*1024)).toFixed(2)+' MB'; }
    function setStatus(s){ const st = $id('statusText'); if(st) st.textContent = s; }

    let files = [];
    function updateUI(){
      try{
        if(files.length){ if(buildBtn) buildBtn.disabled=false; if(fileList) fileList.textContent = files.map(f=>f.webkitRelativePath||f.name).join('\n'); const total = files.reduce((s,f)=>s+(f.size||0),0); if($id('fileCount')) $id('fileCount').textContent = files.length; if($id('fileSize')) $id('fileSize').textContent = humanSize(total); }
        else { if(buildBtn) buildBtn.disabled=true; if(fileList) fileList.textContent='(no files)'; if($id('fileCount')) $id('fileCount').textContent='0'; if($id('fileSize')) $id('fileSize').textContent='0 B'; }
      }catch(e){ console.warn('updateUI', e); }
    }

    if(dirInput) dirInput.addEventListener('change', e=>{ files = Array.from(e.target.files||[]); updateUI(); });
    if(clearBtn) clearBtn.addEventListener('click', ()=>{ files=[]; if(dirInput) dirInput.value=null; updateUI(); if(logArea) logArea.textContent='Cleared.'; if(downloadLog) downloadLog.style.display='none'; if(downloadBuild) downloadBuild.style.display='none'; if(artifactNameEl) artifactNameEl.textContent='-'; if(artifactSizeEl) artifactSizeEl.textContent='-'; setStatus('Idle'); });

    // settings
    try{ const s = JSON.parse(localStorage.getItem('everbuilder.settings')||'{}'); if(s){ if(optClean) optClean.checked = !!s.clean_temp; if(optAutoOpen) optAutoOpen.checked = !!s.auto_open; if(optVerbose) optVerbose.checked = !!s.verbose; if(optCompress) optCompress.checked = !!s.compress; } }catch(e){}
  function saveSettings(){ localStorage.setItem('everbuilder.settings', JSON.stringify({ clean_temp: optClean?optClean.checked:false, auto_open: optAutoOpen?optAutoOpen.checked:false, verbose: optVerbose?optVerbose.checked:false, compress: optCompress?optCompress.checked:false, loader: loaderSelect?loaderSelect.value:'basic' })); }
    [optClean,optAutoOpen,optVerbose,optCompress].forEach(n=>n&&n.addEventListener('change', saveSettings));

    // network helpers
    function candidatePaths(path){ return [path, '/everbuilder'+path]; }
    async function fetchWithFallback(path, opts){ const c = candidatePaths(path); for(const u of c){ try{ const r = await fetch(u, opts); if(r && r.ok) return r; }catch(e){} } return fetch(c[0], opts); }

    // build flow: upload via XHR (to get upload progress) then open a streaming fetch to /build/stream
  async function startBuild(){
      if(!files.length) return;
      if(logArea) logArea.textContent = 'Starting upload...\n'; if(progressBar) progressBar.style.width='0%'; if(progressPct) progressPct.textContent='0%'; if(etaLabel) etaLabel.textContent='ETA: --:--'; setStatus('Uploading');

  const settingsObj = { clean_temp: optClean?optClean.checked:false, auto_open: optAutoOpen?optAutoOpen.checked:false, verbose: optVerbose?optVerbose.checked:false, embed_css: false, compress: optCompress?optCompress.checked:false };
  if(loaderSelect && loaderSelect.value) settingsObj.selected_loader = loaderSelect.value;
  const form = new FormData(); files.forEach(f=>form.append('files', f, f.webkitRelativePath||f.name)); form.append('settings', JSON.stringify(settingsObj));
      if(buildBtn) buildBtn.disabled=true; if(dirInput) dirInput.disabled=true; if(clearBtn) clearBtn.disabled=true; if(spinnerSmall) spinnerSmall.textContent='⏳';

      try{
        // first, upload via XHR to start the server-side build which will populate LAST_BUILD['queue'] on the server
        const urls = candidatePaths('/build');
        const xhr = new XMLHttpRequest();
        xhr.open('POST', urls[0], true);
        xhr.upload.onprogress = function(ev){ if(ev.lengthComputable){ const upPct = Math.floor((ev.loaded / ev.total) * 10); if(progressBar) progressBar.style.width = upPct + '%'; if(progressPct) progressPct.textContent = upPct + '%'; } };

        xhr.onload = function(){
          if(xhr.status < 200 || xhr.status >= 300){ if(logArea) logArea.textContent += '\nUpload failed: ' + xhr.statusText; buildFinishedCleanup(); return; }
          // upload succeeded; now open the streaming connection to receive logs
          setStatus('Building'); if(logArea) logArea.textContent += '\nUpload complete. Connecting to build stream...\n';
          openBuildStream();
        };
        xhr.onerror = function(){ if(logArea) logArea.textContent += '\nUpload failed (network)'; buildFinishedCleanup(); };
        xhr.send(form);

      }catch(err){ if(logArea) logArea.textContent += '\nERROR: '+err.message; buildFinishedCleanup(); }
    }

    async function openBuildStream(){
      try{
        const r = await fetchWithFallback('/build/stream');
        if(!r.ok) throw new Error('Stream not available: ' + r.status);
        setStatus('Streaming');
        const reader = r.body.getReader(); const dec = new TextDecoder(); let acc=''; const start = Date.now(); let lastPct = 10;
        while(true){ const {value, done} = await reader.read(); if(done) break; if(value){ const text = dec.decode(value, {stream:true}); acc += text; if(logArea){ logArea.textContent = acc; logArea.scrollTop = logArea.scrollHeight; }
            const re = /\[(\d{1,3})%\]/g; let m; while((m=re.exec(text))){ const pct = Math.max(0, Math.min(100, Number(m[1]))); if(progressBar) progressBar.style.width = pct + '%'; if(progressPct) progressPct.textContent = pct + '%'; const now = Date.now(); if(pct>0 && pct>lastPct){ const elapsed = (now-start)/1000; const estTotal = elapsed*(100/pct); const remain = Math.max(0, estTotal - elapsed); const mins = Math.floor(remain/60); const secs = Math.floor(remain%60).toString().padStart(2,'0'); if(etaLabel) etaLabel.textContent = `ETA: ${mins}:${secs}`; lastPct = pct; } }
          }
        }

        // after stream ends, fetch result metadata
        try{ const r2 = await fetchWithFallback('/build/result'); if(r2.ok){ const info = await r2.json(); if(info.log_url && downloadLog){ downloadLog.href = info.log_url; downloadLog.style.display='inline'; } if(info.build_url && downloadBuild){ downloadBuild.href = info.build_url; downloadBuild.style.display='inline'; downloadBuild.download = info.build_name || 'artifact'; downloadBuild.textContent = 'Download: '+(info.build_name||'artifact'); if(artifactNameEl) artifactNameEl.textContent = info.build_name||'artifact'; try{ /* replaced direct fetch with fallback to avoid 404 when server uses namespaced paths */ fetchWithFallback(info.build_url,{method:'HEAD'}).then(h=>{ if(h && h.ok){ try{ const s = h.headers.get('content-length'); if(s && artifactSizeEl) artifactSizeEl.textContent = (Number(s)>1024? (Number(s)/1024).toFixed(1)+' KB' : Number(s)+' B'); }catch(e){} try{ if(downloadBuild) downloadBuild.href = h.url; }catch(e){} } }).catch(()=>{}); }catch(e){} } } }catch(e){ console.warn('result metadata fetch failed', e); }

      }catch(err){ if(logArea) logArea.textContent += '\nStream error: '+err.message; }
      finally{ buildFinishedCleanup(); }
    }

    function buildFinishedCleanup(){ if(buildBtn) buildBtn.disabled=false; if(dirInput) dirInput.disabled=false; if(clearBtn) clearBtn.disabled=false; if(spinnerSmall) spinnerSmall.textContent=''; setStatus('Idle'); saveSettings(); }

    if(buildBtn) buildBtn.addEventListener('click', startBuild);

    // Populate loader list from repository (src/loaders/list)
    (async function populateLoaders(){
      try{
        const r = await fetchWithFallback('/everbuilder_static/loaders/list');
        if(!r.ok) return;
        const txt = await r.text();
        const items = txt.split(/\r?\n/).map(s=>s.trim()).filter(Boolean);
        if(loaderSelect && items && items.length){
          loaderSelect.innerHTML = '';
          items.forEach(it=>{
            const opt = document.createElement('option'); opt.value = it; opt.textContent = it; loaderSelect.appendChild(opt);
          });
          // restore saved setting
          try{ const s = JSON.parse(localStorage.getItem('everbuilder.settings')||'{}'); if(s && s.loader && loaderSelect.querySelector('option[value="'+s.loader+'"]')) loaderSelect.value = s.loader; }catch(e){}
          // update preview iframe if present
          try{ if(loaderPreview && loaderSelect && loaderSelect.value) loaderPreview.src = '/everbuilder_static/loaders/' + loaderSelect.value + '/index.html'; }catch(e){}
        }
      }catch(e){ console.warn('populateLoaders', e); }
    })();

    (async ()=>{ try{ const r = await fetchWithFallback('/features'); if(r.ok){ const f = await r.json(); if(f && f.auto_open){ const row = $id('autoOpenRow'); if(row) row.style.display='block'; } } }catch(e){} })();

    try{ if(copyLogBtn) copyLogBtn.addEventListener('click', ()=>{ navigator.clipboard.writeText((logArea&&logArea.textContent)||'').then(()=>{ copyLogBtn.textContent='Copied'; setTimeout(()=>copyLogBtn.textContent='Copy log',1000); }); }); }catch(e){}

  // update preview when selection changes
  if(loaderSelect){ loaderSelect.addEventListener('change', function(){ try{ if(loaderPreview) loaderPreview.src = '/everbuilder_static/loaders/' + this.value + '/index.html'; saveSettings(); }catch(e){} }); }

  // initial UI sync
    updateUI();

})();
