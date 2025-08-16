(function(){
  const pn = window.BOM_PAGE.pn;
  const COL = { parent_pn:0, parent_desc:1, qty:2, uom:3, alt:4 };

  const dt = $('#whereUsedTable').DataTable({
    processing: true,
    serverSide: true,
    orderCellsTop: true,
    fixedHeader: true,
    searchDelay: 250,
    lengthMenu: [10,25,50,100],
    order: [[COL.parent_pn, 'asc']],
    ajax: {
      url: '/bom/api/whereused',
      type: 'GET',
      data: function (d) {
        d.pn = pn;
        const $f = $('#filters');
        // basic two column filters (pn/desc) + alt text box for now
        const pnVal = $f.find('th:eq('+COL.parent_pn+') input').val() || '';
        const descVal = $f.find('th:eq('+COL.parent_desc+') input').val() || '';
        const altVal = $f.find('th:eq('+COL.alt+') input').val() || '';

        // Use DataTables column search fields to piggyback (optional)
        d.columns = d.columns || [];
        d.columns[COL.parent_pn] = { search: { value: pnVal } };
        d.columns[COL.parent_desc] = { search: { value: descVal } };
        d.columns[COL.alt] = { search: { value: altVal } };
      }
    }
  });

  $('#filters input').on('keyup change', function(){ dt.draw(); });
})();
