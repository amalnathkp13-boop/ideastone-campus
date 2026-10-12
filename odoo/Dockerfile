# Odoo 17 Community + OpenEduCat + Ideastone customisations.
# OpenEduCat (LGPL-3) is mounted/copied unmodified from the git submodule;
# all Ideastone-specific code lives in ../addons (separate modules, our IP).
FROM odoo:17.0

USER root
COPY entrypoint-campus.sh /usr/local/bin/entrypoint-campus.sh
RUN chmod +x /usr/local/bin/entrypoint-campus.sh \
 && mkdir -p /mnt/openeducat /mnt/ideastone-addons \
 && chown -R odoo:odoo /mnt/openeducat /mnt/ideastone-addons
USER odoo

ENTRYPOINT ["/usr/local/bin/entrypoint-campus.sh"]
CMD ["odoo"]
