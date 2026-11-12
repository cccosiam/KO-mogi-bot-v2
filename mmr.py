import asyncio
import traceback
from typing import List

import discord
import gspread
from google.oauth2.service_account import Credentials

from mogi_objects import Player
import common

SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
SHEET_CLIENTS: dict[str, gspread.Client] = {}


class RatingsNotReady(Exception):
    pass


class Ratings:
    def __init__(self):
        self.first_run_complete = False
        self.ratings: dict[str, tuple[int, str]] = {}

    async def update_ratings(self):
        try:
            ratings = await asyncio.to_thread(self._pull_sheet_ratings)
        except Exception:
            print("Failed to pull ratings from Google Sheets.", flush=True)
            print(traceback.format_exc(), flush=True)
            return
        self.ratings = ratings
        self.first_run_complete = True

    def _pull_sheet_ratings(self) -> dict[str, tuple[int, str]]:
        credentials_file = common.CONFIG["MMR_SERVICE_ACCOUNT_FILE"]
        client = SHEET_CLIENTS.get(credentials_file)
        if client is None:
            credentials = Credentials.from_service_account_file(
                credentials_file, scopes=SHEETS_SCOPES)
            client = gspread.authorize(credentials)
            SHEET_CLIENTS[credentials_file] = client

        worksheet = client.open_by_key(
            common.CONFIG["MMR_SPREADSHEET_ID"]
        ).worksheet(common.CONFIG["MMR_WORKSHEET_NAME"])
        ratings = {}
        for row in worksheet.get_all_values()[1:]:
            if len(row) < 5:
                continue
            name = row[0].strip()
            if not name:
                continue
            try:
                rating = int(row[4].strip())
            except ValueError:
                continue
            ratings[name.casefold()] = (rating, name)
        return ratings

    def get_rating_for_member(
            self, member: discord.Member | discord.User) -> int | None:
        if not self.first_run_complete:
            raise RatingsNotReady("Ratings not pulled yet.")
        name = getattr(member, "display_name", member.name).strip().casefold()
        rating = self.ratings.get(name)
        return rating[0] if rating is not None else None

    def get_rating(
            self, members: List[discord.User | discord.Member]) -> List[Player]:
        if not self.first_run_complete:
            raise RatingsNotReady("Ratings not pulled yet.")
        all_players = []
        for member in members:
            name = getattr(member, "display_name", member.name).strip().casefold()
            if name not in self.ratings:
                continue
            rating, sheet_name = self.ratings[name]
            all_players.append(Player(member, sheet_name, rating))
        return all_players
