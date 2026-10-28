# Brief para o Codex — Módulo Admin do Atlas Call

> **Para quem é este documento:** um agente de código (Codex) que vai trabalhar
> **neste repositório**. Leia tudo antes de escrever qualquer linha.

---

## 1. O que é o projeto

**Atlas Call** é uma instância **self-hosted do WorkAdventure** (escritório
virtual 2D com vídeo/áudio por proximidade) para uma equipe de ~6 pessoas.
Monorepo TypeScript (npm workspaces). Foi rebrandeado de "WorkAdventure" para
"Atlas Call".

- Repo: `github.com/douglasanndrade/Atlascall` (branch `main`).
- Deploy: VPS DigitalOcean (IP `157.230.52.86`) via **EasyPanel** (serviço tipo
  Compose), arquivo `docker-compose.easypanel.yaml`. Produção:
  `https://atlascall-atlascall.68tvlf.easypanel.host/`.
- Serviços: `play` (frontend Svelte/Phaser + **pusher** Node + **Room API**),
  `back` (API Node), `map-storage`, `uploader`, `icon`, `redis`, `coturn` (TURN),
  `proxy` (nginx).

## 2. Estado atual (NÃO refazer)

Já está pronto e funcionando:
- ✅ Rebrand (strings i18n, meta tags, manifest, logo).
- ✅ Vídeo/áudio por proximidade entre redes diferentes (servidor TURN `coturn`).
- ✅ Chat de proximidade (`ENABLE_CHAT=true`).
- ✅ Jitsi REMOVIDO de propósito (o cliente não quer servidor de terceiros).
  As salas usam WebRTC por proximidade via TURN próprio. **Não reintroduza Jitsi.**

## 3. Divisão de trabalho (EVITE COLISÃO)

**O Claude (outro agente) está cuidando de — NÃO MEXA nestes:**
- `docker-compose.easypanel.yaml`, `deploy/**`, `nginx.conf` (infra/deploy).
- `map/**` e o mapa customizado (.tmj + tilesets LimeZu).
- As strings de rebrand/i18n em `play/src/i18n/**`.

**Você (Codex) é dono de:** o **Módulo Admin** (abaixo). Crie código novo, de
preferência num diretório/serviço novo, sem editar os arquivos acima.

## 4. Sua missão: Módulo Admin

O cliente quer um painel de admin com, por ordem de prioridade:

1. **Presença / tempo** — por usuário: há quanto tempo está **online** e há
   quanto tempo está **offline** (desde o último logout). Painel simples listando
   os membros com esses tempos, atualizando em tempo real.
2. **Moderação** — como admin: **expulsar** (kick / ban temporário), **banir**,
   e enviar aviso a um usuário.
3. **(Stretch, difícil)** mutar alguém para todos. ⚠️ Ver nota de dificuldade.

## 5. Pontos de extensão do WorkAdventure (onde plugar)

O WorkAdventure já expõe ganchos — **use-os, não reinvente**:

### a) Admin WebSocket (recomendado para presença + moderação)
- Controller: `play/src/pusher/controllers/AdminController.ts`
- Mensagens: `play/src/pusher/models/Websocket/Admin/AdminMessages.ts`
- Auth: `play/src/pusher/middlewares/AdminToken.ts` (env `ADMIN_SOCKETS_TOKEN`).
- Um cliente admin conecta num socket, **recebe eventos de join/leave** por sala
  (→ use para calcular tempo online/offline) e pode **enviar comandos** (banir,
  mandar mensagem a um usuário). É o caminho mais leve para presença + kick/ban.

### b) Room API (gRPC) — alternativa para presença/automação
- Server: `play/src/room-api/` · Client JS: `libs/room-api-clients/room-api-client-js`
- Env: `ROOM_API_SECRET_KEY`. Escuta eventos da sala e age (mover usuário, mensagem).

### c) Admin API HTTP (caminho "oficial" completo, mais trabalho)
- Interface: `play/src/pusher/services/AdminInterface.ts` (métodos: `banUserByUuid`,
  `reportPlayer`, `fetchMemberDataByUuid`, `getMember`, `searchMembers`,
  `getIceServers`, `saveName`, …).
- Implementação ativada por env `ADMIN_API_URL` (`AdminApi.ts`). Sem ela, usa o
  stub `LocalAdmin.ts`. Implementar um Admin API externo destrava member mgmt,
  ban, reports etc., mas exige servir TODA a interface que o pusher espera.

**Recomendação:** comece pelo **(a) Admin WebSocket** para presença + kick/ban +
um dashboard próprio (serviço novo, ex. `admin-panel/`). Evite (c) no começo.

## 6. Arquitetura sugerida

- Novo serviço `admin-panel/` (Node/TS + um front simples; SQLite ou Postgres
  para log de sessões = `{userUuid, name, connectedAt, disconnectedAt}`).
- Conecta como admin via Admin WebSocket (token `ADMIN_SOCKETS_TOKEN`), persiste
  join/leave, calcula online/offline em tempo real, expõe dashboard protegido por
  senha.
- Botões de moderação no dashboard chamam os comandos de ban/mensagem do socket.
- Adicione o serviço ao `docker-compose.easypanel.yaml` **propondo um patch ao
  Claude** (não edite o compose direto — ver Seção 3). Documente as novas envs.

## 7. Regras / guardrails (OBRIGATÓRIO)

- **Segredos NUNCA no repo.** Toda credencial (tokens, senhas) vai no `.env` do
  EasyPanel. No código, só referencie via `${VAR}` / `process.env`.
- **Não renomeie** o namespace dos pacotes (`@workadventure/*`), identificadores
  da Scripting API, nem **chaves** de i18n (só valores já foram traduzidos).
- **Não quebre o deploy.** O `play` é buildado do fonte; mudança que não compila
  derruba produção. Rode build/lint/typecheck antes de concluir.
- Siga `AGENTS.md` e `docs/agent/*` (estilo TS, lint, testes Vitest).
- Honestidade: a moderação "mutar alguém para todos" é **difícil** — o áudio de
  proximidade é P2P, não há mute global nativo; ban/kick sim. Deixe claro o que
  entregou de verdade; não finja feature que não funciona.

## 8. Primeiro milestone sugerido

1. Ler `AdminController.ts` + `AdminMessages.ts` e mapear os eventos de join/leave
   e os comandos de ban disponíveis.
2. Protótipo: serviço que conecta no Admin WebSocket e **loga no console** quem
   entrou/saiu de uma sala (prova que a presença funciona).
3. Depois: persistência + dashboard de tempo online/offline.
4. Por último: botões de kick/ban.

Entregue em etapas, com um resumo honesto do que funciona de verdade a cada passo.
