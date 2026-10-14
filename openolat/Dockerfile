# OpenOlat LMS on Tomcat 10.1 / Java 17 (per docs.openolat.org install guide).
# The WAR is downloaded at build time from the official release directory.
ARG OPENOLAT_VERSION=2103
FROM tomcat:10.1-jre17-temurin

ARG OPENOLAT_VERSION
ENV CATALINA_BASE=/home/openolat \
    OLAT_DOMAIN=localhost OLAT_PUBLIC_PORT=80 OLAT_CONTEXT=/lms \
    DB_HOST=db DB_NAME=openolat DB_USER=campus DB_PASSWORD=campus

RUN apt-get update && apt-get install -y --no-install-recommends curl unzip gettext-base \
 && rm -rf /var/lib/apt/lists/* \
 && useradd -m -d /home/openolat openolat \
 && mkdir -p /home/openolat/bin /home/openolat/conf/Catalina/localhost \
             /home/openolat/lib /home/openolat/logs /home/openolat/run \
             /home/openolat/webapp /home/openolat/olatdata /home/openolat/temp /home/openolat/work \
 && curl -fsSL "https://www.openolat.com/fileadmin/downloads/releases/openolat_${OPENOLAT_VERSION}.war" -o /tmp/openolat.war \
 && unzip -q /tmp/openolat.war -d /home/openolat/webapp && rm /tmp/openolat.war \
 && curl -fsSL https://jdbc.postgresql.org/download/postgresql-42.7.4.jar -o /home/openolat/lib/postgresql.jar

COPY conf/server.xml /home/openolat/conf/server.xml
COPY conf/ROOT.xml.template /home/openolat/conf/ROOT.xml.template
COPY conf/olat.local.properties.template /home/openolat/lib/olat.local.properties.template
COPY conf/setenv.sh /home/openolat/bin/setenv.sh
COPY start.sh /home/openolat/bin/start.sh
RUN cp /usr/local/tomcat/conf/web.xml /usr/local/tomcat/conf/logging.properties /home/openolat/conf/ 2>/dev/null; \
    cp -n /usr/local/tomcat/conf/*.xml /usr/local/tomcat/conf/*.properties /home/openolat/conf/ ; \
    chmod +x /home/openolat/bin/*.sh && chown -R openolat:openolat /home/openolat

USER openolat
WORKDIR /home/openolat
EXPOSE 8088
CMD ["/home/openolat/bin/start.sh"]
