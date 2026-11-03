/* Shared matchup math. Keep this aligned with nflrankings/winprob.py. */
(function (root) {
  "use strict";
  var Z80 = 1.2815515655446004;
  var PRIOR = 4;

  function winProbability(margin, scale) {
    var z = margin / scale;
    if (z >= 0) return 1 / (1 + Math.exp(-z));
    var ez = Math.exp(z);
    return ez / (1 + ez);
  }

  function shrink(rate, games, league) {
    games = games || 0;
    if (!games) return league;
    return league + (rate - league) * games / (games + PRIOR);
  }

  function scoring(team) {
    var games = (team.wins || 0) + (team.losses || 0) + (team.ties || 0);
    return {
      pointsFor: games ? (team.points_for || 0) / games : 0,
      pointsAgainst: games ? (team.points_against || 0) / games : 0,
      games: games
    };
  }

  function project(a, b, params, venue, leaguePpg) {
    var hfa = params.home_field_points || 0;
    var bump = venue === "a_home" ? hfa : venue === "b_home" ? -hfa : 0;
    var margin = params.epa_to_points * (a.v2 - b.v2) + bump;
    var sa = scoring(a);
    var sb = scoring(b);
    var total = Math.max(0, (
      shrink(sa.pointsFor, sa.games, leaguePpg) + shrink(sb.pointsAgainst, sb.games, leaguePpg) +
      shrink(sb.pointsFor, sb.games, leaguePpg) + shrink(sa.pointsAgainst, sa.games, leaguePpg)
    ) / 2);
    var half = Z80 * (params.margin_residual_sd || 0);
    return {
      venue: venue,
      margin: margin,
      winProbability: winProbability(margin, params.win_prob_scale),
      total: total,
      scoreA: Math.max(0, (total + margin) / 2),
      scoreB: Math.max(0, (total - margin) / 2),
      marginLow: margin - half,
      marginHigh: margin + half
    };
  }

  root.NFLModel = { project: project, winProbability: winProbability, Z80: Z80 };
})(window);
