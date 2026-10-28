<script lang="ts">
    // Atlas Call - overlay de DESENHO + LASER sobre a tela compartilhada.
    // Montado dentro do CenteredVideo quando o tile e de screen-sharing.
    import { onMount, onDestroy } from "svelte";
    import { get } from "svelte/store";
    import { gameManager } from "../../Phaser/Game/GameManager";
    import { localUserStore } from "../../Connection/LocalUserStore";
    import { remoteLasers, remoteStroke, clearTick, type LaserDot, type DrawSeg } from "../../Stores/ScreenDrawStore";

    const COLORS = ["#ffeb3b", "#ff3b30", "#00e676", "#29b6f6", "#ffffff"];

    let mode: "off" | "draw" | "laser" = $state("off");
    let color = $state("#ffeb3b");
    let dots: LaserDot[] = $state([]);

    let canvas: HTMLCanvasElement | undefined = $state();
    let box: HTMLDivElement | undefined = $state();
    let ctx: CanvasRenderingContext2D | null = null;
    let drawing = false;
    let last: { x: number; y: number } | null = null;
    let lastLaserSent = 0;

    function myName(): string {
        return localUserStore.getName() ?? "Alguém";
    }

    function send(name: string, data: unknown): void {
        try {
            gameManager.getCurrentGameScene()?.connection?.emitScriptableEvent(name, data, undefined)?.catch(() => {});
        } catch {
            /* ignore */
        }
    }

    function resize(): void {
        if (!canvas || !box) return;
        const r = box.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) return;
        canvas.width = Math.round(r.width);
        canvas.height = Math.round(r.height);
        ctx = canvas.getContext("2d");
    }

    function toNorm(e: PointerEvent): { x: number; y: number } {
        const r = canvas!.getBoundingClientRect();
        return { x: (e.clientX - r.left) / r.width, y: (e.clientY - r.top) / r.height };
    }

    function paint(s: DrawSeg): void {
        if (!ctx || !canvas) return;
        ctx.strokeStyle = s.color;
        ctx.lineWidth = s.width;
        ctx.lineCap = "round";
        ctx.beginPath();
        ctx.moveTo(s.x0 * canvas.width, s.y0 * canvas.height);
        ctx.lineTo(s.x1 * canvas.width, s.y1 * canvas.height);
        ctx.stroke();
    }

    function clearAll(): void {
        if (ctx && canvas) ctx.clearRect(0, 0, canvas.width, canvas.height);
    }

    function onPointerDown(e: PointerEvent): void {
        if (mode !== "draw") return;
        drawing = true;
        last = toNorm(e);
        (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
    }

    function onPointerMove(e: PointerEvent): void {
        const p = toNorm(e);
        if (mode === "laser") {
            const now = Date.now();
            if (now - lastLaserSent > 40) {
                lastLaserSent = now;
                send("atlas-laser", { x: p.x, y: p.y, color, name: myName() });
            }
            return;
        }
        if (mode === "draw" && drawing && last) {
            paint({ x0: last.x, y0: last.y, x1: p.x, y1: p.y, color, width: 3, seq: 0 });
            send("atlas-draw", { x0: last.x, y0: last.y, x1: p.x, y1: p.y, color, width: 3 });
            last = p;
        }
    }

    function onPointerUp(): void {
        drawing = false;
        last = null;
    }

    function clearAndSend(): void {
        clearAll();
        send("atlas-draw-clear", {});
    }

    function toggle(m: "draw" | "laser"): void {
        mode = mode === m ? "off" : m;
    }

    let unsubStroke: (() => void) | undefined;
    let unsubClear: (() => void) | undefined;
    let raf = 0;

    onMount(() => {
        resize();
        const ro = new ResizeObserver(() => resize());
        if (box) ro.observe(box);

        unsubStroke = remoteStroke.subscribe((s) => {
            if (s) paint(s);
        });
        unsubClear = clearTick.subscribe(() => clearAll());

        const loop = () => {
            const now = Date.now();
            dots = Object.values(get(remoteLasers)).filter((d) => now - d.ts < 1600);
            raf = requestAnimationFrame(loop);
        };
        raf = requestAnimationFrame(loop);

        return () => ro.disconnect();
    });

    onDestroy(() => {
        unsubStroke?.();
        unsubClear?.();
        if (raf) cancelAnimationFrame(raf);
    });
</script>

<div class="atlas-draw-root" bind:this={box}>
    <canvas
        bind:this={canvas}
        class="atlas-draw-canvas"
        style={mode === "off" ? "pointer-events:none" : "pointer-events:auto; cursor:crosshair"}
        onpointerdown={onPointerDown}
        onpointermove={onPointerMove}
        onpointerup={onPointerUp}
        onpointerleave={onPointerUp}
    ></canvas>

    {#each dots as d (d.name)}
        <div class="atlas-laser" style="left:{d.x * 100}%; top:{d.y * 100}%; background:{d.color}; box-shadow:0 0 10px {d.color}">
            <span class="atlas-laser-name" style="color:{d.color}">{d.name}</span>
        </div>
    {/each}

    <div class="atlas-draw-toolbar">
        <button class:on={mode === "laser"} title="Laser (apontar)" onclick={() => toggle("laser")}>🔴</button>
        <button class:on={mode === "draw"} title="Desenhar" onclick={() => toggle("draw")}>✏️</button>
        {#each COLORS as c}
            <button class="sw" class:on={color === c} style="background:{c}" aria-label="cor" onclick={() => (color = c)}></button>
        {/each}
        <button title="Limpar" onclick={clearAndSend}>🧹</button>
    </div>
</div>

<style>
    .atlas-draw-root {
        position: absolute;
        inset: 0;
        pointer-events: none;
        z-index: 550;
    }
    .atlas-draw-canvas {
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
    }
    .atlas-draw-toolbar {
        position: absolute;
        top: 6px;
        left: 6px;
        display: flex;
        gap: 4px;
        pointer-events: auto;
        background: rgba(0, 0, 0, 0.5);
        padding: 4px;
        border-radius: 8px;
    }
    .atlas-draw-toolbar button {
        width: 26px;
        height: 26px;
        border: 0;
        border-radius: 6px;
        background: rgba(255, 255, 255, 0.14);
        cursor: pointer;
        font-size: 14px;
        line-height: 1;
        padding: 0;
    }
    .atlas-draw-toolbar button.on {
        outline: 2px solid #19c37d;
    }
    .atlas-laser {
        position: absolute;
        width: 14px;
        height: 14px;
        border-radius: 50%;
        transform: translate(-50%, -50%);
        pointer-events: none;
    }
    .atlas-laser-name {
        position: absolute;
        top: 10px;
        left: 10px;
        font-size: 10px;
        white-space: nowrap;
        text-shadow: 0 1px 2px #000;
    }
</style>
