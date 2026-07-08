--Project: Spotify Listening History Analysis


DROP TABLE IF EXISTS staging_listening_history CASCADE;

CREATE TABLE staging_listening_history (
    staging_id           BIGSERIAL PRIMARY KEY,
    track_id             TEXT NOT NULL,
    track_uri            TEXT,

    -- Track metadata (Spotify)
    track_name           TEXT,
    duration_ms          INTEGER,
    popularity           SMALLINT,
    explicit             BOOLEAN,
    track_number         SMALLINT,
    disc_number          SMALLINT,

    -- Artist (Spotify)
    artist_id            TEXT,
    artist_name          TEXT,
    all_artist_names     TEXT[],

    -- Album (Spotify)
    album_id             TEXT,
    album_name           TEXT,
    album_release_date   TEXT,        
    album_type           TEXT,
    album_total_tracks   SMALLINT,

    -- Audio features (ReccoBeats)
    danceability         NUMERIC(6,4),
    energy               NUMERIC(6,4),
    valence              NUMERIC(6,4),
    tempo                NUMERIC(6,2),
    loudness             NUMERIC(6,2),
    acousticness         NUMERIC(6,4),
    instrumentalness     NUMERIC(6,4),
    speechiness          NUMERIC(6,4),
    liveness             NUMERIC(6,4),
    key                  SMALLINT,
    mode                 SMALLINT,

    -- Genre tags (Last.fm)
    track_tags    TEXT[],
    artist_tags   TEXT[],

    -- Play-event data
    played_at            TIMESTAMP NOT NULL,
    ms_played            INTEGER,
    shuffled             BOOLEAN,
    skipped              BOOLEAN,
    reason_start         TEXT,
    reason_end           TEXT,
    offline              BOOLEAN
);




