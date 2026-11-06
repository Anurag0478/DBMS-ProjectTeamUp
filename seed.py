"""Create the database and fill it with synthetic data (Faker) plus two demo accounts.
Usage: python seed.py [num_users]"""
import os, random, sqlite3, sys
from datetime import date, timedelta
from urllib.parse import quote
from faker import Faker
from werkzeug.security import generate_password_hash

DB = os.environ.get("DB_PATH", "matchmaker.db")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 300
fake, rnd = Faker("en_IN"), random.Random(7)
Faker.seed(7)

SKILLS = {
 "Backend":  ["Python","Java","Node.js","Django"],
 "Frontend": ["React","HTML/CSS","JavaScript"],
 "Mobile":   ["Flutter","Android"],
 "Data/AI":  ["Machine Learning","Deep Learning","NLP","Data Visualization"],
 "Database": ["SQL","MongoDB","Firebase"],
 "Design":   ["UI/UX","Figma","Graphic Design"],
 "DevOps":   ["Docker","Git","AWS"],
 "Other":    ["IoT","Arduino","Cybersecurity","Pitching"],
}
ARCHETYPES = [["Backend","Database"],["Frontend","Design"],["Data/AI","Database"],["Mobile","Frontend"],
              ["Design"],["DevOps","Backend"],["Other","Backend"],["Data/AI","Backend"]]
BRANCHES = ["CSE/CSAI","IT","ECE/EVDT","EE","ICE","BT","Mechanical","Civil","Design"]
YEARS = [2026, 2027, 2028, 2029, 2030]
EVENTS = [("Smart India Hackathon","Govt. of India","Hybrid"),("HackFest Delhi","IIT Delhi","Offline"),
          ("CodeSprint 48h","Devfolio","Online"),("Green Tech Challenge","UNEP Youth","Hybrid"),
          ("FinTech Forge","NPCI","Online")]
TEAM_WORDS = ["Byte","Pixel","Quantum","Nova","Neural","Cloud","Fusion","Vector","Spark","Orbit","Cipher","Atlas"]

# Two real, existing GitHub accounts so the GitHub button always opens for the demos.
DEMOS = {
 1: dict(name="Aarav Demo", email="demo1@univ.edu", gender="Male", year=2027, branch="CSE/CSAI", gh="https://github.com/octocat",
         bio="Backend developer looking for a UI/UX designer.", skills={"Python":5,"Django":4,"SQL":4,"Git":3}),
 2: dict(name="Diya Demo", email="demo2@univ.edu", gender="Female", year=2027, branch="ECE/EVDT", gh="https://github.com/github",
         bio="Designer and front-end dev. Leading a team that needs a backend developer.", skills={"UI/UX":5,"Figma":5,"React":4,"HTML/CSS":4,"JavaScript":3}),
}

def main():
    if os.path.exists(DB): os.remove(DB)
    c = sqlite3.connect(DB); c.execute("PRAGMA foreign_keys=ON")
    c.executescript(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")).read())
    sid = {}
    for cat, names in SKILLS.items():
        for n in names: sid[n] = c.execute("INSERT INTO skills(name,category) VALUES(?,?)", (n, cat)).lastrowid
    by_cat = {cat: [sid[n] for n in names] for cat, names in SKILLS.items()}
    pw = generate_password_hash("password123")

    for i in range(1, N + 1):
        if i in DEMOS:
            d = DEMOS[i]; name, email, g, yr, br, gh, bio = d["name"], d["email"], d["gender"], d["year"], d["branch"], d["gh"], d["bio"]
            av, hrs = "Flexible", 12; chosen = {sid[k]: v for k, v in d["skills"].items()}
        else:
            g = rnd.choices(["Male","Female","Other"], [55, 42, 3])[0]
            name = fake.name_female() if g == "Female" else fake.name_male()
            email = f"{name.lower().replace(' ','.')}{i}@univ.edu"
            yr, br, bio = rnd.choice(YEARS), rnd.choice(BRANCHES), fake.sentence(nb_words=10)
            # synthetic students have no real GitHub, so link to a GitHub user search that always opens
            gh = f"https://github.com/search?q={quote(name)}&type=users"
            av, hrs = rnd.choice(["Weekdays","Weekends","Flexible"]), rnd.choice([4,6,8,10,15,20])
            chosen = {}
            for cat in rnd.choice(ARCHETYPES):
                for s in rnd.sample(by_cat[cat], k=min(len(by_cat[cat]), rnd.randint(2, 3))): chosen[s] = rnd.randint(3, 5)
            for s in rnd.sample([x for v in by_cat.values() for x in v], k=rnd.randint(1, 2)): chosen.setdefault(s, rnd.randint(1, 3))
        uid = c.execute("""INSERT INTO users(name,email,password_hash,gender,grad_year,branch,github_url,bio,availability,hours_per_week)
                           VALUES(?,?,?,?,?,?,?,?,?,?)""", (name, email, pw, g, yr, br, gh, bio, av, hrs)).lastrowid
        c.executemany("INSERT INTO user_skills VALUES(?,?,?)", [(uid, s, l) for s, l in chosen.items()])

    today = date.today()
    for k, (title, org, mode) in enumerate(EVENTS):
        start = today + timedelta(days=10 + k * 14)
        eid = c.execute("INSERT INTO events(title,organizer,start_date,end_date,mode,max_team_size,description) VALUES(?,?,?,?,?,4,?)",
            (title, org, start.isoformat(), (start + timedelta(days=2)).isoformat(), mode, fake.paragraph(nb_sentences=2))).lastrowid
        if k == 0:  # Diya (demo 2) leads a team that needs a backend dev, which is Aarav (demo 1)
            tid = c.execute("INSERT INTO teams(event_id,name,description,leader_id,max_size) VALUES(?,?,?,?,4)",
                (eid, "Demo Squad", "A campus lost-and-found app. We have the design covered and need a backend developer.", 2)).lastrowid
            c.execute("INSERT INTO team_members(team_id,user_id,event_id,role) VALUES(?,?,?, 'leader')", (tid, 2, eid))
            c.executemany("INSERT INTO team_required_skills VALUES(?,?)", [(tid, sid[s]) for s in ("Python","Django","SQL")])
        pool = list(range(3, N + 1)); rnd.shuffle(pool)   # demos (ids 1, 2) stay out of random teams
        for t in range(7):
            size = rnd.randint(1, 3)
            members, pool = pool[:size], pool[size:]
            tid = c.execute("INSERT INTO teams(event_id,name,description,leader_id,max_size) VALUES(?,?,?,?,4)",
                (eid, f"Team {rnd.choice(TEAM_WORDS)}{rnd.randint(1,99)}", fake.sentence(nb_words=12), members[0])).lastrowid
            for m_i, m in enumerate(members):
                c.execute("INSERT INTO team_members(team_id,user_id,event_id,role) VALUES(?,?,?,?)", (tid, m, eid, "leader" if m_i == 0 else "member"))
            req = set(rnd.sample(by_cat["Design"], 1) + rnd.sample(by_cat["Backend"], 1) + rnd.sample(by_cat[rnd.choice(["Frontend","Data/AI","Mobile","Database"])], 2))
            c.executemany("INSERT INTO team_required_skills VALUES(?,?)", [(tid, s) for s in req])
            if t < 3 and rnd.random() < .7:
                for u in pool[:2]:
                    c.execute("INSERT INTO join_requests(team_id,user_id,kind,message) VALUES(?,?, 'request', ?)", (tid, u, "I'd love to join, I can ship fast!"))
    c.commit()
    print(f"Seeded {N} users, {sum(len(v) for v in SKILLS.values())} skills, {len(EVENTS)} events.")
    print("Demo 1 (backend dev, free agent): demo1@univ.edu / password123")
    print("Demo 2 (designer, leads 'Demo Squad' in", EVENTS[0][0] + "): demo2@univ.edu / password123")

main()
