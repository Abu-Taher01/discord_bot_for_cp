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
                'startcontest', 'endcontest', 'conteststatus', 'contests'
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
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO users (discord_id, cf_handle) VALUES (?, ?)",
            (ctx.author.id, handle)
        )
        conn.commit()
        conn.close()
        await ctx.send(f'Codeforces handle set to {handle}!')
    
    elif action == 'stats':
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT cf_handle FROM users WHERE discord_id = ?", (ctx.author.id,))
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            await ctx.send('Please set your Codeforces handle first using `!cf set <handle>`')
            return
        
        # Get user's submissions and calculate statistics
        submissions = await CodeforcesAPI.get_user_submissions(user['cf_handle'])
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

@bot.command(name='contest')
async def contest(ctx, action: str, *args):
    """Contest management commands"""
    if action == 'create':
        if len(args) < 2:
            await ctx.send('Please provide contest name and duration!')
            return
        
        name = args[0]
        duration = args[1]
        
        # Create new contest
        contest_id = await contest_manager.create_contest(name, duration, ctx.author.id)
        await ctx.send(f'Contest created! ID: {contest_id}')
    
    elif action == 'join':
        if not args:
            await ctx.send('Please provide contest ID!')
            return
        
        contest_id = int(args[0])
        success, message = await contest_manager.join_contest(contest_id, ctx.author.id)
        await ctx.send(message)
    
    elif action == 'start':
        if not args:
            await ctx.send('Please provide contest ID!')
            return
        
        contest_id = int(args[0])
        success, message = await contest_manager.start_contest(contest_id)
        await ctx.send(message)
    
    elif action == 'end':
        if not args:
            await ctx.send('Please provide contest ID!')
            return
        
        contest_id = int(args[0])
        success, message = await contest_manager.end_contest(contest_id)
        if success:
            # Get contest results
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM contests WHERE id = ?", (contest_id,))
            contest = cursor.fetchone()
            
            if contest:
                embed = discord.Embed(
                    title=f'Contest Results: {contest["name"]}',
                    color=discord.Color.green()
                )
                
                cursor.execute("""
                    SELECT u.cf_handle, cp.score
                    FROM contest_participants cp
                    JOIN users u ON cp.discord_id = u.discord_id
                    WHERE cp.contest_id = ?
                    ORDER BY cp.score DESC
                """, (contest_id,))
                
                results = cursor.fetchall()
                for i, result in enumerate(results, 1):
                    embed.add_field(
                        name=f'{i}. {result["cf_handle"]}',
                        value=f'Score: {result["score"]}',
                        inline=False
                    )
                
                await ctx.send(embed=embed)
            conn.close()
        else:
            await ctx.send(message)
    
    elif action == 'list':
        # List active contests
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.*, COUNT(cp.discord_id) as participant_count
            FROM contests c
            LEFT JOIN contest_participants cp ON c.id = cp.contest_id
            WHERE c.status = 'active'
            GROUP BY c.id
        """)
        active_contests = cursor.fetchall()
        conn.close()
        
        if not active_contests:
            await ctx.send('No active contests found!')
            return
        
        embed = discord.Embed(title='Active Contests', color=discord.Color.blue())
        for contest in active_contests:
            embed.add_field(
                name=contest['name'],
                value=f'ID: {contest["id"]}\nDuration: {contest["duration"]}\nParticipants: {contest["participant_count"]}',
                inline=False
            )
        await ctx.send(embed=embed)

@bot.command(name='goal')
async def goal(ctx, action: str, number: int = None):
    """Daily goal management commands"""
    if action == 'set':
        if not number:
            await ctx.send('Please provide a number of problems to solve daily!')
            return
        
        success, message = await goal_manager.set_daily_goal(ctx.author.id, number)
        await ctx.send(message)
    
    elif action == 'status':
        success, result = await goal_manager.check_daily_progress(ctx.author.id)
        if not success:
            await ctx.send(result)
            return
        
        embed = discord.Embed(
            title='Daily Goal Progress',
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name='Goal',
            value=str(result['goal']),
            inline=True
        )
        embed.add_field(
            name='Solved Today',
            value=str(result['solved']),
            inline=True
        )
        embed.add_field(
            name='Remaining',
            value=str(result['remaining']),
            inline=True
        )
        
        await ctx.send(embed=embed)
    
    elif action == 'stats':
        success, stats = await goal_manager.get_user_stats(ctx.author.id)
        if not success:
            await ctx.send(stats)
            return
        
        embed = discord.Embed(
            title='Goal Statistics',
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name='Current Streak',
            value=str(stats['streak']),
            inline=True
        )
        embed.add_field(
            name='Total Penalties',
            value=str(stats['penalties']),
            inline=True
        )
        embed.add_field(
            name='Last Penalty',
            value=stats['last_penalty'].strftime('%Y-%m-%d %H:%M:%S') if stats['last_penalty'] else 'None',
            inline=True
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
    cursor = conn.cursor()
    cursor.execute("SELECT discord_id, cf_handle FROM users WHERE cf_handle IS NOT NULL")
    users = cursor.fetchall()
    
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
        cursor.execute("SELECT streak, penalties FROM daily_goals WHERE discord_id = ?", (user['discord_id'],))
        goal_data = cursor.fetchone()
        
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
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO users (discord_id, timezone)
            VALUES (?, ?)
        ''', (ctx.author.id, timezone))
        conn.commit()
        conn.close()
        
        await ctx.send(f"✅ Your timezone has been set to {timezone}")
    except pytz.exceptions.UnknownTimeZoneError:
        await ctx.send("❌ Invalid timezone. Please use a valid timezone (e.g., 'UTC', 'America/New_York')")

# Start the bot
if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
