(function () {
  "use strict";
  var site = window.NFLSite;
  if (!site) {
    var missing = document.getElementById("fresh");
    if (missing) missing.textContent = "Could not load this page. Hard-refresh and try again.";
    return;
  }
  var $ = function (id) { return document.getElementById(id); };

  function decisive(g) {
    return g.played && g.home_score !== g.away_score && g.pregame_home_win_chance != null && g.pregame_home_win_chance !== 0.5;
  }
  function hit(g) {
    var pickHome = g.pregame_home_win_chance > 0.5;
    return pickHome === (g.home_score > g.away_score);
  }
  function brier(games) {
    if (!games.length) return null;
    var sum = 0;
    games.forEach(function (g) {
      var y = g.home_score > g.away_score ? 1 : 0;
      var p = g.pregame_home_win_chance;
      sum += (p - y) * (p - y);
    });
    return sum / games.length;
  }
  function row(label, games) {
    var decided = games.filter(decisive);
    var hits = decided.filter(hit).length;
    var score = brier(decided);
    return "<tr><th scope=\"row\">" + label + "</th><td class=\"num\">" + decided.length + "</td><td class=\"num\">" +
      (decided.length ? hits + " (" + (100 * hits / decided.length).toFixed(1) + "%)" : "—") + "</td><td class=\"num\">" +
      (score == null ? "—" : score.toFixed(3)) + "</td></tr>";
  }
  function render(data) {
    var games = data.games || [];
    var weeks = [];
    games.forEach(function (g) { if (weeks.indexOf(g.week) < 0) weeks.push(g.week); });
    weeks.sort(function (a, b) { return a - b; });
    site.setText("fresh", "Season " + data.season + " · Week " + data.week_max + " · generated " + String(data.generated_at || "").slice(0, 10));
    var result = $("result");
    if (!result) return;
    result.innerHTML = '<div class="tablewrap"><table class="schedule"><thead><tr><th>Slice</th><th class="num">Picks</th><th class="num">Winners</th><th class="num">Brier</th></tr></thead><tbody>' +
      row("Season", games) +
      weeks.map(function (w) { return row("Week " + w, games.filter(function (g) { return g.week === w; })); }).join("") +
      "</tbody></table></div>";
  }
  function fail(e) {
    var msg = e && e.message ? e.message : "request failed";
    site.setText("fresh", "Could not load accuracy (" + msg + ").");
  }
  var CURRENT_SEASON = 2026;
  function load(season) {
    return site.getJSON(site.data(season + ".json")).then(render).catch(fail);
  }
  site.getJSON(site.data("index.json")).then(function (idx) {
    if (!idx || !idx.seasons || idx.seasons.map(Number).indexOf(CURRENT_SEASON) < 0) {
      throw new Error("2026 is not in the published season list");
    }
    return load(CURRENT_SEASON);
  }).catch(fail);
})();
