import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict
import random
from codeforces_api import CodeforcesAPI
from db import get_db_connection

class ContestManager:
    def __init__(self):
        self.conn = get_db_connection()

    async def create_contest(self, name: str, duration: str, created_by: int, problems: List[Dict] = None):
        """Create a new contest"""
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO contests (name, duration, created_by, created_at, status) VALUES (?, ?, ?, ?, ?)",
            (name, duration, created_by, datetime.utcnow(), 'active')
        )
        self.conn.commit()
        return cursor.lastrowid

    async def join_contest(self, contest_id: int, user_id: int):
        """Add a user to a contest"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT status FROM contests WHERE id = ?", (contest_id,))
        contest = cursor.fetchone()
        if not contest:
            return False, "Contest not found"
        if contest['status'] != 'active':
            return False, "Contest is not active"
        cursor.execute("INSERT INTO contest_participants (contest_id, discord_id) VALUES (?, ?)", (contest_id, user_id))
        self.conn.commit()
        return True, "Successfully joined the contest"

    async def start_contest(self, contest_id: int):
        """Start a contest"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT status FROM contests WHERE id = ?", (contest_id,))
        contest = cursor.fetchone()
        if not contest:
            return False, "Contest not found"
        if contest['status'] != 'active':
            return False, "Contest is not active"
        start_time = datetime.utcnow()
        duration = self._parse_duration(contest['duration'])
        end_time = start_time + duration
        cursor.execute("UPDATE contests SET status = ?, start_time = ?, end_time = ? WHERE id = ?", ('running', start_time, end_time, contest_id))
        self.conn.commit()
        return True, "Contest started successfully"

    async def end_contest(self, contest_id: int):
        """End a contest and calculate results"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT status FROM contests WHERE id = ?", (contest_id,))
        contest = cursor.fetchone()
        if not contest:
            return False, "Contest not found"
        if contest['status'] != 'running':
            return False, "Contest is not running"
        cursor.execute("SELECT discord_id FROM contest_participants WHERE contest_id = ?", (contest_id,))
        participants = cursor.fetchall()
        results = []
        for participant in participants:
            user_id = participant['discord_id']
            cursor.execute("SELECT cf_handle FROM users WHERE discord_id = ?", (user_id,))
            user = cursor.fetchone()
            if not user:
                continue
            submissions = await CodeforcesAPI.get_user_submissions(user['cf_handle'])
            if not submissions:
                continue
            score = self._calculate_contest_score(submissions, contest['start_time'], contest['end_time'], contest['problems'])
            results.append({'user_id': user_id, 'handle': user['cf_handle'], 'score': score})
        results.sort(key=lambda x: x['score'], reverse=True)
        cursor.execute("UPDATE contests SET status = ? WHERE id = ?", ('ended', contest_id))
        self.conn.commit()
        return True, "Contest ended successfully"

    def _parse_duration(self, duration: str) -> timedelta:
        """Parse duration string into timedelta"""
        value = int(duration[:-1])
        unit = duration[-1].lower()
        if unit == 'h':
            return timedelta(hours=value)
        elif unit == 'm':
            return timedelta(minutes=value)
        elif unit == 'd':
            return timedelta(days=value)
        else:
            return timedelta(hours=1)

    def _calculate_contest_score(self, submissions, start_time, end_time, problems):
        """Calculate user's score for the contest"""
        score = 0
        solved_problems = set()
        for submission in submissions:
            submission_time = datetime.fromtimestamp(submission["creationTimeSeconds"])
            if not (start_time <= submission_time <= end_time):
                continue
            problem_id = f"{submission['problem']['contestId']}{submission['problem']['index']}"
            if problem_id not in solved_problems and submission["verdict"] == "OK":
                solved_problems.add(problem_id)
                if "rating" in submission["problem"]:
                    score += submission["problem"]["rating"] // 100
        return score 