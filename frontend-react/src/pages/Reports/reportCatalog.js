/**
 * Curated report library, grouped by the question people come with.
 *
 * filters:
 *   date: 'none' | 'single' | 'range' | 'month' | 'monthNumber'
 *   dateDefault: for single dates — 'today' | 'yesterday'
 *   extra: any of 'department', 'zone', 'company', 'person', 'search',
 *          'flightStatus', 'direction', 'journeyStatus', 'musterEvent', 'changeType'
 * kpis: summary keys to show (in order) with labels; anything else is ignored.
 *
 * Reports for hidden modules (Payroll, MTD, Meetings) and BioTime door-controller
 * leftovers are intentionally not listed; their backend handlers still exist.
 */

export const REPORT_GROUPS = [
  {
    key: 'onsite',
    title: "Who's on site",
    blurb: 'Personnel on board right now, where they are, and who arrived or left.',
    color: '#2563eb',
    reports: [
      { code: 'pob.daily_manifest', title: 'POB manifest', desc: 'Everyone on board now, with zone, company and days on board.',
        filters: { date: 'none', extra: ['department', 'company', 'zone'] } },
      { code: 'zone.current_occupancy', title: 'Where people are now', desc: 'Each zone and who is inside it at this moment.',
        filters: { date: 'none', extra: [] } },
      { code: 'pob.headcount_by_company', title: 'Headcount by company', desc: 'On-board numbers by company, department and type.',
        filters: { date: 'none', extra: ['company'] } },
      { code: 'pob.crew_change', title: 'Crew change', desc: 'Who arrived and who left on a day — flights, journeys and gate crossings.',
        filters: { date: 'single', dateDefault: 'today', extra: ['changeType'] },
        kpis: { mobilize_count: 'Arrived', demobilize_count: 'Left', net_change: 'Net change' } },
      { code: 'pob.rotation_overdue', title: 'Rotation overdue', desc: 'People on board longer than their rotation allows.',
        filters: { date: 'none', extra: ['department', 'company'] } },
    ],
  },
  {
    key: 'attendance',
    title: 'Attendance & time',
    blurb: 'Clock-ins, lateness, absence and overtime — the figures sent to payroll.',
    color: '#059669',
    reports: [
      { code: 'att.daily', title: 'Daily attendance', desc: 'Clock-in, clock-out, hours, late and overtime per person per day.',
        filters: { date: 'range', extra: ['department', 'person'] } },
      { code: 'att.summary', title: 'Attendance summary', desc: 'Totals per person over a period.',
        filters: { date: 'range', extra: ['department'] } },
      { code: 'att.monthly', title: 'Monthly timesheet', desc: 'A month at a glance for each person.',
        filters: { date: 'month', extra: ['department'] } },
      { code: 'att.late', title: 'Late arrivals', desc: 'Who clocked in after shift start, and by how much.',
        filters: { date: 'single', dateDefault: 'yesterday', extra: ['department'] } },
      { code: 'att.early', title: 'Early departures', desc: 'Who left before shift end.',
        filters: { date: 'single', dateDefault: 'yesterday', extra: ['department'] } },
      { code: 'att.absent', title: 'Absences', desc: 'Scheduled to work, did not attend.',
        filters: { date: 'single', dateDefault: 'yesterday', extra: ['department'] },
        kpis: { total_absent: 'Absent' } },
      { code: 'att.ot', title: 'Overtime', desc: 'Hours worked beyond the scheduled shift.',
        filters: { date: 'single', dateDefault: 'yesterday', extra: ['department'] } },
      { code: 'att.leave', title: 'Leave', desc: 'Approved leave in the period.',
        filters: { date: 'range', extra: ['department'] } },
      { code: 'att.exceptions', title: 'Exceptions', desc: 'Missing punches and other attendance exceptions.',
        filters: { date: 'range', extra: ['department'] } },
      { code: 'att.shift', title: 'Shift schedule', desc: 'Who is rostered on which shift.',
        filters: { date: 'range', extra: [] } },
    ],
  },
  {
    key: 'movement',
    title: 'Movement & access',
    blurb: 'Zone entries and exits, a person’s trail, and security events at doors.',
    color: '#7c3aed',
    reports: [
      { code: 'zone.access_log', title: 'Zone access log', desc: 'Every zone entry and exit.',
        filters: { date: 'range', extra: ['zone', 'person'] } },
      { code: 'zone.person_trail', title: 'Person movement trail', desc: 'Where one person went, and how long they stayed.',
        filters: { date: 'range', extra: ['person'], required: ['person'] } },
      { code: 'pob.zone_occupancy_history', title: 'Zone occupancy history', desc: 'Entries, exits and unique visitors per zone per day.',
        filters: { date: 'range', extra: ['zone'] } },
      { code: 'zone.security_events', title: 'Security events', desc: 'Door alarms, forced entries and lock events.',
        filters: { date: 'range', extra: ['zone'] } },
    ],
  },
  {
    key: 'safety',
    title: 'Safety & mustering',
    blurb: 'Muster results, who was missing, drill performance and emergencies.',
    color: '#dc2626',
    reports: [
      { code: 'muster.event', title: 'Muster events', desc: 'Every muster and drill with expected, safe and missing counts.',
        filters: { date: 'none', extra: [] } },
      { code: 'muster.missing', title: 'Missing persons', desc: 'Who was not accounted for, with last known zone.',
        filters: { date: 'none', extra: ['musterEvent'] } },
      { code: 'muster.compliance', title: 'Muster compliance', desc: 'Accounted-for percentage and grade per event.',
        filters: { date: 'range', extra: [] } },
      { code: 'muster.drill_log', title: 'Drill log', desc: 'Drills held and how long they took.',
        filters: { date: 'range', extra: [] } },
      { code: 'muster.headcount', title: 'Headcount timeline', desc: 'How the safe count rose during a muster.',
        filters: { date: 'none', extra: ['musterEvent'], required: ['musterEvent'] } },
      { code: 'emergency.events', title: 'Emergency log', desc: 'Emergencies raised and their outcome.',
        filters: { date: 'range', extra: [] } },
      { code: 'emergency.response', title: 'Response times', desc: 'How quickly emergencies were acknowledged and closed.',
        filters: { date: 'range', extra: [] } },
    ],
  },
  {
    key: 'travel',
    title: 'Travel',
    blurb: 'Flights, voyages, passengers and land journeys.',
    color: '#0891b2',
    reports: [
      { code: 'travel.flights', title: 'Flights & voyages', desc: 'Each trip with passengers, no-shows and delay.',
        filters: { date: 'range', extra: ['flightStatus'] },
        kpis: { flights: 'Trips', passengers_boarded: 'Boarded', no_shows: 'No-shows', on_time_pct: 'On time %' } },
      { code: 'travel.passengers', title: 'Passengers', desc: 'Who flew in or out, and when POB was updated.',
        filters: { date: 'range', extra: ['direction', 'search'] },
        kpis: { passengers: 'Passengers', arriving: 'Arriving', leaving: 'Leaving', no_shows: 'No-shows' } },
      { code: 'travel.journeys', title: 'Land journeys', desc: 'Journey plans with risk, approvals, check-ins and concerns.',
        filters: { date: 'range', extra: ['journeyStatus'] },
        kpis: { journeys: 'Journeys', high_risk: 'High risk', completed: 'Completed', concerns_reported: 'Concerns' } },
    ],
  },
  {
    key: 'visitors',
    title: 'Visitors',
    blurb: 'Who visited, who they saw, and who stayed too long.',
    color: '#d97706',
    reports: [
      { code: 'visitor.daily_log', title: 'Visitor log', desc: 'Visitors on a day with check-in and check-out.',
        filters: { date: 'single', dateDefault: 'today', extra: [] } },
      { code: 'visitor.overstay', title: 'Overstays', desc: 'Visitors still on site beyond their allowed hours.',
        filters: { date: 'none', extra: [] } },
      { code: 'visitor.host_report', title: 'Visits by host', desc: 'How many visitors each employee hosted.',
        filters: { date: 'range', extra: [] } },
      { code: 'visitor.blacklist', title: 'Blacklist', desc: 'Visitors refused entry, and why.',
        filters: { date: 'none', extra: [] } },
    ],
  },
  {
    key: 'people',
    title: 'People & devices',
    blurb: 'Staff records synced from SeamlessHR, and reader health.',
    color: '#475569',
    reports: [
      { code: 'personnel.employee_list', title: 'Employee list', desc: 'All staff with department, position and status.',
        filters: { date: 'none', extra: ['department', 'search'] } },
      { code: 'personnel.dept_summary', title: 'Department summary', desc: 'Headcount per department.',
        filters: { date: 'none', extra: [] } },
      { code: 'personnel.birthday', title: 'Birthdays', desc: 'Staff birthdays by month.',
        filters: { date: 'monthNumber', extra: [] } },
      { code: 'personnel.anniversary', title: 'Work anniversaries', desc: 'Service anniversaries by month.',
        filters: { date: 'monthNumber', extra: ['department'] } },
      { code: 'device.status', title: 'Reader status', desc: 'Every reader with last contact and enrolled users.',
        filters: { date: 'none', extra: [] } },
      { code: 'device.offline', title: 'Offline readers', desc: 'Readers not heard from recently.',
        filters: { date: 'none', extra: [] } },
    ],
  },
  {
    key: 'audit',
    title: 'Audit',
    blurb: 'Sign-ins and changes made in ApexPOB.',
    color: '#334155',
    reports: [
      { code: 'system.login_log', title: 'Sign-ins', desc: 'Successful and failed sign-ins with IP and device.',
        filters: { date: 'range', extra: [] },
        kpis: { total_attempts: 'Attempts', failed: 'Failed' } },
      { code: 'system.operation_log', title: 'Activity log', desc: 'Who did what, and when.',
        filters: { date: 'range', extra: [] } },
      { code: 'system.data_audit', title: 'Data changes', desc: 'Records created, changed and deleted.',
        filters: { date: 'range', extra: [] } },
    ],
  },
];

export const ALL_REPORTS = REPORT_GROUPS.flatMap(g => g.reports.map(r => ({ ...r, group: g })));
export const findReport = (code) => ALL_REPORTS.find(r => r.code === code) || null;
