(function () {
  "use strict";
  var site = window.NFLSite;
  if (!site) {
    var missing = document.getElementById("fresh");
    if (missing) missing.textContent = "Could not load this page. Hard-refresh and try again.";
    return;
  }
  var $ = function (id) { return document.getElementById(id); };
  var state = { index: null, data: null, open: {} };

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
    var wrap = $("tablewrap");
    if (wrap) wrap.hidden = true;
    var exp = $("export");
    if (exp) exp.disabled = true;
    var count = $("count");
    if (count) count.textContent = "";
    var s = $("state");
    if (s) { s.hidden = false; s.className = "state error"; s.textContent = msg; }
    var power = $("power-panel");
    if (power) power.hidden = true;
  }
  function showEmpty(msg) {
    var board = $("board");
    if (board) board.innerHTML = "";
    var s = $("state");
    if (s) { s.hidden = false; s.className = "state"; s.textContent = msg; }
    var wrap = $("tablewrap");
    if (wrap) wrap.hidden = false;
  }
  function hideState() {
    var s = $("state");
    if (s) s.hidden = true;
    var wrap = $("tablewrap");
    if (wrap) wrap.hidden = false;
  }

  function logo(t) {
    var color = accent(t);
    var src = https(t.logo);
    var style = color ? ' style="border-color:' + esc(color) + '"' : "";
    var img = src
      ? '<img alt="" width="30" height="30" src="' + esc(src) + '" loading="lazy" decoding="async" referrerpolicy="no-referrer" onload="this.parentNode.setAttribute(\'data-logo\',\'loaded\')" onerror="this.remove()">'
      : "";
    return '<span class="logo"' + style + ">" +
      '<span class="logo-fallback" aria-hidden="true">' + esc(t.team) + "</span>" + img + "</span>";
  }

  function stat(label, value, neg) {
    return "<div><dt>" + label + "</dt><dd" + (neg ? ' class="neg"' : "") + ">" + value + "</dd></div>";
  }

  function detail(t, open) {
    var rank = state.data.ranking || {};
    var hfa = Number(rank.home_field_points);
    var home = isNaN(hfa) ? "" : stat("Home margin vs field", signed(t.mean_margin + hfa, 1), t.mean_margin + hfa < 0);
    var href = site.page("team.html?team=" + encodeURIComponent(t.team) + "&season=" + encodeURIComponent(state.data.season));
    return '<div class="rank-detail" id="detail-' + esc(t.team) + '"' + (open ? "" : " hidden") + ">" +
      '<dl class="stat-grid">' +
      stat("Neutral margin", signed(t.mean_margin, 1), t.mean_margin < 0) +
      stat("v2 EPA", fmt(t.v2, 3), t.v2 < 0) +
      stat("Record", record(t), false) +
      stat("Point diff", signed(t.point_diff, 0), t.point_diff < 0) +
      stat("SOS", fmt(t.sos, 3), t.sos < 0) +
      stat("Wins above expected", signed(t.wins_above_expected, 1), t.wins_above_expected < 0) +
      stat("Expected wins vs 31", fmt(t.expected_wins, 2), false) +
      stat("v2 rank", t.v2_rank, false) +
      home +
      stat("Off EPA (adj)", fmt(t.off_epa_adj, 3), t.off_epa_adj < 0) +
      stat("Def EPA (adj)", fmt(t.def_epa_adj, 3), false) +
      stat("Off EPA (raw)", fmt(t.off_epa, 3), t.off_epa < 0) +
      stat("Def EPA (raw)", fmt(t.def_epa, 3), false) +
      stat("Off pass EPA", fmt(t.off_pass_epa_adj, 3), t.off_pass_epa_adj < 0) +
      stat("Off rush EPA", fmt(t.off_rush_epa_adj, 3), t.off_rush_epa_adj < 0) +
      stat("Division", esc(t.division || t.conference || "–"), false) +
      (t.division_power == null ? "" : stat("Division power", signed(t.division_power, 1), t.division_power < 0)) +
      (t.conference_power == null ? "" : stat("Conference power", signed(t.conference_power, 1), t.conference_power < 0)) +
      "</dl><p class=\"detail-link\"><a href=\"" + href + "\">Team page</a></p></div>";
  }

  function visible() {
    var confEl = $("conf"), divEl = $("div"), qEl = $("q");
    var conf = confEl ? confEl.value : "", dv = divEl ? divEl.value : "";
    var q = qEl ? qEl.value.trim().toLowerCase() : "";
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
    var total = state.data.teams.length;
    var count = $("count");
    if (count) count.textContent = rows.length === total
      ? total + " teams shown · " + total + " rated · full league"
      : "Showing " + rows.length + " of " + total + " · ranks stay the full-league order";
    if (!rows.length) { showEmpty("No teams match these filters."); return; }
    hideState();
    var board = $("board");
    if (!board) return;
    board.innerHTML = rows.map(function (t) {
      var open = !!state.open[t.team];
      var href = site.page("team.html?team=" + encodeURIComponent(t.team) + "&season=" + encodeURIComponent(state.data.season));
      return '<article class="rank-row' + (open ? " is-expanded" : "") + '" role="listitem" data-team="' + esc(t.team) + '">' +
        '<div class="rank-main">' +
        '<span class="rank-number">' + t.win_chance_rank + "</span>" +
        logo(t) +
        '<a class="rank-team" href="' + href + '"><span class="rank-team-name">' + esc(t.name) + '</span><span class="rank-abbr">' + esc(t.team) + "</span></a>" +
        '<span class="rank-index" title="Average chance to beat each of the other 31 teams on a neutral field"><span class="rank-index-label">Neutral win</span>' + pct(t.win_chance) + "</span>" +
        '<button type="button" class="rank-toggle" data-team="' + esc(t.team) + '" data-name="' + esc(t.name) + '" aria-expanded="' + (open ? "true" : "false") + '" aria-controls="detail-' + esc(t.team) + '" aria-label="' + (open ? "Hide" : "Show") + " ranking details for " + esc(t.name) + '"><span class="rank-toggle-icon" aria-hidden="true"></span></button>' +
        "</div>" + detail(t, open) + "</article>";
    }).join("");
  }

  function csvCell(value) {
    return '"' + String(value == null ? "" : value).replace(/"/g, '""') + '"';
  }

  function exportCsv() {
    if (!state.data) return;
    var rows = [["Rank", "Team", "Abbr", "Conference", "Division", "Wins", "Losses", "Ties",
      "Avg win chance", "Neutral margin", "Expected wins", "v2 EPA", "v2 rank",
      "Adj off EPA", "Adj def EPA", "Point diff", "SOS", "Wins above expected", "Division power", "Conference power"]];
    visible().forEach(function (t) {
      rows.push([t.win_chance_rank, t.name, t.team, t.conference, t.division, t.wins, t.losses, t.ties,
        (t.win_chance * 100).toFixed(2), Number(t.mean_margin).toFixed(2), Number(t.expected_wins).toFixed(2),
        Number(t.v2).toFixed(3), t.v2_rank, Number(t.off_epa_adj).toFixed(3), Number(t.def_epa_adj).toFixed(3), t.point_diff,
        t.sos == null ? "" : Number(t.sos).toFixed(3), t.wins_above_expected == null ? "" : Number(t.wins_above_expected).toFixed(2),
        t.division_power == null ? "" : Number(t.division_power).toFixed(2),
        t.conference_power == null ? "" : Number(t.conference_power).toFixed(2)]);
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
    var sel = $("div");
    if (!sel || !state.data) return;
    var confEl = $("conf");
    var conf = confEl ? confEl.value : "", seen = {};
    state.data.teams.forEach(function (t) { if ((!conf || t.conference === conf) && t.division) seen[t.division] = 1; });
    var cur = sel.value;
    sel.innerHTML = '<option value="">All</option>' + Object.keys(seen).sort().map(function (d) {
      return '<option value="' + esc(d) + '">' + esc(d) + "</option>";
    }).join("");
    if (seen[cur]) sel.value = cur;
  }

  function fresh() {
    var d = state.data;
    var parts = ["Season " + d.season];
    if (d.week_max) parts.push("Week " + d.week_max);
    var gen = String(d.generated_at || "").slice(0, 10);
    if (gen) parts.push("generated " + gen);
    site.setText("fresh", parts.join(" · "));
    var hfa = d.ranking && d.ranking.home_field_points;
    var note = $("home-note");
    if (note && hfa != null) note.textContent = "Home field is " + signed(hfa, 2) + " points and is not used in the rank. Every team faces the other 31 on a neutral field.";
  }

  function renderPower() {
    var panel = $("power-panel");
    var board = $("power-board");
    var gp = state.data && state.data.group_power;
    if (!panel || !board) return;
    if (!gp || !gp.conferences || !gp.divisions) {
      panel.hidden = true;
      return;
    }
    panel.hidden = false;
    var note = $("power-note");
    if (note) note.textContent = gp.tuning || "";
    function body(items, withConference) {
      return items.map(function (item) {
        return "<tr><th scope=\"row\">" + esc(item.name) + "</th>" +
          (withConference ? "<td>" + esc(item.conference || "") + "</td>" : "") +
          "<td class=\"num\">" + signed(item.points, 1) + "</td><td class=\"num\">" + item.teams + "</td></tr>";
      }).join("");
    }
    board.innerHTML =
      '<div class="power-columns">' +
      '<div class="tablewrap"><table class="power"><thead><tr><th>Conference</th><th class="num">Power</th><th class="num">Teams</th></tr></thead><tbody>' +
      body(gp.conferences, false) + "</tbody></table></div>" +
      '<div class="tablewrap"><table class="power"><thead><tr><th>Division</th><th>Conference</th><th class="num">Power</th><th class="num">Teams</th></tr></thead><tbody>' +
      body(gp.divisions, true) + "</tbody></table></div></div>";
  }

  function loadSeason(season) {
    return site.getJSON(site.data(season + ".json")).then(function (d) {
      if (!d.teams || !d.teams.length || d.teams[0].win_chance_rank == null) {
        site.setText("fresh", "Could not load rankings (season " + season + " has no win-chance ranks).");
        showError("Season " + season + " has no win-chance ranks. Rebuild with python -m nflrankings.");
        return;
      }
      state.data = d;
      state.open = {};
      var exp = $("export");
      if (exp) exp.disabled = false;
      fillDivisions();
      fresh();
      render();
      renderPower();
    }).catch(function (e) {
      var msg = e && e.message ? e.message : "request failed";
      site.setText("fresh", "Could not load rankings (" + msg + ").");
      showError("Could not load season " + season + ". " + msg);
    });
  }

  function init() {
    var exp = $("export");
    if (exp) exp.onclick = exportCsv;
    var conf = $("conf");
    if (conf) conf.onchange = function () { fillDivisions(); render(); };
    var div = $("div");
    if (div) div.onchange = render;
    var q = $("q");
    if (q) q.oninput = render;
    var board = $("board");
    if (board) board.addEventListener("click", function (e) {
      var target = e.target;
      if (!target || !target.closest) return;
      var btn = target.closest(".rank-toggle");
      if (!btn) return;
      var team = btn.getAttribute("data-team");
      var open = !state.open[team];
      state.open[team] = open;
      var row = btn.closest(".rank-row");
      var detailEl = document.getElementById("detail-" + team);
      if (row) row.classList.toggle("is-expanded", open);
      if (detailEl) detailEl.hidden = !open;
      btn.setAttribute("aria-expanded", open ? "true" : "false");
      btn.setAttribute("aria-label", (open ? "Hide" : "Show") + " ranking details for " + btn.getAttribute("data-name"));
    });
    site.getJSON(site.data("index.json")).then(function (idx) {
      state.index = idx;
      if (!idx || !idx.seasons || !idx.seasons.length) {
        site.setText("fresh", "No data yet.");
        showEmpty("No seasons have been built yet. Run python -m nflrankings --season latest.");
        return;
      }
      var sel = $("season");
      if (!sel) {
        site.setText("fresh", "Could not load rankings (season control is missing).");
        showError("Season control is missing from the page.");
        return;
      }
      sel.innerHTML = idx.seasons.map(function (s) { return '<option value="' + s + '">' + s + "</option>"; }).join("");
      sel.value = idx.default_season;
      sel.onchange = function () { loadSeason(sel.value); };
      return loadSeason(idx.default_season);
    }).catch(function (e) {
      var msg = e && e.message ? e.message : "request failed";
      site.setText("fresh", "Could not load rankings (" + msg + ").");
      showError("Rankings data is missing or could not be loaded (" + msg + "). Run python -m nflrankings --season latest to generate docs/data.");
    });
  }
  init();
})();
