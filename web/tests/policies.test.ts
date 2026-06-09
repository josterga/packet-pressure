import { describe, it, expect } from "vitest";
import { GameEngine } from "../src/engine";
import { DeckBuilder } from "../src/deck";
import { FAST_CONFIG } from "../src/config";
import {
  Card,
  CardType,
  GameConfig,
  makeMulberry32,
  registerCard,
} from "../src/models";
import {
  DenialCollision,
  GreedyExitNode,
  RandomLegal,
  RouteBuilder,
  makeDefaultPolicies,
} from "../src/policies";

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

function makeEngineAndState(nPolicies = 3, seed = 0) {
  const config: GameConfig = { ...FAST_CONFIG, playerCount: nPolicies };
  const rng = makeMulberry32(seed);
  const deck = new DeckBuilder(config, rng).build();
  const policies = Array.from({ length: nPolicies }, () => new RandomLegal());
  const engine = new GameEngine(config, policies, deck, makeMulberry32(seed));
  return { state: engine.state, engine };
}

function addToTableau(engine: GameEngine, card: Card): void {
  const s = engine.state;
  registerCard(s, card);
  s.tableau.activeCards.set(card.cardId, card);
}

// ---------------------------------------------------------------------------
// legalPlays (base PlayerPolicy)
// ---------------------------------------------------------------------------

describe("legalPlays", () => {
  it("only returns cards that are in the player's hand", () => {
    const { state } = makeEngineAndState();
    const policy = new RandomLegal();
    const player = state.players[0];
    const plays = policy.legalPlays(state, player);
    const handIds = new Set(player.hand.map(c => c.cardId));
    for (const [card] of plays) {
      expect(handIds.has(card.cardId)).toBe(true);
    }
  });

  it("does not return cards already on the tableau", () => {
    const { state } = makeEngineAndState();
    const policy = new RandomLegal();
    const player = state.players[0];

    if (player.hand.length > 0) {
      const card = player.hand[0];
      state.tableau.activeCards.set(card.cardId, card);
    }

    const plays = policy.legalPlays(state, player);
    const tableauIds = new Set(state.tableau.activeCards.keys());
    for (const [card] of plays) {
      expect(tableauIds.has(card.cardId)).toBe(false);
    }
  });

  it("noise with no scoring routes generates no plays", () => {
    const { state } = makeEngineAndState();
    const policy = new RandomLegal();
    const player = state.players[0];

    const noise = makeCard("NOISE-TEST", CardType.NOISE, null, null, 0);
    registerCard(state, noise);
    player.hand.push(noise);

    const plays = policy.legalPlays(state, player);
    const noisePlays = plays.filter(([c]) => c.cardId === "NOISE-TEST");
    expect(noisePlays).toHaveLength(0);
  });

  it("noise is legal when a scoring route has the targeted channel as an interior hop", () => {
    const { state, engine } = makeEngineAndState();
    const policy = new RandomLegal();
    const player = state.players[0];

    // noise card targets CH02
    const noise = makeCard("NOISE-TEST", CardType.NOISE, null, "02", 0);
    registerCard(state, noise);
    player.hand.push(noise);

    // Build 2-card route: 01→02→03; channelsInRoute=["02","03"]; interior=["02"]
    const c1 = makeCard("R1", CardType.RELAY, "01", "02", 100, "P1");
    const c2 = makeCard("R2", CardType.RELAY, "02", "03", 100, "P1");
    for (const c of [c1, c2]) addToTableau(engine, c);
    (engine as any)._tryStartRoute(c1);
    (engine as any)._updateRoutes(c2);
    expect(state.tableau.routes[0].length).toBe(2);

    const plays = policy.legalPlays(state, player);
    const noisePlays = plays.filter(([c]) => c.cardId === "NOISE-TEST");
    expect(noisePlays.length).toBeGreaterThan(0);
  });

  it("terminal cannot target a stub shorter than routeMinLength", () => {
    const { state, engine } = makeEngineAndState();
    const policy = new RandomLegal();
    const player = state.players[0];

    const term = makeCard("TERM-STUB", CardType.TERMINAL, "ANY", "TERM", 400);
    registerCard(state, term);
    player.hand.push(term);

    // 1-node stub (length < routeMinLength=2)
    const stub = makeCard("R-STUB", CardType.RELAY, "01", "02", 100, "P0");
    addToTableau(engine, stub);
    (engine as any)._tryStartRoute(stub);
    expect(state.tableau.routes[0].length).toBe(1);

    const plays = policy.legalPlays(state, player);
    const termPlays = plays.filter(([c]) => c.cardId === "TERM-STUB");
    expect(termPlays).toHaveLength(0);
  });

  it("returns a pass when no legal play exists", () => {
    // Fill cap (seedNodesPerRound=2) with two stubs, give player a relay that
    // matches neither tail ("01" and "03"); no terminal/noise plays either.
    const { state, engine } = makeEngineAndState();
    const policy = new RandomLegal();
    const player = state.players[0];

    player.hand = [];
    const blocker = makeCard("REL-PASS", CardType.RELAY, "02", "01", 100);
    registerCard(state, blocker);
    player.hand.push(blocker);

    // Two stubs with tails "01" and "03" (fills seedNodesPerRound=2 cap)
    const pairs: [string, string][] = [["03", "01"], ["01", "03"]];
    for (const [i, [inCh, outCh]] of pairs.entries()) {
      const c = makeCard(`SEED-P${i}`, CardType.RELAY, inCh, outCh, 100, "P0");
      addToTableau(engine, c);
      (engine as any)._tryStartRoute(c);
    }

    const plays = policy.legalPlays(state, player);
    expect(plays).toHaveLength(1);
    const [, ctx] = plays[0];
    expect(ctx.passTurn).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// GreedyExitNode
// ---------------------------------------------------------------------------

describe("GreedyExitNode", () => {
  it("prefers higher-value terminal over lower-value terminal", () => {
    const { state, engine } = makeEngineAndState(3, 7);
    const policy = new GreedyExitNode();
    const player = state.players[0];
    player.hand = [];

    // 2-card route (length=2 == routeMinLength)
    const c1 = makeCard("G-R1", CardType.RELAY, "01", "02", 100, "P1");
    const c2 = makeCard("G-R2", CardType.RELAY, "02", "03", 100, "P1");
    for (const c of [c1, c2]) addToTableau(engine, c);
    (engine as any)._tryStartRoute(c1);
    (engine as any)._updateRoutes(c2);
    expect(state.tableau.routes[0].length).toBe(2);

    const lowTerm = makeCard("TERM-LOW", CardType.TERMINAL, "ANY", "TERM", 100);
    const highTerm = makeCard("TERM-HIGH", CardType.TERMINAL, "ANY", "TERM", 999);
    for (const c of [lowTerm, highTerm]) {
      registerCard(state, c);
      player.hand.push(c);
    }

    const [chosen] = policy.choosePlay(state, player);
    expect(chosen.cardId).toBe("TERM-HIGH");
  });
});

// ---------------------------------------------------------------------------
// RouteBuilder
// ---------------------------------------------------------------------------

describe("RouteBuilder", () => {
  it("extends an existing open route over starting a new one", () => {
    const { state, engine } = makeEngineAndState(3, 5);
    const policy = new RouteBuilder();
    const player = state.players[0];
    player.hand = [];

    // Open route ending on channel "02"
    const seed = makeCard("RB-SEED", CardType.RELAY, "01", "02", 100, "P0");
    addToTableau(engine, seed);
    (engine as any)._tryStartRoute(seed);

    // Matching card (input "02") and non-matching card (input "03")
    const match = makeCard("RB-MATCH", CardType.RELAY, "02", "03", 100);
    const noMatch = makeCard("RB-NOMATCH", CardType.RELAY, "03", "01", 100);
    for (const c of [match, noMatch]) {
      registerCard(state, c);
      player.hand.push(c);
    }

    const [chosen, ctx] = policy.choosePlay(state, player);
    expect(chosen.cardId).toBe("RB-MATCH");
    expect(ctx.targetRouteId).not.toBeNull();
  });
});

// ---------------------------------------------------------------------------
// DenialCollision
// ---------------------------------------------------------------------------

describe("DenialCollision", () => {
  it("steals a high-value opponent route with a terminal", () => {
    // DenialCollision prefers a terminal steal on a 200-value opponent route
    // over a 999-value greedy relay play on a separate route.
    const { state, engine } = makeEngineAndState(3, 3);
    const policy = new DenialCollision();
    const player = state.players[0];
    player.hand = [];

    // Opponent route (P1): 2 hops, exit value=200 — triggers denial (≥50 threshold)
    const c1 = makeCard("DC-R1", CardType.RELAY, "01", "02", 100, "P1");
    const c2 = makeCard("DC-R2", CardType.RELAY, "02", "03", 200, "P1");
    for (const c of [c1, c2]) addToTableau(engine, c);
    (engine as any)._tryStartRoute(c1);
    (engine as any)._updateRoutes(c2);
    expect(state.tableau.routes[0].length).toBe(2);

    // Unrelated stub so the relay has an extendable target
    const seedStub = makeCard("DC-SEED", CardType.RELAY, "01", "03", 50, "P0");
    addToTableau(engine, seedStub);
    (engine as any)._tryStartRoute(seedStub);

    // Low terminal (steals opponent route) vs high relay (extends seed stub)
    const term = makeCard("DC-TERM", CardType.TERMINAL, "ANY", "TERM", 100);
    const relay = makeCard("DC-RELAY", CardType.RELAY, "03", "01", 999);
    for (const c of [term, relay]) {
      registerCard(state, c);
      player.hand.push(c);
    }

    const [chosen] = policy.choosePlay(state, player);
    expect(chosen.cardId).toBe("DC-TERM");
  });
});

// ---------------------------------------------------------------------------
// Full game smoke tests
// ---------------------------------------------------------------------------

describe("full game smoke tests", () => {
  it.each([
    ["RandomLegal + RandomLegal + RandomLegal", [new RandomLegal(), new RandomLegal(), new RandomLegal()]],
    ["GreedyExitNode + RandomLegal + RandomLegal", [new GreedyExitNode(), new RandomLegal(), new RandomLegal()]],
    ["RouteBuilder + DenialCollision + RandomLegal", [new RouteBuilder(), new DenialCollision(), new RandomLegal()]],
    ["all 4 policies", [new GreedyExitNode(), new DenialCollision(), new RouteBuilder(), new RandomLegal()]],
  ])("%s completes without throwing", (_label, policies) => {
    const config: GameConfig = { ...FAST_CONFIG, playerCount: policies.length };
    const rng = makeMulberry32(42);
    const deck = new DeckBuilder(config, rng).build();
    const engine = new GameEngine(config, policies, deck, makeMulberry32(42));
    expect(() => engine.run()).not.toThrow();
    expect(engine.state._terminal).toBe(true);
  });
});
