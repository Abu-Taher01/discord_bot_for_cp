import os
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
from datetime import datetime, timedelta
import aiohttp
from bs4 import BeautifulSoup
from codeforces_api import CodeforcesAPI
from contest_manager import ContestManager
from goal_manager import GoalManager
from db import get_db_connection, init_db
import asyncio
import pytz
import sqlite3
from typing import Dict, List, Optional
from keep_alive import keep_alive

# Load environment variables
load_dotenv()

# Get token from environment variable (works for both local and Replit)
TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    raise ValueError("No token found. Please set DISCORD_TOKEN in your environment variables or .env file.")

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Initialize managers
contest_manager = ContestManager()
goal_manager = GoalManager()

# Initialize database
init_db()

# Add a check to see if the database file exists
DB_FILE = 'codeforces_bot.db' # Make sure this matches the one in db.py
if os.path.exists(DB_FILE):
    print(f"Database file '{DB_FILE}' found after init_db().")
else:
    print(f"Database file '{DB_FILE}' NOT found after init_db().")

class CustomHelpCommand(commands.HelpCommand):
    def __init__(self):
        super().__init__()
        self.command_categories = {
            'Goal Management': [
                'setgoal', 'setcategorygoal', 'goals', 'history', 
                'rewards', 'claim', 'timezone'
            ],
            'Contest Management': [
                'createcontest', 'joincontest', 'leavecontest', 
                'startcontest', 'endcontest', 'conteststatus', 'contests',
                'contestproblems', 'mystatus', 'liveleaderboard'
            ],
            'Codeforces Integration': [
                'register', 'profile', 'solved', 'rating'
            ],
            'Other': ['help']
        }

    async def send_bot_help(self, mapping):
        """Send the main help message."""
        embed = discord.Embed(
            title="Codeforces Bot Help",
            description="Here are all the available commands. Use `!help <command>` for more details about a specific command.",
            color=discord.Color.blue()
        )

        for category, commands in self.command_categories.items():
            command_list = []
            for cmd in commands:
                command = self.context.bot.get_command(cmd)
                if command:
                    command_list.append(f"`!{cmd}`")
            if command_list:
                embed.add_field(
                    name=category,
                    value="\n".join(command_list),
                    inline=False
                )

        await self.get_destination().send(embed=embed)

    async def send_command_help(self, command):
        """Send help for a specific command."""
        embed = discord.Embed(
            title=f"Command: !{command.name}",
            description=command.help or "No description available.",
            color=discord.Color.green()
        )

        # Add usage information
        if command.signature:
            embed.add_field(
                name="Usage",
                value=f"`!{command.name} {command.signature}`",
                inline=False
            )

        # Add examples if available
        examples = {
            'setgoal': '`!setgoal 5 30 100 20:00` - Set daily goal of 5 problems, weekly goal of 30, monthly goal of 100, with reminder at 20:00',
            'setcategorygoal': '`!setcategorygoal rating 1500 10` - Set goal to solve 10 problems of rating 1500',
            'createcontest': '`!createcontest Weekly Practice 2h` - Create a 2-hour contest named "Weekly Practice"',
            'register': '`!register tourist` - Register with Codeforces handle "tourist"',
            'timezone': '`!timezone America/New_York` - Set your timezone to New York'
        }

        if command.name in examples:
            embed.add_field(
                name="Example",
                value=examples[command.name],
                inline=False
            )

        # Add related commands
        related_commands = {
            'setgoal': ['goals', 'history', 'timezone'],
            'goals': ['setgoal', 'history', 'rewards'],
            'createcontest': ['joincontest', 'startcontest', 'endcontest'],
            'register': ['profile', 'solved', 'rating']
        }

        if command.name in related_commands:
            related = [f"`!{cmd}`" for cmd in related_commands[command.name]]
            embed.add_field(
                name="Related Commands",
                value="\n".join(related),
                inline=False
            )

        await self.get_destination().send(embed=embed)

    async def send_group_help(self, group):
        """Send help for a command group."""
        embed = discord.Embed(
            title=f"Command Group: !{group.name}",
            description=group.help or "No description available.",
            color=discord.Color.blue()
        )

        for command in group.commands:
            embed.add_field(
                name=f"!{group.name} {command.name}",
                value=command.help or "No description available.",
                inline=False
            )

        await self.get_destination().send(embed=embed)

    async def command_not_found(self, string):
        """Handle when a command is not found."""
        embed = discord.Embed(
            title="Command Not Found",
            description=f"Command `{string}` not found. Use `!help` to see all available commands.",
            color=discord.Color.red()
        )
        await self.get_destination().send(embed=embed)

    async def subcommand_not_found(self, command, string):
        """Handle when a subcommand is not found."""
        embed = discord.Embed(
            title="Subcommand Not Found",
            description=f"Subcommand `{string}` not found for command `{command.name}`.",
            color=discord.Color.red()
        )
        await self.get_destination().send(embed=embed)

# Set the custom help command
bot.help_command = CustomHelpCommand()

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    update_daily_goals.start()
    update_live_leaderboards.start()
    # Load cogs
    await load_cogs()

async def load_cogs():
    """Load all cogs."""
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            await bot.load_extension(f'cogs.{filename[:-3]}')
            print(f'Loaded {filename}')

@bot.command(name='cf')
async def codeforces(ctx, action: str, handle: str = None):
    """Codeforces related commands"""
    if action == 'set':
        if not handle:
            await ctx.send('Please provide a Codeforces handle!')
            return

        # Verify handle exists
        user_info = await CodeforcesAPI.get_user_info(handle)
        if not user_info:
            await ctx.send('Invalid Codeforces handle!')
            return

        # Update user's Codeforces handle
        conn = get_db_connection()
        konnet = conn.konnet()
        konnet.execute(
            "INSERT OR REPLACE INTO users (discord_id, cf_handle) VALUES (?, ?)",
            (ctx.author.id, handle)
        )
        conn.commit()
        conn.close()
        await ctx.send(f'Codeforces handle set to {handle}!')

    elif action == 'stats':
        conn = get_db_connection()
        konnet = conn.konnet()
        konnet.execute("SELECT cf_handle FROM users WHERE discord_id = ?", (ctx.author.id,))
        user = konnet.fetchone()
        conn.close()

        if not user:
            await ctx.send('Please set your Codeforces handle first using `!cf set <handle>`')
            return

        # Get user's submissions and calculate statistics
        submissions = await CodeforcesAPI.get_user_submissions(user['cf_handle'])

        # Add a print statement to check the number of submissions fetched
        print(f"Fetched {len(submissions) if submissions else 0} submissions for {user['cf_handle']}")

        if not submissions:
            await ctx.send('Could not fetch submissions from Codeforces!')
            return

        stats = CodeforcesAPI.get_user_statistics(submissions)

        # Create embed with statistics
        embed = discord.Embed(
            title=f'Codeforces Statistics for {user["cf_handle"]}',
            color=discord.Color.blue()
        )

        embed.add_field(
            name='Total Problems Solved',
            value=str(stats['total_solved']),
            inline=False
        )

        # Add rating distribution
        rating_dist = '\n'.join([f'{rating}: {count}' for rating, count in sorted(stats['problems_by_rating'].items())])
        if rating_dist:
            embed.add_field(
                name='Problems by Rating',
                value=rating_dist,
                inline=False
            )

        # Add top tags
        top_tags = sorted(stats['problems_by_tag'].items(), key=lambda x: x[1], reverse=True)[:5]
        tags_dist = '\n'.join([f'{tag}: {count}' for tag, count in top_tags])
        if tags_dist:
            embed.add_field(
                name='Top Problem Tags',
                value=tags_dist,
                inline=False
            )

        await ctx.send(embed=embed)

@bot.command(name='createcontest')
async def create_contest(ctx, name: str, duration: str, problem_count: int, min_rating: int, max_rating: int):
    """Create a new contest with randomly selected problems within a rating range"""
    # Validate rating range
    if min_rating > max_rating:
        await ctx.send("Minimum rating cannot be greater than maximum rating.")
        return

    contest_id = await contest_manager.create_contest(
        name, duration, ctx.author.id, problem_count, min_rating, max_rating
    )

    if contest_id:
        await ctx.send(f'Contest created! ID: {contest_id}. {problem_count} problems with ratings between {min_rating} and {max_rating} have been added.')
    else:
        await ctx.send("Failed to create contest. Please check the duration format (e.g., 2h, 30m).")

@bot.command(name='joincontest')
async def join_contest(ctx, contest_id: int):
    """Join an existing contest"""
    success, message = await contest_manager.join_contest(contest_id, ctx.author.id)
    await ctx.send(message)

@bot.command(name='leavecontest')
async def leave_contest(ctx, contest_id: int):
    """Leave a contest"""
    konnet = get_db_connection().konnet()
    konnet.execute("DELETE FROM contest_participants WHERE contest_id = ? AND discord_id = ?", 
                  (contest_id, ctx.author.id))
    get_db_connection().commit()
    await ctx.send("Successfully left the contest")

@bot.command(name='startcontest')
async def start_contest(ctx, contest_id: int):
    """Start a contest"""
    success, message = await contest_manager.start_contest(contest_id)
    await ctx.send(message)

@bot.command(name='endcontest')
async def end_contest(ctx, contest_id: int):
    """End a contest and show results"""
    success, message = await contest_manager.end_contest(contest_id)
    if success:
        # Get contest results
        conn = get_db_connection()
        konnet = conn.konnet()
        konnet.execute("SELECT name FROM contests WHERE id = ?", (contest_id,))
        contest = konnet.fetchone()

        if contest:
            embed = discord.Embed(
                title=f'Contest Results: {contest["name"]}',
                color=discord.Color.green()
            )

            konnet.execute("""
                SELECT u.cf_handle, cp.score
                FROM contest_participants cp
                JOIN users u ON cp.discord_id = u.discord_id
                WHERE cp.contest_id = ?
                ORDER BY cp.score DESC
            """, (contest_id,))

            results = konnet.fetchall()
            for i, result in enumerate(results, 1):
                embed.add_field(
                    name=f'{i}. {result["cf_handle"]}',
                    value=f'Score: {result["score"]}',
                    inline=False
                )

            await ctx.send(embed=embed)
        conn.close()

        # Clear live leaderboard message ID and channel ID
        conn = get_db_connection()
        konnet = conn.konnet()
        konnet.execute(
            "UPDATE contests SET leaderboard_message_id = NULL, channel_id = NULL WHERE id = ?",
            (contest_id,)
        )
        conn.commit()
        conn.close()
    else:
        await ctx.send(message)

@bot.command(name='conteststatus')
async def contest_status(ctx, contest_id: int):
    """View the status of a contest"""
    success, status = await contest_manager.get_contest_status(contest_id)
    if not success:
        await ctx.send(status)
        return

    embed = discord.Embed(
        title=f"Contest Status: {status['name']}",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="Status",
        value=status['status'],
        inline=True
    )

    if status['start_time']:
        embed.add_field(
            name="Start Time",
            value=status['start_time'].strftime("%Y-%m-%d %H:%M:%S UTC"),
            inline=True
        )

    if status['end_time']:
        embed.add_field(
            name="End Time",
            value=status['end_time'].strftime("%Y-%m-%d %H:%M:%S UTC"),
            inline=True
        )

    embed.add_field(
        name="Participants",
        value=str(len(status['participants'])),
        inline=True
    )

    if status['participants']:
        participants_list = "\n".join(
            f"{i+1}. {p['handle']}: {p['score']} points"
            for i, p in enumerate(status['participants'])
        )
        embed.add_field(
            name="Current Rankings",
            value=participants_list,
            inline=False
        )

    await ctx.send(embed=embed)

@bot.command(name='contests')
async def list_contests(ctx):
    """List all active contests"""
    success, contests = await contest_manager.list_contests()
    if not success:
        await ctx.send(contests)
        return

    embed = discord.Embed(
        title="Active Contests",
        color=discord.Color.blue()
    )

    for contest in contests:
        embed.add_field(
            name=f"Contest #{contest['id']}: {contest['name']}",
            value=f"Status: {contest['status']}\nDuration: {contest['duration']}\nParticipants: {contest['participants']}",
            inline=False
        )

    await ctx.send(embed=embed)

@bot.command(name='contestproblems')
async def view_contest_problems(ctx, contest_id: int):
    """View problems for a specific contest"""
    success, problems = await contest_manager.get_contest_problems(contest_id)
    if not success:
        await ctx.send(problems)
        return

    # Get contest name
    konnet = get_db_connection().konnet()
    konnet.execute("SELECT name FROM contests WHERE id = ?", (contest_id,))
    contest = konnet.fetchone()

    embed = discord.Embed(
        title=f"Problems for Contest: {contest['name'] if contest else f'#{contest_id}'}",
        color=discord.Color.blue()
    )

    for problem in problems:
        problem_value = f"Rating: {problem['rating']}\n"
        if problem['tags']:
            problem_value += f"Tags: {', '.join(problem['tags'])}\n"
        problem_value += f"Link: https://codeforces.com/problemset/problem/{problem['id'][:-1]}/{problem['id'][-1]}"

        embed.add_field(
            name=problem['name'],
            value=problem_value,
            inline=False
        )

    await ctx.send(embed=embed)

@bot.command(name='mystatus')
async def view_my_status(ctx, contest_id: int):
    """View your problem-solving status in a contest"""
    success, problems = await contest_manager.check_problem_status(contest_id, ctx.author.id)
    if not success:
        await ctx.send(problems)
        return

    # Get contest name
    konnet = get_db_connection().konnet()
    konnet.execute("SELECT name FROM contests WHERE id = ?", (contest_id,))
    contest = konnet.fetchone()

    embed = discord.Embed(
        title=f"Your Status in Contest: {contest['name'] if contest else f'#{contest_id}'}",
        color=discord.Color.blue()
    )

    solved_count = sum(1 for p in problems if p['solved'])
    total_count = len(problems)

    embed.add_field(
        name="Progress",
        value=f"Solved: {solved_count}/{total_count} problems",
        inline=False
    )

    for problem in problems:
        status = "✅" if problem['solved'] else "❌"
        problem_value = f"Status: {status}\n"
        problem_value += f"Rating: {problem['rating']}\n"
        problem_value += f"Link: https://codeforces.com/problemset/problem/{problem['id'][:-1]}/{problem['id'][-1]}"

        embed.add_field(
            name=problem['name'],
            value=problem_value,
            inline=False
        )

    await ctx.send(embed=embed)

@bot.command(name='profile')
async def view_profile(ctx):
    """View your Codeforces profile"""
    konnet = get_db_connection().konnet()
    konnet.execute("SELECT cf_handle FROM users WHERE discord_id = ?", (ctx.author.id,))
    user = konnet.fetchone()

    if not user:
        await ctx.send("Please set your Codeforces handle first using `!cf set <handle>`")
        return

    user_info = await CodeforcesAPI.get_user_info(user['cf_handle'])
    if not user_info:
        await ctx.send("Could not fetch user information from Codeforces")
        return

    embed = discord.Embed(
        title=f"Codeforces Profile: {user_info['handle']}",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="Rating",
        value=str(user_info.get('rating', 'Unrated')),
        inline=True
    )

    embed.add_field(
        name="Max Rating",
        value=str(user_info.get('maxRating', 'Unrated')),
        inline=True
    )

    embed.add_field(
        name="Rank",
        value=user_info.get('rank', 'Unrated'),
        inline=True
    )

    embed.add_field(
        name="Max Rank",
        value=user_info.get('maxRank', 'Unrated'),
            inline=True
        )

    await ctx.send(embed=embed)

@bot.command(name='solved')
async def view_solved(ctx):
    """View your solved problems statistics"""
    konnet = get_db_connection().konnet()
    konnet.execute("SELECT cf_handle FROM users WHERE discord_id = ?", (ctx.author.id,))
    user = konnet.fetchone()

    if not user:
        await ctx.send("Please set your Codeforces handle first using `!cf set <handle>`")
        return

    submissions = await CodeforcesAPI.get_user_submissions(user['cf_handle'])
    if not submissions:
        await ctx.send("Could not fetch submissions from Codeforces")
        return

    stats = CodeforcesAPI.get_user_statistics(submissions)

    embed = discord.Embed(
        title=f"Solved Problems: {user['cf_handle']}",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="Total Solved",
        value=str(stats['total_solved']),
        inline=False
    )

    # Add rating distribution
    rating_dist = '\n'.join([f'{rating}: {count}' for rating, count in sorted(stats['problems_by_rating'].items())])
    if rating_dist:
        embed.add_field(
            name="Problems by Rating",
            value=rating_dist,
            inline=False
        )

    # Add top tags
    top_tags = sorted(stats['problems_by_tag'].items(), key=lambda x: x[1], reverse=True)[:5]
    tags_dist = '\n'.join([f'{tag}: {count}' for tag, count in top_tags])
    if tags_dist:
        embed.add_field(
            name="Top Problem Tags",
            value=tags_dist,
            inline=False
        )

    await ctx.send(embed=embed)

@bot.command(name='rating')
async def view_rating(ctx):
    """View your rating history"""
    konnet = get_db_connection().konnet()
    konnet.execute("SELECT cf_handle FROM users WHERE discord_id = ?", (ctx.author.id,))
    user = konnet.fetchone()

    if not user:
        await ctx.send("Please set your Codeforces handle first using `!cf set <handle>`")
        return

    # Get user's rating history from Codeforces API
    async with aiohttp.ClientSession() as session:
        url = f"{CodeforcesAPI.BASE_URL}/user.rating"
        params = {"handle": user['cf_handle']}

        async with session.get(url, params=params) as response:
            if response.status != 200:
                await ctx.send("Could not fetch rating history from Codeforces")
                return

            data = await response.json()
            if data["status"] != "OK":
                await ctx.send("Could not fetch rating history from Codeforces")
                return

            rating_history = data["result"]

    if not rating_history:
        await ctx.send("No rating history found")
        return

    embed = discord.Embed(
        title=f"Rating History: {user['cf_handle']}",
        color=discord.Color.blue()
    )

    # Show last 5 rating changes
    for change in rating_history[-5:]:
        contest_name = change['contestName']
        old_rating = change['oldRating']
        new_rating = change['newRating']
        change_amount = new_rating - old_rating
        change_sign = "+" if change_amount > 0 else ""

        embed.add_field(
            name=contest_name,
            value=f"Rating: {old_rating} → {new_rating} ({change_sign}{change_amount})",
            inline=False
        )

    # Add current rating
    current_rating = rating_history[-1]['newRating']
    embed.add_field(
        name="Current Rating",
        value=str(current_rating),
        inline=False
        )
    await ctx.send(embed=embed)

@tasks.loop(hours=24)
async def update_daily_goals():
    """Update daily goals and apply penalties"""
    await goal_manager.apply_daily_penalties()

@bot.command(name='rank')
async def rank(ctx):
    """Display user rankings"""
    conn = get_db_connection()
    konnet = conn.konnet()
    konnet.execute("SELECT discord_id, cf_handle FROM users WHERE cf_handle IS NOT NULL")
    users = konnet.fetchall()

    if not users:
        await ctx.send('No users found with Codeforces handles!')
        conn.close()
        return

    # Calculate rankings
    rankings = []
    for user in users:
        submissions = await CodeforcesAPI.get_user_submissions(user['cf_handle'])
        if not submissions:
            continue

        stats = CodeforcesAPI.get_user_statistics(submissions)
        konnet.execute("SELECT streak, penalties FROM daily_goals WHERE discord_id = ?", (user['discord_id'],))
        goal_data = konnet.fetchone()

        score = stats['total_solved']
        if goal_data:
            score += goal_data['streak'] * 10  # Bonus points for streaks
            score -= goal_data['penalties'] * 5  # Penalty points

        rankings.append({
            'handle': user['cf_handle'],
            'score': score,
            'solved': stats['total_solved'],
            'streak': goal_data['streak'] if goal_data else 0
        })

    conn.close()

    # Sort by score
    rankings.sort(key=lambda x: x['score'], reverse=True)

    # Create embed
    embed = discord.Embed(
        title='User Rankings',
        color=discord.Color.gold()
    )

    for i, rank in enumerate(rankings[:10], 1):
        embed.add_field(
            name=f'{i}. {rank["handle"]}',
            value=f'Score: {rank["score"]}\nSolved: {rank["solved"]}\nStreak: {rank["streak"]}',
            inline=False
        )

    await ctx.send(embed=embed)

@bot.command()
async def timezone(ctx, timezone: str):
    """Set your timezone for goal tracking."""
    try:
        # Validate timezone
        pytz.timezone(timezone)

        # Update user's timezone
        conn = sqlite3.connect('codeforces_bot.db')
        konnet = conn.konnet()
        konnet.execute('''
            INSERT OR REPLACE INTO users (discord_id, timezone)
            VALUES (?, ?)
        ''', (ctx.author.id, timezone))
        conn.commit()
        conn.close()

        await ctx.send(f"✅ Your timezone has been set to {timezone}")
    except pytz.exceptions.UnknownTimeZoneError:
        await ctx.send("❌ Invalid timezone. Please use a valid timezone (e.g., 'UTC', 'America/New_York')")

@bot.command(name='setgoal')
async def set_goal(ctx, daily: int, weekly: int = None, monthly: int = None, reminder_time: str = None):
    """Set your daily, weekly, and monthly problem-solving goals"""
    success, message = await goal_manager.set_goals(ctx.author.id, daily, weekly, monthly)
    if success:
        embed = discord.Embed(
            title="Goals Set Successfully",
            description=message,
            color=discord.Color.green()
        )
    else:
        embed = discord.Embed(
            title="Error Setting Goals",
            description=message,
            color=discord.Color.red()
        )
    await ctx.send(embed=embed)

@bot.command(name='setcategorygoal')
async def set_category_goal(ctx, category_type: str, category_value: str, count: int):
    """Set a goal for a specific category (e.g., rating or tag)"""
    if category_type not in ['rating', 'tag']:
        await ctx.send("Category type must be either 'rating' or 'tag'")
        return

    success, message = await goal_manager.set_category_goal(ctx.author.id, category_type, category_value, count)
    if success:
        embed = discord.Embed(
            title="Category Goal Set",
            description=message,
            color=discord.Color.green()
        )
    else:
        embed = discord.Embed(
            title="Error Setting Category Goal",
            description=message,
            color=discord.Color.red()
        )
    await ctx.send(embed=embed)

@bot.command(name='goals')
async def view_goals(ctx):
    """View your current goals and progress"""
    success, stats = await goal_manager.get_user_stats(ctx.author.id)
    if not success:
        await ctx.send(stats)
        return

    embed = discord.Embed(
        title="Your Goals and Progress",
        color=discord.Color.blue()
    )

    # Add daily goal
    embed.add_field(
        name="Daily Goal",
        value=f"Goal: {stats['daily']['goal']}\nSolved: {stats['daily']['solved']}\nRemaining: {stats['daily']['remaining']}",
        inline=True
    )

    # Add weekly goal if set
    if stats['weekly']['goal']:
        embed.add_field(
            name="Weekly Goal",
            value=f"Goal: {stats['weekly']['goal']}\nSolved: {stats['weekly']['solved']}\nRemaining: {stats['weekly']['remaining']}",
            inline=True
        )

    # Add monthly goal if set
    if stats['monthly']['goal']:
        embed.add_field(
            name="Monthly Goal",
            value=f"Goal: {stats['monthly']['goal']}\nSolved: {stats['monthly']['solved']}\nRemaining: {stats['monthly']['remaining']}",
            inline=True
        )

    # Add streak information
    embed.add_field(
        name="Streak",
        value=f"Current: {stats['streak']}\nPenalties: {stats['penalties']}",
        inline=False
    )

    await ctx.send(embed=embed)

@bot.command(name='history')
async def view_history(ctx, days: int = 7):
    """View your goal completion history"""
    if not 1 <= days <= 30:
        await ctx.send("Days must be between 1 and 30")
        return

    success, history = await goal_manager.get_goal_history(ctx.author.id, days)
    if not success:
        await ctx.send(history)
        return

    embed = discord.Embed(
        title=f"Goal History (Last {days} days)",
        color=discord.Color.blue()
    )

    for record in history:
        embed.add_field(
            name=f"{record['date']} - {record['type']}",
            value=f"Target: {record['target']}\nAchieved: {record['achieved']}\nCompletion: {record['completion_rate']:.1f}%\nStreak: {record['streak']}",
            inline=False
        )

    await ctx.send(embed=embed)

@bot.command(name='rewards')
async def view_rewards(ctx):
    """View your available streak rewards"""
    success, rewards = await goal_manager.get_available_rewards(ctx.author.id)
    if not success:
        await ctx.send(rewards)
        return

    embed = discord.Embed(
        title="Available Streak Rewards",
        color=discord.Color.gold()
    )

    for reward in rewards:
        embed.add_field(
            name=f"{reward['streak']}-Day Streak Reward",
            value=f"Type: {reward['type']}\nValue: {reward['value']}",
            inline=False
        )

    await ctx.send(embed=embed)

@bot.command(name='claim')
async def claim_reward(ctx, streak_length: int):
    """Claim a streak reward"""
    success, reward = await goal_manager.claim_reward(ctx.author.id, streak_length)
    if not success:
        await ctx.send(reward)
        return

    embed = discord.Embed(
        title="Reward Claimed Successfully",
        description=f"Type: {reward['type']}\nValue: {reward['value']}",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name='liveleaderboard')
async def live_leaderboard(ctx, contest_id: int):
    """Start a live leaderboard for a contest"""
    # Check if contest exists and is running
    success, status = await contest_manager.get_contest_status(contest_id)
    if not success:
        await ctx.send(status)
        return

    if status['status'] != 'running':
        await ctx.send("Live leaderboard can only be started for a running contest.")
        return

    # Generate and send initial leaderboard embed (similar to conteststatus)
    embed = discord.Embed(
        title=f"Live Leaderboard: {status['name']}",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="Status",
        value=status['status'],
        inline=True
    )

    embed.add_field(
        name="Start Time",
        value=status['start_time'].strftime("%Y-%m-%d %H:%M:%S UTC"),
        inline=True
    )

    embed.add_field(
        name="End Time",
        value=status['end_time'].strftime("%Y-%m-%d %H:%M:%S UTC"),
        inline=True
    )

    embed.add_field(
        name="Participants",
        value=str(len(status['participants'])),
        inline=True
    )

    if status['participants']:
        participants_list = "\n".join(
            f"{i+1}. {p['handle']}: {p['score']} points"
            for i, p in enumerate(status['participants'])
        )
        embed.add_field(
            name="Current Rankings",
            value=participants_list,
            inline=False
        )

    # Add a note about live updates
    embed.set_footer(text="This leaderboard will update automatically.")

    # Send the message and store its ID
    leaderboard_message = await ctx.send(embed=embed)

    # Store the message ID and channel ID in the database
    conn = get_db_connection()
    konnet = conn.konnet()
    konnet.execute(
        "UPDATE contests SET leaderboard_message_id = ?, channel_id = ? WHERE id = ?",
        (leaderboard_message.id, ctx.channel.id, contest_id)
    )
    conn.commit()
    conn.close()

    await ctx.send(f"Live leaderboard started for Contest ID: {contest_id}")

# Task to update live leaderboards
@tasks.loop(seconds=60)  # Update every 60 seconds
async def update_live_leaderboards():
    conn = get_db_connection()
    konnet = conn.konnet()
    # Fetch contests with a live leaderboard message ID and status is running
    konnet.execute("SELECT id, leaderboard_message_id, channel_id FROM contests WHERE leaderboard_message_id IS NOT NULL AND status = 'running'")
    contests_to_update = konnet.fetchall()
    conn.close()

    for contest in contests_to_update:
        contest_id = contest['id']
        message_id = contest['leaderboard_message_id']
        channel_id = contest['channel_id']

        # Fetch participants for the contest
        conn = get_db_connection()
        konnet = conn.konnet()
        konnet.execute("SELECT cp.discord_id, u.cf_handle FROM contest_participants cp JOIN users u ON cp.discord_id = u.discord_id WHERE cp.contest_id = ? AND u.cf_handle IS NOT NULL", (contest_id,))
        participants = konnet.fetchall()
        conn.close()

        # Fetch and process new submissions for each participant
        for participant in participants:
            user_id = participant['discord_id']
            cf_handle = participant['cf_handle']

            if cf_handle:
                # Fetch recent submissions (last 10)
                submissions = await CodeforcesAPI.get_user_submissions(cf_handle)

                if submissions:
                    # Limit to recent submissions (last 10)
                    recent_submissions = submissions[:10] # Limit to last 10 submissions

                    # Get contest start and end times
                    conn = get_db_connection()
                    konnet = conn.konnet()
                    konnet.execute("SELECT start_time, end_time FROM contests WHERE id = ?", (contest_id,))
                    contest_times = konnet.fetchone()
                    conn.close()

                    if contest_times and contest_times['start_time'] and contest_times['end_time']:
                        contest_start_time = datetime.fromisoformat(contest_times['start_time'])
                        contest_end_time = datetime.fromisoformat(contest_times['end_time'])

                        for submission in recent_submissions:
                            submission_time = datetime.fromtimestamp(submission["creationTimeSeconds"])

                            # Check if submission is within contest time and is an AC
                            if contest_start_time <= submission_time <= contest_end_time and submission["verdict"] == "OK":
                                problem_id = f"{submission['problem']['contestId']}{submission['problem']['index']}"

                                # Check if the problem is part of this contest
                                conn = get_db_connection()
                                konnet = conn.konnet()
                                konnet.execute("SELECT 1 FROM contest_problems WHERE contest_id = ? AND problem_id = ?", (contest_id, problem_id))
                                is_contest_problem = konnet.fetchone()
                                conn.close()

                                if is_contest_problem:
                                    # Track the submission and update scores
                                    await contest_manager.track_submission(contest_id, user_id, submission)
                                    # Update scores will be called after processing all submissions for a participant

        # After processing submissions for all participants, update scores and leaderboard message
        for contest in contests_to_update:
             contest_id = contest['id']
             message_id = contest['leaderboard_message_id']
             channel_id = contest['channel_id']

             # Update scores for all participants in the contest
             await contest_manager.update_contest_scores(contest_id)

             # Fetch latest contest status to update leaderboard message
             success, status = await contest_manager.get_contest_status(contest_id)
             if not success:
                 print(f"Failed to fetch status for contest {contest_id}: {status}")
                 continue

             # Fetch the channel and message
             channel = bot.get_channel(channel_id)
             if not channel:
                 print(f"Channel with ID {channel_id} not found for updating leaderboard.")
                 continue

             try:
                 message = await channel.fetch_message(message_id)
             except discord.NotFound:
                 print(f"Leaderboard message with ID {message_id} not found in channel {channel_id}.")
                 # clear the leaderboard_message_id in the database if message is not found
                 continue

             # Update the embed message (similar to conteststatus command)
             embed = discord.Embed(
                 title=f"Live Leaderboard: {status['name']}",
                 color=discord.Color.blue()
             )

             embed.add_field(
                 name="Status",
                 value=status['status'],
                 inline=True
             )

             if status['start_time']:
                 embed.add_field(
                     name="Start Time",
                     value=status['start_time'].strftime("%Y-%m-%d %H:%M:%S UTC"),
                     inline=True
                 )

             if status['end_time']:
                 embed.add_field(
                     name="End Time",
                     value=status['end_time'].strftime("%Y-%m-%d %H:%M:%S UTC"),
                     inline=True
                 )

             embed.add_field(
                 name="Participants",
                 value=str(len(status['participants'])),
                 inline=True
             )

             if status['participants']:
                 participants_list = "\n".join(
                     f"{i+1}. {p['handle']}: {p['score']} points"
                     for i, p in enumerate(status['participants'])
                 )
                 embed.add_field(
                     name="Current Rankings",
                     value=participants_list,
                     inline=False
                 )

             # Add a note about live updates and last updated time
             embed.set_footer(text=f"Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")

             # Edit the message
             try:
                 await message.edit(embed=embed)
             except discord.Forbidden:
                 print(f"Bot does not have permissions to edit message {message_id} in channel {channel_id}.")
             except discord.NotFound:
                 print(f"Leaderboard message {message_id} not found for editing.")
             except Exception as e:
                 print(f"Error updating leaderboard message {message_id}: {e}")



# Start the bot
if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
