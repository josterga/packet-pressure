import { Card, CardType, GameConfig, Rng, specialDistDict } from "./models";

export class DeckBuilder {
  constructor(private cfg: GameConfig, private rng: Rng) {}

  build(): Card[] {
    const dist = specialDistDict(this.cfg);
    const nTerminal = Math.floor(this.cfg.deckSize * (dist.get("terminal") ?? 0));
    const nAmplifier = Math.floor(this.cfg.deckSize * (dist.get("amplifier") ?? 0));
    const nNoise = Math.floor(this.cfg.deckSize * (dist.get("noise") ?? 0));
    const nFilter = Math.floor(this.cfg.deckSize * (dist.get("filter") ?? 0));
    const nSpecial = nTerminal + nAmplifier + nNoise + nFilter;
    const nRelay = Math.max(0, this.cfg.deckSize - nSpecial);

    let idx = 0;
    const cards: Card[] = [];

    const relays = this._buildRelayNodes(nRelay, idx);
    cards.push(...relays); idx += relays.length;

    const terms = this._buildTerminalNodes(nTerminal, idx);
    cards.push(...terms); idx += terms.length;

    const amps = this._buildAmplifierNodes(nAmplifier, idx);
    cards.push(...amps); idx += amps.length;

    const noise = this._buildNoiseNodes(nNoise, idx);
    cards.push(...noise); idx += noise.length;

    const filters = this._buildFilterNodes(nFilter, idx);
    cards.push(...filters);

    this.rng.shuffle(cards);
    return cards;
  }

  private _allChannelPairs(): [string, string][] {
    const ch = this.cfg.channels;
    const pairs: [string, string][] = [];
    for (const i of ch) for (const o of ch) if (i !== o) pairs.push([i, o]);
    return pairs;
  }

  private _buildRelayNodes(count: number, startId: number): Card[] {
    const { channels, colors, packetValues } = this.cfg;
    const pairs: [string, string][] = channels.flatMap(i =>
      channels.filter(o => o !== i).map(o => [i, o] as [string, string])
    );
    const weights = pairs.map(() => 1);

    const cards: Card[] = [];
    for (let i = 0; i < count; i++) {
      const [inCh, outCh] = this.rng.weightedChoice(pairs, weights);
      const pv = this.rng.choice(packetValues);
      const color = this.rng.choice(colors);
      cards.push({
        cardId: `REL-${String(startId + i).padStart(4, "0")}`,
        cardType: CardType.RELAY,
        inputChannel: inCh,
        outputChannel: outCh,
        packetValue: pv,
        color,
        ownerId: null,
        specialProperties: [],
      });
    }
    return cards;
  }

  private _buildTerminalNodes(count: number, startId: number): Card[] {
    const { colors, terminalPacketValues } = this.cfg;
    const cards: Card[] = [];
    for (let i = 0; i < count; i++) {
      const pv = this.rng.choice(terminalPacketValues);
      const color = this.rng.choice(colors);
      cards.push({
        cardId: `TERM-${String(startId + i).padStart(4, "0")}`,
        cardType: CardType.TERMINAL,
        inputChannel: "ANY",
        outputChannel: "TERM",
        packetValue: pv,
        color,
        ownerId: null,
        specialProperties: [],
      });
    }
    return cards;
  }

  private _buildAmplifierNodes(count: number, startId: number): Card[] {
    const { channels, colors, packetValues, amplifierMultiplier } = this.cfg;
    const cards: Card[] = [];
    for (let i = 0; i < count; i++) {
      const inCh = this.rng.choice(channels);
      const outOptions = channels.filter(c => c !== inCh);
      const outCh = outOptions.length > 0 ? this.rng.choice(outOptions) : inCh;
      const pv = this.rng.choice(packetValues);
      const color = this.rng.choice(colors);
      cards.push({
        cardId: `AMP-${String(startId + i).padStart(4, "0")}`,
        cardType: CardType.AMPLIFIER,
        inputChannel: inCh,
        outputChannel: outCh,
        packetValue: pv,
        color,
        ownerId: null,
        specialProperties: [{ key: "multiplier", value: amplifierMultiplier }],
      });
    }
    return cards;
  }

  private _buildNoiseNodes(count: number, startId: number): Card[] {
    const { channels, colors } = this.cfg;
    const cards: Card[] = [];
    for (let i = 0; i < count; i++) {
      const targetCh = this.rng.choice(channels);
      const color = this.rng.choice(colors);
      cards.push({
        cardId: `NOISE-${String(startId + i).padStart(4, "0")}`,
        cardType: CardType.NOISE,
        inputChannel: null,
        outputChannel: targetCh,
        packetValue: 0,
        color,
        ownerId: null,
        specialProperties: [],
      });
    }
    return cards;
  }

  private _buildFilterNodes(count: number, startId: number): Card[] {
    const { channels, colors, packetValues } = this.cfg;
    const cards: Card[] = [];
    for (let i = 0; i < count; i++) {
      const inCh = this.rng.choice(channels);
      const outOptions = channels.filter(c => c !== inCh);
      const outCh = outOptions.length > 0 ? this.rng.choice(outOptions) : inCh;
      const pv = this.rng.choice(packetValues);
      const color = this.rng.choice(colors);
      cards.push({
        cardId: `FLT-${String(startId + i).padStart(4, "0")}`,
        cardType: CardType.FILTER,
        inputChannel: inCh,
        outputChannel: outCh,
        packetValue: pv,
        color,
        ownerId: null,
        specialProperties: [],
      });
    }
    return cards;
  }
}
