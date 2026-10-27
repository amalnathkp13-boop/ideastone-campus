/** @odoo-module **/
import { registry } from "@web/core/registry";
import { session } from "@web/session";

const identityKey = "ideastone.campus.session";
const sessionRoute = "/web/session/get_session_info";

export const campusSessionService = {
    dependencies: ["rpc", "user"],
    start(env, { rpc, user }) {
        if (!/^\/web(?:\/login)?\/?$|^\/my\/campus(?:\/|$)/.test(window.location.pathname)) return {};
        const uid = session.is_public ? false : user.userId;
        // A storage event is only a hint; the server remains the identity authority.
        try { window.localStorage.setItem(identityKey, JSON.stringify(uid || false)); } catch {}
        if (!uid) return {};
        let pending = null;
        let navigating = false;
        const navigate = (url) => {
            if (navigating) return;
            navigating = true;
            window.location.replace(url);
        };
        const check = () => {
            if (pending || navigating) return pending;
            pending = rpc(sessionRoute, {}, { silent: true }).then((current) => {
                if (current.uid !== uid || (session.db && current.db !== session.db)) {
                    // Drop the previous user's action hash and cached company context.
                    navigate(current.is_internal_user ? "/web" : "/my/campus");
                }
            }).catch((error) => {
                if (error.code === 100) navigate("/web/login");
                // A temporary connection failure must not log out a valid user.
            }).finally(() => { pending = null; });
            return pending;
        };
        window.addEventListener("focus", check);
        window.addEventListener("pageshow", (event) => { if (event.persisted) check(); });
        document.addEventListener("visibilitychange", () => { if (!document.hidden) check(); });
        window.addEventListener("storage", (event) => {
            if (event.key === identityKey && event.newValue !== JSON.stringify(uid)) check();
        });
        env.bus.addEventListener("RPC:RESPONSE", (event) => {
            if (event.detail.error && event.detail.data?.params && event.detail.data.params.model) check();
        });
        return { check };
    },
};

registry.category("services").add("campus_session", campusSessionService);
