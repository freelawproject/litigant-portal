User enters flow: [https\://www\.azcourts.gov/drive](https://www.azcourts.gov/drive), \[Got a ticket? Learn more.\] (or similar link language)

Taken to [litigantportal.com/az](http://litigantportal.com/az) landing page

### **\*\*Need: Court branding, exact court name**

Button displayed: Civil Traffic (large heading on button), “Tickets, traffic school, fines, and payment options” (sub header)

Text box displayed with “Chat with the AI Assistant” above it. 

Two Entry Points: AI Chat \+ Non-AI Button Navigation

## **Non-AI Button Navigation (Civil Traffic button clicked)**

3 options: 

1. I got a ticket and want to know my options. Go to \[Know Options\]  
2. I just want to pay. Go to \[Payment Options\]   
3. I have a hold or suspension on my license or registration. Go to \[Hold or Suspension\]

Pre-qualification question: Are you 18 years of age or older? If yes, continue. If no, add in juvenile deviations throughout. 

# **Know Options**

## **Did your citation come from a court or officer directly, or from a letter or notice sent by Arizona’s Motor Vehicle Division (MVD)?”**

1. ## **From a court or officer**

   1. ## **Do you have your citation? You can take a photo of it, or answer a few questions instead.”**

      1. ### **Upload a photo.**

         1. “Here’s what we found on your citation. Please check that this is correct before we continue.”  
            1. Status: civil  
               1. If status \= criminal, take to \[Criminal End\]  
            2. Violation Code:   
               1. Check against list of eligible violation codes	  
               2. If ineligible, Go To \[Ineligible Violation Codes\]   
            3. Violation date: (must be in past)  
            4. Court date: (if past, flag that and follow \[Already Missed Court Date\] pathway; less than 7 days from today’s date \= past completion deadline, flag. Court date has to be after violation date.   
         2. Press the confirm button. If no, allow user to change field answers. Go to \[Options section\]; save to Briefcase

      2. ### **Answer questions instead.**

         1. Is this a civil or criminal citation?  
            1. If criminal, take to \[Criminal End\]. **🛑**  
            2. If civil, continue.   
         2. What is the violation code?   
            1. If outside list of eligible, go to \[Ineligible Violation Codes\] **🛑**  
            2. If on eligible list, continue.   
         3. What was the date of the violation? (must be in past)  
         4. What is your court date? (if past, flag that and follow \[Already Missed Court Date\] pathway; less than 7 days from today’s date \= past completion deadline, flag. Court date has to be after violation date.   
         5. Save all to briefcase. Go to \[Options section\]

      3. ### **I don’t have my citation. 🛑**

         1. Let’s look up your citation on the Arizona courts’ Public Access portal. (gathers below fields \+ hits CORE API)  
            1. Full name:   
            2. Date of birth:   
         2. If found: LP takes user back to \[Answer questions instead\] screens as if they’d had citation all along.   
         3. If not found: “We couldn’t find a matching record. Do you know which court or jurisdiction issued your citation?”  
            1. Yes  
               1. “Please call the court directly and ask about your case status. Let’s gather what you have, so you’re ready when you call, and so we can keep helping here.” \[Tell user to ask court for this, if they don’t have it\]  
                  1. Violation code  
                  2. Violation date  
                  3. Court date  
                  4. Jurisdiction  
               2. After they confirm info with court, go to \[Answer questions instead section\]  
            2. No.   
               1. “Court records can sometimes take a little time to update. You can check back here in about 10 business days, or we can send a summary of this conversation to court support staff so they can look into this for you.”  
                  1. Send it.  
                     1. “Here’s the summary we’d send” \[Summary: \[AI-drafted rollup of this conversation — the intent, the search terms entered, the fact that no record was found\]; Excludes: Social Security number, driver's license number\]  
                     2. Your email address:   
                     3. Send it button. Acknowledge that it went through.🛑   
                  2. I’ll check back later.🛑   
2. A letter or notice from MVD  
   1. Go To \[MVD Letter\] section. 

   # **Options:** 

1. ## **What would you like to do about this citation?** 

   1. ### **See if I can attend defensive driving school**

      1. Go to \[Eligibility Questions\]

   2. ### **Just pay the citation**

      1. “Before you continue: if you haven’t attended defensive driving school in the past 12 months, and this violation doesn’t involve a serious injury or a commercial-vehicle exclusion, school may be available, and it would dismiss this citation with no points added. Want to check first?”  
         1. Yes: Go to \[Eligibility Questions\]  
         2. No: Go to \[Payment Options\]

   3. ### **Contest the citation**

      1. “Before you continue: if you haven’t attended defensive driving school in the past 12 months, and this violation doesn’t involve a serious injury or a commercial-vehicle exclusion, school may be available, and it would dismiss this citation with no points added. Want to check first?”  
         1. Yes: Go to \[Eligibility Question\]  
         2. No: Go to \[How to Contest\] 

   # **Eligibility questions**

1. ## **“Have you completed a defensive driving course for an eligible citation in the past 12 months?” \[Call out that the 12 months calculation is between ticket violation dates, not class completion dates. So it’s important to know violation date to violation date.\]**

   1. Yes  
      1. “Here’s how the 12 months are counted: it’s the time between your two tickets, not between your last class and today.”   
      2. Field: Prior violation date (double check today-prior violation date \< 12 months)  
         1. If user doesn’t know prior violation  
      3. If really w/in 12 month window, “Based on that date, defensive driving school isn’t available for this citation right now. Here are your remaining options.”  
         1. Show \[Pay the Citation\], Go to \[Payment Options\]  
         2. Show \[Contest the Citation\], Go to \[How to Contest\]  
   2. No, continue

2. ## **“Was this violation connected to a crash involving a serious injury or death?” (if the citation itself indicates no injury or fatality, this can render as a confirm-back statement ("Your citation doesn't indicate a crash involving serious injury or death — is that right?") rather than a cold question. )**

   1. Yes  
      1. “Because this involved a serious injury or death, defensive driving school isn’t available for this citation. Here are your remaining options: [Pay the citation]() or [Contest the citation]()” \[How to Contest\] and \[Payment Options\]   
   2. No, continue

3. ## **“Is your driver’s license from Arizona, or another state?”**

   1. Arizona, continue  
   2. Another state

4. ## **Is your license a commercial driver’s license (CDL) or a regular one (vehicle or motorcycle)?**

   1. Regular, continue  
   2. CDL  
      1. Were you driving a CDL required vehicle (work vehicle) at the time of the citation?   
         1. No, continue  
         2. Yes, “Because this violation happened while driving a vehicle that required a CDL for work, defensive driving school isn’t available for this citation. Commercial drivers in this situation are generally directed to Traffic Survival School (TSS) instead. You can find more information here \[link\].”  
5. “Based on what you’ve told us, you appear to meet the general requirements for defensive driving school. This is a preliminary check, not a final answer. The school you choose will run its own check against the state’s records, and that check is what actually decides your eligibility.”  
   1. Continue, Go to \[Driving School Costs & Deadlines\]

   # **Driving School Costs & Deadlines**

1. “Here is your estimated cost \$” (violation date locks fee, need diversion fee \+ state surcharge (\$45) \+ school fee (can change, so shouldn’t be included, but noted that that is extra)) (surcharge also changes April 1 and October 1 each year, so fast updates needed)  
   1. Continue  
2. “You must complete your defensive driving school 7 days before your court date of \[enter court date\]. That means your deadline is \[court date minus 7 days\].”	  
   1. “What if I need more time?”  
      1. “You can call the court and request an extension.”   
3. “Here’s the certified school list and Arizona’s defensive driving program contact information. \[LINK\]. You’ll register, schedule, and pay any additional school fees directly with the school. That part isn’t handled here.”  
   1. Continue  
4. “Do you want to sign up for reminders as your deadline approaches? We can also check in after your class to confirm the school reported your completion to the court.”   
   1. Yes, remind me. Go to \[Register/Login\], then \[Text/Email Alerts\]  
   2. No, thanks. 

   # **MVD letter**

A letter or notice from MVD

# **Payment Options**

Brittany’s website

Scottsdale said they had video on their website of how to pay, could do payment plans if you called the clerk or came in

9 courts don’t use AZcourtpay.com

# **Criminal End 🛑**

	“This tool covers civil traffic citations only. Criminal traffic matters are outside what we can help with here. Criminal charges carry higher stakes and different rights, including the right to an attorney. We’d recommend speaking with a lawyer or contacting legal aid rather than continuing through this tool.” 

- Buttons for referrals to Legal Aid, Lawyer/Bar Ass’n, Contact the Court

  # **Ineligible Violation Codes**

  # **Already Missed Court Date**

  # **How to Contest**

Contesting/asking to see the judge \= lose/waive defensive driving school

Paper evidence only or burned into a CD

Scottsdale had a video explaining process. Rebecca Brannan (Scottsdale) said she’d ask if we could link to video. 

# **Hold or Suspension**

https\://claude.ai/artifact/TbYUYDLmbZ49cSaezCgkhA?sk=XQTC\_gzHXZDQKgtmwxC9GQ