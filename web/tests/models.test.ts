import { describe, it, expect } from "vitest";
import {
  CardType,
  TerminationReason,
  RouteState,
  TableauState,
  cardSpecial,
  channelColor,
  channelIndex,
  makeMulberry32,
  maxOpenRoutes,
  nextRouteId,
  routeIsOpen,
  routeLastOutputChannel,
  routeMaxHops,
  withOwner,
} from "../src/models";
import { DeckBuilder } from "../src/deck";
import { FAST_CONFIG } from "../src/config";

// ---------------------------------------------------------------------------
// GameConfig helpers
// ---------------------------------------------------------------------------

describe("routeMaxHops", () => {
  it("returns channels.length", () => {
    expect(routeMaxHops(FAST_CONFIG)).toBe(FAST_CONFIG.channels.length);
  });
});

describe("maxOpenRoutes", () => {
  it("returns playerCount", () => {
    expect(maxOpenRoutes(FAST_CONFIG)).toBe(FAST_CONFIG.playerCount);
  });
});

describe("channelIndex / channelColor", () => {
  it("returns correct index for known channel", () => {
    expect(channelIndex(FAST_CONFIG, "01")).toBe(0);
    expect(channelIndex(FAST_CONFIG, "02")).toBe(1);
    expect(channelIndex(FAST_CONFIG, "03")).toBe(2);
  });

  it("returns null for unknown channel", () => {
    expect(channelIndex(FAST_CONFIG, "99")).toBeNull();
  });

  it("returns correct color token", () => {
    expect(channelColor(FAST_CONFIG, "01")).toBe("teal");
    expect(channelColor(FAST_CONFIG, "02")).toBe("orange");
    expect(channelColor(FAST_CONFIG, "03")).toBe("purple");
  });

  it("returns null for unknown channel color", () => {
    expect(channelColor(FAST_CONFIG, "99")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Card helpers
// ---------------------------------------------------------------------------

describe("withOwner", () => {
  it("creates a new card with the given ownerId", () => {
    const card = {
      cardId: "PKT-0001",
      cardType: CardType.RELAY,
      inputChannel: "01",
      outputChannel: "02",
      packetValue: 200,
      color: "red",
      ownerId: null,
      specialProperties: [],
    };
    const owned = withOwner(card, "P0");
    expect(owned.ownerId).toBe("P0");
    expect(card.ownerId).toBeNull();
  });
});

describe("cardSpecial", () => {
  it("returns the value for a known key", () => {
    const card = {
      cardId: "AMP-0001",
      cardType: CardType.AMPLIFIER,
      inputChannel: "01",
      outputChannel: "02",
      packetValue: 300,
      color: "blue",
      ownerId: null,
      specialProperties: [{ key: "multiplier", value: 2 }],
    };
    expect(cardSpecial(card, "multiplier")).toBe(2);
  });

  it("returns the default for an unknown key", () => {
    const card = {
      cardId: "AMP-0001",
      cardType: CardType.AMPLIFIER,
      inputChannel: "01",
      outputChannel: "02",
      packetValue: 300,
      color: "blue",
      ownerId: null,
      specialProperties: [],
    };
    expect(cardSpecial(card, "nonexistent", 99)).toBe(99);
  });
});

describe("terminal card channels", () => {
  it("has ANY input and TERM output", () => {
    const card = {
      cardId: "TERM-0001",
      cardType: CardType.TERMINAL,
      inputChannel: "ANY",
      outputChannel: "TERM",
      packetValue: 400,
      color: "green",
      ownerId: null,
      specialProperties: [],
    };
    expect(card.inputChannel).toBe("ANY");
    expect(card.outputChannel).toBe("TERM");
  });
});

// ---------------------------------------------------------------------------
// RouteState helpers
// ---------------------------------------------------------------------------

describe("routeLastOutputChannel", () => {
  it("returns last channel when populated", () => {
    const route: RouteState = {
      routeId: "R-0001",
      cardIds: ["C1", "C2"],
      ownerSequence: ["P0", "P1"],
      channelsInRoute: ["01", "02"],
      entryChannel: "01",
      isValid: true,
      isScoringCandidate: false,
      exitNodeId: "C2",
      length: 2,
      terminationReason: TerminationReason.ACTIVE,
      carried: false,
    };
    expect(routeLastOutputChannel(route)).toBe("02");
  });

  it("returns null when channelsInRoute is empty", () => {
    const route: RouteState = {
      routeId: "R-0001",
      cardIds: [],
      ownerSequence: [],
      channelsInRoute: [],
      entryChannel: null,
      isValid: true,
      isScoringCandidate: false,
      exitNodeId: null,
      length: 0,
      terminationReason: TerminationReason.ACTIVE,
      carried: false,
    };
    expect(routeLastOutputChannel(route)).toBeNull();
  });
});

describe("routeIsOpen", () => {
  it("returns true for an active valid route", () => {
    const route: RouteState = {
      routeId: "R-0001",
      cardIds: ["C1"],
      ownerSequence: ["P0"],
      channelsInRoute: ["01"],
      entryChannel: "01",
      isValid: true,
      isScoringCandidate: false,
      exitNodeId: "C1",
      length: 1,
      terminationReason: TerminationReason.ACTIVE,
      carried: false,
    };
    expect(routeIsOpen(route)).toBe(true);
  });

  it("returns false when terminated by TERMINAL", () => {
    const route: RouteState = {
      routeId: "R-0001",
      cardIds: ["C1"],
      ownerSequence: ["P0"],
      channelsInRoute: ["01"],
      entryChannel: "01",
      isValid: true,
      isScoringCandidate: true,
      exitNodeId: "C1",
      length: 1,
      terminationReason: TerminationReason.TERMINAL,
      carried: false,
    };
    expect(routeIsOpen(route)).toBe(false);
  });

  it("returns false when isValid is false", () => {
    const route: RouteState = {
      routeId: "R-0001",
      cardIds: ["C1"],
      ownerSequence: ["P0"],
      channelsInRoute: ["01"],
      entryChannel: "01",
      isValid: false,
      isScoringCandidate: false,
      exitNodeId: "C1",
      length: 1,
      terminationReason: TerminationReason.ACTIVE,
      carried: false,
    };
    expect(routeIsOpen(route)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// TableauState
// ---------------------------------------------------------------------------

describe("nextRouteId", () => {
  it("increments sequentially from R-0001", () => {
    const tableau: TableauState = {
      activeCards: new Map(),
      seedNodes: [],
      routes: [],
      noisyChannels: new Set(),
      collidedCardIds: new Set(),
      _routeCounter: 0,
    };
    expect(nextRouteId(tableau)).toBe("R-0001");
    expect(nextRouteId(tableau)).toBe("R-0002");
    expect(nextRouteId(tableau)).toBe("R-0003");
  });
});

// ---------------------------------------------------------------------------
// DeckBuilder
// ---------------------------------------------------------------------------

describe("DeckBuilder", () => {
  it("builds relay cards with REL- prefix", () => {
    const rng = makeMulberry32(0);
    const deck = new DeckBuilder(FAST_CONFIG, rng).build();
    const relayIds = deck.filter(c => c.cardType === CardType.RELAY).map(c => c.cardId);
    expect(relayIds.length).toBeGreaterThan(0);
    expect(relayIds.every(id => id.startsWith("REL-"))).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// makeMulberry32
// ---------------------------------------------------------------------------

describe("makeMulberry32", () => {
  it("is deterministic for the same seed", () => {
    const r1 = makeMulberry32(12345);
    const r2 = makeMulberry32(12345);
    const seq1 = [r1.next(), r1.next(), r1.next()];
    const seq2 = [r2.next(), r2.next(), r2.next()];
    expect(seq1).toEqual(seq2);
  });

  it("produces values in [0, 1)", () => {
    const rng = makeMulberry32(1);
    for (let i = 0; i < 20; i++) {
      const v = rng.next();
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThan(1);
    }
  });
});
