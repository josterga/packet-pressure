import "./style.css";
import { FAST_CONFIG } from "./config";
import { GameLoop } from "./game-loop";

const loop = new GameLoop(FAST_CONFIG);
loop.init();
