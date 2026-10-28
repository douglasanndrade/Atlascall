"use strict";
/*
 * Atlas Call - Painel de Admin
 * Conecta no WebSocket de admin do WorkAdventure (/ws/admin/rooms), rastreia
 * presenca (quem esta online, ha quanto tempo online/offline), guarda logs,
 * cargos (CEO, Dono, Gestor de Trafego, Editor de Video...), expulsa e bane.
 * Sem dependencias npm: usa WebSocket nativo (Node >= 22), crypto e http.
 *
 * Cargos e bans sao guardados por NOME (minusculo), pois usuarios anonimos
 * recebem um uuid novo a cada sessao - o nome e o identificador estavel do time.
 *
 * Env:
 *   DOMAIN               ex: atlascall-atlascall.68tvlf.easypanel.host
 *   ADMIN_SOCKETS_TOKEN  segredo p/ assinar o JWT do socket de admin
 *   ADMIN_API_TOKEN      (opcional) token p/ descobrir salas via GET /rooms
 *   ROOM_IDS             (opcional) salas a monitorar, separadas por virgula
 *   ADMIN_PANEL_PASSWORD senha p/ entrar no painel
 *   PORT                 default 3000
 *   DATA_FILE            default /data/state.json
 */
const http = require("http");
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const DOMAIN = process.env.DOMAIN || "";
const ADMIN_SOCKETS_TOKEN = process.env.ADMIN_SOCKETS_TOKEN || "";
const ADMIN_API_TOKEN = process.env.ADMIN_API_TOKEN || "";
const ROOM_IDS = (process.env.ROOM_IDS || "").split(",").map((s) => s.trim()).filter(Boolean);
const ADMIN_PANEL_PASSWORD = process.env.ADMIN_PANEL_PASSWORD || "admin";
const PORT = parseInt(process.env.PORT || "3000", 10);
const DATA_FILE = process.env.DATA_FILE || "/data/state.json";

// cargos disponiveis (o 1o e o default). Cor por cargo no front.
const CARGOS = ["Membro", "Dono", "CEO", "Gestor de Trafego", "Editor de Video", "Social Media", "Suporte"];

// ---------------- state ----------------
/** users[uuid] = {uuid,name,ip,roomId,online,sessionStart,since,totalOnlineMs,firstSeen,lastSeen,joins} */
let users = {};
let logs = [];            // {t, type:'join'|'leave'|'kick'|'ban'|'unban'|'role', uuid, name, extra}
let roles = {};           // nameLower -> cargo
let banned = {};          // nameLower -> true

const nk = (name) => (name || "").trim().toLowerCase();

function loadState() {
    try {
        const raw = JSON.parse(fs.readFileSync(DATA_FILE, "utf-8"));
        users = raw.users || {};
        logs = raw.logs || [];
        roles = raw.roles || {};
        banned = raw.banned || {};
        const now = Date.now();
        for (const u of Object.values(users)) {
            if (u.online) {
                u.totalOnlineMs += Math.max(0, now - (u.sessionStart || now));
                u.online = false;
                u.since = now;
            }
        }
        console.log(`[state] carregado: ${Object.keys(users).length} usuarios, ${Object.keys(roles).length} cargos`);
    } catch {
        console.log("[state] comecando do zero");
    }
}
let saveTimer = null;
function saveState() {
    if (saveTimer) return;
    saveTimer = setTimeout(() => {
        saveTimer = null;
        try {
            fs.mkdirSync(path.dirname(DATA_FILE), { recursive: true });
            fs.writeFileSync(DATA_FILE, JSON.stringify({ users, logs: logs.slice(-500), roles, banned }));
        } catch (e) {
            console.error("[state] erro ao salvar", e.message);
        }
    }, 1000);
}

function addLog(type, uuid, name, extra) {
    logs.push({ t: Date.now(), type, uuid, name: name || uuid, extra: extra || "" });
    if (logs.length > 1000) logs = logs.slice(-1000);
}

function onJoin(d) {
    const now = Date.now();
    // bane de verdade: se o nome esta na lista de banidos, expulsa na hora
    if (banned[nk(d.name)]) {
        addLog("ban", d.uuid, d.name, "tentou entrar (banido)");
        sendBanned(d.uuid, d.roomId, "Voce esta banido deste escritorio.");
        saveState();
        return;
    }
    let u = users[d.uuid];
    if (!u) {
        u = users[d.uuid] = { uuid: d.uuid, name: d.name, ip: d.ipAddress, roomId: d.roomId,
            online: false, sessionStart: 0, since: now, totalOnlineMs: 0, firstSeen: now, lastSeen: now, joins: 0 };
    }
    u.name = d.name || u.name;
    u.ip = d.ipAddress || u.ip;
    u.roomId = d.roomId || u.roomId;
    if (!u.online) { // idempotente: reconexao nao reinicia sessao
        u.online = true;
        u.sessionStart = now;
        u.since = now;
        u.joins = (u.joins || 0) + 1;
        addLog("join", u.uuid, u.name);
    }
    u.lastSeen = now;
    saveState();
}
function onLeave(d) {
    const now = Date.now();
    const u = users[d.uuid];
    if (!u) return;
    if (u.online) {
        u.totalOnlineMs += Math.max(0, now - (u.sessionStart || now));
        u.online = false;
        u.since = now;
        u.lastSeen = now;
        addLog("leave", u.uuid, u.name);
    }
    saveState();
}

// ---------------- JWT (HS256) ----------------
function b64url(buf) {
    return Buffer.from(buf).toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function signAdminJwt(authorizedRoomIds) {
    const header = b64url(JSON.stringify({ alg: "HS256", typ: "JWT" }));
    const payload = b64url(JSON.stringify({ authorizedRoomIds }));
    const data = `${header}.${payload}`;
    const sig = b64url(crypto.createHmac("sha256", ADMIN_SOCKETS_TOKEN).update(data).digest());
    return `${data}.${sig}`;
}

// ---------------- admin socket ----------------
let adminWs = null;
let listened = new Set();
let authorized = new Set(ROOM_IDS);

function connectAdminSocket() {
    const url = `wss://${DOMAIN}/ws/admin/rooms`;
    console.log(`[ws] conectando em ${url}`);
    let ws;
    try {
        ws = new WebSocket(url);
    } catch (e) {
        console.error("[ws] WebSocket nativo indisponivel (precisa Node >=22):", e.message);
        setTimeout(connectAdminSocket, 5000);
        return;
    }
    adminWs = ws;
    listened = new Set();
    ws.addEventListener("open", () => {
        console.log("[ws] conectado");
        listenRooms([...authorized]);
    });
    ws.addEventListener("message", (ev) => {
        let msg;
        try { msg = JSON.parse(typeof ev.data === "string" ? ev.data : Buffer.from(ev.data).toString("utf-8")); }
        catch { return; }
        if (msg.type === "MemberJoin") onJoin(msg.data || {});
        else if (msg.type === "MemberLeave") onLeave(msg.data || {});
        else if (msg.type === "Error") console.error("[ws] erro do servidor:", msg.data && msg.data.message);
    });
    ws.addEventListener("close", (ev) => {
        console.warn(`[ws] fechado (${ev.code}). Reconectando em 5s`);
        adminWs = null;
        markAllOffline();
        setTimeout(connectAdminSocket, 5000);
    });
    ws.addEventListener("error", (e) => { console.error("[ws] erro:", e.message || e); });
}

function markAllOffline() {
    const now = Date.now();
    for (const u of Object.values(users)) {
        if (u.online) { u.totalOnlineMs += Math.max(0, now - (u.sessionStart || now)); u.online = false; u.since = now; }
    }
    saveState();
}

function listenRooms(roomIds) {
    if (!adminWs || adminWs.readyState !== 1) return;
    const fresh = roomIds.filter((r) => !listened.has(r));
    if (fresh.length === 0) return;
    for (const r of fresh) { authorized.add(r); listened.add(r); }
    const jwt = signAdminJwt([...authorized]);
    adminWs.send(JSON.stringify({ jwt, event: "listen", roomIds: fresh }));
    console.log(`[ws] ouvindo ${fresh.length} sala(s)`);
}

// discover rooms via GET /rooms (optional)
const https = require("https");
function discoverRooms() {
    if (!ADMIN_API_TOKEN) return;
    const r = https.request(
        { method: "GET", hostname: DOMAIN, path: "/rooms", headers: { authorization: ADMIN_API_TOKEN } },
        (res) => {
            let body = "";
            res.on("data", (c) => (body += c));
            res.on("end", () => {
                try {
                    const rooms = JSON.parse(body); // {roomId: nbUsers}
                    const ids = Object.keys(rooms);
                    if (ids.length) listenRooms(ids);
                } catch {}
            });
        }
    );
    r.on("error", () => {});
    r.end();
}

// ---------------- helpers ----------------
function fmtDur(ms) {
    if (ms < 0) ms = 0;
    const s = Math.floor(ms / 1000);
    const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60), ss = s % 60;
    if (d) return `${d}d ${h}h`;
    if (h) return `${h}h ${m}m`;
    if (m) return `${m}m ${ss}s`;
    return `${ss}s`;
}
function snapshot() {
    const now = Date.now();
    const list = Object.values(users).map((u) => ({
        uuid: u.uuid, name: u.name, ip: u.ip, online: u.online,
        cargo: roles[nk(u.name)] || "Membro",
        banned: !!banned[nk(u.name)],
        onlineFor: u.online ? now - u.sessionStart : 0,
        offlineFor: u.online ? 0 : now - u.since,
        totalOnline: u.totalOnlineMs + (u.online ? now - u.sessionStart : 0),
        joins: u.joins || 0, lastSeen: u.lastSeen,
    }));
    list.sort((a, b) => (b.online - a.online) || (b.lastSeen - a.lastSeen));
    return { now, cargos: CARGOS, users: list, online: list.filter((u) => u.online).length, total: list.length,
        banned: Object.keys(banned).length, logs: logs.slice(-100).reverse() };
}

// ---------------- auth ----------------
const AUTH_COOKIE = crypto.createHash("sha256").update("atlas:" + ADMIN_PANEL_PASSWORD).digest("hex");
function isAuthed(req) {
    const c = (req.headers.cookie || "").split(";").map((s) => s.trim());
    return c.includes("atlas_admin=" + AUTH_COOKIE);
}

// ---------------- acoes de moderacao ----------------
function sendBanned(uuid, roomId, message) {
    if (!adminWs || adminWs.readyState !== 1) return false;
    const rid = roomId || [...authorized][0] || "";
    const world = rid.split("/")[5] || "";
    const jwt = signAdminJwt([...authorized]);
    adminWs.send(JSON.stringify({ jwt, event: "banned", world,
        message: { userUuid: uuid, message: message || "Voce foi removido por um administrador." } }));
    return true;
}
// expulsar: desconecta agora (temporario - a pessoa pode voltar a entrar)
function kickUser(uuid) {
    const u = users[uuid];
    if (!u) return false;
    const ok = sendBanned(uuid, u.roomId, "Voce foi expulso por um administrador.");
    if (ok) { addLog("kick", uuid, u.name); saveState(); }
    return ok;
}
// banir: entra na lista (por nome) e nunca mais consegue ficar na sala
function setBan(name, on) {
    const key = nk(name);
    if (!key) return false;
    if (on) {
        banned[key] = true;
        // expulsa todas as sessoes online com esse nome
        for (const u of Object.values(users)) {
            if (nk(u.name) === key && u.online) sendBanned(u.uuid, u.roomId, "Voce esta banido deste escritorio.");
        }
        addLog("ban", "", name);
    } else {
        delete banned[key];
        addLog("unban", "", name);
    }
    saveState();
    return true;
}
// promover / mudar cargo (por nome)
function setRole(name, cargo) {
    const key = nk(name);
    if (!key) return false;
    if (cargo && cargo !== "Membro") roles[key] = cargo;
    else delete roles[key];
    addLog("role", "", name, cargo || "Membro");
    saveState();
    return true;
}

function readBody(req) {
    return new Promise((resolve) => {
        let body = "";
        req.on("data", (c) => (body += c));
        req.on("end", () => resolve(body));
    });
}

// ---------------- http server ----------------
const server = http.createServer(async (req, res) => {
    const u = new URL(req.url, "http://x");
    // login
    if (u.pathname === "/login" && req.method === "POST") {
        const body = await readBody(req);
        const params = new URLSearchParams(body);
        if (params.get("password") === ADMIN_PANEL_PASSWORD) {
            res.writeHead(302, { "Set-Cookie": `atlas_admin=${AUTH_COOKIE}; HttpOnly; Path=/; Max-Age=86400`, Location: "./" });
            res.end();
        } else {
            res.writeHead(302, { Location: "./?e=1" });
            res.end();
        }
        return;
    }
    if (!isAuthed(req)) {
        res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
        res.end(loginPage(u.searchParams.get("e")));
        return;
    }
    if (u.pathname === "/api/state") {
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify(snapshot()));
        return;
    }
    if (req.method === "POST" && u.pathname.startsWith("/api/")) {
        const body = await readBody(req);
        let p = {};
        try { p = JSON.parse(body); } catch {}
        let ok = false;
        if (u.pathname === "/api/kick") ok = kickUser(p.uuid);
        else if (u.pathname === "/api/ban") ok = setBan(p.name, true);
        else if (u.pathname === "/api/unban") ok = setBan(p.name, false);
        else if (u.pathname === "/api/role") ok = setRole(p.name, p.cargo);
        res.writeHead(ok ? 200 : 400, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ ok }));
        return;
    }
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    res.end(dashboardPage());
});

function loginPage(err) {
    return `<!doctype html><meta charset=utf-8><title>Atlas Call Admin</title>
<meta name=viewport content="width=device-width,initial-scale=1">
<style>body{font-family:system-ui;background:#0f1420;color:#e7ecf3;display:grid;place-items:center;height:100vh;margin:0}
form{background:#1a2234;padding:32px;border-radius:12px;width:280px}h1{font-size:18px;margin:0 0 16px}
input{width:100%;padding:10px;border-radius:8px;border:1px solid #2c3850;background:#0f1420;color:#fff;box-sizing:border-box}
button{width:100%;margin-top:12px;padding:10px;border:0;border-radius:8px;background:#19c37d;color:#042;font-weight:700;cursor:pointer}
.e{color:#ff7a7a;font-size:13px;margin-top:8px}</style>
<form method=post action="login"><h1>🛡️ Atlas Call — Admin</h1>
<input type=password name=password placeholder=Senha autofocus>
<button>Entrar</button>${err ? '<div class=e>Senha incorreta</div>' : ''}</form>`;
}

function dashboardPage() {
    return `<!doctype html><meta charset=utf-8><title>Atlas Call Admin</title>
<meta name=viewport content="width=device-width,initial-scale=1">
<style>
:root{color-scheme:dark}body{font-family:system-ui;background:#0f1420;color:#e7ecf3;margin:0;padding:16px}
h1{font-size:20px}h2{font-size:15px;color:#9fb0c8;margin:22px 0 8px}
.cards{display:flex;gap:12px;flex-wrap:wrap}.card{background:#1a2234;border-radius:10px;padding:14px 18px;min-width:110px}
.card .n{font-size:26px;font-weight:800}.card .l{color:#9fb0c8;font-size:12px}
table{width:100%;border-collapse:collapse;background:#1a2234;border-radius:10px;overflow:hidden}
th,td{text-align:left;padding:9px 12px;font-size:13px;border-bottom:1px solid #243049;vertical-align:middle}
th{color:#9fb0c8;font-weight:600}.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px}
.on{background:#19c37d}.off{background:#55637a}
.badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:700}
select{background:#0f1420;color:#e7ecf3;border:1px solid #2c3850;border-radius:6px;padding:4px 6px;font-size:12px}
button.act{border:0;border-radius:6px;padding:4px 9px;font-weight:700;cursor:pointer;font-size:12px;margin-left:4px}
.kick{background:#ffb14a;color:#3a2600}.ban{background:#ff5a5a;color:#300}.unban{background:#19c37d;color:#042}
.log{max-height:300px;overflow:auto;background:#1a2234;border-radius:10px;padding:8px 12px}
.log div{font-size:12px;padding:3px 0;color:#b9c6da}
.j{color:#19c37d}.lv{color:#ff9b6b}.k{color:#ffb14a}.b{color:#ff5a5a}.ub{color:#19c37d}.rl{color:#7aa2ff}
small.sub{color:#9fb0c8}
</style>
<h1>🛡️ Atlas Call — Painel de Admin</h1>
<div class=cards>
 <div class=card><div class="n" id=cOn>–</div><div class=l>Online agora</div></div>
 <div class=card><div class="n" id=cTot>–</div><div class=l>Pessoas (total)</div></div>
 <div class=card><div class="n" id=cBan>–</div><div class=l>Banidos</div></div>
</div>
<h2>👥 Usuários & Cargos</h2>
<table><thead><tr><th>Status</th><th>Nome</th><th>Cargo</th><th>Online</th><th>Offline</th><th>Total</th><th>Entradas</th><th>Ações</th></tr></thead>
<tbody id=rows></tbody></table>
<p><small class=sub>💡 <b>Expulsar</b> desconecta na hora (a pessoa pode voltar). <b>Banir</b> bloqueia o nome de vez (reentrou? é expulso automático). Mutar áudio/ouvir é feito dentro do app, clicando na bolha da pessoa (estilo Discord).</small></p>
<h2>📜 Logs de atividade</h2>
<div class="log" id=log></div>
<script>
var CARGOS=[], COLORS={'Dono':'#f4c542','CEO':'#f4c542','Gestor de Trafego':'#7aa2ff','Editor de Video':'#c08cff','Social Media':'#ff8cc8','Suporte':'#5ad1c4','Membro':'#55637a'};
function dur(ms){ms=Math.max(0,ms|0);var s=(ms/1000)|0,d=(s/86400)|0,h=((s%86400)/3600)|0,m=((s%3600)/60)|0,x=s%60;
 return d?d+'d '+h+'h':h?h+'h '+m+'m':m?m+'m '+x+'s':x+'s';}
function esc(t){return (t||'').replace(/[<>&"]/g,function(c){return{'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;'}[c];});}
function badge(c){var col=COLORS[c]||'#55637a';return '<span class=badge style="background:'+col+'22;color:'+col+'">'+esc(c)+'</span>';}
async function post(p,b){await fetch(p,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});load();}
function kick(uuid,name){if(confirm('Expulsar '+name+' agora? (pode voltar a entrar)'))post('api/kick',{uuid:uuid});}
function ban(name){if(confirm('BANIR '+name+' de vez? O nome fica bloqueado.'))post('api/ban',{name:name});}
function unban(name){post('api/unban',{name:name});}
function role(name,cargo){post('api/role',{name:name,cargo:cargo});}
async function load(){
 var s=await (await fetch('api/state')).json();
 CARGOS=s.cargos||CARGOS;
 cOn.textContent=s.online; cTot.textContent=s.total; cBan.textContent=s.banned;
 rows.innerHTML=s.users.map(function(u){
  var opts=CARGOS.map(function(c){return '<option'+(c===u.cargo?' selected':'')+'>'+esc(c)+'</option>';}).join('');
  var sel='<select onchange="role(\\''+esc(u.name)+'\\',this.value)">'+opts+'</select>';
  var acts='';
  if(u.online) acts+='<button class="act kick" onclick="kick(\\''+u.uuid+'\\',\\''+esc(u.name)+'\\')">Expulsar</button>';
  acts+= u.banned
    ? '<button class="act unban" onclick="unban(\\''+esc(u.name)+'\\')">Desbanir</button>'
    : '<button class="act ban" onclick="ban(\\''+esc(u.name)+'\\')">Banir</button>';
  return '<tr><td><span class="dot '+(u.online?'on':'off')+'"></span>'+(u.online?'Online':'Offline')+
   '</td><td>'+esc(u.name)+(u.banned?' 🚫':'')+'</td><td>'+badge(u.cargo)+' '+sel+
   '</td><td>'+(u.online?dur(u.onlineFor):'–')+'</td><td>'+(u.online?'–':dur(u.offlineFor))+
   '</td><td>'+dur(u.totalOnline)+'</td><td>'+u.joins+'</td><td style="white-space:nowrap">'+acts+'</td></tr>';}).join('');
 log.innerHTML=s.logs.map(function(l){var t=new Date(l.t).toLocaleString('pt-BR');
  var m={join:['j','entrou'],leave:['lv','saiu'],kick:['k','EXPULSO'],ban:['b','BANIDO'],unban:['ub','desbanido'],role:['rl','cargo → '+esc(l.extra||'')]};
  var e=m[l.type]||['','?'];
  return '<div><span class="'+e[0]+'">● '+esc(l.name)+' '+e[1]+'</span>'+(l.extra&&l.type!=='role'?' <small class=sub>('+esc(l.extra)+')</small>':'')+' — '+t+'</div>';}).join('');
}
load();setInterval(load,3000);
</script>`;
}

// ---------------- exports (para testes) ----------------
module.exports = { onJoin, onLeave, snapshot, kickUser, setBan, setRole, fmtDur, _state: () => ({ users, logs, roles, banned }) };

// ---------------- boot ----------------
if (require.main === module) {
    loadState();
    if (!DOMAIN || !ADMIN_SOCKETS_TOKEN) {
        console.error("[boot] FALTA env DOMAIN e/ou ADMIN_SOCKETS_TOKEN");
    }
    server.listen(PORT, () => console.log(`[http] painel em :${PORT}`));
    connectAdminSocket();
    if (ADMIN_API_TOKEN) { discoverRooms(); setInterval(discoverRooms, 20000); }
    setInterval(saveState, 30000);
}
