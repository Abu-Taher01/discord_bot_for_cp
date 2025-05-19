import sqlite3
from datetime import datetime, timedelta
import pytz
from typing import Dict, List, Optional, Tuple
import asyncio
import discord
from discord.ext import commands, tasks

class GoalManager:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.conn = sqlite3.connect('codeforces_bot.db')
        self.conn.row_factory = sqlite3.Row
        self.check_goals.start()
        self.send_reminders.start()

    def cog_unload(self):
        self.check_goals.cancel()
        self.send_reminders.cancel()

    async def set_goal(self, discord_id: int, daily_goal: int, weekly_goal: Optional[int] = None, 
                      monthly_goal: Optional[int] = None, reminder_time: Optional[str] = None) -> bool:
        """Set goals for a user."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO daily_goals 
                (discord_id, daily_goal, weekly_goal, monthly_goal, last_updated, reminder_time)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (discord_id, daily_goal, weekly_goal, monthly_goal, datetime.utcnow(), reminder_time))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error setting goal: {e}")
            return False

    async def set_category_goal(self, discord_id: int, category_type: str, 
                              category_value: str, goal_count: int) -> bool:
        """Set a goal for a specific category (e.g., difficulty rating)."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO goal_categories 
                (discord_id, category_type, category_value, goal_count, last_updated)
                VALUES (?, ?, ?, ?, ?)
            ''', (discord_id, category_type, category_value, goal_count, datetime.utcnow()))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error setting category goal: {e}")
            return False

    async def update_progress(self, discord_id: int, solved_count: int, 
                            category_solves: Dict[str, Dict[str, int]]) -> None:
        """Update user's progress towards their goals."""
        try:
            cursor = self.conn.cursor()
            now = datetime.utcnow()
            
            # Get user's timezone
            cursor.execute('SELECT timezone FROM users WHERE discord_id = ?', (discord_id,))
            user = cursor.fetchone()
            timezone = pytz.timezone(user['timezone'] if user else 'UTC')
            user_time = now.astimezone(timezone)
            
            # Update daily progress
            if user_time.hour < 4:  # Before 4 AM in user's timezone
                yesterday = user_time - timedelta(days=1)
                cursor.execute('''
                    UPDATE daily_goals 
                    SET solved_today = solved_today + ?,
                        solved_this_week = solved_this_week + ?,
                        solved_this_month = solved_this_month + ?
                    WHERE discord_id = ?
                ''', (solved_count, solved_count, solved_count, discord_id))
            else:
                cursor.execute('''
                    UPDATE daily_goals 
                    SET solved_today = solved_today + ?,
                        solved_this_week = solved_this_week + ?,
                        solved_this_month = solved_this_month + ?
                    WHERE discord_id = ?
                ''', (solved_count, solved_count, solved_count, discord_id))

            # Update category progress
            for cat_type, cat_values in category_solves.items():
                for cat_value, count in cat_values.items():
                    cursor.execute('''
                        UPDATE goal_categories 
                        SET current_count = current_count + ?
                        WHERE discord_id = ? AND category_type = ? AND category_value = ?
                    ''', (count, discord_id, cat_type, cat_value))

            self.conn.commit()
        except Exception as e:
            print(f"Error updating progress: {e}")

    async def check_goal_completion(self, discord_id: int) -> Dict[str, bool]:
        """Check if user has completed their goals."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT daily_goal, weekly_goal, monthly_goal, solved_today, 
                       solved_this_week, solved_this_month
                FROM daily_goals
                WHERE discord_id = ?
            ''', (discord_id,))
            goals = cursor.fetchone()
            
            if not goals:
                return {}

            return {
                'daily': goals['solved_today'] >= goals['daily_goal'],
                'weekly': goals['weekly_goal'] and goals['solved_this_week'] >= goals['weekly_goal'],
                'monthly': goals['monthly_goal'] and goals['solved_this_month'] >= goals['monthly_goal']
            }
        except Exception as e:
            print(f"Error checking goal completion: {e}")
            return {}

    async def get_streak_info(self, discord_id: int) -> Dict[str, int]:
        """Get user's streak information."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT streak, best_streak, penalties
                FROM daily_goals
                WHERE discord_id = ?
            ''', (discord_id,))
            streak_info = cursor.fetchone()
            
            return {
                'current_streak': streak_info['streak'] if streak_info else 0,
                'best_streak': streak_info['best_streak'] if streak_info else 0,
                'penalties': streak_info['penalties'] if streak_info else 0
            }
        except Exception as e:
            print(f"Error getting streak info: {e}")
            return {'current_streak': 0, 'best_streak': 0, 'penalties': 0}

    async def get_goal_history(self, discord_id: int, days: int = 30) -> List[Dict]:
        """Get user's goal completion history."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT date, goal_type, target, achieved, streak
                FROM goal_history
                WHERE discord_id = ? AND date >= date('now', ?)
                ORDER BY date DESC
            ''', (discord_id, f'-{days} days'))
            
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting goal history: {e}")
            return []

    @tasks.loop(hours=1)
    async def check_goals(self):
        """Periodically check goals and update streaks."""
        try:
            cursor = self.conn.cursor()
            now = datetime.utcnow()
            
            # Get all users with goals
            cursor.execute('''
                SELECT d.discord_id, d.daily_goal, d.solved_today, d.streak, d.best_streak,
                       d.last_check, u.timezone
                FROM daily_goals d
                JOIN users u ON d.discord_id = u.discord_id
            ''')
            
            for user in cursor.fetchall():
                timezone = pytz.timezone(user['timezone'])
                user_time = now.astimezone(timezone)
                
                # Check if it's a new day (after 4 AM in user's timezone)
                if user_time.hour >= 4 and (
                    not user['last_check'] or 
                    (now - datetime.fromisoformat(user['last_check'])).days >= 1
                ):
                    # Update streak
                    if user['solved_today'] >= user['daily_goal']:
                        new_streak = user['streak'] + 1
                        best_streak = max(new_streak, user['best_streak'])
                        
                        # Check for streak rewards
                        if new_streak % 7 == 0:  # Weekly streak milestone
                            await self.create_streak_reward(user['discord_id'], new_streak)
                    else:
                        new_streak = 0
                        best_streak = user['best_streak']
                    
                    # Record goal history
                    cursor.execute('''
                        INSERT INTO goal_history 
                        (discord_id, date, goal_type, target, achieved, streak)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (user['discord_id'], now.date(), 'daily', 
                         user['daily_goal'], user['solved_today'], new_streak))
                    
                    # Reset daily count and update streak
                    cursor.execute('''
                        UPDATE daily_goals
                        SET solved_today = 0,
                            streak = ?,
                            best_streak = ?,
                            last_check = ?
                        WHERE discord_id = ?
                    ''', (new_streak, best_streak, now.isoformat(), user['discord_id']))
            
            self.conn.commit()
        except Exception as e:
            print(f"Error in check_goals: {e}")

    @tasks.loop(minutes=30)
    async def send_reminders(self):
        """Send reminders to users based on their reminder time."""
        try:
            cursor = self.conn.cursor()
            now = datetime.utcnow()
            
            # Get users who have reminders set
            cursor.execute('''
                SELECT d.discord_id, d.reminder_time, d.solved_today, d.daily_goal,
                       u.timezone
                FROM daily_goals d
                JOIN users u ON d.discord_id = u.discord_id
                WHERE d.reminder_time IS NOT NULL
            ''')
            
            for user in cursor.fetchall():
                timezone = pytz.timezone(user['timezone'])
                user_time = now.astimezone(timezone)
                reminder_hour = int(user['reminder_time'].split(':')[0])
                
                if user_time.hour == reminder_hour and user['solved_today'] < user['daily_goal']:
                    try:
                        member = await self.bot.fetch_user(user['discord_id'])
                        remaining = user['daily_goal'] - user['solved_today']
                        await member.send(
                            f"Reminder: You still need to solve {remaining} more problems "
                            f"to reach your daily goal of {user['daily_goal']} problems!"
                        )
                    except Exception as e:
                        print(f"Error sending reminder to {user['discord_id']}: {e}")
        
        except Exception as e:
            print(f"Error in send_reminders: {e}")

    async def create_streak_reward(self, discord_id: int, streak_length: int) -> None:
        """Create a reward for reaching a streak milestone."""
        try:
            cursor = self.conn.cursor()
            
            # Define rewards based on streak length
            if streak_length % 7 == 0:  # Weekly streak
                reward_type = "weekly"
                reward_value = streak_length // 7
            elif streak_length % 30 == 0:  # Monthly streak
                reward_type = "monthly"
                reward_value = streak_length // 30
            else:
                return
            
            cursor.execute('''
                INSERT OR REPLACE INTO streak_rewards
                (discord_id, streak_length, reward_type, reward_value)
                VALUES (?, ?, ?, ?)
            ''', (discord_id, streak_length, reward_type, reward_value))
            
            self.conn.commit()
            
            # Notify user
            try:
                member = await self.bot.fetch_user(discord_id)
                await member.send(
                    f"🎉 Congratulations! You've reached a {streak_length}-day streak! "
                    f"You've earned a {reward_type} reward!"
                )
            except Exception as e:
                print(f"Error notifying user about reward: {e}")
                
        except Exception as e:
            print(f"Error creating streak reward: {e}")

    async def claim_streak_reward(self, discord_id: int, streak_length: int) -> bool:
        """Allow a user to claim their streak reward."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE streak_rewards
                SET claimed = TRUE, claimed_at = ?
                WHERE discord_id = ? AND streak_length = ? AND claimed = FALSE
            ''', (datetime.utcnow(), discord_id, streak_length))
            
            if cursor.rowcount > 0:
                self.conn.commit()
                return True
            return False
        except Exception as e:
            print(f"Error claiming streak reward: {e}")
            return False

    async def get_available_rewards(self, discord_id: int) -> List[Dict]:
        """Get list of available rewards for a user."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT streak_length, reward_type, reward_value
                FROM streak_rewards
                WHERE discord_id = ? AND claimed = FALSE
                ORDER BY streak_length
            ''', (discord_id,))
            
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting available rewards: {e}")
            return []

class Goals(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.goal_manager = GoalManager(bot)

    @commands.command()
    async def setgoal(self, ctx, daily: int, weekly: Optional[int] = None, 
                     monthly: Optional[int] = None, reminder_time: Optional[str] = None):
        """Set your daily, weekly, and monthly goals."""
        if daily < 1:
            await ctx.send("Daily goal must be at least 1 problem.")
            return
        
        if weekly is not None and weekly < daily:
            await ctx.send("Weekly goal must be greater than or equal to daily goal.")
            return
            
        if monthly is not None and monthly < weekly:
            await ctx.send("Monthly goal must be greater than or equal to weekly goal.")
            return
            
        if reminder_time:
            try:
                hour = int(reminder_time.split(':')[0])
                if not (0 <= hour <= 23):
                    raise ValueError
            except ValueError:
                await ctx.send("Invalid reminder time format. Use HH:MM (24-hour format).")
                return
        
        success = await self.goal_manager.set_goal(
            ctx.author.id, daily, weekly, monthly, reminder_time
        )
        
        if success:
            msg = f"✅ Goals set successfully!\nDaily: {daily} problems"
            if weekly:
                msg += f"\nWeekly: {weekly} problems"
            if monthly:
                msg += f"\nMonthly: {monthly} problems"
            if reminder_time:
                msg += f"\nReminder time: {reminder_time}"
            await ctx.send(msg)
        else:
            await ctx.send("❌ Failed to set goals. Please try again.")

    @commands.command()
    async def setcategorygoal(self, ctx, category_type: str, category_value: str, count: int):
        """Set a goal for a specific category (e.g., difficulty rating)."""
        if count < 1:
            await ctx.send("Goal count must be at least 1.")
            return
            
        success = await self.goal_manager.set_category_goal(
            ctx.author.id, category_type, category_value, count
        )
        
        if success:
            await ctx.send(
                f"✅ Category goal set successfully!\n"
                f"Category: {category_type} {category_value}\n"
                f"Goal: {count} problems"
            )
        else:
            await ctx.send("❌ Failed to set category goal. Please try again.")

    @commands.command()
    async def goals(self, ctx):
        """View your current goals and progress."""
        try:
            cursor = self.goal_manager.conn.cursor()
            
            # Get user's goals
            cursor.execute('''
                SELECT daily_goal, weekly_goal, monthly_goal, solved_today,
                       solved_this_week, solved_this_month, streak, best_streak
                FROM daily_goals
                WHERE discord_id = ?
            ''', (ctx.author.id,))
            goals = cursor.fetchone()
            
            if not goals:
                await ctx.send("You haven't set any goals yet. Use `!setgoal` to set your goals.")
                return
            
            # Get category goals
            cursor.execute('''
                SELECT category_type, category_value, goal_count, current_count
                FROM goal_categories
                WHERE discord_id = ?
            ''', (ctx.author.id,))
            category_goals = cursor.fetchall()
            
            # Build response message
            msg = "📊 **Your Goals and Progress**\n\n"
            
            # Daily goals
            msg += f"**Daily Goal:** {goals['solved_today']}/{goals['daily_goal']} problems\n"
            if goals['weekly_goal']:
                msg += f"**Weekly Goal:** {goals['solved_this_week']}/{goals['weekly_goal']} problems\n"
            if goals['monthly_goal']:
                msg += f"**Monthly Goal:** {goals['solved_this_month']}/{goals['monthly_goal']} problems\n"
            
            # Streak information
            msg += f"\n**Current Streak:** {goals['streak']} days\n"
            msg += f"**Best Streak:** {goals['best_streak']} days\n"
            
            # Category goals
            if category_goals:
                msg += "\n**Category Goals:**\n"
                for cat in category_goals:
                    msg += f"{cat['category_type']} {cat['category_value']}: "
                    msg += f"{cat['current_count']}/{cat['goal_count']} problems\n"
            
            await ctx.send(msg)
            
        except Exception as e:
            print(f"Error in goals command: {e}")
            await ctx.send("❌ An error occurred while fetching your goals.")

    @commands.command()
    async def history(self, ctx, days: int = 7):
        """View your goal completion history."""
        if not 1 <= days <= 30:
            await ctx.send("Please specify a number of days between 1 and 30.")
            return
            
        history = await self.goal_manager.get_goal_history(ctx.author.id, days)
        
        if not history:
            await ctx.send("No history found for the specified period.")
            return
            
        msg = f"📅 **Goal History (Last {days} days)**\n\n"
        
        for entry in history:
            date = datetime.fromisoformat(entry['date']).strftime('%Y-%m-%d')
            msg += f"**{date}**\n"
            msg += f"Goal: {entry['goal_type']} ({entry['achieved']}/{entry['target']})\n"
            msg += f"Streak: {entry['streak']} days\n\n"
        
        await ctx.send(msg)

    @commands.command()
    async def rewards(self, ctx):
        """View your available streak rewards."""
        rewards = await self.goal_manager.get_available_rewards(ctx.author.id)
        
        if not rewards:
            await ctx.send("You don't have any available rewards.")
            return
            
        msg = "🎁 **Your Available Rewards**\n\n"
        
        for reward in rewards:
            msg += f"**{reward['streak_length']}-day Streak Reward**\n"
            msg += f"Type: {reward['reward_type']}\n"
            msg += f"Value: {reward['reward_value']}\n\n"
        
        await ctx.send(msg)

    @commands.command()
    async def claim(self, ctx, streak_length: int):
        """Claim a streak reward."""
        success = await self.goal_manager.claim_streak_reward(ctx.author.id, streak_length)
        
        if success:
            await ctx.send(f"✅ Successfully claimed your {streak_length}-day streak reward!")
        else:
            await ctx.send("❌ No unclaimed reward found for this streak length.")

def setup(bot: commands.Bot):
    bot.add_cog(Goals(bot)) 