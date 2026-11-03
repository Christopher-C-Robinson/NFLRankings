/* Week-page cards ported from college-football-index:
   js/game-day-view.js, js/game-team-summary.js, js/margin-graphic.js.
   Scores and win chances are the frozen pregame_* fields. There is no live feed. */
(function (root) {
  "use strict";

  function colors() {
    return root.NFLChartColors || {};
  }

  function finite(value) {
    return typeof value === "number" && isFinite(value);
  }

  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function percent(value) {
    return (value * 100).toFixed(1) + "%";
  }

  function signed(value) {
    if (!finite(value)) return "—";
    var text = Math.abs(value).toFixed(1);
    if (value < 0) return "−" + text;
    if (value > 0) return "+" + text;
    return text;
  }

  function recordText(team, projected) {
    if (!team || !finite(team.wins) || !finite(team.losses)) return "—";
    var wins = Math.trunc(team.wins);
    var losses = Math.trunc(team.losses);
    var ties = team.ties ? Math.trunc(team.ties) : 0;
    if (projected) {
      if (!finite(team.projectedWins) || !finite(team.remainingGames)) return "—";
      var remaining = Math.max(0, Math.trunc(team.remainingGames));
      var expected = team.projectedWins - wins;
      var added = Math.max(0, Math.min(remaining, Math.round(expected)));
      wins += added;
      losses += remaining - added;
    }
    return wins + "–" + losses + (ties ? "–" + ties : "");
  }

  function logo(team, size) {
    var pixels = size || 44;
    var href = typeof team.logo === "string" && team.logo.indexOf("https://") === 0 ? team.logo : "";
    return '<span class="team-logo" data-team-logo data-logo-state="' + (href ? "loading" : "fallback") + '" style="--team-logo-size:' + pixels + 'px" aria-hidden="true">' +
      '<span class="team-logo-fallback">' + esc(team.abbreviation || "—") + "</span>" +
      (href ? '<img class="team-logo-image" src="' + esc(href) + '" alt="" width="' + pixels + '" height="' + pixels + '" loading="lazy" decoding="async" referrerpolicy="no-referrer">' : "") +
      "</span>";
  }

  function rankMarkup(team) {
    var overall = finite(team.neutralRank) && team.neutralRank > 0
      ? '<span class="game-team-rank forecast-rank" title="Overall neutral-field rank by average win chance. Filters do not change it.">#' + team.neutralRank + "</span>"
      : '<span class="game-team-rank forecast-rank is-unranked">Unranked</span>';
    var division = "";
    if (team.division && finite(team.divisionRank) && team.divisionRank > 0) {
      var title = "Rank within " + team.division +
        (finite(team.divisionFieldSize) ? " across " + team.divisionFieldSize + " teams" : "") +
        ", ordered by the same full-league neutral comparison.";
      division = '<span class="game-team-rank forecast-rank is-subdivision" title="' + esc(title) + '">' +
        esc(team.division) + " #" + team.divisionRank + "</span>";
    }
    return { overall: overall, division: division };
  }

  function teamLink(team, inner, className) {
    return '<a class="' + className + '" href="' + esc(team.href || "#") + '">' + inner + "</a>";
  }

  function names(away, home) {
    function one(team) {
      return teamLink(team,
        '<span class="game-matchup-name-rank" aria-hidden="true">' + rankMarkup(team).overall + "</span>" +
        '<span class="game-matchup-name-text">' + esc(team.name) + "</span>",
        "game-matchup-name");
    }
    return '<div class="game-matchup-names">' + one(away) + one(home) + "</div>";
  }

  function summary(team, side, neutral) {
    var label = neutral ? "Neutral site" : side === "home" ? "Home" : "Away";
    var conf = [team.conference, team.division].filter(Boolean).join(" · ");
    var projectedTitle = finite(team.projectedWins)
      ? "Played results plus the current season rating on remaining games, rounded to whole wins and losses."
      : "Season projection unavailable.";
    var division = rankMarkup(team).division;
    return '<div class="game-team-summary is-' + side + '" role="group" aria-label="' + esc(label + " team " + team.name) + '">' +
      teamLink(team, logo(team, 44), "game-team-identity") +
      '<dl class="game-team-records" aria-label="' + esc(team.name + " current and projected season records") + '">' +
      '<div><dt>Current</dt><dd title="Record from played games">' + recordText(team, false) + "</dd></div>" +
      '<div><dt>Projected</dt><dd title="' + esc(projectedTitle) + '">' + recordText(team, true) + "</dd></div></dl>" +
      (division ? '<div class="game-team-ranks">' + division + "</div>" : "") +
      (conf ? '<span class="game-team-conference">' + esc(conf) + "</span>" : "") +
      "</div>";
  }

  function scoreLine(label, awayScore, homeScore, awayName, homeName, className) {
    return '<div class="game-day-score-line ' + className + '"><span class="game-day-score-label">' + esc(label) + "</span>" +
      '<strong class="game-day-score" aria-label="' + esc(label + ": " + awayName + " " + Math.round(awayScore) + ", " + homeName + " " + Math.round(homeScore)) + '">' +
      "<span>" + Math.round(awayScore) + '</span><i aria-hidden="true">–</i><span>' + Math.round(homeScore) + "</span></strong></div>";
  }

  function winner(team) {
    return '<div class="game-matchup-winner"><span>Winner</span>' + teamLink(team, logo(team, 32), "game-winner-logo") + "</div>";
  }

  function scoreboard(row) {
    var prediction = row.prediction;
    var actual = row.actual;
    var forecast = prediction
      ? scoreLine("Pregame", prediction.projectedAwayScore, prediction.projectedHomeScore, row.away.name, row.home.name, "is-projected")
      : '<span class="game-day-score-label">Projection unavailable</span>';
    var observed = "";
    var favorite = "";
    if (actual) {
      observed = scoreLine("Final score", actual.away, actual.home, row.away.name, row.home.name, "is-observed is-final");
      favorite = actual.home === actual.away
        ? '<span class="game-day-favorite">Game ended tied</span>'
        : winner(actual.home > actual.away ? row.home : row.away);
    } else if (prediction) {
      favorite = prediction.simulatedHomeWinProbability === 0.5
        ? '<span class="game-day-favorite">Projected toss-up</span>'
        : '<span class="game-day-favorite">Favors ' + esc(prediction.simulatedHomeWinProbability > 0.5 ? row.home.name : row.away.name) + "</span>";
    }
    return '<div class="game-day-scoreboard' + (actual ? " has-observed-score" : "") + '">' + forecast + observed + favorite + "</div>";
  }

  function probabilityBar(row) {
    var prediction = row.prediction;
    if (!prediction || !finite(prediction.simulatedHomeWinProbability)) return "";
    var homeP = prediction.simulatedHomeWinProbability;
    var awayP = 1 - homeP;
    var palette = colors();
    var awayColor = "rgb(150, 167, 183)";
    var homeColor = "rgb(49, 93, 134)";
    var divider = "rgb(255, 255, 255)";
    if (palette.yardageBarColors && palette.barDividerColor) {
      awayColor = palette.yardageBarColors(row.away.color, row.away.alternateColor).passing;
      homeColor = palette.yardageBarColors(row.home.color, row.home.alternateColor).passing;
      divider = palette.barDividerColor(awayColor, homeColor);
    }
    var favorite = homeP >= awayP ? row.home : row.away;
    var favoriteP = Math.max(homeP, awayP);
    var label = row.away.name + " " + percent(awayP) + " pregame win chance; " + row.home.name + " " + percent(homeP) + " pregame win chance.";
    var hasDivider = awayP > 0 && homeP > 0;
    return '<div class="game-day-probability"><span class="game-day-probability-caption">Pregame win chance</span>' +
      '<div class="game-day-probability-headline"><strong>' + percent(favoriteP) + "</strong><span>" + esc(homeP === awayP ? "Toss-up" : favorite.name) + "</span></div>" +
      '<div class="game-day-probability-labels"><span>' + esc(row.away.abbreviation || row.away.name) + " <strong>" + percent(awayP) + "</strong></span>" +
      "<span>" + esc(row.home.abbreviation || row.home.name) + " <strong>" + percent(homeP) + "</strong></span></div>" +
      '<div class="game-day-probability-bar" role="img" aria-label="' + esc(label) + '" style="--game-day-away-color:' + awayColor + ";--game-day-home-color:" + homeColor + ";--game-day-divider-color:" + divider + '">' +
      '<span class="game-day-probability-fill is-away" style="width:' + (awayP * 100).toFixed(3) + '%"></span>' +
      '<span class="game-day-probability-fill is-home" style="width:' + (homeP * 100).toFixed(3) + '%"></span>' +
      (hasDivider ? '<i class="game-day-probability-divider" style="left:' + (awayP * 100).toFixed(3) + '%" aria-hidden="true"></i>' : "") +
      "</div></div>";
  }

  function marginGraphic(prediction, actual, homeName) {
    if (!prediction || !finite(prediction.predictedMargin) || !finite(prediction.marginLow80) || !finite(prediction.marginHigh80) || prediction.marginLow80 > prediction.marginHigh80) return "";
    var margin = prediction.predictedMargin;
    var low = prediction.marginLow80;
    var high = prediction.marginHigh80;
    var actualMargin = actual ? actual.home - actual.away : null;
    var hasActual = finite(actualMargin);
    var domain = Math.ceil(Math.max(Math.abs(low), Math.abs(high), Math.abs(margin), hasActual ? Math.abs(actualMargin) : 0, 1) * 1.12);
    function x(value) { return (150 + value / domain * 134).toFixed(2); }
    function s(value) { return (value > 0 ? "+" : "") + value.toFixed(1); }
    var label = homeName + " scoring margin; positive favors " + homeName + ". Middle 80% of the residual range: " + s(low) + " to " + s(high) + ". Pregame projection " + s(margin) + (hasActual ? ". Actual margin " + s(actualMargin) : "") + ".";
    return '<div class="forecast-margin-range"><div class="forecast-range-heading"><span>Middle 80% range</span><strong>' + esc(s(low) + " to " + s(high)) + "</strong></div>" +
      '<svg class="forecast-range-chart" viewBox="0 0 300 52" role="img" aria-label="' + esc(label) + '">' +
      '<line class="forecast-range-axis" x1="16" x2="284" y1="20" y2="20"/><line class="forecast-range-zero" x1="150" x2="150" y1="7" y2="30"/>' +
      '<line class="forecast-range-band" x1="' + x(low) + '" x2="' + x(high) + '" y1="20" y2="20"/>' +
      '<circle class="forecast-range-model" cx="' + x(margin) + '" cy="20" r="5"/>' +
      (hasActual ? '<path class="forecast-range-actual" d="M ' + x(actualMargin) + ' 12 l 6 8 l -6 8 l -6 -8 Z"/>' : "") +
      '<text class="forecast-range-label" x="16" y="47" text-anchor="start">−' + domain + '</text><text class="forecast-range-label" x="150" y="47" text-anchor="middle">0</text><text class="forecast-range-label" x="284" y="47" text-anchor="end">+' + domain + "</text></svg>" +
      '<div class="forecast-range-legend"><span><i class="is-model" aria-hidden="true"></i>Pregame ' + esc(s(margin)) + "</span>" +
      (hasActual ? '<span><i class="is-actual" aria-hidden="true"></i>Actual ' + esc(s(actualMargin)) + "</span>" : "") + "</div></div>";
  }

  function marginSection(row) {
    var graphic = marginGraphic(row.prediction, row.actual, row.home.name);
    if (!graphic) return "";
    return '<section class="game-day-range game-day-margin-comparison" aria-label="Pregame margin range and final score"><h4 class="game-day-margin-heading">' + esc(row.home.name) + " margin</h4>" +
      '<div class="game-day-margin-headline"><strong>' + signed(row.prediction.predictedMargin) + "<small> pts</small></strong><span>Positive favors " + esc(row.home.name) + "</span></div>" +
      graphic + '<p class="game-day-range-note">80% range from the fitted point residual. The pregame pick is frozen before the week.</p></section>';
  }

  function epa(value) {
    if (!finite(value)) return "—";
    var text = Math.abs(value).toFixed(3);
    return (value < 0 ? "−" : value > 0 ? "+" : "") + text;
  }

  function cell(label, value) {
    return "<div><dt>" + esc(label) + "</dt><dd>" + value + "</dd></div>";
  }

  function details(row) {
    var prediction = row.prediction;
    if (!prediction) {
      return '<details class="game-day-details"><summary>Forecast unavailable</summary><div class="game-day-details-content"><p class="game-day-unavailable">This game has no frozen pregame pick in the file.</p></div></details>';
    }
    var favored = prediction.predictedMargin >= 0 ? row.home : row.away;
    var marginLabel = prediction.predictedMargin === 0
      ? "Even matchup"
      : (favored.abbreviation || favored.name) + " by " + Math.abs(prediction.predictedMargin).toFixed(1);
    var total = finite(prediction.predictedTotal) ? Math.round(prediction.predictedTotal) : "—";
    var venue = finite(row.venuePoints) ? row.venuePoints : null;
    var strength = finite(prediction.predictedMargin) && finite(venue) ? prediction.predictedMargin - venue : null;
    var unit = '<section><h4>Current-season pass and rush EPA</h4><p class="game-day-detail-note">Schedule-adjusted EPA per play on the published season rating. These splits are not added into the pregame spread.</p><dl class="game-day-margin-breakdown">' +
      cell(row.away.abbreviation + " pass off / def", epa(row.away.passOff) + " / " + epa(row.away.passDef)) +
      cell(row.home.abbreviation + " pass off / def", epa(row.home.passOff) + " / " + epa(row.home.passDef)) +
      cell(row.away.abbreviation + " rush off / def", epa(row.away.rushOff) + " / " + epa(row.away.rushDef)) +
      cell(row.home.abbreviation + " rush off / def", epa(row.home.rushOff) + " / " + epa(row.home.rushDef)) +
      "</dl></section>";
    var pick = row.pick ? '<p class="game-day-detail-note">Pregame winner pick: ' + esc(row.pick) + ".</p>" : "";
    return '<details class="game-day-details"><summary>Forecast details <span>' + esc(marginLabel) + " · " + total + ' total</span></summary>' +
      '<div class="game-day-details-content"><section class="game-day-margin-breakdown"><h4>How the pregame margin adds up</h4><dl>' +
      cell("Team strength", signed(strength)) +
      cell("Home / away effect", signed(venue)) +
      cell("Pass + rush matchup", "Not in spread") +
      cell("Pregame spread", signed(prediction.predictedMargin)) +
      "</dl></section>" + unit +
      '<p class="game-day-detail-note game-day-projection-note">Team strength is the frozen pregame spread minus the league home-field number' +
      (row.neutral ? " (zero at a neutral site)" : "") +
      ". Kickoff time, stadium, live scores, and a pass/rush point adjustment are not in this file. " +
      (row.actual ? "The final score is shown separately and does not change the frozen pick." : "The pick stays frozen after the game is played.") +
      "</p>" + pick + "</div></details>";
  }

  function renderRow(row) {
    var status = row.status === "final" ? "Final" : "Not played";
    if (row.pick) status += " · " + row.pick;
    var statusClass = row.pick === "Hit" ? " is-hit" : row.pick === "Miss" ? " is-miss" : "";
    var description = row.away.name + " versus " + row.home.name + ". " + status + ". Week " + row.week + ".";
    var venue = row.neutral ? '<p class="game-day-venue">Neutral site</p>' : "";
    return '<article class="game-day-card is-' + (row.status === "final" ? "final" : "upcoming") + '" role="listitem" aria-label="' + esc(description) + '">' +
      '<header class="game-day-card-heading"><div class="game-day-kickoff"><span>Week ' + esc(row.week) + "</span></div>" +
      '<span class="game-day-status' + statusClass + '">' + esc(status) + "</span></header>" +
      '<div class="game-day-matchup">' + names(row.away, row.home) + summary(row.away, "away", row.neutral) + scoreboard(row) + summary(row.home, "home", row.neutral) + "</div>" +
      '<div class="game-day-card-footer">' + probabilityBar(row) + marginSection(row) + venue + "</div>" +
      details(row) + "</article>";
  }

  function renderGameDayRows(rows) {
    if (!rows || !rows.length) {
      return '<div class="game-day-empty"><h3>No matching games</h3><p>Try another week or broaden the conference and result filters.</p></div>';
    }
    return '<div class="game-day-list" role="list" aria-label="NFL games and frozen pregame picks">' + rows.map(renderRow).join("") + "</div>";
  }

  function bindLogos(container) {
    if (!container || !container.querySelectorAll) return;
    var images = container.querySelectorAll("img.team-logo-image");
    for (var i = 0; i < images.length; i++) {
      (function (img) {
        function mark(state) {
          var wrap = img.closest("[data-team-logo]");
          if (wrap) wrap.setAttribute("data-logo-state", state);
        }
        img.addEventListener("load", function () { mark(img.naturalWidth > 0 ? "loaded" : "fallback"); });
        img.addEventListener("error", function () { mark("fallback"); });
        if (img.complete) mark(img.naturalWidth > 0 ? "loaded" : "fallback");
      })(images[i]);
    }
  }

  root.NFLGameCards = {
    renderGameDayRows: renderGameDayRows,
    bindLogos: bindLogos,
    recordText: recordText
  };
})(typeof window !== "undefined" ? window : globalThis);
