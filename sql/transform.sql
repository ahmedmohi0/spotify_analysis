-- found nulls when trying to insert into dim_artist:
--SELECT DISTINCT track_id
--FROM staging_listening_history
--WHERE artist_name IS NULL;

--SELECT DISTINCT track_id
--FROM staging_listening_history
--WHERE album_name IS NULL;


--the above queries returned three rows where artist name is null and one where album name is null they were played 35 times
-- 3 tracks (35 total plays) have no artist_name/track_name from Spotify's
-- API (likely local files, verified not a merge bug).
-- Kept rather than dropped, so total listening-time/play-count stats
-- stay accurate 

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
    instrumentalness, speechiness, liveness, key, mode, track_genre
)
SELECT DISTINCT ON (track_id)
    track_id, track_uri, coalesce(track_name, 'Unknown') AS track_name, duration_ms, popularity, explicit,
    track_number, disc_number, artist_id, all_artist_names, album_id,
    danceability, energy, valence, tempo, loudness, acousticness,
    instrumentalness, speechiness, liveness, key, mode,
    coalesce(lower(trim(track_tags[1])),lower(trim(artist_tags[1]))) -- take the first tag as the track genre with consistent casing
FROM staging_listening_history
ORDER BY track_id
ON CONFLICT (track_id) DO NOTHING;

INSERT INTO bridge_artist_genre (artist_id, genre)
SELECT DISTINCT
    artist_id,
    LOWER(TRIM(tag)) AS genre
FROM staging_listening_history, unnest(artist_tags) AS tag
WHERE artist_id IS NOT NULL AND tag IS NOT NULL AND TRIM(tag) != ''
ON CONFLICT (artist_id, genre) DO NOTHING;

INSERT INTO fact_listening_history (
    date_key, track_id, artist_id, album_id,
    played_at, ms_played, shuffled, skipped, reason_start, reason_end, offline
   
)
SELECT
    to_char(played_at, 'YYYYMMDD')::int,
    track_id, artist_id, album_id,
    played_at, ms_played, shuffled, skipped, reason_start, reason_end, offline
FROM staging_listening_history;

