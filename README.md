# Sierra Twitter bot
Periodically tweets warnings about locations with high CO₂ concentrations.

### Future extensions
(in order in which to implement)
- Only create template file if argument given but invalid/nonexistant
- More/richer tweet templates
    - Provide more values to templates, e.g. thresholds, values of CO₂, temperature, etc. 
- Make `--daemon` switch optional, preserving state over executions, so can be used with external schedulers e.g. cron
- Cycle through locations over some period, rather than sending a barrage of tweets at once
- Some sort of combining metric to represent stuffiness/quality of work environment
- Occasional room recommendations
    - Would want as a separate thread, complicates things when daemon-mode is optional