/* Reusable modal helper: showModal and confirmModal */
(function(){
  const overlay = document.getElementById('appModalOverlay');
  const modal = overlay ? overlay.querySelector('.app-modal') : null;
  const titleEl = document.getElementById('appModalTitle');
  const msgEl = document.getElementById('appModalMessage');
  const okBtn = document.getElementById('appModalOk');
  const cancelBtn = document.getElementById('appModalCancel');
  const iconEl = document.getElementById('appModalIcon');

  let resolver = null;

  function setType(type){
    if(!modal) return;
    modal.classList.remove('is-success','is-error','is-warning','is-info');
    const t = ['success','error','warning','info'].includes(type) ? type : 'info';
    modal.classList.add('is-' + t);
    // Simple icon glyphs; can be replaced with boxicons
    const icons = {
      success: '✓',
      error: '⛔',
      warning: '⚠️',
      info: 'ℹ️'
    };
    if(iconEl) iconEl.textContent = icons[t] || '';
  }

  function show(opts){
    const { title='Notice', message='', type='info', okText='OK' } = (opts || {});
    return new Promise(resolve => {
      resolver = (v)=>resolve(v);
      if(titleEl) titleEl.textContent = title;
      if(msgEl) {
        msgEl.textContent = '';
        // if message contains HTML, allow rendering
        if(typeof message === 'string' && /<[^>]+>/.test(message)) {
          msgEl.innerHTML = message;
        } else {
          msgEl.textContent = String(message);
        }
      }
      setType(type);
      if(okBtn) okBtn.textContent = okText || 'OK';
      if(cancelBtn) cancelBtn.style.display = 'none';
      if(overlay){ overlay.classList.add('is-active'); }
      if(okBtn) okBtn.focus();
    });
  }

  function confirm(opts){
    const { title='Confirm', message='', type='warning', okText='Confirm', cancelText='Cancel' } = (opts || {});
    return new Promise(resolve => {
      resolver = (v)=>resolve(v === true);
      if(titleEl) titleEl.textContent = title;
      if(msgEl) {
        msgEl.textContent = '';
        if(typeof message === 'string' && /<[^>]+>/.test(message)) {
          msgEl.innerHTML = message;
        } else {
          msgEl.textContent = String(message);
        }
      }
      setType(type);
      if(okBtn) okBtn.textContent = okText || 'Confirm';
      if(cancelBtn) {
        cancelBtn.textContent = cancelText || 'Cancel';
        cancelBtn.style.display = '';
      }
      if(overlay){ overlay.classList.add('is-active'); }
      if(okBtn) okBtn.focus();
    });
  }

  function closeWith(value){
    if(overlay) overlay.classList.remove('is-active');
    const r = resolver; resolver = null;
    if(typeof r === 'function') r(value);
  }

  if(okBtn) okBtn.addEventListener('click', ()=> closeWith(true));
  if(cancelBtn) cancelBtn.addEventListener('click', ()=> closeWith(false));
  if(overlay) overlay.addEventListener('click', (e)=>{ if(e.target === overlay) closeWith(false); });
  document.addEventListener('keydown', (e)=>{ if(overlay && overlay.classList.contains('is-active') && e.key === 'Escape') closeWith(false); });

  // Expose globally
  window.showModal = show;
  window.confirmModal = confirm;
})();