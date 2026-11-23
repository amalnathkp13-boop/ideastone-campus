// Shared by the existing authenticated browser suites. Check rendered styles,
// including data-backed headings, rather than merely searching the stylesheet.
// Callers use reduced motion so checks sample the final palette, not a hover transition.
const assert = require('node:assert/strict');
async function assertCampusTheme(page) {
    const result = await page.evaluate(() => {
        const visible = el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden';
        const headings = [...document.querySelectorAll('h1,h2,h3')].filter(visible).map(el => {
            const style = getComputedStyle(el);
            const panelTitle = el.matches(':is(.panel-head,.panelhead,.section-head,.sectionhead,.academic_card_head,.profile_card_head,.timetable_card_head,.attendance_panel_head,.exam_panel_head,.coe-panel-head) h3:first-child');
            const profile = !!el.closest('.student_profile_view');
            const profileHero = profile && !!el.closest('.profile_hero');
            let expectedSize = el.tagName === 'H1' ? (innerWidth < 768 ? '24px' : '26px') : el.tagName === 'H3' ? (panelTitle ? '17px' : '15px') : '17px';
            let expectedWeight = el.tagName === 'H1' ? '780' : el.tagName === 'H3' && !panelTitle ? '650' : '760';
            let expectedColor = null;
            if (profile) {
                expectedWeight = '760';
                expectedColor = 'rgb(16, 45, 73)';
                if (el.tagName === 'H1') {
                    expectedSize = innerWidth <= 440 ? '27px' : '31px';
                    expectedColor = 'rgb(14, 49, 81)';
                } else if (profileHero) {
                    expectedSize = innerWidth <= 800 ? '21px' : '24px';
                    expectedColor = 'rgb(255, 255, 255)';
                }
            }
            return {text:el.textContent.trim().slice(0,80), font:style.fontFamily, size:style.fontSize,
                weight:style.fontWeight, color:style.color, tag:el.tagName, profile,
                expectedSize, expectedWeight, expectedColor};
        });
        const workspace = document.querySelector('.o_web_client:has(.campus_navigation),.campus_portal,.student_workspace,.parent_workspace,.vcet_login,.qp-faculty,.qp-hod,.coe-workspace');
        const root = getComputedStyle(workspace || document.documentElement);
        const icon = [...document.querySelectorAll('.fa')].find(visible);
        const card = [...document.querySelectorAll('.academic_card,.student_panel,.profile_card,.timetable_card,.campus_panel,.sa_panel,.swa_panel,.coe-panel,.o_form_sheet')].find(visible);
        const primary = [...document.querySelectorAll('.btn-primary,.academic_button,.coe-btn.primary,.sa_primary,.swa_primary')].find(visible);
        const cardStyle = card ? getComputedStyle(card) : null;
        const buttonStyle = primary ? getComputedStyle(primary) : null;
        const metadata = [...document.querySelectorAll('.kpi-meta,.kpi-label,.academic_metric_label,.staff_profile_subtitle')].filter(visible).map(el => {
            const style = getComputedStyle(el);
            return {size:style.fontSize, weight:style.fontWeight, color:style.color};
        });
        return {headings, blue:root.getPropertyValue('--ui-blue').trim(), canvas:root.getPropertyValue('--ui-canvas').trim(), icon:icon ? getComputedStyle(icon).fontFamily : null,
            metadata,
            card:cardStyle ? {background:cardStyle.backgroundColor, radius:cardStyle.borderRadius} : null,
            button:buttonStyle ? {background:buttonStyle.backgroundColor, size:buttonStyle.fontSize, weight:buttonStyle.fontWeight,
                profile:!!primary.closest('.student_profile_view')} : null};
    });
    assert.equal(result.blue, '#1769e8', 'Shared theme missing from the asset bundle');
    assert.equal(result.canvas, '#f4f7fb');
    for (const h of result.headings) {
        assert.match(h.font, /^Inter,/, `${h.text}: font family`);
        if (h.tag === 'H2' && !h.profile) assert(['17px', '21px'].includes(h.size), `${h.text}: size drifted: ${h.size}`);
        else assert.equal(h.size, h.expectedSize, `${h.text}: size`);
        assert.equal(h.weight, h.expectedWeight, `${h.text}: weight`);
        if (h.profile) assert.equal(h.color, h.expectedColor, `${h.text}: reference color`);
        else assert(['rgb(19, 42, 68)', 'rgb(255, 255, 255)'].includes(h.color), `${h.text}: theme color drifted: ${h.color}`);
    }
    if (result.icon) assert.match(result.icon, /FontAwesome/, 'Text rules overwrote the icon font');
    for (const meta of result.metadata) {
        assert.equal(meta.size, '12px', 'Metadata size drifted');
        assert.equal(meta.weight, '400', 'Metadata weight drifted');
        assert(['rgb(85, 107, 130)', 'rgb(215, 234, 255)'].includes(meta.color), 'Metadata color drifted');
    }
    if (result.card) {
        assert.equal(result.card.background, 'rgb(255, 255, 255)', 'Card background drifted');
        assert.equal(result.card.radius, '15px', 'Card radius drifted');
    }
    if (result.button) {
        const primaryColor = result.button.profile ? 'rgb(23, 105, 210)' : 'rgb(23, 105, 232)';
        assert([primaryColor, 'rgb(17, 83, 168)'].includes(result.button.background), `Primary or hover color drifted: ${result.button.background}`);
        assert.equal(result.button.size, '14px', 'Primary font size drifted');
        assert(['700', '750'].includes(result.button.weight), 'Primary font weight drifted');
    }
}
module.exports = {assertCampusTheme};
