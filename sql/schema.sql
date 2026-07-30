--Project: Spotify Listening History Analysis



-- staging_listening_history: Staging table for listening history data

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


drop table if exists dim_date cascade;

create table dim_date
(
    date_key serial primary key,
    full_date date not null,
    calendar_year smallint not null,
    calendar_month smallint not null,
    calendar_day smallint not null,
    month_name text not null,
    weekday_name text not null
);

drop table if exists dim_artist cascade;
create table dim_artist
(
    artist_id text primary key,
    artist_name text 
);

drop table if exists dim_album cascade;
create table dim_album
(
    album_id text primary key,
    album_name text ,
    album_release_year smallint ,
    album_type text ,
    album_total_tracks smallint
);

drop table if exists dim_genre cascade;
create table dim_genre(

    genre_id SERIAL primary key,
    genre_name text
)


drop table if exists dim_track cascade;
create table dim_track
(
    track_id text primary key,
    track_uri text,
    track_name text ,
    duration_ms integer,
    popularity smallint ,
    explicit boolean ,
    track_number smallint ,
    disc_number smallint ,
    danceability numeric(6,4),
    energy numeric(6,4),
    valence numeric(6,4),
    tempo numeric(6,2),
    loudness numeric(6,2),
    acousticness numeric(6,4),
    instrumentalness numeric(6,4),
    speechiness numeric(6,4),
    liveness numeric(6,4),
    key smallint,
    mode smallint,
    artist_id text references dim_artist(artist_id),
    album_id text references dim_album(album_id),
    all_artist_names text[]
);

drop table if exists fact_listening_history cascade;
create table fact_listening_history
 (
    listen_id        BIGSERIAL PRIMARY KEY,
    date_key         INTEGER NOT NULL REFERENCES dim_date(date_key),
    track_id         TEXT NOT NULL REFERENCES dim_track(track_id),
    artist_id        TEXT REFERENCES dim_artist(artist_id),
    album_id         TEXT REFERENCES dim_album(album_id),
    played_at        TIMESTAMP NOT NULL,
    ms_played        INTEGER,
    shuffled         BOOLEAN,
    skipped          BOOLEAN,
    reason_start     TEXT,
    reason_end       TEXT,
    offline          BOOLEAN,
    genre_id         INT REFERENCES dim_genre(genre_id)
);
 
drop table if exists bridge_track_genre cascade;
CREATE table bridge_track_genre(

    genre_id INT NOT NULL REFERENCES dim_genre(genre_id),
    track_id text NOT NULL REFERENCES dim_track(track_id),
    CONSTRAINT bridge_track_genre_uq UNIQUE (track_id, genre_id)
);



 DROP TABLE IF EXISTS bridge_artist_genre;

CREATE TABLE bridge_artist_genre (
    artist_id TEXT NOT NULL REFERENCES dim_artist(artist_id),
    genre_id  INT NOT NULL REFERENCES dim_genre(genre_id),

    CONSTRAINT bridge_artist_genre_pk
        PRIMARY KEY (artist_id, genre_id)
);


CREATE INDEX idx_fact_date_key    ON fact_listening_history(date_key);
CREATE INDEX idx_fact_track_id    ON fact_listening_history(track_id);
CREATE INDEX idx_fact_artist_id   ON fact_listening_history(artist_id);
CREATE INDEX idx_fact_played_at   ON fact_listening_history(played_at);
 
CREATE INDEX idx_dim_track_genre  ON dim_track(track_genre);
 
 DROP TABLE IF EXISTS bridge_artist_genre CASCADE;
 


