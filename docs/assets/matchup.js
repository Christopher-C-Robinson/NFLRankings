(function () {
  "use strict";
  var site = window.NFLSite;
  if (!site) {
    var missing = document.getElementById("fresh");
    if (missing) missing.textContent = "Could not load this page. Hard-refresh and try again.";
    return;
  }
  var $ = function (id) { return document.getElementById(id); };
  var state = { data: null };

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function fmt(x, d) {
    if (x === null || x === undefined || isNaN(x)) return "–";
    var s = Number(x).toFixed(d);
    return s.indexOf("-") === 0 ? "−" + s.slice(1) : s;
  }
  function signed(x, d) {
    var n = Number(x);
    return (n > 0 ? "+" : "") + fmt(n, d);
  }
  function team(abbr) {
    return state.data.teams.filter(function (t) { return t.team === abbr; })[0];
  }
  function options(sel, teams, current) {
    sel.innerHTML = teams.map(function (t) {
      return '<option value="' + esc(t.team) + '">' + esc(t.name) + "</option>";
    }).join("");
    if (current && team(current)) sel.value = current;
  }
  function query() {
    var q = new URLSearchParams(location.search);
    return { season: q.get("season"), a: q.get("a"), b: q.get("b"), venue: q.get("venue") };
  }
  function writeQuery() {
    var season = $("season"), a = $("team-a"), b = $("team-b"), venue = $("venue");
    if (!season || !a || !b || !venue) return;
    var q = new URLSearchParams();
    q.set("season", season.value);
    q.set("a", a.value);
    q.set("b", b.value);
    q.set("venue", venue.value);
    history.replaceState(null, "", site.page("matchup.html?" + q.toString()));
  }
  function unit(label, a, b, key) {
    return "<tr><th scope=\"row\">" + label + "</th><td class=\"num\">" + fmt(a[key], 3) + "</td><td class=\"num\">" + fmt(b[key], 3) + "</td></tr>";
  }
  function render() {
    var aEl = $("team-a"), bEl = $("team-b"), venueEl = $("venue"), box = $("result");
    if (!aEl || !bEl || !box || !state.data) return;
    var a = team(aEl.value);
    var b = team(bEl.value);
    if (!a || !b) return;
    if (a.team === b.team) {
      box.innerHTML = '<p class="state">Pick two different teams.</p>';
      return;
    }
    var venueValue = venueEl ? venueEl.value : "neutral";
    var proj = NFLModel.project(a, b, state.data.ranking, venueValue, state.data.league_ppg || 0);
    var venue = venueEl && venueEl.selectedOptions && venueEl.selectedOptions[0] ? venueEl.selectedOptions[0].textContent : venueValue;
    var passEdge = (a.off_pass_epa_adj == null || b.def_pass_epa_adj == null) ? null : a.off_pass_epa_adj - b.def_pass_epa_adj;
    var rushEdge = (a.off_rush_epa_adj == null || b.def_rush_epa_adj == null) ? null : a.off_rush_epa_adj - b.def_rush_epa_adj;
    box.innerHTML =
      '<article class="matchup">' +
      '<p class="matchup-venue">' + esc(venue) + "</p>" +
      '<div class="matchup-score"><div><a class="teamlink" href="' + site.page("team.html?team=" + encodeURIComponent(a.team) + "&season=" + state.data.season) + '">' + esc(a.name) + "</a><strong>" + fmt(proj.scoreA, 1) + "</strong><span>" + (proj.winProbability * 100).toFixed(1) + "% win chance</span></div>" +
      "<div><a class=\"teamlink\" href=\"" + site.page("team.html?team=" + encodeURIComponent(b.team) + "&season=" + state.data.season) + "\">" + esc(b.name) + "</a><strong>" + fmt(proj.scoreB, 1) + "</strong><span>" + ((1 - proj.winProbability) * 100).toFixed(1) + "% win chance</span></div></div>" +
      "<dl class=\"matchup-facts\">" +
      "<dt>Spread, team A</dt><dd>" + signed(proj.margin, 1) + "</dd>" +
      "<dt>80% margin range</dt><dd>" + signed(proj.marginLow, 1) + " to " + signed(proj.marginHigh, 1) + "</dd>" +
      "<dt>Projected total</dt><dd>" + fmt(proj.total, 1) + "</dd>" +
      "<dt>A pass vs B defense</dt><dd>" + signed(passEdge, 3) + " EPA/play</dd>" +
      "<dt>A rush vs B defense</dt><dd>" + signed(rushEdge, 3) + " EPA/play</dd>" +
      "</dl>" +
      '<table class="units"><thead><tr><th></th><th class="num">' + esc(a.team) + '</th><th class="num">' + esc(b.team) + "</th></tr></thead><tbody>" +
      unit("Off pass EPA", a, b, "off_pass_epa_adj") +
      unit("Off rush EPA", a, b, "off_rush_epa_adj") +
      unit("Def pass EPA", a, b, "def_pass_epa_adj") +
      unit("Def rush EPA", a, b, "def_rush_epa_adj") +
      "</tbody></table></article>";
    writeQuery();
  }
  function load(season, picked) {
    return site.getJSON(site.data(season + ".json")).then(function (data) {
      state.data = data;
      var a = $("team-a"), b = $("team-b"), venue = $("venue");
      if (!a || !b) throw new Error("team controls are missing");
      var teams = data.teams.slice().sort(function (x, y) { return x.name.localeCompare(y.name); });
      options(a, teams, picked.a || teams[0].team);
      options(b, teams, picked.b || teams[1].team);
      if (picked.venue && venue) venue.value = picked.venue;
      site.setText("fresh", "Season " + data.season + " · Week " + data.week_max + " · generated " + String(data.generated_at || "").slice(0, 10));
      render();
    });
  }
  function init() {
    ["team-a", "team-b", "venue"].forEach(function (id) {
      var el = $(id);
      if (el) el.onchange = render;
    });
    site.getJSON(site.data("index.json")).then(function (idx) {
      var picked = query();
      var sel = $("season");
      if (!sel || !idx || !idx.seasons) throw new Error("season list missing");
      sel.innerHTML = idx.seasons.map(function (s) { return '<option value="' + s + '">' + s + "</option>"; }).join("");
      sel.value = picked.season && idx.seasons.indexOf(Number(picked.season)) >= 0 ? picked.season : idx.default_season;
      sel.onchange = function () {
        var a = $("team-a"), b = $("team-b"), venue = $("venue");
        load(sel.value, { a: a ? a.value : "", b: b ? b.value : "", venue: venue ? venue.value : "" });
      };
      return load(sel.value, picked);
    }).catch(function (e) {
      var msg = e && e.message ? e.message : "request failed";
      site.setText("fresh", "Could not load matchup data (" + msg + ").");
    });
  }
  init();
})();
