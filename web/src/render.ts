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
  maxOpenRoutes,
  routeIsOpen,
  routeLastOutputChannel,
} from "./models";

// ---------------------------------------------------------------------------
// Channel helpers
// ---------------------------------------------------------------------------

function channelToken(ch: string | null, cfg: GameConfig): string {
  if (!ch || ch === "ANY" || ch === "TERM") return "var(--ink-faint)";
  const color = channelColor(cfg, ch);
  if (color === "teal")   return "var(--ch01)";
  if (color === "orange") return "var(--ch02)";
  if (color === "purple") return "var(--ch03)";
  return "var(--ink-faint)";
}

export function channelLabel(ch: string | null, _cfg?: GameConfig): string {
  if (ch === null)   return "——";
  if (ch === "ANY")  return "ANY";
  if (ch === "TERM") return "END";
  return `CH${ch.padStart(2, "0")}`;
}

// Kept for hint builder backward compat
export function channelCssClass(ch: string | null, cfg: GameConfig): string {
  if (!ch || ch === "ANY" || ch === "TERM") return "";
  const color = channelColor(cfg, ch);
  return color ? `ch-${color}` : "";
}

function chSpan(ch: string | null, cfg: GameConfig): string {
  const token = channelToken(ch, cfg);
  const label = channelLabel(ch);
  return `<span style="color:${token};font-weight:600">${label}</span>`;
}

// ---------------------------------------------------------------------------
// Card type metadata
// ---------------------------------------------------------------------------

interface CardMeta {
  sym: string;
  typeLabel: string;
  shortCode: string;
  colorToken: string;
}

const CARD_META: Record<CardType, CardMeta> = {
  [CardType.RELAY]:     { sym: "⇒", typeLabel: "RELAY",     shortCode: "REL",   colorToken: "var(--rel)"   },
  [CardType.TERMINAL]:  { sym: "⊣", typeLabel: "TERMINAL",  shortCode: "TRM",   colorToken: "var(--trm)"   },
  [CardType.AMPLIFIER]: { sym: "⊕", typeLabel: "AMPLIFIER", shortCode: "AMP",   colorToken: "var(--amp)"   },
  [CardType.NOISE]:     { sym: "⚠", typeLabel: "NOISE",     shortCode: "NOISE", colorToken: "var(--noise)" },
  [CardType.FILTER]:    { sym: "⊘", typeLabel: "FILTER",    shortCode: "FLT",   colorToken: "var(--flt)"   },
};

// ---------------------------------------------------------------------------
// Card rendering
// ---------------------------------------------------------------------------

export function renderCard(
  card: Card,
  cfg: GameConfig,
  opts: { invalid?: boolean; selected?: boolean; label?: string } = {},
): string {
  const meta = CARD_META[card.cardType];
  const inCh = card.inputChannel;
  const outCh = card.outputChannel;
  const inToken  = channelToken(inCh, cfg);
  const outToken = channelToken(outCh, cfg);
  const inLabel  = channelLabel(inCh);
  const outLabel = channelLabel(outCh);

  // Extra line for amp (×N) and filter (FLT-CHXX)
  let extraHtml = "";
  if (card.cardType === CardType.AMPLIFIER) {
    const mult = cardSpecial(card, "multiplier", cfg.amplifierMultiplier) as number;
    extraHtml = `<div class="pp-card__extra">×${mult}</div>`;
  } else if (card.cardType === CardType.FILTER && inCh) {
    extraHtml = `<div class="pp-card__extra">FLT-${channelLabel(inCh)}</div>`;
  }

  const classes = [
    "pp-card",
    opts.selected ? "is-selected" : "",
    opts.invalid  ? "is-invalid"  : "",
  ].filter(Boolean).join(" ");

  // Left bar only if there's an in-channel (NOISE has none)
  const leftBar = inCh && inCh !== "ANY" && inCh !== "TERM"
    ? `<div class="pp-card__bar pp-card__bar--l" style="background:${inToken}"></div>`
    : "";
  const rightBar = outCh && outCh !== "TERM"
    ? `<div class="pp-card__bar pp-card__bar--r" style="background:${outToken}"></div>`
    : "";

  return `
    <div class="${classes}" data-card-id="${card.cardId}">
      ${leftBar}${rightBar}
      <div class="pp-card__head">
        <span class="mute">IN</span>
        <span class="chan" style="color:${inToken}">${inCh ? inLabel : "——"}</span>
        <span class="arrow" style="color:var(--ink-faint)">→</span>
        <span class="chan" style="color:${outToken}">${outLabel}</span>
        <span class="mute">OUT</span>
      </div>
      <div class="pp-card__body">
        <div class="pp-card__sym" style="color:${meta.colorToken}">${meta.sym}</div>
        <div class="pp-card__type">${meta.typeLabel}</div>
        ${extraHtml}
        <div class="pp-card__pkt">PKT&nbsp;<b>${card.packetValue}</b></div>
      </div>
      <div class="pp-card__foot">
        <span>${card.ownerId ?? ''}</span>
        <span>${card.cardId}</span>
      </div>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Route rendering
// ---------------------------------------------------------------------------

function routeFlow(route: RouteState, cfg: GameConfig): string {
  // entry → ... → current out
  const parts: string[] = [];
  if (route.entryChannel) parts.push(chSpan(route.entryChannel, cfg));
  for (const ch of route.channelsInRoute) parts.push(chSpan(ch, cfg));
  if (route.terminationReason !== TerminationReason.ACTIVE) {
    parts.push(`<span style="color:var(--ink-mute)">END</span>`);
  }
  const sep = `<span style="color:var(--ink-faint);margin:0 4px">→</span>`;
  return parts.join(sep);
}

export function renderRoute(
  route: RouteState,
  state: GameState,
  opts: { dim?: boolean; armed?: boolean } = {},
): string {
  const cfg = state.config;
  const cards = route.cardIds
    .map(cid => lookupCard(state, cid))
    .filter((c): c is Card => c !== null);

  const closedHtml = !route.isValid
    ? `<span class="pp-route__closed">BROKEN</span>`
    : route.terminationReason !== TerminationReason.ACTIVE
      ? `<span class="pp-route__closed">CLOSED</span>`
      : "";

  const scoringBadge = route.isScoringCandidate && route.terminationReason === TerminationReason.ACTIVE
    ? `<span class="pp-route__meta">✓ scoring</span>`
    : "";

  // Card chain with connectors
  const cardsHtml = cards.map((c, i) => {
    const connector = i > 0
      ? `<div class="pp-route__connector" aria-hidden>·</div>`
      : "";
    return `${connector}${renderCard(c, cfg, { dim: opts.dim } as any)}`;
  }).join("");

  // PLAY HERE slot when armed
  const playHereHtml = opts.armed ? `
    <div class="pp-route__connector" aria-hidden>·</div>
    <button class="pp-route__newslot" data-play-route="${route.routeId}" aria-label="Play onto ${route.routeId}">
      <div>
        <div style="font-size:18px;margin-bottom:6px">+</div>
        <div>PLAY HERE</div>
      </div>
    </button>
  ` : "";

  const dropClass = opts.armed ? "pp-route--drop" : "";
  const opacity   = opts.dim   ? "opacity:0.5;"    : "";

  return `
    <div class="pp-route ${dropClass}" data-route-id="${route.routeId}" style="${opacity}">
      <div class="pp-route__head">
        <span class="pp-route__id">${route.routeId}</span>
        <span class="pp-route__meta">[len ${route.length}]</span>
        <span class="pp-route__flow">${routeFlow(route, cfg)}</span>
        ${scoringBadge}
        ${closedHtml}
      </div>
      <div class="pp-route__cards">
        ${cardsHtml}
        ${playHereHtml}
      </div>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Tableau rendering
// ---------------------------------------------------------------------------

export function renderTableau(state: GameState, armedRouteIds: Set<string> = new Set()): string {
  const active  = state.tableau.routes.filter(r => r.isValid && r.terminationReason === TerminationReason.ACTIVE);
  const carried = active.filter(r => r.carried);
  const live    = active.filter(r => !r.carried);
  const done    = state.tableau.routes.filter(r => r.isValid && r.terminationReason !== TerminationReason.ACTIVE);
  const broken  = state.tableau.routes.filter(r => !r.isValid);

  let html = "";

  if (carried.length > 0) {
    html += `<div class="pp-section-label">Carried</div>`;
    html += carried.map(r => renderRoute(r, state, { armed: armedRouteIds.has(r.routeId) })).join("");
  }

  html += live.map(r => renderRoute(r, state, { armed: armedRouteIds.has(r.routeId) })).join("");

  if (done.length > 0) {
    html += `<div class="pp-section-label">Done</div>`;
    html += done.map(r => renderRoute(r, state, { dim: true })).join("");
  }

  if (broken.length > 0) {
    html += `<div class="pp-section-label">Broken</div>`;
    html += broken.map(r => renderRoute(r, state, { dim: true })).join("");
  }

  if (!html) {
    html = `<div class="mute" style="padding:1rem 0">(tableau empty)</div>`;
  }

  return html;
}

// ---------------------------------------------------------------------------
// Scoreboard
// ---------------------------------------------------------------------------

export function renderScores(state: GameState, humanIndex: number): string {
  const cfg = state.config;
  const activeIdx = state.currentPlayerIndex;

  return state.players.map((p, i) => {
    const name   = i === humanIndex ? "YOU" : p.playerId;
    const isYou  = i === humanIndex;
    const isActive = i === activeIdx;
    const activeDot = isActive ? " · turn" : "";
    const classes = ["pp-player", isActive ? "is-active" : "", isYou ? "is-you" : ""].filter(Boolean).join(" ");

    return `
      <div class="${classes}">
        <div class="pp-player__name">
          <span class="pp-player__dot"></span>
          <span>${name}${activeDot}</span>
        </div>
        <div class="pp-player__score">${p.score}<span class="mute" style="font-size:11px;font-weight:400"> / ${cfg.scoreToWin}</span></div>
      </div>
    `;
  }).join("");
}

// ---------------------------------------------------------------------------
// Round header
// ---------------------------------------------------------------------------

export function renderRoundHeader(state: GameState): string {
  const cfg = state.config;
  const totalTurns   = cfg.turnsPerPlayerPerRound * cfg.playerCount;
  const displayTurn  = Math.min(state.turnNumber + 1, totalTurns);
  const sep = `<span style="color:var(--ink-faint);margin:0 2px">·</span>`;

  const roundSpan = `<span class="dim">Round&nbsp;<b style="color:var(--ink)">${state.roundNumber}</b>&nbsp;of&nbsp;${cfg.maxRounds}</span>`;
  const turnSpan  = cfg.turnsPerPlayerPerRound > 1
    ? `${sep}<span class="dim">Turn&nbsp;<b style="color:var(--ink)">${displayTurn}</b>&nbsp;of&nbsp;${totalTurns}</span>`
    : "";
  const winSpan   = `${sep}<span class="dim">Win&nbsp;<b style="color:var(--ink)">${cfg.scoreToWin}</b></span>`;

  return `${roundSpan}${turnSpan}${winSpan}`;
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
      return `${player} played ${card.cardId} NOISE ${channelLabel(card.outputChannel)}`;
    }
    return `${player} played ${card.cardId} ${channelLabel(card.inputChannel)}→${channelLabel(card.outputChannel)} PKT ${card.packetValue}`;
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
    return `⚡ collision on ${channelLabel(event.channel as string)}`;
  }

  if (etype === "NOISE_APPLIED") {
    return `${player} noised channel ${channelLabel(event.channel as string)}`;
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
// Hint builder (used to determine is-invalid state)
// ---------------------------------------------------------------------------

export interface Hint {
  label: string;
  className: string;
}

export function buildHints(
  state: GameState,
  player: { hand: Card[]; playerId: string },
  policy: import("./policies").PlayerPolicy,
): Hint[][] {
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
          const interChannels = r.channelsInRoute.slice(0, -1);
          for (const c of interChannels) scoringChannels.add(c);
        }
      }
      if (ch && scoringChannels.has(ch)) {
        cardHints.push({ label: `noise CH${ch} ✓`, className: "hint-valid" });
      } else {
        cardHints.push({ label: `CH${ch} — no target`, className: "hint-invalid" });
      }
    } else if (card.cardType === CardType.TERMINAL) {
      for (const route of openRoutes) {
        if (route.length >= cfg.routeMinLength) {
          cardHints.push({ label: `terminate ${route.routeId}`, className: "hint-valid" });
        }
      }
      if (cardHints.length === 0) {
        cardHints.push({ label: "no routes to terminate", className: "hint-invalid" });
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
      const openCount = state.tableau.routes.filter(routeIsOpen).length;
      const capReached = openCount >= maxOpenRoutes(cfg);
      if (!capReached) cardHints.push({ label: "→ new route", className: "hint-new" });
    }

    hints.push(cardHints);
  }

  return hints;
}
