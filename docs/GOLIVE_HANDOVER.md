# Apex POB — Go-Live & Handover

> Deployment, accounts, backups, and security summary for production handover.
> Items marked «FILL IN» are operational decisions the operator/owner must complete.

---

## 1. Environments
| | Dev | Production |
|---|---|---|
| Compose file | `docker-compose.yml` | `docker-compose.prod.yml` |
| Nginx config | `frontend-react/nginx.conf` | `nginx/conf.d/pob.conf` |
| TLS | none (HTTP) | 443 (cert in `nginx/certs/`) |
| Env file | `.env` | `.env.prod` (gitignored) |

**Always deploy production with the prod compose** — the dev stack is HTTP-only and source-mounted.

## 2. Production deploy
```bash
cd /path/to/POB_Version2.0
# 1. Provision TLS certs into nginx/certs/{fullchain,privkey}.pem
#    - DDNS hostname  → Let's Encrypt (recommended)
#    - IP-only        → self-signed (browser warning) [currently in use]
# 2. Create and fill .env.prod (copy from .env.prod.example)
# 3. Bring up the stack
docker compose -f docker-compose.prod.yml up -d --build
# 4. Verify
curl -k https://<server>/health
```
Services started: postgres, redis, db-init, backend, celery-worker, celery-beat, frontend, nginx, db-backup, prometheus, grafana, alertmanager.

## 3. Network / access
- **Users:** `https://<server>` (443).
- **ADMS readers:** `http://<server>` (port **80**, HTTP) — `/iclock/*` stays on 80; readers can't do TLS.
- **Monitoring (Grafana):** `https://<server>/monitoring` — restricted to private/VPN ranges.
- Gateway port-forwards public **80 / 443** → server. (443 only; 80 is required for ADMS.)
- Current host: Docker Desktop on the Mac at LAN IP **192.168.101.237** (readers push to `http://192.168.101.237/iclock/`). Earlier server: public 41.67.137.161 / LAN 192.168.0.235. Recommendation: a **fixed LAN IP or DDNS hostname** so an address change doesn't break readers/cert.
- **`ALLOWED_HOSTS` in `.env.prod` must list the address readers push to** (the server's LAN IP or hostname). Otherwise every push is refused with `400 Invalid host header` and punches are silently lost.

## 4. Accounts & credentials
- Default admin: username `admin` (password **must be changed** at go-live).
- `GLOBAL_ADMIN_PASSWORD` (emergency superuser bypass) is set in `.env.prod` — store in your secrets manager. «FILL IN owner»
- Grafana admin user/password in `.env.prod`.
- **Do not commit `.env.prod` or `nginx/certs/`** (already gitignored). Recreate `.env.prod` on each server — it is intentionally never pushed to git.
- Database user `pob_user` currently uses a weak password — **rotate before/at go-live** («FILL IN»: `ALTER USER pob_user WITH PASSWORD ...` and update `.env.prod`).

## 5. Data migration (new server)
Docker volumes are per-machine; a fresh deploy starts empty. To migrate:
```bash
# OLD server
docker exec pob_postgres pg_dump -U pob_user -Fc pob_system > pob_db.dump
docker run --rm -v pob_version20_uploads_data:/d -v "$PWD":/b alpine tar czf /b/uploads.tar.gz -C /d .
# transfer pob_db.dump, uploads.tar.gz, .env.prod, nginx/certs/ to NEW server
# NEW server
docker compose -f docker-compose.prod.yml up -d postgres
docker exec -i pob_postgres pg_restore -U pob_user -d pob_system --clean --if-exists < pob_db.dump
# restore upload volumes, then: docker compose -f docker-compose.prod.yml up -d --build
```

## 6. Backups
- `db-backup` service runs a daily `pg_dump`; keeps 7 daily + 4 weekly + 3 monthly.
- Set `BACKUP_DIR` in `.env.prod` to a **NAS mount** for off-box storage (else local volume). «FILL IN NAS path»
- **Recommend:** verify a restore works, and confirm a retention/off-site policy.

## 7. Monitoring & alerting
- Prometheus + Grafana (`/monitoring`) + Alertmanager.
- Configure Alertmanager email (`ALERTMANAGER_*` in `.env.prod`) so BackendDown/DBDown alerts reach on-call. «FILL IN on-call email»

## 8. Security summary (client-facing)
- **Transport:** HTTPS/TLS for all user traffic; HSTS + CSP headers. (ADMS reader traffic is HTTP on 80 by device limitation, on the operator's controlled link.)
- **Authentication:** JWT access/refresh tokens with a strict type allowlist; optional **MFA**; login lockout + rate limiting (nginx + app).
- **Authorisation:** role-based access control (RBAC); admin-only configuration/integration endpoints.
- **Secrets:** integration credentials encrypted at rest; config validators refuse insecure default secrets in production; outbound integration URLs validated (https-only, SSRF-guarded).
- **Auditing:** sensitive actions recorded in the audit log; per-sync logs for HR/finance exports.
- **Data integrity:** attendance computed from a single authoritative source; HR/finance exports are idempotent (no double-pay).
- Full internal assessment: `PRODUCTION_READINESS_DEEP_ANALYSIS.md`.

## 9. Outstanding go-live checklist
- [ ] DDNS hostname + Let's Encrypt cert (replace self-signed)
- [ ] Change `admin` password; set strong `GLOBAL_ADMIN_PASSWORD`; rotate DB password
- [ ] **Alerts**: Settings → Email (address + app password) and Settings → WhatsApp & Alerts (provider + response team) — see §13. Until then every alert is logged as *skipped*.
- [ ] Set `DEVICE_SCAN_SUBNETS` (for any same-LAN readers); verify `GET /api/device/network-diagnostics`
- [ ] Validate Business Central + SeamlessHR against vendor sandboxes (`docs/INTEGRATIONS.md`)
- [ ] Confirm backup destination + test restore
- [ ] Configure Alertmanager recipients
- [ ] Run the **full test suite** on the release build: `./scripts/run_tests.sh` (expected: 207 passed, 1 skipped). `./scripts/run_safety_tests.sh` runs just the go-live safety tests (mustering, alerts, controllers, reports). Both use a throwaway database and a throwaway container — never the live data — and the suite **refuses to run** against any database whose name lacks "test".
- [ ] **Renew the licence** (expired 2026-08-31 — unauthenticated requests get 402)
- [ ] Complete §10 (SeamlessHR → Marconi switch-over), §11 (site setup) and §14 (ZKTeco controller commissioning)

## 10. SeamlessHR → Marconi switch-over
Everything was proven on SeamlessHR's sandbox (Integration Company); Marconi uses the same API. On the day:
1. **Back up**: `docker exec pob_postgres pg_dump -U pob_user pob_system > pre_marconi.sql`.
2. **Remove the sandbox staff** (≈344 `hr_source='SEAMLESSHR'` records) and the HR sync history — a pull adds/updates but never deletes, so they would otherwise sit beside Marconi's staff in POB and mustering.
3. **Settings → HR Integration**: API Base URL = SeamlessHR's **production** URL (ask SeamlessHR — the form defaults to the sandbox), Client ID, Client Secret → **Test Connection** → **Pull employees** (≈2–3 min; the sandbox throttles, the pull retries and pages slowly by design).
4. **Attendance IDs** (= the reader PIN, = what SeamlessHR matches punches on): Settings → Attendance IDs → *Adopt from SeamlessHR* (needs Time & Attendance read on Marconi's client) or *Import* an export. Staff without one are **not** sent to SeamlessHR.
5. **Verify one person end to end**: enrol → tap first thing in the morning and again later → Attendance shows clock-in/out → Sync for that day → SeamlessHR reply says `N sent successfully, 0 failed`.
6. In SeamlessHR's T&A module (Schedule Manager → Records, or Reports → Attendance) HR must **create schedules** for staff; their rotational limits (currently 1 h / 1 shift per week) must be corrected.

Open with SeamlessHR (sandbox): records rejected with "0 sent, 1 failed" and no reason since 15 Oct ~18:40; `GET /v1/attendances` "Unauthorized access"; employee list intermittently 400; record #345 unreadable. Draft: `docs/SeamlessHR_sandbox_questions.md`.

## 11. Site setup (before go-live)
- **Zones**: replace the 7 demo zones with the real layout — site → areas → rooms (**Parent Zone**), muster points (type Muster Point), and the boundary zones (**Site boundary** switch: gate / helideck / jetty). Place each on the GPS map (*Place on map*). Name the helideck/jetty zones exactly as flights/journeys name them (e.g. "Helipad") so arrivals land there.
- **Readers**: Marconi's door readers are wired to **ZKTeco C3/inBio controllers** — set them up per §14. (Stand-alone ADMS terminals such as the F18 are set under Devices → reader purpose, then Zones → assign.)
- **Shifts**: set per department (all currently fall back to "Day 07-19 Mon–Fri"). Attendance uses **first punch = in, last punch = out** in site time (`att_rules.punch_state_mode = first_last`; `SITE_TIME_ZONE`, default Africa/Lagos).
- **Roles** (Settings → Roles): give **journey.approve** to supervisors and **transport.override** to the logistics/helideck lead. View/manage rights follow `pob.view` / `pob.change`.
- **Reader memory**: the F18 still stores June–July test punches; clear its attendance log before go-live so a stamp reset cannot re-send them.

## 12. How POB is decided (for operators)
- **On board**: any tap at a site reader; arrival of an inbound flight (status *Completed*); completion of an "arriving at site" land journey.
- **Off board**: Exit through a **site-boundary** zone; departure of an outbound flight (*In transit*); start of a "leaving site" land journey; inactivity auto-checkout (Settings → Database, if enabled).
- Moving between zones never changes POB; leaving a room puts the person in its parent zone. Readers that upload late cannot move anyone backwards.
- Confirming a passenger means *boarded* only — POB moves with the flight. Cancelling a flight in transit, offloading or removing a passenger undoes it.

## 13. Alerts — email, WhatsApp and the response team
Every muster, emergency, panic/duress alarm, missing-person escalation, all-clear, controller-offline and scheduled report goes out on **every channel that is set up**, and is written to the delivery log (Settings → WhatsApp & Alerts → Alert log; also Emergency → Notifications) with *sent / failed / skipped* and the reason.
1. **Email** — Settings → **Email**: the alert mailbox's address + an **app password** → **Connect** (ApexPOB finds the server and proves the login before saving) → **Send a test**.
   - Marconi (`marconi.ng`) is on **Microsoft 365**: the mailbox needs multi-factor sign-in (to create an app password) and an M365 admin must allow **Authenticated SMTP** for it (admin centre → Users → user → Mail → Manage email apps).
2. **WhatsApp** — Settings → **WhatsApp & Alerts**: provider **Meta Cloud API** (recommended) → Phone number ID, permanent access token, and an approved **Utility** template with one variable, e.g. `🚨 ApexPOB alert: {{1}}`. Termii / Twilio also supported. Switch **On** → **Save** → **Send a test**.
3. **Emergency response team** (same tab) — OIM, HSE lead, control room, medic: name, role, WhatsApp number, email. They get every alert wherever they are; staff only get alerts while **on board**.
4. Muster lists are emailed to the response team at **06:00 and 18:00** (printable paper fallback).

## 14. ZKTeco controller commissioning (C3 / inBio)
Readers (IN and OUT per door) are wired to C3 controllers; ApexPOB talks to each panel directly on **TCP 4370** (no Windows PC / ZKAccess needed) and polls it every few seconds.
1. **Network**: fixed IP / DHCP reservation per panel; this server must reach each panel on port 4370.
2. **Access Control → Controllers → Add controller**: name, IP, model, comm password (if set). Doors and reader ports are created automatically.
3. Per **reader port**: assign its **zone** and its **purpose** — *Clock in / out* (main gate IN and OUT — counts for attendance and SeamlessHR), *Door access only* (internal doors), or *Muster point*.
4. Per **door** (*Doors (card / PIN), fire exits & sirens*): how it opens — **Card**, **Card + PIN** (control room, stores, server room) or **PIN only** — and its fire role: **Fire exit — unlock in a fire**, Lock in a fire, or No change.
5. **Sirens / strobes** on AUX outputs → **Add** → **Test 3 s**. **Fire alarm panel** dry contact on an AUX input → edit controller → *Fire alarm wired to* + *opens/closes* → tripping it starts fire mode by itself.
6. **People**: everyone needs an **Attendance ID** (panel user ID = SeamlessHR ID) and a **card** — *Cards & PINs* → tap a new card on any reader and issue it, or paste card numbers from Excel; **Door PINs** → *Create & send missing PINs* (sent privately by WhatsApp/email; stored encrypted, shown once). Report **Door access readiness** shows who is missing what.
7. **Sync users** on each controller (also nightly at 02:30): loads active staff, removes leavers (expired on the panel; only users ApexPOB loaded are touched).
8. **Hardware acceptance — on the first panel, before the rest:** Probe ✓ → Sync users with one test person → their card opens the door, card + PIN works on a keypad door → mark them a leaver, sync → card refused → siren test → a fire exit held open by fire mode and re-locked on *clear* → fire alarm input trips fire mode. *(The panel write used for loading users is verified here — it has only been tested against a simulated panel.)*
9. A panel unreachable for 5 minutes alerts the response team (and again when it is back).
- Known limit: C3 **lockdown** closes held-open doors but valid cards still open them.

## 15. Mustering & emergencies (for operators)
- **Live muster board** (Emergency & Mustering → *Live muster board*, made for the control-room TV): one-tap **General alarm / Fire / Gas / Man down / Drill** — whole-site muster of everyone on board **plus checked-in visitors**; Fire/Gas also open fire exits and sound sirens. Shows % accounted, safe per assembly point, and the missing list by last-seen location with **Safe / Hurt** buttons for wardens. **End muster** sends the all-clear.
- People are counted safe by tapping any reader at a muster point; someone who taps out at the site gate during a muster is **Left site** (accounted for).
- Missing people escalate to the response team at 10 / 20 / 30 / 60 minutes (one message per level, not per person).
- **Print muster list** on the board = paper fallback for power or network loss.
