import {
  Card,
  CardType,
  EVT_CARD_DRAWN,
  EVT_CARD_PLAYED,
  EVT_COLLISION,
  EVT_GAME_OVER,
  EVT_NOISE_APPLIED,
  EVT_ROUND_END,
  EVT_ROUND_START,
  EVT_ROUTE_EXTENDED,
  EVT_ROUTE_INVALIDATED,
  EVT_ROUTE_STARTED,
  EVT_ROUTE_TERMINATED,
  EVT_SCORE_AWARDED,
  GameConfig,
  GameState,
  PlacementContext,
  PlayerState,
  Rng,
  RouteState,
  TableauState,
  TerminationReason,
  cardSpecial,
  logEvent,
  lookupCard,
  maxOpenRoutes,
  nextRouteId,
  registerCard,
  routeIsOpen,
  routeLastOutputChannel,
  routeMaxHops,
  withOwner,
  withSpecial,
} from "./models";
import { PlayerPolicy } from "./policies";

export class GameEngine {
  config: GameConfig;
  policies: PlayerPolicy[];
  state: GameState;
  private _initialDeck: Card[];
  private _rng: Rng;

  constructor(config: GameConfig, policies: PlayerPolicy[], deck: Card[], rng: Rng) {
    if (policies.length !== config.playerCount) {
      throw new Error(`Expected ${config.playerCount} policies, got ${policies.length}`);
    }
    this.config = config;
    this.policies = policies;
    this._initialDeck = [...deck];
    this._rng = rng;
    this.state = this._buildInitialState();
  }

  // ------------------------------------------------------------------
  // Public interface
  // ------------------------------------------------------------------

  run(): GameState {
    while (!this._isTerminal()) this._runRound();
    return this.state;
  }

  stepTurn(): GameState {
    const s = this.state;
    if (this._isTerminal()) return s;
    const pIdx = s.currentPlayerIndex;
    this._runTurn(pIdx);
    s.currentPlayerIndex = (pIdx + 1) % this.config.playerCount;
    return s;
  }

  // ------------------------------------------------------------------
  // Initialisation
  // ------------------------------------------------------------------

  private _buildInitialState(): GameState {
    const cfg = this.config;
    const players: PlayerState[] = [];
    for (let i = 0; i < cfg.playerCount; i++) {
      players.push({
        playerId: `P${i}`,
        score: 0,
        hand: [],
        playHistory: [],
        policyName: this.policies[i].name,
      });
    }

    const tableau: TableauState = {
      activeCards: new Map(),
      seedNodes: [],
      routes: [],
      noisyChannels: new Set(),
      collidedCardIds: new Set(),
      _routeCounter: 0,
    };

    const state: GameState = {
      config: cfg,
      players,
      deck: [...this._initialDeck],
      discard: [],
      tableau,
      roundNumber: 0,
      turnNumber: 0,
      currentPlayerIndex: 0,
      firstPlayerIndex: 0,
      eventLog: [],
      rng: this._rng,
      _terminal: false,
      _cardRegistry: new Map(),
    };

    for (const card of this._initialDeck) registerCard(state, card);

    for (const p of players) {
      const drawn = this._drawN(state, cfg.startingHandSize);
      p.hand.push(...drawn);
    }

    return state;
  }

  // ------------------------------------------------------------------
  // Round-level
  // ------------------------------------------------------------------

  _runRound(): void {
    const s = this.state;
    s.roundNumber += 1;
    s.turnNumber = 0;
    this._beginRound();

    const first = s.firstPlayerIndex;
    for (let t = 0; t < this.config.turnsPerPlayerPerRound; t++) {
      for (let offset = 0; offset < this.config.playerCount; offset++) {
        const pIdx = (first + offset) % this.config.playerCount;
        if (this._isTerminal()) return;
        s.currentPlayerIndex = pIdx;
        this._runTurn(pIdx);
        s.turnNumber += 1;
      }
    }

    this._endOfRoundScoring();
    this._discardTableau();
    this._advanceRound();
  }

  _beginRound(): void {
    const s = this.state;
    logEvent(s, EVT_ROUND_START, { round: s.roundNumber });

    const seedNodes: Card[] = [];
    const skipped: Card[] = [];
    const alreadyOpen = s.tableau.routes.filter(routeIsOpen).length;
    const needed = Math.max(0, this.config.seedNodesPerRound - alreadyOpen);

    while (seedNodes.length < needed && s.deck.length > 0) {
      const card = s.deck.shift()!;
      if (card.cardType === CardType.TERMINAL || card.cardType === CardType.NOISE) {
        skipped.push(card);
        continue;
      }
      if (seedNodes.some(c => c.outputChannel === card.outputChannel)) {
        skipped.push(card);
        continue;
      }
      seedNodes.push(card);
    }
    s.deck.push(...skipped);
    s.tableau.seedNodes = seedNodes;
    for (const card of seedNodes) s.tableau.activeCards.set(card.cardId, card);
    for (const card of seedNodes) this._tryStartRoute(card, true);
  }

  _advanceRound(): void {
    const cfg = this.config;
    const s = this.state;
    for (const p of s.players) {
      const deficit = cfg.startingHandSize - p.hand.length;
      if (deficit > 0) p.hand.push(...this._drawN(s, deficit));
    }
  }

  // ------------------------------------------------------------------
  // Turn-level
  // ------------------------------------------------------------------

  _runTurn(playerIndex: number): void {
    const s = this.state;
    const player = s.players[playerIndex];

    const drawn = this._drawN(s, this.config.drawPerTurn);
    for (const card of drawn) {
      player.hand.push(card);
      logEvent(s, EVT_CARD_DRAWN, { card_id: card.cardId, card_type: card.cardType });
    }

    const policy = this.policies[playerIndex];
    const legalCount = policy.legalPlays(s, player).length;
    const [card, context] = policy.choosePlay(s, player);

    if (context.passTurn) {
      logEvent(s, "PASS_TURN", { player_id: player.playerId });
      return;
    }

    if (!player.hand.includes(card)) {
      throw new Error(`Policy ${policy.name} chose a card not in hand: ${card.cardId}`);
    }

    player.hand.splice(player.hand.indexOf(card), 1);
    player.playHistory.push(card.cardId);

    const ownedCard = this._applyPlay(playerIndex, card, legalCount, context.targetRouteId);
    this._resolveCardEffects(ownedCard);
    this._updateRoutes(ownedCard);
  }

  _applyPlay(
    playerIndex: number,
    card: Card,
    _legalCount: number,
    targetRouteId: string | null,
  ): Card {
    const s = this.state;
    const playerId = s.players[playerIndex].playerId;
    let owned = withOwner(card, playerId);
    registerCard(s, owned);

    if (targetRouteId) {
      owned = withSpecial(owned, [{ key: "target_route_id", value: targetRouteId }]);
      registerCard(s, owned);
    }

    s.tableau.activeCards.set(owned.cardId, owned);
    logEvent(s, EVT_CARD_PLAYED, {
      card_id: owned.cardId,
      card_type: owned.cardType,
      player_id: playerId,
    });
    return owned;
  }

  private _resolveCardEffects(card: Card): void {
    if (card.cardType === CardType.NOISE && card.outputChannel) {
      this._applyNoise(card.outputChannel);
    }
  }

  private _applyNoise(channel: string): void {
    const s = this.state;
    const cfg = this.config;
    logEvent(s, EVT_NOISE_APPLIED, { channel });

    const interRouteCardIds = new Set<string>();
    for (const route of s.tableau.routes) {
      if (route.isValid && route.length >= cfg.routeMinLength) {
        const interChannels = route.channelsInRoute.slice(0, -1);
        if (interChannels.includes(channel)) {
          route.cardIds.forEach(id => interRouteCardIds.add(id));
        }
      }
    }

    const shieldedCardIds = new Set<string>();
    for (const route of s.tableau.routes) {
      if (route.isValid && route.length >= cfg.routeMinLength) {
        const interChannels = route.channelsInRoute.slice(0, -1);
        if (interChannels.includes(channel)) {
          for (const cid of route.cardIds) {
            const c = lookupCard(s, cid);
            if (c && c.cardType === CardType.FILTER && c.inputChannel === channel) {
              route.cardIds.forEach(id => shieldedCardIds.add(id));
              break;
            }
          }
        }
      }
    }

    const toRemove = [...s.tableau.activeCards.entries()]
      .filter(([cid, c]) =>
        c.outputChannel === channel &&
        interRouteCardIds.has(cid) &&
        !shieldedCardIds.has(cid)
      )
      .map(([cid]) => cid);

    for (const cid of toRemove) {
      s.tableau.activeCards.delete(cid);
      s.tableau.collidedCardIds.add(cid);
      logEvent(s, EVT_COLLISION, { reason: "noise", channel, card_id: cid });
    }

    for (const route of s.tableau.routes) {
      if (route.isValid && route.length >= cfg.routeMinLength) {
        if (route.cardIds.some(cid => s.tableau.collidedCardIds.has(cid))) {
          route.isValid = false;
          route.terminationReason = TerminationReason.NOISE;
          logEvent(s, EVT_ROUTE_INVALIDATED, { route_id: route.routeId, reason: "noise" });
        }
      }
    }
  }

  private _updateRoutes(newCard: Card): void {
    const s = this.state;
    if (s.tableau.collidedCardIds.has(newCard.cardId)) return;
    if (newCard.cardType === CardType.NOISE) return;

    const targetRouteId = cardSpecial(newCard, "target_route_id") as string | null;

    let extendedAny = false;
    for (const route of s.tableau.routes) {
      if (!routeIsOpen(route)) continue;
      if (targetRouteId && route.routeId !== targetRouteId) continue;
      if (this._canExtend(route, newCard)) {
        this._extendRoute(route, newCard);
        extendedAny = true;
        break;
      }
    }

    if (!extendedAny) this._tryStartRoute(newCard);
  }

  private _tryStartRoute(card: Card, isSeed = false): void {
    if (card.cardType === CardType.TERMINAL || card.cardType === CardType.NOISE) return;
    if (this.state.tableau.collidedCardIds.has(card.cardId)) return;

    const s = this.state;
    const validRouteCount = s.tableau.routes.filter(routeIsOpen).length;
    if (validRouteCount >= maxOpenRoutes(s.config)) return;

    const route: RouteState = {
      routeId: nextRouteId(s.tableau),
      cardIds: [card.cardId],
      ownerSequence: [card.ownerId ?? ""],
      channelsInRoute: card.outputChannel ? [card.outputChannel] : [],
      entryChannel: card.inputChannel,
      isValid: true,
      isScoringCandidate: false,
      exitNodeId: card.cardId,
      length: 1,
      terminationReason: TerminationReason.ACTIVE,
      carried: false,
    };

    if (route.length >= routeMaxHops(s.config)) {
      route.terminationReason = TerminationReason.HOP_LIMIT;
      route.isScoringCandidate = route.length >= s.config.routeMinLength;
    }

    s.tableau.routes.push(route);
    logEvent(s, EVT_ROUTE_STARTED, { route_id: route.routeId, card_id: card.cardId, seed: isSeed });
  }

  private _canExtend(route: RouteState, card: Card): boolean {
    const cfg = this.config;
    const lastOut = routeLastOutputChannel(route);
    if (lastOut === null) return false;
    if (card.inputChannel !== "ANY" && card.inputChannel !== lastOut) return false;
    if (cfg.noLoops && route.cardIds.includes(card.cardId)) return false;
    if (cfg.noReturnToFirstHop && route.entryChannel !== null) {
      if (card.outputChannel === route.entryChannel) return false;
    }
    if (card.outputChannel && route.channelsInRoute.includes(card.outputChannel)) return false;
    if (route.length >= routeMaxHops(cfg)) return false;
    return true;
  }

  private _extendRoute(route: RouteState, card: Card): void {
    const s = this.state;
    const cfg = this.config;

    route.cardIds.push(card.cardId);
    route.ownerSequence.push(card.ownerId ?? "");
    if (card.outputChannel && card.outputChannel !== "TERM") {
      route.channelsInRoute.push(card.outputChannel);
    }
    route.exitNodeId = card.cardId;
    route.length += 1;

    logEvent(s, EVT_ROUTE_EXTENDED, { route_id: route.routeId, card_id: card.cardId, length: route.length });

    if (card.cardType === CardType.TERMINAL) {
      route.terminationReason = TerminationReason.TERMINAL;
      route.isScoringCandidate = route.length >= cfg.routeMinLength;
      logEvent(s, EVT_ROUTE_TERMINATED, {
        route_id: route.routeId,
        reason: "terminal",
        scoring: route.isScoringCandidate,
        owner_sequence: [...route.ownerSequence],
      });
    } else if (route.length >= routeMaxHops(cfg)) {
      route.terminationReason = TerminationReason.HOP_LIMIT;
      route.isScoringCandidate = route.length >= cfg.routeMinLength;
      logEvent(s, EVT_ROUTE_TERMINATED, {
        route_id: route.routeId,
        reason: "hop_limit",
        scoring: route.isScoringCandidate,
      });
    }
  }

  // ------------------------------------------------------------------
  // End-of-round scoring
  // ------------------------------------------------------------------

  _endOfRoundScoring(): void {
    const s = this.state;
    const cfg = this.config;
    const preScores = new Map(s.players.map(p => [p.playerId, p.score]));

    for (const route of s.tableau.routes) {
      if (routeIsOpen(route) && route.length >= cfg.routeMinLength) {
        route.isScoringCandidate = true;
      }
    }

    for (const route of s.tableau.routes) {
      if (!route.isValid || !route.isScoringCandidate) continue;
      if (route.length < cfg.routeMinLength) continue;

      const [playerId, score] = this._scoreRoute(route);
      if (playerId && score > 0) {
        const p = s.players.find(p => p.playerId === playerId);
        if (p) {
          p.score += score;
          logEvent(s, EVT_SCORE_AWARDED, {
            route_id: route.routeId,
            player_id: playerId,
            score,
            exit_node_id: route.exitNodeId,
            route_length: route.length,
            termination_reason: route.terminationReason,
          });
        }
      }
    }

    if (cfg.winnerGoesFirst) {
      const deltas = new Map(s.players.map(p => [p.playerId, p.score - (preScores.get(p.playerId) ?? 0)]));
      const best = Math.max(...deltas.values());
      const winners = [...deltas.entries()].filter(([, d]) => d === best).map(([id]) => id);
      if (best > 0 && winners.length === 1) {
        s.firstPlayerIndex = s.players.findIndex(p => p.playerId === winners[0]);
      }
    }

    for (const p of s.players) {
      if (p.score >= cfg.scoreToWin) {
        s._terminal = true;
        logEvent(s, EVT_GAME_OVER, { winner: p.playerId, score: p.score });
        return;
      }
    }

    logEvent(s, EVT_ROUND_END, { round: s.roundNumber });
  }

  private _scoreRoute(route: RouteState): [string | null, number] {
    const s = this.state;
    const cfg = this.config;
    if (!route.exitNodeId) return [null, 0];
    const exitNode = lookupCard(s, route.exitNodeId);
    if (!exitNode) return [null, 0];

    let base = exitNode.packetValue;
    if (exitNode.cardType === CardType.AMPLIFIER) {
      const mult = cardSpecial(exitNode, "multiplier", cfg.amplifierMultiplier) as number;
      base = base * mult;
    }
    return [exitNode.ownerId, base];
  }

  _discardTableau(): void {
    const s = this.state;
    const cfg = this.config;

    const persisted = s.tableau.routes.filter(r => routeIsOpen(r) && r.length < cfg.routeMinLength);
    const persistedIds = new Set(persisted.flatMap(r => r.cardIds));
    for (const r of persisted) r.carried = true;

    for (const card of s.tableau.activeCards.values()) {
      if (!persistedIds.has(card.cardId)) s.discard.push(card);
    }

    s.tableau.activeCards = new Map(
      [...s.tableau.activeCards.entries()].filter(([cid]) => persistedIds.has(cid))
    );
    s.tableau.seedNodes = [];
    s.tableau.routes = persisted;
    s.tableau.noisyChannels.clear();
    s.tableau.collidedCardIds.clear();
  }

  // ------------------------------------------------------------------
  // Helpers
  // ------------------------------------------------------------------

  private _drawN(state: GameState, n: number): Card[] {
    const drawn: Card[] = [];
    for (let i = 0; i < n; i++) {
      if (state.deck.length === 0) {
        if (state.discard.length > 0) {
          state.deck = [...state.discard];
          state.discard = [];
          state.rng.shuffle(state.deck);
        } else break;
      }
      drawn.push(state.deck.shift()!);
    }
    return drawn;
  }

  _isTerminal(): boolean {
    const s = this.state;
    if (s._terminal) return true;
    if (s.roundNumber >= this.config.maxRounds) {
      if (!s._terminal) {
        const winner = [...s.players].sort((a, b) => b.score - a.score)[0];
        s._terminal = true;
        logEvent(s, EVT_GAME_OVER, { winner: winner.playerId, score: winner.score, reason: "max_rounds" });
      }
      return true;
    }
    return false;
  }
}
