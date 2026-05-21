import {
  Card,
  CardType,
  GameConfig,
  GameState,
  RouteState,
  TerminationReason,
  cardSpecial,
  channelColor,
  lookupCard,
  routeIsOpen,
  routeLastOutputChannel,
} from "./models";

// ---------------------------------------------------------------------------
// Channel helpers
// ---------------------------------------------------------------------------

export function channelCssClass(ch: string | null, cfg: GameConfig): string {
  if (!ch || ch === "ANY" || ch === "TERM") return "ch-neutral";
  const color = channelColor(cfg, ch);
  return color ? `ch-${color}` : "ch-neutral";
}

export function channelLabel(ch: string | null, cfg: GameConfig): string {
  if (ch === null) return "--";
  if (ch === "ANY") return "ANY";
  if (ch === "TERM") return "END";
  return `CH${ch}`;
}

function chSpan(ch: string | null, cfg: GameConfig): string {
  const cls = channelCssClass(ch, cfg);
  const label = channelLabel(ch, cfg);
  return `<span class="ch ${cls}">${label}</span>`;
}

// ---------------------------------------------------------------------------
// Card rendering
// ---------------------------------------------------------------------------

const CARD_TYPE_SYMBOLS: Record<CardType, string> = {
  [CardType.RELAY]: "⇒",
  [CardType.TERMINAL]: "⊣",
  [CardType.AMPLIFIER]: "⊕",
  [CardType.NOISE]: "⚠",
  [CardType.FILTER]: "⊘",
};

export function renderCard(card: Card, cfg: GameConfig, opts: { dim?: boolean; label?: string } = {}): string {
  const inCls = channelCssClass(card.inputChannel, cfg);
  const outCls = channelCssClass(card.outputChannel, cfg);
  const sym = CARD_TYPE_SYMBOLS[card.cardType];
  const inLabel = channelLabel(card.inputChannel, cfg);
  const outLabel = channelLabel(card.outputChannel, cfg);

  let typeLine = "";
  if (card.cardType === CardType.AMPLIFIER) {
    const mult = cardSpecial(card, "multiplier", cfg.amplifierMultiplier) as number;
    typeLine = `<div class="card-type">${sym} AMP ×${mult}</div>`;
  } else if (card.cardType === CardType.TERMINAL) {
    typeLine = `<div class="card-type">${sym} TERMINAL</div>`;
  } else if (card.cardType === CardType.NOISE) {
    typeLine = `<div class="card-type">${sym} NOISE <span class="ch ${channelCssClass(card.outputChannel, cfg)}">${channelLabel(card.outputChannel, cfg)}</span></div>`;
  } else if (card.cardType === CardType.FILTER) {
    typeLine = `<div class="card-type">${sym} FILTER</div>`;
  } else {
    typeLine = `<div class="card-type">${sym} RELAY</div>`;
  }

  const labelHtml = opts.label !== undefined
    ? `<div class="card-label">[${opts.label}]</div>`
    : "";

  return `
    <div class="card ${opts.dim ? "card-dim" : ""}" data-card-id="${card.cardId}">
      ${labelHtml}
      <div class="card-channels">
        <span class="ch ${inCls}">${inLabel}</span>
        <span class="card-arrow">→</span>
        <span class="ch ${outCls}">${outLabel}</span>
      </div>
      <div class="card-divider"></div>
      ${typeLine}
      <div class="card-pkt">PKT ${card.packetValue}</div>
      <div class="card-divider"></div>
      <div class="card-footer">
        <span class="card-owner">${card.ownerId ?? ""}</span>
        <span class="card-id">${card.cardId}</span>
      </div>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Route rendering
// ---------------------------------------------------------------------------

function routeChannelChain(route: RouteState, cfg: GameConfig): string {
  const parts: string[] = [];
  if (route.entryChannel) parts.push(chSpan(route.entryChannel, cfg));
  for (const ch of route.channelsInRoute) parts.push(chSpan(ch, cfg));
  if (route.terminationReason !== TerminationReason.ACTIVE) {
    parts.push(`<span class="dim">END</span>`);
  }
  return parts.join(" → ");
}

export function renderRoute(route: RouteState, state: GameState, opts: { dim?: boolean } = {}): string {
  const cfg = state.config;
  const scoring = route.isScoringCandidate ? " ✓" : "";
  const chain = routeChannelChain(route, cfg);
  const cls = opts.dim ? "route dim" : "route";

  const cards = route.cardIds
    .map(cid => lookupCard(state, cid))
    .filter((c): c is Card => c !== null);

  const cardsHtml = cards.map(c => renderCard(c, cfg, { dim: opts.dim })).join("");

  return `
    <div class="${cls}">
      <div class="route-header">
        <span class="route-id">${route.routeId}</span>
        <span class="route-meta">len ${route.length}${scoring}</span>
        <span class="route-chain">${chain}</span>
      </div>
      <div class="cards-row">${cardsHtml}</div>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Tableau rendering
// ---------------------------------------------------------------------------

export function renderTableau(state: GameState): string {
  const active = state.tableau.routes.filter(
    r => r.isValid && r.terminationReason === TerminationReason.ACTIVE
  );
  const carried = active.filter(r => r.carried);
  const live = active.filter(r => !r.carried);
  const done = state.tableau.routes.filter(
    r => r.isValid && r.terminationReason !== TerminationReason.ACTIVE
  );
  const broken = state.tableau.routes.filter(r => !r.isValid);

  let html = "";

  if (carried.length > 0) {
    html += `<div class="section-label dim">── CARRIED ──</div>`;
    html += carried.map(r => renderRoute(r, state)).join("");
  }

  html += live.map(r => renderRoute(r, state)).join("");

  if (done.length > 0) {
    html += `<div class="section-label dim">── DONE ──</div>`;
    html += done.map(r => renderRoute(r, state, { dim: true })).join("");
  }

  if (broken.length > 0) {
    html += `<div class="section-label dim">── BROKEN ──</div>`;
    html += broken.map(r => renderRoute(r, state, { dim: true })).join("");
  }

  if (!html) {
    html = `<div class="dim empty-tableau">(tableau empty)</div>`;
  }

  return html;
}

// ---------------------------------------------------------------------------
// Scores + header
// ---------------------------------------------------------------------------

export function renderScores(state: GameState, humanIndex: number): string {
  return state.players.map((p, i) => {
    const label = i === humanIndex ? "you" : p.playerId;
    const cls = i === humanIndex ? "score-you" : "score-ai";
    return `<span class="${cls}"><b>${label}</b> ${p.score}</span>`;
  }).join('<span class="score-sep">│</span>');
}

export function renderRoundHeader(state: GameState): string {
  const cfg = state.config;
  const totalTurns = cfg.turnsPerPlayerPerRound * cfg.playerCount;
  const displayTurn = Math.min(state.turnNumber + 1, totalTurns);
  const turnInfo = cfg.turnsPerPlayerPerRound > 1 ? ` · Turn ${displayTurn} of ${totalTurns}` : "";
  return `PACKET PRESSURE · Round ${state.roundNumber} of ${cfg.maxRounds}${turnInfo} · Score to win: ${cfg.scoreToWin}`;
}

// ---------------------------------------------------------------------------
// Event log
// ---------------------------------------------------------------------------

const SKIP_EVENTS = new Set([
  "ROUND_START", "ROUND_END", "CARD_DRAWN", "ROUTE_STARTED", "GAME_OVER",
]);

export function renderEvent(event: Record<string, unknown>, state: GameState): string | null {
  const etype = event.event as string;
  if (SKIP_EVENTS.has(etype)) return null;

  const player = event.player as string ?? "?";
  const cfg = state.config;

  if (etype === "CARD_PLAYED") {
    const card = lookupCard(state, event.card_id as string);
    if (!card) return null;
    const ct = event.card_type as string;
    if (ct === "noise") {
      return `${player} played ${card.cardId} NOISE ${channelLabel(card.outputChannel, cfg)}`;
    }
    return `${player} played ${card.cardId} ${channelLabel(card.inputChannel, cfg)}→${channelLabel(card.outputChannel, cfg)} PKT ${card.packetValue}`;
  }

  if (etype === "ROUTE_EXTENDED") {
    return `${player} extended ${event.route_id} (len ${event.length})`;
  }

  if (etype === "ROUTE_TERMINATED") {
    const scoring = event.scoring ? " ✓ scoring" : "";
    return `${player} terminated ${event.route_id} [${event.reason}]${scoring}`;
  }

  if (etype === "ROUTE_INVALIDATED") {
    return `route ${event.route_id} invalidated [${event.reason}]`;
  }

  if (etype === "COLLISION") {
    return `⚡ collision on ${channelLabel(event.channel as string, cfg)}`;
  }

  if (etype === "NOISE_APPLIED") {
    return `${player} noised channel ${channelLabel(event.channel as string, cfg)}`;
  }

  if (etype === "SCORE_AWARDED") {
    return `SCORE ${event.player_id} +${event.score} (${event.route_id} len ${event.route_length})`;
  }

  if (etype === "PASS_TURN") {
    return `${event.player_id ?? player} passed (no legal plays)`;
  }

  return null;
}

// ---------------------------------------------------------------------------
// Hint builder
// ---------------------------------------------------------------------------

export interface Hint {
  label: string;
  className: string;
}

export function buildHints(state: GameState, player: { hand: Card[]; playerId: string }, policy: import("./policies").PlayerPolicy): Hint[][] {
  const cfg = state.config;
  const openRoutes = state.tableau.routes.filter(routeIsOpen);
  const hints: Hint[][] = [];

  for (const card of player.hand) {
    const cardHints: Hint[] = [];

    if (card.cardType === CardType.NOISE) {
      const ch = card.outputChannel;
      const scoringChannels = new Set<string>();
      for (const r of state.tableau.routes) {
        if (r.isValid && r.length >= cfg.routeMinLength) {
          for (const cid of r.cardIds) {
            const c = lookupCard(state, cid);
            if (c && c.outputChannel && c.outputChannel !== "TERM") scoringChannels.add(c.outputChannel);
          }
        }
      }
      if (ch && scoringChannels.has(ch)) {
        cardHints.push({ label: `noise CH${ch} ✓`, className: "hint-valid" });
      } else {
        cardHints.push({ label: `noise CH${ch} (no target)`, className: "hint-invalid" });
      }
    } else if (card.cardType === CardType.TERMINAL) {
      for (const route of openRoutes) {
        if (route.length >= cfg.routeMinLength) {
          cardHints.push({ label: `TERM ${route.routeId} ✓`, className: "hint-valid" });
        }
      }
    } else {
      for (const route of openRoutes) {
        if (!policy._canCardExtendRoute(card, route, state)) continue;
        if (card.cardType === CardType.AMPLIFIER) {
          cardHints.push({ label: `AMP ${route.routeId} ×${cfg.amplifierMultiplier}`, className: "hint-amp" });
        } else if (card.cardType === CardType.FILTER) {
          cardHints.push({ label: `FLT ${route.routeId}`, className: "hint-flt" });
        } else {
          cardHints.push({ label: `→ ${route.routeId}`, className: "hint-relay" });
        }
      }
      if (cardHints.length === 0) {
        const openCount = state.tableau.routes.filter(routeIsOpen).length;
        const capReached = openCount >= cfg.playerCount;
        if (!capReached) cardHints.push({ label: "→ new route", className: "hint-new" });
      }
    }

    hints.push(cardHints);
  }

  return hints;
}
