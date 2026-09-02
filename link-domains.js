// Makes the "domain" column clickable by wrapping each cell's text in a link
// to https://<domain>. Runs on every table draw so it survives sorting,
// filtering, and pagination.
(function () {
  var style = document.createElement('style');
  style.textContent = [
    '@media (min-width: 768px) {',
    '  html, body { overflow-x: hidden; }',
    '  .dataTables_wrapper { width: 100%; }',
    '  table.dataTable { table-layout: fixed; width: 100% !important; }',
    '  table.dataTable td, table.dataTable th { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }',
    '  table.dataTable td:first-child { width: 25%; }',
    '}',
    'table.dataTable td a { color: var(--ct-accent); }',
    'div.dts div.dt-scroll-body table { background-color: var(--ct-paper); }',
    'div.dt-container { background: var(--ct-paper); }',
    'table.dataTable tbody td { color: var(--ct-ink); }'
  ].join('\n');
  document.head.appendChild(style);
})();

(function () {
  var table = CsvToTable.table;

  function linkifyDomains() {
    table.column(0).nodes().each(function (cell) {
      if (cell.querySelector("a")) return;
      var text = cell.textContent.trim();
      if (!text) return;
      var url = /^https?:\/\//i.test(text) ? text : "https://" + text;
      var a = document.createElement("a");
      a.href = url;
      a.textContent = text;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      cell.textContent = "";
      cell.appendChild(a);
    });
  }

  table.on("draw", linkifyDomains);
  linkifyDomains();

  // --- "slashes" column filter -------------------------------------------
  // The "slashes" column holds a comma-separated list of slash pages found
  // per site (e.g. "now, about"). csvtotable's auto-generated per-column
  // filter is a single-select that only matches whole-cell values (e.g.
  // selecting "now" would miss "now, about"). Replace it with a checkbox
  // dropdown so multiple pages can be selected at once (OR semantics: any
  // selected page matches), and each page matches as a whole word anywhere
  // in the comma-separated list.
  var SENTINEL_TAGS = ["none", "unknown"];
  var headers = table.columns().header().toArray();
  var slashesColIdx = headers.findIndex(function (th) {
    return th.textContent.trim() === "pages";
  });
  if (slashesColIdx === -1) return;

  // Derive page tags from CSV data at runtime
  var tagSet = {};
  table.column(slashesColIdx).data().each(function (val) {
    (val || "").split(",").forEach(function (t) {
      t = t.trim();
      if (t && SENTINEL_TAGS.indexOf(t) === -1) tagSet[t] = true;
    });
  });
  var SLASH_TAGS = Object.keys(tagSet).sort();
  var allTags = SLASH_TAGS.concat(SENTINEL_TAGS);

  var params0 = new URLSearchParams(window.location.search);
  var selected = (params0.get("pages") || "").split(",").filter(function (t) {
    return allTags.indexOf(t) !== -1;
  });

  function applyFilter() {
    table.search.fixed("pages-filter", selected.length ? function (_, data) {
      var cell = (data[slashesColIdx] || "").trim();
      var cellPages = cell.split(",").map(function (s) { return s.trim(); });
      return selected.some(function (tag) { return cellPages.indexOf(tag) !== -1; });
    } : null);
    table.draw();
    syncPanels();
    var params = new URLSearchParams(window.location.search);
    if (selected.length) params.set("pages", selected.join(","));
    else params.delete("pages");
    var qs = params.toString();
    history.replaceState(null, "", qs ? "?" + qs : window.location.pathname);
  }

  var panels = [];

  function syncPanels() {
    panels.forEach(function (panel) {
      var count = selected.length;
      panel.summary.textContent = count ? "pages: " + selected.join(", ") : "Filter pages";
      panel.checkboxes.forEach(function (cb) {
        cb.checked = selected.indexOf(cb.value) !== -1;
      });
    });
  }

  function toggleTag(tag, checked) {
    var idx = selected.indexOf(tag);
    if (checked && idx === -1) selected.push(tag);
    if (!checked && idx !== -1) selected.splice(idx, 1);
    applyFilter();
  }

  // Hide all selects at the pages column index (tfoot has two)
  var filterCell = null;
  table.table().container().querySelectorAll("tfoot select").forEach(function (sel) {
    var cell = sel.closest("td, th");
    if (cell && cell.cellIndex === slashesColIdx) {
      sel.style.display = "none";
      filterCell = cell;
    }
  });

  var builtinFilters = [filterCell].filter(Boolean);
  builtinFilters.forEach(function (el) {

    var details = document.createElement("details");
    details.style.display = "inline-block";
    var summary = document.createElement("summary");
    summary.textContent = "Filter pages";
    summary.style.cursor = "pointer";
    details.appendChild(summary);

    var menu = document.createElement("div");
    menu.style.cssText =
      "display:flex;flex-direction:column;gap:2px;padding:.35rem .5rem;" +
      "border:1px solid rgba(127,127,127,.35);border-radius:6px;margin-top:2px;background:inherit;";

    var checkboxes = [];
    allTags.forEach(function (tag) {
      var label = document.createElement("label");
      label.style.cssText = "display:flex;align-items:center;gap:.35rem;font-weight:normal;white-space:nowrap;";
      var cb = document.createElement("input");
      cb.type = "checkbox";
      cb.value = tag;
      cb.addEventListener("change", function () {
        toggleTag(tag, cb.checked);
      });
      label.appendChild(cb);
      label.appendChild(document.createTextNode(tag));
      menu.appendChild(label);
      checkboxes.push(cb);
    });
    details.appendChild(menu);

    panels.push({ summary: summary, checkboxes: checkboxes });
    el.appendChild(details);
  });

  if (selected.length) applyFilter();

  // --- URL param sync: global search + column selects ---
  var initParams = new URLSearchParams(window.location.search);

  // Global search
  var initQ = initParams.get('q') || '';
  if (initQ) table.search(initQ).draw();
  var searchInput = table.table().container().querySelector('input[type="search"]');
  if (searchInput) {
    if (initQ) searchInput.value = initQ;
    searchInput.addEventListener('input', function () {
      var p = new URLSearchParams(window.location.search);
      if (searchInput.value) p.set('q', searchInput.value);
      else p.delete('q');
      var qs = p.toString();
      history.replaceState(null, '', qs ? '?' + qs : window.location.pathname);
    });
  }

  // Column selects (skip pages column — already handled above)
  table.table().container().querySelectorAll('tfoot select').forEach(function (sel) {
    var cell = sel.closest('td, th');
    if (!cell) return;
    var colIdx = cell.cellIndex;
    if (colIdx === slashesColIdx) return;
    var colName = (headers[colIdx] && headers[colIdx].textContent.trim().toLowerCase()) || ('col' + colIdx);
    var initVal = initParams.get(colName) || '';
    if (initVal) {
      sel.value = initVal;
      table.column(colIdx).search(initVal).draw();
    }
    sel.addEventListener('change', function () {
      var p = new URLSearchParams(window.location.search);
      if (sel.value) p.set(colName, sel.value);
      else p.delete(colName);
      var qs = p.toString();
      history.replaceState(null, '', qs ? '?' + qs : window.location.pathname);
    });
  });

  var scoreIdx = table.columns().header().toArray().map(function(th) { return th.textContent.trim(); }).indexOf('score');

  // Hide score column
  if (scoreIdx !== -1) {
    table.column(scoreIdx).visible(false);
  }

  // Shuffle rows: group by score (desc), shuffle within each group
  (function () {
    var rows = table.rows().data().toArray();

    function shuffle(arr) {
      for (var i = arr.length - 1; i > 0; i--) {
        var j = Math.floor(Math.random() * (i + 1));
        var tmp = arr[i]; arr[i] = arr[j]; arr[j] = tmp;
      }
    }

    if (scoreIdx === -1) {
      // no score column — fall back to plain shuffle
      shuffle(rows);
      table.clear().rows.add(rows).draw();
      return;
    }

    var groups = {};
    rows.forEach(function(row) {
      var s = parseInt(row[scoreIdx], 10) || 0;
      if (!groups[s]) groups[s] = [];
      groups[s].push(row);
    });

    var sorted = Object.keys(groups).map(Number).sort(function(a, b) { return b - a; });
    var result = [];
    sorted.forEach(function(s) {
      var g = groups[s];
      shuffle(g);
      result = result.concat(g);
    });

    table.clear().rows.add(result).draw();
  })();
})();
