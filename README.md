# Sierra Twitter bot
Periodically tweets warnings about locations with high CO₂ concentrations.

### TODO
- Take command line parameters
    - Check period
    - Averaging period
    - Min. repeated warning period
    - CO₂ warning & safety threshold
    - Paths to key, template and log files (optional)
    - URL of summary file
    - Switch to run as cronjob, i.e. cron manages repeating
        - Need to save state between invocations, may also be useful in continuous mode for seamless restarts
    - Switch to set logging level
- Cycle through locations over some period, rather than sending a barrage of tweets at once
- Some sort of combining metric to represent stuffiness/quality of work environment
- Occasional room recommendations