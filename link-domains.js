// Makes the "domain" column clickable by wrapping each cell's text in a link
// to https://<domain>. Runs on every table draw so it survives sorting,
// filtering, and pagination.
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
  var SLASH_TAGS = ["now", "about", "friends", "ideas"];
  var EXTRA_TAGS = ["none", "unknown"];
  var headers = table.columns().header().toArray();
  var slashesColIdx = headers.findIndex(function (th) {
    return th.textContent.trim() === "slashes";
  });
  if (slashesColIdx === -1) return;

  var selected = [];

  function patternFor(tag) {
    return tag === "none" || tag === "unknown" ? "^" + tag + "$" : "\\b" + tag + "\\b";
  }

  function applyFilter() {
    var pattern = selected.map(patternFor).join("|");
    table.column(slashesColIdx).search(pattern, true, false).draw();
    syncPanels();
  }

  var panels = [];

  function syncPanels() {
    panels.forEach(function (panel) {
      var count = selected.length;
      panel.summary.textContent = count ? "slashes: " + selected.join(", ") : "Filter slashes";
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

  var builtinFilters = document.querySelectorAll('[aria-label="Filter slashes"]');
  builtinFilters.forEach(function (el) {
    el.style.display = "none";

    var details = document.createElement("details");
    details.style.display = "inline-block";
    var summary = document.createElement("summary");
    summary.textContent = "Filter slashes";
    summary.style.cursor = "pointer";
    details.appendChild(summary);

    var menu = document.createElement("div");
    menu.style.cssText =
      "display:flex;flex-direction:column;gap:2px;padding:.35rem .5rem;" +
      "border:1px solid rgba(127,127,127,.35);border-radius:6px;margin-top:2px;background:inherit;";

    var checkboxes = [];
    SLASH_TAGS.concat(EXTRA_TAGS).forEach(function (tag) {
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
    el.parentNode.insertBefore(details, el.nextSibling);
  });

  // Stay in sync if the filter is cleared some other way (the active-filter
  // chip's "x", or the "clear all" control), so checkboxes don't show stale
  // state after an external reset.
  table.on("search.dt", function () {
    var current = table.column(slashesColIdx).search();
    var tags = current
      ? current
          .split("|")
          .map(function (part) {
            var match = part.match(/^\^(.*)\$$/) || part.match(/^\\b(.*)\\b$/);
            return match ? match[1] : null;
          })
          .filter(Boolean)
      : [];
    var changed = tags.length !== selected.length || tags.some(function (t) {
      return selected.indexOf(t) === -1;
    });
    if (changed) {
      selected = tags;
      syncPanels();
    }
  });
})();
