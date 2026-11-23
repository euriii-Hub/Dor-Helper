import os
import asyncio

import discord
from discord.ext import commands
from dotenv import load_dotenv

from database import (
    initialize_database,
    get_payment_count,
    get_vouch_count,
)

from ticket import (
    setup_ticket,
    TicketPanel,
    TicketControlView,
)

from vouch import (
    register_vouch_views,
)


# =========================================================
# ENV
# =========================================================

load_dotenv()

TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise RuntimeError(
        "❌ TOKEN tidak ditemukan.\n"
        "Pastikan TOKEN sudah ada di file .env"
    )


# =========================================================
# INTENTS
# =========================================================

intents = discord.Intents.default()

# Wajib untuk membaca member server
# dan memasukkan Owner / Mod ke private thread.
intents.members = True

# Wajib untuk command prefix seperti !ticket
intents.message_content = True

# Wajib untuk informasi guild/server
intents.guilds = True


# =========================================================
# BOT
# =========================================================

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
)


# =========================================================
# CHECK CHANNEL
# =========================================================

@bot.command(name="checkchannel")
@commands.has_permissions(administrator=True)
async def checkchannel(ctx):

    from config import TICKET_PARENT_ID

    channel = bot.get_channel(
        TICKET_PARENT_ID
    )

    if channel is None:

        try:

            channel = await bot.fetch_channel(
                TICKET_PARENT_ID
            )

        except Exception as error:

            await ctx.send(
                (
                    "❌ Channel tidak ditemukan.\n"
                    f"ID: `{TICKET_PARENT_ID}`\n"
                    f"Error: `{error}`"
                )
            )

            return

    await ctx.send(
        (
            "🔎 **Channel Check**\n\n"
            f"**Name:** `{channel.name}`\n"
            f"**ID:** `{channel.id}`\n"
            f"**Type:** `{type(channel).__name__}`\n"
            f"**Is TextChannel:** "
            f"`{isinstance(channel, discord.TextChannel)}`"
        )
    )


# =========================================================
# ROTATING STATUS
# =========================================================

async def rotate_status():

    await bot.wait_until_ready()

    statuses = [
        "payment",
        "vouch",
        "order",
    ]

    index = 0

    while not bot.is_closed():

        try:

            status_type = statuses[index]

            # =================================================
            # PAYMENT
            # =================================================

            if status_type == "payment":

                payment_count = get_payment_count()

                activity = discord.CustomActivity(
                    name=f"💰 {payment_count} Payments"
                )

            # =================================================
            # VOUCH
            # =================================================

            elif status_type == "vouch":

                vouch_count = get_vouch_count()

                activity = discord.CustomActivity(
                    name=f"⭐ {vouch_count} Vouches"
                )

            # =================================================
            # ORDER HERE
            # =================================================

            else:

                activity = discord.CustomActivity(
                    name="🎫 Order Here"
                )

            await bot.change_presence(
                status=discord.Status.online,
                activity=activity,
            )

        except Exception as error:

            print(
                f"⚠️ Status error: {error}"
            )

        index = (
            index + 1
        ) % len(statuses)

        await asyncio.sleep(15)


# =========================================================
# READY
# =========================================================

@bot.event
async def on_ready():

    print("===============================")
    print(f"✅ Bot online : {bot.user}")
    print(f"🆔 Bot ID     : {bot.user.id}")
    print("===============================")

    # =====================================================
    # START STATUS LOOP ONLY ONCE
    # =====================================================

    if not hasattr(
        bot,
        "_status_task_started"
    ):

        bot._status_task_started = True

        asyncio.create_task(
            rotate_status()
        )


# =========================================================
# TEST COMMAND
# =========================================================

@bot.command(name="test")
@commands.has_permissions(
    administrator=True
)
async def test(
    ctx: commands.Context
):

    await ctx.send(
        "✅ **Dor's STORE Ticket Bot aktif!**"
    )


# =========================================================
# INITIALIZE DATABASE
# =========================================================

initialize_database()


# =========================================================
# SETUP TICKET SYSTEM
# =========================================================

setup_ticket(
    bot
)


# =========================================================
# PERSISTENT TICKET PANEL
# =========================================================

bot.add_view(
    TicketPanel()
)


# =========================================================
# PERSISTENT TICKET CONTROL
# =========================================================

bot.add_view(
    TicketControlView()
)


# =========================================================
# PERSISTENT VOUCH BUTTONS
# =========================================================

register_vouch_views(
    bot
)


# =========================================================
# START BOT
# =========================================================

bot.run(
    TOKEN
)