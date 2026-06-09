declare function gtag(...args: unknown[]): void;

function _gtag(...args: unknown[]): void {
  if (typeof gtag !== "undefined") gtag(...args);
}

export function trackGameStarted(playerCount: number, roundsMax: number, scoreToWin: number): void {
  _gtag("event", "game_started", { player_count: playerCount, rounds_max: roundsMax, score_to_win: scoreToWin });
}

export function trackRoundCompleted(
  roundNumber: number,
  humanScore: number,
  routesScoredCount: number,
  humanRoutesScored: number,
  maxRouteLength: number,
): void {
  _gtag("event", "round_completed", {
    round_number: roundNumber,
    human_score: humanScore,
    routes_scored_count: routesScoredCount,
    human_routes_scored: humanRoutesScored,
    max_route_length: maxRouteLength,
  });
}

export function trackGameCompleted(roundsPlayed: number, humanWon: boolean, humanScore: number, winnerScore: number, humanRank: number): void {
  _gtag("event", "game_completed", { rounds_played: roundsPlayed, human_won: humanWon, human_score: humanScore, winner_score: winnerScore, human_rank: humanRank });
}

export function trackGameAbandoned(roundNumber: number, humanScore: number): void {
  _gtag("event", "game_abandoned", { round_number: roundNumber, human_score: humanScore });
}

export function trackNewGame(source: "game_over" | "round_end"): void {
  _gtag("event", "new_game", { source });
}

export function trackCardPlayed(cardType: string, action: "extend" | "new_route" | "pass"): void {
  _gtag("event", "card_played", { card_type: cardType, action });
}

export function trackNoisePlayed(routesDestroyed: number, destroyedLengths: number[]): void {
  _gtag("event", "noise_played", {
    routes_destroyed: routesDestroyed,
    avg_destroyed_length: destroyedLengths.length > 0
      ? Math.round(destroyedLengths.reduce((a, b) => a + b, 0) / destroyedLengths.length)
      : 0,
  });
}

export function trackHelpOpened(): void {
  _gtag("event", "help_opened");
}

export function trackHintsToggled(enabled: boolean): void {
  _gtag("event", "hints_toggled", { enabled });
}
