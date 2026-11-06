PRAGMA foreign_keys = ON;

CREATE TABLE users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  name          TEXT NOT NULL,
  email         TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  gender        TEXT CHECK (gender IN ('Male','Female','Other')),
  grad_year     INTEGER CHECK (grad_year BETWEEN 2020 AND 2040),
  branch        TEXT,
  github_url    TEXT,
  bio           TEXT,
  availability  TEXT NOT NULL DEFAULT 'Flexible' CHECK (availability IN ('Weekdays','Weekends','Flexible')),
  hours_per_week INTEGER DEFAULT 10 CHECK (hours_per_week BETWEEN 0 AND 80),
  created_at    TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE skills (
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  name     TEXT NOT NULL UNIQUE,
  category TEXT NOT NULL
);

-- M:N junction: a user has many skills, each with a proficiency 1-5
CREATE TABLE user_skills (
  user_id  INTEGER NOT NULL REFERENCES users(id)  ON DELETE CASCADE,
  skill_id INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
  level    INTEGER NOT NULL DEFAULT 3 CHECK (level BETWEEN 1 AND 5),
  PRIMARY KEY (user_id, skill_id)
);
CREATE INDEX idx_user_skills_skill ON user_skills(skill_id, level);
CREATE INDEX idx_users_filters     ON users(grad_year, gender, availability);

CREATE TABLE events (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  title         TEXT NOT NULL,
  organizer     TEXT,
  start_date    TEXT,
  end_date      TEXT,
  mode          TEXT CHECK (mode IN ('Online','Offline','Hybrid')),
  max_team_size INTEGER DEFAULT 4,
  description   TEXT
);

CREATE TABLE teams (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id     INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  name         TEXT NOT NULL,
  description  TEXT,
  leader_id    INTEGER NOT NULL REFERENCES users(id),
  max_size     INTEGER NOT NULL DEFAULT 4 CHECK (max_size BETWEEN 2 AND 10),
  current_size INTEGER NOT NULL DEFAULT 0,
  status       TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','full','closed')),
  created_at   TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (event_id, name)
);

-- event_id is denormalised on purpose: UNIQUE(event_id, user_id) makes it
-- impossible for one student to be on two teams of the same event.
CREATE TABLE team_members (
  team_id   INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  user_id   INTEGER NOT NULL REFERENCES users(id),
  event_id  INTEGER NOT NULL REFERENCES events(id),
  role      TEXT NOT NULL DEFAULT 'member',
  joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (team_id, user_id),
  UNIQUE (event_id, user_id)
);

CREATE TABLE team_required_skills (
  team_id  INTEGER NOT NULL REFERENCES teams(id)  ON DELETE CASCADE,
  skill_id INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
  PRIMARY KEY (team_id, skill_id)
);

-- kind='request': student asks a team   | kind='invite': leader invites a student
CREATE TABLE join_requests (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  team_id     INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind        TEXT NOT NULL DEFAULT 'request' CHECK (kind IN ('request','invite')),
  message     TEXT,
  status      TEXT NOT NULL DEFAULT 'pending'
              CHECK (status IN ('pending','accepted','rejected','withdrawn','closed')),
  created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
  resolved_at TEXT
);
-- only one *pending* request per (team, user); history rows are unrestricted
CREATE UNIQUE INDEX uq_pending_request ON join_requests(team_id, user_id) WHERE status = 'pending';

-- Integrity enforced inside the database, not just in app code
CREATE TRIGGER trg_block_full_team BEFORE INSERT ON team_members
WHEN (SELECT current_size >= max_size FROM teams WHERE id = NEW.team_id)
BEGIN SELECT RAISE(ABORT, 'Team is already full'); END;

CREATE TRIGGER trg_member_added AFTER INSERT ON team_members
BEGIN
  UPDATE teams
     SET current_size = current_size + 1,
         status = CASE WHEN current_size + 1 >= max_size THEN 'full' ELSE status END
   WHERE id = NEW.team_id;
END;

CREATE TRIGGER trg_member_removed AFTER DELETE ON team_members
BEGIN
  UPDATE teams
     SET current_size = current_size - 1,
         status = CASE WHEN status = 'full' THEN 'open' ELSE status END
   WHERE id = OLD.team_id;
END;

-- Supply vs. demand per skill (used by the Insights tab)
CREATE VIEW v_skill_gap AS
SELECT s.id, s.name, s.category,
  (SELECT COUNT(*) FROM team_required_skills r JOIN teams t ON t.id = r.team_id
    WHERE r.skill_id = s.id AND t.status = 'open')            AS demand,
  (SELECT COUNT(*) FROM user_skills us
    WHERE us.skill_id = s.id AND us.level >= 3)               AS supply
FROM skills s;
