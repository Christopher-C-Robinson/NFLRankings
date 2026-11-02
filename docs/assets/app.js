(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var state = { index: null, data: null, model: "v2", open: null };

  function fmt(x, d) {
    if (x === null || x === undefined || isNaN(x)) return "–";
    var s = Number(x).toFixed(d);
    return s.indexOf("-") === 0 ? "−" + s.slice(1) : s;
  }
  function signed(x, d) { return (x > 0 ? "+" : "") + fmt(x, d); }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function record(t) { return t.wins + "-" + t.losses + (t.ties ? "-" + t.ties : ""); }

  function showError(msg) {
    $("tablewrap").hidden = true;
    var s = $("state"); s.hidden = false; s.className = "state error"; s.textContent = msg;
  }
  function showEmpty(msg) {
    $("tbody").innerHTML = "";
    var s = $("state"); s.hidden = false; s.className = "state"; s.textContent = msg;
    $("tablewrap").hidden = false;
  }
  function hideState() { $("state").hidden = true; $("tablewrap").hidden = false; }

  function getJSON(url) {
    return fetch(url, { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error(url + " returned HTTP " + r.status);
      return r.json();
    });
  }

  var COLS = {
    v2: [
      ["Rank", "rank"], ["Team", "team"], ["v2 rating", "num"], ["Adj off EPA", "num"],
      ["Adj def EPA", "num"], ["Record", "num"], ["Point diff", "num"], ["Legacy rank", "num"]
    ],
    legacy: [
      ["Rank", "rank"], ["Team", "team"], ["FUNCTION", "num"], ["Off FUNCTION", "num"],
      ["Def FUNCTION", "num"], ["Record", "num"], ["v2 rank", "num"]
    ]
  };

  function head() {
    $("thead").innerHTML = "<tr>" + COLS[state.model].map(function (c) {
      return '<th scope="col"' + (c[1] === "num" ? ' class="num"' : "") + ">" + c[0] + "</th>";
    }).join("") + "</tr>";
  }

  function detail(t, ncols) {
    function dl(c) {
      return "<dl>" + [
        ["Pts / drive", fmt(c.pts_per_drive, 2)], ["FG%", fmt(c.fg_pct, 3)], ["XP%", fmt(c.xp_pct, 3)],
        ["Yds / play", fmt(c.yards_per_play, 2)], ["1st down %", fmt(c.first_down_pct, 1)],
        ["3rd down rate", fmt(c.third_down_rate, 3)], ["Score %", fmt(c.score_pct, 1)],
        ["Turnover %", fmt(c.turnover_pct, 1)], ["Plays", c.plays], ["Drives", c.drives]
      ].map(function (r) { return "<dt>" + r[0] + "</dt><dd>" + r[1] + "</dd>"; }).join("") + "</dl>";
    }
    return '<tr class="detail"><td colspan="' + ncols + '"><div class="grid">' +
      "<div><h4>Offense (legacy inputs)</h4>" + dl(t.components.offense) + "</div>" +
      "<div><h4>Defense (allowed)</h4>" + dl(t.components.defense) + "</div>" +
      "<div><h4>EPA per play</h4><dl>" +
      "<dt>Off EPA (raw)</dt><dd>" + fmt(t.off_epa, 3) + "</dd>" +
      "<dt>Def EPA (raw)</dt><dd>" + fmt(t.def_epa, 3) + "</dd>" +
      "<dt>Off EPA (adj)</dt><dd>" + fmt(t.off_epa_adj, 3) + "</dd>" +
      "<dt>Def EPA (adj)</dt><dd>" + fmt(t.def_epa_adj, 3) + "</dd>" +
      "<dt>Off FUNCTION rank</dt><dd>" + t.off_function_rank + "</dd>" +
      "<dt>Def FUNCTION rank</dt><dd>" + t.def_function_rank + "</dd></dl></div>" +
      "</div></td></tr>";
  }

  function render() {
    if (!state.data) return;
    var m = state.model, conf = $("conf").value, dv = $("div").value, q = $("q").value.trim().toLowerCase();
    var key = m === "v2" ? "v2_rank" : "legacy_rank";
    var rows = state.data.teams.filter(function (t) {
      return (!conf || t.conference === conf) && (!dv || t.division === dv) &&
        (!q || t.name.toLowerCase().indexOf(q) >= 0 || t.team.toLowerCase().indexOf(q) >= 0);
    }).sort(function (a, b) { return a[key] - b[key] || a.name.localeCompare(b.name); });
    head();
    var ncols = COLS[m].length;
    if (!rows.length) { showEmpty("No teams match these filters."); return; }
    hideState();
    $("tbody").innerHTML = rows.map(function (t) {
      var cells;
      var nm = '<td class="teamname">' + esc(t.name) + "<small> " + esc(t.team) + "</small></td>";
      if (m === "v2") {
        cells = [
          '<td class="num rank">' + t.v2_rank + "</td>", nm,
          '<td class="num">' + fmt(t.v2, 3) + "</td>",
          '<td class="num">' + fmt(t.off_epa_adj, 3) + "</td>",
          '<td class="num">' + fmt(t.def_epa_adj, 3) + "</td>",
          '<td class="num">' + record(t) + "</td>",
          '<td class="num' + (t.point_diff < 0 ? " neg" : "") + '">' + signed(t.point_diff, 0) + "</td>",
          '<td class="num">' + t.legacy_rank + "</td>"
        ];
      } else {
        cells = [
          '<td class="num rank">' + t.legacy_rank + "</td>", nm,
          '<td class="num' + (t.legacy < 0 ? " neg" : "") + '">' + fmt(t.legacy, 0) + "</td>",
          '<td class="num">' + fmt(t.off_function, 0) + "</td>",
          '<td class="num">' + fmt(t.def_function, 0) + "</td>",
          '<td class="num">' + record(t) + "</td>",
          '<td class="num">' + t.v2_rank + "</td>"
        ];
      }
      var first = t[key] === 1 ? " first" : "";
      var open = state.open === t.team;
      return '<tr class="team' + first + '" tabindex="0" role="button" aria-expanded="' + open + '" data-team="' + esc(t.team) + '">' +
        cells.join("") + "</tr>" + (open ? detail(t, ncols) : "");
    }).join("");
  }

  function fillDivisions() {
    var sel = $("div"), conf = $("conf").value, seen = {};
    state.data.teams.forEach(function (t) { if (!conf || t.conference === conf) seen[t.division] = 1; });
    var cur = sel.value;
    sel.innerHTML = '<option value="">All</option>' + Object.keys(seen).sort().map(function (d) {
      return '<option value="' + esc(d) + '">' + esc(d) + "</option>";
    }).join("");
    if (seen[cur]) sel.value = cur;
  }

  function fresh() {
    var d = state.data, parts = ["Season " + d.season];
    if (d.week_max) parts.push("weeks " + d.week_min + "–" + d.week_max + (d.games_played ? " (" + d.games_played + " games)" : ""));
    parts.push("generated " + d.generated_at.replace("T", " ").replace(/\+00:00$/, " UTC"));
    parts.push("source: " + (state.index.source || d.source));
    $("fresh").textContent = parts.join(" · ");
  }

  function loadSeason(season) {
    return getJSON("data/" + season + ".json").then(function (d) {
      state.data = d; state.open = null; fillDivisions(); fresh(); render();
    }).catch(function (e) { showError("Could not load season " + season + ". " + e.message); });
  }

  function setModel(m) {
    state.model = m;
    $("m-v2").setAttribute("aria-pressed", m === "v2");
    $("m-legacy").setAttribute("aria-pressed", m === "legacy");
    render();
  }

  function init() {
    $("m-v2").onclick = function () { setModel("v2"); };
    $("m-legacy").onclick = function () { setModel("legacy"); };
    $("conf").onchange = function () { fillDivisions(); render(); };
    $("div").onchange = render;
    $("q").oninput = render;
    function toggle(tr) {
      var t = tr.getAttribute("data-team");
      state.open = state.open === t ? null : t;
      render();
      var again = document.querySelector('tr[data-team="' + t + '"]');
      if (again) again.focus();
    }
    $("tbody").addEventListener("click", function (e) {
      var tr = e.target.closest("tr.team"); if (tr) toggle(tr);
    });
    $("tbody").addEventListener("keydown", function (e) {
      if (e.key !== "Enter" && e.key !== " ") return;
      var tr = e.target.closest("tr.team"); if (tr) { e.preventDefault(); toggle(tr); }
    });
    head();
    getJSON("data/index.json").then(function (idx) {
      state.index = idx;
      if (!idx.seasons || !idx.seasons.length) { $("fresh").textContent = "No data yet."; showEmpty("No seasons have been built yet. Run python -m nflrankings --season latest."); return; }
      var sel = $("season");
      sel.innerHTML = idx.seasons.map(function (s) { return '<option value="' + s + '">' + s + "</option>"; }).join("");
      sel.value = idx.default_season;
      sel.onchange = function () { loadSeason(sel.value); };
      return loadSeason(idx.default_season);
    }).catch(function (e) {
      $("fresh").textContent = "Data unavailable.";
      showError("Rankings data is missing or could not be loaded (" + e.message + "). Run python -m nflrankings --season latest to generate docs/data.");
    });
  }
  init();
})();
