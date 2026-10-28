// Atlas Call - Zumbido (chamar atencao estilo MSN)
// Botao "Chamar atencao" na barra de acoes. Ao clicar, avisa TODOS os outros
// jogadores (evento "atlas-nudge"): no jogo deles a tela treme + toca o som
// (feito no core, GameScene.ts) e aparece um aviso dizendo QUEM chamou.
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

        // Mostra QUEM deu o zumbido (o treme + som vem do core).
        WA.event.on("atlas-nudge").subscribe((e) => {
            const from = (e && e.data && e.data.from) || "Alguém";
            WA.ui.banner.openBanner({
                id: "atlas-nudge-banner",
                text: "📳 " + from + " chamou sua atenção!",
                bgColor: "#19c37d",
                textColor: "#063",
                closable: true,
                timeToClose: 3500,
            });
        });
    })
    .catch((e) => console.error("[atlas-nudge] erro ao iniciar:", e));
