document.querySelectorAll('form[data-confirm]').forEach(f=>f.addEventListener('submit',e=>{if(!confirm(f.dataset.confirm))e.preventDefault()}));
document.querySelectorAll('form.submit-once').forEach(f=>f.addEventListener('submit',()=>{const b=f.querySelector('button[type=submit],button:not([type])');if(b){b.disabled=true;b.textContent='처리 중…'}}));

