(function () {
  "use strict";
  var site = window.NFLSite;
  if (!site) {
    var missing = document.getElementById("fresh");
    if (missing) missing.textContent = "Could not load this page. Hard-refresh and try again.";
    return;
  }
  var $ = function (id) { return document.getElementById(id); };
  var state = { data: null, conf: {} };

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function fmt(x, d) {
    var s = Number(x).toFixed(d);
    return s.indexOf("-") === 0 ? "−" + s.slice(1) : s;
  }
  function signed(x, d) { var n = Number(x); return (n > 0 ? "+" : "") + fmt(n, d); }
  function name(abbr) { return (state.conf[abbr] && state.conf[abbr].name) || abbr; }
  function grade(g) {
    if (!g.played || g.home_score === g.away_score || g.pregame_home_win_chance == null) return null;
    if (g.pregame_home_win_chance === 0.5) return null;
    var pickHome = g.pregame_home_win_chance > 0.5;
    var homeWon = g.home_score > g.away_score;
    return pickHome === homeWon;
  }

  function render() {
    var weekEl = $("week"), confEl = $("conf"), playedEl = $("played"), sortEl = $("sort");
    if (!weekEl || !state.data) return;
    var week = Number(weekEl.value);
    var conf = confEl ? confEl.value : "";
    var played = playedEl ? playedEl.value : "";
    var games = (state.data.games || []).filter(function (g) { return g.week === week; });
    games = games.filter(function (g) {
      if (played === "played" && !g.played) return false;
      if (played === "left" && g.played) return false;
      if (!conf) return true;
      var home = state.conf[g.home] && state.conf[g.home].conference;
      var away = state.conf[g.away] && state.conf[g.away].conference;
      return home === conf || away === conf;
    });
    var sort = sortEl ? sortEl.value : "spread";
    games.sort(function (a, b) {
      if (sort === "name") return name(a.away).localeCompare(name(b.away));
      if (sort === "chance") return Math.abs(b.pregame_home_win_chance - 0.5) - Math.abs(a.pregame_home_win_chance - 0.5);
      return Math.abs(b.pregame_spread_home) - Math.abs(a.pregame_spread_home);
    });
    var graded = games.map(grade).filter(function (x) { return x !== null; });
    var hits = graded.filter(Boolean).length;
    var count = $("count");
    if (count) count.textContent = games.length + " games" + (graded.length ? " · winner hit rate " + hits + "/" + graded.length + " (" + (100 * hits / graded.length).toFixed(0) + "%)" : "");
    var body = $("rows");
    if (!body) return;
    body.innerHTML = games.map(function (g) {
      var result = grade(g);
      var pick = result === null ? (g.played ? "Tie" : "—") : (result ? "Hit" : "Miss");
      var finalScore = g.played ? g.away_score + "–" + g.home_score : "—";
      return "<tr><td><a class=\"teamlink\" href=\"" + site.page("team.html?team=" + encodeURIComponent(g.away) + "&season=" + state.data.season) + "\">" + esc(name(g.away)) + "</a> at <a class=\"teamlink\" href=\"" + site.page("team.html?team=" + encodeURIComponent(g.home) + "&season=" + state.data.season) + "\">" + esc(name(g.home)) + "</a>" + (g.neutral ? " · neutral" : "") + "</td>" +
        "<td class=\"num game-score\">" + fmt(g.pregame_proj_away, 1) + "–" + fmt(g.pregame_proj_home, 1) + "</td>" +
        "<td class=\"num\">" + signed(g.pregame_spread_home, 1) + "</td>" +
        "<td class=\"num\">" + (g.pregame_home_win_chance * 100).toFixed(1) + "%</td>" +
        "<td class=\"num\">" + finalScore + "</td>" +
        "<td class=\"" + (result === true ? "hit" : result === false ? "miss" : "") + "\">" + pick + "</td></tr>";
    }).join("");
  }

  function load(season) {
    return site.getJSON(site.data(season + ".json")).then(function (data) {
      state.data = data;
      state.conf = {};
      data.teams.forEach(function (t) { state.conf[t.team] = t; });
      var week = $("week");
      if (!week) throw new Error("week control is missing");
      var weeks = [];
      (data.games || []).forEach(function (g) { if (weeks.indexOf(g.week) < 0) weeks.push(g.week); });
      weeks.sort(function (a, b) { return a - b; });
      week.innerHTML = weeks.map(function (w) { return '<option value="' + w + '">Week ' + w + "</option>"; }).join("");
      var playedWeeks = (data.games || []).filter(function (g) { return g.played; }).map(function (g) { return g.week; });
      week.value = String(playedWeeks.length ? Math.max.apply(null, playedWeeks) : data.week_max);
      site.setText("fresh", "Season " + data.season + " · Week " + week.value + " · generated " + String(data.generated_at || "").slice(0, 10));
      render();
    });
  }

  function init() {
    ["week", "conf", "played", "sort"].forEach(function (id) {
      var el = $(id);
      if (el) el.onchange = render;
    });
    site.getJSON(site.data("index.json")).then(function (idx) {
      var sel = $("season");
      if (!sel || !idx || !idx.seasons) throw new Error("season list missing");
      sel.innerHTML = idx.seasons.map(function (s) { return '<option value="' + s + '">' + s + "</option>"; }).join("");
      sel.value = idx.default_season;
      sel.onchange = function () { load(sel.value); };
      return load(idx.default_season);
    }).catch(function (e) {
      var msg = e && e.message ? e.message : "request failed";
      site.setText("fresh", "Could not load the week (" + msg + ").");
    });
  }
  init();
})();
