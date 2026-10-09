"""
DataGhost – classifier training script.
Generates 60 synthetic examples per class (240 total), trains, evaluates, and saves.

Usage:
    python train_classifier.py
"""
import os
import sys
import logging

# Allow running from the backend root directory.
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from classifier.ml_classifier import DataGhostClassifier

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Synthetic training data
# ---------------------------------------------------------------------------

PUBLIC_EXAMPLES = [
    "The college canteen will serve special biryani on Friday. All students are welcome to enjoy the meal at subsidized rates. Timings: 12 PM to 2 PM.",
    "Annual Sports Day is scheduled for 15th March. Events include 100m sprint, long jump, and relay race. Registration forms available at the sports office.",
    "The library will remain closed on 26th January for Republic Day. Students can access e-resources from the college portal during this period.",
    "Class timetable for Semester 4: Monday – Mathematics 9 AM, Physics 11 AM. Tuesday – Chemistry 10 AM, Lab 2 PM. Schedule subject to change.",
    "General meeting of the Student Council will be held on Wednesday at 3 PM in the auditorium. All students are encouraged to attend.",
    "The college bus schedule has been updated. Route 3 now departs at 7:30 AM from Main Gate. Route 5 departs at 8:00 AM from North Campus.",
    "Notice: Submission deadline for project reports is extended to 20th April. Students must submit hard copies to the department office.",
    "Annual cultural fest Euphoria 2024 registration is now open. Participate in dance, music, drama, and art competitions. Prizes worth INR 50,000.",
    "The new batch of books has arrived at the library. Topics include Machine Learning, Data Structures, and Operating Systems. Issue your copy today.",
    "Examination hall tickets for the April 2024 exams are available on the student portal. Download and bring a printout to the exam center.",
    "The college placement cell announces on-campus recruitment by Infosys for BE/BTech students. Eligible branches: CSE, ECE, IT. Register by Friday.",
    "Public notice: Water supply will be interrupted on Sunday from 6 AM to 12 PM for pipeline maintenance. Please store water accordingly.",
    "Scholarship applications for merit-cum-means are open. Eligible students with family income below INR 4 lakh may apply at the finance office.",
    "The computer lab will be open on Saturdays from 9 AM to 5 PM for final year project work. Students must carry their ID cards.",
    "Guest lecture on Artificial Intelligence by Dr. Priya Sharma on 10th March. Venue: Seminar Hall A. Entry free for all students and faculty.",
    "Holiday list 2024: Pongal – 14-15 Jan, Republic Day – 26 Jan, Holi – 25 Mar, Eid – 10 Apr. The college will remain closed on these dates.",
    "Workshop on Python programming for beginners will be held on 5th April. No prior experience required. Register at the CS department.",
    "The college football team won the inter-university tournament. Congratulations to coach Ramesh and all team members for this achievement.",
    "Fee payment portal is open for the next semester. Students must pay tuition fees before 30th March to avoid late payment charges.",
    "Campus recruitment drive by TCS: Eligible for all branches with 60% aggregate. Written test on 12th March, GD and interview on 13th March.",
    "The annual prize distribution ceremony will be held on 25th March at 5 PM. Parents are cordially invited to attend the function.",
    "New additions to the college canteen menu include veg burger, pasta, and fresh juice. Available from Monday onwards at standard prices.",
    "Reminder: Internal examination schedule for February is posted on the notice board. Students must report 30 minutes before the exam time.",
    "The college auditorium is available for booking for student events. Apply at the administrative office two weeks in advance.",
    "A blood donation camp will be organized on 14th March in association with the Red Cross Society. All healthy adults are welcome to participate.",
    "The college magazine 'Horizon' is accepting submissions for the 2024 issue. Send articles, poems, and artwork to the editor by 15th March.",
    "Orientation program for first-year students will be held from 1st to 3rd August. Attendance is compulsory for all new students.",
    "The college is hosting a science exhibition on 20th April. Students from classes 9 and 10 are invited to visit and participate in quizzes.",
    "Notice to all students: Ragging is strictly prohibited on campus. Report any incidents to the anti-ragging committee immediately.",
    "The college swimming pool is open for students on weekdays from 5 AM to 7 AM. Membership cards available at the sports office.",
    "External examination results for November 2023 are now available on the university portal. Students may check their grades online.",
    "Campus cleanliness drive on Saturday: All students and staff are requested to participate and keep our campus green and clean.",
    "The college WiFi has been upgraded to 100 Mbps. Students can connect up to 3 devices using their student ID credentials.",
    "Annual alumni meet is scheduled for 10th February. Alumni are requested to register on the college website by 5th February.",
    "The national seminar on climate change will be held on 8th March. Registration fee: INR 200 for students, INR 500 for faculty.",
    "Library hours extended during examination period: 8 AM to 10 PM on weekdays, 9 AM to 6 PM on weekends.",
    "The college canteen is now accepting digital payments via UPI. Scan the QR code at the counter for a quick and cashless transaction.",
    "Hostel students must submit vacation leave applications before 1st April. Applications received after the deadline will not be accepted.",
    "The college football ground will be closed from 10th to 20th March for renovation. Students may use the alternative ground near Block C.",
    "Notice from the Transport Department: Route 7 bus timing changed from 7:45 AM to 8:00 AM effective from 1st April.",
    "The annual science fair is open for student project submissions. Last date: 15th March. Best projects will represent the college at nationals.",
    "The college health center is now open 24 hours on weekdays. Students experiencing health issues may visit at any time.",
    "Reminder: NPTEL online course enrollment is open. Students can earn extra credit by completing certified courses on the platform.",
    "The college has introduced a new anti-plagiarism policy. All academic submissions will be verified using Turnitin from this semester.",
    "Cultural club members are requested to attend the rehearsal for the Annual Day program this Saturday at 4 PM in the auditorium.",
    "Academic calendar 2024–25 has been published on the college website. Students can view semester dates, holidays, and exam schedules.",
    "The college is conducting a tree plantation drive on World Environment Day. Volunteers may register at the NSS office.",
    "Hostel mess menu for April: Breakfast – idli/dosa, Lunch – rice/chapati with dal and vegetables, Dinner – sambar rice and salad.",
    "Free career counseling sessions are available at the placement cell every Tuesday from 2 PM to 4 PM. Walk-in, no appointment needed.",
    "The robotics club is organizing a workshop on Arduino basics on 5th April. Seats limited to 30. Register on a first-come-first-served basis.",
    "Photography club is accepting new members. All skill levels welcome. First meeting: 10th March at 5 PM, Media Lab, Block D.",
    "Anti-drug awareness campaign on 26th March. Students are encouraged to attend the talk by a guest speaker from the health ministry.",
    "Final year students are requested to submit their no-dues certificates before collecting provisional degree certificates.",
    "The engineering drawing hall has been upgraded with new drawing tables and equipment. Available for student use from next week.",
    "College website is being updated with new content. Suggestions for improvement may be sent to the IT cell by email.",
    "A meditation and yoga session will be held every morning from 6 AM to 7 AM on the college ground. Open to all students and staff.",
    "The college has achieved A++ grade in the latest NAAC accreditation. Congratulations to the entire academic community.",
    "Student feedback forms for the current semester are available on the portal. Please provide your honest feedback by 20th March.",
    "The central library has subscribed to IEEE Xplore and ACM Digital Library. Students can access research papers using their college ID.",
    "A farewell ceremony for the final year batch will be held on 30th April. Juniors are requested to organize the event responsibly.",
]

INTERNAL_EXAMPLES = [
    "TO: All Department Heads. This memo outlines the revised leave policy effective from Q2 2024. Employees are entitled to 12 earned leaves and 6 sick leaves per calendar year.",
    "Internal memo: IT helpdesk hours have been changed to 9 AM to 6 PM. Employees must submit IT support tickets through the new ServiceNow portal.",
    "Meeting minutes – Engineering sync 15/03/2024: Discussed Q2 roadmap. Action items: Ravi to deliver API v2 by April 10, Priya to complete security audit by March 30.",
    "Employee handbook section 4.3 – Performance Review Process: Annual reviews are conducted in December. Mid-year check-ins are mandatory for all employees on PIP.",
    "Internal announcement: The company will switch to a 4-day workweek pilot from April to June 2024. Productivity metrics will be monitored.",
    "HR Update: New health insurance policy effective April 1. Sum insured increased from 3 lakh to 5 lakh. Spouse and children are covered under the family floater plan.",
    "Team meeting notes – Product 20/03/2024: Sprint 14 completed with 85% velocity. Feature X delayed to next sprint. Engineering team to share updated timeline.",
    "Internal IT policy: All employees must enable two-factor authentication on company accounts by March 31. Non-compliance will result in account suspension.",
    "Organizational announcement: The Mumbai and Bangalore offices will be merged under one P&L from April. Regional heads to report directly to VP Operations.",
    "Process document: Expense reimbursement workflow. Submit receipts to finance before 5th of each month. Approval from line manager required for amounts above INR 5,000.",
    "Internal training calendar Q2 2024: Leadership workshop on 5th April, Python for data analysts on 12th April, Cybersecurity awareness on 18th April.",
    "Memo to all staff: Parking space allocation for the new office building will be based on seniority. Two-wheeler spaces available for all; four-wheeler spaces limited.",
    "Internal survey results: Employee satisfaction score improved from 72% to 81% this quarter. Key concerns: workload balance and lack of recognition.",
    "Project update – DataGhost Phase 2: Backend API development is 70% complete. Frontend integration starts next week. Target go-live: 1st May 2024.",
    "HR memo: The company picnic for FY24 is scheduled for 6th April at Funland Resort. Attendance is voluntary; transport will be arranged from the office.",
    "IT security notice: Recent phishing attempts have been reported targeting company email IDs. Do not click unknown links. Report suspicious emails to security@company.com.",
    "Team structure update: The DevOps team is being reorganized into Platform and Site Reliability Engineering sub-teams effective 1st April.",
    "Internal policy: Work from home is permitted up to 3 days per week for employees completing 6 months in the organization. Approval from manager required.",
    "Org chart update: Priya Sharma promoted to Senior Engineering Manager. Rohan Mehta joins as Head of Product. Both report to CTO Arvind Nair.",
    "Q1 2024 business review – Operations: Order fulfillment rate at 94%. Returns reduced by 12%. Warehouse efficiency improved after new WMS deployment.",
    "Internal newsletter March 2024: Employee of the month is Siddharth Rao from Customer Success. New joiners this month: 12 in engineering, 5 in sales.",
    "Finance department update: The company has completed migration to Oracle ERP from SAP. All teams must attend ERP training before April 15.",
    "Internal guidelines for media interaction: Employees must not speak to the press without prior approval from Corporate Communications.",
    "Meeting notes – HR & Finance sync: Budget approval for 2024 hiring plan completed. Headcount additions: 40 in tech, 15 in sales, 10 in support.",
    "Reminder to all managers: Mid-year appraisal forms must be submitted on the HRMS portal by 30th June. Instructions available on the intranet.",
    "Internal knowledge base update: The onboarding wiki for new joinees has been revised. Covers tool access, team introductions, and first-week agenda.",
    "Cross-functional sync notes 22/03/2024: Marketing and Product aligned on Q2 launch messaging. Legal review of new ToS scheduled for next week.",
    "Company travel policy update: All international travel above 7 days requires CFO approval. Book through the designated travel agency for better rates.",
    "Internal communication: The office canteen will be closed for renovation from 15th to 25th April. External catering will be arranged during this period.",
    "Memo – Engineering norms: Code reviews are mandatory for all pull requests. Minimum 2 approvals required before merging to main branch.",
    "Internal HR memo: Maternity leave has been enhanced from 26 weeks to 30 weeks. Paternity leave extended to 15 days. Policy effective immediately.",
    "IT helpdesk update: Company laptops will be refreshed for employees completing 3 years. Submit your current asset details to IT by 1st April.",
    "Process note – Finance: Vendor invoices must be submitted by the 25th of each month. Late invoices will be processed in the next payment cycle.",
    "Project Phoenix internal kickoff notes: Team leads introduced. Project charter signed off. Risk register and RACI matrix to be shared by Friday.",
    "Internal security policy: Employees must not use personal USB drives on company computers. All data transfers must happen via approved cloud storage.",
    "Company values refresher: Our core values are Integrity, Innovation, Inclusion, and Impact. All decisions must be guided by these principles.",
    "Weekly status update – Infrastructure: Cloud cost optimization saved 18% in March. Database migration to managed RDS completed successfully.",
    "Internal update: Company anniversary celebration on 15th May. Budget approved for team outing and awards ceremony. Details to follow.",
    "HR notice: The Employee Assistance Program (EAP) provides free counseling services. Contact the EAP helpline for mental health support.",
    "Internal meeting: Quarterly business review for Q1 2024 scheduled on 10th April. All department heads to present 15-minute updates.",
    "IT policy reminder: VPN must be used for all remote access to company resources. VPN credentials are personal and must not be shared.",
    "Internal document: Vendor evaluation matrix for the new CRM system. Shortlisted vendors: Salesforce, HubSpot, and Zoho. Final decision by April 20.",
    "Process update – Support: All customer complaints above severity 2 must be escalated to the engineering team within 4 hours of receipt.",
    "Internal memo: Annual town hall meeting on 5th May. CEO will share company vision for FY25. Lunch will be provided after the session.",
    "HR update: Flexi-benefit plan options for FY25 are now live on the HRMS portal. Select your preferences before 15th April.",
    "Engineering review notes: Technical debt items prioritized for Q2. Legacy API deprecation and database indexing improvements on the backlog.",
    "Internal procurement note: All software purchases above INR 50,000 require IT and Finance approval. Use the procurement portal for requests.",
    "Team sync – Data Engineering 18/03/2024: Data lake migration to S3 is 60% done. Spark job optimization reduced processing time by 30%.",
    "Internal memo from Legal: All contracts above INR 10 lakh must be reviewed by the legal team before signing. Use DocuSign for digital execution.",
    "Company diversity report Q1 2024 (internal): Women make up 34% of the workforce, up from 28% last year. D&I initiatives on track.",
    "IT security bulletin: A critical vulnerability in OpenSSL has been patched. All servers updated. No action required from employees.",
    "Internal training: Mandatory POSH (Prevention of Sexual Harassment) e-learning module must be completed by all employees before 31st March.",
    "Process note: All employee expense claims require original receipts and manager approval. Claims submitted without receipts will be rejected.",
    "Internal Q2 2024 hiring plan: 40 software engineers, 8 data scientists, 5 product managers, 10 QA engineers. JDs published on the intranet.",
    "Memo from Finance: GST filing for Q4 FY24 is due on 18th April. All input tax credit reconciliations must be submitted to accounts by 10th April.",
    "Internal policy: Social media usage guidelines for employees. Do not share confidential product information or internal announcements on public platforms.",
    "Update from Administration: New security access cards to be issued from 1st April. Old cards will be deactivated after 30 days.",
    "Sprint retrospective notes – Team Delta: What went well: improved code coverage to 85%. What to improve: reduce context switching and meeting load.",
    "Internal announcement: Diwali bonus equivalent to one month's CTC will be credited on 1st November. Tax deductions apply as per IT slab.",
    "Company-wide meeting recap 25/03/2024: Q4 revenue targets met. New partnership with ABC Corp announced. Product roadmap for FY25 shared.",
]

CONFIDENTIAL_EXAMPLES = [
    "Customer database export – Q1 2024. Name: Rahul Sharma, Email: rahul.sharma@gmail.com, Phone: 9876543210, PAN: ABCRS1234K, Account: 12345678901, Balance: 45000.",
    "Employee payroll report March 2024. Emp ID: E001, Name: Priya Nair, Designation: Senior Engineer, CTC: 18,00,000, Bank Account: 50100023456789, IFSC: HDFC0001234.",
    "Patient record – ID: P-20240315. Name: Arun Kumar, DOB: 12/05/1985, Aadhaar: 3456 7890 1234, Diagnosis: Type 2 Diabetes, Medication: Metformin 500mg, Doctor: Dr. Meena Rao.",
    "Sales pipeline report – Confidential. Client: XYZ Corp, Deal Value: INR 85 lakhs, Stage: Negotiation, Contact: Vikram Singh, vikram@xyzcorp.com, 9812345678.",
    "Financial audit report FY 2023-24 – Restricted distribution. Total revenue: 48.6 crore, Net profit: 6.2 crore, EBITDA margin: 18.4%. Board members only.",
    "Contract – This agreement is between Acme Technologies and Global Solutions. Confidential and proprietary. Total contract value: USD 2,50,000. Signed 15th March 2024.",
    "HR confidential: Performance improvement plan for employee Rohan Mehta (ID E0234). Issues: chronic lateness, missed deliverables. Review in 60 days.",
    "Customer credit card data (DO NOT DISTRIBUTE): Name: Sita Devi, Card: 4532015112830366, Expiry: 09/26, CVV: 782, Billing address: 45 MG Road, Bangalore.",
    "Internal research report – CONFIDENTIAL. Market share analysis for Q3 2024. Our share: 23.4%. Competitor A: 31.2%. Competitor B: 18.7%. Source: Third-party survey.",
    "Employee records – Confidential. Name: Deepika Reddy, DOB: 22/07/1990, Aadhaar: 9876 1234 5670, PAN: DEFGR5678P, Salary: 14,50,000 per annum.",
    "Legal notice – Strictly confidential. This document contains privileged attorney-client communication. Case: Acme v/s Beta Systems. Hearing date: 10th May 2024.",
    "Medical billing report – CONFIDENTIAL. Patient: Mohammed Irfan, UHID: MH2024567, Insurance ID: 45678901, Claim amount: INR 1,23,500. Diagnosis: Appendectomy.",
    "Customer KYC file. Name: Sunita Kapoor, Address: 12 Park Street Delhi, DOB: 18/09/1975, Aadhaar: 2345 6789 0123, PAN: ABCSK9012L, Photo ID: Attached.",
    "Annual compensation review – CONFIDENTIAL. VP Engineering: 35 LPA, Sr Manager: 22 LPA, Team Lead: 18 LPA, Senior Engineer: 14 LPA, Engineer: 9 LPA.",
    "Business acquisition proposal – CONFIDENTIAL. Target company: Zeta Analytics. Proposed acquisition price: INR 120 crore. Due diligence report attached.",
    "Strategic plan FY2025 – INTERNAL CONFIDENTIAL. Target markets: Tier 2 cities. New product launches: 3. Headcount growth: 25%. Budget: 80 crore.",
    "Customer churn analysis – do not distribute. 342 customers churned in Q1. Top reasons: pricing (45%), product gaps (30%), support issues (25%).",
    "Employee termination document – CONFIDENTIAL. Employee: Karan Bajaj, ID: E0456, Last working day: 31st March 2024. Settlement amount: INR 2,34,000.",
    "Board meeting minutes – Strictly confidential. Date: 20th March 2024. Discussed quarterly financials, MD&A, and approval of ESOP pool expansion to 12%.",
    "Product pricing strategy – CONFIDENTIAL. New SaaS pricing: Starter INR 999/month, Professional INR 2999/month, Enterprise: custom. Effective 1st May 2024.",
    "Customer complaint log – Confidential. Customer: Mohan Das, ID: CUS-3421, Issue: Unauthorized transaction INR 8,500 on 10th March. Status: Under investigation.",
    "Healthcare record: Name: Preethi S, Age: 34, HIV Status: Positive, Treatment: ART, Last viral load: undetectable. Refer to infectious disease specialist.",
    "Internal fraud investigation report – CONFIDENTIAL. Employee under investigation: Finance Dept staff. Suspected embezzlement: INR 3.6 lakhs. HR and Legal informed.",
    "Investor presentation – CONFIDENTIAL. Pre-money valuation: USD 25 million. Series A target: USD 8 million. Cap table: Founders 62%, Angels 18%, ESOP 12%.",
    "M&A due diligence document – DO NOT DISTRIBUTE. Target: BetaCloud Pvt Ltd. Revenue: 12 crore, EBITDA: 1.8 crore, Employees: 87. Deal structure: all-cash.",
    "Customer database – CONFIDENTIAL. Customer ID: CUS-0789, Name: Fatima Malik, Email: fatima.m@outlook.com, Phone: 9023456789, Subscription: Premium, Since: Jan 2022.",
    "Employee stock option grant – CONFIDENTIAL. Grantee: Arun Venkatesan, Options: 10,000, Strike price: INR 220, Vesting: 4-year cliff. Board approved 15th March.",
    "Confidential business report: This document contains proprietary financial forecasts for FY2025. Not for external distribution. Revenue target: 60 crore.",
    "Personnel file – CONFIDENTIAL. Name: Sneha Pillai, ID: E0789, DoB: 05/12/1988, Qualification: MBA Finance, Salary: 21 LPA, Manager: Vikram Nair.",
    "Insurance claim record – CONFIDENTIAL. Claimant: Rajesh Gupta, Policy: 1234567890, Claim: INR 2,10,000, Diagnosis: Coronary artery disease, Approved: Yes.",
    "Customer feedback – RESTRICTED. Survey reveals 34% dissatisfaction with billing. Verbatim comment: 'Double charged for March – no response from support.'",
    "Vendor contract – CONFIDENTIAL. Supplier: Global Logistics, Contract value: INR 45 lakh/year, SLA: 98% on-time delivery, Penalty clause: 5% for breach.",
    "M&A strategy note – DO NOT DISTRIBUTE. Board has approved exploring acquisition of three startups in AI space. Budget: USD 30 million. Advisors: KPMG.",
    "Employee disciplinary record – CONFIDENTIAL. Employee: Ritu Sharma, Incident: Physical altercation with colleague on 10th March. Outcome: Final written warning.",
    "Company bank account statement – CONFIDENTIAL. Account: 00112345678901, IFSC: ICIC0001234, Closing balance: INR 2.34 crore, Period: 1–31 March 2024.",
    "Whistleblower report – STRICTLY CONFIDENTIAL. Complainant: Anonymous. Allegation: Finance manager manipulating vendor invoices. Under investigation by audit committee.",
    "Customer PII export – CONFIDENTIAL. Total records: 1,842. Contains: Full name, email, phone, Aadhaar, PAN, bank account, salary information.",
    "Trade secret document: Our proprietary algorithm for fraud detection has an F1 score of 0.97. This document describes implementation details. Confidential.",
    "Partnership agreement – CONFIDENTIAL. Between Acme Inc and Zeta Corp. Revenue share: 60-40. Non-compete clause: 3 years. Effective date: 1st April 2024.",
    "HR exit interview summary – CONFIDENTIAL. 34% of departing employees cited management style as primary reason. Data to be reviewed by CHRO only.",
    "Financial forecast FY2025 – CONFIDENTIAL. Q1 target: 14 crore. Expected YoY growth: 32%. Risk factors: macroeconomic headwinds and competitor pricing.",
    "Customer credit assessment – CONFIDENTIAL. Customer: Dinesh Patel, Credit score: 724, Income: INR 8 LPA, Loan requested: INR 15 lakh, Status: Approved.",
    "Strategic supplier list – CONFIDENTIAL. Includes pricing, SLAs, and contact details for all tier-1 vendors. Do not share outside procurement team.",
    "Employee drug test results – CONFIDENTIAL. Batch test results from pre-employment screening. 3 of 45 candidates tested positive. Names attached.",
    "Internal financial statement – CONFIDENTIAL. Unaudited P&L for Q1 FY25. Revenue: 16.2 crore, Expenses: 13.8 crore, PAT: 1.7 crore. Subject to audit.",
    "Board resolution – CONFIDENTIAL. Resolved: To authorize MD to sign loan agreement with HDFC Bank for working capital of INR 5 crore at 8.75% p.a.",
    "Client proposal – CONFIDENTIAL. Prepared for: XYZ Bank. Scope: Digital transformation consulting. Total fee: USD 1.2 million over 18 months.",
    "Payroll master file – CONFIDENTIAL. 245 employees. Average CTC: 12.4 LPA. Highest: 52 LPA (CTO). Lowest: 3.6 LPA (intern). Bonus pool: 1.8 crore.",
    "Security incident report – CONFIDENTIAL. Data breach detected on 15th March. 3,200 customer records may have been exposed. Investigation ongoing.",
    "Customer data file – CONFIDENTIAL. Fields: Name, Email (e.g. user@domain.com), Mobile (e.g. 9876543210), PAN (e.g. ABCDE1234F), Account balance.",
    "Termination agreement – CONFIDENTIAL. Parties: XYZ Technologies and employee Mr. Arun Nair. Severance: 3 months' salary. NDA binds for 2 years post-exit.",
    "Research data – CONFIDENTIAL. Clinical trial phase 2 results for drug XR-2024. Efficacy: 78%. Side effects: mild nausea 12%, headache 8%. Patent pending.",
    "Acquisition term sheet – CONFIDENTIAL. Target: Alpha AI Pvt Ltd. Indicative valuation: INR 80 crore. Structure: 70% cash, 30% equity swap.",
    "Employee background check – CONFIDENTIAL. Candidate: Vinod Kumar Sharma. Criminal record: None. Credit check: Good. Previous employment: Verified.",
    "Customer risk profile – CONFIDENTIAL. Customer: ABC Exports, Risk rating: Medium-High. Outstanding loan: INR 3.2 crore. Collateral: Property at MG Road.",
    "Marketing strategy – CONFIDENTIAL. Q2 2024 campaign budget: INR 2.4 crore. Target segment: urban millennials. Key message: speed and reliability.",
    "Internal audit report – CONFIDENTIAL. Findings: 3 high-risk, 7 medium-risk, 12 low-risk observations. Report to be shared only with CFO and Board.",
    "Litigation summary – CONFIDENTIAL. Active cases: 4. Largest exposure: INR 2.1 crore (labor dispute). Provision made in books. Counsel: AZB Partners.",
    "Personal data export – CONFIDENTIAL. Includes sensitive personal information as per PDPA. Data subjects have not consented to external sharing.",
    "Compensation benchmarking report – CONFIDENTIAL. Our P50 is 8% below market. Recommendation: 10-12% merit increase for senior engineers in Q2.",
]

RESTRICTED_EXAMPLES = [
    "DB_HOST=prod-db.internal.acme.com\nDB_PORT=5432\nDB_NAME=customers_prod\nDB_USER=dbadmin\nDB_PASSWORD=Pr0d@Secure#2024\nSECRET_KEY=b3BlbnNzaC1rZXkAAAABjHJpZ2h0\nJWT_SECRET=xK9mP2qR7vL4nW8tA1sF6dE3gB0cI5",
    "AWS credentials file:\nAWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\nAWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY\nREGION=ap-south-1\nS3_BUCKET=acme-prod-backups",
    "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0Z3VS5JJcds3xHn/ygWep4pBCFSMlqI4oWAKXKGe/+xmSMGT\na52TlXFSBkFVpO1EXAMPLE==\n-----END RSA PRIVATE KEY-----",
    "config.py production secrets:\nSECRET_KEY = 'django-insecure-9f#abc123xyz'\nDATABASE_URL = 'postgresql://admin:P@ssw0rd123@db.prod.internal:5432/maindb'\nREDIS_URL = 'redis://:redis_secret@cache.prod:6379/0'",
    "API keys for production services:\nstripe_api_key = 'sk_test_DUMMY_STRIPE_KEY_SAMPLE_12345678'\ntwilio_auth_token = 'your_twilio_auth_token_here_32chars'\nopenai_api_key = 'sk-proj-abcdefghijklmnopqrstuvwxyz123456'",
    "Google Cloud service account key:\n{\n  \"type\": \"service_account\",\n  \"project_id\": \"acme-prod\",\n  \"private_key_id\": \"abc123\",\n  \"client_email\": \"admin@acme-prod.iam.gserviceaccount.com\",\n  \"private_key\": \"-----BEGIN PRIVATE KEY-----\\nXXXXXXXXXX\\n-----END PRIVATE KEY-----\"\n}",
    "JWT token from auth service: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyMTIzIiwicm9sZSI6ImFkbWluIiwiZXhwIjoxNzEyMDAwMDAwfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
    "SSH private key for prod server:\n-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXkAAAABAAAAMAAAAAsAAAAQAAAAYQBCDEFGHIJKLMNOPQRSTUVWXYZ\n-----END OPENSSH PRIVATE KEY-----\nHost: prod-bastion.acme.com, User: deploy",
    "Vault secrets:\nvault kv put secret/app db_password='V@ult$ecret99'\nvault kv put secret/app api_key='zABCDEF1234567890abcdefghijklmnop'\nvault kv put secret/app jwt_secret='$uP3rS3cr3t#JWT'",
    "Environment variables for CI/CD pipeline:\nDOCKER_REGISTRY_PASSWORD=d0cker_Reg1stry_P@ss\nGITHUB_TOKEN=ghp_abcdefghijklmnop1234567890ABCDEF\nNPM_TOKEN=npm_abcdefghijklmnopqrstuvwxyz123456\nSLACK_WEBHOOK=https://hooks.slack.com/services/DUMMY/DUMMY/DUMMY_SAMPLE_KEY",
    "Production database backup credentials:\nHOST=10.0.0.45\nPORT=3306\nUSERNAME=root\nPASSWORD=MySQL@Root#2024\nBACKUP_ENCRYPTION_KEY=AES256_backup_key_here_32_chars_x\nS3_BUCKET=db-backups-prod",
    "Kubernetes secret manifest:\napiVersion: v1\nkind: Secret\nmetadata:\n  name: app-secrets\ndata:\n  DB_PASSWORD: cHJvZHVjdGlvblBhc3M=\n  API_KEY: c2VjcmV0QXBpS2V5MTIz\n  JWT_SECRET: and1dFNlY3JldEtleUhlcmU=",
    "Firebase config with API key:\nconst firebaseConfig = {\n  apiKey: 'AIzaSyBxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',\n  authDomain: 'acme-prod.firebaseapp.com',\n  projectId: 'acme-prod',\n  storageBucket: 'acme-prod.appspot.com'\n}",
    "Twilio credentials:\nACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\nAUTH_TOKEN=your_auth_token_32_chars_here_0000\nFROM_NUMBER=+14155238886\nSMTP_PASSWORD=Sm1@tp_P@ssword_Here",
    ".htpasswd file contents:\nadmin:$apr1$xyz$ABC123DEFGHIJKLMNOPQRSTuvwxyz\ndbuser:$apr1$abc$XYZ789abcdefghijklmnopqrstuv\nbackup:$apr1$def$123abcXYZdefghijklmnopqrstu",
    "Production secrets exported from HashiCorp Vault:\npath: secret/data/prod\nvalues:\n  database_url: postgresql://prod_user:Pr0d_P@ss@db.internal/appdb\n  encryption_key: 32-char-encryption-key-here-abcd\n  oauth_secret: oauth_client_secret_here_64chars",
    "Okta API token:\nAPI_TOKEN=00ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwx\nORG_URL=https://dev-12345.okta.com\nCLIENT_ID=0oa1b2c3d4e5f6g7h8i9\nCLIENT_SECRET=ABCDEFGHIJKLMNOPQRSTUVWXYZ012345",
    "Email server credentials:\nSMTP_HOST=smtp.gmail.com\nSMTP_PORT=587\nSMTP_USERNAME=admin@acme.com\nSMTP_PASSWORD=GmailApp@cc3ss#2024\nSES_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE\nSES_SECRET=wJalrXUtnFEMI/K7MDENG/bP",
    "Azure service principal credentials:\nAZURE_CLIENT_ID=12345678-1234-1234-1234-123456789abc\nAZURE_CLIENT_SECRET=XYZ~8Q~abcdefghijklmnopQRSTUVWXYZ\nAZURE_TENANT_ID=87654321-4321-4321-4321-cba987654321\nAZURE_SUBSCRIPTION_ID=11111111-2222-3333-4444-555555555555",
    "Credentials for internal tools:\nJira token: JIRA_API_TOKEN=ABCDEFGHijklmnopqrstuvwxyz0123456789ABCD\nConfluence: CONFLUENCE_PASSWORD=C0nflu3nc3_S3cr3t\nGrafana: GRAFANA_API_KEY=eyJrIjoiabcdefghijklmnopqrstuvwxyz",
    "PayPal API credentials for payment processing:\nCLIENT_ID=AaBbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrSsTtUuVvWwXxYyZz\nCLIENT_SECRET=EFGHIJKLMNabcdefghijklmnopqrstuvwxyz0123456789ABCD\nMODE=live\nWEBHOOK_ID=PROD-WEBHOOK-12345-67890",
    "SSL certificate and private key:\n-----BEGIN EC PRIVATE KEY-----\nMHQCAQEEIBkg4NQHQ1nQmEXAMPLE1234567890abcdefghijklmnopqrstuvwxyz\n-----END EC PRIVATE KEY-----\nCERT_PASSWORD=Ssl@Cert#2024\nDOMAIN=api.acme.com",
    "Docker registry credentials:\nDOCKER_USERNAME=acmeadmin\nDOCKER_PASSWORD=D0ck3r@Registry#2024\nDOCKER_REGISTRY=registry.acme.internal\nDOCKER_HUB_TOKEN=dckr_pat_ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "GCP credentials JSON:\n{\n  \"private_key\": \"-----BEGIN PRIVATE KEY-----\\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASC\\n-----END PRIVATE KEY-----\",\n  \"client_email\": \"sa-prod@project.iam.gserviceaccount.com\",\n  \"token_uri\": \"https://oauth2.googleapis.com/token\"\n}",
    "Datadog API keys:\nDD_API_KEY=abcdef1234567890abcdef1234567890\nDD_APP_KEY=abcdefghijklmnopqrstuvwxyz0123456789abcd\nDD_SITE=datadoghq.com\nDD_ENV=production",
    "Redis cache with auth:\nREDIS_HOST=redis.internal.acme.com\nREDIS_PORT=6379\nREDIS_PASSWORD=R3d1s@Cache#P@ss\nREDIS_TLS=true\nREDIS_DB=0",
    "GitHub Actions secrets example:\nGH_TOKEN=ghp_1234567890abcdefghijklmnopqrstuvwxyz\nDEPLOY_SSH_KEY=-----BEGIN RSA PRIVATE KEY-----\\nMIIEpAIBAAKCAQEA0Z3VS\\n-----END RSA PRIVATE KEY-----\nHERETOKU_API_KEY=HEROKU_KEY_HERE_32_chars_xxxx",
    "Production application .env file:\nNODE_ENV=production\nPORT=3000\nJWT_SECRET=jwt_very_secret_key_at_least_32_chars_abcde\nDB_URL=mongodb://admin:M0ng0@DB#2024@mongo.prod:27017/app\nSESSION_SECRET=s3ss10n_s3cr3t_k3y_32chars_abcde",
    "Backup encryption keys:\nBACKUP_AES_KEY=aes256_key_32_bytes_here_abcdefgh\nBACKUP_IV=16_byte_iv_abcdef\nBACKUP_PASSPHRASE=BackupP@ssphr@se#2024\nGPG_KEY_ID=ABCDEF1234567890\nGPG_PASSPHRASE=GpgP@ssphrase#Production",
    "Internal admin credentials:\nadmin_username: sysadmin\nadmin_password: Adm1n@Sys#2024\ndatabase_root_password: DB_R00t#P@ss\napi_master_key: MASTER_KEY_abcdefghijklmnopqrstuvwxyz0123\nencryption_passphrase: EncryptAll#2024",
    "Webhook secrets for integrations:\nGITHUB_WEBHOOK_SECRET=github_webhook_s3cr3t_32chars_abcd\nSTRIPE_WEBHOOK_SECRET=whsec_abcdefghijklmnopqrstuvwxyz01234567\nSLACK_SIGNING_SECRET=slack_signing_secret_32chars_abcde\nJIRA_WEBHOOK_TOKEN=jira_token_abcdefghijklmnopqrstuvwx",
    "Secrets management: These are the production service account credentials for Kubernetes cluster. kubectl config set-credentials admin --token=BEARER_TOKEN_abcdefghijklmnop. API server: https://k8s.prod.internal:6443.",
    "Environment file for data pipeline:\nSF_ACCOUNT=acme.snowflakecomputing.com\nSF_USER=etl_admin\nSF_PASSWORD=Sn0wfl@ke#ETL2024\nSF_WAREHOUSE=COMPUTE_WH\nSF_PRIVATE_KEY_PATH=/keys/snowflake_rsa_key.p8\nSF_PRIVATE_KEY_PASSPHRASE=key_pass_here",
    "Terraform state backend config:\nterraform {\n  backend \"s3\" {\n    bucket = \"acme-tf-state\"\n    key = \"prod/terraform.tfstate\"\n    access_key = \"AKIAIOSFODNN7EXAMPLE\"\n    secret_key = \"wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY\"\n    region = \"ap-south-1\"\n  }\n}",
    "Ansible vault encrypted file (decrypted view):\ndb_password: V@ult_DB_P@ss#2024\napi_secret: ansible_api_secret_here_abcdef1234\nldap_bind_password: LDAP_B1nd_P@ssw0rd\njenkins_admin_password: Jenkins@Admin#2024",
    "Prod secrets for mobile app:\nFCM_SERVER_KEY=AAAAxxxxxxxx:APA91bHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\nAPNS_KEY_ID=ABCDE12345\nAPNS_TEAM_ID=FGHIJ67890\nAPNS_PRIVATE_KEY=-----BEGIN EC PRIVATE KEY-----\\nYYYYY\\n-----END EC PRIVATE KEY-----",
    "Certificate pinning keys:\nCERT_SHA256=sha256//ABCDEFGHIJKLMNOPQRSTUVWXYZ01234567890abcdefghijklm=\nPINNED_KEY=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA\nPINNING_SECRET=pinning_secret_key_32chars_abcde",
    "MongoDB Atlas connection string:\nMONGODB_URI=mongodb+srv://admin:MongoAtlas@P@ss@cluster0.abcde.mongodb.net/proddb?retryWrites=true\nMONGODB_DB_NAME=proddb\nMONGODB_COLLECTION=users",
    "Secrets exposed in git commit:\n+PASSWORD=hunter2_changed_now_P@ss\n+API_KEY=AKIAIOSFODNN7EXAMPLE_leaked_key\n+DATABASE_URL=postgres://admin:badpassword@prod-db:5432/users\n+SECRET_TOKEN=leaked_secret_token_abcdefghijk",
    "Admin portal credentials:\nURL: https://admin.acme.com\nUsername: superadmin\nPassword: Sup3r@Adm1n#2024\nMFA backup codes: 12345678, 87654321, 11223344\nSession token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhZG1pbiI6dHJ1ZX0.signature",
    "Cloudflare API credentials:\nCF_API_TOKEN=abcdefghijklmnopqrstuvwxyz0123456789ABCD\nCF_ACCOUNT_ID=1234567890abcdef1234567890abcdef\nCF_ZONE_ID=abcdef1234567890abcdef1234567890\nCF_EMAIL=admin@acme.com",
    "CI/CD environment secrets:\nCI_DEPLOY_TOKEN=deploy_token_abcdefghijklmnopqrstuvwxyz\nCI_REGISTRY_PASSWORD=reg1stry_p@ss#CI\nCI_SSH_PRIVATE_KEY=-----BEGIN RSA PRIVATE KEY-----\\nMIIEpAIB\\n-----END RSA PRIVATE KEY-----",
    "Elasticsearch cluster credentials:\nES_URL=https://elastic.prod.internal:9200\nES_USERNAME=elastic\nES_PASSWORD=El@stic#Cluster$2024\nES_API_KEY=base64encoded_api_key_here_abcdefghijklm\nES_CA_CERT=/etc/ssl/elastic-ca.pem",
    "Sentry DSN and auth:\nSENTRY_DSN=https://abcdef1234567890@o123456.ingest.sentry.io/1234567\nSENTRY_AUTH_TOKEN=sntrys_eyJpYXQiOjE3ABCDEFGHIJKLMNOP\nSENTRY_ORG=acme-org\nSENTRY_PROJECT=backend",
    "PEM certificate content:\n-----BEGIN CERTIFICATE-----\nMIIFazCCA1OgAwIBAgIRAIIQz7DSQONZRGPgu2OCiwAwDQYJKoZIhvcNAQELBQAw\n-----END CERTIFICATE-----\nPRIVATE_KEY_PASS=C3rt#P@ssphrase2024",
    "Database credentials file for multiple environments:\ndev.db.password=Dev@DB#Pass\nstaging.db.password=St@ging@DB#2024\nprod.db.password=Pr0d@DB#2024!!\nprod.db.host=10.0.10.45\nprod.db.user=prod_app_user",
    "RDS instance master credentials:\nDB_INSTANCE=acme-prod-rds.xxxxx.ap-south-1.rds.amazonaws.com\nDB_MASTER_USERNAME=masteruser\nDB_MASTER_PASSWORD=RDS@Master#P@ss2024\nDB_PORT=5432\nDB_SSL_MODE=require",
    "OAuth2 client secrets:\nGOOGLE_CLIENT_ID=123456789012-abcdefghijklmnop.apps.googleusercontent.com\nGOOGLE_CLIENT_SECRET=GOCSPX-abcdefghijklmnopqrstuv\nFACEBOOK_APP_SECRET=abcdef1234567890abcdef1234567890\nGITHUB_CLIENT_SECRET=ghp_secret_abcdefghijklmnopqrstuvwxyz",
    "Secrets in terraform.tfvars:\ndb_password = \"Terraform@DB#2024\"\nadmin_api_key = \"api_key_32_chars_here_abcdefghij\"\nvpc_cidr = \"10.0.0.0/16\"\nmaster_key_arn = \"arn:aws:kms:ap-south-1:123456789012:key/abcd-1234\"",
    "Vault AppRole credentials:\nROLE_ID=12345678-1234-1234-1234-123456789012\nSECRET_ID=87654321-4321-4321-4321-cba987654321\nVAULT_ADDR=https://vault.prod.internal:8200\nVAULT_TOKEN=hvs.AAAAAQabcdefghijklmnopqrstuvwxyz",
    "Stripe live keys and webhook:\nSTRIPE_PUBLISHABLE_KEY=pk_test_SAMPLE_KEY_00000000000000000000\nSTRIPE_SECRET_KEY=sk_test_SAMPLE_KEY_00000000000000000000\nSTRIPE_WEBHOOK_SECRET=whsec_SAMPLE_KEY_0000000000000000000\nSTRIPE_ACCOUNT_ID=acct_1234567890abcdef",
    "Production deployment credentials:\nansible_user=deploy\nansible_ssh_private_key_file=/home/deploy/.ssh/id_rsa\nansible_become_password=Sudo@Prod#2024\nssh_extra_args=-o StrictHostKeyChecking=no\ndeploy_api_token=deploy_token_abcdefghijklmnop",
    "Machine learning model serving secrets:\nMODEL_SIGNING_KEY=ml_model_signing_key_32chars_abcde\nINFERENCE_API_KEY=inference_key_abcdefghijklmnopqrstuvwxyz\nFEATURE_STORE_PASSWORD=F3ature@St0re#2024\nMLFLOW_TRACKING_URI=https://mlflow.prod.internal\nMLFLOW_TOKEN=mlflow_token_abcdefghijklmno",
    "AWS IAM role credentials (temporary):\nAWS_ACCESS_KEY_ID=ASIAIOSFODNN7EXAMPLE\nAWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY\nAWS_SESSION_TOKEN=IQoJb3JpZ2luX2VjEJr//////////wEaCXVzLWVhc3QtMSJGMEQCIH\nAWS_REGION=ap-south-1",
]


def build_training_data():
    """Return (texts, labels) lists for all 240 examples."""
    texts = (
        PUBLIC_EXAMPLES +
        INTERNAL_EXAMPLES +
        CONFIDENTIAL_EXAMPLES +
        RESTRICTED_EXAMPLES
    )
    labels = (
        ["PUBLIC"] * len(PUBLIC_EXAMPLES) +
        ["INTERNAL"] * len(INTERNAL_EXAMPLES) +
        ["CONFIDENTIAL"] * len(CONFIDENTIAL_EXAMPLES) +
        ["RESTRICTED"] * len(RESTRICTED_EXAMPLES)
    )
    return texts, labels


def train_and_save(model_dir: str = None):
    """
    Train the TF-IDF + LinearSVC classifier and save it to model_dir.

    Workflow
    --------
    1. Build 240 synthetic examples (60 per class).
    2. Stratified 80/20 train/test split (random_state=42).
    3. Fit TF-IDF + LinearSVC pipeline on the training split.
    4. Evaluate on the held-out test split.
    5. Save the pipeline artifact.

    Returns
    -------
    Fitted DataGhostClassifier instance.
    """
    if model_dir is None:
        model_dir = os.path.join(_HERE, "model")

    texts, labels = build_training_data()

    total = len(texts)
    class_dist = {}
    for lbl in labels:
        class_dist[lbl] = class_dist.get(lbl, 0) + 1

    logger.info("Dataset: %d total samples", total)
    for cls, cnt in sorted(class_dist.items()):
        logger.info("  %-15s %d", cls, cnt)

    # Stratified train / test split — reproducible with fixed random_state.
    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )
    logger.info("Train split: %d  |  Test split: %d", len(X_train), len(X_test))

    clf = DataGhostClassifier(model_dir=model_dir)

    # clf.train() internally re-splits for calibration — pass full training set.
    logger.info("Fitting TF-IDF + LinearSVC …")
    clf.train(X_train, y_train)

    estimator_name = type(clf.pipeline.named_steps["clf"]).__name__
    logger.info("Estimator: %s", estimator_name)

    # ---------- Evaluation ----------
    predictions = [clf.predict(t)["label"] for t in X_test]
    acc = accuracy_score(y_test, predictions)

    report_str = classification_report(
        y_test,
        predictions,
        target_names=DataGhostClassifier.LABELS,
        digits=4,
    )

    logger.info("Test accuracy: %.4f", acc)
    print("\n" + "=" * 60)
    print(f"  Estimator     : {estimator_name}")
    print(f"  Dataset size  : {total}")
    print(f"  Class dist.   : {class_dist}")
    print(f"  Train / Test  : {len(X_train)} / {len(X_test)}")
    print(f"  Test accuracy : {acc:.4f}")
    print("=" * 60)
    print(report_str)

    clf.save()
    logger.info("Model artifact saved to %s", model_dir)
    return clf


if __name__ == "__main__":
    train_and_save()
