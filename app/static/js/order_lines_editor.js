document.addEventListener('DOMContentLoaded', function() {
  var root = document.getElementById('order-lines-root');
  if (!root) return;
  var orderId = root.getAttribute('data-order-id');
  if (!orderId) return;
  var table = document.createElement('table');
  table.className = 'table table-sm table-striped';
  var thead = document.createElement('thead');
  thead.innerHTML = '<tr><th>Part</th><th>Rev</th><th>Qty</th><th>UoM</th><th>Note</th><th>Job Required</th><th>Total Ordered</th><th>Actions</th></tr>';
  var tbody = document.createElement('tbody');
  table.appendChild(thead); table.appendChild(tbody); root.appendChild(table);

  function setLoading(msg) {
    tbody.innerHTML = '';
    var tr = document.createElement('tr');
    var td = document.createElement('td'); td.colSpan = 8; td.className = 'text-muted'; td.textContent = msg;
    tr.appendChild(td); tbody.appendChild(tr);
  }

  async function refresh() {
    setLoading('Loading...');
    try {
      var r = await fetch('/admin/orders/' + orderId + '/lines_json');
      if (!r.ok) { setLoading('Failed to load'); return; }
      var rows = await r.json();
      tbody.innerHTML = '';
      if (!rows.length) { setLoading('No lines'); return; }
      rows.forEach(function(x) {
        var tr = document.createElement('tr');
        function tdTxt(t){ var td=document.createElement('td'); td.textContent=t; return td; }
        tr.appendChild(tdTxt(x.pn || ''));
        tr.appendChild(tdTxt(x.rev || ''));
        var tdQty = document.createElement('td'); var iQty=document.createElement('input'); iQty.type='number'; iQty.step='1'; iQty.min='0'; iQty.value=String(x.qty||0); iQty.style.width='90px'; tdQty.appendChild(iQty); tr.appendChild(tdQty);
        var tdUom = document.createElement('td'); var iUom=document.createElement('input'); iUom.type='text'; iUom.value=String(x.uom||'EA'); iUom.style.width='80px'; tdUom.appendChild(iUom); tr.appendChild(tdUom);
        var tdNote = document.createElement('td'); var iNote=document.createElement('input'); iNote.type='text'; iNote.value=String(x.note||''); iNote.style.width='160px'; tdNote.appendChild(iNote); tr.appendChild(tdNote);
        tr.appendChild(tdTxt(String(x.job_required_qty||0)));
        tr.appendChild(tdTxt(String(x.total_ordered_for_job||0)));
        var tdAct = document.createElement('td');
        var btnSave=document.createElement('button'); btnSave.className='btn btn-sm btn-outline-primary me-1'; btnSave.textContent='Save';
        var btnRemove=document.createElement('button'); btnRemove.className='btn btn-sm btn-outline-danger'; btnRemove.textContent='Remove';
        tdAct.appendChild(btnSave); tdAct.appendChild(btnRemove); tr.appendChild(tdAct);
        btnSave.addEventListener('click', async function(){
          var body = {pn:x.pn, rev:(x.rev||''), qty: parseFloat(iQty.value||'0')||0, uom: iUom.value||'EA', note: iNote.value||''};
          await fetch('/admin/orders/'+orderId+'/lines_update', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
          refresh();
        });
        btnRemove.addEventListener('click', async function(){
          await fetch('/admin/orders/'+orderId+'/lines_remove', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({pn:x.pn, rev:(x.rev||'')})});
          refresh();
        });
        tbody.appendChild(tr);
      });
    } catch(e) { setLoading('Error'); }
  }
  // expose refresh and listen for external refresh events
  window._orderLinesRefresh = refresh;
  window.addEventListener('order-lines-refresh', refresh);
  refresh();
});
