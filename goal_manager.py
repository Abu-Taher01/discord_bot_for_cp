import sqlite3
from datetime import datetime, timedelta
from codeforces_api import CodeforcesAPI
from db import get_db_connection

class GoalManager:
    def __init__(self):
        self.conn = get_db_connection()

    async def set_daily_goal(self, user_id: int, goal: int):
        """Set a user's daily problem-solving goal"""
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO daily_goals (discord_id, daily_goal, last_updated, penalties, streak, last_check) VALUES (?, ?, ?, 0, 0, ?)",
            (user_id, goal, datetime.utcnow(), datetime.utcnow())
        )
        self.conn.commit()
        return True, f"Daily goal set to {goal} problems"

    async def check_daily_progress(self, user_id: int):
        """Check user's progress towards daily goal"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT cf_handle FROM users WHERE discord_id = ?", (user_id,))
        user = cursor.fetchone()
        if not user:
            return False, "Please set your Codeforces handle first"

        cursor.execute("SELECT daily_goal FROM daily_goals WHERE discord_id = ?", (user_id,))
        goal_data = cursor.fetchone()
        if not goal_data:
            return False, "No daily goal set"

        submissions = await CodeforcesAPI.get_user_submissions(user['cf_handle'])
        if not submissions:
            return False, "Could not fetch submissions"

        today = datetime.utcnow().date()
        solved_today = CodeforcesAPI.calculate_daily_progress(submissions, today)

        cursor.execute("UPDATE daily_goals SET solved_today = ?, last_check = ? WHERE discord_id = ?", (solved_today, datetime.utcnow(), user_id))
        self.conn.commit()

        return True, {
            'goal': goal_data['daily_goal'],
            'solved': solved_today,
            'remaining': max(0, goal_data['daily_goal'] - solved_today)
        }

    async def apply_daily_penalties(self):
        """Apply penalties for missed daily goals"""
        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)
        cursor = self.conn.cursor()
        cursor.execute("SELECT discord_id, daily_goal FROM daily_goals")
        goals = cursor.fetchall()
        for goal in goals:
            user_id = goal['discord_id']
            cursor.execute("SELECT cf_handle FROM users WHERE discord_id = ?", (user_id,))
            user = cursor.fetchone()
            if not user:
                continue

            submissions = await CodeforcesAPI.get_user_submissions(user['cf_handle'])
            if not submissions:
                continue

            solved_yesterday = CodeforcesAPI.calculate_daily_progress(submissions, yesterday)
            if solved_yesterday < goal['daily_goal']:
                cursor.execute("UPDATE daily_goals SET penalties = penalties + 1, streak = 0, last_penalty = ? WHERE discord_id = ?", (datetime.utcnow(), user_id))
            else:
                cursor.execute("UPDATE daily_goals SET streak = streak + 1 WHERE discord_id = ?", (user_id,))
        self.conn.commit()

    async def get_user_stats(self, user_id: int):
        """Get user's goal statistics"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT daily_goal, penalties, streak, last_penalty, last_check FROM daily_goals WHERE discord_id = ?", (user_id,))
        goal_data = cursor.fetchone()
        if not goal_data:
            return False, "No daily goal set"

        cursor.execute("SELECT cf_handle FROM users WHERE discord_id = ?", (user_id,))
        user = cursor.fetchone()
        if not user:
            return False, "Please set your Codeforces handle first"

        submissions = await CodeforcesAPI.get_user_submissions(user['cf_handle'])
        if not submissions:
            return False, "Could not fetch submissions"

        today = datetime.utcnow().date()
        solved_today = CodeforcesAPI.calculate_daily_progress(submissions, today)

        return True, {
            'goal': goal_data['daily_goal'],
            'solved_today': solved_today,
            'penalties': goal_data['penalties'],
            'streak': goal_data['streak'],
            'last_penalty': goal_data['last_penalty'],
            'last_check': goal_data['last_check']
        } 