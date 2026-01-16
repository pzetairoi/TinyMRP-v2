document.addEventListener('DOMContentLoaded', function() {
  var root = document.getElementById('job-bom-root');
  if (!root) return;
  var jobId = root.getAttribute('data-job-id');
  if (!jobId) return;
  var table = document.createElement('table');
  table.className = 'table table-sm table-striped';
  var thead = document.createElement('thead');
  thead.innerHTML = '<tr><th>Part</th><th>Rev</th><th>Qty</th><th>Ordered</th><th>Remaining</th><th>Orders</th><th>Actions</th></tr>';
  var tbody = document.createElement('tbody');
  table.appendChild(thead); table.appendChild(tbody); root.appendChild(table);

  function setLoading(msg) {
    tbody.innerHTML = '';
    var tr = document.createElement('tr');
    var td = document.createElement('td'); td.colSpan = 7; td.className = 'text-muted'; td.textContent = msg;
    tr.appendChild(td); tbody.appendChild(tr);
  }

  async function refresh() {
    setLoading('Loading...');
    try {
      var r = await fetch('/admin/jobs/' + jobId + '/bom_json');
      if (!r.ok) { setLoading('Failed to load'); return; }
      var rows = await r.json();
      tbody.innerHTML = '';
      if (!rows.length) { setLoading('No lines'); return; }
      var canManage = true;
      if (rows[0] && rows[0].can_manage === false) canManage = false;
      rows.forEach(function(x) {
        var tr = document.createElement('tr');
        function tdTxt(t){ var td=document.createElement('td'); td.textContent=t; return td; }
        tr.appendChild(tdTxt(x.pn || ''));
        tr.appendChild(tdTxt(x.rev || ''));
        var tdQty = document.createElement('td');
        var input = document.createElement('input'); input.type='number'; input.step='1'; input.min='0'; input.value=String(x.qty||0); input.style.width='90px';
        if (!canManage) { input.disabled = true; }
        tdQty.appendChild(input); tr.appendChild(tdQty);
        tr.appendChild(tdTxt(String(x.ordered_qty||0)));
        tr.appendChild(tdTxt(String(x.remaining_qty||0)));
        var tdOrders = document.createElement('td');
        if (Array.isArray(x.orders) && x.orders.length){
          x.orders.forEach(function(o,idx){ var a=document.createElement('a'); a.href=o.href; a.textContent=o.order_number; tdOrders.appendChild(a); if(idx<x.orders.length-1){ tdOrders.appendChild(document.createTextNode(', ')); } });
        }
        tr.appendChild(tdOrders);
        var tdAct = document.createElement('td');
        if (canManage) {
          var btnSave=document.createElement('button'); btnSave.className='btn btn-sm btn-outline-primary me-1'; btnSave.textContent='Save';
          var btnRemove=document.createElement('button'); btnRemove.className='btn btn-sm btn-outline-danger'; btnRemove.textContent='Remove';
          tdAct.appendChild(btnSave); tdAct.appendChild(btnRemove); tr.appendChild(tdAct);
          btnSave.addEventListener('click', async function(){
            var qty=parseFloat(input.value||'0')||0;
            var resp = await fetch('/admin/jobs/'+jobId+'/bom_update', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({pn:x.pn, rev:(x.rev||''), line_rev:(x.line_rev||''), qty:qty})});
            if (!resp.ok) { alert('Update failed.'); return; }
            refresh();
          });
          btnRemove.addEventListener('click', async function(){
            var resp = await fetch('/admin/jobs/'+jobId+'/bom_remove', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({pn:x.pn, rev:(x.rev||''), line_rev:(x.line_rev||'')})});
            if (!resp.ok) { alert('Remove failed.'); return; }
            refresh();
          });
        } else {
          tdAct.textContent = 'Read-only';
          tr.appendChild(tdAct);
        }
        tbody.appendChild(tr);
      });
    } catch(e){ setLoading('Error'); }
  }
  // expose refresh and listen for external refresh events
  window._jobBomRefresh = refresh;
  window.addEventListener('job-bom-refresh', refresh);
  refresh();
});
