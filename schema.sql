-- Optional: run this from VS Code (SQLTools / PostgreSQL extension)
-- to initialize the schema manually. The app also creates it on startup.
CREATE TABLE IF NOT EXISTS owners (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(120) NOT NULL,
    email      VARCHAR(180),
    phone      VARCHAR(40),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pets (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(100) NOT NULL,
    species    VARCHAR(50)  NOT NULL,
    breed      VARCHAR(100),
    age        DOUBLE PRECISION,
    bio        TEXT,
    owner_id   INTEGER REFERENCES owners(id),
    photo_file VARCHAR(300),
    created_at TIMESTAMP DEFAULT NOW()
);
