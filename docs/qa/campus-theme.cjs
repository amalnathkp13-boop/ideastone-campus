// Shared by the existing authenticated browser suites. Check rendered styles,
// including data-backed headings, rather than merely searching the stylesheet.
const assert = require('node:assert/strict');
async function assertCampusTheme(page) {
    const result = await page.evaluate(() => {
        const visible = el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden';
        const hero = '.student_welcome,.academic_hero,.profile_hero,.timetable_hero,.campus_faculty_welcome,.mentor_hero,.parent_welcome,.admin_overview .hero,.campus_admissions_workspace .hero,.campus_students_workspace .hero,.campus_students_workspace .detailhero,.fee_view .balance-card';
        const headings = [...document.querySelectorAll('h1,h2,h3')].filter(visible).map(el => {
            const style = getComputedStyle(el);
            const banner = !!el.closest(hero);
            const panelTitle = el.matches(':is(.panel-head,.panelhead,.section-head,.sectionhead,.academic_card_head,.profile_card_head,.timetable_card_head,.attendance_panel_head,.exam_panel_head,.coe-panel-head) h3:first-child');
            return {text:el.textContent.trim().slice(0,80), font:style.fontFamily, size:style.fontSize,
                weight:style.fontWeight, color:style.color, expectedSize:el.tagName === 'H1' ? (innerWidth < 768 ? '28px' : '31px') : el.tagName === 'H2' ? (banner ? '21px' : '17px') : panelTitle ? '17px' : '15px',
                expectedWeight:el.tagName === 'H3' && !panelTitle ? '650' : '760',
                expectedColor:banner || el.closest('.vcet_login_visual') ? 'rgb(255, 255, 255)' : el.tagName === 'H1' ? 'rgb(14, 49, 81)' : 'rgb(16, 45, 73)'};
        });
        const root = getComputedStyle(document.documentElement);
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
            button:buttonStyle ? {background:buttonStyle.backgroundColor, size:buttonStyle.fontSize, weight:buttonStyle.fontWeight} : null};
    });
    assert.equal(result.blue, '#1769d2', 'Shared theme missing from the asset bundle');
    assert.equal(result.canvas, '#f4f7fb');
    for (const h of result.headings) {
        assert.match(h.font, /^Roboto,/, `${h.text}: font family`);
        assert.equal(h.size, h.expectedSize, `${h.text}: size`);
        assert.equal(h.weight, h.expectedWeight, `${h.text}: weight`);
        assert.equal(h.color, h.expectedColor, `${h.text}: color`);
    }
    if (result.icon) assert.match(result.icon, /FontAwesome/, 'Text rules overwrote the icon font');
    for (const meta of result.metadata) {
        assert.equal(meta.size, '12px', 'Metadata size drifted');
        assert.equal(meta.weight, '400', 'Metadata weight drifted');
        assert.equal(meta.color, 'rgb(97, 123, 150)', 'Metadata color drifted');
    }
    if (result.card) {
        assert.equal(result.card.background, 'rgb(255, 255, 255)', 'Card background drifted');
        assert.equal(result.card.radius, '15px', 'Card radius drifted');
    }
    if (result.button) {
        assert(['rgb(23, 105, 210)', 'rgb(17, 83, 168)'].includes(result.button.background), 'Primary or hover color drifted');
        assert.equal(result.button.size, '12px', 'Primary font size drifted');
        assert.equal(result.button.weight, '750', 'Primary font weight drifted');
    }
}
module.exports = {assertCampusTheme};
