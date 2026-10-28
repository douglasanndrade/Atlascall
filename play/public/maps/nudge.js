// Atlas Call - Zumbido (chamar atencao estilo MSN)
// Adiciona um botao "Chamar atencao" na barra de acoes. Ao clicar, avisa TODOS
// os outros jogadores com o evento "atlas-nudge"; no jogo deles a tela treme e
// toca um som de alerta (isso e feito no core, em GameScene.ts).
WA.onInit()
    .then(() => {
        WA.ui.actionBar.addButton({
            id: "atlas-nudge",
            label: "📳 Chamar atenção",
            toolTip: "Dá um zumbido em todo mundo (treme a tela + som)",
            callback: () => {
                WA.event.broadcast("atlas-nudge", {
                    from: (WA.player && WA.player.name) || "Alguém",
                });
            },
        });
    })
    .catch((e) => console.error("[atlas-nudge] erro ao iniciar:", e));
