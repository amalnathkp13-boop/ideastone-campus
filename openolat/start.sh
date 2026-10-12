#!/bin/bash
# Render config templates from environment, then start Tomcat in the foreground.
set -e
# Tomcat derives the context path from the descriptor file name: ROOT.xml → "/", lms.xml → "/lms"
CTX_NAME=$(echo "${OLAT_CONTEXT:-/}" | tr -d '/'); [ -z "$CTX_NAME" ] && CTX_NAME=ROOT
rm -f /home/openolat/conf/Catalina/localhost/*.xml
envsubst < /home/openolat/conf/ROOT.xml.template > "/home/openolat/conf/Catalina/localhost/${CTX_NAME}.xml"
envsubst < /home/openolat/lib/olat.local.properties.template > /home/openolat/lib/olat.local.properties
export CATALINA_BASE=/home/openolat
export CLASSPATH=/home/openolat/lib/postgresql.jar
exec /usr/local/tomcat/bin/catalina.sh run
