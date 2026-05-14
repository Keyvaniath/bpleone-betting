/*
  EdgeStat client-side probability & betting math library.
  These are the same formulas the Python pipeline uses, mirrored in JS so the
  frontend can compute things like fair price, implied probability, Kelly stake,
  expected value, and edge without a roundtrip to the server.
*/

window.EdgeStat = (function() {

  // ---------- Odds conversions ----------
  function americanToDecimal(am) {
    if (am === 0) return 1;
    return am > 0 ? 1 + am/100 : 1 + 100/Math.abs(am);
  }
  function decimalToAmerican(d) {
    if (d >= 2) return Math.round((d-1)*100);
    return -Math.round(100/(d-1));
  }
  function americanToImplied(am) {
    return am > 0 ? 100/(am+100) : Math.abs(am)/(Math.abs(am)+100);
  }
  function probToAmerican(p) {
    if (p <= 0 || p >= 1) return 0;
    const d = 1/p;
    return decimalToAmerican(d);
  }
  function removeVig(p1, p2) {
    const s = p1+p2;
    return [p1/s, p2/s];
  }

  // ---------- Expected Value ----------
  // EV per $1 stake. Negative EV = market is taking from you.
  function expectedValue(modelProb, americanPrice) {
    const dec = americanToDecimal(americanPrice);
    return modelProb*(dec-1) - (1-modelProb);
  }
  function edgePct(modelProb, americanPrice) {
    return expectedValue(modelProb, americanPrice) * 100;
  }

  // ---------- Kelly Criterion ----------
  // f* = (bp - q) / b   where b = decimal odds - 1, p = win prob, q = 1-p
  // We return fractional Kelly (default 1/4 Kelly) capped at 5u, which is
  // standard among sharp bettors to control variance.
  function kellyStake(modelProb, americanPrice, fraction = 0.25, cap = 5.0) {
    const b = americanToDecimal(americanPrice) - 1;
    const p = modelProb;
    const q = 1 - p;
    const f = (b*p - q) / b;
    if (f <= 0) return 0;
    return Math.min(f * fraction * 100, cap);   // expressed in units (% of bankroll * 100)
  }

  // ---------- Poisson run model for totals ----------
  // P(X=k | lambda) for run distributions; combine away/home runs.
  function poisson(k, lambda) {
    let e = Math.exp(-lambda), f = 1;
    for (let i = 2; i <= k; i++) f *= i;
    return e * Math.pow(lambda, k) / f;
  }
  // Probability total goes OVER `line` runs given expected runs per team.
  function totalOverProb(awayLambda, homeLambda, line) {
    // sum P(total > line) over runs 0..20
    let pOver = 0, pPush = 0;
    for (let a = 0; a <= 20; a++) {
      for (let h = 0; h <= 20; h++) {
        const p = poisson(a, awayLambda) * poisson(h, homeLambda);
        const total = a + h;
        if (total > line) pOver += p;
        else if (total === line) pPush += p;
      }
    }
    // For half-point totals there's no push; pPush will be ~0.
    return pOver + pPush/2;
  }
  // Probability home team wins, ignoring extras (use as ML estimate).
  function homeWinProb(awayLambda, homeLambda) {
    let pHome = 0, pTie = 0;
    for (let a = 0; a <= 20; a++) {
      for (let h = 0; h <= 20; h++) {
        const p = poisson(a, awayLambda) * poisson(h, homeLambda);
        if (h > a) pHome += p;
        else if (h === a) pTie += p;
      }
    }
    // In extras, teams are ~50/50 (close enough for a base model).
    return pHome + 0.5*pTie;
  }

  // ---------- Bayesian update of team "true talent" ----------
  // posterior = prior + (sample - prior) * (n / (n + kappa))
  // Standard shrinkage estimator. Kappa is the strength of the prior.
  function bayesianTalent(prior, sample, n, kappa = 50) {
    return prior + (sample - prior) * (n / (n + kappa));
  }

  // ---------- Pythagorean win expectancy ----------
  // Bill James / Pythagenpat. Uses exponent X derived from runs per game.
  function pythagWinPct(runsFor, runsAgainst) {
    const rpg = (runsFor + runsAgainst) / 162;
    const x = Math.pow(rpg, 0.287);
    return Math.pow(runsFor, x) / (Math.pow(runsFor, x) + Math.pow(runsAgainst, x));
  }

  // ---------- ELO-style rating update ----------
  function eloUpdate(rA, rB, scoreA, k = 6) {
    const expA = 1 / (1 + Math.pow(10, (rB - rA)/400));
    return rA + k * (scoreA - expA);
  }

  // ---------- Confidence bucket ----------
  function confidence(edgePct) {
    if (edgePct >= 5) return 'High';
    if (edgePct >= 3) return 'Medium';
    if (edgePct >= 1.5) return 'Low';
    return 'Pass';
  }

  // ---------- Synthesize a game model ----------
  // Real pipeline (Python) does this more thoroughly. This is a transparent
  // demonstration of how the pieces fit together.
  function modelGame(input) {
    // input: { awayLambda, homeLambda, totalLine }
    const homeP = homeWinProb(input.awayLambda, input.homeLambda);
    const awayP = 1 - homeP;
    const overP = totalOverProb(input.awayLambda, input.homeLambda, input.totalLine);
    return {
      homeWinProb: homeP,
      awayWinProb: awayP,
      overProb: overP,
      underProb: 1 - overP,
      homeFair: probToAmerican(homeP),
      awayFair: probToAmerican(awayP),
      overFair: probToAmerican(overP),
      underFair: probToAmerican(1 - overP),
    };
  }

  return {
    americanToDecimal,
    decimalToAmerican,
    americanToImplied,
    probToAmerican,
    removeVig,
    expectedValue,
    edgePct,
    kellyStake,
    poisson,
    totalOverProb,
    homeWinProb,
    bayesianTalent,
    pythagWinPct,
    eloUpdate,
    confidence,
    modelGame,
  };
})();
