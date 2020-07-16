-- mFund TransData
-- Copyright (C) 2020 XTL Kommunikationssysteme GmbH <info@xtl-gmbh.de>

-- This program is free software: you can redistribute it and/or modify
-- it under the terms of the GNU General Public License as published by
-- the Free Software Foundation, either version 3 of the License, or
-- (at your option) any later version.

-- This program is distributed in the hope that it will be useful,
-- but WITHOUT ANY WARRANTY; without even the implied warranty of
-- MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
-- GNU General Public License for more details.

-- You should have received a copy of the GNU General Public License
-- along with this program.  If not, see <https://www.gnu.org/licenses/>.


CREATE DOMAIN route AS text CHECK (
    VALUE ~ '^[0-9]+\.[0-9]+,[0-9]+\.[0-9]+;[0-9]+\.[0-9]+,[0-9]+\.[0-9]+$'
);

CREATE DOMAIN osmtag AS text CHECK (
    VALUE ~ '^.+=.+$'
);

CREATE TABLE route_timestamps (
    route route NOT NULL,
    start_timestamp timestamp NOT NULL,
    end_timestamp timestamp NOT NULL
);

CREATE VIEW route_reference_times AS
    SELECT
        route,
        EXTRACT(SECOND FROM AVG(end_timestamp - start_timestamp)) AS seconds
    FROM route_timestamps
    GROUP BY route
;

-- CREATE VIEW route_reference_times_9_12 AS
--     SELECT
--         route,
--         EXTRACT(SECOND FROM AVG(end_timestamp - start_timestamp))
--     FROM route_timestamps
--     WHERE
--         EXTRACT(HOUR FROM start_timestamp) BETWEEN 9 AND 12
--     OR
--         EXTRACT(HOUR FROM end_timestamp) BETWEEN 9 AND 12
--     GROUP BY route
-- ;

CREATE TABLE route_osrm_times (
    route route NOT NULL UNIQUE,
    osrm_time float4 NOT NULL
);

CREATE TABLE route_nodes (
    route route NOT NULL,
    node int8 NOT NULL
);

CREATE TABLE route_tags (
    route route NOT NULL,
    tag osmtag NOT NULL,
--     k text NOT NULL,
--     v text NOT NULL,
    counter int4 NOT NULL
);

CREATE TABLE tag_whitelist (
    tag osmtag NOT NULL UNIQUE
);

CREATE VIEW all_way_tags AS
    SELECT way_id, CONCAT(k, '=', v) AS tag, COUNT(*) AS counter FROM (
        SELECT way_id, k, v FROM
            way_tags
        UNION ALL
        SELECT way_id, k, v FROM
            way_nodes JOIN node_tags
            ON way_nodes.node_id = node_tags.node_id
    ) AS tags
    WHERE CONCAT(k, '=', v) IN (
        SELECT * FROM tag_whitelist
    ) GROUP BY way_id, k, v
;


-- data
-- INSERT INTO route_timestamps VALUES
--     (%s, to_timestamp(%s), to_timestamp(%s));
-- INSERT INTO route_osrm_times VALUES
--     (%s, %s);
-- INSERT INTO route_tags VALUES
--     (%s, %s, %s);
-- INSERT INTO tag_whitelist VALUES (%s);
INSERT INTO route_timestamps VALUES
    ('53.0,8.0;53.1,8.1', to_timestamp(1524520800), to_timestamp(1524520860));
INSERT INTO route_osrm_times VALUES
    ('53.0,8.0;53.1,8.1', 12.3);
INSERT INTO route_nodes VALUES
    ('53.0,8.0;53.1,8.1', 1835029415);
INSERT INTO route_tags VALUES
    ('53.0,8.0;53.1,8.1', 'highway=primary', 3),
    ('53.0,8.0;53.1,8.1', 'highway=traffic_signals', 5)
;
INSERT INTO tag_whitelist VALUES ('highway=primary');


-- query
SELECT * FROM route_reference_times;
SELECT * FROM route_tags;
SELECT * FROM all_way_tags;
