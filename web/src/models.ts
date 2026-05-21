// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export enum CardType {
  RELAY = "relay",
  TERMINAL = "terminal",
  AMPLIFIER = "amplifier",
  NOISE = "noise",
  FILTER = "filter",
}

export enum TerminationReason {
  ACTIVE = "active",
  TERMINAL = "terminal",
  AMPLIFIER = "amplifier",
  COLLISION = "collision",
  NOISE = "noise",
  HOP_LIMIT = "hop_limit",
  LOOP_DETECTED = "loop_detected",
  RETURN_TO_FIRST = "return_to_first_hop",
}

// ---------------------------------------------------------------------------
// Event type constants
// ---------------------------------------------------------------------------

export const EVT_ROUND_START = "ROUND_START";
export const EVT_ROUND_END = "ROUND_END";
export const EVT_CARD_DRAWN = "CARD_DRAWN";
export const EVT_CARD_PLAYED = "CARD_PLAYED";
export const EVT_COLLISION = "COLLISION";
export const EVT_NOISE_APPLIED = "NOISE_APPLIED";
export const EVT_ROUTE_STARTED = "ROUTE_STARTED";
export const EVT_ROUTE_EXTENDED = "ROUTE_EXTENDED";
export const EVT_ROUTE_TERMINATED = "ROUTE_TERMINATED";
export const EVT_ROUTE_INVALIDATED = "ROUTE_INVALIDATED";
export const EVT_SCORE_AWARDED = "SCORE_AWARDED";
export const EVT_GAME_OVER = "GAME_OVER";

// ---------------------------------------------------------------------------
// GameConfig
// ---------------------------------------------------------------------------

export interface GameConfig {
  readonly playerCount: number;
  readonly scoreToWin: number;
  readonly maxRounds: number;
  readonly channels: readonly string[];
  readonly channelShapes: readonly string[];
  readonly channelColors: readonly string[];
  readonly colors: readonly string[];
  readonly startingHandSize: number;
  readonly drawPerTurn: number;
  readonly turnsPerPlayerPerRound: number;
  readonly seedNodesPerRound: number;
  readonly routeMinLength: number;
  readonly deckSize: number;
  readonly noLoops: boolean;
  readonly noReturnToFirstHop: boolean;
  readonly winnerGoesFirst: boolean;
  readonly amplifierMultiplier: number;
  readonly noiseScope: string;
  readonly terminalPacketValues: readonly number[];
  readonly specialDistribution: readonly [string, number][];
  readonly packetValues: readonly number[];
}

export function routeMaxHops(cfg: GameConfig): number {
  return cfg.channels.length;
}

export function maxOpenRoutes(cfg: GameConfig): number {
  return cfg.playerCount;
}

export function channelIndex(cfg: GameConfig, ch: string): number | null {
  const idx = cfg.channels.indexOf(ch);
  return idx === -1 ? null : idx;
}

export function channelColor(cfg: GameConfig, ch: string): string | null {
  const idx = channelIndex(cfg, ch);
  if (idx === null || idx >= cfg.channelColors.length) return null;
  return cfg.channelColors[idx];
}

export function specialDistDict(cfg: GameConfig): Map<string, number> {
  return new Map(cfg.specialDistribution);
}

// ---------------------------------------------------------------------------
// Card (immutable)
// ---------------------------------------------------------------------------

export interface SpecialProp {
  readonly key: string;
  readonly value: unknown;
}

export interface Card {
  readonly cardId: string;
  readonly cardType: CardType;
  readonly inputChannel: string | null;
  readonly outputChannel: string | null;
  readonly packetValue: number;
  readonly color: string;
  readonly ownerId: string | null;
  readonly specialProperties: readonly SpecialProp[];
}

export function cardSpecial(card: Card, key: string, defaultVal: unknown = null): unknown {
  const prop = card.specialProperties.find(p => p.key === key);
  return prop !== undefined ? prop.value : defaultVal;
}

export function withOwner(card: Card, ownerId: string): Card {
  return { ...card, ownerId };
}

export function withSpecial(card: Card, props: readonly SpecialProp[]): Card {
  return { ...card, specialProperties: props };
}

// ---------------------------------------------------------------------------
// PlacementContext
// ---------------------------------------------------------------------------

export interface PlacementContext {
  targetRouteId: string | null;
  passTurn: boolean;
}

export function emptyContext(): PlacementContext {
  return { targetRouteId: null, passTurn: false };
}

export function targetContext(routeId: string): PlacementContext {
  return { targetRouteId: routeId, passTurn: false };
}

export function passContext(): PlacementContext {
  return { targetRouteId: null, passTurn: true };
}

// ---------------------------------------------------------------------------
// PlayerState
// ---------------------------------------------------------------------------

export interface PlayerState {
  readonly playerId: string;
  score: number;
  hand: Card[];
  playHistory: string[];
  policyName: string;
}

// ---------------------------------------------------------------------------
// RouteState
// ---------------------------------------------------------------------------

export interface RouteState {
  readonly routeId: string;
  cardIds: string[];
  ownerSequence: string[];
  channelsInRoute: string[];
  entryChannel: string | null;
  isValid: boolean;
  isScoringCandidate: boolean;
  exitNodeId: string | null;
  length: number;
  terminationReason: TerminationReason;
  carried: boolean;
}

export function routeLastOutputChannel(route: RouteState): string | null {
  return route.channelsInRoute.length > 0
    ? route.channelsInRoute[route.channelsInRoute.length - 1]
    : null;
}

export function routeIsOpen(route: RouteState): boolean {
  return route.isValid && route.terminationReason === TerminationReason.ACTIVE;
}

// ---------------------------------------------------------------------------
// TableauState
// ---------------------------------------------------------------------------

export interface TableauState {
  activeCards: Map<string, Card>;
  seedNodes: Card[];
  routes: RouteState[];
  noisyChannels: Set<string>;
  collidedCardIds: Set<string>;
  _routeCounter: number;
}

export function nextRouteId(tableau: TableauState): string {
  tableau._routeCounter += 1;
  return `R-${String(tableau._routeCounter).padStart(4, "0")}`;
}

// ---------------------------------------------------------------------------
// GameState
// ---------------------------------------------------------------------------

export interface GameState {
  config: GameConfig;
  players: PlayerState[];
  deck: Card[];
  discard: Card[];
  tableau: TableauState;
  roundNumber: number;
  turnNumber: number;
  currentPlayerIndex: number;
  firstPlayerIndex: number;
  eventLog: Record<string, unknown>[];
  rng: Rng;
  _terminal: boolean;
  _cardRegistry: Map<string, Card>;
}

export function logEvent(state: GameState, eventType: string, extra: Record<string, unknown> = {}): void {
  const playerId = state.players.length > 0
    ? state.players[state.currentPlayerIndex].playerId
    : null;
  state.eventLog.push({
    round: state.roundNumber,
    turn: state.turnNumber,
    player: playerId,
    event: eventType,
    ...extra,
  });
}

export function registerCard(state: GameState, card: Card): void {
  state._cardRegistry.set(card.cardId, card);
}

export function lookupCard(state: GameState, cardId: string): Card | null {
  return state._cardRegistry.get(cardId) ?? null;
}

// ---------------------------------------------------------------------------
// Minimal seeded PRNG (mulberry32)
// ---------------------------------------------------------------------------

export interface Rng {
  next(): number;           // [0, 1)
  nextInt(n: number): number; // [0, n)
  shuffle<T>(arr: T[]): void;
  choice<T>(arr: readonly T[]): T;
  weightedChoice<T>(items: readonly T[], weights: readonly number[]): T;
}

export function makeMulberry32(seed: number): Rng {
  let s = seed >>> 0;
  function next(): number {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) >>> 0;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }
  function nextInt(n: number): number {
    return Math.floor(next() * n);
  }
  function shuffle<T>(arr: T[]): void {
    for (let i = arr.length - 1; i > 0; i--) {
      const j = nextInt(i + 1);
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
  }
  function choice<T>(arr: readonly T[]): T {
    return arr[nextInt(arr.length)];
  }
  function weightedChoice<T>(items: readonly T[], weights: readonly number[]): T {
    const total = weights.reduce((a, b) => a + b, 0);
    let r = next() * total;
    for (let i = 0; i < items.length; i++) {
      r -= weights[i];
      if (r <= 0) return items[i];
    }
    return items[items.length - 1];
  }
  return { next, nextInt, shuffle, choice, weightedChoice };
}
