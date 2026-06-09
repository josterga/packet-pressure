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
