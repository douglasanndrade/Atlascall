import { writable } from "svelte/store";

// Atlas Call - desenho + laser sobre a TELA COMPARTILHADA.
// Coordenadas sempre NORMALIZADAS [0..1] relativas a area do video, pra bater
// entre telas de tamanhos diferentes. Estes stores guardam o que CHEGA de
// outros usuarios; o GameScene empurra os eventos aqui e o overlay desenha.

export interface LaserDot {
    x: number;
    y: number;
    color: string;
    name: string;
    ts: number;
}

export interface DrawSeg {
    x0: number;
    y0: number;
    x1: number;
    y1: number;
    color: string;
    width: number;
    seq: number;
}

// lasers remotos, indexados pelo nome de quem aponta
export const remoteLasers = writable<Record<string, LaserDot>>({});
// ultimo traco de desenho recebido (incremental)
export const remoteStroke = writable<DrawSeg | null>(null);
// contador que incrementa a cada "limpar" recebido
export const clearTick = writable<number>(0);

let seqCounter = 0;

function asObj(d: unknown): Record<string, unknown> {
    return d && typeof d === "object" ? (d as Record<string, unknown>) : {};
}
function num(v: unknown, def = 0): number {
    return typeof v === "number" && isFinite(v) ? v : def;
}
function str(v: unknown, def = ""): string {
    return typeof v === "string" ? v : def;
}

export function pushLaser(data: unknown): void {
    const d = asObj(data);
    const name = str(d.name, "?");
    remoteLasers.update((m) => {
        m[name] = { x: num(d.x), y: num(d.y), color: str(d.color, "#ff3b30"), name, ts: Date.now() };
        return { ...m };
    });
}

export function pushStroke(data: unknown): void {
    const d = asObj(data);
    remoteStroke.set({
        x0: num(d.x0),
        y0: num(d.y0),
        x1: num(d.x1),
        y1: num(d.y1),
        color: str(d.color, "#ffeb3b"),
        width: num(d.width, 3),
        seq: ++seqCounter,
    });
}

export function pushClear(): void {
    clearTick.update((n) => n + 1);
}
