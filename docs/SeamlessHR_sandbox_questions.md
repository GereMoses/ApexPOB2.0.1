Subject: ApexPOB ↔ SeamlessHR sandbox (Integration Company) — results and open items

Hello SeamlessHR team,

Thank you for the sandbox credentials. ApexPOB is now connected to
https://api-sandbox.seamlesshr.app, and we have the following results and questions.

WORKING
- Authentication with x-client-id / x-client-secret.
- GET /v1/employees: 344 of 345 employees pulled (names, departments, job titles,
  hire dates, exit status).
- POST /biometric/process: one test punch at 13:59 Lagos time on 15 Oct 2026 was
  accepted ("1 attendance records sent successfully, 0 failed").

ISSUES WE NEED YOUR HELP WITH

1. Attendance records are now rejected, and the reply gives no reason.
   From about 18:40 Lagos time on 15 Oct, every POST /biometric/process returns HTTP 200
   with "0 attendance records sent successfully, 1 attendance records failed". This
   includes an exact re-send of the record that succeeded at 13:59, and punches for
   attendanceId 50000083 and 50000085 with deviceSN "0583142500128" (our ZKTeco F18)
   and "POB-TEST".
   - Why are these records failing? Can the response include the reason per record?
   - Does a punch fail if the employee has no schedule, has no Attendance ID set, or
     falls outside a shift?
   - Does deviceSN need to be registered on your side first?

2. GET /v1/attendances returns 400 {"message":"Unauthorized access"} with the documented
   parameters (dateType=custom&startDate=…&endDate=…). Please enable Time & Attendance
   read access for this client, and confirm it will be enabled for the Marconi
   production client. We use it to read each employee's Attendance ID, which becomes
   their PIN on the readers.

3. Attendance ID format for Marconi. Marconi employee codes look like "MARC 14256".
   Is each employee's Attendance ID the number from the code ("14256"), or a separate
   value? Our readers can only hold digits.

4. Visibility. Please provide a sandbox Time & Attendance login (the equivalent of
   marconi.seamlesstime.io), so we can confirm that punches appear under
   Schedule Manager → Records and Reports → Attendance. Please also confirm whether
   punches for employees "Without a schedule" are shown.

5. GET /v1/employees reliability.
   - Valid requests often return 400 "An error occurred while processing the request",
     and repeating the call succeeds. Are there rate limits, or a recommended page
     size and delay?
   - The 345th record fails every time, even when requested alone
     (limit=1&page=345). Please check that record.

6. Production. What is the production base URL for the Marconi tenant? Is the record
   format for /biometric/process identical there (attendanceId, dateTime in Lagos
   local time without an offset, type CLOCK_IN/CLOCK_OUT, deviceSN)?

How ApexPOB will send attendance: ZKTeco readers are connected to ApexPOB only.
ApexPOB calculates each employee's day (first punch = clock-in, last punch =
clock-out) and sends the previous day's CLOCK_IN and CLOCK_OUT for each employee
to /biometric/process once a day, at most 100 records per call.

Regards,

## Update — 28 Oct 2026
- `GET /v1/employees` now fails for **every** page and page size (`page=1&limit=5`, `page=1&limit=25`, `page=2&limit=25`) with HTTP 400 `{"message":"An error occurred while processing the request"}`. Authentication is accepted (no "Unauthorized"). Please check the sandbox tenant.
- **Attendance ID**: the employee list does not include it, and `GET /v1/attendances` is refused for our key. For Marconi, please either (a) enable Time & Attendance read for the integration client, or (b) confirm that each Marconi employee's Attendance ID equals the digits of their employee code (`MARC 14256` → `14256`) so ApexPOB can derive it.
- 28 Oct 09:50: the attendance push is **accepted again** (27 Oct record: "Sent 1/1"). The overnight rejection ("0 sent, 1 failed") was on the sandbox side. Future rejections now record SeamlessHR's own reply in the sync history.
