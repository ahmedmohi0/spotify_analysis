-- found nulls when trying to insert into dim_artist:
--SELECT DISTINCT track_id
--FROM staging_listening_history
--WHERE artist_name IS NULL;

--SELECT DISTINCT track_id
--FROM staging_listening_history
--WHERE album_name IS NULL;

/*
the above queries returned three rows where artist name is null and one where album name is null they were played 35 times
3 tracks (35 total plays) have no artist_name/track_name from Spotify's
API (likely local files, verified not a merge bug).
Kept rather than dropped, so total listening-time/play-count stats stay accurate 
*/


/*
after beggining notebook1 I noticed problems with the genre column originally I decided
to get missing track genre from artist genre but that presented very messy data
so I had to modify the schema by adding dedicated genre table and bridge tables to
tie the genres back to the tracks/artist
I also went with my original idea but with added steps to make the artist tags 
more clean and trustworthy
*/

---Helper Tables-------------------------------------------------------------------------------------------------------------
--First two tables are made by giving ai a csv file resulted from quering my old schema.



CREATE TABLE genre_keywords ( keyword TEXT PRIMARY KEY ); INSERT INTO genre_keywords (keyword) VALUES
 ('metal'), ('rock'), ('pop'), ('hip hop'), ('hip-hop'), ('rap'), ('trap'), ('punk'), ('grunge'), ('shoegaze'), ('emo'), ('hardcore'),
  ('metalcore'), ('deathcore'), ('electronic'), ('electronica'), ('house'), ('techno'), ('trance'), ('dubstep'), ('ambient'), ('drum and bass'),
   ('dnb'), ('indie'), ('alternative'), ('folk'), ('country'), ('blues'), ('jazz'), ('classical'), ('soul'), ('funk'), ('reggae'), ('latin'), ('rnb'), 
   ('phonk'); 



CREATE TABLE invalid_tags ( tag_name TEXT PRIMARY KEY ); INSERT INTO invalid_tags VALUES ('favorite'), ('favorites'), ('seen live'), ('live'), 
('awesome'), ('good'), ('love'), ('sad'), ('happy'), ('spotify'), ('lastfm'), ('male vocalists'), ('female vocalists'), ('american'), ('british'), 
('english'), ('german'), ('japanese'), ('swedish'), ('french'), ('under 2000 listeners'), ('under 1000 listeners'), ('under 500 listeners'), ('under 100 listeners');

CREATE TABLE valid_artist_tags AS
SELECT DISTINCT
    s.artist_id,
    LOWER(TRIM(tag)) AS genre
FROM staging_listening_history s
CROSS JOIN LATERAL unnest(s.artist_tags) AS tag
WHERE
    s.artist_id IS NOT NULL
    AND tag IS NOT NULL
    AND TRIM(tag) <> ''

    AND EXISTS (
        SELECT 1
        FROM genre_keywords g
        WHERE LOWER(tag) LIKE '%' || g.keyword || '%'
    )

    AND NOT EXISTS (
        SELECT 1
        FROM invalid_tags b
        WHERE LOWER(tag) = LOWER(b.tag_name)
    );




CREATE TABLE artist_primary_genre AS
SELECT DISTINCT ON (artist_id)
    artist_id,
    genre
FROM valid_artist_tags
ORDER BY
    artist_id,
    LENGTH(genre),
    genre;


CREATE TABLE valid_track_tags AS
SELECT DISTINCT
    s.track_id,
    LOWER(TRIM(tag)) AS genre
FROM staging_listening_history s
CROSS JOIN LATERAL unnest(s.track_tags) AS tag
WHERE
    s.track_id IS NOT NULL
    AND tag IS NOT NULL
    AND TRIM(tag) <> ''

    AND EXISTS (
        SELECT 1
        FROM genre_keywords g
        WHERE LOWER(tag) LIKE '%' || g.keyword || '%'
    )

    AND NOT EXISTS (
        SELECT 1
        FROM invalid_tags b
        WHERE LOWER(tag) = LOWER(b.tag_name)
    );




CREATE TABLE track_primary_genre AS
SELECT DISTINCT ON (track_id)
    track_id,
    genre
FROM valid_track_tags
ORDER BY
    track_id,
    LENGTH(genre),
    genre;

CREATE TABLE track_final_genre AS
SELECT DISTINCT ON (s.track_id)
    s.track_id,
    COALESCE(tp.genre, ap.genre,'unknown') AS genre
FROM staging_listening_history s
LEFT JOIN track_primary_genre tp
    ON s.track_id = tp.track_id
LEFT JOIN artist_primary_genre ap
    ON s.artist_id = ap.artist_id
ORDER BY s.track_id;
-------------------------------------------------------------------------------------------------------------------------



INSERT INTO dim_date (date_key, full_date, calendar_year, calendar_month, calendar_day,month_name, weekday_name)
SELECT
    to_char(date_value, 'YYYYMMDD')::int,
    date_value::date,
    extract(year  FROM date_value)::smallint,
    extract(month FROM date_value)::smallint,
    extract(day   FROM date_value)::smallint,
    TRIM(to_char(date_value, 'Month')),
    TRIM(to_char(date_value, 'Day'))
FROM (
    SELECT generate_series(min(played_at), max(played_at), '1 day'::interval) 
    AS date_value
    FROM staging_listening_history
)d ;



INSERT INTO dim_artist (artist_id, artist_name)
SELECT DISTINCT ON (artist_id) artist_id, coalesce(artist_name, 'Unknown') AS artist_name
FROM staging_listening_history
WHERE artist_id IS NOT NULL
ORDER BY artist_id
ON CONFLICT (artist_id) DO NOTHING;


INSERT INTO dim_album (album_id, album_name, album_release_year, album_type, album_total_tracks)
SELECT DISTINCT ON (album_id) album_id, coalesce(album_name, 'Unknown') AS album_name, left(album_release_date, 4)::smallint as album_release_year, album_type,
album_total_tracks
FROM staging_listening_history
WHERE album_id IS NOT NULL
ORDER BY album_id
ON CONFLICT (album_id) DO NOTHING;


INSERT INTO dim_track (
    track_id, track_uri, track_name, duration_ms, popularity, explicit,
    track_number, disc_number, artist_id, all_artist_names, album_id,
    danceability, energy, valence, tempo, loudness, acousticness,
    instrumentalness, speechiness, liveness, key, mode)
SELECT DISTINCT ON (track_id)
    track_id, track_uri, coalesce(track_name, 'Unknown') AS track_name, duration_ms, popularity, explicit,
    track_number, disc_number, artist_id, all_artist_names, album_id,
    danceability, energy, valence, tempo, loudness, acousticness,
    instrumentalness, speechiness, liveness, key, mode 
FROM staging_listening_history
ORDER BY track_id
ON CONFLICT (track_id) DO NOTHING;


INSERT INTO dim_genre (genre_name)
SELECT DISTINCT genre
FROM (
    SELECT genre FROM track_final_genre
    UNION
    SELECT genre FROM artist_primary_genre
) g
WHERE genre IS NOT NULL;


INSERT INTO fact_listening_history (
    date_key, track_id, artist_id, album_id,
    played_at, ms_played, shuffled, skipped, reason_start, reason_end, offline,genre_id)
SELECT
    to_char(played_at, 'YYYYMMDD')::int,
    f.track_id, artist_id, album_id,
    played_at, ms_played, shuffled, skipped, reason_start, reason_end, offline,g.genre_id
FROM staging_listening_history f
join bridge_track_genre g on g.track_id = f.track_id;


INSERT INTO bridge_artist_genre (
    artist_id,
    genre_id
)
SELECT
    ap.artist_id,
    dg.genre_id
FROM artist_primary_genre ap
JOIN dim_genre dg
    ON dg.genre_name = ap.genre
ON CONFLICT (artist_id, genre_id) DO NOTHING;


INSERT INTO bridge_track_genre (
    track_id,
    genre_id
)
SELECT
    t.track_id,
    g.genre_id
FROM track_final_genre t
JOIN dim_genre g
    ON g.genre_name = t.genre
ON CONFLICT (track_id, genre_id) DO NOTHING;





DROP TABLE IF EXISTS valid_artist_tags cascade;
DROP TABLE IF EXISTS artist_primary_genre cascade;
DROP TABLE IF EXISTS track_primary_genre cascade;
DROP TABLE IF EXISTS valid_track_tags cascade;
DROP TABLE IF EXISTS invalid_tags cascade;
DROP TABLE IF EXISTS genre_keywords cascade;
DROP TABLE IF EXISTS track_final_genre cascade;



