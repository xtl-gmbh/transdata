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

DROP TABLE route_timestamps;
DROP TABLE route_osrm_times;
DROP TABLE route_nodes;
DROP TABLE route_tags;
DROP TABLE tag_whitelist;

DROP VIEW all_way_tags;
DROP VIEW route_reference_times;
-- DROP VIEW route_reference_times_9_12;

DROP DOMAIN route;
DROP DOMAIN osmtag;
