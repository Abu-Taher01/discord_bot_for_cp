# Codeforces Discord Bot Documentation

## Overview
This Discord bot helps users track their progress on Codeforces, manage group contests, and maintain daily problem-solving goals. It provides features for goal tracking, contest management, and Codeforces integration.

## Features

### 1. Goal Management System
- **Daily Goals**: Set and track daily problem-solving targets
- **Weekly Goals**: Set weekly problem-solving targets
- **Monthly Goals**: Set monthly problem-solving targets
- **Category Goals**: Set goals for specific problem categories (e.g., difficulty ratings)
- **Goal Streaks**: Track daily streaks and best streaks
- **Goal History**: View your goal completion history
- **Streak Rewards**: Earn rewards for maintaining streaks
- **Goal Reminders**: Get reminders to complete your daily goals
- **Timezone Support**: All goals and reminders are based on your local timezone

### 2. Contest Management
- Create and manage group contests
- Join and leave contests
- Track contest progress and scores
- View contest results and rankings
- Set contest duration and start/end times

### 3. Codeforces Integration
- Link your Codeforces handle
- View your Codeforces profile
- Track solved problems
- View rating history
- Get problem statistics by rating and tags

### 4. Ranking System
- Global user rankings
- Streak-based scoring
- Penalty system for missed goals
- Contest-based rankings

## Commands

### Goal Management Commands

#### Set Goals
```
!setgoal <daily> [weekly] [monthly] [reminder_time]
```
- Sets your daily, weekly, and monthly goals
- Optional reminder time in HH:MM format (24-hour)
- Example: `!setgoal 5 30 100 20:00`

#### Set Category Goals
```
!setcategorygoal <category_type> <category_value> <count>
```
- Sets a goal for a specific category
- Example: `!setcategorygoal rating 1500 10`

#### View Goals
```
!goals
```
- Shows your current goals and progress
- Displays daily, weekly, and monthly progress
- Shows current streak and best streak
- Lists category goals and their progress

#### View History
```
!history [days]
```
- Shows your goal completion history
- Optional parameter for number of days (1-30)
- Default: 7 days
- Example: `!history 14`

#### View Rewards
```
!rewards
```
- Shows your available streak rewards
- Displays reward type and value

#### Claim Rewards
```
!claim <streak_length>
```
- Claims a streak reward
- Example: `!claim 7`

#### Set Timezone
```
!timezone <timezone>
```
- Sets your timezone for goal tracking
- Example: `!timezone America/New_York`

### Contest Management Commands

#### Create Contest
```
!createcontest <name> <duration>
```
- Creates a new contest
- Example: `!createcontest Weekly Practice 60 1200 1800`

#### Join Contest
```
!joincontest <contest_id>
```
- Joins an existing contest
- Example: `!joincontest 1`

#### Leave Contest
```
!leavecontest <contest_id>
```
- Leaves a contest
- Example: `!leavecontest 1`

#### Start Contest
```
!startcontest <contest_id>
```
- Starts a contest
- Example: `!startcontest 1`

#### End Contest
```
!endcontest <contest_id>
```
- Ends a contest and shows results
- Example: `!endcontest 1`

#### View Contest Status
```
!conteststatus <contest_id>
```
- Shows current contest status
- Example: `!conteststatus 1`

#### List Contests
```
!contests
```
- Lists all active contests

### Codeforces Integration Commands

#### Register Handle
```
!register <cf_handle>
```
- Registers your Codeforces handle
- Example: `!register tourist`

#### View Profile
```
!profile
```
- Shows your Codeforces profile information

#### View Solved Problems
```
!solved
```
- Shows your solved problems statistics

#### View Rating History
```
!rating
```
- Shows your rating history

### Other Commands

#### Help
```
!help
```
- Shows all available commands and their usage

## Database Schema

### Users Table
- `discord_id`: Primary key
- `cf_handle`: Codeforces handle
- `timezone`: User's timezone

### Daily Goals Table
- `discord_id`: Primary key
- `daily_goal`: Daily problem goal
- `weekly_goal`: Weekly problem goal
- `monthly_goal`: Monthly problem goal
- `last_updated`: Last update timestamp
- `penalties`: Number of penalties
- `streak`: Current streak
- `best_streak`: Best streak achieved
- `last_check`: Last check timestamp
- `last_penalty`: Last penalty timestamp
- `solved_today`: Problems solved today
- `solved_this_week`: Problems solved this week
- `solved_this_month`: Problems solved this month
- `reminder_time`: Daily reminder time

### Goal Categories Table
- `discord_id`: User ID
- `category_type`: Category type
- `category_value`: Category value
- `goal_count`: Goal count
- `current_count`: Current progress
- `last_updated`: Last update timestamp

### Goal History Table
- `id`: Primary key
- `discord_id`: User ID
- `date`: Goal date
- `goal_type`: Type of goal
- `target`: Target count
- `achieved`: Achieved count
- `streak`: Streak at that time

### Streak Rewards Table
- `discord_id`: User ID
- `streak_length`: Streak length
- `reward_type`: Type of reward
- `reward_value`: Reward value
- `claimed`: Whether claimed
- `claimed_at`: Claim timestamp

### Contests Table
- `id`: Primary key
- `name`: Contest name
- `duration`: Contest duration
- `created_by`: Creator's Discord ID
- `created_at`: Creation timestamp
- `status`: Contest status
- `start_time`: Start timestamp
- `end_time`: End timestamp

### Contest Participants Table
- `contest_id`: Contest ID
- `discord_id`: User ID
- `score`: User's score

## Timezone Support
The bot supports all standard timezone names (e.g., 'UTC', 'America/New_York'). All goal tracking and reminders are based on the user's local timezone. The day resets at 4 AM in the user's timezone to allow for late-night problem solving.

## Streak System
- Daily streaks are maintained by completing daily goals
- Streaks reset if a daily goal is not met
- Weekly rewards are given at 7-day milestones
- Monthly rewards are given at 30-day milestones
- Best streaks are tracked separately from current streaks

## Penalty System
- Penalties are applied when daily goals are not met
- Penalties affect the user's ranking score
- Penalty history is tracked and displayed in user statistics

## Ranking System
The ranking system considers:
- Total problems solved
- Current streak (bonus points)
- Penalties (negative points)
- Contest performance

## Error Handling
The bot includes comprehensive error handling for:
- Invalid commands
- Database errors
- API failures
- Timezone validation
- Goal validation
- Contest management

## Security
- All database operations use parameterized queries
- User data is isolated by Discord ID
- API calls are rate-limited
- Input validation for all commands 