(function(){
  const pn = window.BOM_PAGE.pn;

  // Root loader
  $('#bomTree').jstree({
    core: {
      data: function (obj, cb) {
        // obj.id === '#' means load root
        if (obj.id === '#') {
          $.getJSON('/bom/api/tree', { pn }, cb);
        } else {
          $.getJSON('/bom/api/tree', { id: obj.id }, cb);
        }
      },
      themes: { stripes: true }
    },
    plugins: ["wholerow"]   // feel free to add "search" plugin later
  });

  // Click handler (optional: link to child PN BOM)
  $('#bomTree').on('select_node.jstree', function (e, data) {
    const node = data.node;
    const childPn = node.id;
    // Example: navigate on Ctrl+Click
    // if (e.ctrlKey) window.location = '/bom/' + encodeURIComponent(childPn);
  });
})();
