import {
  Card,
  CardType,
  GameState,
  PlacementContext,
  PlayerState,
  emptyContext,
  passContext,
  routeIsOpen,
  targetContext,
} from "./models";
import { PlayerPolicy } from "./policies";
import { renderRoute } from "./render";

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
    this._pendingState = state;
    this._pendingPlayer = player;
    this._attachCardListeners(state, player, resolve);
  }

  private _attachCardListeners(state: GameState, player: PlayerState, resolve: PlayResolver): void {
    const handArea = document.getElementById("hand-area");
    if (!handArea) return;

    const cards = handArea.querySelectorAll<HTMLElement>(".card");
    cards.forEach(cardEl => {
      cardEl.style.cursor = "pointer";
      cardEl.addEventListener("click", () => {
        const cardId = cardEl.dataset.cardId;
        if (!cardId) return;
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
        this._showMessage(`No scoring routes on CH${ch} — choose another card.`);
        this._attachCardListeners(state, player, resolve);
        return;
      }
      resolve([card, emptyContext()]);
      return;
    }

    if (card.cardType === CardType.TERMINAL) {
      const terminable = state.tableau.routes.filter(
        r => routeIsOpen(r) && r.length >= state.config.routeMinLength
      );
      if (terminable.length === 0) {
        this._showMessage("No scoring routes to terminate (need ≥2 cards).");
        this._attachCardListeners(state, player, resolve);
        return;
      }
      if (terminable.length === 1) {
        resolve([card, targetContext(terminable[0].routeId)]);
        return;
      }
      const routeId = await this._promptRoute(state, terminable, "Terminate which route?");
      resolve([card, targetContext(routeId)]);
      return;
    }

    // Relay / Amplifier / Filter
    const plays = this.legalPlays(state, player);
    const hasAnyValid = plays.some(([, ctx]) => !ctx.passTurn);
    const matching = plays.filter(([c]) => c.cardId === card.cardId);

    if (!matching.length || matching.every(([, ctx]) => ctx.passTurn)) {
      if (hasAnyValid) {
        this._showMessage("That card can't be played right now — choose another.");
        this._attachCardListeners(state, player, resolve);
        return;
      }
      resolve([card, passContext()]);
      return;
    }

    if (matching.length === 1) {
      resolve([card, matching[0][1]]);
      return;
    }

    // Multiple target routes — ask
    const routeIds = matching.map(([, ctx]) => ctx.targetRouteId).filter((id): id is string => id !== null);
    const openRoutes = state.tableau.routes.filter(r => routeIds.includes(r.routeId));
    const routeId = await this._promptRoute(state, openRoutes, "Extend which route?");
    const ctx = matching.find(([, c]) => c.targetRouteId === routeId)?.[1] ?? matching[0][1];
    resolve([card, ctx]);
  }

  private _promptRoute(state: GameState, routes: typeof state.tableau.routes, prompt: string): Promise<string> {
    return new Promise(resolve => {
      const actionArea = document.getElementById("action-area")!;
      actionArea.innerHTML = `
        <div class="route-prompt">
          <div class="prompt-label">${prompt}</div>
          <div class="route-choices">
            ${routes.map((r, i) => `
              <button class="route-choice-btn" data-route-id="${r.routeId}">
                [${i + 1}] ${r.routeId} len ${r.length}
                ${r.isScoringCandidate ? " ✓" : ""}
              </button>
            `).join("")}
          </div>
        </div>
      `;

      actionArea.querySelectorAll<HTMLButtonElement>(".route-choice-btn").forEach(btn => {
        btn.addEventListener("click", () => {
          const routeId = btn.dataset.routeId!;
          actionArea.innerHTML = "";
          resolve(routeId);
        }, { once: true });
      });
    });
  }

  private _showMessage(msg: string): void {
    const actionArea = document.getElementById("action-area")!;
    const div = document.createElement("div");
    div.className = "action-message";
    div.textContent = msg;
    actionArea.innerHTML = "";
    actionArea.appendChild(div);
    setTimeout(() => {
      if (actionArea.contains(div)) actionArea.removeChild(div);
    }, 2500);
  }
}
