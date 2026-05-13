# Part 3 — Thinking Question

## Question A — The Immediate Response
**The AI Reply:** "Hi [Guest Name], I am so sorry about the lack of hot water, especially with your breakfast guests arriving so soon. I have escalated this immediately to our night-duty emergency team. Someone will be in touch shortly to assist you and discuss your refund request. Thank you for your patience."
**Why I chose this wording:** It acknowledges the severity, uses empathy, and avoids making a binding financial promise regarding the refund. Internally, because the context states the standard caretaker is only available 8am-10pm, the AI must explicitly set the expectation that a specialized 'night team' will be reaching out, rather than the standard caretaker.

## Question B — The System Design
**Beyond the Message:**
1. **Trigger & Classification:** The payload identifies `query_type: complaint` and high semantic urgency. It forces an `escalate` action, immediately bypassing the auto-send queue.
2. **Intelligent Routing:** Because the standard 8am-10pm caretaker is off-duty, the system skips them and triggers a PagerDuty alert or Twilio voice call to the regional night manager. The dashboard marks the conversation as a critical open incident.
3. **Audit Logging:** The inbound text, system context, AI draft, and escalation timestamp are safely committed to the `messages` and `conversations` database tables for strict SLA tracking.
4. **Automated Fallback (30 mins):** If the night manager misses the alert within the 30-minute SLA, a secondary escalation pushes to the General Manager. A predefined system text updates the guest: "We apologize for the delay; our team is actively trying to reach the on-site emergency staff. We have this prioritized."

## Question C — The Learning
**Handling the Pattern:**
A smart system should auto-tag property `villa-b1` with a high-frequency `complaint:hot_water` flag. This anomaly must prominently display on the operations dashboard as a recurring hardware failure requiring permanent intervention. Crucially, once this hardware failure pattern is detected, the system should temporarily adjust its routing rules: any future message mentioning "water" at Villa B1 should automatically bypass AI drafting and trigger a high-priority agent escalation until operations clears the hardware flag.
**Prevention (Next Steps):** 
1. **Hardware Fix:** Dispatch an external plumber to fully replace the boiler instead of attempting another band-aid patch.
2. **Tech & IoT Fix:** Install an internet-connected smart thermometer on the water heater. If the core temperature drops below baseline, a webhook alerts the caretaker *before* the guest ever notices, transforming reactive support into proactive maintenance.
3. **Process Fix:** Inject a "verify active boiler temperature" step into the mandatory housekeeper digital checklist prior to guest check-in.