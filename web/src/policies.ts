import {
  Card,
  CardType,
  GameConfig,
  GameState,
  PlacementContext,
  PlayerState,
  RouteState,
  cardSpecial,
  emptyContext,
  passContext,
  maxOpenRoutes,
  routeIsOpen,
  routeLastOutputChannel,
  routeMaxHops,
  targetContext,
} from "./models";

// ---------------------------------------------------------------------------
// Base class
// ---------------------------------------------------------------------------

export abstract class PlayerPolicy {
  abstract name: string;

  abstract choosePlay(state: GameState, player: PlayerState): [Card, PlacementContext];

  legalPlays(state: GameState, player: PlayerState): [Card, PlacementContext][] {
    const plays: [Card, PlacementContext][] = [];
    const tableauIds = new Set(state.tableau.activeCards.keys());
    const openRoutes = state.tableau.routes.filter(routeIsOpen);

    for (const card of player.hand) {
      if (tableauIds.has(card.cardId)) continue;

      if (card.cardType === CardType.NOISE) {
        const ch = card.outputChannel;
        if (ch) {
          for (const r of state.tableau.routes) {
            if (r.isValid && r.length >= state.config.routeMinLength) {
              if (r.channelsInRoute.slice(0, -1).includes(ch)) {
                plays.push([card, emptyContext()]);
                break;
              }
            }
          }
        }
      } else if (card.cardType === CardType.TERMINAL) {
        for (const route of openRoutes) {
          if (route.length >= state.config.routeMinLength) {
            plays.push([card, targetContext(route.routeId)]);
          }
        }
      } else {
        const validRouteCount = state.tableau.routes.filter(routeIsOpen).length;
        const capReached = validRouteCount >= maxOpenRoutes(state.config);
        const extendable = openRoutes.filter(r => this._canCardExtendRoute(card, r, state));
        for (const route of extendable) {
          plays.push([card, targetContext(route.routeId)]);
        }
        if (!capReached) {
          plays.push([card, emptyContext()]);
        }
      }
    }

    return plays.length > 0 ? plays : this._fallbackPlay(state, player);
  }

  protected _fallbackPlay(state: GameState, player: PlayerState): [Card, PlacementContext][] {
    if (player.hand.length > 0) return [[player.hand[0], passContext()]];
    throw new Error(`Player ${player.playerId} has no cards`);
  }

  protected _openRoutes(state: GameState): RouteState[] {
    return state.tableau.routes.filter(routeIsOpen);
  }

  _canCardExtendRoute(card: Card, route: RouteState, state: GameState): boolean {
    const cfg = state.config;
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

  protected _estimateExitNodeValue(card: Card, route: RouteState, state: GameState): number {
    const newLength = route.length + 1;
    if (newLength < state.config.routeMinLength) return 0;
    let base = card.packetValue;
    if (card.cardType === CardType.AMPLIFIER) {
      base *= (cardSpecial(card, "multiplier", state.config.amplifierMultiplier) as number);
    }
    return base;
  }

  protected _routeExitNodeValue(route: RouteState, state: GameState): number {
    if (!route.exitNodeId) return 0;
    const card = state._cardRegistry.get(route.exitNodeId);
    if (!card) return 0;
    return card.packetValue;
  }

  protected _chooseRandom(plays: [Card, PlacementContext][], state: GameState): [Card, PlacementContext] {
    return plays[state.rng.nextInt(plays.length)];
  }
}

// ---------------------------------------------------------------------------
// RandomLegal
// ---------------------------------------------------------------------------

export class RandomLegal extends PlayerPolicy {
  name = "random_legal";

  choosePlay(state: GameState, player: PlayerState): [Card, PlacementContext] {
    return this._chooseRandom(this.legalPlays(state, player), state);
  }
}

// ---------------------------------------------------------------------------
// GreedyExitNode
// ---------------------------------------------------------------------------

export class GreedyExitNode extends PlayerPolicy {
  name = "greedy_exit_node";

  choosePlay(state: GameState, player: PlayerState): [Card, PlacementContext] {
    const plays = this.legalPlays(state, player);
    const openRoutes = this._openRoutes(state);

    let bestScore = -1;
    let bestPlays: [Card, PlacementContext][] = [];

    for (let [card, ctx] of plays) {
      let score = 0;
      if (card.cardType === CardType.NOISE) {
        // noise never scores directly
      } else if (card.cardType === CardType.TERMINAL || card.cardType === CardType.AMPLIFIER) {
        for (const route of openRoutes) {
          if (card.cardType === CardType.TERMINAL && route.length < state.config.routeMinLength) continue;
          if (this._canCardExtendRoute(card, route, state)) {
            const v = this._estimateExitNodeValue(card, route, state);
            if (v > score) {
              score = v;
              ctx = targetContext(route.routeId);
            }
          }
        }
      } else {
        for (const route of openRoutes) {
          if (this._canCardExtendRoute(card, route, state)) {
            const v = this._estimateExitNodeValue(card, route, state);
            if (v > score) {
              score = v;
              ctx = targetContext(route.routeId);
            }
          }
        }
      }

      if (score > bestScore) {
        bestScore = score;
        bestPlays = [[card, ctx]];
      } else if (score === bestScore) {
        bestPlays.push([card, ctx]);
      }
    }

    if (bestPlays.length > 0) return this._chooseRandom(bestPlays, state);
    return this._chooseRandom(plays, state);
  }
}

// ---------------------------------------------------------------------------
// DenialCollision
// ---------------------------------------------------------------------------

export class DenialCollision extends PlayerPolicy {
  name = "denial_collision";
  private _threshold = 50;

  choosePlay(state: GameState, player: PlayerState): [Card, PlacementContext] {
    const plays = this.legalPlays(state, player);
    const [targetRoute, denialValue] = this._bestOpponentRoute(state, player);

    if (targetRoute !== null && denialValue >= this._threshold) {
      const denialPlay = this._findDenialPlay(state, player, targetRoute, plays);
      if (denialPlay !== null) return denialPlay;
    }

    return new GreedyExitNode().choosePlay(state, player);
  }

  private _bestOpponentRoute(state: GameState, player: PlayerState): [RouteState | null, number] {
    let bestRoute: RouteState | null = null;
    let bestValue = 0;
    for (const route of this._openRoutes(state)) {
      if (route.ownerSequence.length === 0) continue;
      const lastOwner = route.ownerSequence[route.ownerSequence.length - 1];
      if (lastOwner === player.playerId) continue;
      const val = this._routeExitNodeValue(route, state);
      if (val > bestValue) {
        bestValue = val;
        bestRoute = route;
      }
    }
    return [bestRoute, bestValue];
  }

  private _findDenialPlay(
    state: GameState,
    _player: PlayerState,
    targetRoute: RouteState,
    plays: [Card, PlacementContext][],
  ): [Card, PlacementContext] | null {
    const lastOut = routeLastOutputChannel(targetRoute);
    if (lastOut) {
      for (const [card, ctx] of plays) {
        if (card.cardType === CardType.NOISE && card.outputChannel === lastOut) return [card, ctx];
      }
    }

    if (targetRoute.length >= state.config.routeMinLength) {
      for (const [card] of plays) {
        if (card.cardType === CardType.TERMINAL) {
          return [card, targetContext(targetRoute.routeId)];
        }
      }
    }

    if (lastOut) {
      for (const [card] of plays) {
        if (card.cardType !== CardType.NOISE && card.cardType !== CardType.TERMINAL) {
          if (card.inputChannel === "ANY" || card.inputChannel === lastOut) {
            return [card, targetContext(targetRoute.routeId)];
          }
        }
      }
    }

    return null;
  }
}

// ---------------------------------------------------------------------------
// RouteBuilder
// ---------------------------------------------------------------------------

export class RouteBuilder extends PlayerPolicy {
  name = "route_builder";

  choosePlay(state: GameState, player: PlayerState): [Card, PlacementContext] {
    const plays = this.legalPlays(state, player);
    const openRoutes = this._openRoutes(state);
    const cfg = state.config;

    // 1. Complete a route
    for (const [card, _ctx] of plays) {
      if (card.cardType === CardType.TERMINAL || card.cardType === CardType.AMPLIFIER) {
        for (const route of openRoutes) {
          if (route.length >= cfg.routeMinLength - 1 && this._canCardExtendRoute(card, route, state)) {
            return [card, targetContext(route.routeId)];
          }
        }
      }
    }

    // 2. Extend seed-anchored route
    const seedNodeIds = new Set(state.tableau.seedNodes.map(c => c.cardId));
    for (const [card] of plays) {
      if (card.cardType === CardType.TERMINAL || card.cardType === CardType.NOISE) continue;
      for (const route of openRoutes) {
        if (route.cardIds.length > 0 && seedNodeIds.has(route.cardIds[0])) {
          if (this._canCardExtendRoute(card, route, state)) {
            return [card, targetContext(route.routeId)];
          }
        }
      }
    }

    // 3. Extend any valid route (prefer non-noisy output)
    for (const [card] of plays) {
      if (card.cardType === CardType.TERMINAL || card.cardType === CardType.NOISE) continue;
      for (const route of openRoutes) {
        if (this._canCardExtendRoute(card, route, state)) {
          if (!state.tableau.noisyChannels.has(card.outputChannel ?? "")) {
            return [card, targetContext(route.routeId)];
          }
        }
      }
    }

    // 4. Start new route from seed
    for (const [card] of plays) {
      if (card.cardType === CardType.TERMINAL || card.cardType === CardType.NOISE) continue;
      for (const seed of state.tableau.seedNodes) {
        if (card.inputChannel === seed.outputChannel) {
          if (!state.tableau.noisyChannels.has(card.outputChannel ?? "")) {
            return [card, emptyContext()];
          }
        }
      }
    }

    return this._chooseRandom(plays, state);
  }
}

export function makeDefaultPolicies(cfg: GameConfig): PlayerPolicy[] {
  const aiCount = cfg.playerCount - 1;
  const types = [GreedyExitNode, DenialCollision, RouteBuilder, RandomLegal];
  return Array.from({ length: aiCount }, (_, i) => new types[i % types.length]());
}
