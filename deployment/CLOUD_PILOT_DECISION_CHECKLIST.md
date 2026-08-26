# MDRRMO Cloud Pilot Decision Checklist

Use this sheet with the MDRRMO decision-maker before any account is created,
data is transferred, or public cloud service is activated. Do not write
passwords, recovery codes, database addresses, or OAuth secrets on this sheet.

## 1. Official service owner

The service owner is the office identity that legally and operationally owns
the Streamlit, Aiven, GitHub, and Google OAuth configuration. It should remain
available even if an employee transfers, resigns, or changes duties.

- Approved office-controlled email: ______________________________
- Primary custodian name and position: ___________________________
- Backup custodian name and position: ____________________________
- Who may approve password or recovery changes: _________________

Decision guidance:

- Prefer an MDRRMO or LGU-controlled email, not a developer's personal email.
- Require multi-factor authentication wherever the service supports it.
- Store recovery codes using the office's approved secure procedure.
- Name at least two custodians so the system does not depend on one person.

## 2. Pilot application address

This is the web address pilot users will recognize and bookmark. The approved
name is also used in the Google sign-in callback and should not be changed
casually after configuration.

- Preferred address: `https://____________________.streamlit.app`
- Acceptable second choice: `https://____________________.streamlit.app`
- Office name to display to users: _______________________________
- Is access limited to approved pilot users?  Yes / No

Decision guidance:

- Use a short official name such as `mdrrmo-naic-pilot`.
- Avoid a person's name, a temporary event name, or confidential information.
- Treat the first deployment as a restricted pilot, not a public launch.

## 3. Approved pilot users and roles

List only the three to five people needed to test the complete workflow. Each
person receives the least-powerful role that still allows their assigned job.

| Person | Office email | Assigned role | Why access is needed | Approved by |
|---|---|---|---|---|
|  |  | Administrator |  |  |
|  |  | Encoder |  |  |
|  |  | Validator |  |  |
|  |  | Viewer or Executive |  |  |
|  |  | Optional Operations Officer |  |  |

Role summary:

- Administrator: manages authorized accounts and has full application access.
  Assign to a trusted system custodian, not every supervisor.
- Encoder: enters barangay and evacuation information but cannot approve it.
- Validator: reviews and validates submitted information but does not encode it.
- Viewer: sees only the situation dashboard.
- Executive: sees the dashboard plus situation reports and exports.
- Operations Officer: operates event, validation, evacuation, incident, and
  reporting workspaces but cannot administer user accounts.

Separation guidance:

- When staffing allows, the person who encodes a report should not validate the
  same report.
- Maintain at least one active Administrator and designate a backup custodian.
- Remove or deactivate access promptly when duties change.

## 4. Classification of the present database

Management must decide what the records currently on the laptop represent.
This determines whether anything may be copied to the cloud pilot.

Select one:

- [ ] Entirely disposable UAT/test data. It may be replaced or recreated.
- [ ] Contains real operational or personal information.
- [ ] Mixed test and real information.
- [ ] Unknown; inspection is required before any transfer.

- Person who confirmed the classification: ______________________
- Date confirmed: ______________________________________________
- Records approved for the first cloud pilot: ___________________

Decision guidance:

- If the answer is real, mixed, or unknown, do not copy the database yet.
- Begin the cloud pilot with a new empty database and clearly marked test data.
- Obtain the appropriate privacy, records-management, and third-party cloud
  approval before transferring official or personal information.

## 5. Independent backup destination

Streamlit application storage is temporary and is not an approved database
backup location. Aiven provider recovery is useful, but the office should also
retain an independent encrypted copy outside both Aiven and Streamlit.

- Approved encrypted destination: _______________________________
- Office or person responsible for it: __________________________
- Who may retrieve a backup: ___________________________________
- Planned backup frequency: ____________________________________
- Planned retention period: ____________________________________
- Planned restore-test frequency: _______________________________

Not acceptable:

- GitHub or any source-code repository;
- a public sharing link;
- ordinary email attachments;
- the Streamlit application filesystem;
- an unencrypted personal USB drive or personal cloud account.

## 6. Cloud, privacy, and operating approval

- Aiven approved to store pilot database records?  Yes / No / Pending
- Streamlit approved to run the pilot application?  Yes / No / Pending
- Google sign-in approved for pilot authentication?  Yes / No / Pending
- GitHub repository ownership approved?  Yes / No / Pending
- Privacy or data-protection review required?  Yes / No / Pending
- Internet outage fallback approved?  Yes / No / Pending
- Named authority who may authorize pilot launch: _______________

## 7. Pilot acceptance and stop conditions

The pilot should proceed only when the office agrees how success and failure
will be judged.

- Proposed pilot start and end dates: ___________________________
- Acceptable number of pilot users: _____________________________
- Acceptable wake-up delay after inactivity: ____________________
- Maximum acceptable service interruption: _____________________
- Person receiving problem reports: _____________________________

Stop the pilot and return to the verified local system if:

- access is granted to an unauthorized person;
- a credential or backup is exposed;
- official records differ unexpectedly between systems;
- database connection or storage limits threaten normal operation;
- the approved owner loses control of any service account;
- management withdraws cloud, privacy, or operating approval.

## Approval record

- Decision: Approved for test-data pilot / Changes required / Not approved
- Conditions or restrictions: __________________________________
- Approving official and position: ______________________________
- Signature or approved reference: ______________________________
- Date: _________________________________________________________

Approval of this checklist authorizes only the stated pilot scope. It does not
by itself authorize a public production launch or the transfer of official
operational records.
