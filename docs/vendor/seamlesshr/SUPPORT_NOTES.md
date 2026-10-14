# SeamlessHR support-site findings (retrieved 2026-10-14)

Summarised from support.seamlesshr.com. These are paraphrases, not vendor text;
re-check the live pages before relying on them.

## Attendance ID = Personnel ID on the biometric device
- `time-and-attendance-faqs`: the Personnel ID is "the ID assigned to employees on
  the Biometric Device"; "at the point of upload, the Personnel ID on the biometric
  device is the attendance ID" stored on each employee's profile. Yes, they are the same.
- Attendance IDs are loaded in bulk with the admin "Upload Attendance IDs" template
  (`how-to-upload-attendance-ids`; newer path: Time Management > Device Manager >
  Manage Employee ID > Upload attendance ID, `how-to-upload-attendance-id`).
- `faqs-on-attendance-management`: if a punch does not show up for an employee,
  check the employee is on a schedule AND has an Attendance ID.

## Device provisioning (SeamlessHR's own deployment model)
- `how-to-setup-the-biometric-machine-on-the-time-and-attendance-module`: the device
  points its ADMS cloud server at `attendance.seamlesshrms.com`, and the device
  serial number is sent to SeamlessHR to be "provisioned". Apex POB readers do NOT
  do this (readers talk only to Apex POB), so whether `/biometric/process` requires
  a provisioned `deviceSN` is UNCONFIRMED.

## Still not answered anywhere public
- Allowed values of `type` (doc default CLOCK_IN, doc code samples use "sm").
- Whether `dateTime` without an offset is read as UTC or local time.
- Why the sandbox key gets "Unauthorized access" on `GET /v1/attendances` and a
  generic 400 on `GET /v1/employees`.
- Whether `/biometric/process` rejects unknown `attendanceId` / unprovisioned `deviceSN`
  (the sandbox returned HTTP 200 with "0 sent successfully, 1 failed" for both).
