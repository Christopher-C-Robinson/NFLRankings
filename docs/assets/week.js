(function () {
  "use strict";
  var site = window.NFLSite;
  if (!site) {
    var missing = document.getElementById("fresh");
    if (missing) missing.textContent = "Could not load this page. Hard-refresh and try again.";
    return;
  }
  var $ = function (id) { return document.getElementById(id); };
  var state = { data: null, conf: {}, divisionRank: {}, divisionSize: {} };

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
    var body = $("games-content");
    if (!body) return;
    if (!window.NFLGameCards) {
      body.innerHTML = '<div class="game-day-empty"><h3>Game cards did not load</h3><p>Hard-refresh and try again.</p></div>';
      return;
    }
    body.innerHTML = window.NFLGameCards.renderGameDayRows(games.map(cardRow));
    window.NFLGameCards.bindLogos(body);
  }

  function cardTeam(abbr) {
    var t = state.conf[abbr] || { team: abbr, name: name(abbr) };
    return {
      name: t.name || abbr,
      abbreviation: abbr,
      href: site.page("team.html?team=" + encodeURIComponent(abbr) + "&season=" + state.data.season),
      color: t.color,
      alternateColor: t.color2,
      logo: t.logo,
      conference: t.conference || "",
      division: t.division || "",
      wins: t.wins,
      losses: t.losses,
      ties: t.ties,
      projectedWins: t.projected_wins,
      projectedLosses: t.projected_losses,
      remainingGames: t.remaining_games,
      neutralRank: t.win_chance_rank,
      divisionRank: state.divisionRank[abbr],
      divisionFieldSize: state.divisionSize[t.division],
      passOff: t.off_pass_epa_adj,
      passDef: t.def_pass_epa_adj,
      rushOff: t.off_rush_epa_adj,
      rushDef: t.def_rush_epa_adj
    };
  }

  function cardRow(g) {
    var ranking = state.data.ranking || {};
    var hfa = typeof ranking.home_field_points === "number" ? ranking.home_field_points : null;
    var prediction = null;
    if ([g.pregame_proj_home, g.pregame_proj_away, g.pregame_spread_home, g.pregame_home_win_chance, g.pregame_margin_low, g.pregame_margin_high].every(function (value) {
      return typeof value === "number" && isFinite(value);
    })) {
      prediction = {
        projectedHomeScore: g.pregame_proj_home,
        projectedAwayScore: g.pregame_proj_away,
        predictedMargin: g.pregame_spread_home,
        simulatedHomeWinProbability: g.pregame_home_win_chance,
        marginLow80: g.pregame_margin_low,
        marginHigh80: g.pregame_margin_high,
        predictedTotal: g.pregame_proj_home + g.pregame_proj_away
      };
    }
    var result = grade(g);
    var pick = null;
    if (g.played) {
      if (g.home_score === g.away_score) pick = "Tie";
      else if (result === true) pick = "Hit";
      else if (result === false) pick = "Miss";
      else pick = "No grade";
    }
    return {
      week: g.week,
      status: g.played ? "final" : "upcoming",
      neutral: !!g.neutral,
      venuePoints: g.neutral ? 0 : hfa,
      away: cardTeam(g.away),
      home: cardTeam(g.home),
      prediction: prediction,
      actual: g.played && g.home_score != null && g.away_score != null ? { home: g.home_score, away: g.away_score } : null,
      pick: pick
    };
  }

  function load(season) {
    return site.getJSON(site.data(season + ".json")).then(function (data) {
      state.data = data;
      state.conf = {};
      state.divisionRank = {};
      state.divisionSize = {};
      var groups = {};
      data.teams.forEach(function (t) {
        state.conf[t.team] = t;
        (groups[t.division] = groups[t.division] || []).push(t);
      });
      Object.keys(groups).forEach(function (key) {
        groups[key].sort(function (a, b) { return a.win_chance_rank - b.win_chance_rank; });
        state.divisionSize[key] = groups[key].length;
        groups[key].forEach(function (t, index) { state.divisionRank[t.team] = index + 1; });
      });
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
