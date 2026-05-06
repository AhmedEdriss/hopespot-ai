# Email Categories

This document defines the categories the email classifier uses, with examples and escalation rules for each.

## Quick Reference

| Category | Auto-draft? | Escalate? |
|---|---|---|
| `services_enquiry` | Yes | No |
| `volunteer_enquiry` | Yes | No |
| `donation_enquiry` | Yes (small amounts) | If large/complex |
| `gift_shop_enquiry` | Yes | If complaint or refund |
| `partnership_enquiry` | Yes (initial reply) | Always for substantive |
| `media_press` | No | Always |
| `funder_communication` | No | Always |
| `complaint_or_concern` | No | Always |
| `urgent_welfare` | No | Always (urgent) |
| `general` | Maybe (RAG fallback) | If unclear |

## Detailed Categories

### services_enquiry

**What it is:** Someone asking about HSO's services — language classes, job training, counseling, when classes meet, how to register, who can attend, what to bring, etc.

**Auto-draft:** Yes. This is the highest-volume category and the bulk of the agent's value.

**Examples:**

- "When do Norwegian classes start? I just arrived in Trondheim."
- "Hei, jeg lurer på om dere har norskkurs for nybegynnere."
- "السلام عليكم، هل يمكنني المشاركة في دروس اللغة النروجية؟"
- "Do I need to register in advance? What level should I start at?"
- "My friend told me you help with finding a job. How does that work?"

**Knowledge base documents to load:** `02_FAQs/services.md`, `01_Programs/[relevant program].md`

**Special handling:**

- If the sender mentions a specific personal situation (legal status, family circumstances), draft a general reply but flag for human review
- If the question is about something HSO doesn't offer, draft a polite redirect with referrals

---

### volunteer_enquiry

**What it is:** Someone interested in volunteering, asking about volunteer opportunities, how to apply, what's involved.

**Auto-draft:** Yes.

**Examples:**

- "Hi, I'd love to volunteer with you. What's the next step?"
- "I'm a Norwegian teacher and want to help with classes. Are you looking for volunteers?"
- "Do you need help with the Iftar event next month?"
- "I have some free time and speak Arabic and English — could I help with translation?"

**Knowledge base documents to load:** `02_FAQs/volunteering.md`, `04_Volunteers/lifecycle-stages.md`, `04_Volunteers/role-descriptions.md`

**Special handling:**

- Always invite them to the next orientation
- If they offer specific skills (legal, medical, professional), note this and flag for human follow-up — these are valuable connections
- If they ask about volunteering with minors or in sensitive areas, escalate

---

### donation_enquiry

**What it is:** Questions about how to donate, donation receipts, recurring gifts, tax deductibility, what donations support.

**Auto-draft:** Yes for routine questions. Escalate for amounts above threshold or complex situations.

**Examples:**

- "How can I donate?"
- "Can I set up a monthly donation?"
- "I'd like to give 200 NOK in honor of a friend."
- "Is my donation tax-deductible in Norway?"

**Knowledge base documents to load:** `02_FAQs/donations.md`

**Always escalate if:**

- The mentioned amount exceeds [TBD: threshold, suggest 5,000 NOK]
- The donor mentions estate planning, bequests, or legacy giving
- The donor wants to restrict the gift to a specific use
- The donor wants to discuss naming, recognition, or sponsorship
- The donor is a corporate or institutional entity

---

### gift_shop_enquiry

**What it is:** Questions about gift shop products, ordering, shipping, availability.

**Auto-draft:** Yes for product questions. Escalate for any complaint, refund request, or order problem.

**Examples:**

- "Do you ship internationally?"
- "Is the embroidered bag still available?"
- "How long does shipping take?"

**Knowledge base documents to load:** `02_FAQs/gift-shop.md`, `05_Gift_Shop/products.md`

**Always escalate if:**

- The customer reports a problem with their order (didn't arrive, damaged, wrong item)
- The customer requests a refund or exchange
- The customer disputes a charge

---

### partnership_enquiry

**What it is:** Other organizations, businesses, or institutions wanting to collaborate, partner, or coordinate with HSO.

**Auto-draft:** Yes for an acknowledgment + escalation notice. Substantive replies always come from leadership.

**Examples:**

- "Our school is interested in connecting with your community for a project."
- "I represent [Norwegian organization] — could we discuss a potential partnership?"
- "Our church wants to help support refugees and we'd like to learn more about HSO."

**Auto-draft pattern:**

```
[Acknowledge their interest warmly]
[Confirm we'll have someone get back to them properly]
[Set expectation: within X business days]
[Sign-off]
```

The substantive partnership conversation always involves a human. The agent's job is to make sure people don't wait wondering if their email was received.

**Knowledge base documents to load:** `02_FAQs/partnerships.md`

---

### media_press

**What it is:** Journalists, bloggers, content creators asking for comment, interviews, or information for stories.

**Auto-draft:** No. Always escalate.

**Examples:**

- "I'm writing for [publication] about refugee integration in Norway. Can I interview someone?"
- "We're producing a documentary about Trondheim's immigrant communities."
- "Do you have a press contact?"

**Action:** Flag immediately. Tag with `media-press`. Notify [TBD: communications lead or executive director] directly.

The agent should not even draft a holding reply for media — bad media-relations defaults can damage HSO's standing. Humans handle this start to finish.

---

### funder_communication

**What it is:** Anything from a funder — government agencies, foundations, EEA grant programs.

**Auto-draft:** No. Always escalate.

**Examples:**

- "Confirmation of your grant application receipt"
- "Reporting deadline reminder for grant #..."
- "We have questions about your application"
- Anything from IMDi, Bufdir, named foundations, etc.

**Action:** Flag immediately. Tag with `funder-communication`. Notify [TBD: development lead or executive director].

The agent should not draft anything funder-facing without human direction.

**Detection signals:**

- Sender domain matches a known funder (maintain a list)
- Subject line contains words like "application," "grant," "reporting," "funding"
- Body references specific grant numbers or programs

---

### complaint_or_concern

**What it is:** Any expression of dissatisfaction, complaint about HSO services or staff, allegation of misconduct, or strongly negative feedback.

**Auto-draft:** No. Always escalate.

**Examples:**

- "I am very disappointed with how I was treated..."
- "I want to report a problem with one of your volunteers..."
- "This is unacceptable..."
- "I've been waiting weeks for a response and..."

**Action:** Flag immediately. Tag with `complaint`. Notify [TBD: executive director].

Even if the complaint is mild, the agent should not draft. Complaints require human judgment, empathy, and often involve information the agent doesn't have access to.

**Detection signals:**

- Negative emotion language ("disappointed," "frustrated," "angry," "unacceptable")
- References to unmet expectations or promises broken
- Mentions of specific staff or volunteer behavior negatively
- Threats to escalate publicly or legally

---

### urgent_welfare

**What it is:** Anything indicating safety concerns, mental health crisis, abuse, exploitation, or immediate danger.

**Auto-draft:** No. Escalate urgently.

**Examples:**

- "I don't know what to do, I am thinking of hurting myself..."
- "My husband won't let me leave the house..."
- "Someone is threatening me..."
- "I have nowhere to sleep tonight and have my children with me..."

**Action:** Flag URGENT. Tag with `urgent-welfare`. Notify [TBD: designated welfare contact] immediately, plus backup, plus the executive director.

This is the highest-priority category. Even outside business hours, someone should see these within an hour ideally.

**Detection signals:**

The classifier should look for:

- Mentions of self-harm, suicide, hurting oneself
- Mentions of being hurt by someone else
- Mentions of being trapped or unable to leave
- Mentions of being threatened
- Mentions of children in danger
- Medical emergency language
- Homelessness or urgent housing crisis
- Domestic violence indicators

The classifier should err strongly on the side of flagging this category. False positives (escalating something that wasn't actually urgent) are far better than false negatives (missing a real welfare situation).

---

### general

**What it is:** Anything that doesn't clearly fit the other categories, or where the classifier returns low confidence.

**Auto-draft:** Maybe — depends on the actual content. The agent does a fallback retrieval (search across all FAQ documents for relevant content) and either drafts a tentative reply or escalates if nothing relevant is found.

**Examples:**

- General questions about HSO
- Questions that span multiple categories
- Unclear queries
- Greetings or expressions of support without specific questions

**Knowledge base documents to load:** Top 3 most relevant FAQ documents based on keyword matching or semantic search

**If no relevant content found:** Escalate to general queue with a note that the classifier couldn't categorize.

## Adding New Categories

If a recurring type of email doesn't fit any existing category, propose a new one:

1. Document at least 5 example emails of this type
2. Define the auto-draft / escalate decision
3. Specify which knowledge base documents should load
4. Add detection signals for the classifier
5. Update the classifier prompt with the new category

New categories should be reviewed by the comms lead before adding to production.
