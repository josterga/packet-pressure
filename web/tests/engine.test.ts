import { describe, it, expect } from "vitest";
import { GameEngine } from "../src/engine";
import { DeckBuilder } from "../src/deck";
import { FAST_CONFIG } from "../src/config";
import {
  Card,
  CardType,
  GameConfig,
  TerminationReason,
  makeMulberry32,
  registerCard,
  routeIsOpen,
} from "../src/models";
import { RandomLegal } from "../src/policies";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeCard(
  cardId: string,
  cardType: CardType = CardType.RELAY,
  inCh: string | null = "01",
  outCh: string | null = "02",
  value = 100,
  owner: string | null = null,
  special: { key: string; value: unknown }[] = [],
): Card {
  return { cardId, cardType, inputChannel: inCh, outputChannel: outCh, packetValue: value, color: "red", ownerId: owner, specialProperties: special };
}

function makeEngine(overrides: Partial<GameConfig> = {}, nPolicies = 3): GameEngine {
  const config: GameConfig = { ...FAST_CONFIG, playerCount: nPolicies, ...overrides };
  const rng = makeMulberry32(42);
  const deck = new DeckBuilder(config, rng).build();
  const policies = Array.from({ length: nPolicies }, () => new RandomLegal());
  return new GameEngine(config, policies, deck, makeMulberry32(42));
}

// Place a card directly into the tableau and registry (mirrors Python `s.register_card` + `active_cards`)
function addToTableau(engine: GameEngine, card: Card): void {
  const s = engine.state;
  registerCard(s, card);
  s.tableau.activeCards.set(card.cardId, card);
}

// ---------------------------------------------------------------------------
// Route extension
// ---------------------------------------------------------------------------

describe("route extension", () => {
  it("extends when input channel matches last output channel", () => {
    const engine = makeEngine();
    const s = engine.state;

    const seed = makeCard("SEED-0001", CardType.RELAY, "01", "02", 100, "P0");
    addToTableau(engine, seed);
    engine._runTurn; // not calling _runTurn; use internal helpers directly
    (engine as any)._tryStartRoute(seed);
    expect(s.tableau.routes).toHaveLength(1);
    const route = s.tableau.routes[0];
    expect(route.length).toBe(1);

    const card = makeCard("PKT-9001", CardType.RELAY, "02", "03", 100, "P1");
    addToTableau(engine, card);
    (engine as any)._updateRoutes(card);

    expect(route.length).toBe(2);
    expect(route.exitNodeId).toBe("PKT-9001");
  });

  it("does not extend when input channel mismatches; starts a new route instead", () => {
    const engine = makeEngine();
    const s = engine.state;

    const seed = makeCard("SEED-0002", CardType.RELAY, "01", "02", 100, "P0");
    addToTableau(engine, seed);
    (engine as any)._tryStartRoute(seed);

    const card = makeCard("PKT-9002", CardType.RELAY, "03", "01", 100, "P1");
    addToTableau(engine, card);
    (engine as any)._updateRoutes(card);

    expect(s.tableau.routes).toHaveLength(2);
    expect(s.tableau.routes[0].length).toBe(1);
  });

  it("terminates at hop limit", () => {
    const engine = makeEngine();
    const s = engine.state;

    const c1 = makeCard("PKT-A", CardType.RELAY, "01", "02", 100, "P0");
    const c2 = makeCard("PKT-B", CardType.RELAY, "02", "03", 100, "P0");
    const c3 = makeCard("PKT-C", CardType.RELAY, "03", "01", 100, "P0");
    for (const c of [c1, c2, c3]) addToTableau(engine, c);

    (engine as any)._tryStartRoute(c1);
    (engine as any)._updateRoutes(c2);
    (engine as any)._updateRoutes(c3);

    const route = s.tableau.routes[0];
    expect(route.length).toBe(3);
    expect(route.terminationReason).toBe(TerminationReason.HOP_LIMIT);
  });

  it("noLoops prevents extending with the same card", () => {
    const engine = makeEngine({ noLoops: true });
    const s = engine.state;

    const c1 = makeCard("PKT-LOOP", CardType.RELAY, "01", "02", 100, "P0");
    addToTableau(engine, c1);
    (engine as any)._tryStartRoute(c1);

    const canExtend = (engine as any)._canExtend(s.tableau.routes[0], c1);
    expect(canExtend).toBe(false);
  });

  it("noReturnToFirstHop prevents returning to entry channel", () => {
    const engine = makeEngine({ noReturnToFirstHop: true });
    const s = engine.state;

    const c1 = makeCard("PKT-R1", CardType.RELAY, "01", "02", 100, "P0");
    addToTableau(engine, c1);
    (engine as any)._tryStartRoute(c1);

    // c_return outputs to "01", which is the route's entry channel
    const cReturn = makeCard("PKT-R2", CardType.RELAY, "02", "01", 100, "P1");
    registerCard(s, cReturn);
    const canExtend = (engine as any)._canExtend(s.tableau.routes[0], cReturn);
    expect(canExtend).toBe(false);
  });

  it("does not extend when output channel already in route", () => {
    const engine = makeEngine();
    const s = engine.state;

    // Route already has "01" in channelsInRoute
    const c1 = makeCard("PKT-A", CardType.RELAY, "03", "01", 100, "P0");
    addToTableau(engine, c1);
    (engine as any)._tryStartRoute(c1);

    // c2 input matches route tail ("01"), but output "01" is already in channelsInRoute
    const c2 = makeCard("PKT-B", CardType.RELAY, "01", "01", 100, "P1");
    registerCard(s, c2);
    const canExtend = (engine as any)._canExtend(s.tableau.routes[0], c2);
    expect(canExtend).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Terminal node
// ---------------------------------------------------------------------------

describe("terminal node", () => {
  it("ANY input channel extends any route regardless of last output", () => {
    const engine = makeEngine();
    const s = engine.state;

    const c1 = makeCard("PKT-T1", CardType.RELAY, "01", "03", 100, "P0");
    addToTableau(engine, c1);
    (engine as any)._tryStartRoute(c1);

    const term = makeCard("TERM-0001", CardType.TERMINAL, "ANY", "TERM", 400, "P1");
    addToTableau(engine, term);
    (engine as any)._updateRoutes(term);

    const route = s.tableau.routes[0];
    expect(route.terminationReason).toBe(TerminationReason.TERMINAL);
    expect(route.exitNodeId).toBe("TERM-0001");
  });

  it("is a scoring candidate when min length is met", () => {
    const engine = makeEngine({ routeMinLength: 2 });
    const s = engine.state;

    const c1 = makeCard("PKT-T2", CardType.RELAY, "01", "02", 100, "P0");
    addToTableau(engine, c1);
    (engine as any)._tryStartRoute(c1);

    const term = makeCard("TERM-0002", CardType.TERMINAL, "ANY", "TERM", 400, "P1");
    addToTableau(engine, term);
    (engine as any)._updateRoutes(term);

    const route = s.tableau.routes[0];
    expect(route.length).toBe(2);
    expect(route.isScoringCandidate).toBe(true);
  });

  it("cannot start a new route", () => {
    const engine = makeEngine();
    const s = engine.state;

    const term = makeCard("TERM-X1", CardType.TERMINAL, "ANY", "TERM", 400);
    registerCard(s, term);
    (engine as any)._tryStartRoute(term);
    expect(s.tableau.routes).toHaveLength(0);
  });

  it("terminal PKT value scores, not predecessor value", () => {
    const engine = makeEngine({ routeMinLength: 2 });
    const s = engine.state;

    const c1 = makeCard("REL-T1", CardType.RELAY, "01", "02", 300, "P0");
    const term = makeCard("TERM-T1", CardType.TERMINAL, "ANY", "TERM", 500, "P1");
    for (const c of [c1, term]) addToTableau(engine, c);

    (engine as any)._tryStartRoute(c1);
    (engine as any)._updateRoutes(term);

    const route = s.tableau.routes[0];
    const [owner, score] = (engine as any)._scoreRoute(route);
    expect(score).toBe(500);
    expect(owner).toBe("P1");
  });
});

// ---------------------------------------------------------------------------
// Amplifier node
// ---------------------------------------------------------------------------

describe("amplifier node", () => {
  it("applies multiplier when amplifier is exit node", () => {
    const engine = makeEngine({ amplifierMultiplier: 3 });
    const s = engine.state;

    const c1 = makeCard("PKT-A1", CardType.RELAY, "01", "02", 100, "P0");
    const amp = makeCard("AMP-0001", CardType.AMPLIFIER, "02", "03", 200, "P1", [{ key: "multiplier", value: 3 }]);
    for (const c of [c1, amp]) addToTableau(engine, c);

    (engine as any)._tryStartRoute(c1);
    (engine as any)._updateRoutes(amp);

    const route = s.tableau.routes[0];
    expect(route.terminationReason).toBe(TerminationReason.ACTIVE);
    expect(route.exitNodeId).toBe("AMP-0001");

    const [owner, score] = (engine as any)._scoreRoute(route);
    expect(owner).toBe("P1");
    expect(score).toBe(600); // 200 * 3
  });

  it("multiplier is lost when extended past the amplifier", () => {
    const engine = makeEngine({ amplifierMultiplier: 2, routeMinLength: 2 });
    const s = engine.state;

    const c1 = makeCard("REL-A1", CardType.RELAY, "01", "02", 100, "P0");
    const amp = makeCard("AMP-A1", CardType.AMPLIFIER, "02", "03", 200, "P1", [{ key: "multiplier", value: 2 }]);
    const c3 = makeCard("REL-A2", CardType.RELAY, "03", "01", 150, "P2");
    for (const c of [c1, amp, c3]) addToTableau(engine, c);

    (engine as any)._tryStartRoute(c1);
    (engine as any)._updateRoutes(amp);
    (engine as any)._updateRoutes(c3);

    const route = s.tableau.routes[0];
    expect(route.exitNodeId).toBe("REL-A2");
    const [, score] = (engine as any)._scoreRoute(route);
    expect(score).toBe(150); // relay face value; amplifier bonus gone
  });
});

// ---------------------------------------------------------------------------
// Noise node
// ---------------------------------------------------------------------------

describe("noise node", () => {
  it("removes cards on targeted intermediate channel", () => {
    const engine = makeEngine({ routeMinLength: 2 });
    const s = engine.state;

    const c1 = makeCard("PKT-N1", CardType.RELAY, "01", "02", 100, "P0");
    const c2 = makeCard("PKT-N2", CardType.RELAY, "02", "03", 100, "P0");
    for (const c of [c1, c2]) addToTableau(engine, c);

    (engine as any)._tryStartRoute(c1);
    (engine as any)._updateRoutes(c2);
    expect(s.tableau.routes[0].length).toBe(2);

    // "02" is interior (channelsInRoute[:-1]); "03" is exit and immune
    (engine as any)._applyNoise("02");

    expect(s.tableau.activeCards.has("PKT-N1")).toBe(false);
    expect(s.tableau.collidedCardIds.has("PKT-N1")).toBe(true);
    expect(s.tableau.routes[0].isValid).toBe(false);
  });

  it("does not affect routes shorter than routeMinLength", () => {
    const engine = makeEngine({ routeMinLength: 2 });
    const s = engine.state;

    const c1 = makeCard("PKT-SHORT", CardType.RELAY, "01", "03", 100, "P0");
    addToTableau(engine, c1);
    (engine as any)._tryStartRoute(c1);
    expect(s.tableau.routes[0].length).toBe(1);

    (engine as any)._applyNoise("03");

    // Card survives — route is length 1, below minLength
    expect(s.tableau.activeCards.has("PKT-SHORT")).toBe(true);
  });

  it("invalidated route is not carried over by _discardTableau", () => {
    const engine = makeEngine({ routeMinLength: 2 });
    const s = engine.state;

    const c1 = makeCard("REL-NC1", CardType.RELAY, "01", "02", 100, "P0");
    const c2 = makeCard("REL-NC2", CardType.RELAY, "02", "03", 100, "P0");
    for (const c of [c1, c2]) addToTableau(engine, c);

    (engine as any)._tryStartRoute(c1);
    (engine as any)._updateRoutes(c2);
    (engine as any)._applyNoise("02");
    expect(s.tableau.routes[0].isValid).toBe(false);

    engine._discardTableau();
    expect(s.tableau.routes).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// Filter node
// ---------------------------------------------------------------------------

describe("filter node", () => {
  it("can start a route", () => {
    const engine = makeEngine();
    const s = engine.state;

    const flt = makeCard("FLT-X1", CardType.FILTER, "01", "02", 100, "P0");
    addToTableau(engine, flt);
    (engine as any)._tryStartRoute(flt);
    expect(s.tableau.routes).toHaveLength(1);
    expect(s.tableau.routes[0].length).toBe(1);
  });

  it("shields the route when noise targets its input channel", () => {
    const engine = makeEngine({ routeMinLength: 2 });
    const s = engine.state;

    const c1 = makeCard("REL-X1", CardType.RELAY, "01", "02", 100, "P0");
    const flt = makeCard("FLT-X2", CardType.FILTER, "02", "03", 100, "P0");
    for (const c of [c1, flt]) addToTableau(engine, c);

    (engine as any)._tryStartRoute(c1);
    (engine as any)._updateRoutes(flt);
    expect(s.tableau.routes[0].length).toBe(2);

    (engine as any)._applyNoise("02"); // filter's input channel — absorbed
    expect(s.tableau.routes[0].isValid).toBe(true);
  });

  it("does not protect against noise on a different interior channel", () => {
    // Build a 3-hop route: REL(01→02) + FLT(02→03) + REL(03→01)
    // channelsInRoute=["02","03","01"]; interior=["02","03"]
    // FLT input="02" shields only "02"; noise on "03" still breaks the route
    const engine = makeEngine({ routeMinLength: 2 });
    const s = engine.state;

    const c1 = makeCard("REL-X2", CardType.RELAY, "01", "02", 100, "P0");
    const flt = makeCard("FLT-X3", CardType.FILTER, "02", "03", 100, "P0");
    const c3 = makeCard("REL-X3", CardType.RELAY, "03", "01", 100, "P0");
    for (const c of [c1, flt, c3]) addToTableau(engine, c);

    (engine as any)._tryStartRoute(c1);
    (engine as any)._updateRoutes(flt);
    (engine as any)._updateRoutes(c3);
    expect(s.tableau.routes[0].length).toBe(3);

    (engine as any)._applyNoise("03");
    expect(s.tableau.routes[0].isValid).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// End-of-round scoring
// ---------------------------------------------------------------------------

describe("end-of-round scoring", () => {
  it("credits exit node owner with exit node packet value", () => {
    const engine = makeEngine({ routeMinLength: 2 });
    const s = engine.state;

    const c1 = makeCard("PKT-SC1", CardType.RELAY, "01", "02", 100, "P0");
    const c2 = makeCard("PKT-SC2", CardType.RELAY, "02", "03", 300, "P1");
    for (const c of [c1, c2]) addToTableau(engine, c);

    (engine as any)._tryStartRoute(c1);
    (engine as any)._updateRoutes(c2);

    const route = s.tableau.routes[0];
    expect(route.exitNodeId).toBe("PKT-SC2");

    const [owner, score] = (engine as any)._scoreRoute(route);
    expect(score).toBe(300);
    expect(owner).toBe("P1");
  });

  it("scores open routes at end of round and credits correct player", () => {
    const engine = makeEngine({ routeMinLength: 2 });
    const s = engine.state;

    const c1 = makeCard("SC-P1", CardType.RELAY, "01", "02", 100, "P0");
    const c2 = makeCard("SC-P2", CardType.RELAY, "02", "03", 400, "P1");
    for (const c of [c1, c2]) addToTableau(engine, c);

    (engine as any)._tryStartRoute(c1);
    (engine as any)._updateRoutes(c2);

    s.roundNumber = 1;
    engine._endOfRoundScoring();

    const p1 = s.players.find(p => p.playerId === "P1")!;
    expect(p1.score).toBe(400);
  });
});

// ---------------------------------------------------------------------------
// Determinism
// ---------------------------------------------------------------------------

describe("determinism", () => {
  it("same seed produces identical final state", () => {
    const config: GameConfig = { ...FAST_CONFIG, playerCount: 3 };

    const run = (seed: number) => {
      const rng = makeMulberry32(seed);
      const deck = new DeckBuilder(config, rng).build();
      const policies = Array.from({ length: 3 }, () => new RandomLegal());
      const engine = new GameEngine(config, policies, deck, makeMulberry32(seed));
      engine.run();
      return engine.state.players.map(p => p.score);
    };

    expect(run(99)).toEqual(run(99));
  });

  it("different seeds can produce different results", () => {
    const config: GameConfig = { ...FAST_CONFIG, playerCount: 3 };
    const results = new Set<string>();
    for (let seed = 0; seed < 10; seed++) {
      const rng = makeMulberry32(seed);
      const deck = new DeckBuilder(config, rng).build();
      const policies = Array.from({ length: 3 }, () => new RandomLegal());
      const engine = new GameEngine(config, policies, deck, makeMulberry32(seed));
      engine.run();
      results.add(JSON.stringify(engine.state.players.map(p => p.score)));
    }
    expect(results.size).toBeGreaterThan(1);
  });
});

// ---------------------------------------------------------------------------
// Turn order rotation
// ---------------------------------------------------------------------------

describe("turn order rotation", () => {
  it("round winner becomes firstPlayerIndex when winnerGoesFirst=true", () => {
    const engine = makeEngine({ routeMinLength: 2, winnerGoesFirst: true, maxRounds: 2 });
    const s = engine.state;

    const c1 = makeCard("PKT-R1", CardType.RELAY, "01", "02", 100, "P0");
    const c2 = makeCard("PKT-R2", CardType.RELAY, "02", "03", 500, "P1");
    for (const c of [c1, c2]) addToTableau(engine, c);

    (engine as any)._tryStartRoute(c1);
    (engine as any)._updateRoutes(c2);

    expect(s.firstPlayerIndex).toBe(0);
    s.roundNumber = 1;
    engine._endOfRoundScoring();
    expect(s.firstPlayerIndex).toBe(1);
  });

  it("firstPlayerIndex unchanged when winnerGoesFirst=false", () => {
    const engine = makeEngine({ routeMinLength: 2, winnerGoesFirst: false, maxRounds: 2 });
    const s = engine.state;

    const c1 = makeCard("PKT-N1", CardType.RELAY, "01", "02", 100, "P0");
    const c2 = makeCard("PKT-N2", CardType.RELAY, "02", "03", 500, "P2");
    for (const c of [c1, c2]) addToTableau(engine, c);

    (engine as any)._tryStartRoute(c1);
    (engine as any)._updateRoutes(c2);

    s.roundNumber = 1;
    engine._endOfRoundScoring();
    expect(s.firstPlayerIndex).toBe(0);
  });

  it("tie leaves firstPlayerIndex unchanged", () => {
    const engine = makeEngine({ routeMinLength: 2, winnerGoesFirst: true, maxRounds: 2 });
    const s = engine.state;

    // Route 1: P1 exit, value 300
    const a1 = makeCard("PKT-T1", CardType.RELAY, "01", "02", 100, "P0");
    const a2 = makeCard("PKT-T2", CardType.RELAY, "02", "03", 300, "P1");
    // Route 2: P2 exit, value 300 (tie)
    const b1 = makeCard("PKT-T3", CardType.RELAY, "03", "01", 100, "P0");
    const b2 = makeCard("PKT-T4", CardType.RELAY, "01", "02", 300, "P2");
    for (const c of [a1, a2, b1, b2]) addToTableau(engine, c);

    (engine as any)._tryStartRoute(a1);
    (engine as any)._updateRoutes(a2);
    (engine as any)._tryStartRoute(b1);
    (engine as any)._updateRoutes(b2);

    s.roundNumber = 1;
    engine._endOfRoundScoring();
    expect(s.firstPlayerIndex).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// Carried routes
// ---------------------------------------------------------------------------

describe("carried routes", () => {
  it("stub below routeMinLength carries to next round", () => {
    const engine = makeEngine({ routeMinLength: 2 });
    const s = engine.state;

    const c1 = makeCard("REL-CR1", CardType.RELAY, "01", "02", 100, "P0");
    addToTableau(engine, c1);
    (engine as any)._tryStartRoute(c1);
    expect(s.tableau.routes[0].length).toBe(1);

    engine._discardTableau();
    expect(s.tableau.routes).toHaveLength(1);
    expect(s.tableau.routes[0].carried).toBe(true);
  });

  it("carried route can be extended in the next round", () => {
    const engine = makeEngine({ routeMinLength: 2 });
    const s = engine.state;

    const c1 = makeCard("REL-CR2", CardType.RELAY, "01", "02", 100, "P0");
    addToTableau(engine, c1);
    (engine as any)._tryStartRoute(c1);
    engine._discardTableau();

    const c2 = makeCard("REL-CR3", CardType.RELAY, "02", "03", 100, "P1");
    addToTableau(engine, c2);
    (engine as any)._updateRoutes(c2);
    expect(s.tableau.routes[0].length).toBe(2);
  });

  it("1 carried stub reduces seeds dealt in next round by 1", () => {
    const engine = makeEngine({ routeMinLength: 2, seedNodesPerRound: 2, maxRounds: 2 });
    const s = engine.state;
    s.roundNumber = 0;

    const c1 = makeCard("REL-CR4", CardType.RELAY, "01", "02", 100, "P0");
    addToTableau(engine, c1);
    (engine as any)._tryStartRoute(c1);
    engine._discardTableau();
    expect(s.tableau.routes).toHaveLength(1);

    s.roundNumber = 1;
    engine._beginRound();
    // 1 carried stub already open; needed = max(0, 2 - 1) = 1 new seed → 2 routes total
    expect(s.tableau.routes).toHaveLength(2);
  });
});

// ---------------------------------------------------------------------------
// Route cap
// ---------------------------------------------------------------------------

describe("route cap", () => {
  it("blocks a new route when cap is full", () => {
    const engine = makeEngine({}, 2); // playerCount=2 → maxOpenRoutes=2
    const s = engine.state;

    const c1 = makeCard("REL-CAP1", CardType.RELAY, "01", "02", 100, "P0");
    const c2 = makeCard("REL-CAP2", CardType.RELAY, "03", "01", 100, "P0");
    for (const c of [c1, c2]) addToTableau(engine, c);

    (engine as any)._tryStartRoute(c1);
    (engine as any)._tryStartRoute(c2);
    expect(s.tableau.routes).toHaveLength(2);

    const c3 = makeCard("REL-CAP3", CardType.RELAY, "03", "02", 100, "P1");
    addToTableau(engine, c3);
    (engine as any)._tryStartRoute(c3);
    expect(s.tableau.routes).toHaveLength(2); // still capped
  });

  it("frees a slot when a route closes", () => {
    const engine = makeEngine({ routeMinLength: 2 }, 2);
    const s = engine.state;

    const c1 = makeCard("REL-SL1", CardType.RELAY, "01", "02", 100, "P0");
    const c2 = makeCard("REL-SL2", CardType.RELAY, "03", "01", 100, "P0");
    for (const c of [c1, c2]) addToTableau(engine, c);

    (engine as any)._tryStartRoute(c1);
    (engine as any)._tryStartRoute(c2);

    // Extend route 0 to length 2
    const cExt = makeCard("REL-SL3", CardType.RELAY, "02", "03", 100, "P0");
    addToTableau(engine, cExt);
    (engine as any)._updateRoutes(cExt);

    const route0Id = s.tableau.routes[0].routeId;

    // Close with a targeted terminal
    const term = makeCard("TERM-SL1", CardType.TERMINAL, "ANY", "TERM", 400, "P1", [
      { key: "target_route_id", value: route0Id },
    ]);
    addToTableau(engine, term);
    (engine as any)._updateRoutes(term);
    expect(routeIsOpen(s.tableau.routes[0])).toBe(false);

    // New route should now be startable
    const cNew = makeCard("REL-SL4", CardType.RELAY, "02", "03", 100, "P1");
    addToTableau(engine, cNew);
    (engine as any)._tryStartRoute(cNew);
    const openRoutes = s.tableau.routes.filter(routeIsOpen);
    expect(openRoutes).toHaveLength(2);
  });
});

// ---------------------------------------------------------------------------
// Round / turn structure
// ---------------------------------------------------------------------------

describe("round structure", () => {
  it("refills hands to startingHandSize at _advanceRound", () => {
    const engine = makeEngine({ startingHandSize: 4 });
    const s = engine.state;

    s.players[0].hand = [];
    expect(s.players[0].hand).toHaveLength(0);

    engine._advanceRound();
    expect(s.players[0].hand).toHaveLength(4);
  });

  it("reshuffles discard into deck when deck is empty", () => {
    const engine = makeEngine();
    const s = engine.state;

    s.discard.push(...s.deck);
    s.deck = [];
    expect(s.deck).toHaveLength(0);

    const drawn = (engine as any)._drawN(s, 1);
    expect(drawn).toHaveLength(1);
  });
});

// ---------------------------------------------------------------------------
// Win condition
// ---------------------------------------------------------------------------

describe("win condition", () => {
  it("terminal flag is set when a player reaches scoreToWin", () => {
    const config: GameConfig = { ...FAST_CONFIG, scoreToWin: 1, playerCount: 3 };
    const rng = makeMulberry32(0);
    const deck = new DeckBuilder(config, rng).build();
    const policies = Array.from({ length: 3 }, () => new RandomLegal());
    const engine = new GameEngine(config, policies, deck, makeMulberry32(0));
    engine.run();
    expect(engine.state._terminal).toBe(true);
    expect(engine.state.players.some(p => p.score >= 1)).toBe(true);
  });

  it("game ends when maxRounds is reached", () => {
    const config: GameConfig = { ...FAST_CONFIG, maxRounds: 1, scoreToWin: 999_999, playerCount: 3 };
    const rng = makeMulberry32(7);
    const deck = new DeckBuilder(config, rng).build();
    const policies = Array.from({ length: 3 }, () => new RandomLegal());
    const engine = new GameEngine(config, policies, deck, makeMulberry32(7));
    engine.run();
    expect(engine.state._terminal).toBe(true);
    expect(engine.state.roundNumber).toBe(1);
  });
});
