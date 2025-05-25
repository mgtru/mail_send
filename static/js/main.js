// static/js/main.js  –  предпросмотр Excel и шаблона
document.addEventListener('DOMContentLoaded', () => {

  /* helpers */
  const daysLeft = s => {           // '2027-11-01' → 900
    try { return Math.floor((new Date(s.trim()) - new Date()) / 864e5); }
    catch { return null; }
  };
  const render = (tmpl, row) =>
    tmpl.replace(/\{([A-F]|expiry_days)\}/g, (_, k) =>
      k === 'expiry_days' ? row.expiry_days : (row[k] ?? ''));

  let matched = [];                 // кэш строк после фильтра

  /* Показать строки */
  document.getElementById('previewRowsBtn')?.addEventListener('click', () => {

    const file = document.querySelector('input[name="excel"]').files[0];
    if (!file) return alert('Сначала выберите Excel-файл');

    const filtVal = document.getElementById('filt').value;
    const custom  = parseInt(document.getElementById('customDays').value || '0', 10);
    const maxDays = (filtVal === 'all') ? null :
                    (filtVal === 'custom' ? custom : parseInt(filtVal, 10));

    const fr = new FileReader();
    fr.onload = e => {
      const wb   = XLSX.read(e.target.result, { type:'binary' });
      const ws   = wb.Sheets[wb.SheetNames[0]];
      const rows = XLSX.utils.sheet_to_json(ws, { header:1 });

      matched = [];
      for (let i = 1; i < rows.length; i++) {              // i=0 — заголовки
        const r = rows[i], exp = daysLeft(r[5]);
        const hit = maxDays === null
                  ? true
                  : (exp !== null && 0 <= exp && exp <= maxDays);
        if (hit) matched.push({A:r[0],B:r[1],C:r[2],D:r[3],E:r[4],F:r[5],expiry_days:exp});
        if (maxDays === null && matched.length === 200) break;  // «любой» → 200
      }

      document.getElementById('rowsPreviewBody').innerHTML = matched.map(r =>
        `<tr>${['A','B','C','D','E','F'].map(c=>`<td>${r[c]??''}</td>`).join('')}</tr>`
      ).join('');
      document.getElementById('rowsCnt').textContent = matched.length;
      bootstrap.Modal.getOrCreateInstance('#rowsPreviewModal').show();
    };
    fr.readAsBinaryString(file);
  });

  /* Предпросмотр шаблона */
  document.getElementById('previewTemplateBtn')?.addEventListener('click', () => {
    if (!matched.length) return alert('Сначала нажмите «Показать строки»');

    const subj = document.querySelector('input[name="subject"]').value;
    const body = document.querySelector('textarea[name="body"]').value;
    const row  = matched[0];

    document.getElementById('tmplSubj').textContent = render(subj, row);
    document.getElementById('tmplBody').innerHTML   = render(body, row);
    bootstrap.Modal.getOrCreateInstance('#tmplPreviewModal').show();
  });
});

