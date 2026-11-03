(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var state = { data: null, names: {} };

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
  function signed(x, d) { var n = Number(x); return (n > 0 ? "+" : "") + fmt(n, d); }
  function record(t) { return t.wins + "-" + t.losses + (t.ties ? "-" + t.ties : ""); }
  function team(abbr) { return state.data.teams.filter(function (t) { return t.team === abbr; })[0]; }

  function chart(weeks) {
    if (!weeks || !weeks.length) return "<p>No weekly rating yet.</p>";
    var w = 640, h = 220, pad = 28;
    var xs = weeks.map(function (p) { return p.week; });
    var ys = weeks.map(function (p) { return p.v2; });
    var minX = Math.min.apply(null, xs), maxX = Math.max.apply(null, xs);
    var minY = Math.min(0, Math.min.apply(null, ys)), maxY = Math.max(0, Math.max.apply(null, ys));
    if (minY === maxY) { minY -= 0.05; maxY += 0.05; }
    if (minX === maxX) maxX = minX + 1;
    function px(x) { return pad + (x - minX) / (maxX - minX) * (w - pad * 2); }
    function py(y) { return h - pad - (y - minY) / (maxY - minY) * (h - pad * 2); }
    var line = weeks.map(function (p, i) { return (i ? "L" : "M") + px(p.week).toFixed(1) + " " + py(p.v2).toFixed(1); }).join(" ");
    var dots = weeks.map(function (p) {
      return '<circle cx="' + px(p.week).toFixed(1) + '" cy="' + py(p.v2).toFixed(1) + '" r="3.5"><title>Week ' + p.week + ": " + p.v2.toFixed(3) + "</title></circle>";
    }).join("");
    var labels = weeks.map(function (p) {
      return '<text x="' + px(p.week).toFixed(1) + '" y="' + (h - 8) + '" text-anchor="middle">' + p.week + "</text>";
    }).join("");
    return '<svg class="chart" viewBox="0 0 ' + w + " " + h + '" role="img" aria-label="Schedule-adjusted EPA by week">' +
      '<line class="axis" x1="' + pad + '" y1="' + py(0).toFixed(1) + '" x2="' + (w - pad) + '" y2="' + py(0).toFixed(1) + '"/>' +
      '<path d="' + line + '"/>' + dots + labels + "</svg>";
  }

  function render() {
    var t = team($("team").value);
    if (!t) return;
    document.title = t.name + " — NFL Rankings";
    $("title").textContent = t.name;
    $("dek").textContent = "Rank " + t.win_chance_rank + " · " + (t.win_chance * 100).toFixed(1) + "% average neutral win chance · " + (t.division || t.conference || "");
    var games = (state.data.games || []).filter(function (g) { return g.home === t.team || g.away === t.team; });
    var rows = games.map(function (g) {
      var home = g.home === t.team;
      var opp = home ? g.away : g.home;
      var where = g.neutral ? "N" : home ? "H" : "A";
      var spread = home ? g.spread_home : -g.spread_home;
      var chance = home ? g.home_win_chance : 1 - g.home_win_chance;
      var projFor = home ? g.proj_home : g.proj_away;
      var projAgainst = home ? g.proj_away : g.proj_home;
      var result = g.played ? (home ? g.home_score + "–" + g.away_score : g.away_score + "–" + g.home_score) : "—";
      var href = "matchup.html?season=" + state.data.season + "&a=" + encodeURIComponent(t.team) + "&b=" + encodeURIComponent(opp) + "&venue=" + (g.neutral ? "neutral" : home ? "a_home" : "b_home");
      return "<tr><td>" + g.week + "</td><td>" + where + "</td><td><a class=\"teamlink\" href=\"team.html?team=" + esc(opp) + "&season=" + state.data.season + "\">" + esc(state.names[opp] || opp) + "</a></td><td class=\"num\">" + result + "</td><td class=\"num\">" + signed(spread, 1) + "</td><td class=\"num\">" + (chance * 100).toFixed(1) + "%</td><td class=\"num\"><a class=\"teamlink\" href=\"" + href + "\">" + fmt(projFor, 1) + "–" + fmt(projAgainst, 1) + "</a></td></tr>";
    }).join("");
    var color = /^#[0-9A-Fa-f]{6}$/.test(t.color || "") ? t.color : "#0e3b2e";
    $("result").innerHTML =
      '<section class="teamhead" style="--accent:' + color + '">' +
      (t.logo ? '<img class="teamlogo" alt="" src="' + esc(t.logo) + '" width="56" height="56">' : "") +
      "<div><p class=\"record\">" + record(t) + "</p><p>Projected record <strong>" + fmt(t.projected_wins, 1) + "–" + fmt(t.projected_losses, 1) + "</strong> · schedule expected wins " + fmt(t.schedule_expected_wins, 1) + " · opponent EPA " + fmt(t.sos, 3) + "</p></div></section>" +
      "<h2>Season rating</h2>" + chart(t.weeks) +
      "<h2>Schedule</h2>" +
      '<div class="tablewrap"><table class="schedule"><thead><tr><th>Week</th><th></th><th>Opponent</th><th class="num">Result</th><th class="num">Spread</th><th class="num">Win chance</th><th class="num">Projected</th></tr></thead><tbody>' +
      rows + "</tbody></table></div>";
    var q = new URLSearchParams();
    q.set("team", t.team);
    q.set("season", state.data.season);
    history.replaceState(null, "", "team.html?" + q.toString());
  }

  function load(season, abbr) {
    return fetch("data/" + season + ".json", { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).then(function (data) {
      state.data = data;
      state.names = {};
      data.teams.forEach(function (t) { state.names[t.team] = t.name; });
      var teams = data.teams.slice().sort(function (a, b) { return a.name.localeCompare(b.name); });
      $("team").innerHTML = teams.map(function (t) { return '<option value="' + esc(t.team) + '">' + esc(t.name) + "</option>"; }).join("");
      if (abbr && state.names[abbr]) $("team").value = abbr;
      $("fresh").textContent = "Season " + data.season + " · Week " + data.week_max + " · generated " + String(data.generated_at || "").slice(0, 10);
      render();
    });
  }

  function init() {
    var q = new URLSearchParams(location.search);
    $("team").onchange = render;
    fetch("data/index.json", { cache: "no-cache" }).then(function (r) { return r.json(); }).then(function (idx) {
      $("season").innerHTML = idx.seasons.map(function (s) { return '<option value="' + s + '">' + s + "</option>"; }).join("");
      var season = q.get("season") && idx.seasons.indexOf(Number(q.get("season"))) >= 0 ? q.get("season") : idx.default_season;
      $("season").value = season;
      $("season").onchange = function () { load($("season").value, $("team").value); };
      return load(season, q.get("team"));
    }).catch(function (e) {
      $("fresh").textContent = "Could not load this team. " + e.message;
    });
  }
  init();
})();
