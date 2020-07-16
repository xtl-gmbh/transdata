# XTL OSRM Machine Learning with TensorFlow

This is an XTL tool that uses TensorFlow machine learning to improve the precision of travel times predicted by OSRM.

Requirements (overview):
- Ubuntu system (others may work, but not tested so far)
- PostgreSQL database with [PostGIS](https://wiki.openstreetmap.org/wiki/PostGIS) plugin
- [Osmosis](https://wiki.openstreetmap.org/wiki/Osmosis) (to import OSM data into DB)
- OSM dataset
- Python runtime
- Docker
- Docker image of OSRM (from XTL Docker registry, or build yourself)
- API key for XTL server (or offline data)
- API key for HereMaps (or offline data)


## Dependencies

Install system dependencies (skip Python if you want to use docker only):

```bash
sudo apt-get install -y \
    python3-pip \
    python3-venv \
    python3-tk \
    postgresql \
    postgis \
    osmosis \
    docker.io \
    git
```

Clone the git repo with the source code.
First insert your ssh key into `/home/$USER/.ssh/id_rsa`.
Then into a directory of your choice:

```bash
git clone ssh://git@gitlab.xtl-gmbh.de:10022/xtl/julius_masterarbeit.git
```

## OSRM Docker Images

Build the image yourself:

```bash
git clone https://github.com/toha/osrm-backend.git

cd osrm-backend

sudo docker build -t xtl/osrm-v5:distances .
sudo docker build --file Dockerfile-germany-car -t xtl/osrm-v5-de-car:distances .
```
  
  
## Postgres

Download OSM data file from [https://download.geofabrik.de/](https://download.geofabrik.de/)

On a server: Download with `wget` or `curl`.

For LF region:
- [https://download.geofabrik.de/europe/germany/bayern-latest.osm.pbf](https://download.geofabrik.de/europe/germany/bayern-latest.osm.pbf)
- [https://download.geofabrik.de/europe/germany/baden-wuerttemberg-latest.osm.pbf](https://download.geofabrik.de/europe/germany/baden-wuerttemberg-latest.osm.pbf)

(Optional) Pre-merge smaller areas into 1:

```bash
osmosis \
    --read-pbf file=tuebingen-regbez-latest.osm.pbf \
    --read-pbf file=stuttgart-regbez-latest.osm.pbf \
    --merge \
    --write-pbf file=baden-wuerttemberg-latest.osm.pbf
```

Merge 2 OSM files into 1 (if applicable):

```bash
osmosis \
    --read-pbf file=bayern-latest.osm.pbf \
    --read-pbf file=baden-wuerttemberg-latest.osm.pbf \
    --merge \
    --write-pbf file=bayern-baden-wuerttemberg-latest.osm.pbf
```

Allow access to database:
[https://stackoverflow.com/a/41161674](https://stackoverflow.com/a/41161674)

```bash
# replace x.y by postgres version
cd /etc/postgresql/x.y/main/

echo "listen_addresses = '*'" | sudo tee --append postgresql.conf
echo "host  all  all  0.0.0.0/0  md5" | sudo tee --append pg_hba.conf
sudo /etc/init.d/postgresql restart
```

Initialize database:

```bash
# Set environment variables
POSTGRES_USER='postgres'
POSTGRES_PASSWORD='xxxxxxxxxxxxx'
HOST='127.0.0.1'
DB_NAME='bayern_baden_wuerttemberg'
OSM_FILE='bayern-baden-wuerttemberg-latest.osm.pbf'
TAG_FILTER='highway=*'

# Set password for postgres user
sudo --user="$POSTGRES_USER" psql -c \
    "ALTER USER $POSTGRES_USER PASSWORD '$POSTGRES_PASSWORD';"

# Create database
sudo --user="$POSTGRES_USER" createdb \
    --encoding=UTF8 \
    --owner="$POSTGRES_USER" \
    "$DB_NAME"

# Activate PostGIS plugin
sudo --user="$POSTGRES_USER" psql \
    --dbname="$DB_NAME" \
    --command='CREATE EXTENSION postgis;'

# Initialize database schema
sudo --user="$POSTGRES_USER" psql \
    --dbname="$DB_NAME" \
    --file=/usr/share/doc/osmosis/examples/pgsimple_schema_0.6.sql

# Import OSM data from file
osmosis \
    --read-pbf file="$OSM_FILE" \
    --tag-filter accept-ways "$TAG_FILTER" \
    --used-node \
    --write-pgsimp \
        host="$HOST" \
        database="$DB_NAME" \
        user="$POSTGRES_USER" \
        password="$POSTGRES_PASSWORD"
```

Known issue:
Osmosis does not show a progress bar in the console.
After it has finished, the command prompt should re-appear, but sometimes it does not re-appear.

Query the database (e.g. to check if the import was successful):

```bash
sudo --user="$POSTGRES_USER" psql --dbname="$DB_NAME"
```

```sql
SELECT * FROM nodes LIMIT 100;
SELECT * FROM ways LIMIT 100;
SELECT * FROM way_nodes LIMIT 100;
SELECT * FROM node_tags LIMIT 100;
SELECT * FROM way_tags LIMIT 100;
```

Also, move the OSM file (e.g. `bayern-baden-wuerttemberg-latest.osm.pbf`) to `data/osm/`.


## Config

Optional: Configure OSM tags for learning input in file `data/osm/osm_tags.yaml`  
The structure of the file is:
```yaml
node_tags:
  key1:
    - value1
    - value2
  key2:
    - value1
    - value2

way_tags:
  key1:
    - value1
    - value2
  key2:
    - value1
    - value2
```

Optional: Configure OSM highway tags whitelist for scaling in file `data/config/highway_tags_whitelist.txt`
The structure of the file is:
```text
highway_tag_value1
highway_tag_value2
```

Configure everything else in file `data/config.ini`:
- OSRM (host and region)
- Postgres credentials
- API key for XTL server
- API key for HereMaps
- Parameters for learning (optional)

The file `data/config.ini` is parsed after the application is started.  
In the python code
```ini
[section]
option = value
```
becomes
```python
config.section.option = value
```

`%` must be escaped as `%%`.

Experimental: In the file `data/config.csv` override config values can be defined for multiple consecutive batch runs.


## Run Natively

Install Python dependencies in virtual environment (skip if you want to use docker only):

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Run natively:

```bash
sudo bash -c \
'source venv/bin/activate &&
PYTHONPATH=. python3 osrmlearning/api.py'
```


## Run in Docker Container

Build docker image:

```bash
sudo docker build -t xtl/osrm-learning:latest .
```

Run in docker container:

```bash
sudo docker run -t \
-v /var/run/docker.sock:/var/run/docker.sock \
-v /usr/bin/docker:/usr/bin/docker \
-v $(pwd)/data/:/opt/data/ \
-p 4999:4999 \
--name xtl-osrm-learning-run \
xtl/osrm-learning \
python3 osrmlearning/api.py --docker-host-pwd=$(pwd)
```


## Evaluation

For each run, the reference routes are split into a training set (for TensorFlow) and a test set, which is used to evaluate the learning result at the end of the run.
For each route in the test set the following output is logged:

```text
Coordinates: 48.36872,10.89194;48.37289,10.89342
reference time:            290.0 s
OSRM time:                  99.9 s
TF scaled OSRM time:        88.8 s
TF final OSRM time:        191.6 s
Here time:                 146.0 s
OSRM error:             -190.290 %
TF scaled OSRM error:   -226.491 %
TF final OSRM error:     -51.357 %
Here error:              -98.630 %
TF scaled improvement:   -36.201 %
TF final improvement:    138.933 %
```

- `Coordinates`: route from lat/lon to lat/lon
- `reference time`: all other travel times are compared to this travel time
- `OSRM time`: travel time predicted by plain OSRM
- `TF scaled OSRM time`: travel time predicted by plain OSRM, multiplied by TensorFlow prediction
- `TF final OSRM time`: travel time predicted by OSRM with TensorFlow scaling factors for each OSM way
- `Here time`: travel time predicted by HereMaps
- `OSRM error`: error of plain OSRM travel time, compared to reference
- `TF scaled OSRM error`: error of plain OSRM travel time (multiplied by TensorFlow prediction), compared to reference
- `TF final OSRM error`: error of plain OSRM travel time (with TensorFlow scaling factors for each OSM way), compared to reference
- `Here error`: error of HereMaps travel time, compared to reference
- `TF scaled improvement`: degree of improvement of OSRM travel time (multiplied by TensorFlow prediction) error, compared to plain OSRM error
- `TF final improvement`: degree of improvement of OSRM travel time (with TensorFlow scaling factors for each OSM way) error, compared to plain OSRM error

In addition, boxplots are created from all of these values. (`data/results/plots/timestamp.png`)

With `config.evaluation.log_limit`, the number of logged routes can be limited to a maximum. Routes that are not logged are still evaluated.

For all evaluated routes (also the ones that were not logged), average values are calculated:

```text
average OSRM error:                     324.186 %
average TF OSRM scaled error:           342.416 %
average TF OSRM final error:            184.846 %
average Here error:                     182.284 %
average TF OSRM scaled improvement:     -18.230 %
average TF OSRM final improvement:      139.340 %
TF OSRM scaled improvement frequency:    46.251 %
TF OSRM final improvement frequency:     54.610 %
```

- `average OSRM error`: the average error of travel times predicted by plain OSRM
- `average TF OSRM scaled error`: the average error of travel times predicted by plain OSRM, multiplied by TensorFlow prediction
- `average TF OSRM final error`: the average error of travel times predicted by plain OSRM, with TensorFlow scaling factors for each OSM way
- `average Here error`: the average error of travel times predicted by plain HereMaps
- `average TF OSRM scaled improvement`: the average degree of improvement of OSRM travel time (multiplied by TensorFlow prediction) errors, compared to plain OSRM errors
- `average TF OSRM final improvement`: the average degree of improvement of OSRM travel time (with TensorFlow scaling factors for each OSM way) errors, compared to plain OSRM errors
- `TF OSRM scaled improvement frequency`: how often the degree of improvement of OSRM travel time (multiplied by TensorFlow prediction) errors, compared to plain OSRM errors, is positive
- `TF OSRM final improvement frequency`: how often the degree of improvement of OSRM travel time (with TensorFlow scaling factors for each OSM way) errors, compared to plain OSRM errors, is positive

At the end of each learning run (identified by `timestamp`), several result files are created in `data/results/`.
Some are marked as redundant because all their data can be viewed more conveniently in another file.

- `data/results/config/timestamp.ini` a copy of the config file of the run
- `data/results/highway_tags_whitelists/timestamp.txt` a copy of the highway tags whitelist file of the run
- `data/results/logs/timestamp.log` a file containing all the lines that were logged to the console during the run
- `data/results/osm_tags/timestamp.yaml` a copy of the osm_tags.yaml file of the run
- `data/results/plots/timestamp.png` boxplots of the resulting data of the run
- `data/scaling_factors/timestamp.csv` a file containing the scaling factors of all OSM ways that were predicted by TensorFlow and used by OSRM during the run
- `data/values/timestamp.csv` a file containing the results for all evaluated routes of the run

Redundant files:
- `data/results/config/timestamp.json` the same config values in json format
- `data/summaries/timestamp.json` a file containing containing some input and output values of the run

Route data from XTL server is persistently stored in `data/server/`:
- `data/server/locations/timestamp.json` (courier locations)
- `data/server/plans/scenarios.json` (scenarios)
- `data/server/plans/executed-plans-scenario-n.json` (executed-plans)
- `data/server/plans/plans-scenario-n.json` (planned plans with HereMaps travel times)


## API

The tool has an HTTP API that proxies all requests to one of its OSRM instances.
It accepts all standard OSRM requests.
The OSRM HTTP API is documented here:

- [http://project-osrm.org/docs/v5.15.2/api/#general-options](http://project-osrm.org/docs/v5.15.2/api/#general-options)
- [https://github.com/Project-OSRM/osrm-backend/blob/master/docs/http.md](https://github.com/Project-OSRM/osrm-backend/blob/master/docs/http.md)

Additional option for OSRM requests: `?timestamp=...`  
The date format can be configured in `config.ini`, e.g. `%Y-%m-%dT%H:%M:%S.%fZ`  
The timestamp specifies when the planned route is going to be travelled. The tool chooses the OSRM instance depending on the hour of the timestamp.

Example request:
[http://localhost:4999/route/v1/car/8.8473,53.1080;8.7859,53.0524?overview=false&timestamp=2018-01-01T00:00:00.00Z](http://localhost:4999/route/v1/car/8.8473,53.1080;8.7859,53.0524?overview=false&timestamp=2018-01-01T00:00:00.00Z)

Additional utility HTTP routes:
- `GET/POST /learn` re-run learning
- `GET/POST /shutdown` stop the application


## Command Line Options

Available command line options for debugging:
- `--skip-api`: Do not start the HTTP API
- `--skip-init`: Do not start a learning run immediately
- `--schedule`: Always start a scheduled learning run on a specified weekday and time, defined in `config.ini`
- `--docker-host-pwd=$(pwd)`: When you run the application in a docker container, this locates the `data` folder. When you run the application outside a docker container, this can be omitted.


## Unused Folders

The following folders were used in previous versions but are currently not used:
- `data/route_data/`
- `data/scenarios/`
- `data/sql/`
