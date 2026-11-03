(function () {
  "use strict";
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
    var week = Number($("week").value);
    var conf = $("conf").value;
    var played = $("played").value;
    var games = (state.data.games || []).filter(function (g) { return g.week === week; });
    games = games.filter(function (g) {
      if (played === "played" && !g.played) return false;
      if (played === "left" && g.played) return false;
      if (!conf) return true;
      var home = state.conf[g.home] && state.conf[g.home].conference;
      var away = state.conf[g.away] && state.conf[g.away].conference;
      return home === conf || away === conf;
    });
    var sort = $("sort").value;
    games.sort(function (a, b) {
      if (sort === "name") return name(a.away).localeCompare(name(b.away));
      if (sort === "chance") return Math.abs(b.pregame_home_win_chance - 0.5) - Math.abs(a.pregame_home_win_chance - 0.5);
      return Math.abs(b.pregame_spread_home) - Math.abs(a.pregame_spread_home);
    });
    var graded = games.map(grade).filter(function (x) { return x !== null; });
    var hits = graded.filter(Boolean).length;
    $("count").textContent = games.length + " games" + (graded.length ? " · winner hit rate " + hits + "/" + graded.length + " (" + (100 * hits / graded.length).toFixed(0) + "%)" : "");
    var box = $("rows");
    box.className = "game-list";
    box.innerHTML = games.map(function (g) {
      var result = grade(g);
      var pick = result === null ? (g.played ? "Tie" : "Upcoming") : (result ? "Hit" : "Miss");
      var home = state.conf[g.home] || { team: g.home, name: g.home };
      var away = state.conf[g.away] || { team: g.away, name: g.away };
      function mark(team) {
        var src = typeof team.logo === "string" && team.logo.indexOf("https://") === 0 ? '<img alt="" width="28" height="28" src="' + esc(team.logo) + '">' : "";
        return '<span class="logo">' + src + '<span class="logo-fallback">' + esc(team.team || "") + "</span></span>";
      }
      var p = g.pregame_home_win_chance || 0;
      var fav = p >= 0.5 ? name(g.home) : name(g.away);
      var favP = Math.max(p, 1 - p);
      return '<article class="game-card"><header><span>' + (g.neutral ? "Neutral" : "Home / away") + "</span><span class=\"" + (result === true ? "hit" : result === false ? "miss" : "") + "\">" + pick + "</span></header>" +
        '<div class="game-match"><div class="game-side away"><a href="team.html?team=' + esc(g.away) + "&season=" + state.data.season + '">' + mark(away) + esc(name(g.away)) + "</a></div>" +
        '<div class="game-mid"><span>Pregame</span><strong>' + fmt(g.pregame_proj_away, 1) + "–" + fmt(g.pregame_proj_home, 1) + "</strong>" +
        (g.played ? "<span>Final " + g.away_score + "–" + g.home_score + "</span>" : "<span>Not played</span>") + "</div>" +
        '<div class="game-side"><a href="team.html?team=' + esc(g.home) + "&season=" + state.data.season + '">' + mark(home) + esc(name(g.home)) + "</a></div></div>" +
        '<div class="prob"><div class="prob-labels"><span>' + esc(name(g.away)) + " " + ((1 - p) * 100).toFixed(0) + '%</span><span>' + esc(fav) + " " + (favP * 100).toFixed(0) + '%</span><span>' + esc(name(g.home)) + " " + (p * 100).toFixed(0) + "%</span></div>" +
        '<div class="prob-bar" aria-hidden="true"><i style="width:' + ((1 - p) * 100).toFixed(1) + '%;background:' + esc(away.color || "#477c99") + '"></i><i style="width:' + (p * 100).toFixed(1) + '%;background:' + esc(home.color || "#255b7a") + '"></i></div>' +
        '<p class="note">Home spread ' + signed(g.pregame_spread_home, 1) + "</p></div></article>";
    }).join("");
  }

  function load(season) {
    return fetch("data/" + season + ".json", { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).then(function (data) {
      state.data = data;
      state.conf = {};
      data.teams.forEach(function (t) { state.conf[t.team] = t; });
      var weeks = [];
      (data.games || []).forEach(function (g) { if (weeks.indexOf(g.week) < 0) weeks.push(g.week); });
      weeks.sort(function (a, b) { return a - b; });
      $("week").innerHTML = weeks.map(function (w) { return '<option value="' + w + '">Week ' + w + "</option>"; }).join("");
      var playedWeeks = (data.games || []).filter(function (g) { return g.played; }).map(function (g) { return g.week; });
      $("week").value = String(playedWeeks.length ? Math.max.apply(null, playedWeeks) : data.week_max);
      $("fresh").textContent = "Season " + data.season + " · pregame ratings use only earlier weeks · scores from nflverse";
      render();
    });
  }

  function init() {
    ["week", "conf", "played", "sort"].forEach(function (id) { $(id).onchange = render; });
    fetch("data/index.json", { cache: "no-cache" }).then(function (r) { return r.json(); }).then(function (idx) {
      $("season").innerHTML = idx.seasons.map(function (s) { return '<option value="' + s + '">' + s + "</option>"; }).join("");
      $("season").value = idx.default_season;
      $("season").onchange = function () { load($("season").value); };
      return load(idx.default_season);
    }).catch(function (e) { $("fresh").textContent = "Could not load the week. " + e.message; });
  }
  init();
})();
