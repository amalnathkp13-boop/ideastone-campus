#!/bin/sh
# JVM options for OpenOlat (see install guide). Adjust -Xmx to the host.
export CATALINA_OPTS="-Xms512m -Xmx2048m -Djava.awt.headless=true -Dfile.encoding=UTF-8 -Duser.timezone=Asia/Kolkata"
export CATALINA_TMPDIR=/home/openolat/temp
