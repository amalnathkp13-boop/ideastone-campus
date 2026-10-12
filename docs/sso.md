# Single sign-on with Keycloak

The `campus` realm is imported automatically on first start from `keycloak/campus-realm.json`, with two OpenID Connect clients (`odoo`, `openolat`) and three demo users (`demo.admin`, `demo.faculty`, `demo.student`, password `demo1234`).

## Odoo side — already done by `ideastone_campus`

The module creates the *Ideastone SSO* provider on install and points it at `CAMPUS_PUBLIC_URL/sso/realms/campus/...` (browser) and `KEYCLOAK_INTERNAL_URL/realms/campus/.../userinfo` (server-side validation). Nothing to configure; the login page shows **Log in with Ideastone SSO**. To change the URLs later: Settings → Integrations → OAuth Providers.

Odoo CE matches users by e-mail on first login; create the Odoo user (or let `auth_signup` do it) with the same e-mail as in Keycloak.

## OpenOlat side

1. Log in as `administrator` → Administration → Login → **OpenID Connect**.
2. Enable, then add provider:
   * Name: `Ideastone SSO`, Issuer: `http://localhost/sso/realms/campus`
   * Client ID: `openolat`, Client secret: value of `secret` in `campus-realm.json` (change it!)
   * Discovery / endpoints: `http://localhost/sso/realms/campus/.well-known/openid-configuration`
   * Attribute mapping: `preferred_username` → username, `email`, `given_name`, `family_name`
3. Optionally enable *Create user on first login*.

## Production notes

* Put Keycloak behind nginx with TLS and set `KC_HOSTNAME=sso.<college-domain>`; update the redirect URIs in the realm file.
* Keycloak can federate the college's existing Active Directory / LDAP (User federation → LDAP) so staff keep their current passwords.
* Roles in the realm (`admin`, `faculty`, `student`, `parent`) are the single place to control who is what; map them to Odoo groups / OpenOlat roles in each system's OIDC settings.
