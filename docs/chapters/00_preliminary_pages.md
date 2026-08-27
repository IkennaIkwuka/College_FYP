# TITLE PAGE

**DESIGN AND IMPLEMENTATION OF A SECURE UNIVERSITY INFORMATION MANAGEMENT PORTAL WITH ROLE-BASED ACCESS CONTROL USING PYTHON**

BY

**IKENNA NICHOLAS IKWUKA**
**([Matriculation Number])**

A PROJECT PRESENTED TO THE DEPARTMENT OF COMPUTER SCIENCE, FACULTY OF NATURAL AND APPLIED SCIENCES, LEGACY UNIVERSITY OKIJA

IN PARTIAL FULFILMENT OF THE REQUIREMENTS FOR THE AWARD OF BACHELOR OF SCIENCE (B.SC) DEGREE IN COMPUTER SCIENCE

SUPERVISOR
**[Supervisor's Name]**

**[Month, Year]**

# CERTIFICATION

This is to certify that this research work titled **"DESIGN AND IMPLEMENTATION OF A SECURE UNIVERSITY INFORMATION MANAGEMENT PORTAL WITH ROLE-BASED ACCESS CONTROL USING PYTHON"** is an original research work carried out by me, **IKENNA NICHOLAS IKWUKA**, with registration number **[Matriculation Number]**, in partial fulfilment of the requirements for the award of Bachelor of Science degree in Computer Science, Faculty of Natural and Applied Sciences, LEGACY UNIVERSITY OKIJA. The research has not been presented anywhere for the award of any certificate whatsoever.

&nbsp;

&nbsp;

──────────────────────────

**Ikenna Nicholas Ikwuka ([Matriculation Number])**

Date: ──────────────────────────

# APPROVAL

This project written by **IKENNA NICHOLAS IKWUKA** with registration number **[Matriculation Number]** of the Department of Computer Science, Faculty of Natural and Applied Sciences, has been examined and approved in partial fulfilment of the requirements for the award of Bachelor of Science (B.Sc.) degree in Computer Science of LEGACY UNIVERSITY OKIJA.

&nbsp;

&nbsp;

──────────────────────────

**[Supervisor's Name]**
Supervisor

Date: ──────────────────────────

&nbsp;

&nbsp;

──────────────────────────

**[Head of Department's Name]**
Head of Department

Date: ──────────────────────────

&nbsp;

&nbsp;

──────────────────────────

**[External Examiner's Name]**
External Examiner

Date: ──────────────────────────

# DEDICATION

This project is dedicated to God, for grace and strength throughout the course of this programme, and to my family, for their support and patience.

# ACKNOWLEDGEMENTS

I am grateful to my supervisor, **[Supervisor's Name]**, for the guidance, corrections, and patience that shaped this project from its earliest planning stages through to completion.

I also thank the Head of Department, **[Head of Department's Name]**, and the rest of the lecturers in the Department of Computer Science, Legacy University, Okija, for the instruction and support that made this work possible.

My parents and family have my deepest gratitude for their support, encouragement, and patience throughout this programme.

I thank my friends and classmates who offered feedback, tested the system, or otherwise supported this work along the way.

Finally, I thank God for grace and strength throughout the course of this project and this programme.

# ABSTRACT

Legacy University, Okija, currently manages student registration, course administration, and results processing through manual, paper- and spreadsheet-based methods that offer no reliable access control, are slow to operate, and leave no dependable record of who changed what. This project set out to design and implement a secure, web-based University Information Management Portal for Legacy University, built around Role-Based Access Control (RBAC), to replace those manual processes across four modules: authentication and access control, student information, course registration, and results and grading. The system was built with Python and Django, following an object-oriented, iterative and incremental methodology, and models seven user roles, Student, Lecturer, Head of Department, Registrar, Bursar, Dean, and IT Administrator, each scoped to a dashboard and a set of permissions enforced at the application layer through per-role access decorators. Authentication uses a passwordless, PIN-verified first login for students and an emailed setup link for staff, so no account starts life with a shared default password. Results are graded automatically against the National Universities Commission's five-point scale, with GPA and CGPA computed directly from a student's stored results.
