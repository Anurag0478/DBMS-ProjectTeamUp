"""Cosine-similarity recommendation engine (pure Python, no heavy deps).

Each skill is one dimension of a vector space.
  user vector  : proficiency/5 for every skill the user has
  team vector  : 1.0 for every skill the team STILL needs
                 (required skills minus those already covered by members at level >= 3)
score = (u . t) / (|u| |t|)
"""
import math


def cosine(a: dict, b: dict) -> float:
    dot = sum(v * b.get(k, 0.0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def _vectors(conn, user_ids):
    if not user_ids:
        return {}
    ph = ",".join("?" * len(user_ids))
    vecs = {}
    for r in conn.execute(f"SELECT user_id, skill_id, level FROM user_skills WHERE user_id IN ({ph})", user_ids):
        vecs.setdefault(r["user_id"], {})[r["skill_id"]] = r["level"] / 5.0
    return vecs


def team_need_vector(conn, team_id):
    req = [r[0] for r in conn.execute("SELECT skill_id FROM team_required_skills WHERE team_id=?", (team_id,))]
    covered = {r[0] for r in conn.execute(
        """SELECT us.skill_id FROM team_members tm JOIN user_skills us ON us.user_id = tm.user_id
           WHERE tm.team_id=? AND us.level >= 3""", (team_id,))}
    need = [s for s in req if s not in covered] or req
    return {s: 1.0 for s in need}


def recommend_users(conn, team_id, k=5):
    """Top-k free agents (not yet in any team of this event) for a team."""
    event_id = conn.execute("SELECT event_id FROM teams WHERE id=?", (team_id,)).fetchone()["event_id"]
    need = team_need_vector(conn, team_id)
    if not need:
        return []
    ph = ",".join("?" * len(need))
    # SQL pre-filter: only users owning at least one needed skill can score > 0
    cands = conn.execute(
        f"""SELECT DISTINCT u.id, u.name, u.grad_year, u.branch, u.availability, u.github_url
            FROM users u JOIN user_skills us ON us.user_id = u.id AND us.skill_id IN ({ph})
            WHERE u.id NOT IN (SELECT user_id FROM team_members WHERE event_id = ?)""",
        [*need.keys(), event_id]).fetchall()
    vecs = _vectors(conn, [c["id"] for c in cands])
    names = {r["id"]: r["name"] for r in conn.execute("SELECT id, name FROM skills")}
    out = []
    for c in cands:
        v = vecs.get(c["id"], {})
        out.append({**dict(c), "score": round(cosine(v, need), 3),
                    "matched": [names[s] for s in need if s in v]})
    out.sort(key=lambda x: (-x["score"], x["name"]))
    return out[:k]


def recommend_teams(conn, user_id, event_id, k=5):
    """Top-k open teams in an event whose missing skills best fit this user."""
    v = _vectors(conn, [user_id]).get(user_id, {})
    names = {r["id"]: r["name"] for r in conn.execute("SELECT id, name FROM skills")}
    teams = conn.execute(
        """SELECT t.id, t.name, t.current_size, t.max_size FROM teams t
           WHERE t.event_id=? AND t.status='open'
             AND t.id NOT IN (SELECT team_id FROM team_members WHERE user_id=?)""",
        (event_id, user_id)).fetchall()
    out = []
    for t in teams:
        need = team_need_vector(conn, t["id"])
        out.append({**dict(t), "score": round(cosine(v, need), 3),
                    "matched": [names[s] for s in need if s in v]})
    out = [o for o in out if o["score"] > 0]
    out.sort(key=lambda x: -x["score"])
    return out[:k]
