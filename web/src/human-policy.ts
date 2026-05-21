import {
  Card,
  CardType,
  GameState,
  PlacementContext,
  PlayerState,
  RouteState,
  emptyContext,
  passContext,
  routeIsOpen,
  targetContext,
} from "./models";
import { PlayerPolicy } from "./policies";

type PlayResolver = (result: [Card, PlacementContext]) => void;

// ---------------------------------------------------------------------------
// HumanPolicy: drives play selection via DOM interaction
// ---------------------------------------------------------------------------

export class HumanPolicy extends PlayerPolicy {
  name = "human";
  private _humanIndex: number;
  private _pendingResolve: PlayResolver | null = null;
  private _pendingState: GameState | null = null;
  private _pendingPlayer: PlayerState | null = null;
  private _selectedCardId: string | null = null;
  private _cleanupFns: (() => void)[] = [];

  constructor(humanIndex: number) {
    super();
    this._humanIndex = humanIndex;
  }

  choosePlay(_state: GameState, _player: PlayerState): [Card, PlacementContext] {
    throw new Error("HumanPolicy.choosePlay called synchronously — use requestPlay");
  }

  getProxy(): PlayerPolicy {
    return this;
  }

  requestPlay(state: GameState, player: PlayerState, resolve: PlayResolver): void {
    this._pendingResolve = resolve;
    this._pendingState   = state;
    this._pendingPlayer  = player;
    this.attachCardListeners();
  }

  // Called by game-loop after rendering the hand
  attachCardListeners(): void {
    const state  = this._pendingState;
    const player = this._pendingPlayer;
    const resolve = this._pendingResolve;
    if (!state || !player || !resolve) return;

    const handCards = document.getElementById("hand-cards");
    if (!handCards) return;

    const cards = handCards.querySelectorAll<HTMLElement>(".pp-card");
    cards.forEach(cardEl => {
      cardEl.addEventListener("click", () => {
        const cardId = cardEl.dataset.cardId;
        if (!cardId) return;

        // Deselect if clicking already-selected card
        if (this._selectedCardId === cardId) {
          this._clearSelection();
          this.attachCardListeners();
          return;
        }

        const card = player.hand.find(c => c.cardId === cardId);
        if (!card) return;
        this._handleCardClick(card, state, player, resolve);
      }, { once: true });
    });
  }

  private async _handleCardClick(
    card: Card,
    state: GameState,
    player: PlayerState,
    resolve: PlayResolver,
  ): Promise<void> {
    this._clearSelection();

    if (card.cardType === CardType.NOISE) {
      const ch = card.outputChannel;
      const scoringChannels = new Set<string>();
      for (const r of state.tableau.routes) {
        if (r.isValid && r.length >= state.config.routeMinLength) {
          for (const cid of r.cardIds) {
            const c = state._cardRegistry.get(cid);
            if (c && c.outputChannel && c.outputChannel !== "TERM") scoringChannels.add(c.outputChannel);
          }
        }
      }
      if (!ch || !scoringChannels.has(ch)) {
        this._showHint(`No scoring routes on CH${ch} — choose another card.`);
        this.attachCardListeners();
        return;
      }
      this._resetHint();
      resolve([card, emptyContext()]);
      return;
    }

    if (card.cardType === CardType.TERMINAL) {
      const terminable = state.tableau.routes.filter(
        r => routeIsOpen(r) && r.length >= state.config.routeMinLength
      );
      if (terminable.length === 0) {
        this._showHint("No scoring routes to terminate (need ≥2 cards).");
        this.attachCardListeners();
        return;
      }
      if (terminable.length === 1) {
        this._resetHint();
        resolve([card, targetContext(terminable[0].routeId)]);
        return;
      }
      this._selectCard(card);
      this._armRoutes(terminable, card, resolve);
      return;
    }

    // Relay / Amplifier / Filter
    const plays = this.legalPlays(state, player);
    const hasAnyValid = plays.some(([, ctx]) => !ctx.passTurn);
    const matching    = plays.filter(([c]) => c.cardId === card.cardId);

    if (!matching.length || matching.every(([, ctx]) => ctx.passTurn)) {
      if (hasAnyValid) {
        this._showHint("That card can't be played right now — choose another.");
        this.attachCardListeners();
        return;
      }
      this._resetHint();
      resolve([card, passContext()]);
      return;
    }

    if (matching.length === 1) {
      const ctx = matching[0][1];
      if (ctx.targetRouteId) {
        const route = state.tableau.routes.find(r => r.routeId === ctx.targetRouteId);
        if (route) {
          this._selectCard(card);
          this._armRoutes([route], card, resolve);
          return;
        }
      } else {
        // Only option is a new route
        this._selectCard(card);
        this._armNewRoute(card, resolve);
        return;
      }
    }

    // Multiple targets
    const routeIds   = matching.map(([, c]) => c.targetRouteId).filter((id): id is string => id !== null);
    const newRouteCtx = matching.find(([, c]) => c.targetRouteId === null)?.[1];
    const openRoutes  = state.tableau.routes.filter(r => routeIds.includes(r.routeId));

    this._selectCard(card);
    this._armRoutes(openRoutes, card, resolve, newRouteCtx ? () => {
      this._clearSelection();
      this._resetHint();
      resolve([card, newRouteCtx]);
    } : undefined);
  }

  // ── Selection state ─────────────────────────────────────────────────

  private _selectCard(card: Card): void {
    this._selectedCardId = card.cardId;
    const cardEl = document.querySelector<HTMLElement>(`.pp-card[data-card-id="${card.cardId}"]`);
    cardEl?.classList.add("is-selected");
    this._updateHandHint(`Selected ${card.cardId} · pick a route above`);
  }

  private _armRoutes(
    routes: RouteState[],
    selectedCard: Card,
    resolve: PlayResolver,
    onNewRoute?: () => void,
  ): void {
    for (const route of routes) {
      const routeEl = document.querySelector<HTMLElement>(`.pp-route[data-route-id="${route.routeId}"]`);
      if (!routeEl) continue;

      routeEl.classList.add("pp-route--drop");

      const cardsRow = routeEl.querySelector<HTMLElement>(".pp-route__cards");
      if (!cardsRow) continue;

      const connector = document.createElement("div");
      connector.className = "pp-route__connector";
      connector.setAttribute("aria-hidden", "true");
      connector.textContent = "·";

      const slot = document.createElement("button");
      slot.className = "pp-route__newslot";
      slot.setAttribute("data-play-route", route.routeId);
      slot.setAttribute("aria-label", `Play ${selectedCard.cardId} onto ${route.routeId}`);
      slot.innerHTML = `<div><div style="font-size:18px;margin-bottom:6px">+</div><div>PLAY HERE</div><div class="mute" style="margin-top:4px;font-size:10px">${selectedCard.cardId}</div></div>`;

      slot.addEventListener("click", () => {
        this._clearSelection();
        this._resetHint();
        resolve([selectedCard, targetContext(route.routeId)]);
      }, { once: true });

      cardsRow.appendChild(connector);
      cardsRow.appendChild(slot);

      this._cleanupFns.push(() => {
        routeEl.classList.remove("pp-route--drop");
        if (connector.parentNode) connector.remove();
        if (slot.parentNode)      slot.remove();
      });
    }

    // Optionally arm the new-route button too
    if (onNewRoute) {
      this._armNewRouteWithCallback(onNewRoute);
    }
  }

  private _armNewRoute(card: Card, resolve: PlayResolver): void {
    this._armNewRouteWithCallback(() => {
      this._clearSelection();
      this._resetHint();
      resolve([card, emptyContext()]);
    });
  }

  private _armNewRouteWithCallback(cb: () => void): void {
    const btn = document.getElementById("new-route-btn");
    if (!btn) return;
    btn.classList.remove("hidden");
    btn.classList.add("is-armed");

    const handler = () => {
      btn.removeEventListener("click", handler);
      cb();
    };
    btn.addEventListener("click", handler, { once: true });

    this._cleanupFns.push(() => {
      btn.classList.add("hidden");
      btn.classList.remove("is-armed");
      btn.removeEventListener("click", handler);
    });
  }

  private _clearSelection(): void {
    this._selectedCardId = null;
    this._cleanupFns.forEach(fn => fn());
    this._cleanupFns = [];
    document.querySelectorAll(".pp-card.is-selected").forEach(el => el.classList.remove("is-selected"));
  }

  // ── Hint text helpers ────────────────────────────────────────────────

  private _showHint(msg: string): void {
    this._updateHandHint(msg);
    setTimeout(() => this._resetHint(), 2500);
  }

  private _resetHint(): void {
    this._updateHandHint("Select a card to play");
  }

  private _updateHandHint(text: string): void {
    const el = document.getElementById("hand-hint");
    if (el) el.textContent = text;
  }
}
