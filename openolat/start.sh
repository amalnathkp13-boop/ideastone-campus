#!/bin/bash
# Render config templates from environment, then start Tomcat in the foreground.
set -e
envsubst < /home/openolat/conf/ROOT.xml.template > /home/openolat/conf/Catalina/localhost/ROOT.xml
envsubst < /home/openolat/lib/olat.local.properties.template > /home/openolat/lib/olat.local.properties
export CATALINA_BASE=/home/openolat
export CLASSPATH=/home/openolat/lib/postgresql.jar
exec /usr/local/tomcat/bin/catalina.sh run
