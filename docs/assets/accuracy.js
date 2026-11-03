(function () {
  "use strict";
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
    $("fresh").textContent = "Season " + data.season + " · Week " + data.week_max + " · generated " + String(data.generated_at || "").slice(0, 10);
    $("result").innerHTML = '<div class="tablewrap"><table class="schedule"><thead><tr><th>Slice</th><th class="num">Picks</th><th class="num">Winners</th><th class="num">Brier</th></tr></thead><tbody>' +
      row("Season", games) +
      weeks.map(function (w) { return row("Week " + w, games.filter(function (g) { return g.week === w; })); }).join("") +
      "</tbody></table></div>";
  }
  function load(season) {
    fetch("data/" + season + ".json", { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).then(render).catch(function (e) { $("fresh").textContent = "Could not load accuracy. " + e.message; });
  }
  fetch("data/index.json", { cache: "no-cache" }).then(function (r) { return r.json(); }).then(function (idx) {
    $("season").innerHTML = idx.seasons.map(function (s) { return '<option value="' + s + '">' + s + "</option>"; }).join("");
    $("season").value = idx.default_season;
    $("season").onchange = function () { load($("season").value); };
    load(idx.default_season);
  });
})();
