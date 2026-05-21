import { DeckBuilder } from "./deck";
import { GameEngine } from "./engine";
import { Card, CardType, EVT_CARD_DRAWN, GameConfig, GameState, PlacementContext, PlayerState, emptyContext, lookupCard, makeMulberry32, passContext, routeIsOpen, targetContext } from "./models";
import { PlayerPolicy, makeDefaultPolicies } from "./policies";
import { HumanPolicy } from "./human-policy";
import {
  buildHints,
  renderEvent,
  renderRoundHeader,
  renderRoute,
  renderScores,
  renderTableau,
  renderCard,
} from "./render";

const OPPONENT_DELAY_MS = 600;

function delay(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ---------------------------------------------------------------------------
// DOM helpers
// ---------------------------------------------------------------------------

function el(id: string): HTMLElement {
  return document.getElementById(id)!;
}

function setHtml(id: string, html: string): void {
  el(id).innerHTML = html;
}

function show(id: string): void {
  el(id).classList.remove("hidden");
}

function hide(id: string): void {
  el(id).classList.add("hidden");
}

// ---------------------------------------------------------------------------
// Screen management
// ---------------------------------------------------------------------------

type Screen = "start" | "game" | "round-end" | "game-over";

function showScreen(screen: Screen): void {
  for (const s of ["start", "game", "round-end", "game-over"]) {
    const elem = document.getElementById(`screen-${s}`);
    if (elem) elem.classList.toggle("hidden", s !== screen);
  }
}

// ---------------------------------------------------------------------------
// Background pattern
// ---------------------------------------------------------------------------

function buildPatternDataUri(dark: boolean): string {
  // 5 glyphs tiled in 88×88 grid, muted hues
  const hues = dark
    ? { rel: "%232D6F6A", amp: "%236E3818", flt: "%235C1B70", trm: "%239C937F", noise: "%239C937F" }
    : { rel: "%237E938F", amp: "%23A86D4A", flt: "%237B5894", trm: "%235C564B", noise: "%235C564B" };

  const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='88' height='88'><style>text{font-family:monospace;font-size:16px}</style>` +
    `<text x='14' y='22' fill='${hues.rel}' opacity='1' text-anchor='middle'>⇒</text>` +
    `<text x='44' y='22' fill='${hues.amp}' opacity='1' text-anchor='middle'>⊕</text>` +
    `<text x='74' y='22' fill='${hues.flt}' opacity='1' text-anchor='middle'>⊘</text>` +
    `<text x='14' y='55' fill='${hues.trm}' opacity='1' text-anchor='middle'>⊣</text>` +
    `<text x='44' y='55' fill='${hues.noise}' opacity='1' text-anchor='middle'>⚠</text>` +
    `<text x='74' y='55' fill='${hues.rel}' opacity='1' text-anchor='middle'>⇒</text>` +
    `<text x='29' y='82' fill='${hues.amp}' opacity='1' text-anchor='middle'>⊕</text>` +
    `<text x='59' y='82' fill='${hues.flt}' opacity='1' text-anchor='middle'>⊘</text>` +
    `</svg>`;

  return `url("data:image/svg+xml,${svg}")`;
}

function applyPattern(dark: boolean): void {
  document.documentElement.style.setProperty("--pattern-bg", buildPatternDataUri(dark));
}

// ---------------------------------------------------------------------------
// GameLoop controller
// ---------------------------------------------------------------------------

export class GameLoop {
  private engine!: GameEngine;
  private humanPolicy!: HumanPolicy;
  private humanIndex = 0;
  private config: GameConfig;
  private seed: number;
  private _aborted = false;

  constructor(config: GameConfig) {
    this.config = config;
    this.seed = Math.floor(Math.random() * 0xffffffff);
  }

  init(): void {
    this._setupStart();
    this._setupHelp();
    this._setupQuit();
    this._setupTheme();
    this._setupHintsToggle();
    showScreen("start");
  }

  private _setupStart(): void {
    el("btn-start").addEventListener("click", () => this._startGame());
    el("btn-new-game-over").addEventListener("click", () => {
      this.seed = Math.floor(Math.random() * 0xffffffff);
      showScreen("start");
      this._updateSeedDisplay();
    });
    el("btn-new-round-end").addEventListener("click", () => {
      this.seed = Math.floor(Math.random() * 0xffffffff);
      showScreen("start");
      this._updateSeedDisplay();
    });
    this._updateSeedDisplay();
  }

  private _setupHelp(): void {
    const openHelp  = () => el("help-modal").classList.remove("hidden");
    const closeHelp = () => el("help-modal").classList.add("hidden");
    el("btn-help").addEventListener("click", openHelp);
    el("btn-start-help").addEventListener("click", openHelp);
    el("btn-help-close").addEventListener("click", closeHelp);
    el("btn-help-close-bottom").addEventListener("click", closeHelp);
    el("help-modal").addEventListener("click", (e) => {
      if (e.target === el("help-modal")) closeHelp();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeHelp();
    });
  }

  private _setupTheme(): void {
    const startBtn = el("btn-theme-toggle-start");
    const gameBtn  = el("btn-theme-toggle");
    const btns = [startBtn, gameBtn];

    const apply = (dark: boolean) => {
      if (dark) {
        document.documentElement.setAttribute("data-theme", "dark");
        btns.forEach(b => b.textContent = "☀ Light");
      } else {
        document.documentElement.removeAttribute("data-theme");
        btns.forEach(b => b.textContent = "☾ Dark");
      }
      localStorage.setItem("pp-theme", dark ? "dark" : "light");
      applyPattern(dark);
    };

    // Init from current state (set by inline script before body)
    const isDark = document.documentElement.getAttribute("data-theme") === "dark";
    apply(isDark);

    btns.forEach(b => b.addEventListener("click", () => {
      apply(document.documentElement.getAttribute("data-theme") !== "dark");
    }));
  }

  private _setupHintsToggle(): void {
    const btn = el("btn-hints-toggle");
    const apply = (on: boolean) => {
      document.body.classList.toggle("hints-off", !on);
      btn.textContent = on ? "Hints: on" : "Hints: off";
      btn.classList.toggle("is-on", on);
      localStorage.setItem("pp-hints", on ? "on" : "off");
    };
    const stored = localStorage.getItem("pp-hints") !== "off";
    apply(stored);
    btn.addEventListener("click", () => apply(document.body.classList.contains("hints-off")));
  }

  private _setupQuit(): void {
    el("btn-quit").addEventListener("click", () => {
      this._aborted = true;
      el("help-modal").classList.add("hidden");
      this.seed = Math.floor(Math.random() * 0xffffffff);
      showScreen("start");
      this._updateSeedDisplay();
    });
  }

  private _updateSeedDisplay(): void {
    const seedEl = document.getElementById("seed-display");
    if (seedEl) seedEl.textContent = `Seed ${this.seed}`;
  }

  private _startGame(): void {
    this._aborted = false;
    const rng = makeMulberry32(this.seed);
    const deck = new DeckBuilder(this.config, rng).build();

    this.humanPolicy = new HumanPolicy(this.humanIndex);
    const aiPolicies = makeDefaultPolicies(this.config);
    const allPolicies: PlayerPolicy[] = [...aiPolicies];
    allPolicies.splice(this.humanIndex, 0, this.humanPolicy);

    this.engine = new GameEngine(this.config, allPolicies, deck, rng);
    showScreen("game");
    this._runGame();
  }

  private async _runGame(): Promise<void> {
    const state = this.engine.state;
    this._renderGameHeader(state);

    while (!this.engine._isTerminal() && !this._aborted) {
      await this._runRound(state);
    }

    if (!this._aborted) this._showGameOver(state);
  }

  private async _runRound(state: GameState): Promise<void> {
    state.roundNumber += 1;
    state.turnNumber = 0;
    this.engine._beginRound();

    const cfg = this.config;
    const first = state.firstPlayerIndex;
    const allTurns: number[] = [];
    for (let t = 0; t < cfg.turnsPerPlayerPerRound; t++) {
      for (let offset = 0; offset < cfg.playerCount; offset++) {
        allTurns.push((first + offset) % cfg.playerCount);
      }
    }

    for (const pIdx of allTurns) {
      if (this.engine._isTerminal()) break;
      state.currentPlayerIndex = pIdx;
      const logBefore = state.eventLog.length;

      if (pIdx === this.humanIndex) {
        await this._runHumanTurn(state, pIdx);
      } else {
        await this._runOpponentTurn(state, pIdx, logBefore);
      }

      state.turnNumber += 1;
    }

    this.engine._endOfRoundScoring();
    this.engine._discardTableau();
    this.engine._advanceRound();

    if (!this.engine._isTerminal()) {
      await this._showRoundEnd(state);
    }
  }

  // ------------------------------------------------------------------
  // Human turn
  // ------------------------------------------------------------------

  private async _runHumanTurn(state: GameState, pIdx: number): Promise<void> {
    const player = state.players[pIdx];

    const drawn = this._engineDrawForTurn(state, pIdx);

    this._renderFullState(state, player, drawn);

    const [card, ctx] = await this._waitForHumanPlay(state, player);
    if (this._aborted) return;

    player.hand.splice(player.hand.indexOf(card), 1);
    player.playHistory.push(card.cardId);
    const owned = this.engine._applyPlay(pIdx, card, 0, ctx.targetRouteId);
    (this.engine as any)._resolveCardEffects(owned);
    (this.engine as any)._updateRoutes(owned);

    this._renderHeader(state);
    const newEvents = state.eventLog.slice(this._lastLogIdx);
    this._appendEventLog(newEvents, state);
  }

  private _lastLogIdx = 0;

  private _engineDrawForTurn(state: GameState, pIdx: number): Card[] {
    const player = state.players[pIdx];
    const drawn: Card[] = (this.engine as any)._drawN(state, this.config.drawPerTurn);
    for (const card of drawn) {
      player.hand.push(card);
      state.eventLog.push({
        round: state.roundNumber,
        turn: state.turnNumber,
        player: player.playerId,
        event: EVT_CARD_DRAWN,
        card_id: card.cardId,
        card_type: card.cardType,
      });
    }
    this._lastLogIdx = state.eventLog.length;
    return drawn;
  }

  private _waitForHumanPlay(state: GameState, player: PlayerState): Promise<[Card, PlacementContext]> {
    return new Promise(resolve => {
      this.humanPolicy.requestPlay(state, player, resolve);
    });
  }

  // ------------------------------------------------------------------
  // Opponent turn
  // ------------------------------------------------------------------

  private async _runOpponentTurn(state: GameState, pIdx: number, _logBefore: number): Promise<void> {
    const logBefore = state.eventLog.length;
    this.engine._runTurn(pIdx);
    const newEvents = state.eventLog.slice(logBefore);

    const policyName = this.engine.policies[pIdx].name;
    const playerId   = state.players[pIdx].playerId;

    const keyLines = newEvents
      .map(e => renderEvent(e, state))
      .filter((l): l is string => l !== null && /played|noised|SCORE|invalidated|terminated|collision|passed/.test(l));

    if (keyLines.length > 0) {
      this._appendOpponentSummary(playerId, policyName, keyLines.slice(0, 3), state);
    }

    this._renderHeader(state);
    await delay(OPPONENT_DELAY_MS);
  }

  // ------------------------------------------------------------------
  // UI rendering
  // ------------------------------------------------------------------

  private _renderGameHeader(state: GameState): void {
    this._renderHeader(state);
  }

  private _renderHeader(state: GameState): void {
    setHtml("header-bar",  renderRoundHeader(state));
    setHtml("scores-bar",  renderScores(state, this.humanIndex));
    setHtml("tableau-area", renderTableau(state));
    // hide new-route btn by default (armed by human-policy when needed)
    el("new-route-btn").classList.add("hidden");
    el("new-route-btn").classList.remove("is-armed");
  }

  private _renderFullState(state: GameState, player: PlayerState, drawn: Card[]): void {
    this._renderHeader(state);
    this._renderHand(state, player, drawn);
  }

  private _renderHand(state: GameState, player: PlayerState, drawn: Card[]): void {
    const cfg   = state.config;
    const proxy = this.humanPolicy.getProxy();
    const hints = buildHints(state, player, proxy);

    const slotsHtml = player.hand.map((card, i) => {
      const hasValidPlay = hints[i].some(h =>
        h.className !== "hint-invalid" && h.className !== ""
      );
      const isInvalid = !hasValidPlay && hints[i].length > 0;

      const hintsHtml = hints[i].map(h => {
        const cls = h.className.replace("hint-", "pp-hint--");
        return `<span class="pp-hint ${cls}">${h.label}</span>`;
      }).join("");

      return `
        <div class="pp-hand__slot">
          <span class="pp-hand__index">[${i + 1}]</span>
          ${renderCard(card, cfg, { invalid: isInvalid })}
          <div class="pp-hints">${hintsHtml}</div>
        </div>
      `;
    }).join("");

    setHtml("hand-cards", slotsHtml);

    // Update hint text
    const hintEl = document.getElementById("hand-hint");
    if (hintEl) hintEl.textContent = "Select a card to play";

    if (drawn.length > 0) {
      const drawnText = drawn.map(c =>
        `${c.cardId} ${c.inputChannel ?? "—"}→${c.outputChannel ?? "—"} PKT ${c.packetValue}`
      ).join(", ");
      const logEl = el("event-log");
      const div = document.createElement("div");
      div.className = "pp-log__line is-drawn";
      div.textContent = `Drew: ${drawnText}`;
      logEl.prepend(div);
    }

    // Attach card click listeners via human-policy
    this.humanPolicy.attachCardListeners();
  }

  private _appendEventLog(events: Record<string, unknown>[], state: GameState): void {
    const lines = events
      .map(e => renderEvent(e, state))
      .filter((l): l is string => l !== null);
    const logEl = el("event-log");
    for (const line of lines.reverse()) {
      const div = document.createElement("div");
      div.className = `pp-log__line${line.includes("SCORE") ? " is-score" : ""}`;
      div.textContent = line;
      logEl.prepend(div);
    }
  }

  private _appendOpponentSummary(playerId: string, policyName: string, lines: string[], state: GameState): void {
    const logEl = el("event-log");
    const wrapper = document.createElement("div");
    wrapper.className = "pp-log__line is-opponent";
    wrapper.innerHTML = `<b>${playerId} [${policyName}]</b><br>` + lines.map(l => `<span>${l}</span>`).join("<br>");
    logEl.prepend(wrapper);
  }

  // ------------------------------------------------------------------
  // Round end
  // ------------------------------------------------------------------

  private _showRoundEnd(state: GameState): Promise<void> {
    const scored = state.eventLog.filter(
      e => e.event === "SCORE_AWARDED" && e.round === state.roundNumber
    );

    let html = `<h2>End of Round ${state.roundNumber}</h2>`;

    const scoreLine = state.players.map((p, i) => {
      const name = i === this.humanIndex ? "YOU" : p.playerId;
      return `${name} ${p.score}`;
    }).join(" · ");
    html += `<div class="overlay-scores">${scoreLine}</div>`;

    if (scored.length > 0) {
      html += "<ul class='round-scores'>";
      for (const e of scored) {
        html += `<li>+${e.score} · ${e.player_id} · (${e.route_id} len ${e.route_length})</li>`;
      }
      html += "</ul>";
    } else {
      html += "<p class='mute' style='font-size:0.88em'>(no scoring routes this round)</p>";
    }

    setHtml("round-end-content", html);
    showScreen("round-end");

    return new Promise(resolve => {
      const btn = el("btn-continue");
      const handler = () => {
        btn.removeEventListener("click", handler);
        if (this._aborted) { resolve(); return; }
        showScreen("game");
        this._renderHeader(state);
        setHtml("event-log", "");
        setHtml("hand-cards", "");
        resolve();
      };
      btn.addEventListener("click", handler);

      const abortCheck = setInterval(() => {
        if (this._aborted) { clearInterval(abortCheck); btn.removeEventListener("click", handler); resolve(); }
      }, 100);
    });
  }

  // ------------------------------------------------------------------
  // Game over
  // ------------------------------------------------------------------

  private _showGameOver(state: GameState): void {
    const ranked = [...state.players].sort((a, b) => b.score - a.score);
    const you    = state.players[this.humanIndex];
    const winner = ranked[0];

    let html = `<h2>GAME OVER</h2>`;
    html += "<ol class='final-scores'>";
    for (const p of ranked) {
      const isYou = state.players.indexOf(p) === this.humanIndex;
      html += `<li class="${isYou ? "you" : ""}">${p.playerId} [${p.policyName}] — ${p.score}${isYou ? " ← you" : ""}</li>`;
    }
    html += "</ol>";

    if (you.playerId === winner.playerId) {
      html += `<p class="winner-msg">You won with ${you.score} points!</p>`;
    } else {
      html += `<p class="winner-msg">${winner.playerId} wins with ${winner.score}. Your score: ${you.score}</p>`;
    }

    setHtml("game-over-content", html);
    showScreen("game-over");
  }
}
