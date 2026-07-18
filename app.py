import base64
import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from schedule_data import PLAYER_PINS, SCHEDULE

APP_NAME = "Quiniela Joan Santos"
DB_PATH = Path(__file__).with_name("quiniela.db")
ASSETS = Path(__file__).with_name("assets")
TZ = ZoneInfo("America/Mexico_City")

# El organizador aparece primero, como se solicitó.
PLAYERS = [
    ("CAZ", "Joan Santos", "Cruz Azul"),
    ("TOL", "Diego", "Toluca"),
    ("TIG", "Lupe", "Tigres UANL"),
    ("AME", "Oscar", "América"),
    ("CHI", "Pity", "Guadalajara"),
    ("ATL", "Sholko", "Atlante"),
    ("MTY", "José Luis", "Monterrey"),
    ("ATS", "Lugo", "Atlas"),
    ("JUA", "Jorge Ceballos", "Juárez"),
    ("PUE", "Giovanni Román", "Puebla"),
    ("SAN", "José Juan", "Santos Laguna"),
    ("PUM", "Ricky Zazueta", "Pumas UNAM"),
    ("NEC", "Sebastián", "Necaxa"),
    ("QRO", "Juan Antonio", "Querétaro"),
    ("LEO", "Roger", "León"),
    ("TIJ", "Laura", "Tijuana"),
    ("SLP", "Chino Terrazas", "Atlético de San Luis"),
    ("PAC", "Rodolfo Félix", "Pachuca"),
]

TEAM_SHORT = {
    "Atlético de San Luis": "San Luis", "Guadalajara": "Chivas",
    "Pumas UNAM": "Pumas", "Santos Laguna": "Santos", "Tigres UANL": "Tigres",
}
TEAM_SLUG = {
    "Toluca":"toluca", "Tigres UANL":"tigres-uanl", "América":"america", "Guadalajara":"guadalajara",
    "Atlante":"atlante", "Monterrey":"monterrey", "Atlas":"atlas", "Juárez":"juarez", "Puebla":"puebla",
    "Cruz Azul":"cruz-azul", "Santos Laguna":"santos-laguna", "Pumas UNAM":"pumas-unam", "Necaxa":"necaxa",
    "Querétaro":"queretaro", "León":"leon", "Tijuana":"tijuana", "Atlético de San Luis":"atletico-de-san-luis",
    "Pachuca":"pachuca",
}
ALL_TEAMS = sorted({team for games in SCHEDULE.values() for _, home, away in games for team in (home, away)})


def hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()


def conn():
    connection = sqlite3.connect(DB_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def now_local() -> datetime:
    return datetime.now(TZ).replace(tzinfo=None)


def team_logo(team: str) -> Path:
    return ASSETS / "team_logos" / f"{TEAM_SLUG.get(team, 'generic')}.svg"


def init_db():
    with conn() as c:
        c.executescript("""
        PRAGMA foreign_keys = ON;
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY, code TEXT UNIQUE, name TEXT, team TEXT,
            pin_hash TEXT, is_admin INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS rounds(
            id INTEGER PRIMARY KEY, number INTEGER UNIQUE, name TEXT,
            deadline TEXT, is_open INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS matches(
            id INTEGER PRIMARY KEY, round_id INTEGER, home_team TEXT, away_team TEXT,
            kickoff TEXT, home_score INTEGER, away_score INTEGER,
            UNIQUE(round_id, home_team, away_team)
        );
        CREATE TABLE IF NOT EXISTS predictions(
            id INTEGER PRIMARY KEY, user_id INTEGER, match_id INTEGER,
            home_score INTEGER, away_score INTEGER, submitted_at TEXT,
            UNIQUE(user_id, match_id)
        );
        CREATE TABLE IF NOT EXISTS survivor_picks(
            id INTEGER PRIMARY KEY, user_id INTEGER, round_id INTEGER,
            team TEXT, submitted_at TEXT,
            UNIQUE(user_id, round_id), UNIQUE(user_id, team)
        );
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS champion_eligible(team TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS champion_picks(
            id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE, team TEXT UNIQUE,
            pick_order INTEGER, submitted_at TEXT
        );
        """)
        c.execute(
            "INSERT OR IGNORE INTO users(code,name,team,pin_hash,is_admin) VALUES(?,?,?,?,1)",
            ("ADMIN", "Administrador", "", hash_pin("2026")),
        )
        for code, name, team in PLAYERS:
            # INSERT OR IGNORE evita restablecer el PIN en cada reinicio.
            c.execute(
                "INSERT OR IGNORE INTO users(code,name,team,pin_hash,is_admin) VALUES(?,?,?,?,0)",
                (code, name, team, hash_pin(PLAYER_PINS[code])),
            )
            c.execute("UPDATE users SET name=?, team=? WHERE code=?", (name, team, code))
        for number, games in SCHEDULE.items():
            deadline = min(datetime.fromisoformat(game[0]) for game in games).isoformat(timespec="minutes")
            c.execute(
                "INSERT OR IGNORE INTO rounds(number,name,deadline,is_open) VALUES(?,?,?,0)",
                (number, f"Jornada {number}", deadline),
            )
            round_id = c.execute("SELECT id FROM rounds WHERE number=?", (number,)).fetchone()[0]
            for kickoff, home, away in games:
                c.execute(
                    "INSERT OR IGNORE INTO matches(round_id,home_team,away_team,kickoff) VALUES(?,?,?,?)",
                    (round_id, home, away, kickoff),
                )
        c.execute("INSERT OR IGNORE INTO settings VALUES('champion_draft_active','0')")


def inject_style():
    st.markdown("""
    <style>
    :root{
      --mx-green:#00a859; --mx-pink:#e5007d; --mx-navy:#071a33;
      --mx-blue:#0d315b; --mx-bg:#f4f7fb; --mx-card:#ffffff;
      --mx-text:#142033; --mx-muted:#64748b; --mx-border:#dbe4ef;
    }
    .stApp{background:var(--mx-bg);color:var(--mx-text)}
    [data-testid="stHeader"]{background:rgba(244,247,251,.94)}
    .block-container{max-width:1120px;padding-top:.75rem;padding-bottom:4rem}
    h1,h2,h3,p,label,.stMarkdown,.stCaption{color:var(--mx-text)}
    .hero{position:relative;overflow:hidden;display:flex;align-items:center;gap:16px;padding:18px 20px;margin-bottom:18px;
      background:linear-gradient(120deg,var(--mx-navy),var(--mx-blue));border-radius:22px;border-bottom:5px solid var(--mx-green)}
    .hero:after{content:"";position:absolute;right:-34px;top:-52px;width:170px;height:170px;border:28px solid rgba(229,0,125,.28);border-radius:50%}
    .hero img{width:78px;height:78px;z-index:1}.hero h1{margin:0;color:white;font-size:clamp(1.55rem,4vw,2.45rem)}
    .hero p{margin:4px 0 0;color:#dbeafe}.hero .tag{display:inline-block;margin-top:8px;padding:4px 10px;border-radius:999px;background:var(--mx-green);color:white;font-size:.78rem;font-weight:800}
    .login-shell{max-width:560px;margin:0 auto}.profile-card{display:flex;align-items:center;gap:14px;background:white;border:1px solid var(--mx-border);border-left:6px solid var(--mx-green);border-radius:18px;padding:15px 17px;margin:10px 0 16px}
    .profile-card img{width:70px;height:70px}.profile-card .name{font-size:1.15rem;font-weight:900}.profile-card .sub{color:var(--mx-muted)}
    .section-note{background:#eefaf5;border:1px solid #bdebd4;border-radius:14px;padding:11px 13px;color:#075f43;font-weight:700}
    .match-title{text-align:center;font-size:.82rem;color:var(--mx-muted);font-weight:800;margin-bottom:4px}
    .team-name{text-align:center;font-weight:900;font-size:.92rem;line-height:1.1;margin-top:4px;color:var(--mx-text)}
    .score-sep{text-align:center;font-size:1.65rem;font-weight:900;color:var(--mx-pink)}
    .privacy-lock{background:#fff6fb;border:1px solid #f5bddc;border-radius:14px;padding:12px;color:#8b1455}
    [data-testid="stVerticalBlockBorderWrapper"]{background:var(--mx-card);border-color:var(--mx-border)!important;border-radius:18px!important;box-shadow:0 4px 14px rgba(7,26,51,.055)}
    div[data-testid="stMetric"]{background:white;border:1px solid var(--mx-border);padding:12px;border-radius:15px}
    div[data-testid="stMetricLabel"] p{color:var(--mx-muted)!important}div[data-testid="stMetricValue"]{color:var(--mx-navy)!important}
    .stButton>button,.stDownloadButton>button{border-radius:12px;font-weight:850;min-height:44px}
    .stButton>button[kind="primary"]{background:var(--mx-green);border-color:var(--mx-green);color:white}
    div[data-baseweb="select"]>div,input{background:white!important;color:var(--mx-text)!important;border-color:#b8c7d9!important}
    [data-testid="stNumberInput"] input{text-align:center;font-size:1.35rem;font-weight:900;color:var(--mx-navy)!important;min-height:50px}
    [data-baseweb="tab-list"]{gap:5px;background:#e7edf5;padding:5px;border-radius:14px;overflow-x:auto}
    [data-baseweb="tab"]{border-radius:10px;color:var(--mx-text);white-space:nowrap}[aria-selected="true"]{background:white!important;color:var(--mx-navy)!important}
    [data-testid="stDataFrame"]{background:white;border-radius:14px;overflow:hidden}.stAlert{border-radius:14px}
    @media(max-width:640px){.block-container{padding-left:.65rem;padding-right:.65rem}.hero{padding:13px}.hero img{width:58px;height:58px}.team-name{font-size:.76rem}.profile-card img{width:58px;height:58px}[data-testid="stNumberInput"] input{font-size:1.1rem}.stTabs [data-baseweb="tab"]{font-size:.75rem;padding-left:7px;padding-right:7px}}
    </style>
    """, unsafe_allow_html=True)


def brand():
    logo = (ASSETS / "quiniela_logo.svg").read_text(encoding="utf-8")
    data = base64.b64encode(logo.encode("utf-8")).decode("ascii")
    st.markdown(
        f'<div class="hero"><img src="data:image/svg+xml;base64,{data}" alt="Balón de la quiniela">'
        f'<div><h1>{APP_NAME}</h1><p>Apertura 2026</p><span class="tag">Quiniela · Survivor · Duelos</span></div></div>',
        unsafe_allow_html=True,
    )


def result_type(home, away):
    if home is None or away is None:
        return None
    return "L" if home > away else "V" if home < away else "E"


def score_prediction(ph, pa, rh, ra):
    if rh is None or ra is None:
        return 0
    if (ph, pa) == (rh, ra):
        return 2
    return 1 if result_type(ph, pa) == result_type(rh, ra) else 0


def show_team(column, team, width=72):
    with column:
        st.image(str(team_logo(team)), width=width)
        st.markdown(f'<div class="team-name">{TEAM_SHORT.get(team, team)}</div>', unsafe_allow_html=True)


def match_score_card(match, previous=None, locked=False, prefix="p"):
    with st.container(border=True):
        kickoff = datetime.fromisoformat(match["kickoff"]).strftime("%d %b · %H:%M")
        st.markdown(f'<div class="match-title">{kickoff}</div>', unsafe_allow_html=True)
        c1, c2, c3, c4, c5 = st.columns([1.25, .72, .25, .72, 1.25], vertical_alignment="center")
        show_team(c1, match["home_team"])
        home = c2.number_input(
            f"Goles {match['home_team']}", min_value=0, max_value=20,
            value=int(previous["home_score"]) if previous else 0,
            key=f"{prefix}h{match['id']}", disabled=locked, label_visibility="collapsed",
        )
        c3.markdown('<div class="score-sep">–</div>', unsafe_allow_html=True)
        away = c4.number_input(
            f"Goles {match['away_team']}", min_value=0, max_value=20,
            value=int(previous["away_score"]) if previous else 0,
            key=f"{prefix}a{match['id']}", disabled=locked, label_visibility="collapsed",
        )
        show_team(c5, match["away_team"])
        return home, away


def standings():
    with conn() as c:
        users = c.execute("SELECT id,name,team FROM users WHERE is_admin=0").fetchall()
        rows = c.execute("""
            SELECT p.user_id,r.number jornada,p.home_score ph,p.away_score pa,
                   m.home_score rh,m.away_score ra
            FROM predictions p JOIN matches m ON m.id=p.match_id
            JOIN rounds r ON r.id=m.round_id
        """).fetchall()
    data = {u["id"]: {"USER_ID":u["id"], "JUGADOR":u["name"], "EQUIPO":TEAM_SHORT.get(u["team"],u["team"]), "TOTAL":0} for u in users}
    for row in rows:
        points = score_prediction(row["ph"], row["pa"], row["rh"], row["ra"])
        column = f"J{row['jornada']}"
        data[row["user_id"]][column] = data[row["user_id"]].get(column, 0) + points
        data[row["user_id"]]["TOTAL"] += points
    df = pd.DataFrame(data.values()).fillna(0)
    journeys = sorted([x for x in df.columns if x.startswith("J")], key=lambda x:int(x[1:]))
    df = df[["USER_ID","JUGADOR","EQUIPO","TOTAL"] + journeys].sort_values(["TOTAL","JUGADOR"], ascending=[False,True]).reset_index(drop=True)
    df.insert(0, "POS", range(1, len(df)+1))
    return df


def round_submission_status(round_id):
    with conn() as c:
        total_matches = c.execute("SELECT COUNT(*) FROM matches WHERE round_id=?", (round_id,)).fetchone()[0]
        users = c.execute("SELECT id,name FROM users WHERE is_admin=0 ORDER BY name").fetchall()
        counts = {row["user_id"]: row["n"] for row in c.execute("""
            SELECT p.user_id, COUNT(*) n FROM predictions p
            JOIN matches m ON m.id=p.match_id WHERE m.round_id=? GROUP BY p.user_id
        """, (round_id,)).fetchall()}
    rows = [{"JUGADOR":u["name"], "CAPTURADOS":counts.get(u["id"],0), "TOTAL":total_matches,
             "ESTADO":"Listo" if counts.get(u["id"],0)==total_matches else "Pendiente"} for u in users]
    complete = bool(total_matches and all(r["CAPTURADOS"] == total_matches for r in rows))
    return rows, complete


def public_predictions(round_id):
    status, complete = round_submission_status(round_id)
    if not complete:
        ready = sum(1 for row in status if row["ESTADO"] == "Listo")
        st.markdown(
            f'<div class="privacy-lock">🔒 Los pronósticos se mostrarán cuando los 18 participantes terminen. '
            f'Avance actual: <b>{ready}/18</b>.</div>', unsafe_allow_html=True,
        )
        return
    with conn() as c:
        matches = c.execute("SELECT * FROM matches WHERE round_id=? ORDER BY kickoff", (round_id,)).fetchall()
        users = c.execute("SELECT id,name FROM users WHERE is_admin=0").fetchall()
        predictions = c.execute("""
            SELECT p.user_id,p.match_id,p.home_score,p.away_score FROM predictions p
            JOIN matches m ON m.id=p.match_id WHERE m.round_id=?
        """, (round_id,)).fetchall()
    lookup = {(p["user_id"], p["match_id"]):(p["home_score"],p["away_score"]) for p in predictions}
    rows = []
    for user in users:
        row = {"PARTICIPANTE":user["name"]}
        for i, match in enumerate(matches, 1):
            score = lookup.get((user["id"], match["id"]))
            row[f"P{i}"] = f"{score[0]}-{score[1]}" if score else "—"
        rows.append(row)
    st.success("Todos terminaron. Los pronósticos ya son visibles para el grupo.")
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    with st.expander("Ver qué partido corresponde a P1, P2, P3…"):
        st.dataframe(pd.DataFrame([
            {"PARTIDO":f"P{i}", "ENCUENTRO":f"{TEAM_SHORT.get(m['home_team'],m['home_team'])} vs {TEAM_SHORT.get(m['away_team'],m['away_team'])}"}
            for i,m in enumerate(matches,1)
        ]), hide_index=True, use_container_width=True)


def login():
    brand()
    st.markdown('<div class="login-shell">', unsafe_allow_html=True)
    st.subheader("Iniciar sesión")
    options = [(code,name,team) for code,name,team in PLAYERS] + [("ADMIN","Administrador","")]
    labels = [name for _,name,_ in options]
    selected_name = st.selectbox("Tu nombre", labels)
    code, name, team = next(item for item in options if item[1] == selected_name)
    if code != "ADMIN":
        logo = team_logo(team)
        logo_data = base64.b64encode(logo.read_bytes()).decode("ascii")
        st.markdown(
            f'<div class="profile-card"><img src="data:image/svg+xml;base64,{logo_data}" alt="{team}">'
            f'<div><div class="name">{name}</div><div class="sub">Equipo de duelos: {TEAM_SHORT.get(team,team)}</div></div></div>',
            unsafe_allow_html=True,
        )
    pin = st.text_input("PIN personal", type="password", placeholder="Escribe tu PIN")
    if st.button("Entrar", type="primary", use_container_width=True):
        with conn() as c:
            user = c.execute("SELECT * FROM users WHERE code=? AND pin_hash=?", (code, hash_pin(pin))).fetchone()
        if user:
            st.session_state.user = dict(user)
            st.rerun()
        else:
            st.error("El nombre o el PIN no son correctos.")
    st.caption("Cada participante tiene un PIN diferente. No lo compartas.")
    st.markdown('</div>', unsafe_allow_html=True)


def round_points(user_id, journey):
    with conn() as c:
        rows = c.execute("""
            SELECT p.home_score ph,p.away_score pa,m.home_score rh,m.away_score ra
            FROM predictions p JOIN matches m ON m.id=p.match_id JOIN rounds r ON r.id=m.round_id
            WHERE p.user_id=? AND r.number=?
        """, (user_id, journey)).fetchall()
    return sum(score_prediction(x["ph"],x["pa"],x["rh"],x["ra"]) for x in rows)


def round_complete(journey):
    with conn() as c:
        row = c.execute("""
            SELECT COUNT(*) n,SUM(CASE WHEN m.home_score IS NOT NULL AND m.away_score IS NOT NULL THEN 1 ELSE 0 END) d
            FROM matches m JOIN rounds r ON r.id=m.round_id WHERE r.number=?
        """, (journey,)).fetchone()
    return bool(row["n"] and row["n"] == row["d"])


def duels_round(journey):
    with conn() as c:
        users = {u["team"]:u for u in c.execute("SELECT id,name,team FROM users WHERE is_admin=0")}
        games = c.execute("""SELECT m.home_team,m.away_team FROM matches m JOIN rounds r ON r.id=m.round_id
                             WHERE r.number=? ORDER BY m.id""", (journey,)).fetchall()
    output = []
    complete = round_complete(journey)
    for game in games:
        home, away = users.get(game["home_team"]), users.get(game["away_team"])
        if not home or not away:
            continue
        hp, ap = round_points(home["id"],journey), round_points(away["id"],journey)
        if not complete: hd=ad=0; result="Pendiente"
        elif hp>ap: hd,ad,result=3,0,home["name"]
        elif hp<ap: hd,ad,result=0,3,away["name"]
        else: hd,ad,result=1,1,"Empate"
        output.append({"J":journey,"LOCAL":home["name"],"VISITANTE":away["name"],"QUINIELA":f"{hp}-{ap}","DUELO":f"{hd}-{ad}","RESULTADO":result})
    return output


def duel_standings():
    data = {name:{"JUGADOR":name,"EQUIPO":TEAM_SHORT.get(team,team),"PTS":0,"JG":0,"JE":0,"JP":0} for _,name,team in PLAYERS}
    for journey in range(1,18):
        if not round_complete(journey): continue
        for row in duels_round(journey):
            a,b=row["LOCAL"],row["VISITANTE"]
            pa,pb=map(int,row["DUELO"].split("-")); data[a]["PTS"]+=pa; data[b]["PTS"]+=pb
            if pa==3: data[a]["JG"]+=1; data[b]["JP"]+=1
            elif pb==3: data[b]["JG"]+=1; data[a]["JP"]+=1
            else: data[a]["JE"]+=1; data[b]["JE"]+=1
    df=pd.DataFrame(data.values()).sort_values(["PTS","JG","JUGADOR"],ascending=[False,False,True]).reset_index(drop=True)
    df.insert(0,"POS",range(1,len(df)+1)); return df


def survivor_status():
    with conn() as c:
        users=c.execute("SELECT id,name FROM users WHERE is_admin=0").fetchall()
        picks=c.execute("""SELECT sp.user_id,sp.team,m.home_team,m.away_team,m.home_score,m.away_score
                           FROM survivor_picks sp JOIN rounds r ON r.id=sp.round_id
                           LEFT JOIN matches m ON m.round_id=r.id AND (m.home_team=sp.team OR m.away_team=sp.team)""").fetchall()
    data={u["id"]:{"JUGADOR":u["name"],"VIDAS":3.0,"ELECCIONES":0} for u in users}
    for row in picks:
        data[row["user_id"]]["ELECCIONES"]+=1
        if row["home_score"] is None: continue
        gf=row["home_score"] if row["team"]==row["home_team"] else row["away_score"]
        ga=row["away_score"] if row["team"]==row["home_team"] else row["home_score"]
        data[row["user_id"]]["VIDAS"]-=1 if gf<ga else (.5 if gf==ga else 0)
    df=pd.DataFrame(data.values()).sort_values(["VIDAS","JUGADOR"],ascending=[False,True]).reset_index(drop=True)
    df.insert(0,"POS",range(1,len(df)+1)); return df


def survivor_pick(user, round_row, locked):
    with conn() as c:
        used=[x["team"] for x in c.execute("SELECT team FROM survivor_picks WHERE user_id=?",(user["id"],))]
        old=c.execute("SELECT team FROM survivor_picks WHERE user_id=? AND round_id=?",(user["id"],round_row["id"])).fetchone()
        matches=c.execute("SELECT home_team,away_team FROM matches WHERE round_id=?",(round_row["id"],)).fetchall()
    teams=sorted({t for match in matches for t in (match["home_team"],match["away_team"])})
    available=[t for t in teams if t not in used or (old and t==old["team"])]
    st.caption("Gana: conserva vidas · Empata: pierde 0.5 · Pierde: pierde 1 · No se repiten equipos.")
    if not available:
        st.warning("No tienes equipos disponibles."); return
    pick=st.selectbox("Elige tu equipo Survivor",available,format_func=lambda x:TEAM_SHORT.get(x,x),disabled=locked)
    center=st.columns([1,1,1])[1]
    center.image(str(team_logo(pick)),width=96)
    center.markdown(f'<div class="team-name">{TEAM_SHORT.get(pick,pick)}</div>',unsafe_allow_html=True)
    if st.button("Guardar Survivor",type="primary",disabled=locked,use_container_width=True):
        try:
            with conn() as c:
                c.execute("""INSERT INTO survivor_picks(user_id,round_id,team,submitted_at) VALUES(?,?,?,?)
                             ON CONFLICT(user_id,round_id) DO UPDATE SET team=excluded.team,submitted_at=excluded.submitted_at""",
                          (user["id"],round_row["id"],pick,now_local().isoformat()))
            st.success("Elección guardada.")
        except sqlite3.IntegrityError:
            st.error("Ese equipo ya fue utilizado.")


def champion_order():
    return standings().head(8)[["POS","USER_ID","JUGADOR","TOTAL"]]


def champion_view(user=None, admin=False):
    with conn() as c:
        active=c.execute("SELECT value FROM settings WHERE key='champion_draft_active'").fetchone()["value"]=="1"
        eligible=[x["team"] for x in c.execute("SELECT team FROM champion_eligible")]
        picks=c.execute("""SELECT cp.pick_order,u.id user_id,u.name,cp.team FROM champion_picks cp
                           JOIN users u ON u.id=cp.user_id ORDER BY cp.pick_order""").fetchall()
    if picks:
        st.dataframe(pd.DataFrame([{"TURNO":x["pick_order"],"JUGADOR":x["name"],"CAMPEÓN":TEAM_SHORT.get(x["team"],x["team"])} for x in picks]),hide_index=True,use_container_width=True)
    if not active: st.info("La selección de campeón todavía no está activa."); return
    if len(picks)>=8: st.success("La selección terminó."); return
    order=champion_order(); picked_ids={x["user_id"] for x in picks}; picked_teams={x["team"] for x in picks}
    nxt=order[~order.USER_ID.isin(picked_ids)].iloc[0]
    st.write(f"Turno actual: **#{int(nxt.POS)} {nxt.JUGADOR}**")
    if admin: return
    if user["id"] not in set(order.USER_ID): st.warning("Solo participan los primeros 8."); return
    if user["id"] in picked_ids: st.success("Ya elegiste."); return
    if user["id"]!=int(nxt.USER_ID): st.warning("Todavía no es tu turno."); return
    available=[t for t in eligible if t not in picked_teams]
    if not available: st.error("El administrador debe cargar los equipos elegibles."); return
    team=st.selectbox("Equipo campeón",available,format_func=lambda x:TEAM_SHORT.get(x,x))
    if st.button("Confirmar campeón",type="primary",use_container_width=True):
        with conn() as c:
            c.execute("INSERT INTO champion_picks(user_id,team,pick_order,submitted_at) VALUES(?,?,?,?)",(user["id"],team,len(picks)+1,now_local().isoformat()))
        st.rerun()


def player_view(user):
    logo_data=base64.b64encode(team_logo(user["team"]).read_bytes()).decode("ascii")
    st.markdown(f'<div class="profile-card"><img src="data:image/svg+xml;base64,{logo_data}" alt="{user["team"]}"><div><div class="name">{user["name"]}</div><div class="sub">Equipo de duelos: {TEAM_SHORT.get(user["team"],user["team"])}</div></div></div>',unsafe_allow_html=True)
    table=standings(); me=table[table.JUGADOR==user["name"]].iloc[0]
    duel_df=duel_standings(); duel=duel_df[duel_df["JUGADOR"]==user["name"]].iloc[0]
    survivor_df=survivor_status(); survivor=survivor_df[survivor_df["JUGADOR"]==user["name"]].iloc[0]
    a,b,c,d=st.columns(4); a.metric("Posición",f"#{int(me.POS)}"); b.metric("Puntos",int(me.TOTAL)); c.metric("Duelos",int(duel.PTS)); d.metric("Vidas",f"{survivor.VIDAS:g}")
    tabs=st.tabs(["Pronósticos","Grupo","Survivor","Tabla","Duelos","Campeón"])
    with tabs[0]:
        with conn() as c: rounds=c.execute("SELECT * FROM rounds ORDER BY number").fetchall()
        choices={f"Jornada {r['number']}":r for r in rounds}; round_row=choices[st.selectbox("Jornada",list(choices))]
        locked=not round_row["is_open"] or now_local()>datetime.fromisoformat(round_row["deadline"])
        st.markdown(f'<div class="section-note">{"🟢 Jornada abierta" if not locked else "🔒 Jornada cerrada"}</div>',unsafe_allow_html=True)
        with conn() as c:
            matches=c.execute("SELECT * FROM matches WHERE round_id=? ORDER BY kickoff",(round_row["id"],)).fetchall()
            previous={x["match_id"]:x for x in c.execute("SELECT * FROM predictions WHERE user_id=?",(user["id"],))}
        values=[]
        for match in matches:
            h,a=match_score_card(match,previous.get(match["id"]),locked,prefix=f"j{round_row['number']}_")
            values.append((match["id"],h,a))
        if st.button("Guardar todos mis pronósticos",type="primary",disabled=locked,use_container_width=True):
            with conn() as c:
                for match_id,h,a in values:
                    c.execute("""INSERT INTO predictions(user_id,match_id,home_score,away_score,submitted_at) VALUES(?,?,?,?,?)
                                 ON CONFLICT(user_id,match_id) DO UPDATE SET home_score=excluded.home_score,away_score=excluded.away_score,submitted_at=excluded.submitted_at""",
                              (user["id"],match_id,h,a,now_local().isoformat()))
            st.success("Tus pronósticos quedaron guardados.")
    with tabs[1]:
        with conn() as c: rounds=c.execute("SELECT * FROM rounds ORDER BY number").fetchall()
        choices={f"Jornada {r['number']}":r for r in rounds}; round_row=choices[st.selectbox("Pronósticos del grupo",list(choices))]
        public_predictions(round_row["id"])
    with tabs[2]:
        with conn() as c: rounds=c.execute("SELECT * FROM rounds ORDER BY number").fetchall()
        choices={f"Jornada {r['number']}":r for r in rounds}; round_row=choices[st.selectbox("Jornada Survivor",list(choices))]
        locked=not round_row["is_open"] or now_local()>datetime.fromisoformat(round_row["deadline"])
        survivor_pick(user,round_row,locked); st.dataframe(survivor_status(),hide_index=True,use_container_width=True)
    with tabs[3]: st.dataframe(table.drop(columns=["USER_ID"]),hide_index=True,use_container_width=True)
    with tabs[4]:
        st.dataframe(duel_standings(),hide_index=True,use_container_width=True)
        journey=st.selectbox("Detalle de jornada",range(1,18)); st.dataframe(pd.DataFrame(duels_round(journey)),hide_index=True,use_container_width=True)
    with tabs[5]: champion_view(user=user)


def admin_view():
    tabs=st.tabs(["Resultados","Jornadas","Entregas","Participantes","Tabla","Duelos","Survivor","Campeón"])
    with tabs[0]:
        with conn() as c: matches=c.execute("""SELECT m.*,r.number FROM matches m JOIN rounds r ON r.id=m.round_id ORDER BY r.number,m.kickoff""").fetchall()
        options={f"J{x['number']} · {TEAM_SHORT.get(x['home_team'],x['home_team'])} vs {TEAM_SHORT.get(x['away_team'],x['away_team'])}":x for x in matches}
        match=options[st.selectbox("Partido",list(options))]
        current={"home_score":int(match["home_score"] or 0),"away_score":int(match["away_score"] or 0)}
        home,away=match_score_card(match,current,False,prefix="admin_")
        if st.button("Guardar resultado oficial",type="primary",use_container_width=True):
            with conn() as c: c.execute("UPDATE matches SET home_score=?,away_score=? WHERE id=?",(home,away,match["id"]))
            st.success("Resultado guardado.")
    with tabs[1]:
        with conn() as c: rounds=c.execute("SELECT * FROM rounds ORDER BY number").fetchall()
        for round_row in rounds:
            a,b=st.columns([4,1]); a.write(f"**Jornada {round_row['number']}** · {'ABIERTA' if round_row['is_open'] else 'CERRADA'} · límite {round_row['deadline']}")
            if b.button("Cerrar" if round_row["is_open"] else "Activar",key=f"r{round_row['id']}"):
                with conn() as c: c.execute("UPDATE rounds SET is_open=1-is_open WHERE id=?",(round_row["id"],))
                st.rerun()
    with tabs[2]:
        with conn() as c: rounds=c.execute("SELECT * FROM rounds ORDER BY number").fetchall()
        choices={f"Jornada {r['number']}":r for r in rounds}; round_row=choices[st.selectbox("Revisar entregas",list(choices))]
        status,complete=round_submission_status(round_row["id"])
        ready=sum(1 for row in status if row["ESTADO"]=="Listo")
        a,b=st.columns(2); a.metric("Entregaron",f"{ready}/18"); b.metric("Publicación", "Visible" if complete else "Bloqueada")
        st.dataframe(pd.DataFrame(status),hide_index=True,use_container_width=True)
        public_predictions(round_row["id"])
    with tabs[3]:
        accesses=pd.DataFrame([(code,name,TEAM_SHORT.get(team,team),PLAYER_PINS[code]) for code,name,team in PLAYERS],columns=["CLAVE","PARTICIPANTE","EQUIPO","PIN"])
        st.warning("Comparte cada PIN de forma privada.")
        st.dataframe(accesses,hide_index=True,use_container_width=True)
        st.download_button("Descargar accesos",accesses.to_csv(index=False).encode("utf-8-sig"),"accesos_privados.csv")
    with tabs[4]: st.dataframe(standings().drop(columns=["USER_ID"]),hide_index=True,use_container_width=True)
    with tabs[5]:
        st.dataframe(duel_standings(),hide_index=True,use_container_width=True)
        journey=st.selectbox("Jornada de duelos",range(1,18)); st.dataframe(pd.DataFrame(duels_round(journey)),hide_index=True,use_container_width=True)
    with tabs[6]: st.dataframe(survivor_status(),hide_index=True,use_container_width=True)
    with tabs[7]:
        st.dataframe(champion_order().drop(columns=["USER_ID"]),hide_index=True,use_container_width=True)
        with conn() as c:
            current=[x["team"] for x in c.execute("SELECT team FROM champion_eligible")]
            active=c.execute("SELECT value FROM settings WHERE key='champion_draft_active'").fetchone()["value"]=="1"
        eligible=st.multiselect("Equipos elegibles",ALL_TEAMS,default=current)
        if st.button("Guardar equipos elegibles"):
            with conn() as c:
                c.execute("DELETE FROM champion_eligible"); c.executemany("INSERT INTO champion_eligible VALUES(?)",[(x,) for x in eligible])
            st.success("Guardados.")
        if st.button("Desactivar selección" if active else "Activar selección",type="primary"):
            with conn() as c: c.execute("UPDATE settings SET value=? WHERE key='champion_draft_active'",("0" if active else "1",))
            st.rerun()
        champion_view(admin=True)
        if st.button("Reiniciar selección de campeón"):
            with conn() as c: c.execute("DELETE FROM champion_picks")
            st.rerun()


def main():
    st.set_page_config(page_title=APP_NAME,page_icon="⚽",layout="wide",initial_sidebar_state="collapsed")
    inject_style(); init_db()
    if "user" not in st.session_state:
        login(); return
    brand(); user=st.session_state.user
    left,right=st.columns([5,1]); left.caption("Apertura 2026")
    if right.button("Salir",use_container_width=True):
        del st.session_state.user; st.rerun()
    admin_view() if user["is_admin"] else player_view(user)


if __name__ == "__main__":
    main()
