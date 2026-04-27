This is a list of use cases by which the app will be tested. 

## User Interactions

### Registering for an account
- no registering for account. 
- [ ] there is a CLI tool for user management
  - [ ] admins can add new users
  - [ ] admins can delete users
  - [ ] admins can update users
    - [ ] change password
    - [ ] change email
    - [ ] change name
    - [ ] change role
  - [ ] admins can list users

### Logging in
- [ ] User enters email and password
- [ ] User clicks login
- [ ] User is redirected to med list page

### Logout
- [ ] User clicks logout
- [ ] User is redirected to login page

### Add Medicine
- [ ] User clicks add medicine button
- [ ] User is redirected to add medicine page
- [ ] User enters medicine name
- [ ] User enters medicine dosage
- [ ] User enters medicine frequency
- [ ] User enters medicine start date
- [ ] User enters medicine end date
- [ ] User clicks save
- [ ] User is redirected to med list page

## User Stories

### Granny Smith
* Granny smith is an older lady who has to take medication 3 times a day. She
  wants to be able to quickly see if she's taken her morning, afternoon and
  evening doses and be able to mark them as taken.
* Not only does she want to see that she took her medication, she wants to
  see a timestamp of when she took it.
* She also needs to be reminded of her medication at the scheduled times.
* She also fills out a lot of medical paperwork and would like a list of her
  medications with the dosages and frequencies.

### Billy Bat
* Tore his ACL and has had surgery for it. to manage the pain he has been
  prescribed T3 pain medication. He can take 3 in a 6 hour period if needed.
  However, he wants to keep from having valleys in his pain med coverage, so
  he takes 1 every 2 hours keep at a peak level of pain coverage.
* He also needs to be reminded of his medication at the scheduled times.
  However, he needs to be able to snooze the reminder for an hour if he's in
  the middle of something.

### Migrane Molly
* Molly gets migraines and has to take medication to treat them. She can't take
  Ibprophen when under the effects of her migraine medication. She also has to
  wait 2 hours to take Tylenol if she takes her migraine medication.

### Headache Harry
* Harry gets headaches and just takes regular advil as needed. Unfortunately he's
  forgetful and doesn't always remember if he's taken his medication. He'd like
  to be able to see a list of his medication with a timestamp of when he took it.

### Diabetic Dan
* Dan has type 2 diabetes and has to take medication to treat it. He needs to
  take his medication at specific times of the day, but he doesn't need to take
  it at the same time every day. He'd like to be able to see a list of his
  medication with a timestamp of when he took it.
* He also needs to be reminded of his medication at the scheduled times.
  However, he needs to be able to snooze the reminder for an hour if he's in
  the middle of something.

## Thoughts on Timers

I've been thinking about the timer implementation. It seems like there are a few types of medication timers. 

1. Ones like Granny smith's doesn't need a timer. Just a boolean flag that gets flipped
   when the user takes the medication. It will need a very obvious indicator that the
   medication has been taken. Also a modal or something if it is tapped again. Like "This med has
   already been taken. Would you like to remove the "taken" status?"
2. Ones like Molly's needs a timer. It should probably count up, indicating how long
   its been since the last dose.
3. Ones like Harry's needs a timer. It should probably count down, indicating how long
   its been since the last dose, and how long until he can take another.
4. Ones like Billy's needs a timer. It should probably count down, indicating how long
   its been since the last dose, and how long until he can take another. However, it needs
   a timer for each of his sub doses. Maybe split the timer bar in 3rds?
   Or have 3 timers bars attached under the medication entry? one for each dose.

## Thoughts on tracking meds over time

How will we track if a user has taken their medication over a long period of time? 
Mostly concerned about  tracking regular prescription medication. like did I remember
to take my blood pressure medication yesterday? or last week?

Probably need some sort of calendar view. or stacked bars or something to show
that the user took their medication on a given day. 

Maybe color coding would be good too?

## Developer Story

As a very busy developer, 
- I want the code base to adhere to strict software engineering principles, so
  that I can be assured that it is well-written and maintainable.
  - Obey SOLID principles
  - Obey KISS principles
  - Obey DRY principles
  - Obey YAGNI principles
- I want the code base to be well-documented, so that I can understand it
  quickly.
- I want the code base to be well-tested, so that I can be assured that it
  is working correctly.
- I want the code base to be well-architected, so that I can understand it
  quickly.
- I want the code base to be fully typed
- I want the code base to be composed of reasonably sized functions and files
  so that it is easy to understand and maintain
- I want the code base to be loosely coupled
- I want the code base to have minimal code / data model duplication.
- I want the code base to have no dead code.
- I want the code base to be easily testable
- I want the docs/ dir to have comprehensive documentation.
  - ADRs for architectural decisions
  - ER diagrams for the data model
  - State diagrams for the application state
  - User stories
  - Use cases
  - Sequence diagrams for key user flows
- I don't want deeply nested code or conditional logic
- I don't want deeply nested data models
