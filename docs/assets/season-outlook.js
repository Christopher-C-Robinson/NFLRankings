/* Season outlook ported from college-football-index:
   js/season-chart.js and renderProjectionSummary in js/season-projections-view.js.
   Bar height is each game's win chance on the published season rating.
   weeks[].v2 is a different series and is not drawn here. */
(function (root) {
  "use strict";

  function finite(value) {
    return typeof value === "number" && isFinite(value);
  }

  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function number(value, digits) {
    if (!finite(value)) return "—";
    var text = Math.abs(value).toFixed(digits == null ? 1 : digits);
    return value < 0 ? "−" + text : text;
  }

  function plural(count, singular) {
    return count + " " + singular + (count === 1 ? "" : "s");
  }

  function recordText(team, projected) {
    if (root.NFLGameCards && root.NFLGameCards.recordText) return root.NFLGameCards.recordText(team, projected);
    if (!team || !finite(team.wins) || !finite(team.losses)) return "—";
    var wins = Math.trunc(team.wins);
    var losses = Math.trunc(team.losses);
    var ties = team.ties ? Math.trunc(team.ties) : 0;
    if (projected) {
      if (!finite(team.projectedWins) || !finite(team.remainingGames)) return "—";
      var remaining = Math.max(0, Math.trunc(team.remainingGames));
      var added = Math.max(0, Math.min(remaining, Math.round(team.projectedWins - wins)));
      wins += added;
      losses += remaining - added;
    }
    return wins + "–" + losses + (ties ? "–" + ties : "");
  }

  function anchor(index) {
    return "season-game-" + index;
  }

  function probabilityFor(row) {
    var value = row.forecast && row.forecast.winProbability;
    return finite(value) && value >= 0 && value <= 1 ? value : null;
  }

  function resultFor(row) {
    return row.status === "final" && row.actual && ["W", "L", "T"].indexOf(row.actual.outcome) >= 0 ? row.actual.outcome : null;
  }

  function opponentLabel(row) {
    var abbreviation = String(row.opponentAbbr || "").trim();
    if (abbreviation) return abbreviation.slice(0, 7);
    return String(row.opponentName || "OPP").slice(0, 7);
  }

  function description(row) {
    var probability = probabilityFor(row);
    var result = resultFor(row);
    var chance = probability === null ? "No forecast available" : (probability * 100).toFixed(1) + "% season-rating win chance";
    var score = row.actual && finite(row.actual.for) && finite(row.actual.against) ? " " + row.actual.for + "–" + row.actual.against : "";
    return "Week " + (row.week == null ? "unknown" : row.week) + ", " + (row.site || "") + " versus " + row.opponentName + ": " + chance +
      (result ? "; actual " + ({ W: "win", L: "loss", T: "tie" })[result] + score : "") + ".";
  }

  function renderSeasonChart(analysis) {
    var rows = analysis.rows || [];
    if (!rows.length) return "";
    var width = Math.max(620, rows.length * 54 + 68);
    var left = 44;
    var right = 16;
    var top = 32;
    var bottom = 212;
    var slot = (width - left - right) / rows.length;
    var barWidth = Math.min(34, slot * 0.62);
    function y(probability) { return bottom - probability * (bottom - top); }
    var grid = [0, 0.5, 1].map(function (probability) {
      return '<line class="season-chart-grid' + (probability === 0.5 ? " is-threshold" : "") + '" x1="' + left + '" x2="' + (width - right) + '" y1="' + y(probability) + '" y2="' + y(probability) + '"/>' +
        '<text class="season-chart-axis" x="' + (left - 9) + '" y="' + (y(probability) + 4) + '" text-anchor="end">' + Math.round(probability * 100) + "%</text>";
    }).join("");
    var games = rows.map(function (row, index) {
      var x = left + slot * (index + 0.5);
      var probability = probabilityFor(row);
      var result = resultFor(row);
      var bar = probability === null
        ? '<line class="season-chart-gap" x1="' + x + '" x2="' + x + '" y1="' + (top + 30) + '" y2="' + (bottom - 24) + '"/>' +
          '<text class="season-chart-unavailable" x="' + x + '" y="' + (y(0.5) + 4) + '" text-anchor="middle">N/A</text>'
        : '<rect class="season-chart-bar' + (probability < 0.5 ? " is-underdog" : "") + '" x="' + (x - barWidth / 2) + '" y="' + y(probability) + '" width="' + barWidth + '" height="' + (bottom - y(probability)) + '" rx="4"/>' +
          '<text class="season-chart-value" x="' + x + '" y="' + (y(probability) - 8) + '" text-anchor="middle">' + Math.round(probability * 100) + "%</text>";
      var outcome = result
        ? '<g class="season-chart-outcome ' + ({ W: "is-win", L: "is-loss", T: "is-tie" })[result] + '"><circle cx="' + x + '" cy="265" r="10"/><text x="' + x + '" y="269" text-anchor="middle">' + result + "</text></g>"
        : '<text class="season-chart-status" x="' + x + '" y="269" text-anchor="middle">' + (probability === null ? "No forecast" : "Upcoming") + "</text>";
      var target = anchor(index);
      return '<a class="season-chart-game" href="#' + target + '" aria-label="' + esc("View game: " + description(row)) + '"><title>' + esc(description(row)) + "</title>" +
        '<rect class="season-chart-hit" x="' + (left + slot * index + 2) + '" y="12" width="' + (slot - 4) + '" height="268" rx="5"/>' + bar +
        '<text class="season-chart-label" x="' + x + '" y="231" text-anchor="middle">' + esc(opponentLabel(row)) + "</text>" +
        '<text class="season-chart-week" x="' + x + '" y="246" text-anchor="middle">WK ' + esc(row.week == null ? "—" : row.week) + "</text>" + outcome + "</a>";
    }).join("");
    return '<figure class="season-chart" style="--season-chart-width:' + width + 'px"><figcaption class="season-chart-heading"><h4>Season at a glance</h4><p>' + esc(analysis.teamName) + " win chance for every listed game, from the published season rating.</p></figcaption>" +
      '<div class="season-chart-scroll" style="--season-chart-width:' + width + 'px" tabindex="0" aria-label="Season win-chance chart; scroll horizontally on smaller screens"><svg class="season-chart-svg" viewBox="0 0 ' + width + ' 288" role="group">' +
      "<title>" + esc(analysis.teamName) + " season win chances and actual results</title>" +
      "<desc>" + esc(rows.map(description).join(" ")) + "</desc>" + grid + games + "</svg></div>" +
      "<p class=\"season-chart-note\">Select a bar to jump to that game. The dashed line marks a 50% chance. W, L, and T badges are actual results. Bar height is this team's win chance on the published season rating, which already includes games that have been played. It is not a frozen pregame pick. The line below is schedule-adjusted EPA from weeks[].v2, a different number.</p></figure>";
  }

  function renderSummary(analysis) {
    var summary = analysis.summary || {};
    var recordTeam = {
      wins: summary.wins,
      losses: summary.losses,
      ties: summary.ties,
      projectedWins: summary.projectedWins,
      remainingGames: summary.remainingGames
    };
    var expected = finite(summary.projectedWins) && finite(summary.wins) ? summary.projectedWins - summary.wins : null;
    var modeled = finite(summary.remainingGames) ? summary.remainingGames : 0;
    var graded = summary.gradedGames || 0;
    var currentRecord = recordText(recordTeam, false);
    var projectedRecord = recordText(recordTeam, true);
    var rank = finite(analysis.teamRank) && analysis.teamRank > 0
      ? '<span class="game-team-rank forecast-rank" title="Overall neutral-field rank by average win chance.">#' + analysis.teamRank + "</span>"
      : '<span class="game-team-rank forecast-rank is-unranked">Unranked</span>';
    var division = analysis.division && finite(analysis.divisionRank)
      ? '<span class="game-team-rank forecast-rank is-subdivision" title="' + esc("Rank within " + analysis.division + " using the same full-league order.") + '">' + esc(analysis.division) + " #" + analysis.divisionRank + "</span>"
      : "";
    return '<div class="season-projection-team-rank"><span>NEUTRAL MATCHUP RANK</span><div class="forecast-ranks" aria-label="Neutral matchup rank">' + rank + division + "</div></div>" +
      '<div class="season-projection-metrics"><div class="season-projection-metric"><span>PROJECTED REMAINING WINS</span><strong>' +
      (finite(expected) ? Math.round(expected) : "—") + "<small> / " + modeled + " modeled</small></strong><p>Rounded expected wins from the published season rating. Unrounded remaining wins: " + number(expected, 1) + ".</p></div>" +
      '<div class="season-projection-metric"><span>PROJECTED FINAL RECORD</span><strong>' + projectedRecord + "</strong><p>Played results stay as they are. Only remaining games use the season-rating win chance, then the added wins are rounded.</p></div></div>" +
      renderSeasonChart(analysis) +
      '<div class="season-projection-accuracy"><div class="season-projection-accuracy-heading"><span>SEASON RATING VS RESULTS</span><span>' + plural(graded, "completed comparison") + "</span></div>" +
      '<div class="season-projection-error-metrics"><div><span>Margin error</span><strong>' + (graded ? number(summary.marginMae) : "—") + "<small> pts MAE</small></strong></div>" +
      "<div><span>Score error</span><strong>" + (graded ? number(summary.scoreMae) : "—") + "<small> pts MAE</small></strong><small>Average per team</small></div>" +
      "<div><span>Matched winners</span><strong>" + (summary.pickGames ? summary.correctPicks + "/" + summary.pickGames : "—") + "</strong></div></div>" +
      (graded ? "<p>MAE is average absolute error against the published season rating, which includes these results. It is not the frozen pregame grade on the Accuracy page.</p>" : "<p>No completed games to compare yet.</p>") +
      "</div>" +
      '<div class="season-projection-provenance"><span>Current record ' + currentRecord + " · " + plural(modeled, "listed game") + " remaining</span>" +
      "<span>" + esc(analysis.season || "Season") + (analysis.generatedAt ? " · snapshot " + esc(String(analysis.generatedAt).slice(0, 10)) : "") + "</span></div>";
  }

  function divisionTables(teams) {
    var groups = {};
    teams.forEach(function (team) {
      var key = team.division || "";
      (groups[key] = groups[key] || []).push(team);
    });
    var rank = {};
    var size = {};
    Object.keys(groups).forEach(function (key) {
      groups[key].sort(function (a, b) { return a.win_chance_rank - b.win_chance_rank; });
      size[key] = groups[key].length;
      groups[key].forEach(function (team, index) { rank[team.team] = index + 1; });
    });
    return { rank: rank, size: size };
  }

  function build(team, games, teams, meta) {
    meta = meta || {};
    var byName = {};
    teams.forEach(function (entry) { byName[entry.team] = entry; });
    var divisions = divisionTables(teams);
    var rows = (games || []).filter(function (game) {
      return game.home === team.team || game.away === team.team;
    }).slice().sort(function (a, b) {
      return a.week - b.week || String(a.home).localeCompare(String(b.home)) || String(a.away).localeCompare(String(b.away));
    });
    var compared = [];
    var mapped = rows.map(function (game) {
      var home = game.home === team.team;
      var opponent = home ? game.away : game.home;
      var opponentTeam = byName[opponent] || { team: opponent, name: opponent };
      var chance = finite(game.home_win_chance) ? (home ? game.home_win_chance : 1 - game.home_win_chance) : null;
      var margin = finite(game.spread_home) ? (home ? game.spread_home : -game.spread_home) : null;
      var projFor = home ? game.proj_home : game.proj_away;
      var projAgainst = home ? game.proj_away : game.proj_home;
      var actual = null;
      if (game.played && finite(game.home_score) && finite(game.away_score)) {
        var scored = home ? game.home_score : game.away_score;
        var allowed = home ? game.away_score : game.home_score;
        var outcome = scored > allowed ? "W" : scored < allowed ? "L" : "T";
        actual = { for: scored, against: allowed, outcome: outcome, margin: scored - allowed };
        if (finite(margin) && finite(projFor) && finite(projAgainst) && finite(chance)) {
          compared.push({
            marginErr: Math.abs(actual.margin - margin),
            scoreErr: Math.abs(scored - projFor) + Math.abs(allowed - projAgainst),
            pick: outcome !== "T" && chance !== 0.5 ? (chance > 0.5) === (outcome === "W") : null
          });
        }
      }
      return {
        week: game.week,
        opponentName: opponentTeam.name || opponent,
        opponentAbbr: opponent,
        site: game.neutral ? "Neutral site" : home ? "Home" : "Away",
        where: game.neutral ? "N" : home ? "H" : "A",
        status: game.played ? "final" : "upcoming",
        forecast: finite(chance) ? { winProbability: chance } : null,
        actual: actual,
        spread: margin,
        chance: chance,
        projFor: projFor,
        projAgainst: projAgainst,
        opponent: opponent
      };
    });
    var picks = compared.filter(function (row) { return row.pick !== null; });
    return {
      teamName: team.name,
      teamAbbr: team.team,
      season: meta.season,
      generatedAt: meta.generatedAt || "",
      teamRank: team.win_chance_rank,
      division: team.division,
      divisionRank: divisions.rank[team.team],
      divisionFieldSize: divisions.size[team.division] || 0,
      rows: mapped,
      summary: {
        wins: team.wins,
        losses: team.losses,
        ties: team.ties,
        projectedWins: team.projected_wins,
        projectedLosses: team.projected_losses,
        remainingGames: team.remaining_games,
        gradedGames: compared.length,
        marginMae: compared.length ? compared.reduce(function (sum, row) { return sum + row.marginErr; }, 0) / compared.length : null,
        scoreMae: compared.length ? compared.reduce(function (sum, row) { return sum + row.scoreErr; }, 0) / (2 * compared.length) : null,
        correctPicks: picks.filter(function (row) { return row.pick; }).length,
        pickGames: picks.length
      }
    };
  }

  function render(analysis) {
    if (!analysis) return "";
    return '<article class="panel season-outlook-panel" aria-labelledby="season-outlook-title">' +
      '<div class="panel-heading"><h2 id="season-outlook-title">Season outlook</h2></div>' +
      '<div id="season-projection-summary" class="season-projection-summary">' + renderSummary(analysis) + "</div>" +
      '<div id="schedule-forecast-note" class="schedule-forecast-note"><p>Every bar uses the season rating published for the whole year, so a played game is described by a rating that includes it. Projected record keeps results already played and adds the win chances of games not yet played. Frozen pregame picks live on the Week page.</p></div></article>';
  }

  root.NFLSeasonOutlook = {
    build: build,
    render: render,
    anchor: anchor,
    divisionTables: divisionTables
  };
})(typeof window !== "undefined" ? window : globalThis);
