(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var state = { index: null, data: null, open: null };

  function fmt(x, d) {
    if (x === null || x === undefined || isNaN(x)) return "–";
    var s = Number(x).toFixed(d);
    return s.indexOf("-") === 0 ? "−" + s.slice(1) : s;
  }
  function signed(x, d) {
    var n = Number(x);
    return (n > 0 ? "+" : "") + fmt(n, d);
  }
  function pct(x) { return (Number(x) * 100).toFixed(1) + "%"; }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function record(t) { return t.wins + "-" + t.losses + (t.ties ? "-" + t.ties : ""); }
  function accent(t) { return /^#[0-9A-Fa-f]{6}$/.test(t.color || "") ? t.color : ""; }
  function https(url) { return typeof url === "string" && /^https:\/\/[^\s\\]+$/.test(url) ? url : ""; }

  function showError(msg) {
    $("tablewrap").hidden = true;
    $("export").disabled = true;
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

  var COLS = [
    ["Rank", "rank"], ["Team", "team"], ["Avg win chance", "num"], ["Neutral margin", "num"],
    ["v2 EPA", "num"], ["Record", "num"], ["Point diff", "num"], ["SOS", "num"], ["WAE", "num"]
  ];

  function head() {
    $("thead").innerHTML = "<tr>" + COLS.map(function (c) {
      var tip = c[0] === "Neutral margin" ? ' title="Average point margin if this team played each of the other 31 on a neutral field"' : "";
      var tip2 = c[0] === "v2 EPA" ? ' title="Schedule-adjusted EPA per play, offense minus defense"' : "";
      var tip3 = c[0] === "Avg win chance" ? ' title="Average chance to beat each of the other 31 teams on a neutral field"' : "";
      return '<th scope="col"' + (c[1] === "num" ? ' class="num"' : "") + tip + tip2 + tip3 + ">" + c[0] + "</th>";
    }).join("") + "</tr>";
  }

  function logo(t) {
    var color = accent(t);
    var src = https(t.logo);
    var style = color ? ' style="background:' + esc(color) + '"' : "";
    var img = src
      ? '<img alt="" width="28" height="28" src="' + esc(src) + '" loading="lazy" decoding="async" onerror="this.remove()">'
      : "";
    return '<span class="logo"' + style + ">" +
      '<span class="logo-fallback">' + esc(t.team) + "</span>" + img + "</span>";
  }

  function detail(t) {
    var rank = state.data.ranking || {};
    var hfa = Number(rank.home_field_points);
    var homeLine = isNaN(hfa) ? "" : "<dt>Home margin vs the field</dt><dd>" + signed(t.mean_margin + hfa, 1) + "</dd>";
    return '<tr class="detail"><td colspan="' + COLS.length + '"><div class="grid">' +
      "<div><h4>Win chance</h4><dl>" +
      "<dt>Avg win chance</dt><dd>" + pct(t.win_chance) + "</dd>" +
      "<dt>Expected wins vs 31</dt><dd>" + fmt(t.expected_wins, 2) + "</dd>" +
      "<dt>Neutral margin</dt><dd>" + signed(t.mean_margin, 1) + "</dd>" +
      homeLine +
      "<dt>v2 rank</dt><dd>" + t.v2_rank + "</dd>" +
      "</dl></div>" +
      "<div><h4>EPA per play</h4><dl>" +
      "<dt>Off EPA (raw)</dt><dd>" + fmt(t.off_epa, 3) + "</dd>" +
      "<dt>Def EPA (raw)</dt><dd>" + fmt(t.def_epa, 3) + "</dd>" +
      "<dt>Off EPA (adj)</dt><dd>" + fmt(t.off_epa_adj, 3) + "</dd>" +
      "<dt>Def EPA (adj)</dt><dd>" + fmt(t.def_epa_adj, 3) + "</dd>" +
      "<dt>v2 margin</dt><dd>" + fmt(t.v2, 3) + "</dd>" +
      "<dt>Off pass EPA</dt><dd>" + fmt(t.off_pass_epa_adj, 3) + "</dd>" +
      "<dt>Off rush EPA</dt><dd>" + fmt(t.off_rush_epa_adj, 3) + "</dd>" +
      "</dl><p class=\"detail-link\"><a href=\"" +
      ("team.html?team=" + encodeURIComponent(t.team) + "&season=" + encodeURIComponent(state.data.season)) +
      "\">Team page</a></p></div>" +
      "<div><h4>" + esc(t.conference || "League") + "</h4><dl>" +
      "<dt>Division</dt><dd>" + esc(t.division || "–") + "</dd>" +
      "<dt>Record</dt><dd>" + record(t) + "</dd>" +
      "<dt>Point diff</dt><dd>" + signed(t.point_diff, 0) + "</dd>" +
      "</dl></div></div></td></tr>";
  }

  function visible() {
    var conf = $("conf").value, dv = $("div").value, q = $("q").value.trim().toLowerCase();
    return state.data.teams.filter(function (t) {
      return (!conf || t.conference === conf) && (!dv || t.division === dv) &&
        (!q || t.name.toLowerCase().indexOf(q) >= 0 || t.team.toLowerCase().indexOf(q) >= 0);
    }).sort(function (a, b) {
      return a.win_chance_rank - b.win_chance_rank || a.name.localeCompare(b.name);
    });
  }

  function render() {
    if (!state.data) return;
    var rows = visible();
    head();
    var total = state.data.teams.length;
    $("count").textContent = rows.length === total
      ? total + " teams. Ranks are the full-league order."
      : "Showing " + rows.length + " of " + total + ". Ranks stay the full-league order.";
    if (!rows.length) { showEmpty("No teams match these filters."); return; }
    hideState();
    $("tbody").innerHTML = rows.map(function (t) {
      var color = accent(t);
      var style = color ? ' style="--accent:' + esc(color) + '"' : "";
      var open = state.open === t.team;
      var href = "team.html?team=" + encodeURIComponent(t.team) + "&season=" + encodeURIComponent(state.data.season);
      var nm = '<td class="teamcell"><span class="rankbadge">' + t.win_chance_rank + "</span>" + logo(t) +
        '<span class="teamname"><a class="teamlink" href="' + href + '">' + esc(t.name) + "</a><small>" + esc(t.team) + "</small></span></td>";
      var cells = [
        '<td class="num rank">' + t.win_chance_rank + "</td>",
        nm,
        '<td class="num win" data-label="Avg win chance">' + pct(t.win_chance) + "</td>",
        '<td class="num" data-label="Neutral margin">' + signed(t.mean_margin, 1) + "</td>",
        '<td class="num" data-label="v2 EPA">' + fmt(t.v2, 3) + "</td>",
        '<td class="num" data-label="Record">' + record(t) + "</td>",
        '<td class="num' + (t.point_diff < 0 ? " neg" : "") + '" data-label="Point diff">' + signed(t.point_diff, 0) + "</td>",
        '<td class="num" data-label="SOS">' + fmt(t.sos, 3) + "</td>",
        '<td class="num' + (t.wins_above_expected < 0 ? " neg" : "") + '" data-label="Wins above expected">' + signed(t.wins_above_expected, 1) + "</td>"
      ];
      var first = t.win_chance_rank === 1 ? " first" : "";
      return '<tr class="team' + first + '" tabindex="0" role="button" aria-expanded="' + open + '" data-team="' + esc(t.team) + '"' + style + ">" +
        cells.join("") + "</tr>" + (open ? detail(t) : "");
    }).join("");
  }

  function csvCell(value) {
    return '"' + String(value == null ? "" : value).replace(/"/g, '""') + '"';
  }

  function exportCsv() {
    if (!state.data) return;
    var rows = [["Rank", "Team", "Abbr", "Conference", "Division", "Wins", "Losses", "Ties",
      "Avg win chance", "Neutral margin", "Expected wins", "v2 EPA", "v2 rank",
      "Adj off EPA", "Adj def EPA", "Point diff", "SOS", "Wins above expected"]];
    visible().forEach(function (t) {
      rows.push([t.win_chance_rank, t.name, t.team, t.conference, t.division, t.wins, t.losses, t.ties,
        (t.win_chance * 100).toFixed(2), Number(t.mean_margin).toFixed(2), Number(t.expected_wins).toFixed(2),
        Number(t.v2).toFixed(3), t.v2_rank, Number(t.off_epa_adj).toFixed(3), Number(t.def_epa_adj).toFixed(3), t.point_diff,
        t.sos == null ? "" : Number(t.sos).toFixed(3), t.wins_above_expected == null ? "" : Number(t.wins_above_expected).toFixed(2)]);
    });
    var blob = new Blob([rows.map(function (r) { return r.map(csvCell).join(","); }).join("\n") + "\n"], { type: "text/csv;charset=utf-8" });
    var link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "nfl-rankings-" + state.data.season + ".csv";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(link.href);
  }

  function fillDivisions() {
    var sel = $("div"), conf = $("conf").value, seen = {};
    state.data.teams.forEach(function (t) { if ((!conf || t.conference === conf) && t.division) seen[t.division] = 1; });
    var cur = sel.value;
    sel.innerHTML = '<option value="">All</option>' + Object.keys(seen).sort().map(function (d) {
      return '<option value="' + esc(d) + '">' + esc(d) + "</option>";
    }).join("");
    if (seen[cur]) sel.value = cur;
  }

  function fresh() {
    var d = state.data, rank = d.ranking || {}, parts = ["Season " + d.season];
    if (d.week_max) parts.push("weeks " + d.week_min + "–" + d.week_max + (d.games_played ? " (" + d.games_played + " games)" : ""));
    parts.push("ranked by average neutral win chance");
    if (rank.home_field_points != null) parts.push("home field " + signed(rank.home_field_points, 2) + " pts, not used in the rank");
    parts.push("generated " + String(d.generated_at).replace("T", " ").replace(/\+00:00$/, " UTC"));
    $("fresh").textContent = parts.join(" · ");
  }

  function loadSeason(season) {
    return getJSON("data/" + season + ".json").then(function (d) {
      if (!d.teams || !d.teams.length || d.teams[0].win_chance_rank == null) {
        showError("Season " + season + " has no win-chance ranks. Rebuild with python -m nflrankings.");
        return;
      }
      state.data = d;
      state.open = null;
      $("export").disabled = false;
      fillDivisions();
      fresh();
      render();
    }).catch(function (e) { showError("Could not load season " + season + ". " + e.message); });
  }

  function init() {
    $("export").onclick = exportCsv;
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
      if (e.target.closest("a")) return;
      var tr = e.target.closest("tr.team"); if (tr) toggle(tr);
    });
    $("tbody").addEventListener("keydown", function (e) {
      if (e.key !== "Enter" && e.key !== " ") return;
      var tr = e.target.closest("tr.team"); if (tr) { e.preventDefault(); toggle(tr); }
    });
    head();
    getJSON("data/index.json").then(function (idx) {
      state.index = idx;
      if (!idx.seasons || !idx.seasons.length) {
        $("fresh").textContent = "No data yet.";
        showEmpty("No seasons have been built yet. Run python -m nflrankings --season latest.");
        return;
      }
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
