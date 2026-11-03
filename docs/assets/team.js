(function () {
  "use strict";
  var site = window.NFLSite;
  if (!site) {
    var missing = document.getElementById("fresh");
    if (missing) missing.textContent = "Could not load this page. Hard-refresh and try again.";
    return;
  }
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
  function dashRecord(wins, losses, ties) {
    return wins + "–" + losses + (ties ? "–" + ties : "");
  }
  function team(abbr) { return state.data.teams.filter(function (t) { return t.team === abbr; })[0]; }
  function teamOr(abbr) {
    return team(abbr) || {
      team: abbr, name: state.names[abbr] || abbr, wins: 0, losses: 0, ties: 0,
      projected_wins: NaN, projected_losses: NaN, color: "", conference: "", division: "", logo: ""
    };
  }
  function whole(x) {
    if (x === null || x === undefined || isNaN(x)) return "–";
    return String(Math.round(Number(x)));
  }
  function pct(p) { return (Number(p) * 100).toFixed(1) + "%"; }
  function hexOk(value) { return /^#[0-9A-Fa-f]{6}$/.test(value || ""); }
  function rgbList(hex, fallback) {
    var color = hexOk(hex) ? hex : fallback;
    var n = parseInt(color.slice(1), 16);
    return ((n >> 16) & 255) + ", " + ((n >> 8) & 255) + ", " + (n & 255);
  }
  function channelLum(c) {
    c /= 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  }
  function relLum(hex) {
    var n = parseInt(hex.slice(1), 16);
    return 0.2126 * channelLum((n >> 16) & 255) + 0.7152 * channelLum((n >> 8) & 255) + 0.0722 * channelLum(n & 255);
  }
  function contrast(a, b) {
    var hi = Math.max(relLum(a), relLum(b));
    var lo = Math.min(relLum(a), relLum(b));
    return (hi + 0.05) / (lo + 0.05);
  }
  function dividerColor(left, right) {
    var a = hexOk(left) ? left : "#477c99";
    var b = hexOk(right) ? right : "#7e8c9b";
    var options = ["#ffffff", "#172333", "#f4f7fb", "#0f1822"];
    var best = options[0];
    var bestScore = -1;
    options.forEach(function (color) {
      var score = Math.min(contrast(color, a), contrast(color, b));
      if (score > bestScore) { bestScore = score; best = color; }
    });
    return best;
  }
  function teamHref(abbr) {
    return site.page("team.html?team=" + encodeURIComponent(abbr) + "&season=" + state.data.season);
  }
  function logoMark(entry) {
    var fallback = '<span class="team-logo-fallback">' + esc(entry.team) + "</span>";
    if (!entry.logo) return '<span class="team-logo" data-logo-state="failed">' + fallback + "</span>";
    return '<span class="team-logo" data-logo-state="loaded"><img alt="" src="' + esc(entry.logo) + '" width="44" height="44">' + fallback + "</span>";
  }
  function bindLogos(root) {
    root.querySelectorAll(".team-logo img").forEach(function (img) {
      img.addEventListener("error", function () {
        var logo = img.closest(".team-logo");
        if (logo) logo.setAttribute("data-logo-state", "failed");
      });
    });
  }

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

  function nameLink(entry) {
    var rank = entry.win_chance_rank ? '<span class="game-matchup-name-rank"><span class="game-team-rank forecast-rank">#' + entry.win_chance_rank + "</span></span>" : "";
    return '<a class="game-matchup-name" href="' + teamHref(entry.team) + '">' + rank +
      '<span class="game-matchup-name-text">' + esc(entry.name) + "</span></a>";
  }

  function teamSummary(entry, side) {
    var label = side === "home" ? "Home" : "Away";
    var division = entry.division || entry.conference || "";
    return '<div class="game-team-summary is-' + side + '" role="group" aria-label="' + esc(label + " team " + entry.name) + '">' +
      '<a class="game-team-identity" href="' + teamHref(entry.team) + '" aria-label="Open ' + esc(entry.name) + '">' + logoMark(entry) + "</a>" +
      '<dl class="game-team-records"><div><dt>Current</dt><dd>' + dashRecord(entry.wins, entry.losses, entry.ties) + "</dd></div>" +
      "<div><dt>Projected</dt><dd>" + fmt(entry.projected_wins, 1) + "–" + fmt(entry.projected_losses, 1) + "</dd></div></dl>" +
      (division ? '<span class="game-team-conference">' + esc(division) + "</span>" : "") + "</div>";
  }

  function scoreLine(label, left, right, className, href, title) {
    var score = '<strong class="forecast-matchup-score"' + (title ? ' title="' + esc(title) + '"' : "") +
      '><span>' + left + '</span><i aria-hidden="true">–</i><span>' + right + "</span></strong>";
    if (href) score = '<a class="forecast-score-link" href="' + href + '">' + score + "</a>";
    return '<div class="forecast-matchup-score-line ' + className + '"><span class="forecast-matchup-status">' + esc(label) + "</span>" + score + "</div>";
  }

  function sideChance(entry, game, homeP) {
    if (homeP === null) return null;
    return entry.team === game.home ? homeP : 1 - homeP;
  }
  function sidePoints(entry, game, homeKey, awayKey) {
    return entry.team === game.home ? game[homeKey] : game[awayKey];
  }

  function probabilityBar(left, right, leftP, rightP, selected, played) {
    if (leftP === null || rightP === null) {
      return '<section class="forecast-analytics-panel forecast-matchup-outlook"><h5 class="forecast-section-title">Model win chance</h5><p class="forecast-unavailable">Win chance unavailable.</p></section>';
    }
    var selectedP = selected.team === right.team ? rightP : leftP;
    var leftRgb = rgbList(left.color, "#7e8c9b");
    var rightRgb = rgbList(right.color, "#477c99");
    var divider = dividerColor(left.color, right.color);
    var leftClass = selected.team === left.team ? "is-selected" : "is-opponent";
    var rightClass = selected.team === right.team ? "is-selected" : "is-opponent";
    var hasDivider = leftP > 0 && rightP > 0;
    var label = left.name + " " + pct(leftP) + " win chance; " + right.name + " " + pct(rightP) + " win chance.";
    var note = played ? "Reprojected with the current rating, including this result." : "From the current season rating.";
    return '<section class="forecast-analytics-panel forecast-matchup-outlook"><h5 class="forecast-section-title">Model win chance</h5>' +
      '<div class="forecast-probability-headline"><strong>' + pct(selectedP) + "</strong><span>" + esc(selected.name) + "</span></div>" +
      '<div class="forecast-probability-bar' + (hasDivider ? " has-divider" : "") + '" style="--bar-divider-color:' + divider + '" role="img" aria-label="' + esc(label) + '">' +
      '<span class="' + leftClass + '" style="width:' + (leftP * 100).toFixed(3) + "%;--probability-team-rgb:" + leftRgb + '"></span>' +
      '<span class="' + rightClass + '" style="width:' + (rightP * 100).toFixed(3) + "%;--probability-team-rgb:" + rightRgb + '"></span></div>' +
      '<div class="forecast-probability-labels"><span>' + esc(left.team) + "<strong>" + pct(leftP) + "</strong></span>" +
      "<span>" + esc(right.team) + "<strong>" + pct(rightP) + "</strong></span></div>" +
      '<p class="forecast-analytics-note">' + note + "</p></section>";
  }

  function matchupCard(g, selected, index) {
    var away = teamOr(g.away);
    var home = teamOr(g.home);
    var homeChance = Number(g.home_win_chance);
    var homeP = isFinite(homeChance) ? homeChance : null;
    var selectedHome = g.home === selected.team;
    var left = g.neutral ? selected : away;
    var right = left.team === away.team ? home : away;
    var leftP = sideChance(left, g, homeP);
    var rightP = sideChance(right, g, homeP);
    var spread = selectedHome ? g.spread_home : -g.spread_home;
    var siteLabel = g.neutral ? "Neutral" : selectedHome ? "Home" : "Away";
    var venue = g.neutral ? "neutral" : selectedHome ? "a_home" : "b_home";
    var opponent = selectedHome ? g.away : g.home;
    var matchHref = site.page("matchup.html?season=" + state.data.season + "&a=" + encodeURIComponent(selected.team) + "&b=" + encodeURIComponent(opponent) + "&venue=" + venue);
    var projLeft = sidePoints(left, g, "proj_home", "proj_away");
    var projRight = sidePoints(right, g, "proj_home", "proj_away");
    var projTitle = "Unrounded projection: " + fmt(projLeft, 1) + "–" + fmt(projRight, 1);
    var center = scoreLine("Projected", whole(projLeft), whole(projRight), "is-projected", matchHref, projTitle);
    var winnerClass = "";
    var winnerRgb = "";
    var played = g.played && g.home_score !== null && g.away_score !== null;
    if (played) {
      center += scoreLine("Final", String(sidePoints(left, g, "home_score", "away_score")), String(sidePoints(right, g, "home_score", "away_score")), "is-observed");
      if (g.home_score !== g.away_score) {
        var winner = g.home_score > g.away_score ? home : away;
        winnerClass = " is-winner-actual";
        winnerRgb = rgbList(winner.color, "#477c99");
        center += '<div class="game-matchup-winner"><span>Winner</span><a class="game-winner-logo" href="' + teamHref(winner.team) + '" aria-label="Winner: ' + esc(winner.name) + '">' + logoMark(winner) + "</a></div>";
      } else {
        center += '<span class="forecast-matchup-favorite">Final tied</span>';
      }
    } else if (homeP !== null) {
      if (leftP === rightP) center += '<span class="forecast-matchup-favorite">Projected toss-up</span>';
      else {
        var favorite = rightP > leftP ? right : left;
        winnerClass = " is-winner-predicted";
        winnerRgb = rgbList(favorite.color, "#477c99");
        center += '<span class="forecast-matchup-favorite">Projected favorite: ' + esc(favorite.name) + "</span>" +
          '<span class="forecast-matchup-probability">' + pct(Math.max(leftP, rightP)) + " win chance</span>";
      }
    }
    if (g.neutral) center += '<span class="forecast-neutral-label">Neutral site</span>';
    if (isFinite(Number(spread))) {
      center += '<span class="forecast-matchup-probability" title="Positive favors ' + esc(selected.name) + '">Spread ' + signed(spread, 1) + "</span>";
    }
    var label = left.name + " versus " + right.name + ", week " + g.week + ", " + siteLabel + ".";
    return '<article id="season-game-' + index + '" class="forecast-game is-compact-game' + winnerClass + '"' +
      (winnerRgb ? ' style="--game-winner-rgb:' + winnerRgb + '"' : "") +
      ' role="listitem" aria-label="' + esc(label) + '">' +
      '<div class="forecast-game-heading"><div class="forecast-date">WK ' + esc(g.week) + "<span>" + esc(siteLabel) + "</span></div>" +
      '<span class="forecast-status-meta">' + (played ? "Final" : "Upcoming") + "</span>" +
      '<span class="forecast-venue-meta">' + (g.neutral ? "Neutral site" : "") + "</span></div>" +
      '<div class="forecast-matchup-header">' +
      '<div class="game-matchup-names">' + nameLink(left) + nameLink(right) + "</div>" +
      teamSummary(left, "away") +
      '<div class="forecast-matchup-center">' + center + "</div>" +
      teamSummary(right, "home") +
      "</div>" +
      '<div class="forecast-game-body forecast-analytics-grid">' + probabilityBar(left, right, leftP, rightP, selected, played) + "</div></article>";
  }

  function powerSection(t) {
    if (t.division_power == null && t.conference_power == null) return "";
    return "<h2>Division and conference</h2>" +
      '<dl class="stat-grid">' +
      "<div><dt>" + esc(t.division || "Division") + " power</dt><dd>" + signed(t.division_power, 1) + "</dd></div>" +
      "<div><dt>" + esc(t.conference || "Conference") + " power</dt><dd>" + signed(t.conference_power, 1) + "</dd></div>" +
      "<div><dt>Team rating in the fit</dt><dd>" + signed(t.hierarchy_power, 1) + "</dd></div>" +
      "</dl>" +
      '<p class="fresh">Points from the joint score-margin fit. Positive is stronger than the league prior. This does not change the neutral win-chance rank.</p>';
  }

  function render() {
    var sel = $("team");
    if (!sel || !state.data) return;
    var t = team(sel.value);
    if (!t) return;
    document.title = t.name + " — NFL Rankings";
    var title = $("title");
    if (title) title.textContent = t.name;
    var dek = $("dek");
    if (dek) dek.textContent = "Rank " + t.win_chance_rank + " · " + (t.win_chance * 100).toFixed(1) + "% average neutral win chance · " + (t.division || t.conference || "");
    var games = (state.data.games || []).filter(function (g) { return g.home === t.team || g.away === t.team; });
    games.sort(function (a, b) {
      return a.week - b.week || String(a.home).localeCompare(String(b.home)) || String(a.away).localeCompare(String(b.away));
    });
    var outlook = window.NFLSeasonOutlook ? window.NFLSeasonOutlook.build(t, state.data.games || [], state.data.teams, {
      season: state.data.season,
      generatedAt: state.data.generated_at
    }) : null;
    var cards = games.map(function (g, index) { return matchupCard(g, t, index); }).join("");
    var color = hexOk(t.color) ? t.color : "#0e3b2e";
    var resultBox = $("result");
    if (!resultBox) return;
    resultBox.innerHTML =
      '<section class="teamhead" style="--accent:' + color + '">' +
      (t.logo ? '<img class="teamlogo" alt="" src="' + esc(t.logo) + '" width="56" height="56">' : "") +
      "<div><p class=\"record\">" + record(t) + "</p><p>Projected record <strong>" + fmt(t.projected_wins, 1) + "–" + fmt(t.projected_losses, 1) + "</strong> · schedule expected wins " + fmt(t.schedule_expected_wins, 1) + " · opponent EPA " + fmt(t.sos, 3) + "</p></div></section>" +
      (outlook ? window.NFLSeasonOutlook.render(outlook) : "") +
      "<h2>Season rating</h2><p class=\"chart-caption\">Schedule-adjusted EPA after each played week. This line is weeks[].v2. The bars above are win chance by game.</p>" + chart(t.weeks) +
      powerSection(t) +
      "<h2>Schedule</h2>" +
      '<p class="schedule-note">Away on the left, home on the right. The bar is each side’s win chance from the current rating.</p>' +
      (cards ? '<div class="forecast-ledger" role="list">' + cards + "</div>" : "<p>No games listed.</p>");
    bindLogos(resultBox);
    var q = new URLSearchParams();
    q.set("team", t.team);
    q.set("season", state.data.season);
    var hash = /^#season-game-\d+$/.test(location.hash) ? location.hash : "";
    history.replaceState(null, "", site.page("team.html?" + q.toString()) + hash);
  }

  function load(season, abbr) {
    return site.getJSON(site.data(season + ".json")).then(function (data) {
      state.data = data;
      state.names = {};
      data.teams.forEach(function (t) { state.names[t.team] = t.name; });
      var sel = $("team");
      if (!sel) throw new Error("team control is missing");
      var teams = data.teams.slice().sort(function (a, b) { return a.name.localeCompare(b.name); });
      sel.innerHTML = teams.map(function (t) { return '<option value="' + esc(t.team) + '">' + esc(t.name) + "</option>"; }).join("");
      if (abbr && state.names[abbr]) sel.value = abbr;
      site.setText("fresh", "Season " + data.season + " · Week " + data.week_max + " · generated " + String(data.generated_at || "").slice(0, 10));
      render();
    });
  }

  function init() {
    var q = new URLSearchParams(location.search);
    var team = $("team");
    if (team) team.onchange = render;
    site.getJSON(site.data("index.json")).then(function (idx) {
      var sel = $("season");
      if (!sel || !idx || !idx.seasons) throw new Error("season list missing");
      sel.innerHTML = idx.seasons.map(function (s) { return '<option value="' + s + '">' + s + "</option>"; }).join("");
      var season = q.get("season") && idx.seasons.indexOf(Number(q.get("season"))) >= 0 ? q.get("season") : idx.default_season;
      sel.value = season;
      sel.onchange = function () {
        var current = $("team");
        load(sel.value, current ? current.value : "");
      };
      return load(season, q.get("team"));
    }).catch(function (e) {
      var msg = e && e.message ? e.message : "request failed";
      site.setText("fresh", "Could not load this team (" + msg + ").");
    });
  }
  init();
})();
