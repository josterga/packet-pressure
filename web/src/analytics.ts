declare function gtag(...args: unknown[]): void;

function _gtag(...args: unknown[]): void {
  if (typeof gtag !== "undefined") gtag(...args);
}

export function trackGameStarted(playerCount: number, roundsMax: number, scoreToWin: number): void {
  _gtag("event", "game_started", { player_count: playerCount, rounds_max: roundsMax, score_to_win: scoreToWin });
}

export function trackRoundCompleted(roundNumber: number, humanScore: number, routesScoredCount: number): void {
  _gtag("event", "round_completed", { round_number: roundNumber, human_score: humanScore, routes_scored_count: routesScoredCount });
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

export function trackNoisePlayed(routesDestroyed: number): void {
  _gtag("event", "noise_played", { routes_destroyed: routesDestroyed });
}

export function trackPassTaken(roundNumber: number): void {
  _gtag("event", "pass_taken", { round_number: roundNumber });
}

export function trackRouteScored(routeLength: number, terminationReason: string, score: number, humanOwned: boolean): void {
  _gtag("event", "route_scored", { route_length: routeLength, termination_reason: terminationReason, score, human_owned: humanOwned });
}

export function trackRouteDestroyed(routeLength: number): void {
  _gtag("event", "route_destroyed", { route_length: routeLength });
}

export function trackHelpOpened(): void {
  _gtag("event", "help_opened");
}

export function trackHintsToggled(enabled: boolean): void {
  _gtag("event", "hints_toggled", { enabled });
}
