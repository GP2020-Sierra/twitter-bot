# Sierra Twitter bot
Periodically tweets warnings about locations with high CO₂ concentrations.

## Usage
### Python script
This script was written in Python 3.7 as that's what Microsoft Azure supports, 
but can be run anywhere with a suitable Python installation, 
<a href="https://github.com/pyenv/pyenv">`pyenv`</a> is handy when using multiple 
versions of Python on one machine.

Required modules are all available on <a href="https://pypi.org/">PyPi</a> and can be installed with:

    pip install -r requirements.txt

The script can then simply be run with:

    python SierraBot.py <url of summary> --daemon <tweet frequency>

E.g. <a href="https://twitter.com/CLSierra2020">@CLSierra2020</a> is run with 
`python SierraBot.py https://gp2020-sierra.azurewebsites.net/api/summary --daemon 15mins`

For `--daemon` and other options taking time periods parsing is done with the  
<a href="https://github.com/wroberts/pytimeparse">`pytimeparse`</a> module, which 
support a wide range of fairly relaxed formats.

Options to keep the bot running include running it in the background using the 
`--log-file` option to send log output to a file or using 
<a href="https://www.gnu.org/software/screen/">GNU Screen</a>.
 
| Option | Usage | Default |
|--------|:------|:--------|
| `-h`, `--help` | show help | |
| `-warn <max. concentration>`, `--warning-threshold <max. concentration>` | CO₂ concentration (ppm) at which to post a warning | 1400 ppm |
| `-safe <safe concentration>`, `--safety-threshold <safe concentration>` |CO₂ concentration (ppm) at which to post a safety notice | 1000 ppm |
| `--averaging-period <time threshold>` | Time period for which to consider conditions | All time (as far as provided by the summary) |
| `--warning-period <warning period>` | How frequently to repeat warnings about rooms with detrimental conditions | `<time threshold>` if given, otherwise 90 minutes |
| `-keys <key file>`, `--key-file <key file>` | File containing Twitter API keys | `keys.json` |
| `-templates <template file>`, `--template-file <template file>` | File containing templates for tweets | `templates.json` |
| `-log [log file]`, `--log-file [log file]` | File for log messages | `SierraBot.py.log` if option provided, otherwise log messages go to stdout/stderr |
| `--logging-level <logging level>` | Minimum level of log messages, one of: `CRITICAL`, `ERROR`, `WARNING`, `INFO`, `DEBUG`, `NOTSET` | `WARNING` |

### Twitter API
Running a Twitter bot requires access to Twitter's API, which you can request 
<a href="https://developer.twitter.com/en/apply-for-access">here</a>. You'll 
need to create an app to get an API key and secret and an access token and secret.
When you first run `SierraBot.py` it will create a `.json` file in which to place 
these. The script will log a `DEBUG` message with the account handle if you want 
to check it has access. 

## Future extensions
(in rough order of implementation)
- Include timestamps in templates
- Only create template file if argument given but invalid/nonexistant
- More/richer tweet templates
    - Provide more values to templates, e.g. thresholds, values of CO₂, temperature, etc. 
- Make `--daemon` switch optional, preserving state over executions, so can be used with external schedulers e.g. cron
- Cycle through locations over some period, rather than sending a barrage of tweets at once
- Some sort of combining metric to represent stuffiness/quality of work environment
- Occasional room recommendations
    - Would want as a separate thread, complicates things when daemon-mode is optional
