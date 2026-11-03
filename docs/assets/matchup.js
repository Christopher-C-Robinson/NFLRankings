(function () {
  "use strict";
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
    var q = new URLSearchParams();
    q.set("season", $("season").value);
    q.set("a", $("team-a").value);
    q.set("b", $("team-b").value);
    q.set("venue", $("venue").value);
    history.replaceState(null, "", "matchup.html?" + q.toString());
  }
  function unit(label, a, b, key) {
    return "<tr><th scope=\"row\">" + label + "</th><td class=\"num\">" + fmt(a[key], 3) + "</td><td class=\"num\">" + fmt(b[key], 3) + "</td></tr>";
  }
  function render() {
    var a = team($("team-a").value);
    var b = team($("team-b").value);
    var box = $("result");
    if (!a || !b) return;
    if (a.team === b.team) {
      box.innerHTML = '<p class="state">Pick two different teams.</p>';
      return;
    }
    var proj = NFLModel.project(a, b, state.data.ranking, $("venue").value, state.data.league_ppg || 0);
    var venue = $("venue").selectedOptions[0].textContent;
    var passEdge = (a.off_pass_epa_adj == null || b.def_pass_epa_adj == null) ? null : a.off_pass_epa_adj - b.def_pass_epa_adj;
    var rushEdge = (a.off_rush_epa_adj == null || b.def_rush_epa_adj == null) ? null : a.off_rush_epa_adj - b.def_rush_epa_adj;
    box.innerHTML =
      '<article class="matchup">' +
      '<p class="matchup-venue">' + esc(venue) + "</p>" +
      '<div class="matchup-score"><div><a class="teamlink" href="team.html?team=' + esc(a.team) + "&season=" + state.data.season + '">' + esc(a.name) + "</a><strong>" + fmt(proj.scoreA, 1) + "</strong><span>" + (proj.winProbability * 100).toFixed(1) + "% win chance</span></div>" +
      "<div><a class=\"teamlink\" href=\"team.html?team=" + esc(b.team) + "&season=" + state.data.season + "\">" + esc(b.name) + "</a><strong>" + fmt(proj.scoreB, 1) + "</strong><span>" + ((1 - proj.winProbability) * 100).toFixed(1) + "% win chance</span></div></div>" +
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
    return fetch("data/" + season + ".json", { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).then(function (data) {
      state.data = data;
      var teams = data.teams.slice().sort(function (a, b) { return a.name.localeCompare(b.name); });
      options($("team-a"), teams, picked.a || teams[0].team);
      options($("team-b"), teams, picked.b || teams[1].team);
      if (picked.venue) $("venue").value = picked.venue;
      $("fresh").textContent = "Season " + data.season + " · Week " + data.week_max + " · generated " + String(data.generated_at || "").slice(0, 10);
      render();
    });
  }
  function init() {
    ["team-a", "team-b", "venue"].forEach(function (id) { $(id).onchange = render; });
    fetch("data/index.json", { cache: "no-cache" }).then(function (r) { return r.json(); }).then(function (idx) {
      var picked = query();
      $("season").innerHTML = idx.seasons.map(function (s) { return '<option value="' + s + '">' + s + "</option>"; }).join("");
      $("season").value = picked.season && idx.seasons.indexOf(Number(picked.season)) >= 0 ? picked.season : idx.default_season;
      $("season").onchange = function () { load($("season").value, { a: $("team-a").value, b: $("team-b").value, venue: $("venue").value }); };
      return load($("season").value, picked);
    }).catch(function (e) {
      $("fresh").textContent = "Could not load matchup data. " + e.message;
    });
  }
  init();
})();
