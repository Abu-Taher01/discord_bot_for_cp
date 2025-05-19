# Codeforces Discord Bot

A Discord bot for tracking Codeforces progress, managing contests, and maintaining daily problem-solving goals.

## Features

- **Codeforces Integration**
  - Track solved problems
  - View problem history
  - Monitor daily progress

- **Group Contests**
  - Create and manage contests
  - Track participant progress
  - Generate rankings

- **Daily Goals System**
  - Set daily problem-solving targets
  - Track completion status
  - Penalty system for missed goals

- **Ranking System**
  - User rankings based on performance
  - Contest leaderboards
  - Progress tracking

- **Goal Tracking**
  - Daily, weekly, monthly goals
  - Streak system with rewards

- **Timezone Support**
  - Customizable timezone

## Deployment Instructions

### 1. Create a Replit Account
1. Go to [Replit](https://replit.com)
2. Sign up for a free account
3. Click "Create Repl"
4. Choose "Python" as your language
5. Name your repl (e.g., "codeforces-bot")

### 2. Set Up Your Bot
1. Create a new Discord application at [Discord Developer Portal](https://discord.com/developers/applications)
2. Go to the "Bot" section and create a bot
3. Copy your bot token
4. In Replit, create a new file called `.env`
5. Add your bot token: `DISCORD_TOKEN=your_token_here`

### 3. Upload Files
1. Upload all the bot files to your Replit:
   - `bot.py`
   - `db.py`
   - `goals.py`
   - `contest_manager.py`
   - `codeforces_api.py`
   - `keep_alive.py`
   - `requirements.txt`

### 4. Install Dependencies
1. In Replit's shell, run:
   ```bash
   pip install -r requirements.txt
   ```

### 5. Set Up UptimeRobot
1. Go to [UptimeRobot](https://uptimerobot.com)
2. Sign up for a free account
3. Add a new monitor
4. Choose "HTTP(s)" as the monitor type
5. Name it (e.g., "Codeforces Bot")
6. Add your Replit URL (e.g., `https://your-repl-name.your-username.repl.co`)
7. Set the monitoring interval to 5 minutes

### 6. Run the Bot
1. In Replit, click the "Run" button
2. Your bot should now be online and stay online 24/7

## Commands

- `!cf set <handle>` - Set your Codeforces handle
- `!cf stats` - View your problem-solving statistics
- `!contest create <name> <duration>` - Create a new contest
- `!contest join <contest_id>` - Join a contest
- `!contest list` - List active contests
- `!goal set <number>` - Set daily problem-solving goal
- `!goal status` - Check goal completion status
- `!rank` - View current rankings
- `!help` - View all available commands

## Support

If you encounter any issues:
1. Check the Replit console for error messages
2. Make sure your bot token is correct
3. Verify that UptimeRobot is pinging your Replit URL
4. Check if all dependencies are installed correctly

## Notes

- The free tier of Replit may have some limitations
- The bot will restart if Replit's free tier goes to sleep
- UptimeRobot's free tier allows up to 50 monitors
- Keep your bot token secret and never share it

## Contributing

Feel free to contribute to this project by:
1. Forking the repository
2. Creating a new branch
3. Making your changes
4. Submitting a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 