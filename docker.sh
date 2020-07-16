#!/usr/bin/env bash
#$ user=$USER; sudo ./docker.sh
#$ sudo ./docker.sh

# mFund TransData
# Copyright (C) 2020 XTL Kommunikationssysteme GmbH <info@xtl-gmbh.de>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

sudo docker build -t xtl/osrm-learning:latest .

#sudo docker rm -f xtl-osrm-run
#sudo docker rm -f xtl-osrm-learning-run
#sudo docker rm -f $(sudo docker ps | grep osrm | grep -o ^[0-9a-z]*)

#sudo docker run -d \
sudo docker run -t \
-v /var/run/docker.sock:/var/run/docker.sock \
-v /usr/bin/docker:/usr/bin/docker \
-v $(pwd)/data/:/opt/data/ \
-p 4999:4999 \
--name xtl-osrm-learning-run \
xtl/osrm-learning \
python3 osrmlearning/api.py --docker-host-pwd=$(pwd) #--skip-api #& 1>/dev/null 2>&1
#gunicorn osrmlearning.api:app

#sudo docker rm -f xtl-osrm-run
#sudo docker rm -f xtl-osrm-learning-run

#sudo chown -R $user data
#sudo chgrp -R $user data

#zenity --notification --text "Finished learning"
